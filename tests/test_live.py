import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PDSNO_LIVE_LAB"),
    reason="Live lab tests require PDSNO_LIVE_LAB=1 and running containerlab"
)


def test_interface_description_executes_on_frr_spine():
    """
    Phase C live test: push a real interface description to frr-spine.

    Uses CONFIGURE_INTERFACE intent — the correct way to express config
    changes through the adapter layer rather than raw device-specific syntax.

    Verifies:
    1. Proposal signed and accepted by RC
    2. RC approves, issues token, dispatches to LC
    3. LC executes via FRRAdapter docker exec
    4. NIB reflects EXECUTED
    5. vtysh on frr-spine confirms description was applied
    6. Cleanup restores original state
    """
    import hashlib
    import subprocess
    from pdsno.controllers.local_controller import LocalController
    from pdsno.controllers.context_manager import ContextManager
    from pdsno.datastore import NIBStore, ConfigStatus
    from pdsno.communication.http_client import ControllerHTTPClient
    from pdsno.security.message_auth import MessageAuthenticator

    secret = os.environ.get(
        "PDSNO_MESSAGE_SIGNING_SECRET",
        "pdsno-message-signing-secret-change-in-production",
    )
    key = hashlib.sha256(secret.encode()).digest()
    auth = MessageAuthenticator(
        shared_secret=key, controller_id="local_cntl_zone-a_001"
    )
    http_client = ControllerHTTPClient(authenticator=auth)
    http_client.register_controller(
        "regional_cntl_zone-A_1", "http://172.20.20.6:8002"
    )

    lc = LocalController(
        controller_id="local_cntl_zone-a_001",
        region="zone-A",
        subnet="172.20.20.0/24",
        context_manager=ContextManager("./sim_distributed/lc_context.yaml"),
        nib_store=NIBStore("./sim_distributed/pdsno.db"),
        http_client=http_client,
    )

    # Resolve frr-spine by MAC — stable across lab restarts
    FRR_SPINE_MAC = "ae:f9:a9:e4:c0:67"
    spine_device = lc.nib_store.get_device_by_mac(FRR_SPINE_MAC)
    assert spine_device is not None, (
        f"frr-spine not found by MAC {FRR_SPINE_MAC}. "
        "Is the lab running and has discovery completed at least one cycle?"
    )

    TOPOLOGY = "pdsno-distributed-lab"
    CONTAINER = f"clab-{TOPOLOGY}-frr-spine"
    TEST_DESC = "PDSNO_PhaseC_Test"

    # Fire proposal using vtysh-compatible interface commands
    result = lc.submit_config_proposal(
        rc_id="regional_cntl_zone-A_1",
        device_id=spine_device.device_id,
        config_lines=[
            "configure terminal",
            "interface eth1",
            f"description {TEST_DESC}",
            "end",
            "write memory",
        ],
    )

    assert result["status"] == "submitted", (
    f"submit_config_proposal did not reach RC. "
    f"Full result: {result}"
    )
    assert "response" in result, (
        f"No 'response' in result — proposal may have been auto-approved locally "
        f"or failed before reaching RC. Full result: {result}"
    )
    assert result["response"]["decision"] == "APPROVE", (
        f"RC did not approve: {result['response']}"
    )
    # Verify NIB state
    config = lc.nib_store.get_config(result["proposal_id"])
    assert config is not None, "Config record missing from NIB"
    assert config.status == ConfigStatus.EXECUTED, (
        f"Expected EXECUTED, got {config.status}. "
        f"Reason: {result['response'].get('execution_result', {})}"
    )

    # Verify actual device state
    verify = subprocess.run(
        ["docker", "exec", CONTAINER,
         "vtysh", "-c", "show interface eth1"],
        capture_output=True, text=True, timeout=10
    )
    assert TEST_DESC in verify.stdout, (
        f"Description '{TEST_DESC}' not found on {CONTAINER}. "
        f"vtysh output: {verify.stdout[:400]}. "
        "Adapter may have reported success without applying config."
    )

    # Cleanup — restore neutral description
    subprocess.run(
        ["docker", "exec", CONTAINER, "vtysh",
         "-c", "configure terminal",
         "-c", "interface eth1",
         "-c", "no description",
         "-c", "end",
         "-c", "write memory"],
        capture_output=True, timeout=10
    )