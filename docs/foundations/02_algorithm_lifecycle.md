---
title: Algorithm Lifecycle Pattern
status: Active
author: Alexander Adjei
last_updated: 2026-02-14
component: Core Framework
depends_on: PROJECT_OVERVIEW.md
---

# Algorithm Lifecycle Pattern

## Overview

The **Algorithm Lifecycle Pattern** is the foundational design contract for every operational module in PDSNO. Every algorithm — from device discovery to congestion mitigation to controller validation — inherits from the same base class and follows the same three-phase structure.

This consistency means that controllers can load, execute, monitor, and roll back any algorithm through a single standard interface, regardless of what that algorithm actually does.

---

## The Three Phases

| Phase | Method | Purpose | Key Actions |
|-------|--------|---------|-------------|
| **1. Initialize** | `initialize(context)` | Prepare the algorithm to run | Validate parameters, load configuration, fetch required data, store as instance state |
| **2. Execute** | `execute()` | Run the core logic | Perform computation, analyze data, communicate with other components, make decisions |
| **3. Finalize** | `finalize()` | Clean up and return results | Free resources, write outputs to NIB or context store, log performance data, return result payload |

---

## Base Class Interface

```python
# pdsno/base/algorithm_base.py

class AlgorithmBase:
    """
    Base lifecycle interface for all PDSNO algorithms.

    Design notes:
    - initialize() receives all external data via `context` and stores it as instance
      variables. execute() and finalize() operate on that stored state.
    - This means each AlgorithmBase instance is single-use: initialize → execute → finalize.
      Do not reuse an instance across multiple runs. Controllers are responsible for
      instantiating a fresh object for each execution cycle.
    - Algorithms are NOT thread-safe by default. If a controller runs multiple algorithms
      concurrently, each must run in its own instance. Shared resources (NIB, context store)
      must be accessed through their thread-safe managers, not directly.
    """

    def initialize(self, context: dict) -> None:
        """
        Prepare the algorithm for execution.

        Args:
            context: A dictionary containing all inputs the algorithm needs.
                     Controllers are responsible for assembling this from the
                     NIB, context_runtime.yaml, and any runtime parameters.

        Raises:
            ValueError: If required context fields are missing or invalid.
            RuntimeError: If required resources cannot be allocated.
        """
        raise NotImplementedError

    def execute(self) -> any:
        """
        Run the algorithm's core logic.

        Uses state stored during initialize(). Does not accept parameters —
        all inputs must be loaded in initialize().

        Returns:
            Algorithm-specific output. Each subclass documents its return type.

        Raises:
            RuntimeError: If execute() is called before initialize().
        """
        raise NotImplementedError

    def finalize(self) -> dict:
        """
        Clean up resources and return the result payload.

        Returns:
            A dictionary with at minimum:
            {
                "status": "complete" | "failed" | "partial",
                "timestamp": ISO-8601 string,
                "result": <algorithm-specific data>
            }
        """
        raise NotImplementedError
```

---

## Lifecycle Flow

```
CONTROLLER
    │
    │  Assembles context dict from NIB + runtime config
    │
    ▼
algorithm.initialize(context)
    │
    │  Validates inputs, stores state as instance variables,
    │  allocates any temporary resources
    │
    ▼
algorithm.execute()
    │
    │  Runs core logic using stored instance state.
    │  May communicate with other components.
    │  Returns raw result.
    │
    ▼
algorithm.finalize()
    │
    │  Frees resources, writes to NIB/audit log,
    │  returns standardized result payload.
    │
    ▼
CONTROLLER
    │
    │  Receives result payload, makes orchestration
    │  decisions, triggers next actions.
```

---

## Example Implementation

This example shows a congestion mitigation algorithm following the pattern correctly, including proper state storage and the standardized finalize return format.

```python
# pdsno/algorithms/congestion_mitigation.py

from pdsno.base.algorithm_base import AlgorithmBase
from datetime import datetime, timezone


class CongestionMitigationAlgorithm(AlgorithmBase):
    """
    Identifies overloaded network links and returns a list of affected links
    for the controller to act on.

    Expected context keys:
        network_data (dict): Map of link_id → utilization percentage (0–100)
        threshold (int, optional): Utilization % above which a link is overloaded. Default: 80
    """

    def initialize(self, context: dict) -> None:
        if "network_data" not in context:
            raise ValueError("context must include 'network_data'")

        self.network_data = context["network_data"]
        self.threshold = context.get("threshold", 80)
        self.overloaded_links = []
        self._start_time = datetime.now(timezone.utc)

    def execute(self) -> list:
        self.overloaded_links = [
            link_id
            for link_id, utilization in self.network_data.items()
            if utilization > self.threshold
        ]
        return self.overloaded_links

    def finalize(self) -> dict:
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": {
                "overloaded_links": self.overloaded_links,
                "threshold_used": self.threshold,
                "links_checked": len(self.network_data),
            }
        }
```

---

## How Controllers Use Algorithms

Controllers load and run algorithms through a standardized pattern. The controller is responsible for assembling the context and handling the result.

```python
# Inside a controller method

algorithm = CongestionMitigationAlgorithm()

context = {
    "network_data": self.nib.get_link_utilization(region=self.region),
    "threshold": self.policy.get("congestion_threshold", 80),
}

algorithm.initialize(context)
raw_result = algorithm.execute()
result_payload = algorithm.finalize()

# Controller acts on the result
if result_payload["status"] == "complete":
    for link_id in result_payload["result"]["overloaded_links"]:
        self.trigger_reroute(link_id)
```

---

## Key Rules for Algorithm Implementations

**1. All external data enters through `initialize(context)`.**
Never reach into the NIB, file system, or network inside `execute()` or `finalize()`. This makes algorithms testable in isolation — you can pass any context dict in a test without needing real infrastructure.

**2. One instance, one run.**
Create a new instance for each execution. Do not reset and reuse an instance. The controller handles instantiation.

**3. `execute()` must be idempotent where possible.**
If the controller needs to retry an algorithm, it creates a new instance and runs the full lifecycle again. Algorithms should not produce side effects that make re-running dangerous.

**4. `finalize()` always returns a result dict.**
Even on failure. Use `"status": "failed"` and include an `"error"` key with a description. Never let `finalize()` raise an unhandled exception.

**5. Document your context keys.**
Every algorithm subclass must document exactly which keys it expects in `context`, which are required vs optional, and what the defaults are for optional keys.

---

## Benefits of This Pattern

**Consistency** — Every algorithm has the same structure. A contributor who understands one can understand all of them.

**Testability** — Because all inputs come through `initialize(context)`, any algorithm can be unit-tested by passing a carefully constructed context dict. No mocking of live network infrastructure required.

**Observability** — Controllers can time each phase independently, log which algorithm is running, and detect hangs in `execute()` without special instrumentation per algorithm.

**Portability** — The pattern is simple enough to reimplement in Go, Rust, or any other language when PDSNO moves beyond the Python prototype phase.
