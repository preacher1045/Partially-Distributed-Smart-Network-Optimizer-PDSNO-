# PDSNO Master Reference Document

> **Purpose:** A single comprehensive document summarizing the entire PDSNO project for collaborators. For detailed specifications, refer to the individual documentation files in this directory.

---

## 1. Project Overview

### What is PDSNO?

**PDSNO (Partially Distributed Software-Defined Network Orchestrator)** is a hierarchical network orchestration framework that distributes control intelligence across three tiers — Global, Regional, and Local — while maintaining a centralized root of trust at the top.

The "partial" in the name is deliberate: PDSNO is not a fully peer-to-peer system. Policy authority and trust flow downward from the Global Controller. What is distributed is *execution* and *local decision-making* — Local Controllers handle device-level actions without waiting for global approval on every operation, and Regional Controllers govern their zones with meaningful autonomy.

### Project Goals

- Reduce single points of failure by distributing execution across controller tiers
- Enable programmable, policy-driven orchestration at every layer
- Provide strong auditability — every action, approval, and change is traceable
- Automate routine network management while keeping humans in the loop for high-risk changes
- Build a vendor-agnostic framework that can integrate with Cisco, VMware, Juniper, and others

### Research Foundations

PDSNO's architecture is grounded in established SDN research:

- **ONF SDN Architecture (TR-521)** — Standardized interface naming (NBI, SBI, East/West)
- **Onix NIB Design (Koponen et al., OSDI 2010)** — Network Information Base concept where controllers read/write shared state
- **Self-Organizing Network Principles** — Self-Configuration, Self-Optimization, Self-Healing
- **DISCO Architecture** — Delta-sync principle for inter-controller communication
- **Alsheikh et al. (2024)** — Adaptive consistency model recommendation

---

## 2. System Architecture

### Architectural Principles

1. **State lives in the NIB** — No controller trusts its own memory for network facts
2. **Hierarchy for governance, not performance** — Clear chain of authority for auditability
3. **Every action is auditable** — No change executes without a signed audit trail
4. **Interfaces are contracts** — Controllers communicate only through defined message types

### System Layers

```
┌─────────────────────────────────────────────────────┐
│              APPLICATION LAYER                       │
│  External tools, dashboards, vendor adapters (NBI)  │
└───────────────────────┬─────────────────────────────┘
                        │ NBI (REST/HTTP)
┌───────────────────────▼─────────────────────────────┐
│              CONTROL LAYER                           │
│                                                      │
│  Global Controller (GC)                              │
│    └─► Regional Controller (RC)                     │
│          └─► Local Controller (LC)                  │
└───────────────────────┬─────────────────────────────┘
                        │ SBI (NETCONF, SNMP, ARP, ICMP)
┌───────────────────────▼─────────────────────────────┐
│              DATA LAYER                              │
│  Network Devices (switches, routers, endpoints)     │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              STATE LAYER (NIB)                       │
│  Device Table │ Config Table │ Policy Table          │
│  Metadata Store │ Event Log │ Controller Sync Table  │
└─────────────────────────────────────────────────────┘
```

### Internal Controller Structure

Every controller has four internal components:
- **Decision Engine** — Runs approval logic, policy checks, escalation decisions
- **Communication Layer** — REST server (NBI/East-West), MQTT client (pub/sub)
- **Data Layer** — NIBStore interface for all reads/writes
- **Algorithm Modules** — Discovery, validation, optimization (initialize/execute/finalize pattern)

---

## 3. Controller Hierarchy

### Three-Tier Model

| Tier | Count | Scope | Validates | Approves |
|------|-------|-------|-----------|----------|
| **Global** | 1 primary + 1 standby | Entire network | Regional Controllers | HIGH configs |
| **Regional** | 1 per geographic zone | Single zone | Local Controllers (delegated) | MEDIUM/LOW configs |
| **Local** | 1 per subnet block | Direct device reach | Nothing | LOW configs (direct) |

### Controller Responsibilities

| Responsibility | LC | RC | GC |
|---------------|----|----|-----|
| Device discovery (execution) | ✓ | | |
| Discovery report aggregation | | ✓ | |
| LOW config approval | ✓ | Auto | |
| MEDIUM config approval | | ✓ | |
| HIGH config approval | | | ✓ |
| Emergency execution | ✓ | | |
| Controller validation (LC) | | ✓ | |
| Controller validation (RC) | | | ✓ |
| Global policy holder | | | ✓ |

### Validation Flow

Before any controller joins the network, it must pass a multi-step cryptographic verification:

1. **Request** — New controller sends validation request with temp ID, public key, bootstrap token
2. **Checks** — Validator verifies timestamp freshness, checks blocklist
3. **Token Verification** — Bootstrap token cryptographically verified
4. **Challenge-Response** — Nonce issued; controller signs with private key
5. **Policy Check** — Metadata validated against policy (region, type, zone)
6. **Identity Assignment** — Unique ID, certificate, role assigned atomically

### Offline Behavior

- **LC Offline**: RC queues discovery cycles; configs targeting LC's devices are blocked
- **RC Offline**: LCs queue proposals locally; LOW changes can execute if policy allows; HIGH changes blocked
- **GC Offline**: RCs continue operating for LOW/MEDIUM; HIGH changes blocked; new validations impossible

### Naming Convention

| Pattern | Example | Notes |
|---------|---------|-------|
| `global_cntl_{seq}` | `global_cntl_1` | Primary is always `_1` |
| `regional_cntl_{region}_{seq}` | `regional_cntl_zoneA_2` | Region slug + sequence |
| `local_cntl_{region}_{seq}` | `local_cntl_zoneA_5` | Same region as parent RC |

---

## 4. Communication Model

### Protocol Assignment

| Message Category | Protocol | Direction | Rationale |
|-----------------|----------|-----------|-----------|
| Controller validation | REST/HTTP | LC→RC, RC→GC | Request/response with definite answer |
| Config approval | REST/HTTP | LC→RC, RC→GC | Approval is a decision with result |
| Policy distribution | MQTT (pub/sub) | GC→RC→LC | Broadcast, fire-and-forget with QoS |
| Discovery reports | REST/HTTP | LC→RC | Structured report requiring validation |
| State change events | MQTT (pub/sub) | Any→Any | Event notification |
| NBI (external) | REST/HTTP | External→GC | Standard API |
| SBI (devices) | NETCONF/SNMP | LC→Device | Industry standard |

### Delta-Sync Principle

Controllers only exchange what changed, never full state. Every NIB entity has a `version` integer and `updated_at` timestamp. Changed entities are published via MQTT; subscribers merge deltas into their local view.

### Message Envelope Format

```json
{
  "envelope": {
    "message_id": "uuid-v4",
    "message_type": "VALIDATION_REQUEST | CHALLENGE | CONFIG_PROPOSAL | ...",
    "sender_id": "regional_cntl_1",
    "recipient_id": "global_cntl_1",
    "timestamp": "ISO-8601",
    "signature": "hmac-sha256-hex",
    "schema_version": "1.0"
  },
  "payload": { /* message-type-specific */ }
}
```

### Message Authentication

- Every message must be signed; unsigned messages rejected unconditionally
- **PoC (Phases 1-5)**: HMAC-SHA256 with shared secret
- **Phase 6+**: Asymmetric signatures (Ed25519/ECDSA)
- **Replay prevention**: Timestamp freshness window (5 min) + message_id deduplication

### Timeout Contracts

| Message Type | Timeout | Max Retries | On Failure |
|-------------|---------|-------------|------------|
| Validation challenge | 30s | 0 | Reject, audit entry |
| Config approval | 60s | 3 (exponential backoff) | Escalate or deny |
| Discovery report | 30s | 3 | Log failure, reconciliation |

---

## 5. Network Information Base (NIB)

### Overview

The NIB is PDSNO's authoritative source of truth for all network and system state. Controllers read from and write to the NIB through a defined interface — they never trust local memory for network facts.

### NIB Modules

| Module | Description | Primary Writer |
|--------|-------------|----------------|
| **Device Table** | Discovered network devices | Local Controller |
| **Metadata Store** | Extended device attributes | Local Controller |
| **Config Table** | Configuration history and approvals | LC (proposals), RC/GC (approvals) |
| **Policy Table** | Active policies from GC | Global Controller |
| **Event Log** | Immutable audit trail | All controllers |
| **Controller Sync** | Locks, tokens, sync state | RC, GC |

### Two-Tier Data Classification

| Tier | Characteristics | Examples | Priority |
|------|----------------|---------|----------|
| **Transient** | Changes frequently, tolerable staleness | Link utilization, discovery results, counters | Availability |
| **Durable** | Changes slowly, must be consistent | Controller identities, approved configs, audit logs | Consistency |

**PoC**: All data in SQLite with optimistic locking
**Phase 6+**: Transient → Redis; Durable → PostgreSQL with Raft

### Consistency Model

**Optimistic Locking Protocol:**
1. READ record + current version
2. COMPUTE change locally
3. WRITE with condition: commit only if version matches
4. ON CONFLICT: Re-read, re-compute, retry (max 3)

**Conflict Resolution Rules:**
- Config approval: First writer wins; second gets CONFLICT
- Device discovery: Most recent `last_seen` wins
- Policy writes: Serialized through GC (no conflicts possible)
- Event Log: Append-only with UUID keys

### Device Table Schema

```
device_id          STRING    PRIMARY KEY
mac_address        STRING    UNIQUE
ip_address         STRING    NOT NULL
hostname           STRING
vendor             STRING
device_type        STRING    -- router | switch | server | endpoint | unknown
region             STRING    NOT NULL
local_controller   STRING    NOT NULL
status             STRING    NOT NULL -- active | inactive | unreachable | quarantined
first_seen         DATETIME
last_seen          DATETIME
discovery_method   STRING    -- arp | snmp | icmp | fingerprint
```

---

## 6. Algorithm Lifecycle Pattern

### Three-Phase Structure

Every operational module follows this pattern:

| Phase | Method | Purpose |
|-------|--------|---------|
| **Initialize** | `initialize(context)` | Validate parameters, load config, store as instance state |
| **Execute** | `execute()` | Run core logic using stored state |
| **Finalize** | `finalize()` | Free resources, write outputs, return result payload |

### Base Class Interface

```python
class AlgorithmBase:
    def initialize(self, context: dict) -> None:
        """Prepare algorithm. Store state as instance variables."""
        raise NotImplementedError

    def execute(self) -> any:
        """Run core logic. Uses state from initialize()."""
        raise NotImplementedError

    def finalize(self) -> dict:
        """Clean up. Return: {status, timestamp, result}"""
        raise NotImplementedError
```

### Key Rules

- Each instance is single-use: initialize → execute → finalize
- Algorithms are NOT thread-safe by default
- Controllers assemble context from NIB + config + runtime parameters
- `_initialized` flag prevents `execute()` before `initialize()`

---

## 7. Configuration Approval System

### Sensitivity Classification

| Level | Approval Path | Examples |
|-------|--------------|----------|
| **LOW** | LC auto-approves | Logging changes, minor interface updates |
| **MEDIUM** | RC approval required | VLAN changes, routing updates |
| **HIGH** | GC approval required | BGP policy, ACL changes, security policies |
| **EMERGENCY** | LC executes immediately | DDoS mitigation, quarantine |

### Approval Flow

1. LC creates proposal with suggested sensitivity, rollback payload
2. RC independently re-classifies (LC suggestion is advisory only)
3. RC acquires device lock via Controller Sync Table
4. LOW/MEDIUM: RC approves, issues execution token
5. HIGH: RC escalates to GC; GC approves/denies
6. Execution token returned to LC
7. LC verifies token (signature + binding + expiry + single-use)
8. LC writes EXECUTING → applies config → writes EXECUTED
9. On failure: rollback → write ROLLED_BACK or DEGRADED
10. Release device lock

### Execution Tokens

- Cryptographically signed, single-use, time-bounded
- Bound to: proposal ID, config hash, target devices, approver ID, expiry
- Prevents: Tampering, replay attacks, unauthorized execution
- Token redemption recorded in NIB; second use rejected

### Emergency Mode

- Rate-limited per controller (default: 3/hour)
- Restricted to specific config types (quarantine, rate-limit)
- Every emergency invocation triggers immediate notification to RC/GC
- Most heavily audited path — full payload captured

---

## 8. Network Discovery

### Discovery Engine

Local Controllers identify and track devices using multiple protocols:

| Protocol | Purpose |
|----------|---------|
| **ARP Scan** | Local subnet device detection |
| **ICMP Ping** | Reachability testing |
| **SNMP** | Device capability and health gathering |
| **HTTP/SSH** | Device type and firmware fingerprinting |

### Discovery Flow

1. LC reads policy → builds scan targets
2. LC runs parallel scans (ARP + ICMP + SNMP)
3. LC consolidates per-device (keyed on MAC)
4. LC diffs against local NIB
5. LC writes to NIB: Device Table, Event Log
6. LC sends DISCOVERY_REPORT to RC (delta only)
7. RC validates, deduplicates across LCs, flags anomalies
8. RC sends DISCOVERY_SUMMARY to GC
9. GC performs global deduplication (cross-region MAC check)

### Device State Transitions

- Device not responding: `missed_cycles` counter incremented
- After `missed_cycles_before_inactive` (default: 3): status → `inactive`
- Device comes back: next discovery cycle → status → `active`

---

## 9. Data Flow Summary

### Flow 1: Device Discovery

**Direction:** Upward (LC → RC → GC)
**Data Type:** Delta reports (only changed devices)
**Transport:** REST for reports; MQTT for notifications

### Flow 2: Configuration Approval

**Direction:** Proposals upward (LC → RC → GC); Approvals downward (GC → RC → LC)
**Data Type:** Signed JSON messages
**Transport:** REST for request/response

### Flow 3: Policy Distribution

**Direction:** Downward only (GC → RC → LC)
**Data Type:** MQTT pub/sub (QoS 2 — exactly-once)
**Transport:** MQTT topics: `pdsno/{region}/policy/updates`

---

## 10. Security Model

### Trust Boundaries

```
UNTRUSTED                    TRUST BOUNDARY                    TRUSTED
─────────────────────────────────────────────────────────────────────
Unvalidated controller  ──[Validation flow]──►  Validated controller
External application    ──[NBI auth]──────────►  Authorized client
Network device          ──[SBI credentials]───►  Managed device
```

### Security Properties

| Component | Property |
|-----------|----------|
| **Controller Identity** | Cryptographically assigned, expires, must be renewed |
| **Message Authentication** | HMAC-SHA256 (PoC) → Ed25519 (Phase 6+) |
| **Replay Prevention** | Timestamp freshness + message_id deduplication |
| **Config Governance** | Signed execution tokens, single-use, bound to proposal |
| **NIB Integrity** | Event Log append-only, all entries signed |

### Security Phases

| Phase | Capabilities |
|-------|-------------|
| **PoC (1-5)** | HMAC signing, shared secrets, signed JSON certificates, single-use tokens |
| **Phase 6** | Asymmetric crypto (Ed25519), mTLS, MQTT over TLS, certificate rotation |
| **Phase 7+** | Key management service, HSM support, formal RBAC |

---

## 11. Threat Model Summary

| Threat | Mitigation |
|--------|-----------|
| Rogue controller joins | Validation flow with challenge-response + bootstrap token |
| LC spoofs LOW sensitivity for HIGH | RC independently re-classifies every proposal |
| Emergency mode abuse | Rate limiting + restricted configs + mandatory audit |
| Execution token replay | Single-use, bound to hash/devices, expiry |
| Partial execution failure | Execution state written first; reconciliation on reconnect |
| Concurrent config conflicts | Device locking at approval time |
| Rollback failure | Device → DEGRADED state; blocks automation until manual review |
| Forged audit logs | Signed entries; cross-validated with NIB state |

### Out of Scope for v1

- Compromised Global Controller (requires HSM, distributed consensus)
- Physical security of controller hosts
- Insider threats from administrators with legitimate access

---

## 12. API Reference Summary

### Controller Validation Messages

| Message | Direction | Purpose |
|---------|-----------|---------|
| `VALIDATION_REQUEST` | Unvalidated → Validator | Submit registration with temp_id, public key, bootstrap token |
| `CHALLENGE` | Validator → Requester | Issue nonce for signature |
| `CHALLENGE_RESPONSE` | Requester → Validator | Return signed nonce |
| `VALIDATION_RESULT` | Validator → Requester | Return assigned_id, certificate, delegation credential |

### Discovery Messages

| Message | Direction | Purpose |
|---------|-----------|---------|
| `DISCOVERY_REQUEST` | RC/GC → LC | Trigger on-demand scan |
| `DISCOVERY_REPORT` | LC → RC | Submit scan results (delta) |
| `DISCOVERY_SUMMARY` | RC → GC | Aggregate regional results |

### Config Approval Messages

| Message | Direction | Purpose |
|---------|-----------|---------|
| `CONFIG_PROPOSAL` | LC → RC | Submit config change request |
| `APPROVAL_RESPONSE` | RC/GC → LC | Return decision + token |
| `EXECUTION_INSTRUCTION` | RC → LC | Deliver execution token |
| `EXECUTION_RESULT` | LC → RC | Report execution outcome |

### MQTT Topics

| Topic | Publisher | Purpose |
|-------|-----------|---------|
| `pdsno/{region}/discovery/reports` | LC | Discovery submissions |
| `pdsno/global/policy/updates` | GC | Global policy broadcast |
| `pdsno/{region}/policy/updates` | RC | Regional policy propagation |
| `pdsno/global/events` | Any | System-wide event feed |

---

## 13. Use Cases

### UC-1: New Device Joins Network

1. LC discovery cycle detects new MAC via ARP
2. ICMP confirms reachability; SNMP returns vendor info
3. LC writes to Device Table + Event Log
4. LC sends discovery report to RC
5. RC validates, writes to regional NIB
6. Device now visible to all tiers

### UC-2: Low-Risk Config Change

1. External tool POSTs proposal via NBI
2. RC classifies as LOW, policy allows LC direct execution
3. RC issues execution token (TTL: 600s)
4. LC verifies token, applies config
5. Full round-trip: ~5 seconds, zero human intervention

### UC-3: High-Risk Config Change

1. LC creates proposal with HIGH sensitivity
2. RC confirms HIGH, acquires device lock, escalates to GC
3. GC checks policy, approves, issues token (TTL: 300s)
4. Token travels back through RC to LC
5. LC verifies, applies change, reports result
6. Full audit trail maintained

### UC-4: Emergency Response (DDoS)

1. LC detects traffic surge exceeding threshold
2. LC creates EMERGENCY proposal (rate limiter allows)
3. LC executes immediately (no token required)
4. LC writes audit entry with full payload
5. LC notifies RC and GC asynchronously
6. If RC denies retrospectively: rollback runs

### UC-5: Device Goes Unreachable

1. LC discovery cycle: ARP/ICMP fail for device
2. `missed_cycles` counter incremented
3. After 3 consecutive misses: status → `inactive`
4. Pending configs targeting device blocked
5. When device returns: next discovery → `active`

---

## 14. Deployment

### PoC Deployment (Phases 1-5)

All controllers as Python processes on single machine or local network.

**Prerequisites:**
- Python 3.11+
- SQLite 3.35+
- pip packages from requirements.txt

**Starting Controllers:**
```bash
# 1. Initialize NIB
python -m pdsno.data.init_nib --env dev

# 2. Start Global Controller
python -m pdsno.controllers.global_controller --id global_cntl_1 --role global

# 3. Start Regional Controller
python -m pdsno.controllers.regional_controller --region zone-A --parent global_cntl_1

# 4. Start Local Controller
python -m pdsno.controllers.local_controller --region zone-A --subnets 10.0.1.0/24
```

### Phase 6+ Deployment

**Infrastructure:**
- MQTT broker (Mosquitto/EMQX)
- PostgreSQL (durable NIB)
- Redis (transient NIB)
- TLS certificates

**Scaling:**
- Global: 1 primary + 1 standby
- Regional: 1 per geographic zone
- Local: 1 per /24 subnet block (tune based on device count)

---

## 15. Production Hardening

### Security Checklist

- [ ] TLS enabled for REST (HTTPS)
- [ ] TLS enabled for MQTT (port 8883)
- [ ] Rate limiting configured
- [ ] CA certificates generated and distributed
- [ ] Bootstrap tokens provisioned
- [ ] RBAC roles assigned
- [ ] Secrets encrypted and backed up

### Monitoring

- Prometheus metrics on port 9090
- Key metrics: active_controllers, validation_requests, config_approvals, message_latency
- Alerts for: controller offline, high error rate, failed auth, cert expiration

### Backup & Recovery

- NIB database backup automated
- Configuration backups automated
- DR plan documented
- Recovery runbooks created

---

## 16. Development Roadmap

### Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Documentation & architecture hardening |
| Phase 1 | ✅ Complete | Project foundation (venv, folder structure, logging) |
| Phase 2 | ✅ Complete | Base classes (AlgorithmBase, BaseController, ContextManager) |
| Phase 3 | ✅ Complete | NIB (SQLite, optimistic locking) |
| Phase 4 | ✅ Complete | In-process message bus |
| Phase 5 | ✅ Complete | Controller validation flow |
| Phase 6A | ✅ Complete | REST communication layer |
| Phase 6B | ✅ Complete | MQTT integration |
| Phase 7 | ✅ Complete | Configuration approval logic |
| Phase 8 | 🟡 In Progress | Production hardening |

### Future Directions

- Vendor adapters (Cisco ACI, VMware NSX, Juniper)
- AI/ML decision layer for predictive orchestration
- Multi-tenant and multi-domain support
- Kubernetes/Docker deployment

---

## 17. Contribution Guidelines

### Architecture Alignment

All new modules must:
- Fit into one controller tier (Global/Regional/Local)
- Clearly state tier and communication interface
- Use REST or MQTT per the protocol assignment
- Never directly access another tier's internal structures
- Follow the algorithm lifecycle pattern (initialize/execute/finalize)

### Review Process

Every PR must:
1. Reference an approved issue
2. Include architecture alignment section
3. Pass code review by core maintainer
4. Include README/docstring explaining purpose
5. Update architecture docs if affecting system flow

### Technology Stack

- **Prototype**: Python
- **Performance modules**: Go or Rust (future)
- **Web/API layer**: FastAPI

---

## 18. Competitive Positioning

### Target Customer

Organizations running multiple vendor orchestration platforms (Cisco ACI, VMware NSX, etc.) that need:
- Unified visibility across all vendor domains
- Consistent policy enforcement
- Unified audit trail for compliance
- Cross-domain change governance

### Value Proposition

**"PDSNO gives you control and visibility across your entire network, not just the parts your vendor covers."**

### Key Differentiators

1. **Vendor-Agnostic** — Adapter layer integrates with any vendor's API
2. **Multi-Domain Policy** — Common policy model translated per vendor
3. **Unified Audit Trail** — Single compliance report across all domains
4. **Governance-First** — Approval workflows built for enterprise requirements

---

## 19. Glossary

| Term | Definition |
|------|------------|
| **GC** | Global Controller — root of trust |
| **RC** | Regional Controller — zone governance |
| **LC** | Local Controller — device-level control |
| **NIB** | Network Information Base — shared state store |
| **NBI** | Northbound Interface — external API |
| **SBI** | Southbound Interface — device communication |
| **SON** | Self-Organizing Network principles |
| **ONF** | Open Networking Foundation |
| **mTLS** | Mutual TLS authentication |

---

## 20. Document Reference

For detailed specifications, refer to these files:

| Topic | Document |
|-------|----------|
| Project overview | PROJECT_OVERVIEW.md |
| System architecture | architecture.md |
| Controller hierarchy | controller_hierarchy.md |
| Communication model | communication_model.md |
| NIB specification | nib_spec.md |
| NIB consistency | nib_consistency.md |
| Algorithm lifecycle | algorithm_lifecycle.md |
| Data flow | dataflow.md |
| Security model | security_model.md |
| Threat model | threat_model_and_mitigation.md |
| API reference | api_reference.md |
| Use cases | use_cases.md |
| Deployment guide | deployment_guide.md |
| Production hardening | Production_hardening.md |
| Operational runbook | OPERATIONAL_RUNBOOK.md |
| Roadmap | ROADMAP_AND_TODO.md |
| Contribution rules | contibution-rules.md |
| Gap analysis | pdsno_gap_analysis.md |
| Research analysis | research_paper_analysis.md |

---

*Document generated: February 2026*
*For questions, refer to individual documentation files or contact the project maintainer.*
