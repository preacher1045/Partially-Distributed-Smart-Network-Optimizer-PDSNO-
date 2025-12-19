# Device Configuration Approval Logic

**Hybrid Tier-Based Approval (Local → Regional → Global)**

## Core Design Goals (Recap)

* **Fast path for safe changes**
* **Strict escalation for risky changes**
* **Deterministic decisions**
* **Auditable and reversible**
* **Graceful degradation if controllers are unreachable**

---

## Key Concepts (Minimal, Necessary)

| Term              | Meaning                                  |
| ----------------- | ---------------------------------------- |
| `proposal_id`     | Unique config proposal identifier        |
| `config_hash`     | Hash of normalized config payload        |
| `sensitivity`     | LOW / MEDIUM / HIGH / EMERGENCY          |
| `blast_radius`    | Number + criticality of affected devices |
| `execution_token` | Short-lived signed approval token        |
| `constraints`     | Rate limits, device caps, timing windows |

---

## High-Level Decision Rules

```
LOW      → Regional approval only
MEDIUM   → Regional approval only
HIGH     → Global approval required
EMERGENCY→ Local auto-apply (logged + escalated)
```

---

## Step-by-Step Approval Algorithm

### 1. Local Controller — Proposal Creation

```pseudo
function propose_config_change(config_payload, target_devices):

    proposal_id = generate_uuid()
    config_hash = hash(config_payload)

    proposal = {
        proposal_id,
        config_payload,
        config_hash,
        target_devices,
        suggested_sensitivity,
        timestamp,
        local_policy_version
    }

    send proposal → RegionalController
```

---

### 2. Regional Controller — Intake & Classification

```pseudo
function handle_proposal(proposal):

    if proposal.config_hash already approved:
        reject("Duplicate proposal")

    sensitivity = classify_sensitivity(
        config_payload,
        target_devices,
        regional_policy
    )

    blast_radius = calculate_blast_radius(target_devices)

    if conflict_detected(target_devices):
        queue_for_resolution(proposal)
        return "PENDING_CONFLICT"
```

---

### 3. Emergency Fast Path (Optional but Critical)

```pseudo
if sensitivity == EMERGENCY:
    approve_locally()
    issue_execution_token(ttl=SHORT)
    log_emergency_override()
    notify_global_async()
    return APPROVED
```

---

### 4. Regional Decision Logic

```pseudo
if sensitivity in [LOW, MEDIUM]:
    approve_regionally()
    token = issue_execution_token(
        scope=target_devices,
        constraints=regional_limits,
        ttl=STANDARD
    )
    return APPROVED_WITH_TOKEN
```

---

### 5. Escalation to Global Controller

```pseudo
if sensitivity == HIGH:
    forward proposal → GlobalController
```

---

### 6. Global Controller — Final Validation

```pseudo
function global_validate(proposal):

    verify_policy_alignment(proposal)
    assess_security_impact(proposal)
    assess_cross_region_effects(proposal)

    if violates_global_policy:
        return REJECTED

    constraints = derive_constraints(proposal)

    token = issue_execution_token(
        scope=proposal.target_devices,
        constraints,
        ttl=STRICT
    )

    return APPROVED_WITH_TOKEN
```

---

### 7. Token Verification & Execution (Local)

```pseudo
function execute_config(token, config_payload):

    if token.expired or invalid:
        abort_execution()

    if violates_constraints(token, runtime_state):
        abort_execution()

    apply_config_safely(config_payload)

    report_results → RegionalController
```

---

### 8. Post-Execution Reporting & Audit

```pseudo
function report_execution(result):

    write_audit_log(
        proposal_id,
        devices,
        diffs,
        success_rate,
        timestamps
    )

    propagate_logs → GlobalController
```

---

## Failure & Degradation Handling

### Regional Unreachable

```pseudo
Local → queue proposal
Retry with backoff
```

### Global Unreachable (HIGH sensitivity)

```pseudo
Reject (default)
OR require emergency flag
```

### Token Abuse Prevention

* One-time use tokens
* Device scope enforced
* Time-bounded execution window
