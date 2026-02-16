---
title: Data Flow
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: architecture.md, communication_model.md, nib/nib_spec.md
---

# PDSNO — Data Flow

## Overview

Three primary data flows drive PDSNO's operation. Understanding them together shows how discovery feeds approval, and how both feed the audit trail.

---

## Flow 1 — Device Discovery

```
Network Devices
     │  ARP / ICMP / SNMP (SBI)
     ▼
Local Controller
  [Stage 1] Read policy → build scan targets
  [Stage 2] Run parallel scans (ARP + ICMP + SNMP)
  [Stage 3] Consolidate per-device (keyed on MAC)
  [Stage 4] Diff against local NIB
  [Stage 5] Write to NIB:
            Device Table ← new/updated/inactive records
            Event Log   ← DEVICE_DISCOVERED / UPDATED / INACTIVE
  [Stage 6] Send DISCOVERY_REPORT to RC (delta only)
     │
     ▼
Regional Controller
  [Stage 7]  Validate report (LC identity + policy version)
  [Stage 8]  Deduplicate across LCs (MAC = canonical key)
  [Stage 9]  Write to regional NIB; flag anomalies
  [Stage 10] Send DISCOVERY_SUMMARY to GC
     │
     ▼
Global Controller
  [Stage 11] Global deduplication (cross-region MAC check)
  [Stage 12] Update global NIB view
  [Stage 13] Escalate flagged anomalies to NBI
```

**Data direction:** Upward (LC → RC → GC). Each tier writes to its own NIB view.
**Data type:** Delta reports — only changed devices travel up, not full inventories.

---

## Flow 2 — Configuration Approval

```
Local Controller
  Propose → write PENDING to Config Table → send to RC
     │
     ▼
Regional Controller
  Re-classify sensitivity
  Acquire device locks (Controller Sync Table)
  LOW/MEDIUM → approve, issue token, write APPROVED
  HIGH → escalate to GC, await response
     │ (if HIGH)
     ▼
Global Controller
  Check immutable policy rules
  Approve or deny → write to Event Log
  Issue execution token (HIGH category)
     │
     ▼ (approval flows back down)
Regional Controller → forwards execution instruction to LC
     │
     ▼
Local Controller
  Verify token (signature + binding + expiry + single-use)
  Write EXECUTING → apply config to devices → write EXECUTED
  On failure → rollback → write ROLLED_BACK or DEGRADED
  Release device locks
  Report result to RC
```

**Data direction:** Proposal flows upward (LC → RC → GC). Approval + token flows downward (GC → RC → LC). Result flows upward.
**Data type:** Signed JSON messages via REST for request/response legs.

---

## Flow 3 — Policy Distribution

```
Global Controller
  Policy created/updated
  Write to NIB Policy Table (global scope)
  Publish POLICY_UPDATE to MQTT topic: pdsno/global/policy/updates
     │
     ▼
Regional Controllers (subscribed)
  Receive policy delta
  Validate signature + version
  Write to regional NIB Policy Table
  Publish to local MQTT topic: pdsno/{region}/policy/updates
     │
     ▼
Local Controllers (subscribed)
  Receive policy delta
  Validate + write to local NIB Policy Table
  All future proposals/decisions use new policy version
```

**Data direction:** Downward only (GC → RC → LC). Policy is never written by lower tiers.
**Data type:** MQTT pub/sub (QoS 2 — exactly-once for policy). Delta updates, not full policy dumps.

---

## NIB as the Data Hub

All three flows converge in the NIB. The NIB is not a passive store — it is the coordination point:

```
Discovery Flow  ──► Device Table + Metadata Store
                         │
                         ▼ (RC reads device state for approval decisions)
Approval Flow   ──► Config Table + Controller Sync Table
                         │
                         ▼ (both flows write to Event Log)
Policy Flow     ──► Policy Table
                         │
                         ▼
                    Event Log (all flows)
```
