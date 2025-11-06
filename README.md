
# PDSNO — Partially Distributed Smart Network Orchestrator

> **An intelligent, modular, and scalable orchestration framework for distributed networks.**
> Designed to unify global, regional, and local control — making modern networks adaptive, efficient, and self-optimizing.

![Status](https://img.shields.io/badge/Status-Design%20%26%20Architecture%20Phase-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Primary%20Language-Python%20(Prototype)-yellow)
![Architecture](https://img.shields.io/badge/Architecture-Hierarchical%20%7C%20Distributed-orange)
![Polyglot](https://img.shields.io/badge/Design-Language%20Agnostic-lightgrey)


---

## What Problem It Solves

Modern networks are increasingly **complex**, **dynamic**, and **geographically distributed**, making it difficult to manage performance, policies, and automation at scale.
Traditional orchestrators are often **monolithic**, **vendor-locked**, or **lacking adaptive intelligence**.

**PDSNO** aims to solve this by introducing a **hierarchical distributed orchestration model** that blends intelligence and modularity — allowing administrators to manage, monitor, and optimize networks in real time without losing control or visibility.

---

## Network Orchestration Use Cases

PDSNO is designed to serve as a **next-generation orchestration system**, handling challenges across enterprise and ISP environments, including:

*  **Dynamic Device Discovery** — Detects new, disconnected, or rogue devices in real time.
*  **Congestion Detection & Response** — Identifies traffic bottlenecks and automatically reroutes flows.
*  **Policy Enforcement & Optimization** — Ensures consistent rules across distributed controllers.
*  **Multi-Domain Coordination** — Synchronizes operations across different network zones or data centers.
*  **Event-Driven Automation** — Responds intelligently to topology or performance changes as they occur.

---

##  High-Level Architecture

PDSNO’s architecture follows a **hierarchical distributed control model**, enabling both centralized intelligence and localized decision-making:

### 🔹 Controllers

| Layer                   | Responsibility                                                                | Example Tasks                              |
| :---------------------- | :---------------------------------------------------------------------------- | :----------------------------------------- |
| **Global Controller**   | High-level orchestration, cross-region optimization, and policy distribution. | Global policy sync, telemetry aggregation. |
| **Regional Controller** | Zone-specific optimization and performance tuning.                            | Load balancing, zone-level analytics.      |
| **Local Controller**    | Device-level control and low-latency responses.                               | Interface monitoring, fast rerouting.      |

### 🔹 Internal Layers

Each controller includes four main layers:

* **Application Layer** → Implements discovery, optimization, and orchestration logic.
* **Communication Layer** → Handles messaging (e.g., REST, MQTT) between controllers.
* **Decision Layer** → Runs analytics, decision-making, and rule evaluation.
* **Data Layer** → Manages lightweight storage (e.g., SQLite) for metadata and device info.

### 🔹 Data & Control Flow

* **Upstream:** Local → Regional → Global (for telemetry and insights).
* **Downstream:** Global → Regional → Local (for decisions, updates, and control actions).

---

## Future Scalability Goals

PDSNO is being designed with **enterprise-grade scalability** in mind.
The roadmap includes:

* **Microservices Transition** — Decouple components for modular deployment and updates.
* **Cloud-Native Compatibility** — Support Kubernetes, Docker, and CI/CD orchestration.
* **AI-Driven Decision Layer** — Leverage ML models for predictive analytics and proactive control.
* **Extensible Plugin Framework** — Enable vendor-agnostic integrations and third-party extensions.
* **Multi-Tenant & Multi-Domain Support** — Support ISPs and large organizations with federated control.

---

## Project Roadmap

PDSNO is in its **Design & Architecture** phase.  
The project is being developed iteratively, starting with a Python-based proof of concept before transitioning to a scalable, multi-language orchestration framework.

Below is a high-level overview of the planned directions and system evolution:

| **Theme** | **Focus Areas** |
|------------|----------------|
|  **Architecture Evolution** | Gradual transition to a microservices model, refined controller hierarchy (Global–Regional–Local), and event-driven orchestration. |
| **Intelligent Orchestration** | Integrate AI/ML-based decision systems, adaptive device discovery, and predictive congestion management. |
| **Automation & Integration** | Deep Ansible integration, plugin-based architecture, and vendor-agnostic interoperability APIs. |
| **Security & Access Control** | Role-based access (RBAC), secure controller communication, and organization-specific onboarding. |
| **Cloud-Native Scalability** | Full support for Kubernetes/Docker, hybrid cloud/edge deployment, and polyglot service design. |
| **Data & Observability** | Enhanced telemetry, lightweight data storage (SQLite → Redis/Postgres), and structured audit logging. |
| **Enterprise & Multi-Domain Readiness** | Multi-tenant orchestration, NMS/OSS compatibility, and a sandboxed simulation environment. |

> A detailed version of this roadmap is available in [`/docs/roadmap.md`](docs/roadmap.md).

---

## Current Focus

> PDSNO is currently in the **Architecture Design & Proof-of-Concept Phase**.
> Core focus areas include:
>
> * Defining architecture and communication models.
> * Implementing discovery modules.
> * Developing controller communication interfaces.
> * Establishing YAML-based configuration and logging systems.

---