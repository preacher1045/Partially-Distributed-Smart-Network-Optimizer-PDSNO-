---
title: Documentation Index
status: Active — Updated as docs are added
last_updated: 2026-02-14
---

# PDSNO — Documentation Index

This index maps every document in the project to its purpose and recommended reading order. Start here if you are new to the project.

---

## Recommended Reading Order

If you are new to PDSNO, read documents in this order:

1. `README.md` — Project summary, what problem it solves, current status
2. `docs/PROJECT_OVERVIEW.md` — Architecture foundations, design decisions, interface naming
3. `docs/architecture/architecture.md` — System layers, controller matrix, key decisions
4. `docs/algorithm_lifecycle.md` — The core pattern every module follows
5. `docs/architecture/nib/nib_spec.md` — The data layer everything depends on
6. `docs/architecture/communication_model.md` — How controllers communicate
7. `docs/architecture/verification/controller_validation_sequence.md` — How controllers join the network
8. `docs/architecture/approval_logic/config_approval_logic.md` — How configuration changes are governed
9. `docs/architecture/device_discovery/device_discovery_sequence.md` — How devices are discovered
10. `docs/security_model.md` — Security properties and threat summary
11. `docs/use_cases.md` — Concrete scenarios end-to-end
12. `ROADMAP_AND_TODO.md` — What is being built next and why

---

## Document Map

### Root Level

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Project introduction, use cases, architecture summary | ✅ Active |
| `ROADMAP_AND_TODO.md` | Master development roadmap and task tracker | ✅ Active |
| `CONTRIBUTING.md` | How to contribute, coding standards, PR process | ✅ Active |

### `/docs`

| File | Purpose | Status |
|------|---------|--------|
| `PROJECT_OVERVIEW.md` | Full architectural overview with design rationale | ✅ Active |
| `algorithm_lifecycle.md` | Algorithm base class pattern and implementation guide | ✅ Active |
| `roadmap.md` | High-level roadmap summary (see ROADMAP_AND_TODO.md for full version) | ✅ Active |
| `architecture.md` | System architecture — layers, controller matrix, key decisions | ✅ Active |
| `security_model.md` | Security properties, trust boundaries, threat summary by component | ✅ Active |
| `dataflow.md` | End-to-end data flow for discovery, approval, and policy distribution | ✅ Active |
| `api_reference.md` | All inter-controller message types, payloads, NBI endpoints | ✅ Active |
| `deployment_guide.md` | Dev setup, context_runtime.yaml reference, scaling guidelines | ✅ Active |
| `use_cases.md` | 7 scenarios traced step-by-step — discovery, approval, emergency, validation | ✅ Active |
| `contibution-rules.md` | Architecture review rules for contributors | ✅ Active |

### `/docs/architecture`

| File | Purpose | Status |
|------|---------|--------|
| `communication_model.md` | Protocol assignment (REST/MQTT), delta-sync principle, message envelope, auth, timeouts | ✅ Active |
| `controller_hierarchy.md` | Controller tiers, offline behaviour, naming convention, scaling guidelines | ✅ Active |

### `/docs/architecture/verification`

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Module overview for the verification component | ✅ Active |
| `controller_validation_sequence.md` | Full verification flow design, pseudocode, and error states | ✅ Active |
| `controller_verification_sequence.drawio` | Sequence diagram source file | ✅ Active |
| `key_management.md` | Key generation, distribution, rotation, revocation (HMAC→Ed25519 path) | ⚪ Pending |

### `/docs/architecture/approval_logic`

| File | Purpose | Status |
|------|---------|--------|
| `config_approval_doc.md` | Canonical approval logic specification (JSON schemas, timeouts, retry logic) | ✅ Active |
| `config_approval_logic.md` | Pseudocode / algorithm reference for the approval flow | ✅ Active |
| `config_approval_sequence.drawio` | Sequence diagram source file | ✅ Active |

### `/docs/architecture/policy_propagation`

| File | Purpose | Status |
|------|---------|--------|
| `policy_propagation_doc.md` | Design summary of the configuration approval system | ✅ Active |
| `threat_model_and_mitigation.md` | Security threats and design-level mitigations | ✅ Active |

### `/docs/architecture/nib`

| File | Purpose | Status |
|------|---------|--------|
| `nib_spec.md` | NIB schema, two-tier data classification, adaptive consistency model, typed entity hierarchy, access interface, write protocol, retention | ✅ Active — Research updated |
| `nib_consistency.md` | Deep-dive: optimistic locking (PoC), adaptive consistency target (Phase 6+) | ✅ Active |

### `/docs/architecture/device_discovery`

| File | Purpose | Status |
|------|---------|--------|
| `device_discovery_sequence.md` | Discovery flow design and NIB integration | 🟡 Needs Rewrite |
| `device_discovery_sequence.drawio` | Sequence diagram source file | ✅ Active |

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ Active | Current, reviewed, reliable |
| 🟡 Needs Rewrite | Exists but needs significant cleanup or expansion |
| ⚪ Pending | Does not yet exist — tracked in ROADMAP_AND_TODO.md |
