
# PDSNO — Partially Distributed Software-Defined Network Orchestrator

> **An intelligent, modular, and scalable orchestration framework for distributed networks.**
> Designed to unify global, regional, and local control — making modern networks adaptive, efficient, and self-optimizing.

![Status](https://img.shields.io/badge/Status-Foundation%20Complete-brightgreen)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Architecture](https://img.shields.io/badge/Architecture-Hierarchical%20%7C%20Distributed-orange)
![Tests](https://img.shields.io/badge/Tests-Passing-success)

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main entry point
python PDSNO/main.py

# Try the examples
python examples/basic_algorithm_usage.py
python examples/nib_store_usage.py

# Run tests
python -m pytest
```

**📖 New to PDSNO?** Start with [QUICK_START.md](QUICK_START.md) for detailed setup instructions.

**📋 Recent Updates?** See [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md) for what's new.

---

## ✅ Implemented Features

**Current Phase:** Foundation Complete (Phases 1-3 from [ROADMAP](docs/ROADMAP_AND_TODO.md))

### Core Framework
- ✅ **AlgorithmBase** - Three-phase lifecycle pattern (initialize → execute → finalize)
- ✅ **BaseController** - Controller orchestration with context management
- ✅ **ContextManager** - Thread-safe YAML configuration with atomic writes
- ✅ **Structured Logging** - JSON-formatted logs with controller IDs

### Data Layer (NIB)
- ✅ **NIBStore** - SQLite-backed Network Information Base
- ✅ **Data Models** - Device, Config, Policy, Event, Lock, Controller entities
- ✅ **Optimistic Locking** - Version-based conflict detection for concurrent writes
- ✅ **Event Log** - Immutable audit trail with HMAC signatures
- ✅ **Coordination Locks** - Distributed lock mechanism with TTL

### Communication Layer
- ✅ **Message Formats** - Standard message envelope and type system
- ✅ **REST Client** - HTTP-based controller-to-controller messaging
- ✅ **Message Types** - Validation, Discovery, Config, Policy messages

### Development Infrastructure
- ✅ **Test Suite** - Pytest-based tests with fixtures
- ✅ **Examples** - Working demonstrations of core features
- ✅ **Documentation** - Comprehensive specs and guides

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

## 📦 Installation

### Prerequisites
- Python 3.11 or higher
- pip package manager

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Partially-Distributed-Smart-Network-Optimizer-PDSNO-
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python PDSNO/main.py
   ```

4. **Run tests:**
   ```bash
   python -m pytest
   ```

See [QUICK_START.md](QUICK_START.md) for detailed instructions and usage examples.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [QUICK_START.md](QUICK_START.md) | Installation and basic usage guide |
| [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md) | Recent changes and implementation details |
| [docs/INDEX.md](docs/INDEX.md) | Complete documentation index |
| [docs/ROADMAP_AND_TODO.md](docs/ROADMAP_AND_TODO.md) | Development roadmap and phases |
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Architecture overview |
| [docs/algorithm_lifecycle.md](docs/algorithm_lifecycle.md) | Algorithm design pattern |
| [docs/nib_spec.md](docs/nib_spec.md) | Network Information Base specification |
| [docs/api_reference.md](docs/api_reference.md) | Message formats and API contracts |

---

## 💡 Usage Examples

### Creating a Custom Algorithm

```python
from PDSNO.core.base_class import AlgorithmBase
from datetime import datetime, timezone

class MyAlgorithm(AlgorithmBase):
    def initialize(self, context):
        self.data = context.get('input_data', [])
        self._initialized = True
    
    def execute(self):
        super().execute()  # Validates initialization
        self.result = sum(self.data)
        self._executed = True
        return self.result
    
    def finalize(self):
        super().finalize()  # Validates execution
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": self.result
        }
```

### Running with a Controller

```python
from PDSNO.controllers import BaseController, ContextManager

# Setup
context_mgr = ContextManager("config/context_runtime.yaml")
controller = BaseController(
    controller_id="my_controller_1",
    role="local",
    context_manager=context_mgr
)

# Run algorithm
algorithm = MyAlgorithm()
result = controller.run_algorithm(algorithm, {'input_data': [1, 2, 3, 4, 5]})
print(f"Result: {result['result']}")  # Output: 15
```

### Working with the NIB

```python
from PDSNO.datastore import NIBStore, Device, DeviceStatus

# Initialize NIB
nib = NIBStore("config/pdsno.db")

# Create and store device
device = Device(
    device_id="",
    ip_address="192.168.1.100",
    mac_address="AA:BB:CC:DD:EE:FF",
    hostname="switch-1",
    status=DeviceStatus.DISCOVERED
)

result = nib.upsert_device(device)
print(f"Device stored with ID: {result.data}")
```

**More examples:** See the [examples/](examples/) directory for complete working demonstrations.

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_base_classes.py

# Run with coverage report
python -m pytest --cov=PDSNO --cov-report=html
```

---

## 🗺️ Current Status & Roadmap

### ✅ Phase 0-3: Foundation (COMPLETE)
- [x] Documentation architecture complete
- [x] Base classes implemented
- [x] NIB storage layer operational
- [x] Communication layer functional
- [x] Test infrastructure in place

### 🔄 Phase 4: Controller Validation (NEXT)
- [ ] Challenge-response validation flow
- [ ] Global Controller implementation
- [ ] Regional Controller implementation
- [ ] Message bus for controller communication
- [ ] Validation simulation script

### 📋 Phase 5+: Advanced Features (PLANNED)
- [ ] Device discovery module
- [ ] Configuration approval workflow
- [ ] Policy distribution system
- [ ] Integration with real network devices
- [ ] Web dashboard and monitoring

**Full roadmap:** See [docs/ROADMAP_AND_TODO.md](docs/ROADMAP_AND_TODO.md)

---

## Current Focus

> **PDSNO has completed its foundation phase** and is ready for Phase 4 development.
>
> **What's working:**
> - ✅ Complete base framework with algorithms, controllers, and data layer
> - ✅ SQLite-backed NIB with optimistic locking and audit logging
> - ✅ Structured JSON logging and configuration management
> - ✅ Message formats and REST communication layer
> - ✅ Comprehensive test suite and working examples
>
> **Next milestone:** Implement controller validation with challenge-response authentication
>
> **Getting started:** See [QUICK_START.md](QUICK_START.md) for installation and usage

For architectural details: [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md)

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install dependencies: `pip install -r requirements.txt`
4. Make your changes
5. Run tests: `python -m pytest`
6. Submit a pull request

### Code Standards
- Follow the algorithm lifecycle pattern for new algorithms
- Use structured logging via `get_logger()`
- Write tests for new functionality
- Update documentation as needed

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Related Documentation

- [Architecture Decision Records](docs/ROADMAP_AND_TODO.md#phase-0--documentation-completion--architecture-hardening)
- [Security Model](docs/threat_model_and_mitigation.md)
- [Communication Model](docs/communication_model.md)
- [NIB Consistency Model](docs/nib_consistency.md)
- [Vendor Gap Analysis](docs/pdsno_gap_analysis.md)

---

**Built with research-backed architectural patterns from SDN literature (Onix, ONF TR-521, DISCO)**

