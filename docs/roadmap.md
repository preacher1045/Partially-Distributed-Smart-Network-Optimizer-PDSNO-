# 🗺️ PDSNO Detailed Roadmap

This document outlines the long-term development vision for **PDSNO (Partially Distributed Smart Network Orchestrator)** — a next-generation, intelligent, and partially distributed orchestration system.

---

## ⚙️ Current Phase: Design & Architecture (Proof of Concept in Python)
- Defining hierarchical controller logic (Global, Regional, Local)
- Designing discovery engine and communication interfaces
- Implementing YAML-based configuration and logging system
- Building modular folder structure and initial system diagrams
- Creating architectural documentation and onboarding structure

---

## 🚀 Planned Development Directions

| **Category** | **Planned Goal / Direction** | **Purpose / Benefit** |
|---------------|-----------------------------|------------------------|
| **Architecture Evolution** | Transition to **microservices** | Independent scaling and fault isolation between system components. |
|  | Strengthen **hierarchical controller communication** | Improve synchronization, reduce redundancy, handle policy conflicts. |
|  | Adopt **event-driven architecture (EDA)** | Enable asynchronous updates and responsive orchestration logic. |
|**Polyglot Design** | Use **different languages** for different modules (Python → prototype; Go/Rust → performance-critical; Node.js → APIs). | Maximizes performance and flexibility. |
|**Cloud-Native Support** | Adapt PDSNO for **Kubernetes** and **Docker**. | Simplifies deployment across on-premise, edge, and cloud environments. |
|**AI/ML Decision Layer** | Integrate **machine learning** to predict congestion, optimize routing, and detect anomalies. | Moves orchestration from reactive → predictive. |
|**Plugin-Based Framework** | Develop an **extension system** for vendor or third-party integrations. | Makes PDSNO vendor-agnostic and extensible. |
|**Adaptive Discovery Engine** | Implement **dynamic intervals** and **on-demand triggers**. | Improves performance and responsiveness during network changes. |
|**Data Layer Optimization** | Move from SQLite → Redis/Postgres. | Ensures scalable and fast data operations. |
|**Access & Security** | Implement **role-based access control (RBAC)** and API tokens. | Guarantees only authorized administrators perform orchestration tasks. |
| **Multi-Tenant & Multi-Domain Support** | Build systems for **ISPs and large enterprises** managing isolated domains. | Scales orchestration to multiple clients or organizational structures. |
| **Automation (Ansible)** | Deepen integration with **Ansible playbooks** and **YAML configs**. | Simplifies automated network reconfiguration and management. |
|  **Monitoring & Logging** | Implement structured **telemetry**, **audit logs**, and **visual dashboards**. | Improves insight and operational traceability. |
| **Simulation / Sandbox Mode** | Create a **test environment** for orchestration logic. | Enables validation and safe experimentation. |

---

## Long-Term Research & Innovation Goals
- Explore **AI-driven closed-loop orchestration**
- Develop **intent-based networking models**
- Implement **federated orchestration** for large, distributed infrastructures
- Contribute to **open-source standards** in distributed SDN/NFV orchestration

---

## Status Summary
| **Stage** | **Description** |
|------------|----------------|
| Phase 1 | Design & Proof of Concept (Python core, documentation, base modules) |
| Phase 2 | Controller refinement, discovery automation, and communication pipeline |
| Phase 3 | Modular microservice transition and cloud-native adaptation |
| Phase 4 | AI/ML integration and predictive orchestration |
| Phase 5 | Multi-domain orchestration, enterprise-grade deployment, and open-source release |

---

_Last updated: October 2025_
