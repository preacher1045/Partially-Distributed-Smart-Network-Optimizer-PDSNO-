---
title: Controller Validation Sequence
description: Complete design and pseudocode for the PDSNO controller validation system.
author: Alexander Adjei
status: Active
last_updated: 2026-02-16
component: Controller Verification Module
depends_on: nib_spec.md, communication_model.md
---

# Controller Validation Sequence

## Overview

The Controller Validation System ensures only authorized, authenticated controllers
can participate in PDSNO. Every controller — Global, Regional, and Local — must be
validated before it can send commands, approve configurations, or write to the NIB.

This document covers:
- What a validation request contains and why each field exists
- The complete 6-step validation flow with error states at every step
- The security fix to the bootstrap token path
- The atomicity requirement for identity assignment
- The NIB writes that occur during validation
- Error state table for all failure modes
- How Regional Controllers delegate Local Controller validation

---

## The Trust Chain

Validation always flows from a higher-tier controller to a lower-tier one:

```
global_cntl_1
    └── validates → regional_cntl_1 ... regional_cntl_N
                        └── validates → local_cntl_1 ... local_cntl_N
```

A Regional Controller cannot validate another Regional Controller. A Local
Controller cannot validate anything. The Global Controller is the trust anchor
for the entire system — it validates Regional Controllers directly. Regional
Controllers, once validated, are delegated authority to validate Local Controllers
within their zone. This delegation is explicit: the GC issues a signed delegation
credential to each validated RC at validation time.

**Key implication:** A Local Controller submits its validation request to its
Regional Controller, not to the Global Controller. The RC runs the same 6-step
flow against the LC that the GC ran against the RC.

---

## Validation Request Structure

Every controller seeking validation sends this message envelope:

```json
{
  "envelope": {
    "message_id": "uuid-v4",
    "message_type": "VALIDATION_REQUEST",
    "sender_id": "temp-<uuid>",
    "recipient_id": "global_cntl_1",
    "timestamp": "2026-02-16T10:30:00.000Z",
    "signature": "<hmac-sha256 of envelope+payload>",
    "schema_version": "1.0"
  },
  "payload": {
    "temp_id": "temp-<uuid>",
    "controller_type": "regional | local",
    "region": "zone-A",
    "public_key": "<base64-encoded Ed25519 pubkey>",
    "bootstrap_token": "<hmac-sha256 token issued during provisioning>",
    "metadata": {
      "hostname": "rc-zone-a-01",
      "ip_address": "10.0.1.5",
      "software_version": "0.1.0",
      "capabilities": ["discovery", "approval", "policy_enforcement"]
    }
  }
}
```

### Why Each Field Exists

| Field | Purpose | What happens if missing/invalid |
|-------|---------|--------------------------------|
| `temp_id` | Unique but unverified identifier for this registration attempt | Rejected — cannot track the request |
| `timestamp` | Freshness check — prevents delayed/replayed requests | Rejected if stale (> 5 min window) |
| `controller_type` | Tells the validator what role and zone rules to apply | Rejected if not a recognised type |
| `region` | The zone this controller will serve — verified against policy | Rejected if zone not permitted |
| `public_key` | The key the challenge will be signed with — proves ownership | Rejected — cannot run challenge |
| `bootstrap_token` | Pre-shared secret issued during provisioning — proves it was provisioned legitimately | Rejected if invalid |
| `metadata` | Contextual info for policy checks and audit record | Logged; rejection only if policy requires specific fields |

---

## The 6-Step Validation Flow

```
Requesting Controller                Validating Controller (GC or RC)
        │                                       │
        │ ── VALIDATION_REQUEST ───────────────►│
        │                                       │ Step 1: Timestamp + Blocklist
        │                                       │ Step 2: Bootstrap Token Check
        │                                       │
        │◄── CHALLENGE (nonce) ─────────────────│ Step 3: Issue Challenge
        │                                       │
        │ ── CHALLENGE_RESPONSE (signed nonce) ►│
        │                                       │ Step 4: Verify Signature
        │                                       │ Step 5: Policy Checks
        │                                       │ Step 6: Atomic Identity Assignment
        │◄── VALIDATION_RESULT ─────────────────│
        │    {assigned_id, cert, role, expiry}   │
        │                                       │
        │ ── ACK ──────────────────────────────►│
```

---

### Step 1 — Timestamp and Blocklist Check

**Purpose:** Reject stale requests and known-bad controllers immediately, before
doing any expensive cryptographic work.

**Logic:**

```python
FRESHNESS_WINDOW_SECONDS = 300  # 5 minutes — configurable in policy

def step1_timestamp_and_blocklist(req):
    now = utc_now()
    request_age = (now - req.timestamp).total_seconds()

    if request_age > FRESHNESS_WINDOW_SECONDS:
        write_audit(AUDIT_REJECT, req.temp_id, reason="STALE_TIMESTAMP",
                    age_seconds=request_age)
        return Reject("STALE_TIMESTAMP")

    if request_age < 0:
        # Clock skew or replay from the future — also reject
        write_audit(AUDIT_REJECT, req.temp_id, reason="FUTURE_TIMESTAMP")
        return Reject("FUTURE_TIMESTAMP")

    if blocklist.contains(req.temp_id):
        write_audit(AUDIT_REJECT, req.temp_id, reason="BLOCKLISTED")
        return Reject("BLOCKLISTED")

    return Continue
```

**NIB writes at this step:** Audit log entry written on reject. Nothing written on
continue — writing on continue would create noise from failed attempts that never
complete.

---

### Step 2 — Bootstrap Token Validation

**Purpose:** Confirm the requesting controller was legitimately provisioned — it
holds the token that was issued to it during the provisioning process.

**Important: the bootstrap token does NOT replace the challenge-response.**
This is the security fix from the original design. The token proves:
- "I was provisioned with the right secret" ✓

But it does NOT prove:
- "I am the specific controller that was provisioned" ✗

A stolen token could be replayed by any process. The challenge-response in Step 3
is what proves key ownership. The bootstrap token is only a prerequisite gate —
pass it or stop here. It never grants a shortcut to identity assignment.

```python
def step2_bootstrap_token(req):
    # The bootstrap token is HMAC-SHA256(temp_id + region + type, provisioning_secret)
    # The provisioning_secret was issued to this controller during deployment
    expected_token = hmac_sha256(
        message=f"{req.temp_id}:{req.region}:{req.controller_type}",
        key=provisioning_secret_store.get(req.region, req.controller_type)
    )

    if not hmac_compare_digest(req.bootstrap_token, expected_token):
        write_audit(AUDIT_REJECT, req.temp_id, reason="INVALID_BOOTSTRAP_TOKEN")
        # Flag for security review — invalid tokens may indicate a provisioning
        # error or an active attack
        security_events.flag(req.temp_id, req.sender_ip, "INVALID_TOKEN_ATTEMPT")
        return Reject("INVALID_BOOTSTRAP_TOKEN")

    # Token is single-use: mark it consumed to prevent replay
    provisioning_secret_store.consume_token(req.region, req.controller_type, req.temp_id)

    return Continue
```

**Why token is single-use:** Once a controller has been validated once, the bootstrap
token must be invalidated. If a second registration request arrives for the same
`temp_id` after a successful validation, it is either a misconfiguration or an
attacker trying to register a second controller with the same credentials.

**NIB writes at this step:** Audit entry on reject. Token consumed from provisioning
store on continue (this is a side-effect write, not a NIB write — the provisioning
store is separate from the NIB).

---

### Step 3 — Issue Challenge

**Purpose:** Generate a cryptographic challenge that only the holder of the private
key corresponding to `req.public_key` can answer correctly. This is the step that
proves *key ownership*, not just token possession.

```python
def step3_issue_challenge(req):
    nonce = generate_cryptographic_nonce(length=32)  # 256 bits

    challenge = {
        "challenge_id": generate_uuid(),
        "temp_id": req.temp_id,
        "nonce": base64_encode(nonce),
        "issued_at": utc_now_iso(),
        "expires_at": (utc_now() + timedelta(seconds=CHALLENGE_TIMEOUT)).isoformat()
    }

    # Store challenge state so we can verify the response
    pending_challenges[challenge["challenge_id"]] = {
        "nonce": nonce,
        "temp_id": req.temp_id,
        "public_key": req.public_key,
        "expires_at": challenge["expires_at"]
    }

    send_message(
        recipient=req.temp_id,
        message_type="CHALLENGE",
        payload=challenge
    )

    return WaitForResponse(
        challenge_id=challenge["challenge_id"],
        timeout_seconds=CHALLENGE_TIMEOUT  # default: 30 seconds
    )
```

**NIB writes at this step:** None. The pending challenge is held in in-memory state
only — it is short-lived and does not need to survive a restart.

---

### Step 4 — Verify Challenge Response

**Purpose:** Confirm the requesting controller signed the nonce with the private key
corresponding to the public key it submitted. This proves it controls that key.

```python
CHALLENGE_TIMEOUT = 30  # seconds

def step4_verify_challenge_response(challenge_id, response):
    pending = pending_challenges.get(challenge_id)

    if pending is None:
        write_audit(AUDIT_REJECT, response.temp_id, reason="UNKNOWN_CHALLENGE_ID")
        return Reject("UNKNOWN_CHALLENGE")

    if utc_now_iso() > pending["expires_at"]:
        del pending_challenges[challenge_id]
        write_audit(AUDIT_REJECT, response.temp_id, reason="CHALLENGE_EXPIRED")
        return Reject("CHALLENGE_EXPIRED")

    if response.temp_id != pending["temp_id"]:
        write_audit(AUDIT_REJECT, response.temp_id, reason="TEMP_ID_MISMATCH")
        return Reject("TEMP_ID_MISMATCH")

    # Verify the signature: the controller must have signed the nonce
    # using the private key corresponding to the public_key in the original request
    signature_valid = verify_ed25519_signature(
        message=pending["nonce"],
        signature=base64_decode(response.signed_nonce),
        public_key=base64_decode(pending["public_key"])
    )

    del pending_challenges[challenge_id]  # Challenge consumed regardless of outcome

    if not signature_valid:
        write_audit(AUDIT_REJECT, response.temp_id, reason="INVALID_SIGNATURE")
        security_events.flag(response.temp_id, "SIGNATURE_FAILURE")
        return Reject("INVALID_SIGNATURE")

    return Continue(public_key=pending["public_key"])
```

**Why the challenge expires:** An unanswered challenge sitting in memory indefinitely
is a denial-of-service vector — an attacker could flood the validator with requests
and exhaust memory. The 30-second window is generous for a legitimate controller on
any reasonable network path.

**NIB writes at this step:** Audit entry on reject.

---

### Step 5 — Policy and Metadata Verification

**Purpose:** Ensure the requesting controller is permitted to join the system in
the role and region it claims. Even a controller with valid credentials can be
rejected if policy does not allow its role or region.

```python
def step5_policy_checks(req, validated_public_key):
    policy = nib.get_active_policy(scope="global")

    # Check 1: Is this controller type permitted to register right now?
    if req.controller_type not in policy.permitted_controller_types:
        write_audit(AUDIT_REJECT, req.temp_id, reason="TYPE_NOT_PERMITTED",
                    controller_type=req.controller_type)
        return Reject("CONTROLLER_TYPE_NOT_PERMITTED")

    # Check 2: Is this region a valid zone?
    if req.region not in policy.valid_regions:
        write_audit(AUDIT_REJECT, req.temp_id, reason="INVALID_REGION",
                    region=req.region)
        return Reject("INVALID_REGION")

    # Check 3: For Local Controllers — is the claimed region served by
    # this validating RC? (Prevents a LC from registering with the wrong RC)
    if req.controller_type == "local":
        if req.region not in this_controller.managed_regions:
            write_audit(AUDIT_REJECT, req.temp_id, reason="REGION_NOT_SERVED_BY_THIS_RC",
                        region=req.region, rc_id=this_controller.assigned_id)
            return Reject("REGION_NOT_SERVED_BY_THIS_RC")

    # Check 4: Has the regional controller quota been reached?
    current_count = nib.count_active_controllers(
        controller_type=req.controller_type,
        region=req.region
    )
    max_allowed = policy.max_controllers_per_region.get(req.controller_type, 10)

    if current_count >= max_allowed:
        write_audit(AUDIT_REJECT, req.temp_id, reason="QUOTA_EXCEEDED",
                    current=current_count, max=max_allowed)
        return Reject("CONTROLLER_QUOTA_EXCEEDED")

    return Continue(validated_public_key=validated_public_key)
```

**NIB reads at this step:** `get_active_policy()`, `count_active_controllers()`
**NIB writes at this step:** Audit entries on reject only.

---

### Step 6 — Atomic Identity Assignment

**Purpose:** Assign the validated controller a permanent identity and write its
record to the NIB. This step has an atomicity requirement: the certificate
issuance and the NIB context write must both succeed, or both must be rolled back.
A certificate without a NIB record means the controller has credentials that cannot
be verified. A NIB record without a certificate means the controller has no way
to prove its identity.

```python
def step6_atomic_identity_assignment(req, validated_public_key):
    assigned_id = allocate_controller_id(req.controller_type, req.region)
    # Format: regional_cntl_<region>_<sequence> or local_cntl_<region>_<sequence>
    # e.g., regional_cntl_zoneA_3

    role = determine_role(req.controller_type)
    expiry = utc_now() + timedelta(days=CERT_VALIDITY_DAYS)  # default: 90 days

    # Build the certificate (PoC: signed JSON object; Phase 6: Ed25519-signed)
    cert_payload = {
        "assigned_id": assigned_id,
        "role": role,
        "region": req.region,
        "public_key": validated_public_key,
        "issued_by": this_controller.assigned_id,
        "issued_at": utc_now_iso(),
        "expires_at": expiry.isoformat()
    }
    cert_payload["signature"] = hmac_sha256(
        message=canonical_json(cert_payload),
        key=this_controller.signing_key
    )

    # ── ATOMIC SECTION ──────────────────────────────────────────────────
    # Both writes must succeed. If either fails, roll back both.
    try:
        # Write 1: Store the controller record in the NIB
        nib_result = nib.register_controller(
            assigned_id=assigned_id,
            temp_id=req.temp_id,
            controller_type=req.controller_type,
            region=req.region,
            public_key=validated_public_key,
            validated_by=this_controller.assigned_id,
            cert_signature=cert_payload["signature"],
            status="active",
            expires_at=expiry
        )

        if not nib_result.success:
            raise AtomicCommitFailure(
                f"NIB write failed: {nib_result.error}"
            )

        # Write 2: Write audit entry confirming successful validation
        audit_result = nib.write_event(Event(
            event_type="CONTROLLER_VALIDATED",
            actor=this_controller.assigned_id,
            subject=assigned_id,
            action=f"Validated {req.controller_type} controller. "
                   f"temp_id={req.temp_id} assigned_id={assigned_id}",
            decision="APPROVED"
        ))

        if not audit_result.success:
            # Audit failure is not a reason to invalidate the controller,
            # but it must be flagged — we have a gap in the audit trail
            security_events.flag(
                assigned_id,
                "AUDIT_WRITE_FAILURE_POST_VALIDATION"
            )
            # Do NOT roll back — the controller is valid. Log the gap.

    except AtomicCommitFailure as e:
        # Roll back: the cert was never sent, so no rollback needed on the cert.
        # Just write a failure audit entry and return an error.
        nib.write_event(Event(
            event_type="VALIDATION_COMMIT_FAILURE",
            actor=this_controller.assigned_id,
            subject=req.temp_id,
            action=f"Identity assignment failed during NIB commit: {e}",
            decision="FAILED"
        ))
        return Error("IDENTITY_ASSIGNMENT_FAILED")
    # ── END ATOMIC SECTION ──────────────────────────────────────────────

    # If validating controller is a GC validating an RC,
    # also issue a delegation credential so the RC can validate LCs
    delegation_credential = None
    if this_controller.role == "global" and req.controller_type == "regional":
        delegation_credential = issue_delegation_credential(
            delegatee_id=assigned_id,
            delegatee_region=req.region,
            permitted_actions=["validate_local_controllers"],
            issued_by=this_controller.assigned_id,
            expires_at=expiry
        )

    return ValidationResult(
        status="APPROVED",
        assigned_id=assigned_id,
        certificate=cert_payload,
        delegation_credential=delegation_credential,  # None for LC validations
        role=role,
        region=req.region
    )
```

**NIB writes at this step:**
- `nib.register_controller()` — permanent controller record in the Controller
  Sync Table (new entry, not an update to an existing record)
- `nib.write_event()` — audit log entry for the validation event

**Atomicity requirement:** Both writes must succeed or both must be treated as
failed. The system must not be left in a state where a certificate exists but no
NIB record does, or where a NIB record exists but no certificate was issued.

---

## Complete Pseudocode (Integrated)

```python
def validate_registration(req):
    """
    Main entry point for the validation flow.
    Called by GlobalController for Regional Controllers,
    called by RegionalController for Local Controllers.
    """

    # Step 1 — Timestamp and blocklist
    result = step1_timestamp_and_blocklist(req)
    if result.is_reject():
        return ValidationResult(status="REJECTED", reason=result.reason)

    # Step 2 — Bootstrap token
    result = step2_bootstrap_token(req)
    if result.is_reject():
        return ValidationResult(status="REJECTED", reason=result.reason)

    # Step 3 — Issue challenge (always runs — no shortcut path)
    challenge_state = step3_issue_challenge(req)

    # Step 4 — Verify challenge response (async — await the reply)
    response = await_challenge_response(
        challenge_id=challenge_state.challenge_id,
        timeout=CHALLENGE_TIMEOUT
    )
    if response is None:
        write_audit(AUDIT_REJECT, req.temp_id, reason="CHALLENGE_TIMEOUT")
        return ValidationResult(status="REJECTED", reason="CHALLENGE_TIMEOUT")

    result = step4_verify_challenge_response(challenge_state.challenge_id, response)
    if result.is_reject():
        return ValidationResult(status="REJECTED", reason=result.reason)

    # Step 5 — Policy checks
    result = step5_policy_checks(req, result.public_key)
    if result.is_reject():
        return ValidationResult(status="REJECTED", reason=result.reason)

    # Step 6 — Atomic identity assignment
    result = step6_atomic_identity_assignment(req, result.validated_public_key)
    if result.is_error():
        return ValidationResult(status="ERROR", reason=result.reason)

    return result  # Contains assigned_id, cert, role, delegation_credential
```

---

## Error State Table

Every error has a defined reason code, what triggered it, and what the validator
must do after rejecting.

| Reason Code | Triggered By | Validator Action | Audit Written? |
|------------|--------------|-----------------|----------------|
| `STALE_TIMESTAMP` | Request older than 5 min | Reject, write audit | Yes |
| `FUTURE_TIMESTAMP` | Request timestamp in the future | Reject, write audit | Yes |
| `BLOCKLISTED` | `temp_id` on the blocklist | Reject, write audit, alert | Yes |
| `INVALID_BOOTSTRAP_TOKEN` | Token does not match provisioning record | Reject, flag for security review | Yes |
| `UNKNOWN_CHALLENGE` | Response references unknown challenge ID | Reject, write audit | Yes |
| `CHALLENGE_EXPIRED` | Response arrived after 30-second window | Reject, write audit | Yes |
| `TEMP_ID_MISMATCH` | Response `temp_id` ≠ challenge `temp_id` | Reject, write audit, flag | Yes |
| `INVALID_SIGNATURE` | Signature does not verify against submitted pubkey | Reject, write audit, flag | Yes |
| `CHALLENGE_TIMEOUT` | No response received within timeout window | Reject, write audit | Yes |
| `CONTROLLER_TYPE_NOT_PERMITTED` | Policy does not allow this type currently | Reject, write audit | Yes |
| `INVALID_REGION` | Region not in valid regions list | Reject, write audit | Yes |
| `REGION_NOT_SERVED_BY_THIS_RC` | LC claims region not managed by this RC | Reject, write audit | Yes |
| `CONTROLLER_QUOTA_EXCEEDED` | Max controllers for this region/type reached | Reject, write audit | Yes |
| `IDENTITY_ASSIGNMENT_FAILED` | NIB commit failed during Step 6 | Return error (not reject), write audit, alert operator | Yes |

**Key distinction between REJECTED and ERROR:** A `REJECTED` result means the
requesting controller failed a validation check — it was not legitimate or did not
pass policy. An `ERROR` result means the requesting controller passed all validation
steps but the system failed to complete the registration — this is a PDSNO-side
problem that requires operator attention, not a problem with the requesting controller.

---

## Security Considerations

**Timestamp freshness** prevents replay attacks where an intercepted validation
request is re-sent later. The 5-minute window accommodates reasonable clock skew
between controllers.

**Bootstrap token as prerequisite, not shortcut.** The original design allowed the
bootstrap token to skip the challenge-response. This was removed. The token proves
provisioning legitimacy. The challenge proves key ownership. Both are needed. Neither
substitutes for the other.

**Single-use tokens and challenges.** Both the bootstrap token and the challenge
nonce are consumed on use. This prevents a valid token or a captured challenge
response from being replayed.

**Blocklist checked before cryptographic work.** The blocklist check happens in Step 1
before any HMAC verification or challenge issuance. This ensures a known-bad
controller cannot use a validation attempt as a way to consume validator resources.

**Delegation credential scope.** When a GC delegates LC validation authority to
an RC, the delegation credential is scoped to a specific region and a specific
permitted action. An RC cannot use its delegation credential to validate other
RCs or to act outside its designated zone.

---

## Future Enhancements

These are out of scope for the PoC but should be addressed before production deployment:

**Phase 6 — Asymmetric certificates:** Replace HMAC-signed JSON certificates with
Ed25519-signed certificates. The validator's public key should be independently
verifiable by any controller, not just by holders of the shared HMAC key.

**Phase 6 — Key rotation:** Bootstrap tokens and controller certificates both expire.
The re-validation flow (what happens when a certificate expires and the controller
needs to renew) is not yet designed. This must be resolved before Phase 6.

**Future — Validation ledger:** Recording the full validation history in a
tamper-evident append-only store (beyond the NIB Event Log) would provide a stronger
audit trail for compliance purposes. Blocked hash chains or a merkle tree structure
would make it computationally infeasible to retroactively alter validation records.

**Future — Dynamic role adjustment:** Promotion (LC → RC) or demotion of controllers
based on trust metrics or operational status. Requires careful design to prevent
privilege escalation.
