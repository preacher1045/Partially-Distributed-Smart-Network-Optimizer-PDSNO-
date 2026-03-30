---
title: Data Persistence Architecture & Staged Migration Strategy
status: Active
author: Alexander Adjei
last_updated: 2026-03-30
component: Data Layer
depends_on: 02_nib_spec.md, /pdsno/datastore/schema.sql
---

# Data Persistence Architecture & Staged Migration Strategy

## Executive Summary

PDSNO uses a **staged approach to data persistence**:

- **Phase 1–5 (Current PoC)**: Single SQLite database with logically separated durable/transient schema
- **Phase 6+ (Production)**: Dual-backend architecture (PostgreSQL for durable data, Redis for transient data)

This document explains:
1. **Why** the current unified approach is correct for the PoC
2. **How** the schema is prepared for future splitting
3. **When** to migrate (growth signals)
4. **How** to execute the migration with zero controller logic changes

---

## Current Architecture: Unified SQLite (Phases 1–5)

### Schema Organization

All PDSNO data lives in `/pdsno/datastore/schema.sql` with tables classified as **Durable** or **Transient** per the [NIB Specification](02_nib_spec.md#two-tier-data-classification):

| Table | Classification | Purpose |
|-------|----------------|---------|
| `schema_version` | **Durable** | Admin table; tracks schema migrations |
| `devices` | **Durable** | Discovered network devices (slow-change, high trust) |
| `controllers` | **Durable** | Controller identity & validation state |
| `config_records` | **Durable** | Submitted configurations (immutable after approval) |
| `config_approvals` | **Durable** | Approval decisions (audit trail) |
| `execution_tokens` | **Durable** | Runtime auth tokens (must survive restarts) |
| `backups` | **Durable** | Snapshots of network state (audit/recovery) |
| `events` | **Durable** | Immutable event log (compliance, accountability) |
| `discovery_reports` | **Transient** | Scan results from device discovery (cacheable) |
| `locks` | **Transient** | Distributed locks for cross-controller coordination (ephemeral) |

### Why This Works (Now)

1. **Single point of failure is acceptable** — We're validating that the control logic works. SQLite is sufficient for PoC.
2. **Performance is adequate** — Current scale (< 1000 devices, < 10 concurrent operations) has SQLite throughput headroom.
3. **No distributed coordination complexity** — Unified backend means strong consistency is free; no quorum logic needed.
4. **Rapid iteration** — Don't pay the cost of multi-backend coordination code before the logic is proven.

### Access Pattern: Through `NIBStore`

Critical design: **No controller ever accesses SQLite directly.** All R/W operations flow through the `NIBStore` abstraction layer:

```
Discovery Engine -> NIBStore.write_device() -> SQLite
     ↓
Config Manager -> NIBStore.read_config() -> SQLite
     ↓
Approval Engine -> NIBStore.write_approval() -> SQLite
```

This indirection is deliberate and enables the migration strategy described below.

---

## Growth Signals: When to Migrate

As the project grows, **specific symptoms** will indicate that the unified approach is no longer sufficient:

### Signal 1: Distributed Deployment Requirements

**Symptom**: Multiple independent controller deployments (e.g., different geographic regions or cloud providers) need to sync.

**Current constraint**: SQLite's write model assumes a single writer (or heavy coordination).

**When to migrate**: If you need genuine multi-writer scenarios without coordinating all writes through a single node.

**Solution**: PostgreSQL (Durable) with Raft consensus; Redis cluster (Transient).

---

### Signal 2: Transient Data Throughput Bottleneck

**Symptom**: Lock operations, discovery scan submissions, or event logging are CPU/I/O bound.

**Current constraint**: SQLite serializes all writes; transient data gets queued behind durable data despite lower consistency requirements.

**When to migrate**: If profile data shows > 50% of I/O is transient writes being blocked by durable read-locks.

**Solution**: Redis (Transient) has < 1ms write latency. Durable writes stay PostgreSQL (Raft provides consistency).

---

### Signal 3: Durability Audit Requirements

**Symptom**: Compliance audits require immutable, replicated storage with strong consistency guarantees.

**Current constraint**: SQLite is process-local; no cross-node replication or Byzantine-fault tolerance.

**When to migrate**: If regulatory burden requires proof that approval records survive data center failure.

**Solution**: PostgreSQL with WAL shipping + standby replicas, or etcd for stronger Byzantine properties.

---

### Signal 4: Data Type Mismatch

**Symptom**: A new data type has fundamentally different access patterns than SQLite supports well.

**Example**: Real-time telemetry time-series data, full-text search over audit logs, or graph queries over device relationships.

**When to migrate**: If a new requirement doesn't fit SQLite's relational model.

**Solution**: Specialized store (e.g., TimescaleDB, Elasticsearch, Neo4j) routed via expanded `NIBStore`.

---

## Phase 6+ Target Architecture

### Dual-Backend with Swappable `NIBStore`

```
┌─────────────────────────────────────────────────────────────┐
│ Controller Logic (unchanged)                                 │
│ - approval_engine.py                                         │
│ - config_manager.py                                          │
│ - discovery_engine.py                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────── NIBStore API ──────────────────────┐
│ .read_client(id)       .write_approval()                   │
│ .write_device()        .list_events()                      │
│ .read_config()         .acquire_lock()                     │
└─────────────────┬──────────────────────────────┬───────────┘
                  │                              │
           ┌──────v─────┐              ┌────────v────────┐
           │  PostgreSQL │              │     Redis       │
           │  (Durable)  │              │  (Transient)    │
           │             │              │                 │
           │ - devices   │              │ - locks         │
           │ - config    │              │ - disc_reports  │
           │ - approvals │              │                 │
           │ - events    │              │                 │
           │ - backups   │              │                 │
           │ - tokens    │              │                 │
           └─────────────┘              └─────────────────┘
```

### Key Guarantees

1. **Controller code is untouched** — `NIBStore` interface remains identical. Only the implementation swaps (PostgreSQL, Redis).
2. **Incremental migration** — Can migrate durable tables one at a time, keeping tests passing.
3. **No consistency regressions** — Phase 6 architecture guarantees ≥ Phase 5 consistency (actually improves it for durable tables).

---

## Migration Path (When Triggered)

Assuming a growth signal shows the migration is needed:

### Step 1: Stabilize `NIBStore` Interface (Cost: 2–4 weeks if done alongside feature work)

- Audit all direct SQLite access; route through `NIBStore`
- Add routing metadata to each table (`DURABLE` or `TRANSIENT` tag in schema comments)
- Add unit tests that mock `NIBStore` backend (so tests pass against any backend)

*Note: This is already partially done; schema.sql has classification comments.*

---

### Step 2: Implement PostgreSQL Backend (Cost: 3–6 weeks, parallelizable)

- Create `pdsno/datastore/backends/postgresql.py` implementing `NIBStore` interface
- Write migrations to map SQLite schema → PostgreSQL
- Add integration tests (spin up Postgres in CI, run full controller validation suite)
- Shadow-write to PostgreSQL while reading from SQLite (verify consistency)

---

### Step 3: Implement Redis Backend (Cost: 1–2 weeks, parallelizable)

- Create `pdsno/datastore/backends/redis.py` for transient tables
- Write expiration policies (TTL locks, temporary scan results)
- Add integration tests (spin up Redis in CI, validate lock semantics)
- Canary: test transient data under high-frequency operations

---

### Step 4: Cutover (Cost: 1 day, low-risk)

- Update deployment configs to select backend
- Point production to PostgreSQL (durable) + Redis (transient)
- SQLite becomes development/PoC-only backend

---

## Implementation Today (Phase 5)

To **prepare** for future migration without adding complexity now:

1. ✅ **Schema separation** — Maintain `/pdsno/datastore/schema_durable.sql` and `schema_transient.sql` (or logical groupings in single file with clear demarcation)

2. ✅ **`NIBStore` abstraction** — Ensure all controller access to data goes through `pdsno/datastore/nib_store.py`, never direct SQLite calls

3. ✅ **Classification comments** — Each table in schema.sql has a comment identifying it as `[DURABLE]` or `[TRANSIENT]` per NIB spec

4. ⚠️ **Backend abstraction** — Create `pdsno/datastore/backends/sqlite.py` so SQLite becomes just one pluggable backend option (defer until growth signal)

5. ⚠️ **Test harness** — Unit tests should mock `NIBStore`, not SQLite directly (defer unless new code requires it)

---

## For Contributors: Decision Context

This staged approach is **not random** — it reflects a deliberate tradeoff:

| Phase | Constraint | Benefit |
|-------|-----------|---------|
| **Now (PoC)** | Single backend, simple schema | Faster validation, fewer operational dependencies to debug |
| **Phase 6** | Dual backend, table routing | Horizontal scaling, failure isolation, audit durability |

**If you observe a growth signal** (distribution, throughput, audit), **document it** and file an issue proposing migration. Decisions on backend changes should be data-driven, not speculative.

### Red Flags That Suggest Migration Is Overdue

- Lock contention errors in logs (transient data congestion)
- SQLite disk quota exceeded warnings (schema growing faster than expected)
- Controllers unable to sync approval state (distributed write concurrency)
- Audit log size making schema initialization slow (event log unbounded growth)

---

## Related Documentation

- **[02_nib_spec.md](02_nib_spec.md)** — Durable/Transient classification rationale and access patterns
- **[/pdsno/datastore/schema.sql](/pdsno/datastore/schema.sql)** — Table definitions with `[DURABLE]` / `[TRANSIENT]` comments
- **Architecture Decision Records (ADRs)** — Future — will document why specific backend choices were made
- **[D10 Issue: Adaptive Consistency Promotion](../issues.md#d10)** — Parent tracking issue for the PoC→Production roadmap
