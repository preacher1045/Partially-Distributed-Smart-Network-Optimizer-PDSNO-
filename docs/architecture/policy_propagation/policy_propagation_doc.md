# PDSNO — Configuration Approval Logic

*Status: Design Complete (Pre-Implementation)*  
*Audience: Core contributors, architects, reviewers*

---

## 1. Overview

The **Configuration Approval Logic** governs how configuration changes are proposed, reviewed, approved, and executed across the PDSNO controller hierarchy.

Its purpose is to balance:

- **Security** (prevent unauthorized or unsafe changes)
- **Speed** (avoid unnecessary human bottlenecks)
- **Scalability** (support large, multi-region deployments)
- **Auditability** (every decision is traceable)

The approval system is **policy-driven**, **tier-aware**, and **risk-sensitive**.

---

## 2. Controller Roles in Approval

### Global Controller (GC)
- Defines global approval policies
- Handles high-risk changes
- Acts as final authority
- Maintains system-wide governance

### Regional Controller (RC)
- Primary approval authority for most changes
- Re-classifies configuration risk
- Enforces policy consistency
- Coordinates multiple local controllers

### Local Controller (LC)
- Proposes configuration changes
- Executes approved configurations
- Reports execution results
- Cannot self-approve sensitive changes

---

## 3. Configuration Sensitivity Levels

Each configuration request is classified into a **sensitivity category**.

| Category | Description | Approval Path |
|--------|-------------|---------------|
| LOW | Safe, localized, reversible | Local / Regional auto-approval |
| MEDIUM | Operational impact, limited scope | Regional approval |
| HIGH | Core network, security-critical | Global approval |
| EMERGENCY | Immediate risk mitigation | Tier-limited bypass with constraints |

> **Important Rule:**  
> Lower-tier controllers may *suggest* sensitivity, but **higher tiers must re-classify independently**.

---

## 4. Approval Flow Summary

1. **Proposal**
   - LC submits config request with metadata
2. **Re-classification**
   - RC (or GC) independently determines sensitivity
3. **Policy Validation**
   - Policy version consistency is verified
4. **Approval Decision**
   - Auto-approve, manual approve, or reject
5. **Execution Token Issued**
   - Token bound to request + config hash
6. **Execution**
   - LC applies config within strict constraints
7. **Post-Execution Reporting**
   - Results written to NIB and sent upstream
8. **Audit Logging**
   - Immutable logs generated and stored

---

## 5. Emergency Approval Mode

Emergency mode exists to **contain damage**, not bypass governance.

### Emergency Constraints
- Rate-limited per controller
- Restricted config types (e.g., quarantine, rate-limit)
- Restricted device roles (e.g., edge only)
- Automatically escalated and audited

Emergency actions are **never silent** and **never permanent**.

---

## 6. Execution Tokens

Approved requests receive a **single-use execution token**.

Tokens are cryptographically bound to:
- Request ID
- Config hash
- Affected devices
- Controller identity
- Expiration timestamp

Replay or mismatch results in immediate denial.

---

## 7. Concurrency & Conflict Handling

- Approval-time locking prevents conflicting changes
- Locks may apply per-device or per-config-section
- Lower-priority requests wait or are rejected
- No speculative execution allowed

---

## 8. Rollback & Failure Handling

### Execution States
- `PENDING`
- `EXECUTING`
- `SUCCESS`
- `FAILED`
- `DEGRADED`
- `MANUAL_INTERVENTION`

If rollback fails:
- Device enters `DEGRADED`
- Further changes blocked
- Escalation required

---

## 9. Audit & Accountability

Every approval decision records:
- Who requested
- Who approved
- Why it was approved
- What was changed
- What actually happened

Audit logs are:
- Signed
- Tamper-evident
- Cross-validated with discovery/NIB state

---

## 10. Design Principles

- **Never trust lower tiers blindly**
- **Speed is tier-dependent**
- **Safety overrides convenience**
- **State lives in the NIB**
- **Everything is auditable**

---

## 11. Status

✔ Design complete  
⏳ Implementation pending  
🔍 Threat-model validated  

See `THREAT_MODEL.md` for known risks and mitigations.
