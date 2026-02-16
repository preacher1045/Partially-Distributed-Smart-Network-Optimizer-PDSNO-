"""
Example: Basic Algorithm Usage

Demonstrates how to create and run a simple algorithm using PDSNO's base classes.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PDSNO.core.base_class import AlgorithmBase
from PDSNO.controllers.base_controller import BaseController
from PDSNO.controllers.context_manager import ContextManager


class HelloWorldAlgorithm(AlgorithmBase):
    """
    A simple example algorithm that demonstrates the three-phase lifecycle.
    """
    
    def initialize(self, context):
        """Load configuration from context"""
        self.message = context.get('message', 'Hello, PDSNO!')
        self.repeat_count = context.get('repeat', 1)
        self._initialized = True
        print(f"[Initialize] Message: {self.message}, Repeat: {self.repeat_count}")
    
    def execute(self):
        """Run the algorithm logic"""
        super().execute()  # Checks that initialize was called
        self.results = []
        for i in range(self.repeat_count):
            self.results.append(f"{i+1}. {self.message}")
        self._executed = True
        print(f"[Execute] Generated {len(self.results)} messages")
        return self.results
    
    def finalize(self):
        """Clean up and return results"""
        super().finalize()  # Checks that execute was called
        print(f"[Finalize] Returning {len(self.results)} results")
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": self.results,
            "message_count": len(self.results)
        }


def main():
    print("="*60)
    print("PDSNO Example: Basic Algorithm Usage")
    print("="*60)
    print()
    
    # 1. Create a context manager
    print("1. Creating ContextManager...")
    context_mgr = ContextManager("config/example_context.yaml")
    
    # 2. Create a controller
    print("2. Creating BaseController...")
    controller = BaseController(
        controller_id="example_controller_1",
        role="local",
        context_manager=context_mgr,
        region="example-zone"
    )
    
    # 3. Load an algorithm
    print("3. Loading HelloWorldAlgorithm...")
    algorithm = controller.load_algorithm(HelloWorldAlgorithm)
    
    # 4. Prepare context for the algorithm
    print("4. Preparing algorithm context...")
    algo_context = {
        'message': 'PDSNO is working!',
        'repeat': 3
    }
    
    # 5. Run the algorithm through its full lifecycle
    print("5. Running algorithm lifecycle...\n")
    result = controller.run_algorithm(algorithm, algo_context)
    
    # 6. Display results
    print("\n" + "="*60)
    print("Algorithm Results:")
    print("="*60)
    print(f"Status: {result['status']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Message Count: {result['message_count']}")
    print("\nMessages:")
    for msg in result['result']:
        print(f"  {msg}")
    print("="*60)
    print("\n✓ Example completed successfully!")


if __name__ == "__main__":
    main()
