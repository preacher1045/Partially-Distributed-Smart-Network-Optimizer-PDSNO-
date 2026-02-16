---
title: Threat Model & Security Mitigations
status: Reviewed
author: Alexander Adjei
last_updated: 2026-02-14
component: Security
depends_on: PROJECT_OVERVIEW.md, docs/security_model.md, docs/architecture/verification/controller_validation_sequence.md
---

# PDSNO — Threat Model & Mitigations

## 1. Purpose

This document identifies security threats, failure modes, and abuse scenarios in the PDSNO orchestration and approval systems, and describes the design-level mitigations for each.

It focuses on four categories of threat:

- Malicious external actors attempting to enter or manipulate the system
- Compromised controllers operating within the trust hierarchy
- Operational mistakes by legitimate administrators
- Distributed-system failure modes that create exploitable inconsistencies

---

## 2. Threat Assumptions

### What We Assume Can Happen

- Any controller at any tier can be compromised
- Network partitions will occur and may last for extended periods
- Administrators will make mistakes in configuration and approval
- Policies may drift temporarily across tiers during update propagation
- Attackers will attempt privilege escalation (claiming higher authority than granted)
- Replay attacks will be attempted against the validation and approval flows

### What We Do Not Assume

- A trusted, always-available internal network
- Perfect uptime for any component including the Global Controller
- Honest behavior from lower-tier controllers
- That audit logs stored locally by a compromised controller are trustworthy

---

## 3. Scope of This Document

**In scope:**

- Threats against the controller validation flow
- Threats against the configuration approval flow
- Threats against the NIB (state store)
- Threats arising from controller compromise at Local and Regional tiers

**Explicitly out of scope for v1:**

- Compromise of the **Global Controller** itself (see T10 below — this is acknowledged but deferred)
- Physical security of controller hosts
- Threats against the underlying network devices being orchestrated
- Insider threats from human administrators with legitimate access

These out-of-scope items are not ignored — they are tracked and will be addressed as the system matures. Deferring them is a conscious decision based on the current development phase, not a belief that they are unimportant.

---

## 4. Threat Scenarios & Mitigations

---

### T1 — Sensitivity Category Spoofing by Local Controller

**Description**
A Local Controller declares a high-risk configuration change as `LOW` sensitivity to bypass Regional or Global approval.

**Impact**
A dangerous config change is executed without appropriate oversight.

**Mitigation**
Regional and Global Controllers independently re-classify sensitivity based on their own policy evaluation and NIB data. A Local Controller's suggested sensitivity is treated as advisory input only, never as authoritative. If RC classification differs from LC suggestion by more than one level, an additional audit flag is raised.

**Residual Risk**
If both the LC and RC are compromised simultaneously, this mitigation fails. This is addressed by T6 (cross-region blast radius) and the Global Controller's independent validation for HIGH-sensitivity changes.

---

### T2 — Emergency Mode Abuse

**Description**
A controller repeatedly invokes emergency mode to bypass the normal approval flow.

**Impact**
Unapproved configuration changes accumulate; the audit trail becomes noisy and operators stop paying attention.

**Mitigation**
Emergency mode is rate-limited per controller (configurable via policy, default: 3 emergency invocations per hour). Emergency changes are restricted to specific config types (quarantine, rate-limit) and specific device roles (edge only). Every emergency invocation triggers an immediate, non-dismissible notification to Regional and Global Controllers. Repeated emergency invocations without corresponding post-facto approvals will trigger automatic controller suspension.

---

### T3 — Policy Version Drift

**Description**
A Local Controller submits a config request using an outdated policy version.

**Impact**
The config is evaluated against stale rules. A change that would be denied under the current policy may be approved under an old one.

**Mitigation**
Policy version is a required field in every config request. Regional Controllers reject any request whose `policy_version` does not match the current active version. Rejected requests receive a `POLICY_MISMATCH` response with the current version identifier so the LC can update and retry.

---

### T4 — Execution Token Replay

**Description**
A valid execution token is captured and reused to apply a configuration a second time, or to apply it to a different device.

**Impact**
Unauthorized configuration changes executed under a legitimate-appearing token.

**Mitigation**
Tokens are single-use. The NIB records token redemption. Any second use of the same token is rejected with a `TOKEN_ALREADY_USED` error and an audit flag. Tokens are also cryptographically bound to: the specific request ID, the config hash, the list of affected device IDs, the issuing controller ID, and an expiration timestamp. A token captured from one context cannot be applied in any other context.

---

### T5 — Partial Execution with Communication Failure

**Description**
A Local Controller applies a configuration but fails to report the result to the Regional Controller. The system's state is now inconsistent: the device has been reconfigured but the NIB still shows the old state.

**Impact**
Subsequent approval decisions are made based on incorrect state. Rollback decisions may be triggered incorrectly.

**Mitigation**
Local Controllers write execution state to their Local NIB first, before sending the upstream report. If the upstream report fails, the LC retries with exponential backoff. The Regional Controller initiates reconciliation if it does not receive an execution report within the expected window. No assumption-based state transitions are permitted — the system waits for confirmation or escalates.

---

### T6 — Concurrent Config Conflicts

**Description**
Two approved configuration changes targeting the same device are executed concurrently, with the second change overwriting the first in an unintended way.

**Impact**
The device ends up in a state that neither approval intended. Rollback becomes complicated because neither change knows about the other.

**Mitigation**
The Controller Sync Table implements per-device and per-config-section locking at approval time. A device lock is acquired when an approval is granted and held until execution is confirmed. A second request targeting the same device during an active lock receives a `DENY_CONFLICT` response and is queued or rejected based on policy. See the NIB specification for lock schema details.

---

### T7 — Rollback Failure

**Description**
A configuration change fails during execution, and the rollback of that change also fails. The device is left in an indeterminate state.

**Impact**
Network disruption continues. No automated recovery is possible.

**Mitigation**
A failed rollback transitions the device to `DEGRADED` state in the NIB, which blocks all further automated configuration changes for that device. An escalation is raised to the Regional and Global Controllers. The device remains in `DEGRADED` until an operator explicitly reviews and resolves the state. This is an intentional forcing function — it is better to block automation than to keep applying changes to a device in an unknown state.

---

### T8 — Forged Audit Logs

**Description**
A compromised Local Controller falsifies its execution reports or audit log entries to conceal unauthorized actions.

**Impact**
Malicious or erroneous changes go undetected. Forensics are compromised.

**Mitigation**
Audit log entries are signed by the originating controller. Regional and Global Controllers cross-validate audit entries against independent NIB state (device discovery records, config table state, lock table history). A discrepancy between what an LC reports and what the NIB independently records triggers an audit flag and may trigger controller suspension pending manual review.

Note: This mitigation assumes the Regional Controller is not also compromised. If both LC and RC are compromised simultaneously, log integrity at those tiers cannot be guaranteed. The Global Controller's independent audit aggregation provides a third check, but this is not a complete defense against coordinated compromise.

---

### T9 — Human Approval Errors

**Description**
An administrator approves a configuration change that is unsafe, without fully understanding its impact.

**Impact**
Damage caused by a change that passed all automated checks but was harmful.

**Mitigation**
Every approval request presented to a human reviewer must include: a computed blast radius (count and criticality of affected devices), a structured diff showing exactly what will change, an estimated downtime field, and a flag if the change requires a maintenance window. The UI layer (when built) will enforce a confirmation step for changes above a defined blast radius threshold. Audit logs record which human approved and when, supporting accountability.

---

### T10 — Compromised Global Controller *(Acknowledged — Out of Scope for v1)*

**Description**
The Global Controller (`global_cntl_1`) is compromised. Since it is the root of trust, an attacker with control over it can issue fraudulent certificates to any controller, modify global policy, approve destructive configuration changes, and corrupt the global audit trail.

**Impact**
Complete compromise of the PDSNO trust hierarchy.

**Why This Is Out of Scope for v1**
The mitigations for a compromised root of trust — hardware attestation, distributed consensus among multiple Global Controllers, external audit anchors, formal key ceremony procedures — add significant complexity that is not appropriate for the proof-of-concept phase. Including them now would delay the entire project without validating the core orchestration logic.

**Planned Mitigations for Future Phases**

- **Multi-GC consensus** — Require agreement from 2-of-3 (or similar) Global Controllers for critical operations, eliminating the single point of compromise
- **Hardware Security Module (HSM) backing** — Store the GC's private key in tamper-resistant hardware so key extraction requires physical access
- **External audit anchor** — Publish audit log hashes to an external, independently controlled system so GC-level log tampering is detectable
- **Formal threat modeling (STRIDE)** — Apply a structured methodology to enumerate all GC attack surfaces when the system reaches production readiness

This threat is noted here to ensure it is not forgotten and to set accurate expectations about v1 security guarantees.

---

## 5. Security Design Rules

These rules are non-negotiable across all implementations:

1. **Never trust self-reported sensitivity.** Higher tiers always re-classify independently.
2. **Emergency is not a bypass.** Emergency mode has stricter audit requirements than normal mode, not fewer.
3. **No policy sync = no approval.** Policy version mismatch results in rejection, not degraded-mode acceptance.
4. **Execution must be provable.** A change that cannot be confirmed by the NIB is treated as if it did not happen — even if it actually did.
5. **The NIB is the source of truth.** If a controller's local state disagrees with the NIB, the NIB wins and the controller reconciles.
6. **Audit is mandatory, not optional.** Every decision — approve, deny, flag, execute, rollback — generates a signed audit entry. There is no silent path.

---

## 6. Residual Risks

The following risks are known, accepted for now, and logged for future mitigation:

| Risk | Current Status |
|------|---------------|
| Coordinated compromise of LC + RC | Logged; partially mitigated by GC-level audit aggregation |
| Global Controller compromise | Deferred to future phase (see T10) |
| Human operator errors in approval | Partially mitigated by blast radius UI; full mitigation requires approval workflow implementation |
| Delayed reconciliation during long network partitions | Logged; current design accepts eventual consistency during partitions with reconciliation on reconnect |

---

## 7. Status

| Item | Status |
|------|--------|
| Threat scenarios T1–T9 | ✅ Reviewed and mitigated in design |
| T10 (GC compromise) | ✅ Acknowledged, explicitly deferred, future mitigations defined |
| Mitigations implemented in code | ⏳ Pending Phase 1 implementation |
| Formal STRIDE threat model | ⏳ Planned for pre-production phase |

---

*This document evolves alongside the system. As new components are added, corresponding threat scenarios should be added here.*
