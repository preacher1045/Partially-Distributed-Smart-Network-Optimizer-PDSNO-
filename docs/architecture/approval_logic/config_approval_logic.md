---
title: Configuration Approval Logic
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
component: Approval Logic
depends_on: nib_spec.md, communication_model.md, controller_validation_sequence.md
replaces: config_approval_doc.md, config_approval_logic.md (both superseded by this file)
---

# Configuration Approval Logic

## Overview

The Configuration Approval Logic governs how configuration changes are proposed,
reviewed, approved, and executed across the PDSNO controller hierarchy.

Its purpose is to balance four competing requirements: security (prevent unauthorized
or unsafe changes), speed (avoid bottlenecks on low-risk changes), scalability (work
across large multi-region deployments), and auditability (every decision is traceable
and reconstructible).

The system is **policy-driven**, **tier-aware**, and **risk-sensitive**. Every
approved change produces a cryptographic execution token. Every decision — approval,
denial, escalation, or execution — is written to the NIB Event Log.

---

## Actors and Responsibilities

| Actor | Role in Approval Flow |
|-------|----------------------|
| **LC** (Local Controller) | Originates proposals. Executes approved changes. Reports results. Cannot self-approve anything above LOW. |
| **RC** (Regional Controller) | Primary approval authority. Re-classifies sensitivity independently. Approves LOW/MEDIUM. Escalates HIGH to GC. |
| **GC** (Global Controller) | Final authority for HIGH changes. Holds immutable global policy. Issues execution tokens for HIGH approvals. |
| **NIB** | Source of truth for all state used in decisioning. All proposals, approvals, tokens, and audit entries are stored here. |

**Key rule:** An LC's suggested sensitivity is advisory only. RC and GC always
re-classify independently. A LOW suggestion from a compromised LC does not bypass
regional classification.

---

## Sensitivity Levels

| Level | Description | Examples | Approval Path |
|-------|-------------|---------|---------------|
| **LOW** | Safe, localized, reversible | SNMP community update, logging level change, discovery schedule tweak | LC executes directly OR RC auto-approves (policy-dependent) |
| **MEDIUM** | Operational impact, limited scope | Interface shutdown on non-production VLAN, ACL change on regional edge, branch routing policy | RC approval required |
| **HIGH** | Core network, security-critical, multi-region | Core routing change, firewall deny-all, firmware update on core device, change affecting multiple regions | GC approval required; RC enforces and executes |
| **EMERGENCY** | Immediate risk mitigation — active incident | DDoS null-route, quarantine of compromised device | LC executes immediately; RC and GC notified post-facto; audit required; rollback on RC/GC denial |

### Sensitivity Metadata Fields

Every config proposal carries these fields alongside the payload:

```json
{
  "category": "LOW | MEDIUM | HIGH | EMERGENCY",
  "impact_scope": "local | regional | global",
  "affected_devices": ["nib-dev-001", "nib-dev-002"],
  "estimated_downtime_seconds": 0,
  "requires_maintenance_window": false,
  "rollback_payload": { ... }
}
```

The `rollback_payload` is required for MEDIUM and above. It must be present at
proposal time — not constructed after execution. If a change cannot be reversed,
it must be declared as such and subject to a higher approval threshold.

---

## Decision Rules

```
LOW       → RC auto-approve (or LC direct execution if policy allows)
MEDIUM    → RC approves (escalates to GC if multi-region or high impact)
HIGH      → GC approval required; RC enforces and executes
EMERGENCY → LC executes immediately; RC+GC notified async; audit mandatory
```

### Escalation Triggers

RC **must** escalate to GC when any of the following are true:
- `impact_scope == "global"`
- `affected_devices` span more than one region
- `estimated_downtime_seconds > policy.escalation_downtime_threshold`
- Device in affected list is flagged `critical` in NIB Metadata
- RC policy explicitly requires GC sign-off for that device type

LC **must** escalate to RC (instead of executing directly) when:
- Local NIB data for an affected device is stale (older than `policy.stale_threshold`)
- Affected device has a `quarantined` or `suspicious` flag in NIB
- Local policy marks the device as protected

### Immutable Policy Override

If a proposal conflicts with a GC-flagged `immutable` policy rule, it is denied
immediately at whichever tier catches the conflict first. Immutable rules cannot
be overridden by regional or local policy, or by escalation.

---

## Complete Approval Flow

### Stage 1 — LC: Proposal Creation

```python
def propose_config_change(config_payload, target_devices):

    # Validate local state before proposing
    for device_id in target_devices:
        device = nib.get_device(device_id)
        if device is None:
            raise ProposalError(f"Device {device_id} not in NIB — cannot propose")
        if device.status in ("quarantined", "unreachable"):
            raise ProposalError(f"Device {device_id} status={device.status} — escalate to RC")

    proposal_id = generate_uuid()
    config_hash = sha256(canonical_json(config_payload))
    policy = nib.get_active_policy(scope="local", region=this_controller.region)

    proposal = {
        "proposal_id": proposal_id,
        "config_payload": config_payload,
        "config_hash": config_hash,
        "target_devices": target_devices,
        "suggested_sensitivity": suggest_sensitivity(config_payload, target_devices, policy),
        "impact_scope": determine_scope(target_devices),
        "rollback_payload": build_rollback(config_payload, target_devices),
        "timestamp": utc_now_iso(),
        "policy_version": policy.policy_version,
        "origin": this_controller.assigned_id,
        "origin_signature": sign(config_hash, this_controller.private_key)
    }

    # Write proposal to NIB before sending — so it exists if the network call fails
    nib.create_config_proposal(ConfigRecord(
        proposal_id=proposal_id,
        config_hash=config_hash,
        category=proposal["suggested_sensitivity"],
        status="PENDING",
        proposed_by=this_controller.assigned_id,
        target_devices=target_devices,
        rollback_payload=proposal["rollback_payload"]
    ))

    # EMERGENCY path — execute now, notify async
    if proposal["suggested_sensitivity"] == "EMERGENCY":
        return handle_emergency_proposal(proposal)

    # All other paths — send to RC
    send_to_rc(proposal)
```

**NIB writes at this stage:**
- `nib.create_config_proposal()` — proposal record in Config Table, status=`PENDING`
- `nib.write_event()` — audit entry: `CONFIG_PROPOSED`

---

### Stage 2 — RC: Intake, Classification, and Decision

```python
def handle_proposal(proposal):

    # Idempotency check — reject duplicates
    existing = nib.get_config_by_hash(proposal["config_hash"])
    if existing and existing.status in ("APPROVED", "EXECUTED"):
        return deny(proposal["proposal_id"], reason="DUPLICATE_PROPOSAL")

    # Re-classify sensitivity independently — never trust LC suggestion
    regional_policy = nib.get_active_policy(scope="regional", region=this_controller.region)
    sensitivity = classify_sensitivity(
        payload=proposal["config_payload"],
        devices=proposal["target_devices"],
        policy=regional_policy,
        nib=nib
    )

    # Policy version check — must match what LC was operating under
    if proposal["policy_version"] != regional_policy.policy_version:
        nib.write_event(Event(
            event_type="CONFIG_REJECTED",
            actor=this_controller.assigned_id,
            subject=proposal["proposal_id"],
            action="Policy version mismatch",
            decision="DENIED"
        ))
        return deny(proposal["proposal_id"], reason="POLICY_VERSION_MISMATCH")

    # Conflict check — is any target device already locked?
    for device_id in proposal["target_devices"]:
        existing_lock = nib.check_lock(device_id, "CONFIG_LOCK")
        if existing_lock and existing_lock.status == "ACTIVE":
            return queue_pending_conflict(proposal, blocking_lock=existing_lock)

    # Acquire locks on all target devices
    for device_id in proposal["target_devices"]:
        lock_result = nib.acquire_lock(
            subject_id=device_id,
            lock_type="CONFIG_LOCK",
            held_by=this_controller.assigned_id,
            ttl_seconds=APPROVAL_LOCK_TTL
        )
        if not lock_result.success:
            # Another process acquired the lock between check and acquire — back off
            release_all_locks_for_proposal(proposal["proposal_id"])
            return queue_pending_conflict(proposal, reason="LOCK_RACE")

    # Emergency fast path
    if sensitivity == "EMERGENCY":
        return handle_emergency_regional(proposal)

    # LOW / MEDIUM — RC decides
    if sensitivity in ("LOW", "MEDIUM"):
        return approve_regionally(proposal, sensitivity, regional_policy)

    # HIGH — escalate to GC
    if sensitivity == "HIGH":
        return escalate_to_gc(proposal, regional_policy)
```

**NIB writes at this stage:**
- `nib.acquire_lock()` — CONFIG_LOCK for each target device
- `nib.write_event()` — audit entries for classification, conflict detection, escalation

---

### Stage 3a — RC: Approve LOW/MEDIUM

```python
def approve_regionally(proposal, sensitivity, policy):

    token = issue_execution_token(
        proposal_id=proposal["proposal_id"],
        config_hash=proposal["config_hash"],
        target_devices=proposal["target_devices"],
        approved_by=this_controller.assigned_id,
        ttl_seconds=EXECUTION_TOKEN_TTL,  # default: 600 seconds
        constraints={
            "max_devices_per_minute": policy.rate_limits.devices_per_minute,
            "rollback_required_on_failure": True
        }
    )

    nib.update_config_status(
        config_id=proposal["proposal_id"],
        status="APPROVED",
        approver=this_controller.assigned_id,
        execution_token=token.token_id,
        expiry=token.expires_at
    )

    nib.write_event(Event(
        event_type="CONFIG_APPROVED",
        actor=this_controller.assigned_id,
        subject=proposal["proposal_id"],
        action=f"Approved {sensitivity} config proposal",
        decision="APPROVED"
    ))

    # Send execution instruction to LC
    send_execution_instruction(
        recipient=proposal["origin"],
        proposal_id=proposal["proposal_id"],
        execution_token=token,
        execute_at=None  # immediate
    )
```

**NIB writes at this stage:**
- `nib.update_config_status()` — Config Table, status=`APPROVED`, token stored
- `nib.write_event()` — audit entry: `CONFIG_APPROVED`

---

### Stage 3b — RC: Escalate HIGH to GC

```python
def escalate_to_gc(proposal, regional_policy):

    nib.update_config_status(
        config_id=proposal["proposal_id"],
        status="PENDING",  # still pending — now awaiting GC
        approver=None
    )

    nib.write_event(Event(
        event_type="CONFIG_ESCALATED",
        actor=this_controller.assigned_id,
        subject=proposal["proposal_id"],
        action="Escalated HIGH proposal to GC",
        decision="ESCALATED"
    ))

    # Forward to GC with regional context attached
    send_to_gc({
        **proposal,
        "escalated_by": this_controller.assigned_id,
        "regional_context": {
            "blast_radius": calculate_blast_radius(proposal["target_devices"], nib),
            "affected_critical_devices": get_critical_devices(proposal["target_devices"], nib),
            "regional_policy_version": regional_policy.policy_version
        }
    })

    # Wait for GC response with timeout
    response = await_gc_response(
        proposal_id=proposal["proposal_id"],
        timeout_seconds=GC_RESPONSE_TIMEOUT  # default: 300 seconds
    )

    if response is None:
        # GC did not respond — default deny (safe)
        release_all_locks_for_proposal(proposal["proposal_id"])
        nib.update_config_status(proposal["proposal_id"], status="DENIED",
                                  approver=None)
        nib.write_event(Event(event_type="CONFIG_DENIED", actor=this_controller.assigned_id,
                               subject=proposal["proposal_id"],
                               action="GC response timeout — defaulting to DENY",
                               decision="DENIED"))
        return deny(proposal["proposal_id"], reason="GC_TIMEOUT")

    if response.decision == "DENY":
        release_all_locks_for_proposal(proposal["proposal_id"])
        nib.update_config_status(proposal["proposal_id"], status="DENIED",
                                  approver=response.responder)
        nib.write_event(Event(event_type="CONFIG_DENIED", actor=response.responder,
                               subject=proposal["proposal_id"],
                               action=f"GC denied: {response.notes}",
                               decision="DENIED"))
        return deny(proposal["proposal_id"], reason="GC_DENIED")

    # GC approved — RC forwards execution instruction to LC
    forward_execution_to_lc(proposal, response.execution_token)
```

**NIB writes at this stage:**
- `nib.update_config_status()` — status=`DENIED` or forwards to execution
- `nib.write_event()` — `CONFIG_ESCALATED`, `CONFIG_DENIED`, or `CONFIG_APPROVED`
- `nib.release_lock()` — all device locks released on deny or timeout

---

### Stage 4 — GC: HIGH Approval Decision

```python
def global_validate(proposal_with_context):

    global_policy = nib.get_active_policy(scope="global")

    # Check immutable rules first
    for rule in global_policy.immutable_rules:
        if rule.applies_to(proposal_with_context["config_payload"]):
            return gc_deny(proposal_with_context, reason=f"IMMUTABLE_RULE: {rule.id}")

    # Assess cross-region effects
    regions_affected = get_unique_regions(proposal_with_context["target_devices"], nib)
    if len(regions_affected) > global_policy.max_regions_per_change:
        return gc_deny(proposal_with_context, reason="TOO_MANY_REGIONS")

    # Approve and issue execution token
    token = issue_execution_token(
        proposal_id=proposal_with_context["proposal_id"],
        config_hash=proposal_with_context["config_hash"],
        target_devices=proposal_with_context["target_devices"],
        approved_by=this_controller.assigned_id,
        ttl_seconds=EXECUTION_TOKEN_TTL_HIGH,  # tighter TTL for HIGH changes
        constraints={
            "max_devices_per_minute": global_policy.rate_limits.high_category,
            "rollback_required_on_failure": True,
            "maintenance_window_required": proposal_with_context.get(
                "requires_maintenance_window", False)
        }
    )

    nib.write_event(Event(
        event_type="CONFIG_APPROVED",
        actor=this_controller.assigned_id,
        subject=proposal_with_context["proposal_id"],
        action="GC approved HIGH config proposal",
        decision="APPROVED"
    ))

    return GCResponse(
        decision="APPROVE",
        execution_token=token,
        responder=this_controller.assigned_id
    )
```

**NIB writes at this stage:**
- `nib.write_event()` — `CONFIG_APPROVED` or `CONFIG_DENIED`

---

### Stage 5 — LC: Token Verification and Execution

```python
def execute_config(execution_instruction):

    token = execution_instruction["execution_token"]

    # Verify token has not expired
    if utc_now_iso() > token["expires_at"]:
        nib.write_event(Event(event_type="EXECUTION_ABORTED",
                               actor=this_controller.assigned_id,
                               subject=token["proposal_id"],
                               action="Token expired before execution",
                               decision="ABORTED"))
        return abort("TOKEN_EXPIRED")

    # Verify token bindings — proposal_id, config_hash, devices, approver
    if not verify_token_signature(token, approver_public_key=get_pubkey(token["approved_by"])):
        nib.write_event(Event(event_type="EXECUTION_ABORTED",
                               actor=this_controller.assigned_id,
                               subject=token["proposal_id"],
                               action="Token signature invalid",
                               decision="ABORTED"))
        security_events.flag(token["proposal_id"], "INVALID_TOKEN_PRESENTED")
        return abort("INVALID_TOKEN")

    # Verify token is single-use — mark consumed before execution begins
    consume_result = token_store.consume(token["token_id"])
    if not consume_result.success:
        return abort("TOKEN_ALREADY_CONSUMED")  # replay attempt

    # Re-verify device states immediately before execution
    for device_id in token["target_devices"]:
        device = nib.get_device(device_id)
        if device is None or device.status in ("quarantined", "unreachable"):
            return abort_and_rollback(token, reason=f"DEVICE_STATE_CHANGED: {device_id}")

    # Write EXECUTING status to NIB before touching any device
    nib.update_config_status(token["proposal_id"], status="EXECUTING",
                              approver=token["approved_by"])

    # Execute — apply the config to each device with rate limiting
    results = {}
    failed_devices = []

    for device_id in token["target_devices"]:
        try:
            apply_config_to_device(device_id, token["config_payload"],
                                   constraints=token["constraints"])
            results[device_id] = "SUCCESS"
        except ExecutionError as e:
            results[device_id] = f"FAILED: {e}"
            failed_devices.append(device_id)

    # Determine final status
    if not failed_devices:
        final_status = "EXECUTED"
    elif len(failed_devices) < len(token["target_devices"]):
        final_status = "PARTIAL_FAILURE"  # some devices failed — rollback all
    else:
        final_status = "FAILED"

    if final_status in ("PARTIAL_FAILURE", "FAILED"):
        return execute_rollback(token, results)

    # Successful execution
    nib.update_config_status(token["proposal_id"], status="EXECUTED",
                              approver=token["approved_by"])
    nib.write_event(Event(
        event_type="CONFIG_EXECUTED",
        actor=this_controller.assigned_id,
        subject=token["proposal_id"],
        action=f"Config applied to {len(token['target_devices'])} devices",
        decision="APPROVED"
    ))

    # Release locks
    release_all_locks_for_proposal(token["proposal_id"])

    # Report upstream
    report_execution_result(token["proposal_id"], final_status, results)
```

**NIB writes at this stage:**
- `nib.update_config_status()` — status=`EXECUTING` then `EXECUTED` or `FAILED`
- `nib.write_event()` — `EXECUTION_ABORTED` or `CONFIG_EXECUTED`
- `nib.release_lock()` — all CONFIG_LOCKs released on completion

---

### Stage 6 — LC: Rollback

```python
def execute_rollback(token, execution_results):

    nib.update_config_status(token["proposal_id"], status="ROLLING_BACK",
                              approver=token["approved_by"])

    rollback_results = {}
    rollback_failed = []

    for device_id in token["target_devices"]:
        try:
            apply_config_to_device(device_id, token["rollback_payload"][device_id])
            rollback_results[device_id] = "ROLLED_BACK"
        except ExecutionError as e:
            rollback_results[device_id] = f"ROLLBACK_FAILED: {e}"
            rollback_failed.append(device_id)

    if rollback_failed:
        # Rollback itself failed — device is in unknown state
        for device_id in rollback_failed:
            nib.update_device_status(device_id, "degraded", version=get_version(device_id))
            nib.write_event(Event(
                event_type="DEVICE_DEGRADED",
                actor=this_controller.assigned_id,
                subject=device_id,
                action=f"Rollback failed after execution failure — device in unknown state",
                decision="FAILED"
            ))

        nib.update_config_status(token["proposal_id"], status="DEGRADED",
                                  approver=token["approved_by"])
        # Block all further changes to degraded devices
        # Escalate to RC for manual intervention
        notify_rc_degraded(token["proposal_id"], rollback_failed)
    else:
        nib.update_config_status(token["proposal_id"], status="ROLLED_BACK",
                                  approver=token["approved_by"])

    nib.write_event(Event(
        event_type="CONFIG_ROLLED_BACK",
        actor=this_controller.assigned_id,
        subject=token["proposal_id"],
        action=f"Rollback completed. Failed devices: {rollback_failed}",
        decision="ROLLED_BACK" if not rollback_failed else "DEGRADED"
    ))

    release_all_locks_for_proposal(token["proposal_id"])
    report_execution_result(token["proposal_id"],
                             "ROLLED_BACK" if not rollback_failed else "DEGRADED",
                             rollback_results)
```

**NIB writes at this stage:**
- `nib.update_config_status()` — `ROLLING_BACK`, then `ROLLED_BACK` or `DEGRADED`
- `nib.update_device_status()` — affected devices marked `degraded` on rollback failure
- `nib.write_event()` — `CONFIG_ROLLED_BACK` or `DEVICE_DEGRADED`
- `nib.release_lock()` — all CONFIG_LOCKs released

---

### Stage 7 — Emergency Fast Path

```python
def handle_emergency_proposal(proposal):
    """
    Emergency = execute first, audit immediately, notify async.
    Emergency is NOT a bypass of governance — it is governance with
    post-facto accountability.
    """

    # Rate limit check — emergency mode cannot be invoked freely
    if not emergency_rate_limiter.allow(this_controller.assigned_id):
        # Rate limit hit — treat as HIGH instead
        proposal["suggested_sensitivity"] = "HIGH"
        send_to_rc(proposal)
        return

    # Restricted config types only
    if not is_emergency_permitted_type(proposal["config_payload"]):
        nib.write_event(Event(
            event_type="EMERGENCY_REJECTED",
            actor=this_controller.assigned_id,
            subject=proposal["proposal_id"],
            action="Emergency attempted for non-permitted config type",
            decision="DENIED"
        ))
        return abort("EMERGENCY_TYPE_NOT_PERMITTED")

    # Execute immediately — no token required for emergency path
    nib.update_config_status(proposal["proposal_id"], status="EXECUTING",
                              approver=this_controller.assigned_id)

    try:
        for device_id in proposal["target_devices"]:
            apply_config_to_device(device_id, proposal["config_payload"])

        nib.update_config_status(proposal["proposal_id"], status="EXECUTED",
                                  approver=this_controller.assigned_id)
    except ExecutionError as e:
        execute_rollback_emergency(proposal)
        return

    # Mandatory audit entry — must include full payload
    nib.write_event(Event(
        event_type="EMERGENCY_EXECUTION",
        actor=this_controller.assigned_id,
        subject=proposal["proposal_id"],
        action=f"Emergency config applied. Rate limiter: {emergency_rate_limiter.status()}",
        decision="EMERGENCY_APPROVED"
    ))

    # Notify RC and GC asynchronously — they must acknowledge within window
    notify_emergency_upstream(proposal, timeout=EMERGENCY_POSTFACT_TIMEOUT)
    # If RC/GC deny retrospectively → rollback_protocol runs
```

---

## Execution Token Structure

```json
{
  "token_id": "uuid-v4",
  "proposal_id": "uuid-v4",
  "config_hash": "sha256-hex",
  "target_devices": ["nib-dev-001", "nib-dev-002"],
  "approved_by": "regional_cntl_zoneA_1",
  "issued_at": "2026-02-16T10:30:00Z",
  "expires_at": "2026-02-16T10:40:00Z",
  "constraints": {
    "max_devices_per_minute": 10,
    "rollback_required_on_failure": true,
    "maintenance_window_required": false
  },
  "signature": "hmac-sha256-of-all-fields-above"
}
```

Tokens are single-use, bound to a specific proposal and config hash, time-limited,
and cryptographically signed by the approving controller. Any mismatch between the
token fields and the actual execution attempt aborts the execution.

---

## Timeouts and Retry Contracts

| Operation | Timeout | Max Retries | On Final Failure |
|-----------|---------|-------------|-----------------|
| LC → RC proposal send | 30s | 3 (exp. backoff) | Queue locally; retry after `policy.rc_retry_interval` |
| RC → GC escalation response | 300s (5 min) | 0 (no retry — one escalation) | Default DENY; release locks |
| Execution token TTL (LOW/MEDIUM) | 600s (10 min) | N/A — token expires | LC must request re-approval |
| Execution token TTL (HIGH) | 300s (5 min) | N/A | LC must request re-approval |
| Emergency post-facto acknowledgement | 600s (10 min) | N/A | RC/GC may issue retrospective rollback |
| Approval lock TTL | 900s (15 min) | N/A — lock auto-expires | Background cleanup releases stale locks |

---

## Config Status State Machine

```
PENDING
   │
   ├─── RC denies ───────────────────────────────► DENIED
   │
   ├─── RC approves (LOW/MEDIUM) ───────────────► APPROVED
   │                                                  │
   ├─── RC escalates (HIGH) ─── GC denies ──────► DENIED
   │                        └── GC approves ────► APPROVED
   │                                                  │
   │                              APPROVED ──────► EXECUTING
   │                                                  │
   │                              EXECUTING ─────► EXECUTED (success)
   │                                           └── PARTIAL_FAILURE
   │                                           └── FAILED
   │                                                  │
   │                              FAILED/PARTIAL ─► ROLLING_BACK
   │                                                  │
   │                              ROLLING_BACK ──► ROLLED_BACK (clean)
   │                                           └── DEGRADED (rollback failed)
   │
   └─── Emergency path ───────────────────────────► EXECUTING → EXECUTED
                                                              └── (rollback if RC/GC deny)
```

---

## NIB Write Summary

Every stage of the approval flow writes to the NIB. This table is the
implementation checklist — no stage is complete until its NIB writes are done.

| Stage | NIB Write | Table | Status Written |
|-------|-----------|-------|---------------|
| LC Proposal | `create_config_proposal()` | Config Table | `PENDING` |
| LC Proposal | `write_event()` | Event Log | `CONFIG_PROPOSED` |
| RC Lock | `acquire_lock()` | Controller Sync | `ACTIVE` |
| RC Approve | `update_config_status()` | Config Table | `APPROVED` + token |
| RC Approve | `write_event()` | Event Log | `CONFIG_APPROVED` |
| RC Escalate | `write_event()` | Event Log | `CONFIG_ESCALATED` |
| RC/GC Deny | `update_config_status()` | Config Table | `DENIED` |
| RC/GC Deny | `write_event()` | Event Log | `CONFIG_DENIED` |
| RC/GC Deny | `release_lock()` | Controller Sync | `RELEASED` |
| GC Approve | `write_event()` | Event Log | `CONFIG_APPROVED` |
| LC Execute Start | `update_config_status()` | Config Table | `EXECUTING` |
| LC Execute End | `update_config_status()` | Config Table | `EXECUTED` |
| LC Execute End | `write_event()` | Event Log | `CONFIG_EXECUTED` |
| LC Execute End | `release_lock()` | Controller Sync | `RELEASED` |
| LC Rollback | `update_config_status()` | Config Table | `ROLLED_BACK` or `DEGRADED` |
| LC Rollback | `update_device_status()` | Device Table | `degraded` (if rollback failed) |
| LC Rollback | `write_event()` | Event Log | `CONFIG_ROLLED_BACK` or `DEVICE_DEGRADED` |
| Emergency | `write_event()` | Event Log | `EMERGENCY_EXECUTION` |

---

## Quick Reference Decision Table

| Category | Approver | Execution | Escalation |
|----------|---------|-----------|-----------|
| LOW | LC direct or RC auto | LC immediately after approval | None |
| MEDIUM | Regional Controller | LC after RC approval | RC → GC if multi-region or high impact |
| HIGH | Global Controller | LC after GC approval via RC | Already at GC — no further escalation |
| EMERGENCY | None (pre-facto) | LC immediately | RC + GC notified async; rollback if denied |

---

## Example Scenarios

**LOW — Logging level update on a leaf switch**
LC validates device is active in NIB. Policy allows direct LC execution for LOW.
LC writes proposal with status=`EXECUTED` directly. Single audit entry.

**MEDIUM — ACL change on a regional edge device**
LC creates proposal, sends to RC. RC re-classifies as MEDIUM. RC checks NIB for
device lock, acquires it, approves, issues token, instructs LC. LC verifies token,
executes, writes result. RC releases lock. Two audit entries: `CONFIG_APPROVED`,
`CONFIG_EXECUTED`.

**HIGH — Core routing policy update**
LC creates proposal, RC re-classifies as HIGH, escalates to GC with blast radius
and critical device list attached. GC verifies against immutable policy rules,
approves, issues HIGH-category token (shorter TTL). RC forwards to LC. LC verifies
and executes. Three audit entries: `CONFIG_ESCALATED`, `CONFIG_APPROVED`,
`CONFIG_EXECUTED`.

**EMERGENCY — Active DDoS, immediate null-route needed**
LC detects traffic anomaly. Creates EMERGENCY proposal. Rate limiter allows it.
Config type (null-route) is on permitted emergency list. LC executes immediately,
writes `EMERGENCY_EXECUTION` audit entry, notifies RC and GC async. RC acknowledges
within 10 minutes. If RC had denied: rollback protocol runs.

---

## Security Notes

**Never trust self-reported sensitivity.** RC always re-classifies. An LC under
attacker control claiming LOW for a destructive change is caught at RC.

**Emergency ≠ bypass.** Emergency changes are the most heavily audited, not the
least. Rate limiting, permitted-type restrictions, and mandatory post-facto
acknowledgement together ensure emergency mode cannot be used as a routine
governance bypass.

**Token binding prevents lateral movement.** A token issued for `nib-dev-001`
cannot be used to execute a change on `nib-dev-002`. Every field of the token is
verified before execution begins.

**Rollback payload is required at proposal time.** Not constructing rollback
after the fact — it must exist when the proposal is submitted. This forces the
proposer to think about reversal before acting.

---

## Extensibility

These features are explicitly deferred — they are not needed for v1 but the
schema and logic are designed to accommodate them:

- **Risk scoring engine** — NIB-fed `sensitivity_score` based on device criticality,
  historical failures, vendor CVEs. Would replace or supplement manual classification.
- **Multi-signature approvals** — require sign-off from two RC operators for HIGH
  changes. Schema already has `approved_by` as a field; extend to an array.
- **Auto-rollback with health checks** — post-execution metric monitoring triggers
  automatic rollback if KPIs degrade. Requires telemetry layer (Phase 8).
- **GUI-driven approvals** — operator dashboard for reviewing and approving pending
  proposals. Requires NBI REST endpoints (Phase 6).
- **Approval delegation and SLA windows** — specify who can auto-approve during
  off-hours and within what change window constraints.
