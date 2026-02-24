#!/usr/bin/env python3
"""
Complete Configuration Approval Workflow Simulation

Demonstrates Phase 7 end-to-end:
1. Configuration creation and sensitivity classification
2. Approval workflow based on sensitivity
3. Execution token issuance
4. Configuration state transitions
5. Backup and rollback capability
6. Complete audit trail

Simulates: LOCAL -> REGIONAL -> GLOBAL approval hierarchy
"""

import logging
import secrets

from pdsno.config import (
    ConfigSensitivityClassifier,
    SensitivityLevel,
    ApprovalWorkflowEngine,
    ApprovalState,
    ExecutionTokenManager,
    ConfigurationRecord,
    ConfigState,
    RollbackManager,
    AuditTrail
)


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Run complete approval workflow simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("PDSNO Phase 7 - Configuration Approval Workflow Simulation")
    logger.info("=" * 70)

    # Initialize components
    logger.info("\n[1/10] Initializing components...")

    classifier = ConfigSensitivityClassifier()

    lc_approval = ApprovalWorkflowEngine("local_cntl_001", "local")
    rc_approval = ApprovalWorkflowEngine("regional_cntl_zone-A_1", "regional")

    shared_secret = secrets.token_bytes(32)
    token_manager = ExecutionTokenManager("regional_cntl_zone-A_1", shared_secret)

    rollback_mgr = RollbackManager("local_cntl_001")
    audit_trail = AuditTrail("local_cntl_001")

    logger.info("✓ All components initialized")

    # Scenario 1: LOW sensitivity (auto-approved)
    logger.info("\n[2/10] Scenario 1: LOW Sensitivity Configuration")
    logger.info("-" * 70)

    low_config = [
        "interface gigabitethernet0/1",
        "description Updated link description",
        "!"
    ]

    sensitivity = classifier.classify(low_config)
    logger.info(f"Configuration classified as: {sensitivity.value}")

    config_low = ConfigurationRecord(
        config_id="config-low-001",
        device_id="switch-core-01",
        config_lines=low_config,
        requester_id="local_cntl_001"
    )

    audit_trail.log_config_created(
        config_low.config_id,
        config_low.device_id,
        config_low.requester_id,
        sensitivity.value
    )

    request_low = lc_approval.create_request(
        device_id=config_low.device_id,
        config_lines=config_low.config_lines,
        sensitivity=sensitivity
    )

    config_low.approval_request_id = request_low.request_id

    lc_approval.submit_request(request_low.request_id)

    if request_low.state == ApprovalState.APPROVED:
        logger.info("✓ LOW sensitivity: Auto-approved")
        config_low.transition(ConfigState.APPROVED, "local_cntl_001", "Auto-approved")
        audit_trail.log_config_approved(config_low.config_id, "local_cntl_001", auto_approved=True)

    # Scenario 2: MEDIUM sensitivity (regional approval)
    logger.info("\n[3/10] Scenario 2: MEDIUM Sensitivity Configuration")
    logger.info("-" * 70)

    medium_config = [
        "vlan 100",
        "name Engineering_Lab",
        "interface gigabitethernet0/5",
        "switchport mode access",
        "switchport access vlan 100"
    ]

    sensitivity = classifier.classify(medium_config)
    logger.info(f"Configuration classified as: {sensitivity.value}")

    config_medium = ConfigurationRecord(
        config_id="config-medium-001",
        device_id="switch-access-02",
        config_lines=medium_config,
        requester_id="local_cntl_001"
    )

    audit_trail.log_config_created(
        config_medium.config_id,
        config_medium.device_id,
        config_medium.requester_id,
        sensitivity.value
    )

    request_medium = lc_approval.create_request(
        device_id=config_medium.device_id,
        config_lines=config_medium.config_lines,
        sensitivity=sensitivity
    )

    config_medium.approval_request_id = request_medium.request_id
    config_medium.transition(ConfigState.PENDING_APPROVAL, "local_cntl_001", "Submitted")

    lc_approval.submit_request(request_medium.request_id)
    audit_trail.log_config_submitted(config_medium.config_id, "local_cntl_001")

    logger.info(f"Request state: {request_medium.state.value}")

    logger.info("Regional Controller reviewing...")

    rc_approval.approve_request(
        request_medium.request_id,
        "regional_cntl_zone-A_1"
    )

    if request_medium.state == ApprovalState.APPROVED:
        logger.info("✓ MEDIUM sensitivity: Approved by Regional Controller")
        config_medium.transition(ConfigState.APPROVED, "regional_cntl_zone-A_1", "Regional approval")
        audit_trail.log_config_approved(config_medium.config_id, "regional_cntl_zone-A_1")

    # Scenario 3: HIGH sensitivity (global approval)
    logger.info("\n[4/10] Scenario 3: HIGH Sensitivity Configuration")
    logger.info("-" * 70)

    high_config = [
        "router bgp 65001",
        "neighbor 10.10.10.1 remote-as 65002",
        "network 192.168.100.0 mask 255.255.255.0"
    ]

    sensitivity = classifier.classify(high_config)
    details = classifier.classify_with_details(high_config)

    logger.info(f"Configuration classified as: {sensitivity.value}")
    logger.info(f"Reasoning: {details['reasoning']}")
    logger.info(f"High-risk commands: {details['high_risk_commands']}")

    config_high = ConfigurationRecord(
        config_id="config-high-001",
        device_id="router-core-01",
        config_lines=high_config,
        requester_id="local_cntl_001"
    )

    audit_trail.log_config_created(
        config_high.config_id,
        config_high.device_id,
        config_high.requester_id,
        sensitivity.value
    )

    logger.info("HIGH sensitivity requires Global Controller approval")

    # Issue execution token for MEDIUM config
    logger.info("\n[5/10] Issuing execution token...")
    logger.info("-" * 70)

    token = token_manager.issue_token(
        request_id=config_medium.approval_request_id,
        device_id=config_medium.device_id,
        validity_minutes=15
    )

    config_medium.execution_token_id = token.token_id

    logger.info(f"✓ Token issued: {token.token_id[:16]}...")
    logger.info("  Valid for: 15 minutes")
    logger.info(f"  Device: {token.device_id}")

    audit_trail.log_token_issued(
        token.token_id,
        config_medium.config_id,
        token.device_id,
        "regional_cntl_zone-A_1",
        15
    )

    # Verify token before execution
    logger.info("\n[6/10] Verifying execution token...")

    valid, error = token_manager.verify_token(token, config_medium.device_id)

    if valid:
        logger.info("✓ Token verified successfully")
        audit_trail.log_token_verified(
            token.token_id,
            token.device_id,
            "local_cntl_001"
        )
    else:
        logger.error(f"✗ Token verification failed: {error}")
        audit_trail.log_token_rejected(
            token.token_id,
            token.device_id,
            "local_cntl_001",
            error
        )
        return 1

    # Create backup before execution
    logger.info("\n[7/10] Creating pre-execution backup...")

    current_config = [
        "interface gigabitethernet0/5",
        "switchport mode trunk",
        "switchport trunk allowed vlan 1,10,20"
    ]

    backup = rollback_mgr.create_backup(
        device_id=config_medium.device_id,
        config_lines=current_config,
        metadata={'pre_change': config_medium.config_id}
    )

    config_medium.backup_config = current_config

    logger.info(f"✓ Backup created: {backup.backup_id}")

    # Execute configuration
    logger.info("\n[8/10] Executing configuration...")
    logger.info("-" * 70)

    config_medium.transition(ConfigState.EXECUTING, "local_cntl_001", "Executing with valid token")

    # Simulate successful execution
    execution_success = True

    if execution_success:
        config_medium.transition(ConfigState.EXECUTED, "local_cntl_001", "Execution successful")
        config_medium.execution_result = {
            'success': True,
            'lines_applied': len(config_medium.config_lines),
            'device_response': 'OK'
        }

        audit_trail.log_config_executed(
            config_medium.config_id,
            config_medium.device_id,
            "local_cntl_001",
            token.token_id
        )

        logger.info("✓ Configuration executed successfully")
    else:
        config_medium.transition(ConfigState.FAILED, "local_cntl_001", "Execution failed")
        audit_trail.log_config_failed(
            config_medium.config_id,
            config_medium.device_id,
            "local_cntl_001",
            "Device rejected configuration"
        )

        logger.error("✗ Configuration execution failed")

    # Simulate rollback scenario
    logger.info("\n[9/10] Demonstrating rollback capability...")
    logger.info("-" * 70)

    logger.info("Simulating configuration failure requiring rollback...")

    event = rollback_mgr.rollback(
        config_id=config_medium.config_id,
        device_id=config_medium.device_id,
        backup_id=backup.backup_id,
        reason="Demonstration of rollback capability"
    )

    if event.success:
        logger.info("✓ Rollback successful")
        config_medium.transition(ConfigState.ROLLED_BACK, "local_cntl_001", "Rolled back")

        audit_trail.log_config_rolled_back(
            config_medium.config_id,
            config_medium.device_id,
            "local_cntl_001",
            backup.backup_id,
            event.reason
        )
    else:
        logger.error(f"✗ Rollback failed: {event.error}")

    # Generate audit report
    logger.info("\n[10/10] Generating audit report...")
    logger.info("-" * 70)

    report = audit_trail.generate_report()

    logger.info(f"Total audit events: {report['total_events']}")
    logger.info("Events by type:")
    for event_type, count in report['by_type'].items():
        logger.info(f"  {event_type}: {count}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("Phase 7 Simulation Complete!")
    logger.info("=" * 70)

    logger.info("\nFeatures Demonstrated:")
    logger.info("  ✓ Sensitivity classification (LOW/MEDIUM/HIGH)")
    logger.info("  ✓ Automatic approval for LOW sensitivity")
    logger.info("  ✓ Regional approval for MEDIUM sensitivity")
    logger.info("  ✓ Global approval required for HIGH sensitivity")
    logger.info("  ✓ Cryptographic execution tokens")
    logger.info("  ✓ Token verification before execution")
    logger.info("  ✓ Configuration state machine")
    logger.info("  ✓ Pre-execution backup")
    logger.info("  ✓ Rollback capability")
    logger.info("  ✓ Complete audit trail")

    logger.info("\nConfiguration Lifecycle:")
    logger.info("  DRAFT → PENDING_APPROVAL → APPROVED →")
    logger.info("  EXECUTING → EXECUTED → [ROLLED_BACK if needed]")

    logger.info("\nApproval Hierarchy:")
    logger.info("  LOCAL:    Can execute LOW")
    logger.info("  REGIONAL: Can approve MEDIUM")
    logger.info("  GLOBAL:   Can approve HIGH")

    logger.info("\nAudit Trail:")
    logger.info(f"  {report['total_events']} events logged")
    logger.info(f"  {report['unique_actors']} unique actors")
    logger.info("  Complete configuration lifecycle tracked")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
