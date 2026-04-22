import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PDSNO_LIVE_LAB"),
    reason="Live lab tests require PDSNO_LIVE_LAB=1 and running containerlab"
)


def test_vlan_proposal_executes_on_frr_spine():
    """
    Phase C live test: fire a real VLAN proposal against frr-spine.

    Verifies:
    1. Proposal is accepted and approved by RC
    2. NIB reflects EXECUTED after the flow completes
    3. vtysh on frr-spine actually shows the VLAN was created
    4. Cleanup: VLAN is removed after test so reruns are clean
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
    FRR_SPINE_MAC = "06:6f:65:f7:66:dc"
    spine_device = lc.nib_store.get_device_by_mac(FRR_SPINE_MAC)
    assert spine_device is not None, (
        f"frr-spine not found by MAC {FRR_SPINE_MAC}. "
        "Is the lab running and has discovery completed at least one cycle?"
    )

    TOPOLOGY = "pdsno-distributed-lab"
    CONTAINER = f"clab-{TOPOLOGY}-frr-spine"
    TEST_VLAN = 777  # Use an obscure VLAN ID unlikely to conflict

    # Clean up from any previous failed run
    subprocess.run(
        ["docker", "exec", CONTAINER, "vtysh", "-c",
         f"configure terminal\nno vlan {TEST_VLAN}\nend\nwrite memory"],
        capture_output=True, timeout=10
    )

    # Fire the proposal
    result = lc.submit_config_proposal(
        rc_id="regional_cntl_zone-A_1",
        device_id=spine_device.device_id,
        config_lines=[f"vlan {TEST_VLAN}", f"name PhaseC_Test"],
    )

    assert result["status"] == "submitted", f"Unexpected: {result}"
    assert result["response"]["decision"] == "APPROVE", (
        f"RC did not approve: {result['response']}"
    )

    proposal_id = result["proposal_id"]

    # Verify NIB state
    config = lc.nib_store.get_config(proposal_id)
    assert config is not None, "Config record missing from NIB"
    assert config.status == ConfigStatus.EXECUTED, (
        f"Expected EXECUTED, got {config.status}. "
        f"Reason: {result['response'].get('execution_result', {})}"
    )

    # Verify actual device state — the VLAN must exist on frr-spine
    verify = subprocess.run(
        ["docker", "exec", CONTAINER, "vtysh", "-c",
         f"show vlan id {TEST_VLAN}"],
        capture_output=True, text=True, timeout=10
    )
    assert str(TEST_VLAN) in verify.stdout, (
        f"VLAN {TEST_VLAN} not found on {CONTAINER} after EXECUTED. "
        f"vtysh output: {verify.stdout[:300]}. "
        "The adapter may have reported success without actually pushing config."
    )

    # Cleanup — remove test VLAN
    subprocess.run(
        ["docker", "exec", CONTAINER, "vtysh", "-c",
         f"configure terminal\nno vlan {TEST_VLAN}\nend\nwrite memory"],
        capture_output=True, timeout=10
    )