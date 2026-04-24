
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
FRR Adapter

Executes configuration changes on FRRouting (FRR) containers.
Uses docker exec to invoke vtysh — appropriate for containerlab environments
where the LC and FRR nodes share the same Docker host.

Phase C implementation: real execution via subprocess docker exec.
Phase D (future): replace with Netmiko SSH when FRR containers have
SSH servers configured, or with NETCONF when FRR NETCONF support matures.
"""

import subprocess
import logging
from typing import Dict, List, Optional

from pdsno.adapters.base_adapter import VendorAdapter
from pdsno.adapters import ConfigIntent, IntentType


class FRRAdapter(VendorAdapter):
    """
    Adapter for FRRouting devices in containerlab environments.

    Execution model: docker exec → vtysh -c <command>
    This requires the Python process running the LC to have access
    to the Docker socket (/var/run/docker.sock), which is true when
    running on the containerlab host.

    Container name convention: clab-<topology>-<node-name>
    Default topology: pdsno-distributed-lab
    """

    VENDOR = "frr"
    PLATFORM = "linux"

    # Default topology name — matches containerlab topology file name
    TOPOLOGY_NAME = "pdsno-distributed-lab"

    def __init__(self, device_info: Optional[Dict] = None):
        self._device_info = device_info or {}
        self.logger = logging.getLogger(__name__)
        self._container_name: Optional[str] = None

    def _resolve_container_name(self) -> str:
        """
        Resolve the Docker container name for this device.

        Uses device_info['container_name'] if provided directly.
        Otherwise derives from hostname: clab-<topology>-<hostname>
        Handles containerlab node names which may or may not have numeric suffixes.
        """
        if self._device_info.get("container_name"):
            return self._device_info["container_name"]

        hostname = self._device_info.get("hostname", "")
        if hostname:
            # Try exact hostname first
            primary = f"clab-{self.TOPOLOGY_NAME}-{hostname}"
            if self._container_exists(primary):
                return primary
            
            # Strip trailing -NN suffix (containerlab may not include it)
            import re
            stripped = re.sub(r'-\d+$', '', hostname)
            if stripped != hostname:
                fallback = f"clab-{self.TOPOLOGY_NAME}-{stripped}"
                if self._container_exists(fallback):
                    return fallback
            
            # If neither exists but hostname was provided, return the primary anyway
            # (connect will fail with clear error)
            return primary

        # Fall back to IP-based lookup
        ip = self._device_info.get("ip_address") or self._device_info.get("ip", "")
        if ip:
            return self._resolve_container_by_ip(ip)

        raise ValueError(
            "Cannot resolve container name: device_info must contain "
            "'container_name', 'hostname', or 'ip_address'"
        )

    def _container_exists(self, container_name: str) -> bool:
        """Check if a container with the given name exists and is running."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container_name}", "--quiet"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _resolve_container_by_ip(self, ip: str) -> str:
        """Find container name by IP address using docker inspect."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=5
            )
            candidates = [
                name.strip() for name in result.stdout.splitlines()
                if "pdsno" in name and "lc" not in name and "rc" not in name
                and "gc" not in name
            ]
            for name in candidates:
                ip_result = subprocess.run(
                    ["docker", "inspect", "--format",
                     "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name],
                    capture_output=True, text=True, timeout=5
                )
                if ip in ip_result.stdout:
                    return name
        except Exception as e:
            self.logger.warning(f"Container IP lookup failed: {e}")
        raise ValueError(f"No container found with IP {ip}")

    def connect(self, device_info: Dict) -> bool:
        """
        Verify container is reachable via docker exec.
        No persistent connection needed for docker exec model.
        """
        self._device_info = device_info
        try:
            container = self._resolve_container_name()
            result = subprocess.run(
                ["docker", "exec", container, "vtysh", "-n", "-c", "show version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self._container_name = container
                self.logger.info(
                    f"FRRAdapter connected to {container} via docker exec"
                )
                return True
            else:
                self.logger.error(
                    f"vtysh not available in {container}: {result.stderr[:200]}"
                )
                return False
        except Exception as e:
            self.logger.error(f"FRRAdapter connect failed: {e}")
            return False

    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """Translate a ConfigIntent to FRR vtysh commands."""
        if intent.intent_type == IntentType.CREATE_VLAN:
            vlan_id = intent.parameters["vlan_id"]
            name = intent.parameters.get("name", "")
            commands = ["configure terminal", f"vlan {vlan_id}"]
            if name:
                commands.append(f"  name {name}")
            commands.extend(["exit", "end", "write memory"])
            return commands

        if intent.intent_type == IntentType.DELETE_VLAN:
            vlan_id = intent.parameters["vlan_id"]
            return [
                "configure terminal",
                f"no vlan {vlan_id}",
                "end",
                "write memory",
            ]

        if intent.intent_type == IntentType.CONFIGURE_INTERFACE:
            iface = intent.parameters["interface"]
            commands = ["configure terminal", f"interface {iface}"]
            if "description" in intent.parameters:
                commands.append(f"  description {intent.parameters['description']}")
            if "ip_address" in intent.parameters:
                commands.append(
                    f"  ip address {intent.parameters['ip_address']}"
                )
            commands.extend(["exit", "end", "write memory"])
            return commands

        raise NotImplementedError(
            f"FRRAdapter does not support intent type: {intent.intent_type}"
        )

    def apply_config(self, commands: List[str]) -> Dict:
        """
        Apply configuration commands via a single vtysh invocation.
        All commands are passed as separate -c flags so they run
        in the same vtysh session with shared context.
        """
        if not self._container_name:
            return {"success": False, "error": "Not connected"}

        # Filter empty lines
        cmds = [c.strip() for c in commands if c.strip()]
        if not cmds:
            return {"success": True, "outputs": []}

        # Build: docker exec <container> vtysh -n -c cmd1 -c cmd2 ...
        # -n flag: don't load config files on startup
        exec_args = ["docker", "exec", self._container_name, "vtysh", "-n"]
        for cmd in cmds:
            exec_args.extend(["-c", cmd])

        try:
            result = subprocess.run(
                exec_args,
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                self.logger.error(
                    f"vtysh failed on {self._container_name}: "
                    f"{result.stderr[:300]}"
                )
                return {
                    "success": False,
                    "error": result.stderr.strip() or result.stdout.strip(),
                    "commands": cmds,
                }
            self.logger.info(
                f"FRRAdapter applied {len(cmds)} commands to "
                f"{self._container_name}: {result.stdout[:200]}"
            )
            return {
                "success": True,
                "output": result.stdout,
                "commands": cmds,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "vtysh execution timed out"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        

    def get_running_config(self) -> str:
        """Retrieve running configuration from FRR container."""
        if not self._container_name:
            return ""
        try:
            result = subprocess.run(
                ["docker", "exec", self._container_name,
                 "vtysh", "-c", "show running-config"],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            self.logger.warning(f"get_running_config failed: {e}")
            return ""

    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify that an intent was applied successfully."""
        if not self._container_name:
            return False
        try:
            if intent.intent_type == IntentType.CREATE_VLAN:
                vlan_id = intent.parameters["vlan_id"]
                result = subprocess.run(
                    ["docker", "exec", self._container_name,
                     "vtysh", "-c", f"show vlan id {vlan_id}"],
                    capture_output=True, text=True, timeout=10
                )
                return result.returncode == 0 and str(vlan_id) in result.stdout
        except Exception as e:
            self.logger.warning(f"verify_config failed: {e}")
        return False

    def disconnect(self):
        """No persistent connection to close in docker exec model."""
        self._container_name = None