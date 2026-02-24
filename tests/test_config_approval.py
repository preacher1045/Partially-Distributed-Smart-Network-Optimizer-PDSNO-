"""
Tests for Configuration Approval Logic (Phase 7)

Tests all components of the configuration approval workflow.
"""

import pytest
import secrets
from datetime import datetime, timezone, timedelta

from pdsno.config import (
    SensitivityLevel,
    ConfigSensitivityClassifier,
    ApprovalState,
    ApprovalWorkflowEngine,
    ExecutionTokenManager,
    ConfigState,
    ConfigStateMachine,
    ConfigurationRecord,
    RollbackManager,
    AuditTrail,
    AuditEventType
)


class TestSensitivityClassifier:
    """Test configuration sensitivity classification"""

    def test_low_sensitivity(self):
        """Test LOW sensitivity detection"""
        classifier = ConfigSensitivityClassifier()

        config = [
            "interface gigabitethernet0/1",
            "description Uplink to Core",
            "!"
        ]

        level = classifier.classify(config)
        assert level == SensitivityLevel.LOW

    def test_medium_sensitivity(self):
        """Test MEDIUM sensitivity detection"""
        classifier = ConfigSensitivityClassifier()

        config = [
            "vlan 100",
            "name Engineering",
            "interface gigabitethernet0/2",
            "switchport mode access",
            "switchport access vlan 100"
        ]

        level = classifier.classify(config)
        assert level == SensitivityLevel.MEDIUM

    def test_high_sensitivity(self):
        """Test HIGH sensitivity detection"""
        classifier = ConfigSensitivityClassifier()

        config = [
            "router bgp 65001",
            "neighbor 10.0.0.1 remote-as 65002",
            "network 192.168.0.0 mask 255.255.255.0"
        ]

        level = classifier.classify(config)
        assert level == SensitivityLevel.HIGH

    def test_classify_with_details(self):
        """Test detailed classification"""
        classifier = ConfigSensitivityClassifier()

        config = ["router ospf 1"]

        details = classifier.classify_with_details(config)

        assert details['sensitivity'] == SensitivityLevel.HIGH
        assert len(details['matched_patterns']) > 0
        assert 'routing' in details['reasoning'].lower()


class TestApprovalWorkflow:
    """Test approval workflow engine"""

    def test_create_request(self):
        """Test approval request creation"""
        engine = ApprovalWorkflowEngine("local_cntl_001", "local")

        request = engine.create_request(
            device_id="switch-01",
            config_lines=["vlan 100"],
            sensitivity=SensitivityLevel.MEDIUM
        )

        assert request.device_id == "switch-01"
        assert request.sensitivity == SensitivityLevel.MEDIUM
        assert request.state == ApprovalState.DRAFT

    def test_submit_low_auto_approves(self):
        """Test LOW sensitivity auto-approval"""
        engine = ApprovalWorkflowEngine("local_cntl_001", "local")

        request = engine.create_request(
            device_id="switch-01",
            config_lines=["description Test"],
            sensitivity=SensitivityLevel.LOW
        )

        engine.submit_request(request.request_id)

        assert request.state == ApprovalState.APPROVED
        assert "local_cntl_001" in request.approvers

    def test_submit_medium_pending(self):
        """Test MEDIUM sensitivity requires approval"""
        engine = ApprovalWorkflowEngine("local_cntl_001", "local")

        request = engine.create_request(
            device_id="switch-01",
            config_lines=["vlan 100"],
            sensitivity=SensitivityLevel.MEDIUM
        )

        engine.submit_request(request.request_id)

        assert request.state == ApprovalState.PENDING_APPROVAL
        assert len(request.approvers) == 0

    def test_approve_request(self):
        """Test request approval"""
        engine = ApprovalWorkflowEngine("local_cntl_001", "local")

        request = engine.create_request(
            device_id="switch-01",
            config_lines=["vlan 100"],
            sensitivity=SensitivityLevel.MEDIUM
        )

        engine.submit_request(request.request_id)

        success = engine.approve_request(
            request.request_id,
            "regional_cntl_zone-A_1"
        )

        assert success
        assert request.state == ApprovalState.APPROVED

    def test_reject_request(self):
        """Test request rejection"""
        engine = ApprovalWorkflowEngine("local_cntl_001", "local")

        request = engine.create_request(
            device_id="switch-01",
            config_lines=["vlan 100"],
            sensitivity=SensitivityLevel.MEDIUM
        )

        engine.submit_request(request.request_id)

        success = engine.reject_request(
            request.request_id,
            "regional_cntl_zone-A_1",
            "VLAN conflicts with existing allocation"
        )

        assert success
        assert request.state == ApprovalState.REJECTED
        assert request.rejection_reason is not None


class TestExecutionToken:
    """Test execution token system"""

    def test_issue_token(self):
        """Test token issuance"""
        shared_secret = secrets.token_bytes(32)
        manager = ExecutionTokenManager("regional_cntl_1", shared_secret)

        token = manager.issue_token(
            request_id="req-001",
            device_id="switch-01",
            validity_minutes=15
        )

        assert token.request_id == "req-001"
        assert token.device_id == "switch-01"
        assert token.signature is not None

    def test_verify_valid_token(self):
        """Test valid token verification"""
        shared_secret = secrets.token_bytes(32)
        manager = ExecutionTokenManager("regional_cntl_1", shared_secret)

        token = manager.issue_token(
            request_id="req-001",
            device_id="switch-01"
        )

        valid, error = manager.verify_token(token, "switch-01")

        assert valid
        assert error is None

    def test_verify_tampered_token(self):
        """Test tampered token detection"""
        shared_secret = secrets.token_bytes(32)
        manager = ExecutionTokenManager("regional_cntl_1", shared_secret)

        token = manager.issue_token(
            request_id="req-001",
            device_id="switch-01"
        )

        token.device_id = "switch-02"

        valid, error = manager.verify_token(token, "switch-02")

        assert not valid
        assert "Invalid signature" in error

    def test_verify_expired_token(self):
        """Test expired token detection"""
        shared_secret = secrets.token_bytes(32)
        manager = ExecutionTokenManager("regional_cntl_1", shared_secret)

        token = manager.issue_token(
            request_id="req-001",
            device_id="switch-01",
            validity_minutes=0
        )

        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        token.signature = manager._sign_token(token)

        valid, error = manager.verify_token(token)

        assert not valid
        assert "expired" in error.lower()

    def test_replay_prevention(self):
        """Test token replay prevention"""
        shared_secret = secrets.token_bytes(32)
        manager = ExecutionTokenManager("regional_cntl_1", shared_secret)

        token = manager.issue_token(
            request_id="req-001",
            device_id="switch-01"
        )

        valid1, _ = manager.verify_token(token, "switch-01")
        assert valid1

        valid2, error2 = manager.verify_token(token, "switch-01")
        assert not valid2
        assert "already used" in error2.lower()


class TestConfigStateMachine:
    """Test configuration state machine"""

    def test_initial_state(self):
        """Test initial state"""
        sm = ConfigStateMachine("config-001")
        assert sm.current_state == ConfigState.DRAFT

    def test_valid_transition(self):
        """Test valid state transition"""
        sm = ConfigStateMachine("config-001")

        success = sm.transition(
            ConfigState.PENDING_APPROVAL,
            "local_cntl_001",
            "Submitted for approval"
        )

        assert success
        assert sm.current_state == ConfigState.PENDING_APPROVAL

    def test_invalid_transition(self):
        """Test invalid state transition"""
        sm = ConfigStateMachine("config-001")

        success = sm.transition(
            ConfigState.EXECUTED,
            "local_cntl_001"
        )

        assert not success
        assert sm.current_state == ConfigState.DRAFT

    def test_transition_history(self):
        """Test transition history tracking"""
        sm = ConfigStateMachine("config-001")

        sm.transition(ConfigState.PENDING_APPROVAL, "controller1")
        sm.transition(ConfigState.APPROVED, "controller2")

        history = sm.get_transition_history()

        assert len(history) == 2
        assert history[0]['to_state'] == ConfigState.PENDING_APPROVAL.value
        assert history[1]['to_state'] == ConfigState.APPROVED.value


class TestRollbackManager:
    """Test rollback manager"""

    def test_create_backup(self):
        """Test backup creation"""
        manager = RollbackManager("local_cntl_001")

        config = ["vlan 100", "name Engineering"]

        backup = manager.create_backup(
            device_id="switch-01",
            config_lines=config
        )

        assert backup.device_id == "switch-01"
        assert backup.config_lines == config

    def test_get_latest_backup(self):
        """Test getting latest backup"""
        manager = RollbackManager("local_cntl_001")

        manager.create_backup("switch-01", ["config v1"])
        import time
        time.sleep(0.01)
        backup2 = manager.create_backup("switch-01", ["config v2"])

        latest = manager.get_latest_backup("switch-01")

        assert latest.backup_id == backup2.backup_id

    def test_rollback(self):
        """Test rollback execution"""
        manager = RollbackManager("local_cntl_001")

        config = ["vlan 100"]
        backup = manager.create_backup("switch-01", config)

        event = manager.rollback(
            config_id="config-001",
            device_id="switch-01",
            backup_id=backup.backup_id,
            reason="Execution failed"
        )

        assert event.success
        assert event.device_id == "switch-01"

    def test_auto_rollback(self):
        """Test automatic rollback"""
        manager = RollbackManager("local_cntl_001")

        manager.create_backup("switch-01", ["vlan 100"])

        event = manager.auto_rollback(
            config_id="config-001",
            device_id="switch-01",
            failure_reason="Device rejected configuration"
        )

        assert event is not None
        assert event.success


class TestAuditTrail:
    """Test audit trail system"""

    def test_log_config_created(self):
        """Test configuration creation logging"""
        audit = AuditTrail("local_cntl_001")

        event = audit.log_config_created(
            config_id="config-001",
            device_id="switch-01",
            requester_id="local_cntl_001",
            sensitivity="MEDIUM"
        )

        assert event.event_type == AuditEventType.CONFIG_CREATED
        assert event.result == "SUCCESS"

    def test_query_events(self):
        """Test event querying"""
        audit = AuditTrail("local_cntl_001")

        audit.log_config_created("config-001", "switch-01", "user1", "LOW")
        audit.log_config_created("config-002", "switch-02", "user2", "HIGH")

        user1_events = audit.query_events(actor_id="user1")

        assert len(user1_events) == 1
        assert user1_events[0].resource_id == "config-001"

    def test_get_config_history(self):
        """Test configuration history retrieval"""
        audit = AuditTrail("local_cntl_001")

        audit.log_config_created("config-001", "switch-01", "user1", "MEDIUM")
        audit.log_config_submitted("config-001", "user1")
        audit.log_config_approved("config-001", "approver1")

        history = audit.get_config_history("config-001")

        assert len(history) == 3

    def test_generate_report(self):
        """Test audit report generation"""
        audit = AuditTrail("local_cntl_001")

        audit.log_config_created("config-001", "switch-01", "user1", "LOW")
        audit.log_config_approved("config-001", "approver1")

        report = audit.generate_report()

        assert report['total_events'] == 2
        assert 'CONFIG_CREATED' in report['by_type']
        assert report['by_result']['SUCCESS'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
