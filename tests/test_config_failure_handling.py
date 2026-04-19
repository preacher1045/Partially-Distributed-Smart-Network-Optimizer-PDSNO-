# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Failure Handling Tests for Config Approval

Tests the failure path through the approval loop:
  LC proposal → RC approve + lock → RC dispatch → LC execution failure
  → RC receives FAILED result → lock released → NIB updated

NOTE ON ROLLBACK:
  True rollback (ROLLED_BACK state) requires _execute_config_change to attempt
  an actual device change and then undo it on failure. That logic is deferred to
  Phase C when real device execution is introduced. What is tested here is the
  failure cleanup path — the path that must work correctly before rollback can
  be layered on top of it.

  Specifically we verify:
    - Config reaches FAILED in NIB (not left as EXECUTING or APPROVED)
    - Device lock is released on failure (not left held indefinitely)
    - Audit event is written for the failure
    - A subsequent proposal for the same device is accepted (lock is actually gone)
"""

from pathlib import Path
from unittest.mock import patch

from pdsno.communication.message_bus import MessageBus
from pdsno.communication.message_format import MessageType
from pdsno.controllers.context_manager import ContextManager
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.datastore import ConfigStatus, LockType, NIBStore


# ── Shared factory ────────────────────────────────────────────────────────────

def _build_controllers(tmp_path: Path, register_execution_handler: bool = True):
    """
    Identical factory to test_config_approval_controllers.py so tests
    are consistent. Both LC and RC share a single NIB instance backed
    by the same SQLite file — the same arrangement the distributed
    runtime uses via the shared sim_distributed volume.
    
    """
    nib = NIBStore(str(tmp_path / "pdsno_test.db"))
    bus = MessageBus()

    rc = RegionalController(
        temp_id="regional_cntl_zone-A_1",
        region="zone-A",
        context_manager=ContextManager(str(tmp_path / "rc_context.yaml")),
        nib_store=nib,
        message_bus=bus,
    )

    lc = LocalController(
        controller_id="local_cntl_zone-A_1",
        region="zone-A",
        subnet="172.20.20.0/24",
        context_manager=ContextManager(str(tmp_path / "lc_context.yaml")),
        nib_store=nib,
        message_bus=bus,
        simulate=True,
    )

    bus.register_controller(
        rc.controller_id,
        {
            MessageType.CONFIG_PROPOSAL: rc.handle_config_proposal,
            MessageType.EXECUTION_RESULT: rc.handle_execution_result,
        },
    )

    if register_execution_handler:
        bus.register_controller(
            lc.controller_id,
            {
                MessageType.EXECUTION_INSTRUCTION: lc.handle_execution_instruction,
            },
        )

    return lc, rc, nib


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_execution_failure_marks_config_failed(tmp_path) -> None:
    """
    When _execute_config_change returns success=False, the config must
    reach ConfigStatus.FAILED in the NIB.

    Why this matters: if the failure path doesn't write FAILED, the config
    stays as EXECUTING or APPROVED indefinitely, which blocks any future
    proposal for the same device and corrupts the audit trail.
    """
    lc, rc, nib = _build_controllers(tmp_path)

    with patch.object(
        lc,
        "_execute_config_change",
        return_value={"success": False, "reason": "SIMULATED_DEVICE_REJECTION"},
    ):
        result = lc.submit_config_proposal(
            rc_id=rc.controller_id,
            device_id="nib-dev-failure-001",
            config_lines=["vlan 200", "name FailureTest"],
        )

    assert result["status"] == "submitted", f"Unexpected status: {result}"

    proposal_id = result["proposal_id"]
    config = nib.get_config(proposal_id)

    assert config is not None, "Config record missing from NIB after failure"
    assert config.status == ConfigStatus.FAILED, (
        f"Expected FAILED, got {config.status}. "
        "The failure path did not write terminal state to NIB."
    )


def test_execution_failure_releases_device_lock(tmp_path):
    """
    After an execution failure the device lock must be released.

    Why this matters: a lock that survives a failure permanently blocks
    all future proposals for that device. The only recovery would be
    manual operator intervention or lock TTL expiry. Neither is acceptable
    for a deterministic failure.
    """
    lc, rc, nib = _build_controllers(tmp_path)

    with patch.object(
        lc,
        "_execute_config_change",
        return_value={"success": False, "reason": "SIMULATED_DEVICE_REJECTION"},
    ):
        result = lc.submit_config_proposal(
            rc_id=rc.controller_id,
            device_id="nib-dev-lock-release-001",
            config_lines=["vlan 201", "name LockReleaseTest"],
        )

    assert result["status"] == "submitted"

    # Lock must be gone — check_lock returns None when no active lock exists
    active_lock = nib.check_lock("nib-dev-lock-release-001", LockType.CONFIG_LOCK)
    assert active_lock is None, (
        f"Device lock still held after execution failure: {active_lock}. "
        "RC did not release the lock on the failure path."
    )


def test_failed_device_accepts_subsequent_proposal(tmp_path):
    """
    A device whose previous proposal failed must accept a new proposal
    immediately — no manual intervention required.

    Why this matters: this is the practical consequence of correct lock
    release. It's not enough to assert the lock field is None; we need
    to prove the system actually works for the next operation. A lock
    that is logically released but physically still present would only
    be caught by this test.
    """
    lc, rc, nib = _build_controllers(tmp_path)
    device_id = "nib-dev-retry-001"

    # First proposal — force failure
    with patch.object(
        lc,
        "_execute_config_change",
        return_value={"success": False, "reason": "SIMULATED_DEVICE_REJECTION"},
    ):
        first_result = lc.submit_config_proposal(
            rc_id=rc.controller_id,
            device_id=device_id,
            config_lines=["vlan 202", "name RetryTest"],
        )

    assert first_result["status"] == "submitted"
    first_config = nib.get_config(first_result["proposal_id"])
    assert first_config.status == ConfigStatus.FAILED

    # Second proposal — should succeed without any lock conflict
    second_result = lc.submit_config_proposal(
        rc_id=rc.controller_id,
        device_id=device_id,
        config_lines=["vlan 202", "name RetryTestFixed"],
    )

    assert second_result["status"] == "submitted"
    assert second_result["response"]["decision"] == "APPROVE", (
        f"Second proposal was not approved: {second_result['response']}. "
        "Lock from failed first proposal may still be held."
    )

    second_config = nib.get_config(second_result["proposal_id"])
    assert second_config is not None
    assert second_config.status == ConfigStatus.EXECUTED


def test_execution_failure_writes_audit_event(tmp_path):
    """
    An execution failure must produce an audit event in the NIB Event Log.

    Why this matters: the Event Log is the tamper-evident record of everything
    that happened. A failure that leaves no audit trail is a governance gap —
    an operator reviewing the log would have no record that the execution was
    attempted and failed.
    """
    lc, rc, nib = _build_controllers(tmp_path)
    device_id = "nib-dev-audit-001"

    with patch.object(
        lc,
        "_execute_config_change",
        return_value={"success": False, "reason": "SIMULATED_DEVICE_REJECTION"},
    ):
        result = lc.submit_config_proposal(
            rc_id=rc.controller_id,
            device_id=device_id,
            config_lines=["vlan 203", "name AuditTest"],
        )

    proposal_id = result["proposal_id"]

    # Query the event log for this proposal
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "pdsno_test.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events WHERE subject = ? ORDER BY timestamp",
        (proposal_id,),
    ).fetchall()
    conn.close()

    assert len(rows) > 0, (
        f"No audit events found for proposal {proposal_id}. "
        "The failure path did not write to the Event Log."
    )

    # At least one event should record the failure decision
    decisions = [r["decision"] for r in rows]
    assert any(d in ("FAILED", "EXECUTION_FAILED") for d in decisions), (
        f"No FAILED decision recorded in audit events. Decisions found: {decisions}. "
        "The audit trail does not reflect the execution failure."
    )


def test_missing_execution_handler_denies_and_releases_lock(tmp_path):
    """
    When RC cannot dispatch the execution instruction (LC has no handler
    registered), the proposal must be denied and the lock released.

    This is the existing test_dispatch_failure_releases_lock_and_marks_failed
    scenario from test_config_approval_controllers.py, included here for
    completeness of the failure handling suite.

    It tests a different failure mode: the dispatch itself fails rather
    than the execution inside LC. Both paths must clean up correctly.
    """
    # Build without registering execution handler on LC
    lc, rc, nib = _build_controllers(tmp_path, register_execution_handler=False)

    result = lc.submit_config_proposal(
        rc_id=rc.controller_id,
        device_id="nib-dev-dispatch-fail-001",
        config_lines=["vlan 204", "name DispatchFailTest"],
    )

    assert result["status"] == "submitted"
    assert result["response"]["decision"] == "DENY"
    assert result["response"]["reason"] == "EXECUTION_DISPATCH_FAILED"

    config = nib.get_config(result["proposal_id"])
    assert config is not None
    assert config.status == ConfigStatus.FAILED

    # Lock must be released even when dispatch fails
    active_lock = nib.check_lock("nib-dev-dispatch-fail-001", LockType.CONFIG_LOCK)
    assert active_lock is None, (
        "Lock still held after dispatch failure. "
        "RC did not release lock on the EXECUTION_DISPATCH_FAILED path."
    )
