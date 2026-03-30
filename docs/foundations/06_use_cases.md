---
title: Use Cases
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: architecture.md, config_approval_logic.md, device_discovery_sequence.md
---

# PDSNO — Use Cases

Each use case is traced step-by-step through the system, showing which controllers act,
which NIB tables are written, and which SON principle it demonstrates.

---

## UC-1: New Device Joins the Network

**Trigger:** A network switch is physically connected to a subnet managed by `local_cntl_zoneA_1`.
**SON Principle:** Self-Configuration

**Flow:**
1. LC's scheduled discovery cycle runs. ARP scan detects new MAC `aa:bb:cc:dd:ee:ff` at `10.0.1.45`.
2. ICMP confirms reachability. SNMP returns vendor=Cisco, model=C9300.
3. LC diffs against NIB — MAC not found → classified `NEW`.
4. LC allocates `nib-dev-047`. Writes Device Table + Metadata Store + `DEVICE_DISCOVERED` event.
5. LC sends discovery report to RC. RC validates, writes to regional NIB.
6. RC sends regional summary to GC. GC updates global inventory.
7. Device is now visible to all tiers. Any policy that applies to Cisco devices is automatically applicable to it on next policy evaluation.

**NIB tables touched:** Device Table (write), Metadata Store (write), Event Log (write ×3 — LC, RC, GC)

---

## UC-2: Low-Risk Config Change (Logging Update)

**Trigger:** Operator updates logging level on a leaf switch via external tool.
**SON Principle:** Self-Optimization

**Flow:**
1. External tool POSTs `CONFIG_PROPOSAL` to GC NBI. GC routes to `regional_cntl_zoneA_1`.
2. RC re-classifies as LOW. Policy allows LC direct execution.
3. RC issues execution token (TTL: 600s). Sends `EXECUTION_INSTRUCTION` to `local_cntl_zoneA_1`.
4. LC verifies token. Writes `EXECUTING`. Applies config to device via SBI.
5. LC writes `EXECUTED`. Releases device lock. Reports result to RC.
6. Full round-trip: ~5 seconds. Zero human intervention.

**NIB tables touched:** Config Table (PENDING → APPROVED → EXECUTING → EXECUTED), Controller Sync Table (lock acquired + released), Event Log (×4)

---

## UC-3: High-Risk Config Change (Core Routing Update)

**Trigger:** Network engineer submits a BGP policy change affecting a core router.
**SON Principle:** Self-Optimization with governance gate

**Flow:**
1. LC creates proposal with `suggested_sensitivity=HIGH`, `rollback_payload` included.
2. RC re-classifies independently → confirms HIGH. Acquires device lock. Escalates to GC.
3. GC checks immutable policy rules — no conflicts. Assesses cross-region impact (single region). Approves. Issues HIGH-category token (TTL: 300s, tighter window).
4. GC response travels back to RC. RC forwards `EXECUTION_INSTRUCTION` to LC.
5. LC verifies token bindings. Writes `EXECUTING`. Applies BGP change to router.
6. LC reports `EXECUTED`. RC releases lock. Full audit trail: proposal → escalation → GC approval → execution.

**Notable:** If GC does not respond within 300s, RC defaults to DENY and releases locks. No change happens by timeout.

---

## UC-4: Emergency Response (DDoS Mitigation)

**Trigger:** LC detects traffic surge exceeding `policy.ddos_threshold` on an edge device.
**SON Principle:** Self-Healing

**Flow:**
1. LC creates EMERGENCY proposal. Rate limiter allows (first emergency in 1 hour).
2. Null-route config type is on the permitted emergency list.
3. LC executes immediately — no token required. Writes `EXECUTING` → `EXECUTED`.
4. LC writes `EMERGENCY_EXECUTION` audit entry (full payload + rate limiter status).
5. LC notifies RC and GC asynchronously. Both acknowledge within 10-minute window.
6. Traffic anomaly resolved. If RC had denied retrospectively: rollback protocol runs.

**Notable:** Emergency mode is the most heavily audited path, not the least. The audit entry is mandatory and includes the full config payload — more detail than a normal execution.

---

## UC-5: Controller Comes Online (Regional Controller Registration)

**Trigger:** New RC `regional_cntl_zoneB_1` starts up for the first time.
**SON Principle:** Self-Configuration

**Flow:**
1. RC sends `VALIDATION_REQUEST` to `global_cntl_1` (bootstrap token + public key + metadata).
2. GC runs Step 1 (timestamp/blocklist) → Step 2 (bootstrap token consumed) → Step 3 (issues challenge).
3. RC signs nonce with private key. Returns `CHALLENGE_RESPONSE`.
4. GC verifies signature. Runs policy checks (zone valid, quota not exceeded).
5. GC atomically: writes controller record to NIB + writes `CONTROLLER_VALIDATED` audit event.
6. GC issues `VALIDATION_RESULT` with assigned_id=`regional_cntl_zoneB_1`, certificate, and delegation credential to validate LCs in zone-B.
7. RC now participates in the system. Its first action: request discovery from its LCs.

**NIB tables touched:** Controller Sync Table (new record), Event Log (`CONTROLLER_VALIDATED`)

---

## UC-6: Device Goes Unreachable (Link Failure)

**Trigger:** Switch `nib-dev-022` stops responding — link failure or device crash.
**SON Principle:** Self-Healing

**Flow:**
1. LC's next discovery cycle: ARP finds no response for device's IP. ICMP also fails.
2. `missed_cycles` counter for `nib-dev-022` incremented. Not yet marked inactive.
3. After `policy.missed_cycles_before_inactive` consecutive missed cycles (default: 3): LC writes `status=inactive` to Device Table. Writes `DEVICE_INACTIVE` event.
4. LC sends discovery report to RC flagging the device as inactive.
5. RC updates regional view. Any pending config proposals targeting `nib-dev-022` are blocked (device status check at proposal time).
6. When device comes back online: next discovery cycle detects it, writes `DEVICE_UPDATED` with `status=active`. Config proposals can resume.

**Notable:** Three missed cycles before inactive prevents a single slow scan from incorrectly removing a healthy device. Transient network noise does not pollute the NIB.

---

## UC-7: Policy Update Distributed Across Hierarchy

**Trigger:** Operator updates global discovery interval from 300s to 180s.
**SON Principle:** Self-Configuration

**Flow:**
1. Operator PUTs new policy to GC NBI. GC validates and writes new version to Policy Table.
2. GC publishes `POLICY_UPDATE` to MQTT topic `pdsno/global/policy/updates`.
3. All RCs receive update. Each validates signature + version. Writes to regional Policy Table.
4. Each RC publishes to `pdsno/{region}/policy/updates`.
5. All LCs receive update. Write to local Policy Table.
6. Next discovery cycle across all LCs uses the new 180s interval.
7. Any proposal submitted after this point must reference the new policy version — old version proposals rejected.

**Transport:** MQTT QoS 2 (exactly-once delivery). No polling. Update reaches all controllers within seconds.
