# PDSNO — Partial Distributed Software-Defined Network Orchestrator

## Overview

**PDSNO** is a **partially decentralized network orchestration system**, inspired by **Software-Defined Networking (SDN)** principles.
It aims to deliver **intelligent, scalable, and resilient network management** through distributed control and automation.

The project serves as the **proof-of-concept** and foundation for the upcoming **DSNO** (Distributed SDN Orchestrator) framework.

---

## Core Objectives

* Reduce **reliance on centralized controllers**.
* Enable **programmable, intelligent orchestration** across network layers.
* Improve **resilience, scalability, and fault tolerance**.
* Automate **network management tasks** using **Python** and **Ansible**.
* Serve as a flexible, **multi-language framework** in the future.

---

## Architectural Model

PDSNO is structured around **four primary layers**, each serving a distinct function in the orchestration pipeline:

| Layer                   | Purpose                                                      |
| ----------------------- | ------------------------------------------------------------ |
| **Decision Layer**      | Handles logic, orchestration decisions, and policy control.  |
| **Communication Layer** | Manages inter-controller messaging and data synchronization. |
| **Data Layer**          | Stores dynamic context, metadata, and state information.     |
| **Application Layer**   | Provides APIs, automation tools, and user-facing interfaces. |

The system uses a **hybrid architecture** that combines:

* **Layered Architecture** → for structure and clarity.
* **Event-Driven Architecture** → for responsiveness and modularity.
* **Microservice Architecture** → for scalability and independent component evolution.

---

## 🧠 Controller Hierarchy

PDSNO operates using **a multi-tier controller model**, allowing distributed intelligence across the network:

| Controller Type         | Function                                                                                 | Example                               |
| ----------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------- |
| **Global Controller**   | High-level coordination, global policy enforcement, and validation of other controllers. | `global_cntl_1`, `global_cntl_2`      |
| **Regional Controller** | Manages network domains or geographic zones. Reports to a global controller.             | `regional_cntl_1` → `regional_cntl_5` |
| **Local Controller**    | Handles direct device orchestration and rapid event response.                            | `local_cntl_1` → `local_cntl_9`       |

Controllers are validated before joining the system through a **token or key-based mechanism**, ensuring only authorized components can participate.

---

## Controller Validation Process

| Step                  | Description                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------ |
| **1. Request**        | A new controller (regional/local) sends a validation request to a higher-level controller. |
| **2. Authentication** | The request includes a **secure token or key** for verification.                           |
| **3. Verification**   | The global controller validates the token and approves the controller.                     |
| **4. Assignment**     | Role and permissions are dynamically assigned and logged in `context.yaml`.                |
| **5. Propagation**    | The system updates the orchestration state across the hierarchy.                           |

### 🔸 Key Principles

* Prevent unauthorized controllers from entering the system.
* Support concurrent validation through a **validation queue**.
* Use **asynchronous context updates** for efficiency and safety.
* Future-ready for **certificate or blockchain-based trust models**.

---

## ⚙️ Algorithm Framework

Every major subsystem (discovery, validation, policy execution, etc.) follows a unified algorithm pattern for consistency and modularity.

```python
class BaseClass:
    def initialize(self, context): ...
    def execute(self, data): ...
    def finalize(self): ...
```

| Method           | Function                                                               |
| ---------------- | ---------------------------------------------------------------------- |
| **initialize()** | Loads context, validates configurations, and prepares the module.      |
| **execute()**    | Runs the module’s specialized task (e.g., discovery or orchestration). |
| **finalize()**   | Handles cleanup, logs, and result returns.                             |

This ensures that **each module “speaks the same internal language”**, simplifying maintenance, updates, and testing.

---

## Dynamic Context Management

All system configurations and orchestration states are managed dynamically through `context.yaml`.

### Example (actual field implementations may differ):

```yaml
system:
  id: auto_generated
  name: auto_assigned
  role: auto_determined
  status: initializing
controllers:
  global:
    total: 2
    primary: global_cntl_1
    secondary: global_cntl_2
  regional:
    total: 5
  local:
    total: 9
validation_queue: []
```

### Managed By:

`context_manager.py` — ensures **safe and atomic updates** to context data, preventing race conditions in distributed environments.

---

## 🌐 Network Discovery (Planned Module)

The **discovery engine** identifies and tracks network devices using multiple protocols:

| Protocol      | File           | Description                                  |
| ------------- | -------------- | -------------------------------------------- |
| **ARP Scan**  | `arp_scan.py`  | Local subnet device detection.               |
| **ICMP Ping** | `icmp_ping.py` | Active reachability testing.                 |
| **SNMP**      | `snmp.py`      | Device information gathering and monitoring. |

Each discovery method will run asynchronously, enabling **parallel multi-device scanning** and dynamic context updates.

---

## 🚀 Future Scalability Goals

| Goal                                    | Description                                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Language Flexibility**                | PDSNO will evolve into a multi-language framework (Python → Go/Rust/C++ for high-performance modules). |
| **Microservice Expansion**              | Each module (discovery, validation, orchestration) becomes an independent service.                     |
| **Advanced Orchestration Intelligence** | Integrate AI/ML for predictive network optimization.                                                   |
| **API Ecosystem**                       | REST and gRPC endpoints for integration with OSS/NMS systems.                                          |
| **Security Enhancements**               | Incorporate certificate-based validation and trust policies.                                           |

---

## 🧭 Current Development Stage

✅ Defined core architecture
✅ Built base algorithm and controller templates
✅ Designed dynamic context and validation structure
✅ Established open-source governance
🟡 Next: Implement controller validation logic
🟡 Next: Prototype discovery algorithm
🟡 Next: Refine documentation and developer onboarding

---

## 🤝 Contributing

We welcome contributions from developers, architects, and researchers who share our vision of scalable, distributed orchestration.

See: [`CONTRIBUTING.md`](../CONTRIBUTING.md)

---

