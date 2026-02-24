"""
Audit Trail System

Complete audit logging for all configuration changes.

Tracks:
- Who requested what configuration
- Who approved/rejected
- When execution occurred
- What was the outcome
- Any rollbacks performed
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import json


class AuditEventType(Enum):
    """Types of audit events"""
    CONFIG_CREATED = "CONFIG_CREATED"
    CONFIG_SUBMITTED = "CONFIG_SUBMITTED"
    CONFIG_APPROVED = "CONFIG_APPROVED"
    CONFIG_REJECTED = "CONFIG_REJECTED"
    CONFIG_EXECUTED = "CONFIG_EXECUTED"
    CONFIG_FAILED = "CONFIG_FAILED"
    CONFIG_ROLLED_BACK = "CONFIG_ROLLED_BACK"
    CONFIG_CANCELLED = "CONFIG_CANCELLED"
    BACKUP_CREATED = "BACKUP_CREATED"
    TOKEN_ISSUED = "TOKEN_ISSUED"
    TOKEN_VERIFIED = "TOKEN_VERIFIED"
    TOKEN_REJECTED = "TOKEN_REJECTED"


class AuditEvent:
    """Represents an audit log event"""

    def __init__(
        self,
        event_id: str,
        event_type: AuditEventType,
        timestamp: datetime,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        details: Optional[Dict] = None
    ):
        """
        Initialize audit event.

        Args:
            event_id: Unique event identifier
            event_type: Type of event
            timestamp: When event occurred
            actor_id: Who performed the action
            resource_type: Type of resource (config, device, token)
            resource_id: Specific resource identifier
            action: Action performed
            result: SUCCESS, FAILURE, PENDING
            details: Additional event details
        """
        self.event_id = event_id
        self.event_type = event_type
        self.timestamp = timestamp
        self.actor_id = actor_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.result = result
        self.details = details or {}

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'actor_id': self.actor_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action': self.action,
            'result': self.result,
            'details': self.details
        }

    def to_log_string(self) -> str:
        """Format as human-readable log entry"""
        return (
            f"[{self.timestamp.isoformat()}] "
            f"{self.event_type.value}: "
            f"Actor={self.actor_id} "
            f"Resource={self.resource_type}/{self.resource_id} "
            f"Action={self.action} "
            f"Result={self.result}"
        )


class AuditTrail:
    """
    Manages audit trail for configuration changes.
    """

    def __init__(self, controller_id: str):
        """
        Initialize audit trail.

        Args:
            controller_id: This controller's ID
        """
        self.controller_id = controller_id
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")

        # In-memory event storage (in production, write to database)
        self.events: List[AuditEvent] = []

    def log_event(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        details: Optional[Dict] = None
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            actor_id: Who performed action
            resource_type: Resource type
            resource_id: Resource identifier
            action: Action performed
            result: Outcome (SUCCESS/FAILURE/PENDING)
            details: Additional details

        Returns:
            Created audit event
        """
        import uuid

        event = AuditEvent(
            event_id=f"audit-{uuid.uuid4()}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            details=details
        )

        # Store event
        self.events.append(event)

        # Log to file
        self.logger.info(event.to_log_string())

        return event

    def log_config_created(
        self,
        config_id: str,
        device_id: str,
        requester_id: str,
        sensitivity: str
    ):
        """Log configuration creation"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_CREATED,
            actor_id=requester_id,
            resource_type="configuration",
            resource_id=config_id,
            action="create",
            result="SUCCESS",
            details={
                'device_id': device_id,
                'sensitivity': sensitivity
            }
        )

    def log_config_submitted(
        self,
        config_id: str,
        requester_id: str
    ):
        """Log configuration submission for approval"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_SUBMITTED,
            actor_id=requester_id,
            resource_type="configuration",
            resource_id=config_id,
            action="submit_for_approval",
            result="PENDING",
            details={}
        )

    def log_config_approved(
        self,
        config_id: str,
        approver_id: str,
        auto_approved: bool = False
    ):
        """Log configuration approval"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_APPROVED,
            actor_id=approver_id,
            resource_type="configuration",
            resource_id=config_id,
            action="approve",
            result="SUCCESS",
            details={'auto_approved': auto_approved}
        )

    def log_config_rejected(
        self,
        config_id: str,
        rejector_id: str,
        reason: str
    ):
        """Log configuration rejection"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_REJECTED,
            actor_id=rejector_id,
            resource_type="configuration",
            resource_id=config_id,
            action="reject",
            result="SUCCESS",
            details={'reason': reason}
        )

    def log_config_executed(
        self,
        config_id: str,
        device_id: str,
        executor_id: str,
        token_id: str
    ):
        """Log successful configuration execution"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_EXECUTED,
            actor_id=executor_id,
            resource_type="configuration",
            resource_id=config_id,
            action="execute",
            result="SUCCESS",
            details={
                'device_id': device_id,
                'token_id': token_id
            }
        )

    def log_config_failed(
        self,
        config_id: str,
        device_id: str,
        executor_id: str,
        error: str
    ):
        """Log failed configuration execution"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_FAILED,
            actor_id=executor_id,
            resource_type="configuration",
            resource_id=config_id,
            action="execute",
            result="FAILURE",
            details={
                'device_id': device_id,
                'error': error
            }
        )

    def log_config_rolled_back(
        self,
        config_id: str,
        device_id: str,
        triggered_by: str,
        backup_id: str,
        reason: str
    ):
        """Log configuration rollback"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_ROLLED_BACK,
            actor_id=triggered_by,
            resource_type="configuration",
            resource_id=config_id,
            action="rollback",
            result="SUCCESS",
            details={
                'device_id': device_id,
                'backup_id': backup_id,
                'reason': reason
            }
        )

    def log_token_issued(
        self,
        token_id: str,
        config_id: str,
        device_id: str,
        issued_by: str,
        validity_minutes: int
    ):
        """Log execution token issuance"""
        return self.log_event(
            event_type=AuditEventType.TOKEN_ISSUED,
            actor_id=issued_by,
            resource_type="execution_token",
            resource_id=token_id,
            action="issue",
            result="SUCCESS",
            details={
                'config_id': config_id,
                'device_id': device_id,
                'validity_minutes': validity_minutes
            }
        )

    def log_token_verified(
        self,
        token_id: str,
        device_id: str,
        verifier_id: str
    ):
        """Log successful token verification"""
        return self.log_event(
            event_type=AuditEventType.TOKEN_VERIFIED,
            actor_id=verifier_id,
            resource_type="execution_token",
            resource_id=token_id,
            action="verify",
            result="SUCCESS",
            details={'device_id': device_id}
        )

    def log_token_rejected(
        self,
        token_id: str,
        device_id: str,
        verifier_id: str,
        reason: str
    ):
        """Log failed token verification"""
        return self.log_event(
            event_type=AuditEventType.TOKEN_REJECTED,
            actor_id=verifier_id,
            resource_type="execution_token",
            resource_id=token_id,
            action="verify",
            result="FAILURE",
            details={
                'device_id': device_id,
                'reason': reason
            }
        )

    def query_events(
        self,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            resource_id: Filter by resource
            actor_id: Filter by actor
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            Filtered events
        """
        filtered = self.events

        if resource_id:
            filtered = [e for e in filtered if e.resource_id == resource_id]

        if actor_id:
            filtered = [e for e in filtered if e.actor_id == actor_id]

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]

        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        return filtered

    def get_config_history(self, config_id: str) -> List[AuditEvent]:
        """Get complete history for a configuration"""
        return self.query_events(resource_id=config_id)

    def get_actor_actions(self, actor_id: str) -> List[AuditEvent]:
        """Get all actions by an actor"""
        return self.query_events(actor_id=actor_id)

    def export_to_json(self, filename: str):
        """Export audit trail to JSON file"""
        data = [event.to_dict() for event in self.events]

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Exported {len(data)} events to {filename}")

    def generate_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        Generate audit report for time period.

        Returns:
            Summary statistics
        """
        events = self.query_events(start_time=start_time, end_time=end_time)

        # Count by type
        by_type = {}
        for event in events:
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + 1

        # Count by result
        by_result = {}
        for event in events:
            by_result[event.result] = by_result.get(event.result, 0) + 1

        # Unique actors
        actors = set(event.actor_id for event in events)

        return {
            'period': {
                'start': start_time.isoformat() if start_time else 'beginning',
                'end': end_time.isoformat() if end_time else 'now'
            },
            'total_events': len(events),
            'by_type': by_type,
            'by_result': by_result,
            'unique_actors': len(actors),
            'actors': list(actors)
        }


# Example usage:
"""
from pdsno.config.audit_trail import AuditTrail, AuditEventType

# Initialize audit trail
audit = AuditTrail("local_cntl_001")

# Log configuration lifecycle
audit.log_config_created(
    config_id="config-001",
    device_id="switch-core-01",
    requester_id="local_cntl_001",
    sensitivity="MEDIUM"
)

audit.log_config_submitted(
    config_id="config-001",
    requester_id="local_cntl_001"
)

audit.log_config_approved(
    config_id="config-001",
    approver_id="regional_cntl_zone-A_1",
    auto_approved=False
)

audit.log_config_executed(
    config_id="config-001",
    device_id="switch-core-01",
    executor_id="local_cntl_001",
    token_id="token-abc123"
)

# Query history
history = audit.get_config_history("config-001")
print(f"Configuration had {len(history)} events")

# Generate report
report = audit.generate_report()
print(f"Total events: {report['total_events']}")
print(f"By type: {report['by_type']}")
"""
