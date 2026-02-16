---
title: Project Overview
status: Active
author: Alexander Adjei
last_updated: 2026-02-14
depends_on: README.md
---

# PDSNO — Project Overview

## What Is PDSNO?

**PDSNO (Partially Distributed Software-Defined Network Orchestrator)** is a hierarchical network orchestration framework that distributes control intelligence across three tiers — Global, Regional, and Local — while maintaining a centralized root of trust at the top.

The "partial" in the name is deliberate and worth explaining upfront. PDSNO is not a fully peer-to-peer or leaderless system. Policy authority and trust flow downward from the Global Controller. What is distributed is *execution* and *local decision-making* — Local Controllers handle device-level actions without waiting for global approval on every operation, and Regional Controllers govern their zones with meaningful autonomy for most operational tasks.

This hybrid model is a conscious tradeoff: it provides the operational speed benefits of distributed systems while preserving the governance and auditability that enterprise networks require.

---

## Architectural Foundations

PDSNO's architecture is grounded in established SDN research and standards. Key alignments:

**ONF SDN Architecture (TR-521)** — PDSNO follows the Open Networking Foundation's SDN architecture principles, including standardized interface naming (NBI, SBI, East/West interfaces), the feedback-loop controller model, and the principle of coexistence with non-SDN infrastructure. This means PDSNO speaks the same architectural language as the rest of the SDN industry.

**Onix NIB Design** — The Network Information Base concept in PDSNO is independently aligned with Onix (Koponen et al., OSDI 2010), the distributed SDN controller developed at Nicira and used as the foundation for VMware NSX. The core insight — that control applications should read and write to a shared data structure rather than communicate with each other directly — is the same in both systems.

**Self-Organizing Network Principles** — PDSNO's algorithm framework and controller autonomy map to the three SON principles: Self-Configuration (device discovery), Self-Optimization (congestion mitigation, policy adaptation), and Self-Healing (rollback, fault recovery). This framing is useful for describing PDSNO to audiences familiar with SON/automation concepts.

### A Note on Hierarchy vs. Performance

PDSNO uses a hierarchical controller model (Global → Regional → Local). Research into distributed SDN architectures notes that flat, logically-centralized physically-distributed architectures offer better raw performance for large-scale fluctuating networks because they eliminate the latency of cross-domain communication through a root controller.

PDSNO accepts this tradeoff deliberately. The hierarchy exists for **governance reasons, not performance reasons**:

- The Global Controller is the root of trust — someone must be authoritative for identity and policy
- High-sensitivity configuration changes require a chain of custody that a flat architecture cannot provide
- Audit trails and compliance reporting require a well-defined authority hierarchy

In environments where the governance requirements are less strict and performance is the primary concern, a flatter topology would be appropriate. PDSNO is designed for environments where governance matters. This tradeoff is documented explicitly so future contributors understand it was a conscious decision.

---

- Reduce single points of failure by distributing execution across controller tiers
- Enable programmable, policy-driven orchestration at every layer of the network
- Provide strong auditability — every action, approval, and change is traceable
- Automate routine network management tasks while keeping humans in the loop for high-risk changes
- Build a framework that can evolve from a Python prototype toward a production-grade, multi-language system

---

## Architectural Model

PDSNO is organized around four functional layers present in every controller:

| Layer | Purpose |
|-------|---------|
| **Decision Layer** | Runs logic, evaluates policies, and makes orchestration decisions |
| **Communication Layer** | Handles inter-controller messaging and data synchronization |
| **Data Layer** | Stores dynamic context, device state, and configuration history |
| **Application Layer** | Provides discovery algorithms, optimization modules, and external APIs |

The system combines three architectural patterns:

**Layered Architecture** provides clear boundaries between concerns. No layer reaches into another's internals.

**Event-Driven Architecture** allows controllers to react to network changes asynchronously. A device going offline triggers a chain of events rather than a polling loop.

**Microservice Architecture** (targeted for later phases) allows individual modules — discovery, validation, approval — to be deployed, scaled, and updated independently.

### Standard Interface Naming (ONF TR-521)

PDSNO follows the Open Networking Foundation's interface naming conventions:

| Interface | ONF Name | Direction | Purpose in PDSNO |
|-----------|----------|-----------|-----------------|
| **NBI** (Northbound Interface) | Applications-Control Plane Interface (A-CPI) | Controller → Applications above | Exposes orchestration capabilities to external tools, dashboards, and the vendor adapter layer |
| **SBI** (Southbound Interface) | Device-Control Plane Interface (D-CPI) | Controller → Devices below | Communicates with managed network devices via NETCONF, SNMP, REST, or OpenFlow |
| **East/West Interface** | Inter-Controller Interface | Controller ↔ Controller | Peer communication between controllers at the same tier; also used for the hierarchical validation flow |

These naming conventions are used consistently throughout all PDSNO documentation.

---

## Controller Hierarchy

PDSNO uses three controller tiers. Each tier has distinct authority and responsibility:

| Tier | Role | Scope | Examples |
|------|------|-------|---------|
| **Global Controller** | Root of trust, policy authority, high-risk approvals | System-wide | `global_cntl_1`, `global_cntl_2` |
| **Regional Controller** | Zone governance, most operational approvals, local controller validation (after being validated itself) | One network region or geographic zone | `regional_cntl_1` through `regional_cntl_5` |
| **Local Controller** | Device-level control, discovery, low-latency response | Direct device interaction | `local_cntl_1` through `local_cntl_9` |

### Data and Control Flow

Control flows **downward**: Global sets policy → Regional enforces it → Local executes it.

Telemetry flows **upward**: Local reports device state → Regional aggregates → Global correlates.

Neither direction is synchronous for all operations. Local controllers cache relevant policy and can operate with degraded connectivity to their regional controller, within defined limits.

### An Important Note on Trust

Every controller — Regional and Local — must be **validated before participating** in the system. Regional controllers are validated by the Global Controller. Local controllers are validated by their respective Regional Controller (after that Regional Controller has itself been validated). This creates a chain of trust rooted at the Global Controller.

If the Global Controller is unavailable, no new Regional Controllers can be validated and no new trust can be established. This is an intentional design constraint in v1, with a planned mitigation (secondary global controller failover) tracked in the architecture backlog.

---

## Controller Validation

Before any controller joins the network it must pass a multi-step cryptographic verification process:

| Step | What Happens |
|------|-------------|
| **1. Request** | The new controller sends a validation request with a temporary ID, public key, metadata, and a bootstrap token |
| **2. Checks** | The validating controller verifies timestamp freshness and checks the temp ID against a blocklist |
| **3. Token Verification** | The bootstrap token is cryptographically verified |
| **4. Challenge-Response** | A nonce is issued; the requesting controller must sign it with its private key |
| **5. Policy Check** | Metadata is cross-validated against policy (correct region, correct type, permitted zone) |
| **6. Identity Assignment** | A unique ID, certificate, and role are assigned and written atomically to the NIB and context store |

Full details are in [`docs/architecture/verification/controller_validation_sequence.md`](architecture/verification/controller_validation_sequence.md).

---

## Algorithm Framework

Every operational module in PDSNO — discovery, validation, congestion handling, policy execution — follows a three-phase lifecycle. This enforces consistency and makes each module predictable to implement and test.

```python
class AlgorithmBase:
    def initialize(self, context: dict) -> None:
        """Load context, validate inputs, allocate resources. Store state as instance variables."""
        raise NotImplementedError

    def execute(self) -> any:
        """Run the algorithm's core logic using state stored during initialize()."""
        raise NotImplementedError

    def finalize(self) -> dict:
        """Clean up resources, write outputs, return result payload."""
        raise NotImplementedError
```

Controllers load, run, and monitor algorithms through a standard interface, which allows algorithms to be scheduled, audited, and rolled back independently.

Full details are in [`docs/algorithm_lifecycle.md`](algorithm_lifecycle.md).

---

## Dynamic Context Management

All runtime state — controller identities, validation status, active policies, pending queue entries — is stored in `context_runtime.yaml` and managed by `context_manager.py`.

The context manager enforces **atomic writes**: no partial updates are permitted. Either the full state change is committed or nothing changes. This is critical in the validation flow, where a certificate issuance and a context update must succeed or fail together.

Example structure (field names illustrative, not final):

```yaml
system:
  id: auto_generated
  name: auto_assigned
  role: auto_determined
  status: active

controllers:
  global:
    primary: global_cntl_1
    secondary: global_cntl_2
  regional:
    validated: [regional_cntl_1, regional_cntl_3]
    pending: []
  local:
    validated: [local_cntl_1, local_cntl_2]
    pending: [local_cntl_5]

validation_queue: []
```

---

## Network Information Base (NIB)

The NIB is the system's source of truth for all device and network state. Rather than each controller maintaining its own independent state, all controllers read from and write to the NIB through a defined interface.

The NIB stores:

- Discovered device records (IP, MAC, vendor, capabilities, health status)
- Configuration version history and approval records
- Policy tables distributed from Global → Regional → Local
- Audit and event logs
- Controller synchronization state

The NIB consistency model and schema are defined in [`docs/architecture/nib/nib_spec.md`](architecture/nib/nib_spec.md).

---

## Network Discovery

The discovery engine identifies and tracks network devices using multiple protocols running in parallel:

| Protocol | File | Purpose |
|----------|------|---------|
| ARP Scan | `arp_scan.py` | Local subnet device detection |
| ICMP Ping | `icmp_ping.py` | Reachability testing |
| SNMP | `snmp.py` | Device capability and health gathering |
| HTTP/SSH Fingerprinting | `fingerprint.py` | Device type and firmware identification |

Each method is implemented as an `AlgorithmBase` subclass and can run in parallel under coordination from the Local Controller.

---

## Current Development Stage

| Status | Item |
|--------|------|
| ✅ Complete | Core architecture definition |
| ✅ Complete | Controller hierarchy and validation design |
| ✅ Complete | Algorithm lifecycle pattern |
| ✅ Complete | Configuration approval logic design |
| ✅ Complete | Threat model (v1) |
| 🟡 In Progress | Documentation cleanup and gap-filling |
| 🟡 In Progress | NIB specification |
| ⚪ Not Started | Python proof-of-concept implementation |
| ⚪ Not Started | Discovery module implementation |
| ⚪ Not Started | Real communication layer (REST/MQTT) |

See [`ROADMAP_AND_TODO.md`](../ROADMAP_AND_TODO.md) for the full phased development plan.

---

## Contributing

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for setup instructions, coding standards, and the architecture review process.
