# PDSNO — Threat Model & Mitigations

*Status: Reviewed*  
*Audience: Architects, security reviewers, core contributors*

---

## 1. Purpose

This document identifies **security threats, failure modes, and abuse scenarios** in the PDSNO approval system and describes **design-level mitigations**.

It focuses on:
- Malicious actors
- Compromised controllers
- Operational mistakes
- Distributed-system failures

---

## 2. Threat Assumptions

We assume:
- Controllers can be compromised
- Network partitions will occur
- Humans make mistakes
- Policies may drift temporarily
- Attackers attempt privilege escalation

We do **not** assume:
- Trusted internal environment
- Perfect uptime
- Honest lower-tier behavior

---

## 3. Threat Scenarios & Mitigations

---

### T1: Category Spoofing by Local Controller

**Threat**  
LC declares a risky change as LOW sensitivity.

**Mitigation**
- RC/GC independently re-classify sensitivity
- LC classification treated as advisory only

---

### T2: Emergency Mode Abuse

**Threat**  
LC repeatedly invokes emergency mode.

**Mitigation**
- Rate limits per controller
- Restricted config types
- Restricted device roles
- Automatic escalation and audit

---

### T3: Policy Version Drift

**Threat**  
LC submits request under outdated policy.

**Mitigation**
- Mandatory policy version match
- Requests rejected if versions differ

---

### T4: Execution Token Replay

**Threat**  
Token reused for unauthorized execution.

**Mitigation**
- Tokens bound to request, config hash, devices, controller ID
- Tokens are single-use and short-lived

---

### T5: Partial Execution with Network Failure

**Threat**  
Execution succeeds but report fails.

**Mitigation**
- Execution state written to Local NIB first
- Upstream reconciliation required
- No assumption-based state transitions

---

### T6: Concurrent Config Conflicts

**Threat**  
Multiple approved changes collide.

**Mitigation**
- Approval-time locking
- Conflict detection on same device/config scope

---

### T7: Rollback Failure

**Threat**  
Rollback itself fails.

**Mitigation**
- `DEGRADED` state
- Block further changes
- Escalate for manual intervention

---

### T8: Forged Audit Logs

**Threat**  
LC falsifies execution reports.

**Mitigation**
- Signed logs
- Cross-check with discovery/NIB updates
- Upstream validation

---

### T9: Human Approval Errors

**Threat**  
Operator approves unsafe change.

**Mitigation**
- Mandatory blast-radius summary
- Affected device count
- Structured config diff metadata

---

## 4. Security Design Rules

1. Never trust self-reported sensitivity
2. Emergency ≠ bypass
3. No policy sync = no approval
4. Execution must be provable
5. NIB is the source of truth
6. Audit is mandatory, not optional

---

## 5. Residual Risks

Known but accepted (for now):
- Human judgment errors
- Temporary network partitions
- Delayed reconciliation

These are logged and monitored, not ignored.

---

## 6. Future Enhancements

- Formal threat modeling (STRIDE)
- Cryptographic log chaining
- Behavioral anomaly detection
- Zero-trust controller identity

---

## 7. Status

✔ Threat scenarios reviewed  
✔ Mitigations defined  
⏳ Implementation pending  

### Note
This document is meant to evolve alongside the system.
