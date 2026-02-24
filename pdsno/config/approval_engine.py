"""
Approval Workflow Engine

Manages configuration approval workflows based on sensitivity:
- LOW: Automatic approval (no human intervention)
- MEDIUM: Regional Controller approval required
- HIGH: Global Controller approval required

Implements state machine with transitions and timeout handling.
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid

from pdsno.config.sensitivity_classifier import SensitivityLevel


class ApprovalState(Enum):
    """Configuration approval states"""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ApprovalRequest:
    """
    Represents a configuration change requiring approval.
    """

    def __init__(
        self,
        request_id: str,
        device_id: str,
        config_lines: List[str],
        sensitivity: SensitivityLevel,
        requester_id: str,
        created_at: Optional[datetime] = None
    ):
        """
        Initialize approval request.

        Args:
            request_id: Unique identifier
            device_id: Target device
            config_lines: Configuration commands
            sensitivity: Sensitivity classification
            requester_id: Controller that initiated request
            created_at: Request creation timestamp
        """
        self.request_id = request_id
        self.device_id = device_id
        self.config_lines = config_lines
        self.sensitivity = sensitivity
        self.requester_id = requester_id
        self.created_at = created_at or datetime.now(timezone.utc)

        # State management
        self.state = ApprovalState.DRAFT
        self.approvers: List[str] = []
        self.rejector: Optional[str] = None
        self.rejection_reason: Optional[str] = None

        # Timestamps
        self.submitted_at: Optional[datetime] = None
        self.approved_at: Optional[datetime] = None
        self.executed_at: Optional[datetime] = None

        # Execution
        self.execution_token: Optional[str] = None
        self.execution_result: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'request_id': self.request_id,
            'device_id': self.device_id,
            'config_lines': self.config_lines,
            'sensitivity': self.sensitivity.value,
            'requester_id': self.requester_id,
            'state': self.state.value,
            'approvers': self.approvers,
            'rejector': self.rejector,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'execution_token': self.execution_token,
            'execution_result': self.execution_result
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ApprovalRequest':
        """Deserialize from dictionary"""
        request = cls(
            request_id=data['request_id'],
            device_id=data['device_id'],
            config_lines=data['config_lines'],
            sensitivity=SensitivityLevel(data['sensitivity']),
            requester_id=data['requester_id'],
            created_at=datetime.fromisoformat(data['created_at'])
        )

        request.state = ApprovalState(data['state'])
        request.approvers = data['approvers']
        request.rejector = data['rejector']
        request.rejection_reason = data['rejection_reason']

        if data['submitted_at']:
            request.submitted_at = datetime.fromisoformat(data['submitted_at'])
        if data['approved_at']:
            request.approved_at = datetime.fromisoformat(data['approved_at'])
        if data['executed_at']:
            request.executed_at = datetime.fromisoformat(data['executed_at'])

        request.execution_token = data['execution_token']
        request.execution_result = data['execution_result']

        return request


class ApprovalWorkflowEngine:
    """
    Manages approval workflows for configuration changes.

    Workflow rules:
    - LOW sensitivity: Auto-approve
    - MEDIUM sensitivity: Requires Regional Controller approval
    - HIGH sensitivity: Requires Global Controller approval
    """

    def __init__(
        self,
        controller_id: str,
        controller_role: str,
        approval_timeout_minutes: int = 60
    ):
        """
        Initialize approval workflow engine.

        Args:
            controller_id: This controller's ID
            controller_role: "global", "regional", or "local"
            approval_timeout_minutes: Minutes before approval expires
        """
        self.controller_id = controller_id
        self.controller_role = controller_role
        self.approval_timeout = timedelta(minutes=approval_timeout_minutes)
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")

        # Active approval requests
        self.requests: Dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        device_id: str,
        config_lines: List[str],
        sensitivity: SensitivityLevel
    ) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            device_id: Target device
            config_lines: Configuration commands
            sensitivity: Sensitivity level

        Returns:
            Created approval request
        """
        request_id = str(uuid.uuid4())

        request = ApprovalRequest(
            request_id=request_id,
            device_id=device_id,
            config_lines=config_lines,
            sensitivity=sensitivity,
            requester_id=self.controller_id
        )

        self.requests[request_id] = request

        self.logger.info(
            f"Created approval request {request_id} "
            f"for device {device_id} (sensitivity: {sensitivity.value})"
        )

        return request

    def submit_request(self, request_id: str) -> bool:
        """
        Submit request for approval.

        Args:
            request_id: Request to submit

        Returns:
            True if submitted successfully
        """
        request = self.requests.get(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        if request.state != ApprovalState.DRAFT:
            self.logger.error(f"Request {request_id} already submitted")
            return False

        request.state = ApprovalState.PENDING_APPROVAL
        request.submitted_at = datetime.now(timezone.utc)

        # Auto-approve LOW sensitivity
        if request.sensitivity == SensitivityLevel.LOW:
            self.logger.info(f"Auto-approving LOW sensitivity request {request_id}")
            return self.approve_request(request_id, self.controller_id, auto=True)

        self.logger.info(
            f"Submitted request {request_id} for approval "
            f"(sensitivity: {request.sensitivity.value})"
        )

        return True

    def approve_request(
        self,
        request_id: str,
        approver_id: str,
        auto: bool = False
    ) -> bool:
        """
        Approve a request.

        Args:
            request_id: Request to approve
            approver_id: Controller ID approving
            auto: Whether this is automatic approval

        Returns:
            True if approved successfully
        """
        request = self.requests.get(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        if request.state != ApprovalState.PENDING_APPROVAL:
            self.logger.error(
                f"Request {request_id} not in PENDING_APPROVAL state "
                f"(current: {request.state.value})"
            )
            return False

        # Verify approver has authority
        if not self._can_approve(request, approver_id):
            self.logger.error(
                f"Controller {approver_id} lacks authority to approve "
                f"{request.sensitivity.value} request"
            )
            return False

        # Check for timeout
        if self._is_expired(request):
            request.state = ApprovalState.EXPIRED
            self.logger.warning(f"Request {request_id} expired")
            return False

        # Approve
        request.state = ApprovalState.APPROVED
        request.approved_at = datetime.now(timezone.utc)
        request.approvers.append(approver_id)

        approval_type = "Auto-approved" if auto else "Approved"
        self.logger.info(
            f"{approval_type} request {request_id} by {approver_id}"
        )

        return True

    def reject_request(
        self,
        request_id: str,
        rejector_id: str,
        reason: str
    ) -> bool:
        """
        Reject a request.

        Args:
            request_id: Request to reject
            rejector_id: Controller ID rejecting
            reason: Rejection reason

        Returns:
            True if rejected successfully
        """
        request = self.requests.get(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        if request.state != ApprovalState.PENDING_APPROVAL:
            self.logger.error(f"Request {request_id} not pending approval")
            return False

        # Verify rejector has authority
        if not self._can_approve(request, rejector_id):
            self.logger.error(
                f"Controller {rejector_id} lacks authority to reject "
                f"{request.sensitivity.value} request"
            )
            return False

        request.state = ApprovalState.REJECTED
        request.rejector = rejector_id
        request.rejection_reason = reason

        self.logger.info(
            f"Rejected request {request_id} by {rejector_id}: {reason}"
        )

        return True

    def _can_approve(self, request: ApprovalRequest, approver_id: str) -> bool:
        """
        Check if controller can approve request.

        Rules:
        - LOCAL can auto-approve LOW
        - REGIONAL can approve LOW and MEDIUM
        - GLOBAL can approve all
        """
        if "global" in approver_id.lower():
            approver_role = "global"
        elif "regional" in approver_id.lower():
            approver_role = "regional"
        else:
            approver_role = "local"

        if request.sensitivity == SensitivityLevel.LOW:
            return True
        if request.sensitivity == SensitivityLevel.MEDIUM:
            return approver_role in ["regional", "global"]
        return approver_role == "global"

    def _is_expired(self, request: ApprovalRequest) -> bool:
        """Check if request has expired"""
        if not request.submitted_at:
            return False

        age = datetime.now(timezone.utc) - request.submitted_at
        return age > self.approval_timeout

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get request by ID"""
        return self.requests.get(request_id)

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests"""
        return [
            req for req in self.requests.values()
            if req.state == ApprovalState.PENDING_APPROVAL
        ]

    def cleanup_expired_requests(self) -> int:
        """
        Mark expired requests.

        Returns:
            Number of requests expired
        """
        count = 0

        for request in self.requests.values():
            if (
                request.state == ApprovalState.PENDING_APPROVAL and
                self._is_expired(request)
            ):
                request.state = ApprovalState.EXPIRED
                count += 1
                self.logger.info(f"Expired request {request.request_id}")

        return count


# Example usage:
"""
from pdsno.config.approval_engine import ApprovalWorkflowEngine, ApprovalState
from pdsno.config.sensitivity_classifier import SensitivityLevel

# Initialize engine
engine = ApprovalWorkflowEngine(
    controller_id="local_cntl_001",
    controller_role="local",
    approval_timeout_minutes=60
)

# Create request
request = engine.create_request(
    device_id="switch-core-01",
    config_lines=[
        "vlan 100",
        "name Engineering"
    ],
    sensitivity=SensitivityLevel.MEDIUM
)

# Submit for approval
engine.submit_request(request.request_id)

# Approve (from Regional Controller)
engine.approve_request(
    request.request_id,
    approver_id="regional_cntl_zone-A_1"
)

# Check state
assert request.state == ApprovalState.APPROVED
"""
