# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Approval Workflow Engine

Manages configuration approval workflows based on sensitivity:
- LOW: Automatic approval (no human intervention)
- MEDIUM: Regional Controller approval required
- HIGH: Global Controller approval required

Implements state machine with transitions and timeout handling.
"""

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Approval Workflow Engine

Manages configuration approval workflows based on sensitivity:
- LOW: Automatic approval (no human intervention)
- MEDIUM: Regional Controller approval required
- HIGH: Global Controller approval required

Fix (2026-03-21):
  - Requests are now persisted to NIB on submit_request() so the RC's
    engine instance can retrieve them. Previously both LC and RC held
    separate in-memory dicts, causing "Request not found" across
    controller boundaries.
  - LOW sensitivity path now correctly transitions DRAFT -> PENDING_APPROVAL
    -> APPROVED (two hops) instead of attempting DRAFT -> APPROVED in a
    single call to approve_request() which bypassed submit_request().
  - NIBStore is optional (defaults to None) for backwards compatibility
    with unit tests that don't inject a store.
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid
import json

from pdsno.config.sensitivity_classifier import SensitivityLevel


class ApprovalState(Enum):
    """
    Configuration approval states
        - DRAFT: Created but not yet submitted for approval
        - PENDING_APPROVAL: Submitted and awaiting approval
        - APPROVED: Approved and ready for execution
        - REJECTED: Rejected by approver
        - EXPIRED: Not approved within timeout window
        - EXECUTED: Execution instruction sent and marked as executed
        - FAILED: Execution instruction sent but failed
        - ROLLED_BACK: Execution failed and changes were rolled back
    
    """
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ApprovalRequest:
    """Represents a configuration change requiring approval."""

    def __init__(
        self,
        request_id: str,
        device_id: str,
        config_lines: List[str],
        sensitivity: SensitivityLevel,
        requester_id: str,
        created_at: Optional[datetime] = None
    ):
        self.request_id = request_id
        self.device_id = device_id
        self.config_lines = config_lines
        self.sensitivity = sensitivity
        self.requester_id = requester_id
        self.created_at = created_at or datetime.now(timezone.utc)

        self.state = ApprovalState.DRAFT
        self.approvers: List[str] = []
        self.rejector: Optional[str] = None
        self.rejection_reason: Optional[str] = None

        self.submitted_at: Optional[datetime] = None
        self.approved_at: Optional[datetime] = None
        self.executed_at: Optional[datetime] = None

        self.execution_token: Optional[str] = None
        self.execution_result: Optional[Dict] = None

    def to_dict(self) -> Dict:
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
    - LOW: Auto-approve (no human review needed)
    - MEDIUM: Regional Controller approval required
    - HIGH: Global Controller approval required

    Requests are persisted to NIB so they are visible across controller
    boundaries. The in-memory dict is a write-through cache.
    """

    def __init__(
        self,
        controller_id: str,
        controller_role: str,
        approval_timeout_minutes: int = 60,
        nib_store=None   # Optional NIBStore — injected by controller
    ):
        self.controller_id = controller_id
        self.controller_role = controller_role
        self.approval_timeout = timedelta(minutes=approval_timeout_minutes)
        self.nib_store = nib_store
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")

        # In-memory cache — source of truth is NIB when nib_store is set
        self.requests: Dict[str, ApprovalRequest] = {}

    # ── NIB persistence helpers ──────────────────────────────────────────────

    def _persist_request(self, request: ApprovalRequest):
        """Write request state to NIB if a store is available."""
        if not self.nib_store:
            return
        try:
            # Store serialised request as a config record in the NIB
            from pdsno.datastore.models import Config, ConfigCategory, ConfigStatus

            status_map = {
                ApprovalState.DRAFT: ConfigStatus.PENDING,
                ApprovalState.PENDING_APPROVAL: ConfigStatus.PENDING,
                ApprovalState.APPROVED: ConfigStatus.APPROVED,
                ApprovalState.REJECTED: ConfigStatus.DENIED,
                ApprovalState.EXPIRED: ConfigStatus.DENIED,
                ApprovalState.EXECUTED: ConfigStatus.EXECUTED,
                ApprovalState.FAILED: ConfigStatus.FAILED,
                ApprovalState.ROLLED_BACK: ConfigStatus.ROLLED_BACK,
            }
            category_map = {
                SensitivityLevel.LOW: ConfigCategory.LOW,
                SensitivityLevel.MEDIUM: ConfigCategory.MEDIUM,
                SensitivityLevel.HIGH: ConfigCategory.HIGH,
            }

            existing = self.nib_store.get_config(request.request_id)
            if not existing:
                config = Config(
                    config_id=request.request_id,
                    device_id=request.device_id,
                    config_data=json.dumps(request.to_dict()),
                    status=status_map.get(request.state, ConfigStatus.PENDING),
                    category=category_map.get(request.sensitivity, ConfigCategory.LOW),
                    proposed_by=request.requester_id,
                    approved_by=request.approvers[-1] if request.approvers else None,
                    execution_token=request.execution_token,
                    proposed_at=request.submitted_at or request.created_at,
                    approved_at=request.approved_at,
                )
                self.nib_store.create_config_proposal(config)
            else:
                self.nib_store.update_config_status(
                    config_id=request.request_id,
                    status=status_map.get(request.state, ConfigStatus.PENDING),
                    version=existing.version,
                    approver=request.approvers[-1] if request.approvers else None,
                    execution_token=request.execution_token,
                )
        except Exception as e:
            # Non-fatal — log and continue. In-memory state still valid.
            self.logger.warning(f"Could not persist request {request.request_id} to NIB: {e}")

    def _load_request_from_nib(self, request_id: str) -> Optional[ApprovalRequest]:
        """Load a request from NIB (used by RC to find LC-created requests)."""
        if not self.nib_store:
            return None
        try:
            config = self.nib_store.get_config(request_id)
            if config and config.config_data:
                try:
                    data = json.loads(config.config_data)
                    return ApprovalRequest.from_dict(data)
                except json.JSONDecodeError:
                    self.logger.debug(
                        f"Config {request_id} has non-JSON config_data; skipping request reconstruction"
                    )
        except Exception as e:
            self.logger.warning(f"Could not load request {request_id} from NIB: {e}")
        return None

    # ── Public API ───────────────────────────────────────────────────────────

    def create_request(
        self,
        device_id: str,
        config_lines: List[str],
        sensitivity: SensitivityLevel
    ) -> ApprovalRequest:
        """Create a new approval request (DRAFT state)."""
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

        Always transitions DRAFT -> PENDING_APPROVAL first.
        LOW sensitivity then immediately auto-approves in the same call,
        producing the correct two-hop path: DRAFT -> PENDING_APPROVAL -> APPROVED.
        """
        request = self.requests.get(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found in local cache")
            return False

        if request.state != ApprovalState.DRAFT:
            self.logger.error(
                f"Request {request_id} cannot be submitted from state {request.state.value}"
            )
            return False

        # Always go DRAFT -> PENDING_APPROVAL first
        request.state = ApprovalState.PENDING_APPROVAL
        request.submitted_at = datetime.now(timezone.utc)
        self.logger.info(f"Request {request_id} submitted (PENDING_APPROVAL)")

        # Persist so RC can find it
        self._persist_request(request)

        # LOW sensitivity: auto-approve immediately
        if request.sensitivity == SensitivityLevel.LOW:
            self.logger.info(f"Auto-approving LOW sensitivity request {request_id}")
            return self.approve_request(request_id, self.controller_id, auto=True)

        return True

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get request by ID, checking NIB if not in local cache.

        This is what allows RC to find requests originally created by LC.
        """
        if request_id in self.requests:
            return self.requests[request_id]

        # Try NIB — needed when RC processes a request created by LC
        nib_request = self._load_request_from_nib(request_id)
        if nib_request:
            self.requests[request_id] = nib_request  # cache it
            self.logger.debug(f"Loaded request {request_id} from NIB")
            return nib_request

        return None

    def approve_request(
        self,
        request_id: str,
        approver_id: str,
        auto: bool = False
    ) -> bool:
        """
        Approve a request.

        Requires state == PENDING_APPROVAL.
        """
        request = self.get_request(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found (checked cache + NIB)")
            return False

        if request.state != ApprovalState.PENDING_APPROVAL:
            self.logger.error(
                f"Request {request_id} not in PENDING_APPROVAL "
                f"(current: {request.state.value})"
            )
            return False

        if not self._can_approve(request, approver_id):
            self.logger.error(
                f"Controller {approver_id} lacks authority to approve "
                f"{request.sensitivity.value} request"
            )
            return False

        if self._is_expired(request):
            request.state = ApprovalState.EXPIRED
            self._persist_request(request)
            self.logger.warning(f"Request {request_id} expired before approval")
            return False

        request.state = ApprovalState.APPROVED
        request.approved_at = datetime.now(timezone.utc)
        request.approvers.append(approver_id)

        # Ensure it's in local cache (may have been loaded from NIB)
        self.requests[request_id] = request
        self._persist_request(request)

        approval_type = "Auto-approved" if auto else "Approved"
        self.logger.info(f"{approval_type} request {request_id} by {approver_id}")

        return True

    def reject_request(
        self,
        request_id: str,
        rejector_id: str,
        reason: str
    ) -> bool:
        """Reject a request."""
        request = self.get_request(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        if request.state != ApprovalState.PENDING_APPROVAL:
            self.logger.error(f"Request {request_id} not pending approval")
            return False

        if not self._can_approve(request, rejector_id):
            self.logger.error(
                f"Controller {rejector_id} lacks authority to reject "
                f"{request.sensitivity.value} request"
            )
            return False

        request.state = ApprovalState.REJECTED
        request.rejector = rejector_id
        request.rejection_reason = reason

        self.requests[request_id] = request
        self._persist_request(request)

        self.logger.info(f"Rejected request {request_id} by {rejector_id}: {reason}")
        return True

    def get_pending_requests(self) -> List[ApprovalRequest]:
        return [
            req for req in self.requests.values()
            if req.state == ApprovalState.PENDING_APPROVAL
        ]

    def cleanup_expired_requests(self) -> int:
        count = 0
        for request in self.requests.values():
            if (
                request.state == ApprovalState.PENDING_APPROVAL
                and self._is_expired(request)
            ):
                request.state = ApprovalState.EXPIRED
                self._persist_request(request)
                count += 1
                self.logger.info(f"Expired request {request.request_id}")
        return count

    def set_execution_token(self, request_id: str, token_id: str) -> bool:
        """Attach execution token ID to an approved request and persist it."""
        request = self.get_request(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        if request.state != ApprovalState.APPROVED:
            self.logger.error(
                f"Request {request_id} must be APPROVED before setting execution token "
                f"(current: {request.state.value})"
            )
            return False

        request.execution_token = token_id
        self.requests[request_id] = request
        self._persist_request(request)
        return True

    def set_execution_result(self, request_id: str, result: Dict) -> bool:
        """Persist execution result and transition request to terminal state."""
        request = self.get_request(request_id)
        if not request:
            self.logger.error(f"Request {request_id} not found")
            return False

        status = (result or {}).get("status", "").upper()
        if status in ("EXECUTED", "SUCCESS"):
            request.state = ApprovalState.EXECUTED
        elif status in ("FAILED", "ERROR", "DEGRADED"):
            request.state = ApprovalState.FAILED
        elif status == "ROLLED_BACK":
            request.state = ApprovalState.ROLLED_BACK

        request.execution_result = result
        request.executed_at = datetime.now(timezone.utc)
        self.requests[request_id] = request
        self._persist_request(request)
        return True

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _can_approve(self, request: ApprovalRequest, approver_id: str) -> bool:
        """
        Check if controller can approve based on role inferred from ID.

        Convention: IDs contain "global", "regional", or "local".
        """
        aid = approver_id.lower()
        if "global" in aid:
            approver_role = "global"
        elif "regional" in aid:
            approver_role = "regional"
        else:
            approver_role = "local"

        if request.sensitivity == SensitivityLevel.LOW:
            return True
        if request.sensitivity == SensitivityLevel.MEDIUM:
            return approver_role in ("regional", "global")
        # HIGH
        return approver_role == "global"

    def _is_expired(self, request: ApprovalRequest) -> bool:
        if not request.submitted_at:
            return False
        return (datetime.now(timezone.utc) - request.submitted_at) > self.approval_timeout

    # def _is_expired(self, request: ApprovalRequest) -> bool:
    #     """Check if request has expired"""
    #     if not request.submitted_at:
    #         return False

    #     age = datetime.now(timezone.utc) - request.submitted_at
    #     return age > self.approval_timeout

    # def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
    #     """Get request by ID"""
    #     return self.requests.get(request_id)

    # def get_pending_requests(self) -> List[ApprovalRequest]:
    #     """Get all pending approval requests"""
    #     return [
    #         req for req in self.requests.values()
    #         if req.state == ApprovalState.PENDING_APPROVAL
    #     ]

    # def cleanup_expired_requests(self) -> int:
    #     """
    #     Mark expired requests.

    #     Returns:
    #         Number of requests expired
    #     """
    #     count = 0

    #     for request in self.requests.values():
    #         if (
    #             request.state == ApprovalState.PENDING_APPROVAL and
    #             self._is_expired(request)
    #         ):
    #             request.state = ApprovalState.EXPIRED
    #             count += 1
    #             self.logger.info(f"Expired request {request.request_id}")

    #     return count


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
