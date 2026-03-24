# PDSNO — Partially Distributed Software-Defined Network Orchestrator

> **You're running Cisco ACI in the data center, VMware NSX for virtualization, and something else at the branch. You have three dashboards, three policy systems, and three audit logs. When something breaks, you reconstruct what happened manually. PDSNO fixes that.**

![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-brightgreen)
![Tests](https://img.shields.io/badge/Tests-62%20Passing-success)
![Phase](https://img.shields.io/badge/Phase-6D%20Complete-orange)
![Status](https://img.shields.io/badge/Status-Active%20Development-yellow)
![Contributions](https://img.shields.io/badge/Contributions-Welcome-brightgreen)

---

## What Is PDSNO?

PDSNO is an open-source network orchestration framework that sits **above** your existing vendor tools — Cisco ACI, VMware NSX, Juniper Apstra, whatever you're running — and provides the layer none of them deliver alone:

- **Unified governance** across vendor domains
- **Cross-domain change approval** with cryptographic execution tokens
- **A single audit trail** that covers every change, regardless of vendor
- **Policy consistency enforcement** that doesn't care which vendor manufactured the device

The target environment is any organization running multiple vendor platforms and experiencing the governance gaps that creates. If your compliance team cannot produce a unified 90-day change record, or if you manage policy in three separate systems that can drift out of sync, PDSNO is designed for you.

PDSNO does not replace Cisco ACI or VMware NSX. It governs them.

---

## The Architecture

PDSNO uses a three-tier hierarchical controller model grounded in ONF SDN Architecture (TR-521) and the Onix NIB design (Koponen et al., OSDI 2010):

```
┌─────────────────────────────────────────────────────┐
│          Global Controller (GC)                      │
│  Root of trust · HIGH config approval · Global policy│
└──────────────────────┬──────────────────────────────┘
                       │ East/West
┌──────────────────────▼──────────────────────────────┐
│          Regional Controller (RC)                    │
│  Zone governance · MEDIUM/LOW approval · LC validation│
└──────────────────────┬──────────────────────────────┘
                       │ East/West
┌──────────────────────▼──────────────────────────────┐
│          Local Controller (LC)                       │
│  Device discovery · Config execution · SBI interface │
└──────────────────────┬──────────────────────────────┘
                       │ SBI (NETCONF, SNMP, ARP, ICMP)
                 Network Devices
```

Every controller reads and writes state through the **Network Information Base (NIB)** — a shared state store that eliminates consistency bugs from local controller memory. Every action produces a signed, tamper-evident audit entry. No change executes without a cryptographic execution token bound to the specific proposal, devices, and time window.

---

## What's Built

This project is in active development. Here's an honest snapshot of what exists today:

### ✅ Complete and Tested (62/62 tests passing)

| Component | What It Does |
|-----------|-------------|
| **Three-tier controller hierarchy** | Global, Regional, Local controllers with delegated validation authority |
| **Controller validation** | Full 6-step challenge-response flow — bootstrap token, nonce signing, policy checks, atomic identity assignment |
| **Network Information Base (NIB)** | SQLite-backed shared state store with optimistic locking, append-only Event Log, device locks |
| **Device discovery** | ARP, ICMP, SNMP parallel scanning with delta detection and MAC-based deduplication |
| **Configuration approval** | Sensitivity classification (LOW/MEDIUM/HIGH/EMERGENCY), approval workflows, state machine |
| **Execution tokens** | HMAC-SHA256 signed, single-use, bound to proposal + config hash + target devices + expiry |
| **REST communication** | FastAPI endpoints for controller-to-controller request/response |
| **MQTT pub/sub** | Policy distribution (GC → RC → LC), discovery report broadcasting |
| **Message authentication** | HMAC-SHA256 signing on all inter-controller messages, replay attack prevention via nonces |
| **DH key exchange** | Ephemeral Diffie-Hellman with HKDF derivation — perfect forward secrecy, no pre-shared secrets |
| **Vendor adapter layer** | Factory pattern for Cisco IOS (Netmiko/SSH), Juniper (PyEZ/NETCONF), Arista (eAPI), Generic NETCONF |
| **RBAC** | Role definitions for Global/Regional/Local controllers, operators, API clients |
| **Algorithm lifecycle** | `initialize → execute → finalize` pattern enforced across all operational modules |

### 🔄 In Progress

- Phase 7 state machine integration (config approval ↔ execution token handoff)
- ContainerLab integration for real network testing (FRRouting)
- Production hardening (TLS, rate limiting, Prometheus metrics)

### 📋 Planned

- Vendor adapters for Cisco ACI REST API, VMware NSX Manager
- Multi-machine deployment testing
- Web dashboard (NBI layer)
- AI/ML decision layer for predictive orchestration

---

## Quick Start

### Prerequisites

- Python 3.11+
- Git

### Run the Simulation

```bash
# Clone
git clone https://github.com/AtlasIris/PDSNO.git
cd PDSNO

# Set up environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Initialize the NIB (Network Information Base)
python scripts/init_db.py --db config/pdsno.db

# Run the full validation + discovery simulation
python examples/simulate_discovery.py

# Run the test suite
pytest tests/ -v
```

### What the simulation does

The discovery simulation starts a Global Controller, validates a Regional Controller through the full 6-step challenge-response flow, creates a Local Controller, runs ARP/ICMP/SNMP scans against a simulated subnet, writes discovered devices to the NIB, sends a delta discovery report to the RC, and checks for MAC address collisions across controllers. You'll see the full audit trail in the output.

---

## How It Compares

| Capability | Cisco ACI | VMware NSX | Juniper Apstra | **PDSNO** |
|-----------|-----------|-----------|----------------|-----------|
| Multi-vendor governance | ❌ Cisco only | ❌ VMware only | ⚠️ Limited | ✅ Vendor-agnostic |
| Unified audit trail | ❌ Per-domain | ❌ Per-domain | ⚠️ Partial | ✅ Cross-domain |
| Open source | ❌ | ❌ | ❌ | ✅ AGPL-3.0 |
| Cryptographic change governance | ⚠️ | ⚠️ | ⚠️ | ✅ Signed tokens |
| Cross-domain policy enforcement | ❌ | ❌ | ⚠️ | ✅ Designed for it |
| Sits above existing tools | ❌ | ❌ | ❌ | ✅ Augments, not replaces |

Juniper Apstra is the closest existing product to what PDSNO is building — it was acquired precisely because it solved multi-vendor management. Apstra is now owned by Juniper, which creates commercial incentives to favour Juniper hardware. PDSNO has no such incentive.

---

## Contributing

PDSNO is actively looking for contributors across several domains. You don't need to be an expert in all of them.

### Where You Can Help Right Now

**Network engineers / SDN specialists**
- Test the vendor adapters against real Cisco, Juniper, or Arista hardware
- Contribute adapter implementations for vendors not yet covered
- Validate discovery behaviour against real network topologies
- Set up ContainerLab integration for CI testing

**Python / distributed systems developers**
- Fix the Phase 7 state machine integration (see GitHub issues)
- Improve NIB consistency under concurrent writes
- Build the REST API NBI layer for external tool integration
- Write integration tests against ContainerLab topologies

**Security engineers**
- Review the cryptographic implementation (HMAC, DH key exchange, token binding)
- Threat model review — compare against `docs/threat_model_and_mitigation.md`
- TLS/mTLS implementation for Phase 8

**DevOps / infrastructure engineers**
- ContainerLab topology files for CI
- Kubernetes Helm chart improvements
- Docker Compose multi-controller setup
- GitHub Actions CI pipeline

### Getting Started

```bash
# Read these three documents first
cat docs/PROJECT_OVERVIEW.md
cat docs/architecture.md
cat docs/INDEX.md

# Then set up your environment
pip install -r requirements.txt
pytest tests/ -v
```

Full contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)

Open questions and good first issues: [GitHub Issues](https://github.com/AtlasIris/PDSNO/issues)

Community standards and support:

- Code of Conduct: [.github/CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Support channels: [SUPPORT.md](SUPPORT.md)

### Architecture Principles (Read Before Contributing)

Three rules that govern every contribution:

1. **State lives in the NIB.** No controller trusts local memory for network facts. All reads and writes go through `NIBStore`.
2. **Every action is auditable.** No change executes without a signed audit trail entry.
3. **Hierarchy for governance, not performance.** The three-tier model exists for chain-of-authority, not speed. We accept the latency cost.

If your contribution violates any of these, it will need to be rethought regardless of how well it works technically.

---

## Documentation

| Document | What It Covers |
|----------|---------------|
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Architecture foundations and design decisions |
| [docs/architecture.md](docs/architecture.md) | System layers, controller matrix, key decisions |
| [docs/nib_spec.md](docs/nib_spec.md) | NIB schema, consistency model, write protocol |
| [docs/communication_model.md](docs/communication_model.md) | REST/MQTT split, message envelope, auth |
| [docs/algorithm_lifecycle.md](docs/algorithm_lifecycle.md) | The initialize/execute/finalize pattern |
| [docs/pdsno_gap_analysis.md](docs/pdsno_gap_analysis.md) | Competitive analysis vs Cisco ACI, VMware NSX, Juniper Apstra |
| [docs/threat_model_and_mitigation.md](docs/threat_model_and_mitigation.md) | Security threat scenarios and mitigations |
| [docs/api_reference.md](docs/api_reference.md) | All inter-controller message types and payloads |
| [docs/use_cases.md](docs/use_cases.md) | Seven end-to-end scenarios traced through the system |
| [docs/ROADMAP_AND_TODO.md](docs/ROADMAP_AND_TODO.md) | Full phased development plan with open questions |
| [docs/DOCS_PORTAL_MAP.md](docs/DOCS_PORTAL_MAP.md) | Deep documentation-site navigation blueprint |
| [docs/INDEX.md](docs/INDEX.md) | Complete documentation map and reading order |

---

Historical and internal working documents are preserved under
`docs/not_for_github/` to keep the repository root and public docs clean.

---

## Research Foundation

PDSNO's architecture is grounded in published SDN research:

- **Koponen et al. — Onix (OSDI 2010):** The NIB concept. Controllers read/write shared state rather than communicating directly. PDSNO independently arrived at the same design before encountering this paper.
- **ONF TR-521 SDN Architecture:** Standardised interface naming (NBI, SBI, East/West). PDSNO follows these conventions throughout.
- **Alsheikh et al. — Distributed SDN Management (ARO 2024):** Adaptive consistency model. Justification for the REST + MQTT protocol split.
- **DISCO (Phemius et al.):** Delta-sync principle. Controllers exchange only what changed, never full state dumps.
- **Self-Organizing Network principles:** Self-Configuration (discovery), Self-Optimization (congestion), Self-Healing (rollback) map directly to PDSNO's algorithm modules.

---

## License

PDSNO is licensed under the **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**.

This means: you can use, study, modify, and distribute PDSNO freely. If you use PDSNO in a networked product or service, your modifications must also be released under AGPL-3.0. This protects the project from being absorbed into proprietary products without contributing back.

See [LICENSE](LICENSE) for the full text.

---

## Project Status

PDSNO is the technical foundation of **TENKEI** (天系 — Celestial System), a company being built around open-source enterprise network orchestration.

The codebase is the result of deliberate, research-backed architectural work. The hierarchy, the NIB design, the consistency model, the security primitives — none of these are accidents or placeholders. They are documented decisions with explicit tradeoffs.

If you're a network engineer frustrated with vendor lock-in, a distributed systems developer looking for a serious Python infrastructure project, or a security engineer who wants to review real cryptographic governance code — this project is worth your time.

---

*Built on research-backed SDN architecture. Grounded in real enterprise pain.*