---
title: System Architecture
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: PROJECT_OVERVIEW.md, nib/nib_spec.md, communication_model.md
---

# PDSNO — System Architecture

## Architectural Principles

PDSNO is built on four non-negotiable principles that every design decision must respect:

**1. State lives in the NIB.** No controller trusts its own memory for network facts. Every piece of state that matters — device records, config approvals, policies, audit entries — is written to the NIB before any action is taken based on it.

**2. Hierarchy for governance, not performance.** The three-tier model (Global → Regional → Local) exists because governance and auditability require a clear chain of authority. A flat architecture would be faster; PDSNO accepts the latency cost in exchange for a well-defined root of trust and escalation path.

**3. Every action is auditable.** No change is executed without a signed audit trail. No approval is granted without a record. The Event Log is append-only and tamper-evident.

**4. Interfaces are the contracts.** Controllers communicate only through defined message types on defined interfaces (NBI, SBI, East/West). No controller reaches into another's internals.

---

## System Layers

```
┌─────────────────────────────────────────────────────┐
│              APPLICATION LAYER                       │
│  External tools, dashboards, vendor adapters (NBI)  │
└───────────────────────┬─────────────────────────────┘
                        │ NBI (REST/HTTP)
┌───────────────────────▼─────────────────────────────┐
│              CONTROL LAYER                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │           Global Controller (GC)             │   │
│  │  - Root of trust / identity anchor           │   │
│  │  - Global policy holder                      │   │
│  │  - HIGH config approval authority            │   │
│  │  - Cross-region anomaly detection            │   │
│  └────────────────────┬─────────────────────────┘   │
│                East/West│                            │
│  ┌─────────────────────▼───────────────────────┐    │
│  │         Regional Controller (RC)            │    │
│  │  - Zone governance (1 per geographic zone)  │    │
│  │  - MEDIUM/LOW config approval               │    │
│  │  - LC validation authority (delegated)      │    │
│  │  - Discovery report aggregation             │    │
│  └────────────────────┬────────────────────────┘    │
│                East/West│                            │
│  ┌─────────────────────▼───────────────────────┐    │
│  │          Local Controller (LC)              │    │
│  │  - Direct device interface (SBI)            │    │
│  │  - Device discovery execution               │    │
│  │  - Config execution (after approval)        │    │
│  │  - First responder to device events         │    │
│  └────────────────────┬────────────────────────┘    │
└───────────────────────┼─────────────────────────────┘
                        │ SBI (NETCONF, SNMP, ARP, ICMP)
┌───────────────────────▼─────────────────────────────┐
│              DATA LAYER                              │
│  Network Devices (switches, routers, endpoints)     │
└─────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              STATE LAYER (NIB)                       │
│  Device Table │ Config Table │ Policy Table          │
│  Metadata Store │ Event Log │ Controller Sync Table  │
└─────────────────────────────────────────────────────┘
```

---

## Controller Responsibilities Matrix

| Responsibility | LC | RC | GC |
|---------------|----|----|-----|
| Device discovery (execution) | ✓ | | |
| Discovery report aggregation | | ✓ | |
| Global device inventory | | | ✓ |
| LOW config approval | ✓ (direct) | ✓ (auto) | |
| MEDIUM config approval | | ✓ | |
| HIGH config approval | | | ✓ |
| Emergency execution | ✓ | | |
| Controller validation (LC) | | ✓ (delegated) | |
| Controller validation (RC) | | | ✓ |
| Global policy holder | | | ✓ |
| Regional policy enforcement | | ✓ | |
| Anomaly detection (local) | ✓ | | |
| Anomaly detection (regional) | | ✓ | |
| Anomaly detection (global) | | | ✓ |
| Audit log writes | ✓ | ✓ | ✓ |

---

## Internal Controller Structure

Every controller — regardless of tier — has the same four internal components:

```
┌──────────────────────────────────┐
│         DECISION ENGINE          │  Runs approval logic, policy checks,
│  (approval_logic, policy_engine) │  escalation decisions
├──────────────────────────────────┤
│        COMMUNICATION LAYER       │  REST server (NBI/East-West inbound)
│  (rest_server, mqtt_client)      │  MQTT client (pub/sub state updates)
├──────────────────────────────────┤
│          DATA LAYER              │  NIBStore interface — all reads/writes
│  (nib_store, models)             │  go through here
├──────────────────────────────────┤
│        ALGORITHM MODULES         │  Discovery, validation, optimization
│  (discovery, validation, etc.)   │  All follow initialize/execute/finalize
└──────────────────────────────────┘
```

---

## Key Architectural Decisions

| Decision | Choice | Rationale |
|---------|--------|-----------|
| Controller topology | Hierarchical (3-tier) | Governance requires clear chain of authority |
| State store | NIB (centralized per tier, scoped views) | Eliminates consistency bugs from local state |
| Consistency model | Optimistic locking (PoC) → Adaptive (Phase 6+) | Balance correctness vs complexity |
| Inter-controller protocol | REST (request/response) + MQTT (events) | Right tool for each message type |
| Inter-controller state sync | Delta-only (changed entities only) | Scales; full dumps do not |
| Interface naming | ONF TR-521 standard (NBI/SBI/East-West) | Industry-standard legibility |
| PoC storage | SQLite with WAL mode | Minimal dependencies; swappable via NIBStore |

See `ROADMAP_AND_TODO.md` for the full decisions log with rationale for each.
