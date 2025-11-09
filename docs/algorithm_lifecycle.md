## Algorithm Lifecycle Pattern (Core Design Principle)

The **Algorithm Lifecycle Pattern** defines how all PDSNO algorithms from device discovery to congestion handling are structured and executed within the orchestration system.
It ensures consistency, modularity, and maintainability across all layers of PDSNO (local, regional, global).

---

### **Lifecycle Overview**

Every algorithm in PDSNO follows a three-phase lifecycle:

| Phase             | Purpose                                      | Typical Actions                                                                                           |
| ----------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **1. Initialize** | Prepare the environment and input            | Validate parameters, load configurations, fetch data, allocate temporary resources                        |
| **2. Execute**    | Perform the core logic of the algorithm      | Run computations, analyze network metrics, make optimization decisions, communicate with other components |
| **3. Finalize**   | Wrap up, clean resources, and return results | Store outputs, release resources, log performance data, trigger follow-up actions                         |

---

### **Interface Design (Base Class)**

All algorithms/domains inherit from a shared base interface that defines this lifecycle:

```python
# A domain is a function that inheretes from the base class and is implemented in a controller
```

```python
# algorithm_base.py

class AlgorithmBase:
    """Defines the base lifecycle for all algorithms in PDSNO."""

    def initialize(self, context):
        """Prepare environment and validate inputs."""
        raise NotImplementedError

    def execute(self):
        """Run core logic. Must be implemented by each derived algorithm/domian."""
        raise NotImplementedError

    def finalize(self):
        """Perform cleanup and return output data."""
        raise NotImplementedError
```
---
### **Algorithm Lifecycle (Flow Overview)**
          +-------------------------+
          |     CONTROLLER LAYER    |
          |-------------------------|
          | Loads algorithm module  |
          | Passes context data     |
          +-----------+-------------+
                      |
                      v
          +-------------------------+
          |   AlgorithmBase Class   |
          +-------------------------+
          |   initialize()          |   -->  Prepare: validate inputs,
          |                         |        load configs, allocate resources
          +-----------+-------------+
                      |
                      v
          +-------------------------+
          |     execute()           |   -->  Core Logic:
          |                         |        analyze data, make decisions,
          |                         |        run computations
          +-----------+-------------+
                      |
                      v
          +-------------------------+
          |     finalize()          |   -->  Cleanup: store results,
          |                         |        free memory, return outputs
          +-----------+-------------+
                      |
                      v
          +-------------------------+
          | Controller receives     |
          | output & triggers next  |
          | orchestration action    |
          +-------------------------+

### Flow Summary

**Controller** → Initialize: Sends context (network data, parameters, configs).

**Algorithm** → Execute: Performs its primary logic and returns results.

**Algorithm** → Finalize: Cleans up and hands results back.

**Controller** → Next Step: Uses results for policy decisions or orchestration actions.

---

---

#### **Example Implementation**

```python
# congestion_algorithm.py
from PDSNO.Base.base_class import Base

class CongestionMitigationAlgorithm(AlgorithmBase):
    def initialize(self, context):
        self.network_data = context.get("network_data", {})
        self.threshold = context.get("threshold", 80)
        print("Initialized congestion monitor.")

    def execute(self):
        overloaded_links = [
            link for link, usage in self.network_data.items() if usage > self.threshold
        ]
        print(f"Detected overloaded links: {overloaded_links}")
        return overloaded_links

    def finalize(self):
        print("Finalizing congestion mitigation process.")
        return {"status": "complete", "timestamp": "2025-10-18"}
```

---

### **Benefits**

* **Consistency:** Every algorithm has a predictable structure.
* **Scalability:** Supports orchestration across distributed controllers.
* **Language-agnostic:** Easily portable to Go, Rust, or C++ later.
* **Ease of onboarding:** New contributors can quickly understand and extend system logic.

---

### **Integration with PDSNO Controllers**

Each controller (Local, Regional, Global) can load, execute, and monitor algorithms dynamically:

#### **Example Implementation**
```python
controller.load_algorithm(CongestionMitigationAlgorithm)
controller.run_algorithm(context={"network_data": data})
```

This separation of lifecycle phases allows the controllers to schedule, audit, and rollback algorithms independently which is a key feature for distributed orchestration systems.

---
