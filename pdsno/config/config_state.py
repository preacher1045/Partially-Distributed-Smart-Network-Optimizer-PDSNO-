"""
Configuration State Machine

Manages configuration lifecycle from draft to execution.

States:
- DRAFT: Being prepared
- PENDING_APPROVAL: Awaiting approval
- APPROVED: Approved, ready for execution
- EXECUTING: Currently being applied
- EXECUTED: Successfully applied
- FAILED: Execution failed
- ROLLED_BACK: Reverted to previous state
- CANCELLED: Request cancelled
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from pdsno.config.approval_engine import ApprovalState


class ConfigState(Enum):
    """Configuration states"""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class ConfigTransition:
    """Represents a state transition"""

    def __init__(
        self,
        from_state: ConfigState,
        to_state: ConfigState,
        timestamp: datetime,
        triggered_by: str,
        reason: Optional[str] = None
    ):
        """Initialize transition"""
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp
        self.triggered_by = triggered_by
        self.reason = reason

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'timestamp': self.timestamp.isoformat(),
            'triggered_by': self.triggered_by,
            'reason': self.reason
        }


class ConfigStateMachine:
    """
    Manages configuration state transitions.

    Enforces valid state transitions and tracks history.
    """

    VALID_TRANSITIONS = {
        ConfigState.DRAFT: [
            ConfigState.PENDING_APPROVAL,
            ConfigState.CANCELLED
        ],
        ConfigState.PENDING_APPROVAL: [
            ConfigState.APPROVED,
            ConfigState.CANCELLED,
            ConfigState.DRAFT
        ],
        ConfigState.APPROVED: [
            ConfigState.EXECUTING,
            ConfigState.CANCELLED
        ],
        ConfigState.EXECUTING: [
            ConfigState.EXECUTED,
            ConfigState.FAILED
        ],
        ConfigState.EXECUTED: [
            ConfigState.ROLLED_BACK
        ],
        ConfigState.FAILED: [
            ConfigState.ROLLED_BACK,
            ConfigState.DRAFT
        ],
        ConfigState.ROLLED_BACK: [
            ConfigState.DRAFT
        ],
        ConfigState.CANCELLED: []
    }

    def __init__(
        self,
        config_id: str,
        initial_state: ConfigState = ConfigState.DRAFT
    ):
        """
        Initialize state machine.

        Args:
            config_id: Configuration identifier
            initial_state: Starting state
        """
        self.config_id = config_id
        self.current_state = initial_state
        self.logger = logging.getLogger(f"{__name__}.{config_id}")

        # Transition history
        self.transitions: List[ConfigTransition] = []

        # State metadata
        self.state_entered_at = datetime.now(timezone.utc)
        self.state_metadata: Dict[ConfigState, Dict] = {}

    def transition(
        self,
        to_state: ConfigState,
        triggered_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Transition to new state.

        Args:
            to_state: Target state
            triggered_by: Controller/user triggering transition
            reason: Optional reason for transition

        Returns:
            True if transition successful
        """
        if not self._is_valid_transition(self.current_state, to_state):
            self.logger.error(
                f"Invalid transition: {self.current_state.value} -> {to_state.value}"
            )
            return False

        transition = ConfigTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            triggered_by=triggered_by,
            reason=reason
        )

        self.transitions.append(transition)

        old_state = self.current_state
        self.current_state = to_state
        self.state_entered_at = datetime.now(timezone.utc)

        self.logger.info(
            f"Transitioned: {old_state.value} -> {to_state.value} "
            f"(by {triggered_by})"
        )

        if reason:
            self.logger.info(f"Reason: {reason}")

        return True

    def _is_valid_transition(
        self,
        from_state: ConfigState,
        to_state: ConfigState
    ) -> bool:
        """Check if state transition is valid"""
        return to_state in self.VALID_TRANSITIONS.get(from_state, [])

    def can_transition_to(self, to_state: ConfigState) -> bool:
        """Check if can transition to state"""
        return self._is_valid_transition(self.current_state, to_state)

    def get_valid_transitions(self) -> List[ConfigState]:
        """Get list of valid next states"""
        return self.VALID_TRANSITIONS.get(self.current_state, [])

    def get_state_duration(self) -> float:
        """Get time in current state (seconds)"""
        return (datetime.now(timezone.utc) - self.state_entered_at).total_seconds()

    def set_state_metadata(self, key: str, value):
        """Set metadata for current state"""
        if self.current_state not in self.state_metadata:
            self.state_metadata[self.current_state] = {}

        self.state_metadata[self.current_state][key] = value

    def get_state_metadata(self, key: str, default=None):
        """Get metadata for current state"""
        return self.state_metadata.get(self.current_state, {}).get(key, default)

    def get_transition_history(self) -> List[Dict]:
        """Get full transition history"""
        return [t.to_dict() for t in self.transitions]

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'config_id': self.config_id,
            'current_state': self.current_state.value,
            'state_entered_at': self.state_entered_at.isoformat(),
            'transitions': self.get_transition_history(),
            'state_metadata': {
                state.value: metadata
                for state, metadata in self.state_metadata.items()
            }
        }


class ConfigurationRecord:
    """
    Complete configuration record with state machine.

    Combines configuration details with state management.
    """

    def __init__(
        self,
        config_id: str,
        device_id: str,
        config_lines: List[str],
        requester_id: str
    ):
        """Initialize configuration record"""
        self.config_id = config_id
        self.device_id = device_id
        self.config_lines = config_lines
        self.requester_id = requester_id
        self.created_at = datetime.now(timezone.utc)

        # State machine
        self.state_machine = ConfigStateMachine(config_id)

        # Associated records
        self.approval_request_id: Optional[str] = None
        self.execution_token_id: Optional[str] = None
        self.backup_config: Optional[List[str]] = None

        # Results
        self.execution_result: Optional[Dict] = None
        self.rollback_result: Optional[Dict] = None

    @property
    def state(self) -> ConfigState:
        """Get current state"""
        return self.state_machine.current_state

    def transition(
        self,
        to_state: ConfigState,
        triggered_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """Transition to new state"""
        return self.state_machine.transition(to_state, triggered_by, reason)

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'config_id': self.config_id,
            'device_id': self.device_id,
            'config_lines': self.config_lines,
            'requester_id': self.requester_id,
            'created_at': self.created_at.isoformat(),
            'state': self.state.value,
            'state_machine': self.state_machine.to_dict(),
            'approval_request_id': self.approval_request_id,
            'execution_token_id': self.execution_token_id,
            'execution_result': self.execution_result,
            'rollback_result': self.rollback_result
        }


# Example usage:
"""
from pdsno.config.config_state import ConfigStateMachine, ConfigState

# Create state machine
state_machine = ConfigStateMachine("config-001")

# Transition through states
state_machine.transition(
    ConfigState.PENDING_APPROVAL,
    triggered_by="local_cntl_001",
    reason="Configuration submitted for approval"
)

state_machine.transition(
    ConfigState.APPROVED,
    triggered_by="regional_cntl_zone-A_1",
    reason="MEDIUM sensitivity approved by regional controller"
)

state_machine.transition(
    ConfigState.EXECUTING,
    triggered_by="local_cntl_001",
    reason="Executing with valid token"
)

state_machine.transition(
    ConfigState.EXECUTED,
    triggered_by="local_cntl_001",
    reason="Configuration applied successfully"
)

# Check state
print(f"Current state: {state_machine.current_state.value}")
print(f"Time in state: {state_machine.get_state_duration():.2f}s")

# Get history
history = state_machine.get_transition_history()
for trans in history:
    print(f"{trans['from_state']} -> {trans['to_state']}: {trans['reason']}")
"""
