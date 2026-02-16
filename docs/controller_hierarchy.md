---
title: Controller Hierarchy
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: architecture.md, verification/controller_validation_sequence.md
---

# Controller Hierarchy

## The Three-Tier Model

```
global_cntl_1 (primary)    global_cntl_2 (standby)
       │                           │
       └─────────── East/West ─────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
  regional_cntl_1  regional_cntl_2  ...  (1 per zone, up to N)
          │
     ┌────┼────┐
     ▼    ▼    ▼
  lc_1  lc_2  lc_3  ...  (1–N per region, based on subnet density)
```

| Tier | Count | Scope | Validates |
|------|-------|-------|-----------|
| Global | 1 primary + 1 standby | Entire network | Regional Controllers |
| Regional | 1 per geographic zone | Single zone | Local Controllers (delegated authority) |
| Local | 1 per subnet block (guideline) | Direct device reach | Nothing |

---

## Why Hierarchy?

PDSNO accepts a performance penalty for governance correctness. A flat,
logically-centralized physically-distributed architecture (as used by ONOS)
delivers better raw performance because controllers communicate as peers without
routing through a root. PDSNO's hierarchy adds latency on HIGH config approvals
because they must travel LC → RC → GC → RC → LC.

This is intentional. PDSNO's target environments require:
- A single, unambiguous root of trust for controller identity
- A clear chain of custody for high-sensitivity changes
- A defined authority hierarchy for policy — no ambiguity about which controller's
  policy wins in a conflict

In environments where governance is less strict and performance is the priority,
a flatter architecture is the better choice. PDSNO is not that system.

---

## Controller Discovery and Peering

Controllers do not discover each other via network broadcast. Connections are
configured explicitly:
- LCs know their parent RC's address from `context_runtime.yaml`
- RCs know their parent GC's address from `context_runtime.yaml`
- A controller that cannot reach its parent on startup enters `PENDING_VALIDATION`
  state and retries with exponential backoff

---

## Offline Behaviour

### LC Goes Offline
- RC detects missing discovery reports after `policy.lc_report_timeout`
- RC writes `LC_DISCOVERY_OVERDUE` event, sends on-demand discovery request
- If LC remains offline: its managed devices accumulate missed cycles; eventually
  marked inactive per normal discovery rules
- Config proposals targeting LC's devices are blocked until LC is back online

### RC Goes Offline
- LCs queue proposals locally and retry with exponential backoff
- LOW changes can execute directly if policy allows (`allow_local_exec=true`)
- HIGH changes are blocked — no path to GC without RC
- RC's NIB view becomes stale; on reconnect, RC requests full resync from GC for
  the period it was absent

### GC Primary Goes Offline
- RCs and LCs continue operating for LOW/MEDIUM changes — RC has approval authority
- HIGH changes are blocked — GC is the only HIGH approval authority
- `global_cntl_2` standby is warm but failover is manual in the PoC
- GC failover design is an open question (Q4 in `ROADMAP_AND_TODO.md`) — must be
  resolved before Phase 6

---

## Controller Naming Convention

| Pattern | Example | Notes |
|---------|---------|-------|
| `global_cntl_{sequence}` | `global_cntl_1` | Sequence from 1; primary is always `_1` |
| `regional_cntl_{region}_{sequence}` | `regional_cntl_zoneA_2` | Region slug + sequence |
| `local_cntl_{region}_{sequence}` | `local_cntl_zoneA_5` | Same region slug as parent RC |

Names are assigned by the validating controller (GC for RCs, RC for LCs) during
the validation flow. Controllers do not self-name.

---

## Scaling Guidelines

A Local Controller should manage no more than one /24 subnet directly for the PoC.
Larger subnets should be split across multiple LCs. This is not a hard limit —
it is a guideline based on scan timing: a single LC scanning a full /24 with three
protocols (ARP + ICMP + SNMP) at 300-second intervals should complete well within
the interval on any reasonable host.

For Phase 6 with real network deployments, tune based on observed scan duration.
If the discovery cycle duration approaches the discovery interval, add another LC.
