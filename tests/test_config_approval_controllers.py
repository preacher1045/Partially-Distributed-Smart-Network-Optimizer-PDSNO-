# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""Controller-level tests for config approval proposal/execution flow."""

from pathlib import Path

from unittest.mock import patch
from pdsno.communication.message_bus import MessageBus
from pdsno.communication.message_format import MessageType
from pdsno.controllers.context_manager import ContextManager
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.datastore import ConfigStatus, LockType, NIBStore

def _seed_device(nib: NIBStore, device_id: str, ip: str = "172.20.20.11"):
    """Insert a minimal device record so LC can look it up during execution."""
    from pdsno.datastore.models import Device, DeviceStatus
    from datetime import datetime, timezone
    device = Device(
        device_id=device_id,
        ip_address=ip,
        mac_address=f"aa:bb:cc:dd:ee:{device_id[-2:]}",
        vendor="frr",
        status=DeviceStatus.ACTIVE,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        local_controller="local_cntl_zone-A_1",
        region="zone-A",
    )
    nib.upsert_device(device)


def _build_controllers(tmp_path: Path, register_execution_handler: bool = True):
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


def test_medium_proposal_executes_end_to_end(tmp_path):
    lc, rc, nib = _build_controllers(tmp_path)
    
    # Seed device so LC can find it during execution.
    # IP/MAC can be arbitrary since we're simulating.
    with patch.object(
        lc,
        "_execute_config_change",
        return_value={"success": True, "applied_lines": 5},
    ):
        result = lc.submit_config_proposal(
            rc_id=rc.controller_id,
            device_id="nib-dev-001",
            config_lines=[
                "vlan 120",
                "name BlueTeam",
                "interface ethernet0/1",
                "switchport mode access",
                "switchport access vlan 120",
            ],
        )

    assert result["status"] == "submitted"
    assert result["response"]["decision"] == "APPROVE"

    proposal_id = result["proposal_id"]
    config = nib.get_config(proposal_id)
    assert config is not None
    assert config.status == ConfigStatus.EXECUTED


def test_high_proposal_escalates(tmp_path):
    lc, rc, nib = _build_controllers(tmp_path)
    device_id = "nib-dev-001"
    _seed_device(nib, device_id)

    result = lc.submit_config_proposal(
        rc_id=rc.controller_id,
        device_id="nib-dev-002",
        config_lines=[
            "router bgp 65000",
            "neighbor 10.0.0.1 remote-as 65001",
        ],
    )

    assert result["status"] == "submitted"
    assert result["response"]["decision"] == "ESCALATE"

    proposal_id = result["proposal_id"]
    config = nib.get_config(proposal_id)
    assert config is not None
    assert config.status == ConfigStatus.PENDING

    # RC should not hold lock after escalation-only response.
    assert nib.check_lock("nib-dev-002", LockType.CONFIG_LOCK) is None


def test_dispatch_failure_releases_lock_and_marks_failed(tmp_path):
    lc, rc, nib = _build_controllers(tmp_path, register_execution_handler=False)
    device_id = "nib-dev-001"
    _seed_device(nib, device_id)

    result = lc.submit_config_proposal(
        rc_id=rc.controller_id,
        device_id="nib-dev-003",
        config_lines=[
            "vlan 303",
            "name DispatchFailure",
            "interface ethernet0/3",
            "switchport mode access",
            "switchport access vlan 303",
        ],
    )

    assert result["status"] == "submitted"
    assert result["response"]["decision"] == "DENY"
    assert result["response"]["reason"] == "EXECUTION_DISPATCH_FAILED"

    proposal_id = result["proposal_id"]
    config = nib.get_config(proposal_id)
    assert config is not None
    assert config.status == ConfigStatus.FAILED
    assert nib.check_lock("nib-dev-003", LockType.CONFIG_LOCK) is None


def test_proposal_denied_when_device_lock_held(tmp_path):
    lc, rc, nib = _build_controllers(tmp_path)
    device_id = "nib-dev-001"
    _seed_device(nib, device_id)

    lock_result = nib.acquire_lock(
        subject_id="nib-dev-009",
        lock_type=LockType.CONFIG_LOCK,
        held_by="other_controller",
        ttl_seconds=600,
        associated_request="existing-proposal",
    )
    assert lock_result.success

    result = lc.submit_config_proposal(
        rc_id=rc.controller_id,
        device_id="nib-dev-009",
        config_lines=[
            "vlan 909",
            "name LockedDeviceTest",
            "interface ethernet0/9",
            "switchport mode access",
            "switchport access vlan 909",
        ],
    )

    assert result["status"] == "submitted"
    assert result["response"]["decision"] == "DENY"
    assert "LOCK_HELD_BY_" in result["response"]["reason"]
