# PDSNO — Configuration Approval Logic (Architecture Spec)

Version: Draft — Hybrid Approval (core now, advanced optional later)

---

## 1. Goals & Principles

1. **Safety-first** — prevent accidental or malicious config pushes that can damage production networks.
2. **Speed where safe** — low-risk changes should deploy fast (Local or Regional only).
3. **Escalation for risk** — high-risk changes require higher-tier approval (Regional → Global).
4. **Auditability & Forensics** — every request, decision, and action is logged in NIB-backed audit records.
5. **Resilience** — timeouts, retries, and fallback rules to avoid blocking operations permanently.
6. **Extensibility** — schema and logic are designed so advanced features (risk scoring, multi-sign) can be added later.

---

## 2. Actors & Responsibilities

### Actors (abbrev.)

* **LC** — Local Controller (executes changes, can propose changes)
* **RC** — Regional Controller (governs region, approves/denies most changes)
* **GC** — Global Controller (final authority for critical changes, holds global policy)
* **NIB** — Network Information Base (Local NIB tables, Regional/Global views)
* **AuditStore** — persistent audit log (local and regional)

### Responsibilities

* **LC**

  * Propose config changes (originates request).
  * Enforce local policy; execute approved changes.
  * Send signed requests to RC/GC.
  * Immediately log actions to Local NIB and AuditStore.
* **RC**

  * Validate config proposal vs regional policy and context from Regional NIB view.
  * Approve/deny or forward to GC if critical or ambiguous.
  * Maintain regional approval history in Regional NIB view and AuditStore.
* **GC**

  * Acts on critical or high-impact approvals.
  * Maintains global policy and per-policy lock flags (immutable rules).
  * Issues signed approvals/certificates.
* **NIB**

  * Stores state used for decisioning (device metadata, recent discovery events, policy version).
  * Stores approval tokens and sync state per controller.
* **AuditStore**

  * Stores tamper-evident audit entries (signed by originating controller).

---

## 3. Config Categories & Sensitivity Levels

Design a small, extendable taxonomy now; can be extended later.

### Categories (3-core + metadata)

1. **LOW (Safe)**

   * Examples: add SNMP read-only community to an inventory, adjust local discovery schedule minor tweak, logging level updates.
   * Approval: **Local** (LC) or RC auto-approve based on policy.
2. **MEDIUM (Operational)**

   * Examples: interface shutdown on non-production VLAN, routing policy tweak on branch office, security policy changes that affect a subset of traffic.
   * Approval: **Regional** required (RC evaluates + authorizes).
3. **HIGH / CRITICAL (Risky)**

   * Examples: core routing change, firewall deny-all rule at region edge, firmware updates on core devices, config pushing to devices in multiple regions.
   * Approval: **Global + Regional** (GC must sign off; RC enforces region-level gating).
4. **EMERGENCY (Immediate bypass allowed)**

   * Examples: active DDoS mitigation, immediate quarantine of compromised device.
   * Approval: **LC may execute immediately** but must create an emergency report and notify RC & GC (post-facto approval & audit). Emergency mode can be gated by a toggle in policy.

### Sensitivity metadata (for each config request)

* `category`: LOW|MEDIUM|HIGH|EMERGENCY
* `impact_scope`: local|regional|global
* `affected_devices`: list of device_ids (NIB IDs)
* `estimated_downtime`: seconds | null
* `requires_maintenance_window`: true|false
* `requires_multi_signature`: true|false (advanced feature)

---

## 4. Decision Rules & Escalation Paths

### 4.1 Overview (core rules)

* If `category == LOW` and request conforms to `nib_policy` and `RC.allow_local_exec == true` → **RC auto-approve** OR **LC may execute** (policy-dependent).
* If `category == MEDIUM` → **RC decides**. RC can approve or escalate to GC if policy or context demands.
* If `category == HIGH` → **GC approval required**. RC forwards request to GC with context. GC reviews (may consult Regional NIB) → GC approves/denies → RC enforces and instructs LC to execute.
* If `category == EMERGENCY` and `policy.emergency_allow_local_exec == true` → **LC may execute immediately**, then generate audit + follow-up approval flow (RC & GC must ACK within window or create rollback).
* Global `immutable` policy flags override local/regional overrides. If a config conflicts with immutable global rules → **deny**.

### 4.2 Escalation triggers (automatic)

RC must escalate to GC when:

* The `impact_scope == global` OR
* `affected_devices` include devices from multiple regions OR
* `estimated_downtime > threshold` OR
* `policy.sensitivity_score(affected_devices) >= threshold` (future feature) OR
* RC policy explicitly requires GC for that object type.

LC should escalate to RC when:

* LC cannot validate device state from Local NIB (stale data) OR
* Device shows suspicious metadata in NIB (new vendor, previously quarantined) OR
* Local policy forbids direct execution (e.g., device in protected list)

### 4.3 Deny behavior

* Immediate deny must include a `reason_code` and an optional `suggested_action` (e.g., “reschedule to maintenance window”, “request rollback authorization”).
* Denied requests are stored as `denied_event` in NIB + AuditStore.

---

## 5. Message Flows & Required Fields

Standard message envelope used across LC↔RC↔GC. All messages are signed and timestamped.

### 5.1 Config Request (from LC → RC)

```json
{
  "request_id": "uuid-v4",
  "origin": "lc_id",
  "origin_signature": "...",            // signed by LC private key
  "timestamp": "2025-12-07T12:34:56Z",
  "category": "MEDIUM",
  "impact_scope": "regional",
  "affected_devices": ["nib-dev-001","nib-dev-002"],
  "config_payload": { ... },           // device-specific commands / structured model
  "requires_maintenance_window": false,
  "estimated_downtime": 0,
  "policy_version": "region1-scan-v3",
  "context_snapshot": {                // optional, pulled from Local NIB
     "device_states": { ... },
     "last_discovery_ts": "..."
  }
}
```

### 5.2 RC Response (approve/deny/escalate)

```json
{
  "request_id": "uuid-v4",
  "responder": "rc_id",
  "timestamp": "...",
  "decision": "APPROVE" | "DENY" | "ESCALATE",
  "responder_signature": "...",
  "notes": "optional notes",
  "escalation_target": "gc_id"         // if ESCALATE
}
```

### 5.3 GC Response (if escalated)

```json
{
  "request_id":"uuid-v4",
  "responder":"gc_id",
  "decision":"APPROVE" | "DENY",
  "responder_signature":"...",
  "policy_override_flag": false,       // true if GC overrides regional rule
  "notes":"..."
}
```

### 5.4 Execution Instruction (RC → LC)

If approved:

```json
{
  "request_id":"uuid-v4",
  "execute_at":"YYYY-MM-DDTHH:MM:SSZ" or null,
  "execution_token":"signed-token",    // short-lived
  "execution_instructions": {...}
}
```

### 5.5 Execution Result (LC → RC + AuditStore)

```json
{
  "request_id":"uuid-v4",
  "executor":"lc_id",
  "status":"SUCCESS" | "FAILED" | "ROLLED_BACK",
  "details":"...",
  "execution_signature":"..."
}
```

All messages recorded in AuditStore and referenced in NIB Controller Sync Table.

---

## 6. Timeouts, Retries & Fallback Rules

### Default timeouts (configurable policy)

* `rc_response_timeout`: 30 seconds (default)
* `gc_response_timeout`: 5 minutes (default)
* `execution_token_ttl`: 10 minutes (default)
* `emergency_postfact_timeout`: 10 minutes (time RC/GC must acknowledge emergency execution)

### Retry logic

* LC sends first request to RC; if RC does not respond within `rc_response_timeout`, LC retries up to `rc_max_retries` (default 3) with exponential backoff.
* If no RC response, LC logs `rc_unreachable` and **does not execute** unless `category == EMERGENCY` and `policy.emergency_allow_local_exec == true`.
* If RC forwards to GC, RC waits GC response up to `gc_response_timeout`. If GC unreachable, RC can either:

  * apply local/regional fallback policy (e.g., deny by default), or
  * if `policy.allow_local_fallback_on_gc_unreachable == true`, allow RC to make decision with elevated audit. Fallback must be tightly scoped.

### Rollbacks

* If `execution_result.status == FAILED` and config changed partial state, LC attempts rollback using `rollback_instructions` if provided.
* Rollback itself is an event that must be logged and if rollback fails, escalate to RC/GC immediately.

---

## 7. Conflict Handling & Concurrency

### Conflicting concurrent requests

* Each request locks affected NIB entries using `Controller Sync Table` transaction flags. Locks are soft and expire in `lock_ttl` (policy).
* If a second request touches the same device(s) while lock is active, RC responds `DENY_CONFLICT` or queues based on `policy.queue_conflicts`.
* Queueing: RC can enqueue lower-priority requests; GC can reorder based on priority.

### Policy version mismatch

* If `request.policy_version` differs from RC/GC current `policy_version`, RC rejects with `reason:policy_mismatch` and suggests `target_policy_version` or `force_update`.

---

## 8. Audit & NIB Integration

### Audit entries (minimum fields)

* `audit_id`, `request_id`, `actor`, `action`, `decision`, `timestamp`, `signature`, `notes`, `nib_snapshot_ref`.

### Where to store

* Local NIB stores local audit logs locally (retention per `policy.logging.retention_days_local`).
* RC aggregates and stores regional audit entries (retention per regional policy).
* GC stores high-level audit summary entries.

### Tamper-evidence

* All requests/responses/executions are signed. AuditStore should support append-only storage and optionally cryptographic chaining.

### Using NIB data for decisions

* RC/GC use `context_snapshot` pulled from NIB to decide: device health, last_discovery_ts, quarantined flag, known vulnerabilities, previous failed changes, etc.
* RC caches NIB snapshots for short windows to reduce chatter.

---

## 9. Edge Cases & Emergency Handling

### Emergency execution

* LC may execute if:

  * `category == EMERGENCY` AND `policy.emergency_allow_local_exec == true`
  * OR explicit emergency_override token present (rare)
* LC must:

  * Immediately create `emergency_event` in Local NIB + AuditStore with full payload and signature.
  * Notify RC & GC with `emergency_notification` and wait `emergency_postfact_timeout` for acknowledgement.
  * If RC/GC deny retrospectively, RC/GC may request rollback. Rollback support must exist.

### RC/GC unreachable

* Policies must state default behavior:

  * default-deny (safe) OR default-allow for certain low-risk categories (configurable)
* If default-deny, LC will queue and try again.

---

## 10. Decision Table (Quick Reference)

|  Category |         Approver         |      Execute Permitted?      |             Escalation            |
| --------: | :----------------------: | :--------------------------: | :-------------------------------: |
|       LOW |      Local / RC auto     |         Yes (LC can)         |                 No                |
|    MEDIUM |         Regional         |    Only after RC approves    |  RC→GC if multiple regions/impact |
|      HIGH |     Global + Regional    | Only after GC & RC approvals |                N/A                |
| EMERGENCY | Local (post-facto audit) |        Yes (immediate)       | RC+GC notified; rollback possible |

---

## 11. Example Scenarios

### Example 1 — Low change (adjust logging)

* LC creates request with `category=LOW`.
* LC validates local NIB (device exists). RC policy allows local execution.
* LC executes immediately (or RC auto-approves). Logs written to NIB & AuditStore.

### Example 2 — Medium change (change ACL on a regional edge device)

* LC creates `category=MEDIUM`, `affected_devices` contains regional-edge device.
* RC examines regional NIB (topology, maintenance windows) → approves → instructs LC to execute. LC executes and reports.

### Example 3 — High change (core routing policy)

* LC creates `category=HIGH`, RC forwards to GC. GC checks global policy and network-wide impact, approves. RC then instructs LC to execute. All steps logged.

### Example 4 — Emergency (DDoS mitigation)

* LC detects surge and needs to apply null-route. `category=EMERGENCY`.
* LC executes immediately (policy allows). LC creates emergency audit entry, notifies RC & GC. RC/GC acknowledge and confirm. If RC later denies, rollback protocol runs.

---

## 12. Security & Keys

* All controllers hold private keys for signing messages. Public keys are registered in controller registry (NIB) and validated during verification flow.
* Use short-lived execution tokens signed by RC (or GC for high changes) and validated by LC before executing.
* Use mutual TLS + token-based auth for message channels.

---

## 13. Extensibility (Advanced Features for Later)

* **Risk scoring engine** (NIB-fed) to produce `sensitivity_score` based on device criticality, historical failures, vendor CVEs.
* **Multi-signature approvals** for highly sensitive changes.
* **Auto-rollbacks with health checks** (if new config degrades key metrics).
* **GUI-driven approvals** (admin web console).
* **Approval delegation & SLA windows** (who can auto-approve during nights/weekends).

---

## 14. Implementation Notes (for contributors)

* Implement message handlers in pdsno.communication (mqtt_client, rest_api).
* Implement request validation in controllers/base_controller → new approval helper.
* Add new NIB table `controller_sync` to manage locks and tokens.
* Add audit helper in pdsno.logging that signs entries.
* Keep all decisions idempotent (use request_id to dedupe).
* Start with core rules (LOW/MEDIUM/HIGH/EMERGENCY) and feature-flag advanced behavior.
