---
title: NIB Consistency Deep Dive
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: nib/nib_spec.md
---

# NIB Consistency — Deep Dive

## The Core Problem

PDSNO runs multiple controllers that all read and write shared state. Without
coordination, two controllers can read the same record, make independent decisions
based on it, and write conflicting updates — neither knowing the other existed.

The classic example: two RCs both read that device `nib-dev-001` has no active
config lock. Both proceed to approve a config change for it. The device receives
two conflicting configs.

---

## PoC Approach: Per-Subject Optimistic Locking

Every mutable NIB table has a `version` integer column. The write protocol is:

```
1. READ record + current version number
2. COMPUTE change locally
3. WRITE with condition: only commit if version == value_read_in_step_1
4. CHECK result:
   - version matched → commit succeeded, increment version
   - version mismatch → CONFLICT — another writer got there first
5. ON CONFLICT: re-read, re-compute, retry (up to max_retries=3)
```

### Why Optimistic, Not Pessimistic?

Pessimistic locking (lock before reading, release after writing) would serialize
all writes through a lock manager. At low contention — which is the normal case
for PDSNO — this adds latency for no benefit. Optimistic locking adds zero overhead
on the fast path (no conflict) and only pays a cost when conflicts actually occur.

### What Optimistic Locking Cannot Prevent

It prevents the **lost update** problem (two writers clobbering each other).
It does not prevent **read skew** (reading two related records at different points
in time, seeing an inconsistent snapshot). For PDSNO's PoC use cases, this is
acceptable — the NIB is not a financial ledger.

---

## Conflict Resolution Rules

| Data Type | Conflict Rule | Rationale |
|-----------|--------------|-----------|
| Config approval | First writer wins; second gets CONFLICT and must wait for lock expiry | Preventing duplicate approvals is worth the retry cost |
| Device discovery | Most recent `last_seen` timestamp wins | Fresher data is more accurate |
| Policy writes | Serialized through GC — RC never writes policy directly | No conflicts possible by design |
| Event Log | Append-only with UUID keys — no conflicts possible | |
| Controller sync locks | CAS (compare-and-swap) on lock acquisition | Atomic at DB level |

---

## Phase 6+ Target: Adaptive Consistency

Research (Alsheikh et al., 2024) recommends neither static eventual nor static
strong consistency for distributed SDN — both are suboptimal across all operation
types. The adaptive model switches based on data type:

| Operation | Consistency Level | Storage Tier |
|-----------|-----------------|-------------|
| Device discovery | Eventual | Transient (Redis) |
| Link health / telemetry | Eventual | Transient |
| Config proposals + approvals | Strong | Durable (PostgreSQL+Raft) |
| Controller identity | Strong | Durable |
| Policy distribution | Strong | Durable |
| Audit log | Strong (append-only) | Durable |
| Lock acquisition | Strong | Durable |

The `data_tier` field on every `NetworkEntity` drives routing. No controller code
changes — only `NIBStore` is re-implemented.

---

## Frequently Asked Questions

**Q: What happens if the SQLite DB is locked by another process during a write?**
SQLite WAL mode allows concurrent reads while a write is in progress. Write
contention (two writers simultaneously) is serialized by SQLite's locking. The
second writer waits up to `busy_timeout` (default: 5s) before failing. The NIBStore
treats this as a CONFLICT and retries.

**Q: Is eventual consistency ever safe for config approvals?**
No. Even a brief window where one controller approves a change that another has
already approved — or that violates a policy update that hasn't arrived yet — can
cause real damage to the network. Config approvals are always durable/strong.

**Q: Why not just use Raft for everything now?**
Raft requires at least 3 nodes to tolerate a single failure, adds deployment
complexity, and requires a leader election protocol. For a PoC validating business
logic, this is premature. The NIBStore interface means Raft can be added later
without touching controller code.
