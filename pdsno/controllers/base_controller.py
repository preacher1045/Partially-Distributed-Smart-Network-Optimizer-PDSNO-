"""
BaseController — Foundation for all PDSNO Controllers

Provides common functionality for Global, Regional, and Local controllers.
Implements the algorithm lifecycle execution and context management.
"""

from typing import Type, Dict, Any, Optional
from datetime import datetime, timezone

from ..core.base_class import AlgorithmBase
from ..logging.logger import get_logger
from .context_manager import ContextManager


class BaseController:
    """
    Base controller implementing common functionality for all controller tiers.
    
    Design notes:
    - Controllers are stateless with respect to network knowledge.
      All network state is read from the NIB.
    - Controllers inject dependencies (ContextManager, NIBStore) rather
      than creating them internally. This enables testing and flexibility.
    - The algorithm lifecycle (initialize → execute → finalize) is managed
      by run_algorithm(), ensuring consistent execution across all algorithms.
    """
    
    def __init__(
        self,
        controller_id: str,
        role: str,
        context_manager: ContextManager,
        region: Optional[str] = None
    ):
        """
        Initialize base controller.
        
        Args:
            controller_id: Unique identifier for this controller
            role: Controller role ("global", "regional", "local")
            context_manager: Shared context manager instance
            region: Optional region identifier (required for regional/local)
        """
        self.controller_id = controller_id
        self.role = role
        self.region = region
        self.context_manager = context_manager
        
        # Initialize logger with controller ID
        self.logger = get_logger(__name__, controller_id=controller_id)
        
        self.logger.info(
            f"{role.capitalize()} controller initialized",
            extra={'extra_fields': {'region': region}}
        )
    
    def load_algorithm(self, algorithm_class: Type[AlgorithmBase]) -> AlgorithmBase:
        """
        Instantiate an algorithm.
        
        Args:
            algorithm_class: Algorithm class (must inherit from AlgorithmBase)
        
        Returns:
            Fresh algorithm instance
        
        Raises:
            TypeError: If algorithm_class doesn't inherit from AlgorithmBase
        """
        if not issubclass(algorithm_class, AlgorithmBase):
            raise TypeError(
                f"{algorithm_class.__name__} must inherit from AlgorithmBase"
            )
        
        self.logger.info(f"Loading algorithm: {algorithm_class.__name__}")
        return algorithm_class()
    
    def run_algorithm(
        self,
        algorithm: AlgorithmBase,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an algorithm through its full lifecycle.
        
        Runs: initialize(context) → execute() → finalize()
        Logs each phase and returns the result payload.
        
        Args:
            algorithm: Algorithm instance to run
            context: Context dictionary passed to initialize()
        
        Returns:
            Result payload from finalize()
        
        Raises:
            RuntimeError: If any lifecycle phase fails
        """
        algorithm_name = algorithm.__class__.__name__
        
        try:
            # Phase 1: Initialize
            self.logger.info(
                f"Initializing algorithm: {algorithm_name}",
                extra={'extra_fields': {'phase': 'initialize'}}
            )
            algorithm.initialize(context)
            algorithm._initialized = True
            
            # Phase 2: Execute
            self.logger.info(
                f"Executing algorithm: {algorithm_name}",
                extra={'extra_fields': {'phase': 'execute'}}
            )
            result = algorithm.execute()
            algorithm._executed = True
            
            # Phase 3: Finalize
            self.logger.info(
                f"Finalizing algorithm: {algorithm_name}",
                extra={'extra_fields': {'phase': 'finalize'}}
            )
            payload = algorithm.finalize()
            
            self.logger.info(
                f"Algorithm completed: {algorithm_name}",
                extra={'extra_fields': {
                    'status': payload.get('status'),
                    'phase': 'complete'
                }}
            )
            
            return payload
            
        except Exception as e:
            self.logger.error(
                f"Algorithm failed: {algorithm_name}",
                extra={'extra_fields': {'error': str(e)}},
                exc_info=True
            )
            
            # Return a standardized error payload
            return {
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "algorithm": algorithm_name
            }
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get a value from runtime context.
        
        Args:
            key: Context key
            default: Default value if key not found
        
        Returns:
            Context value or default
        """
        return self.context_manager.get(key, default)
    
    def set_context(self, key: str, value: Any) -> None:
        """
        Set a value in runtime context.
        
        Args:
            key: Context key
            value: Value to set
        """
        self.context_manager.set(key, value)
    
    def update_context(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple context values.
        
        Args:
            updates: Dictionary of key-value pairs to update
        """
        self.context_manager.update(updates)
    
    def receive_message(self, message):
        """
        Handle incoming message.
        
        Subclasses should override this to implement message handling logic.
        
        Args:
            message: Incoming message to process
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement receive_message()"
        )
    
    def send_message(self, target, message):
        """
        Send message to another controller.
        
        Subclasses should override this to implement message sending logic.
        
        Args:
            target: Target controller identifier
            message: Message to send
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement send_message()"
        )