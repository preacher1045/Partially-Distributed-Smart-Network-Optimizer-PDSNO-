"""
AlgorithmBase — Foundational Lifecycle Pattern

Base interface for all PDSNO algorithms following the three-phase lifecycle:
initialize → execute → finalize

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

from abc import ABC, abstractmethod
from typing import Any, Dict


class AlgorithmBase(ABC):
    """
    Base lifecycle interface for all PDSNO algorithms.
    
    All algorithms must inherit from this class and implement the three required methods.
    """
    
    def __init__(self):
        self._initialized = False
        self._executed = False
    
    @abstractmethod
    def initialize(self, context: Dict[str, Any]) -> None:
        """
        Prepare the algorithm for execution.
        
        Store all necessary state as instance variables. execute() will use this state.

        Args:
            context: A dictionary containing all inputs the algorithm needs.
                    Controllers are responsible for assembling this from the
                    NIB, context_runtime.yaml, and any runtime parameters.

        Raises:
            ValueError: If required context fields are missing or invalid.
            RuntimeError: If required resources cannot be allocated.
        """

    @abstractmethod
    def execute(self) -> Any:
        """
        Run the algorithm's core logic.

        Uses state stored during initialize(). Does not accept parameters —
        all inputs must be loaded in initialize().

        Returns:
            Algorithm-specific output. Each subclass documents its return type.

        Raises:
            RuntimeError: If execute() is called before initialize().
        """
        if not self._initialized:
            raise RuntimeError("initialize() must be called before execute()")

    @abstractmethod
    def finalize(self) -> Dict[str, Any]:
        """
        Clean up resources and return the result payload.
        
        Returns:
            A dictionary with at minimum:
            {
                "status": "complete" | "failed" | "partial",
                "timestamp": ISO-8601 string,
                "result": <algorithm-specific data>
            }
        
        Raises:
            RuntimeError: If finalize() is called before execute().
        """
        if not self._executed:
            raise RuntimeError("execute() must be called before finalize()")


# Legacy alias for backwards compatibility
BaseClass = AlgorithmBase

