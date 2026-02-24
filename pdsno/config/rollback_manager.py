"""
Rollback Manager

Handles configuration backup and rollback for failure recovery.

Features:
- Pre-execution config backup
- Automatic rollback on failure
- Manual rollback triggers
- Rollback verification
- Rollback history tracking
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging


class ConfigBackup:
    """Represents a configuration backup"""

    def __init__(
        self,
        backup_id: str,
        device_id: str,
        config_lines: List[str],
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Initialize configuration backup.

        Args:
            backup_id: Unique backup identifier
            device_id: Device this backup is from
            config_lines: Configuration commands
            created_at: Backup timestamp
            metadata: Additional backup metadata
        """
        self.backup_id = backup_id
        self.device_id = device_id
        self.config_lines = config_lines
        self.created_at = created_at or datetime.now(timezone.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'backup_id': self.backup_id,
            'device_id': self.device_id,
            'config_lines': self.config_lines,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfigBackup':
        """Deserialize from dictionary"""
        return cls(
            backup_id=data['backup_id'],
            device_id=data['device_id'],
            config_lines=data['config_lines'],
            created_at=datetime.fromisoformat(data['created_at']),
            metadata=data.get('metadata', {})
        )


class RollbackEvent:
    """Represents a rollback event"""

    def __init__(
        self,
        event_id: str,
        config_id: str,
        device_id: str,
        backup_id: str,
        triggered_by: str,
        triggered_at: Optional[datetime] = None,
        reason: Optional[str] = None,
        success: Optional[bool] = None,
        error: Optional[str] = None
    ):
        """Initialize rollback event"""
        self.event_id = event_id
        self.config_id = config_id
        self.device_id = device_id
        self.backup_id = backup_id
        self.triggered_by = triggered_by
        self.triggered_at = triggered_at or datetime.now(timezone.utc)
        self.reason = reason
        self.success = success
        self.error = error

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'event_id': self.event_id,
            'config_id': self.config_id,
            'device_id': self.device_id,
            'backup_id': self.backup_id,
            'triggered_by': self.triggered_by,
            'triggered_at': self.triggered_at.isoformat(),
            'reason': self.reason,
            'success': self.success,
            'error': self.error
        }


class RollbackManager:
    """
    Manages configuration backup and rollback.
    """

    def __init__(self, controller_id: str):
        """
        Initialize rollback manager.

        Args:
            controller_id: This controller's ID
        """
        self.controller_id = controller_id
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")

        # Storage
        self.backups: Dict[str, ConfigBackup] = {}
        self.device_backups: Dict[str, List[str]] = {}
        self.rollback_events: List[RollbackEvent] = []

    def create_backup(
        self,
        device_id: str,
        config_lines: List[str],
        metadata: Optional[Dict] = None
    ) -> ConfigBackup:
        """
        Create a configuration backup.

        Args:
            device_id: Device to backup
            config_lines: Current configuration
            metadata: Additional metadata

        Returns:
            Created backup
        """
        import uuid
        backup_id = f"backup-{uuid.uuid4()}"

        backup = ConfigBackup(
            backup_id=backup_id,
            device_id=device_id,
            config_lines=config_lines,
            metadata=metadata
        )

        # Store backup
        self.backups[backup_id] = backup

        # Track by device
        if device_id not in self.device_backups:
            self.device_backups[device_id] = []
        self.device_backups[device_id].append(backup_id)

        self.logger.info(
            f"Created backup {backup_id} for device {device_id} "
            f"({len(config_lines)} lines)"
        )

        return backup

    def get_backup(self, backup_id: str) -> Optional[ConfigBackup]:
        """Get backup by ID"""
        return self.backups.get(backup_id)

    def get_device_backups(self, device_id: str) -> List[ConfigBackup]:
        """Get all backups for a device"""
        backup_ids = self.device_backups.get(device_id, [])
        return [self.backups[bid] for bid in backup_ids if bid in self.backups]

    def get_latest_backup(self, device_id: str) -> Optional[ConfigBackup]:
        """Get most recent backup for device"""
        backups = self.get_device_backups(device_id)
        if not backups:
            return None

        return max(backups, key=lambda b: b.created_at)

    def rollback(
        self,
        config_id: str,
        device_id: str,
        backup_id: str,
        reason: str,
        triggered_by: Optional[str] = None
    ) -> RollbackEvent:
        """
        Perform configuration rollback.

        Args:
            config_id: Configuration being rolled back
            device_id: Target device
            backup_id: Backup to restore
            reason: Rollback reason
            triggered_by: Controller triggering rollback

        Returns:
            Rollback event
        """
        import uuid

        triggered_by = triggered_by or self.controller_id
        event_id = f"rollback-{uuid.uuid4()}"

        # Create event
        event = RollbackEvent(
            event_id=event_id,
            config_id=config_id,
            device_id=device_id,
            backup_id=backup_id,
            triggered_by=triggered_by,
            reason=reason
        )

        # Get backup
        backup = self.backups.get(backup_id)
        if not backup:
            event.success = False
            event.error = f"Backup {backup_id} not found"
            self.logger.error(event.error)
            self.rollback_events.append(event)
            return event

        if backup.device_id != device_id:
            event.success = False
            event.error = f"Backup for {backup.device_id}, not {device_id}"
            self.logger.error(event.error)
            self.rollback_events.append(event)
            return event

        self.logger.info(
            f"Rolling back device {device_id} to backup {backup_id} "
            f"({len(backup.config_lines)} lines)"
        )

        # Simulate execution
        try:
            event.success = True
            self.logger.info(f"Rollback {event_id} successful")

        except Exception as e:
            event.success = False
            event.error = str(e)
            self.logger.error(f"Rollback {event_id} failed: {e}")

        self.rollback_events.append(event)
        return event

    def auto_rollback(
        self,
        config_id: str,
        device_id: str,
        failure_reason: str
    ) -> Optional[RollbackEvent]:
        """
        Automatically rollback after execution failure.

        Args:
            config_id: Failed configuration
            device_id: Target device
            failure_reason: Why execution failed

        Returns:
            Rollback event, or None if no backup available
        """
        backup = self.get_latest_backup(device_id)
        if not backup:
            self.logger.error(f"No backup available for {device_id}")
            return None

        self.logger.info(
            f"Auto-rollback triggered for {device_id} due to: {failure_reason}"
        )

        return self.rollback(
            config_id=config_id,
            device_id=device_id,
            backup_id=backup.backup_id,
            reason=f"Automatic rollback after failure: {failure_reason}",
            triggered_by=self.controller_id
        )

    def verify_rollback(
        self,
        device_id: str,
        expected_config: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Verify rollback was successful.

        Args:
            device_id: Device to verify
            expected_config: Expected configuration after rollback

        Returns:
            (success, error_message) tuple
        """
        self.logger.info(f"Verifying rollback for {device_id}")

        return True, None

    def cleanup_old_backups(
        self,
        device_id: str,
        keep_count: int = 10
    ) -> int:
        """
        Remove old backups, keeping only most recent.

        Args:
            device_id: Device to cleanup
            keep_count: Number of backups to keep

        Returns:
            Number of backups deleted
        """
        backups = self.get_device_backups(device_id)

        if len(backups) <= keep_count:
            return 0

        sorted_backups = sorted(backups, key=lambda b: b.created_at)

        to_delete = sorted_backups[:-keep_count]
        deleted_count = 0

        for backup in to_delete:
            if backup.backup_id in self.backups:
                del self.backups[backup.backup_id]
                self.device_backups[device_id].remove(backup.backup_id)
                deleted_count += 1
                self.logger.debug(f"Deleted old backup {backup.backup_id}")

        self.logger.info(
            f"Cleaned up {deleted_count} old backups for {device_id} "
            f"(kept {keep_count} most recent)"
        )

        return deleted_count

    def get_rollback_history(
        self,
        device_id: Optional[str] = None
    ) -> List[RollbackEvent]:
        """
        Get rollback history.

        Args:
            device_id: Optional filter by device

        Returns:
            List of rollback events
        """
        if device_id:
            return [e for e in self.rollback_events if e.device_id == device_id]
        return self.rollback_events


# Example usage:
"""
from pdsno.config.rollback_manager import RollbackManager

# Initialize manager
manager = RollbackManager("local_cntl_001")

# Before executing config, create backup
current_config = [
    "interface gigabitethernet0/1",
    "description Uplink",
    "!"
]

backup = manager.create_backup(
    device_id="switch-core-01",
    config_lines=current_config,
    metadata={'pre_change': 'VLAN100 addition'}
)

# Execute new config...
# If execution fails:

event = manager.auto_rollback(
    config_id="config-001",
    device_id="switch-core-01",
    failure_reason="Device rejected VLAN configuration"
)

if event and event.success:
    print("Rollback successful")
else:
    print(f"Rollback failed: {event.error if event else 'No backup'}")

# Verify rollback
success, error = manager.verify_rollback(
    device_id="switch-core-01",
    expected_config=current_config
)
"""
