---
title: Network Information Base (NIB) Specification
status: Active
author: Alexander Adjei
last_updated: 2026-02-14
component: Data Layer
depends_on: PROJECT_OVERVIEW.md, docs/architecture/controller_hierarchy.md
research_basis: >
  Koponen et al. (Onix, OSDI 2010) — foundational NIB design and distribution model.
  Alsheikh et al. (Distributed SDN Management, ARO 2024) — adaptive consistency model.
  ONF TR-521 SDN Architecture Issue 1.1 — interface naming and architectural alignment.
---

# Network Information Base (NIB) — Specification

## Overview

The **Network Information Base (NIB)** is PDSNO's authoritative source of truth for all network and system state. Rather than each controller maintaining independent local state, every controller reads from and writes to the NIB through a defined interface.

This document defines the NIB's schema, consistency model, access interface, and write conflict rules. It is the foundational data layer specification that the controller validation, device discovery, and configuration approval systems all depend on.

### Research Grounding

The NIB concept in PDSNO is independently aligned with **Onix** — the distributed SDN control platform developed at Nicira (Koponen et al., OSDI 2010), which first formally defined the NIB as a production architecture pattern. Onix describes the NIB as "the heart of the control model" — a graph of all network entities that control applications read from and write to, rather than communicating with each other directly.

PDSNO's NIB follows the same fundamental design: data-centric, controller-agnostic, and accessible only through a defined interface. The key differences are that PDSNO's NIB is scoped to orchestration governance (approval tracking, policy distribution, audit) rather than OpenFlow forwarding state management, and PDSNO adds the two-tier data classification described below, which Onix also uses in production.

---

## Why a Centralized State Store?

The core challenge in a distributed orchestration system is **state consistency**. If controllers maintain their own independent state, they will inevitably diverge. A device that one controller believes is online may be considered offline by another. A configuration that one controller believes is approved may be unknown to the one responsible for executing it.

The NIB solves this by making one store authoritative. Controllers are stateless with respect to network knowledge — they always query the NIB rather than trusting their local memory. This is a deliberate tradeoff: it creates a dependency on NIB availability, but it eliminates an entire class of consistency bugs.

The NIB is not a single centralized server. Each controller tier maintains a **scoped NIB view**:

- **Local Controller** — NIB view covering its directly managed devices
- **Regional Controller** — NIB view covering its zone (aggregated from Local Controller submissions)
- **Global Controller** — NIB view covering the full network (aggregated from Regional Controller summaries)

Writes flow upward through this hierarchy. Reads are served from the local view, with a fallback to request data from a higher tier.

---

## NIB Modules

| Module | Description | Primary Writer | Primary Readers |
|--------|-------------|----------------|-----------------|
| **Device Table** | Records for every discovered network device | Local Controller (via discovery) | All tiers |
| **Metadata Store** | Extended device attributes (vendor, firmware, capabilities) | Local Controller | RC, GC for policy decisions |
| **Config Table** | Configuration version history and approval status per device | LC (proposals), RC/GC (approvals) | All tiers |
| **Policy Table** | Active policies distributed from GC → RC → LC | Global Controller | RC, LC for enforcement |
| **Event Log** | Immutable audit trail of all operations | All controllers | Audit/compliance systems |
| **Controller Sync Table** | Locks, tokens, and synchronization state between controllers | RC, GC | All tiers during approval flow |

---

## Two-Tier Data Classification

*Adopted from Onix (Koponen et al., 2010) — production-validated design.*

Not all NIB data has the same consistency and durability requirements. Treating all data identically — as a single SQLite store does — is correct for the PoC but creates unnecessary constraints at scale. PDSNO distinguishes two data tiers based on how frequently data changes and how critical consistency is:

| Tier | Characteristics | Examples | Consistency Priority | Durability Priority |
|------|----------------|---------|---------------------|-------------------|
| **Transient Data** | Changes frequently, tolerable to be briefly stale, short-lived value | Link utilization, discovery scan results, device reachability counters, lock state | Availability over consistency | Low — can be reconstructed |
| **Durable Data** | Changes slowly, must be consistent, long-lived value | Validated controller identities, approved config records, active policies, audit log entries | Consistency over availability | High — must survive failures |

### What This Means in Practice

**For the PoC (Phases 1–5):** All data lives in SQLite with optimistic locking. The distinction is documented but not yet enforced at the storage layer. This is intentional — the goal of the PoC is to validate the logic, not the storage architecture.

**For Phase 6+:** The NIB interface (`NIBStore`) is designed to be swappable. The target architecture separates the two tiers:
- **Transient store** — a high-availability, lower-consistency store (e.g., Redis) for data that changes at per-second rates. Prioritizes speed and availability.
- **Durable store** — a strongly consistent, replicated store (e.g., PostgreSQL with Raft, or etcd) for data that must survive controller failures and network partitions. Prioritizes correctness.

Because no controller ever accesses the storage layer directly (all access goes through `NIBStore`), this migration requires only reimplementing `NIBStore` — no controller logic changes.

### Classifying Your Data

When adding a new data type to the NIB, ask these two questions:

1. *Can the system function correctly if this data is briefly stale (seconds to minutes)?* If yes → Transient.
2. *Must this data survive a controller restart or network partition intact?* If yes → Durable.

When in doubt, classify as Durable. The cost of incorrect Transient classification (stale reads causing wrong decisions) is higher than the cost of over-classifying as Durable (slightly slower writes).

---

### Device Table

Stores one record per discovered network device. Updated by Local Controllers during discovery cycles.

```
device_id          STRING    PRIMARY KEY   -- NIB-assigned unique ID (e.g., nib-dev-001)
temp_scan_id       STRING                  -- Temporary ID from discovery scan (may change)
ip_address         STRING    NOT NULL
mac_address        STRING    UNIQUE        -- Hardware address, used for deduplication
hostname           STRING
vendor             STRING
device_type        STRING                  -- router | switch | server | endpoint | unknown
firmware_version   STRING
region             STRING    NOT NULL      -- Which regional zone this device belongs to
local_controller   STRING    NOT NULL      -- ID of the LC that discovered this device
status             STRING    NOT NULL      -- active | inactive | unreachable | quarantined
first_seen         DATETIME  NOT NULL
last_seen          DATETIME  NOT NULL
last_updated       DATETIME  NOT NULL
discovery_method   STRING                  -- arp | snmp | icmp | fingerprint
```

### Metadata Store

Extended attributes that don't belong in the core device record. One-to-one with Device Table.

```
device_id          STRING    FOREIGN KEY → Device Table
snmp_info          JSON      -- OID data, system description, interface list
protocol_caps      JSON      -- Supported protocols (OSPF, BGP, etc.)
interface_list     JSON      -- Physical and logical interfaces
uptime_seconds     INTEGER
custom_tags        JSON      -- Operator-assigned labels
last_updated       DATETIME
```

### Config Table

Tracks every configuration proposal and its approval status.

```
config_id          STRING    PRIMARY KEY   -- UUID
device_id          STRING    FOREIGN KEY → Device Table
proposal_id        STRING    NOT NULL
config_hash        STRING    NOT NULL      -- Hash of normalized config payload
category           STRING    NOT NULL      -- LOW | MEDIUM | HIGH | EMERGENCY
status             STRING    NOT NULL      -- PENDING | APPROVED | DENIED | EXECUTED | ROLLED_BACK | FAILED
proposed_by        STRING    NOT NULL      -- Controller ID of LC that proposed this
approved_by        STRING                  -- Controller ID of RC or GC that approved
execution_token    STRING                  -- Short-lived token issued on approval
proposed_at        DATETIME  NOT NULL
approved_at        DATETIME
executed_at        DATETIME
expiry             DATETIME                -- After this time, token is invalid
policy_version     STRING    NOT NULL      -- Policy version in effect at proposal time
rollback_payload   JSON                    -- Instructions to undo this config if needed
```

### Policy Table

Holds the active policy set distributed from the Global Controller downward.

```
policy_id          STRING    PRIMARY KEY
policy_version     STRING    NOT NULL      -- Semantic version string (e.g., "region1-v3.2")
scope              STRING    NOT NULL      -- global | regional | local
target_region      STRING                  -- NULL for global scope
content            JSON      NOT NULL      -- Policy rules as structured data
distributed_by     STRING    NOT NULL      -- Controller that pushed this policy
distributed_at     DATETIME  NOT NULL
valid_from         DATETIME  NOT NULL
valid_until        DATETIME                -- NULL = indefinite
is_active          BOOLEAN   NOT NULL DEFAULT TRUE
```

### Event Log

Append-only. No record is ever deleted or modified. The audit trail.

```
event_id           STRING    PRIMARY KEY   -- UUID
event_type         STRING    NOT NULL      -- DISCOVERY | VALIDATION | CONFIG_PROPOSAL | APPROVAL | EXECUTION | ROLLBACK | POLICY_UPDATE | ERROR
actor              STRING    NOT NULL      -- Controller ID that triggered the event
subject            STRING                  -- Device ID, controller ID, or proposal ID this event is about
action             STRING    NOT NULL      -- Human-readable description of what happened
decision           STRING                  -- APPROVED | DENIED | FLAGGED | N/A
timestamp          DATETIME  NOT NULL
signature          STRING    NOT NULL      -- HMAC or digital signature of event content (tamper-evidence)
payload_ref        STRING                  -- Reference to full payload stored in blob store (if large)
notes              STRING                  -- Optional operator or system notes
```

### Controller Sync Table

Manages locks, tokens, and synchronization state during multi-step operations like config approval.

```
lock_id            STRING    PRIMARY KEY
lock_type          STRING    NOT NULL      -- DEVICE_LOCK | CONFIG_LOCK | VALIDATION_LOCK
subject_id         STRING    NOT NULL      -- Device ID, config ID, or controller ID being locked
held_by            STRING    NOT NULL      -- Controller ID holding this lock
acquired_at        DATETIME  NOT NULL
expires_at         DATETIME  NOT NULL      -- Locks are always time-bounded
status             STRING    NOT NULL      -- ACTIVE | EXPIRED | RELEASED
associated_request STRING                  -- Proposal ID or validation request ID this lock is for
```

---

## Consistency Model

### Current Approach: Per-Subject Optimistic Locking (PoC)

For Phases 1–5, PDSNO uses **per-subject optimistic locking**. Each write includes a `version` field. Before committing, the NIB checks that the version the writer read matches the current version. If another writer has modified the record since the read, the write is rejected with a `CONFLICT` error and the writer must re-read and retry.

This approach was chosen because it catches the most dangerous conflicts (two approvals for the same device) while being implementable with SQLite and without requiring distributed coordination infrastructure.

**Evaluation of alternatives rejected for the PoC:**

Option 1 — Eventual Consistency — was rejected. While simpler to implement, it creates windows where two controllers make conflicting decisions based on stale reads. This is unacceptable for config approval and device quarantine operations, where a wrong decision can damage the network.

Option 2 — Strong Consistency (Serializable) — was rejected for the PoC phase. It requires distributed coordination infrastructure (Raft consensus or similar) that adds significant complexity before the core logic is validated.

### Target Approach: Adaptive Consistency (Phase 6+)

*Based on Alsheikh et al. (Distributed SDN Management, ARO 2024) — recommended for large-scale distributed SDN architectures.*

Research into distributed SDN architectures identifies a critical limitation of both static eventual consistency and static strong consistency: neither is optimal across all operation types. The recommended solution for production distributed SDN systems is an **adaptive consistency model** — the system dynamically adjusts its consistency guarantees based on the nature of the operation and the current network conditions.

The adaptive model PDSNO will target in Phase 6 works as follows:

| Operation Type | Consistency Level | Rationale |
|---------------|------------------|-----------|
| Device discovery updates | Eventual | Brief staleness is acceptable; speed matters for large subnet scans |
| Link health / telemetry | Eventual | High-frequency updates; stale by definition within milliseconds |
| Config proposals | Strong | A proposal must be visible to all approvers immediately |
| Controller validation | Strong | An identity must be consistent across all tiers before the controller acts |
| Policy distribution | Strong | All controllers must see the same policy version simultaneously |
| Audit log writes | Strong (append-only) | No staleness permitted in the compliance record |
| Lock acquisition | Strong | Race conditions here are dangerous by definition |

The transition between consistency levels is handled at the `NIBStore` layer — controllers do not need to specify which consistency level they want. The data type determines the behavior automatically. This keeps the controller code simple while making the storage layer intelligent.

**Implementation path:** When the NIB is migrated to a two-tier storage backend (Phase 6), eventual consistency operations target the Transient store and strong consistency operations target the Durable store. The `NIBStore` interface routes transparently.

### Conflict Resolution Rules

When a write conflict is detected under optimistic locking, the following rules apply:

1. **Config approval conflicts** — The second writer receives a `CONFLICT` response. The Controller Sync Table lock held by the first writer takes precedence. The second writer must wait for the lock to expire or be released, then retry.

2. **Discovery update conflicts** — If two Local Controllers report the same device (same MAC address) with different attributes, the record with the more recent `last_seen` timestamp wins. Both submissions are recorded in the Event Log.

3. **Policy update conflicts** — Policy writes are serialized through the Global Controller. Regional Controllers receive policies via the NBI distribution mechanism and do not write to the Policy Table directly. Conflicts cannot arise by design.

4. **Event Log conflicts** — Not possible. The Event Log is append-only. Each event gets a unique UUID.

---

## Entity Model

*Adopted from Onix (Koponen et al., 2010) — applied to PDSNO's Python implementation.*

Every object stored in the NIB descends from a common `NetworkEntity` base class. This provides consistent identity, versioning, and key-value access across all entity types without duplicating those fields in every schema.

```python
# pdsno/data/models.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

@dataclass
class NetworkEntity:
    """
    Base class for all NIB entities.
    Every entity has a UUID, a version counter for optimistic locking,
    and a timestamp for ordering.
    """
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_tier: str = "durable"  # "transient" | "durable" — determines consistency treatment

@dataclass
class Device(NetworkEntity):
    """Represents a discovered network device."""
    data_tier: str = "transient"  # Discovery data is transient by default
    mac_address: str = ""
    ip_address: str = ""
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    device_type: str = "unknown"
    region: str = ""
    local_controller: str = ""
    status: str = "active"
    # ... remaining fields per schema above

@dataclass
class ConfigRecord(NetworkEntity):
    """Represents a configuration proposal and its approval state."""
    data_tier: str = "durable"  # Config approvals are durable by definition
    device_id: str = ""
    config_hash: str = ""
    category: str = ""
    status: str = "PENDING"
    # ... remaining fields per schema above
```

The `data_tier` field on each entity is what the adaptive consistency model will use in Phase 6 to route writes to the appropriate storage backend. Setting it correctly now costs nothing but makes the Phase 6 migration straightforward.

---

## Access Interface

Controllers interact with the NIB exclusively through the `NIBStore` class. No controller accesses the underlying storage layer directly. This interface contract is what makes the storage backend swappable without changing any controller code.

```python
class NIBStore:
    """
    Thread-safe interface to the Network Information Base.

    All methods that modify state return a NIBResult indicating success,
    conflict, or failure. Callers must check the result before proceeding.

    Interface naming follows ONF SDN Architecture (TR-521):
    - Data arriving from the network (southbound) is written via upsert/update methods
    - Data requested by controllers (northbound) is read via get methods
    - Controller-to-controller synchronization uses the lock/sync methods
    """

    # Device Table
    def get_device(self, device_id: str) -> Device | None: ...
    def get_device_by_mac(self, mac: str) -> Device | None: ...
    def upsert_device(self, device: Device) -> NIBResult: ...
    def update_device_status(self, device_id: str, status: str, version: int) -> NIBResult: ...
    def quarantine_device(self, device_id: str, reason: str) -> NIBResult: ...

    # Config Table
    def create_config_proposal(self, proposal: ConfigRecord) -> NIBResult: ...
    def update_config_status(self, config_id: str, status: str, approver: str, version: int) -> NIBResult: ...
    def get_active_config(self, device_id: str) -> ConfigRecord | None: ...

    # Policy Table
    def get_active_policy(self, scope: str, region: str = None) -> Policy | None: ...
    def distribute_policy(self, policy: Policy) -> NIBResult: ...

    # Event Log (SBI equivalent — all events from the network and controllers)
    def write_event(self, event: Event) -> NIBResult: ...  # Always succeeds or raises

    # Controller Sync — East/West interface state
    def acquire_lock(self, subject_id: str, lock_type: str, held_by: str, ttl_seconds: int) -> NIBResult: ...
    def release_lock(self, lock_id: str, held_by: str) -> NIBResult: ...
    def check_lock(self, subject_id: str, lock_type: str) -> Lock | None: ...
```

---

## Write Protocol

Every write to the NIB follows this sequence to ensure consistency:

```
1. READ current record + current version number
2. APPLY changes to local copy
3. WRITE with version check:
   - If stored version == version read in step 1: commit succeeds
   - If stored version != version read in step 1: return CONFLICT
4. CHECK result:
   - SUCCESS: proceed
   - CONFLICT: re-read, re-apply, retry (up to max_retries)
   - FAILURE: log error, escalate
```

---

## Retention and Cleanup

| Table | Retention Policy |
|-------|-----------------|
| Device Table | Devices unseen for `policy.device_retention_days` (default: 90) are marked `inactive`. After `policy.device_purge_days` (default: 365) they may be deleted if still inactive. |
| Config Table | Config records are retained for `policy.config_retention_days` (default: 180) after execution. |
| Policy Table | Superseded policies are retained for `policy.policy_retention_days` (default: 30) for audit purposes. |
| Event Log | Never deleted. Retention is indefinite. Old logs may be archived to cold storage after `policy.event_archive_days` (default: 365). |
| Controller Sync Table | Expired locks are cleaned up by a background job every `policy.lock_cleanup_interval` (default: 60 seconds). |

---

## Implementation Notes

### Phase 1–5 (PoC): SQLite Single-Tier

All data lives in a single SQLite database with:
- WAL (Write-Ahead Logging) mode for better concurrent read performance
- Optimistic locking via a `version` integer column on all mutable tables
- The `Event Log` table configured as append-only via a database trigger that rejects UPDATE and DELETE operations
- The `data_tier` field stored per entity for future routing, even though it is not yet used for storage decisions

### Phase 6+: Two-Tier Storage Target

The `NIBStore` interface will be re-implemented against a two-tier backend without changing any controller code:

| Tier | Storage Technology | Data Types | Rationale |
|------|--------------------|-----------|-----------|
| **Transient** | Redis (or similar high-availability KV store) | Device discovery, link health, telemetry | High write throughput, acceptable staleness, fast expiry |
| **Durable** | PostgreSQL + Raft replication (or etcd) | Config approvals, controller identities, policies, audit log | Strong consistency, survives failures, replicated |

This two-tier design mirrors Onix's production architecture — DHT for transient state, Paxos-backed storage for durable state — adapted to use more modern and accessible technologies (Redis, PostgreSQL) rather than Chord DHT and custom Paxos implementations.

### References

- Koponen, T. et al. "Onix: A Distributed Control Platform for Large-Scale Production Networks." OSDI 2010.
- Alsheikh, R.S. et al. "Distributed Software-Defined Networking Management: An Overview and Open Challenges." ARO, King Abdulaziz University, 2024.
- Open Networking Foundation. "SDN Architecture Issue 1.1." TR-521, 2016.
