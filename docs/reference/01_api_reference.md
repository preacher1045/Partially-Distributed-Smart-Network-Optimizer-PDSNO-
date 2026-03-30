---
title: API Reference
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: communication_model.md, architecture.md
---

# PDSNO — API Reference

## Message Types

All inter-controller messages use the standard envelope defined in `communication_model.md`.
This document catalogs every defined message type, its direction, required payload fields,
and the response it expects.

---

## Controller Validation Messages

### VALIDATION_REQUEST
**Direction:** Unvalidated controller → GC (for RC) or RC (for LC)
**Transport:** REST POST

```json
{
  "temp_id": "temp-<uuid>",
  "controller_type": "regional | local",
  "region": "zone-A",
  "public_key": "<base64 Ed25519 pubkey>",
  "bootstrap_token": "<hmac-sha256>",
  "metadata": {
    "hostname": "string",
    "ip_address": "string",
    "software_version": "string",
    "capabilities": ["discovery", "approval", "policy_enforcement"]
  }
}
```

### CHALLENGE
**Direction:** Validator → Requesting controller
**Transport:** REST response to VALIDATION_REQUEST

```json
{
  "challenge_id": "uuid",
  "temp_id": "string",
  "nonce": "<base64 32-byte random>",
  "issued_at": "ISO-8601",
  "expires_at": "ISO-8601"
}
```

### CHALLENGE_RESPONSE
**Direction:** Requesting controller → Validator
**Transport:** REST POST

```json
{
  "challenge_id": "uuid",
  "temp_id": "string",
  "signed_nonce": "<base64 Ed25519 signature of nonce>"
}
```

### VALIDATION_RESULT
**Direction:** Validator → Requesting controller
**Transport:** REST response to CHALLENGE_RESPONSE

```json
{
  "status": "APPROVED | REJECTED | ERROR",
  "assigned_id": "regional_cntl_zoneA_1",
  "certificate": { "assigned_id": "...", "role": "...", "signature": "..." },
  "delegation_credential": null,
  "role": "regional | local",
  "region": "zone-A",
  "reason": "string (on REJECTED/ERROR)"
}
```

---

## Discovery Messages

### DISCOVERY_REQUEST
**Direction:** RC or GC → LC
**Transport:** REST POST

```json
{
  "request_id": "uuid",
  "trigger": "SCHEDULED | ON_DEMAND | BOOTSTRAP | RC_REQUESTED_OVERDUE",
  "subnets": ["10.0.1.0/24"],
  "protocols": ["arp", "icmp", "snmp"]
}
```

### DISCOVERY_REPORT
**Direction:** LC → RC
**Transport:** REST POST

```json
{
  "report_id": "uuid",
  "lc_id": "local_cntl_zoneA_1",
  "region": "zone-A",
  "scan_start": "ISO-8601",
  "scan_end": "ISO-8601",
  "new_devices": [ { "mac_address": "...", "ip_address": "...", "vendor": "..." } ],
  "updated_devices": [ { "entity_id": "nib-dev-001", "mac_address": "...", "status": "active" } ],
  "inactive_devices": ["nib-dev-003"],
  "total_devices_seen": 47,
  "write_summary": { "new": 2, "updated": 1, "inactive": 0, "conflicts": 0 },
  "policy_version": "region1-v3.2"
}
```

### DISCOVERY_SUMMARY
**Direction:** RC → GC
**Transport:** REST POST

```json
{
  "summary_id": "uuid",
  "rc_id": "regional_cntl_zoneA_1",
  "region": "zone-A",
  "cycle_start": "ISO-8601",
  "cycle_end": "ISO-8601",
  "total_new": 2,
  "total_updated": 5,
  "total_inactive": 1,
  "total_devices_in_region": 134,
  "anomalies_flagged": [],
  "lcs_reported": ["local_cntl_zoneA_1", "local_cntl_zoneA_2"],
  "lcs_missing": []
}
```

---

## Config Approval Messages

### CONFIG_PROPOSAL
**Direction:** LC → RC
**Transport:** REST POST

```json
{
  "proposal_id": "uuid",
  "config_payload": {},
  "config_hash": "sha256-hex",
  "target_devices": ["nib-dev-001"],
  "suggested_sensitivity": "MEDIUM",
  "impact_scope": "regional",
  "rollback_payload": {},
  "timestamp": "ISO-8601",
  "policy_version": "region1-v3.2",
  "origin": "local_cntl_zoneA_1",
  "origin_signature": "hmac-sha256-hex"
}
```

### APPROVAL_RESPONSE
**Direction:** RC → LC (or GC → RC)
**Transport:** REST response

```json
{
  "proposal_id": "uuid",
  "decision": "APPROVE | DENY | ESCALATE",
  "responder": "regional_cntl_zoneA_1",
  "timestamp": "ISO-8601",
  "responder_signature": "hmac-sha256-hex",
  "reason": "string (on DENY)",
  "escalation_target": "global_cntl_1"
}
```

### EXECUTION_INSTRUCTION
**Direction:** RC → LC
**Transport:** REST POST

```json
{
  "proposal_id": "uuid",
  "execution_token": {
    "token_id": "uuid",
    "proposal_id": "uuid",
    "config_hash": "sha256-hex",
    "target_devices": ["nib-dev-001"],
    "approved_by": "regional_cntl_zoneA_1",
    "issued_at": "ISO-8601",
    "expires_at": "ISO-8601",
    "constraints": { "max_devices_per_minute": 10, "rollback_required_on_failure": true },
    "signature": "hmac-sha256-hex"
  },
  "execute_at": null
}
```

### EXECUTION_RESULT
**Direction:** LC → RC
**Transport:** REST POST

```json
{
  "proposal_id": "uuid",
  "executor": "local_cntl_zoneA_1",
  "status": "EXECUTED | FAILED | ROLLED_BACK | DEGRADED",
  "device_results": { "nib-dev-001": "SUCCESS" },
  "timestamp": "ISO-8601",
  "execution_signature": "hmac-sha256-hex"
}
```

---

## Policy Messages

### POLICY_UPDATE
**Direction:** GC → RC → LC
**Transport:** MQTT publish to `pdsno/{region}/policy/updates`

```json
{
  "policy_id": "uuid",
  "policy_version": "region1-v3.3",
  "scope": "global | regional | local",
  "target_region": "zone-A",
  "content": {},
  "distributed_by": "global_cntl_1",
  "valid_from": "ISO-8601"
}
```

---

## Event Notification Topics (MQTT)

| Topic | Publisher | Subscriber | Purpose |
|-------|-----------|-----------|---------|
| `pdsno/{region}/discovery/reports` | LC | RC | Discovery report submission |
| `pdsno/global/policy/updates` | GC | All RCs | Global policy broadcast |
| `pdsno/{region}/policy/updates` | RC | All LCs in region | Regional policy propagation |
| `pdsno/global/events` | Any | Monitoring systems | System-wide event feed |
| `pdsno/{controller_id}/notifications` | RC or GC | Specific controller | Targeted alerts |

---

## NBI REST Endpoints (Phase 6)

External applications access PDSNO through the Global Controller's NBI.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/devices` | List all devices in global NIB |
| `GET` | `/api/v1/devices/{device_id}` | Get device record |
| `GET` | `/api/v1/devices/{device_id}/history` | Config history for device |
| `GET` | `/api/v1/proposals` | List config proposals (filterable by status) |
| `GET` | `/api/v1/proposals/{proposal_id}` | Get proposal detail + audit trail |
| `POST` | `/api/v1/proposals` | Submit config proposal (from external tool) |
| `GET` | `/api/v1/policy` | Get active global policy |
| `PUT` | `/api/v1/policy` | Update global policy (authorized operators only) |
| `GET` | `/api/v1/audit` | Query Event Log (filterable by time, actor, event type) |
| `GET` | `/api/v1/controllers` | List all registered controllers and their status |
| `GET` | `/api/v1/health` | System health summary |

All NBI endpoints require a valid `Authorization: Bearer <token>` header.
Authentication mechanism for external clients is defined separately in Phase 6 design.
