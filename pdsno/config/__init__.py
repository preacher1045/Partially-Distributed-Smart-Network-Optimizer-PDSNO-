# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Configuration Approval Module (Phase 7)

Exports all configuration approval components:
- Sensitivity classification
- Approval workflow engine
- Execution tokens
- Configuration state machine
- Rollback manager
- Audit trail
"""

from pdsno.config.sensitivity_classifier import ConfigSensitivityClassifier, SensitivityLevel
from pdsno.config.approval_engine import ApprovalWorkflowEngine, ApprovalState, ApprovalRequest
from pdsno.config.execution_token import ExecutionToken, ExecutionTokenManager
from pdsno.config.config_state import ConfigState, ConfigStateMachine, ConfigurationRecord
from pdsno.config.rollback_manager import RollbackManager
from pdsno.config.audit_trail import AuditTrail, AuditEvent, AuditEventType

__all__ = [
    "ConfigSensitivityClassifier",
    "SensitivityLevel",
    "ApprovalWorkflowEngine",
    "ApprovalState",
    "ApprovalRequest",
    "ExecutionToken",
    "ExecutionTokenManager",
    "ConfigState",
    "ConfigStateMachine",
    "ConfigurationRecord",
    "RollbackManager",
    "AuditTrail",
    "AuditEvent",
    "AuditEventType"
]
