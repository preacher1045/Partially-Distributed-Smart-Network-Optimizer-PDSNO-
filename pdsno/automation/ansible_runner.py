# Copyright (C) 2025 Atlas Iris
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Ansible Runner for PDSNO

Executes Ansible playbooks programmatically for device configuration.
"""

import tempfile
from typing import Dict, List, Optional
from pathlib import Path
import logging
import ansible_runner


class AnsiblePlaybookRunner:
    """
    Execute Ansible playbooks from PDSNO controllers.
    
    Features:
    - Dynamic inventory from NIB
    - Playbook validation
    - Dry-run support
    - Result collection
    - Error handling
    """
    
    def __init__(
        self,
        playbook_dir: str = "pdsno/automation/playbooks",
        inventory_path: str = "pdsno/automation/inventory/dynamic_inventory.py",
        roles_path: str = "pdsno/automation/roles"
    ):
        """
        Initialize Ansible runner.
        
        Args:
            playbook_dir: Directory containing playbooks
            inventory_path: Path to dynamic inventory script
            roles_path: Directory containing roles
        """
        self.playbook_dir = Path(playbook_dir)
        self.inventory_path = Path(inventory_path)
        self.roles_path = Path(roles_path)
        self.logger = logging.getLogger(__name__)
        
        # Validate paths
        if not self.playbook_dir.exists():
            raise FileNotFoundError(f"Playbook directory not found: {playbook_dir}")
        
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Inventory script not found: {inventory_path}")
    
    def run_playbook(
        self,
        playbook_name: str,
        extra_vars: Optional[Dict] = None,
        limit: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dry_run: bool = False,
        verbosity: int = 0
    ) -> Dict:
        """
        Execute an Ansible playbook.
        
        Args:
            playbook_name: Name of playbook (e.g., 'apply_policy.yaml')
            extra_vars: Extra variables to pass to playbook
            limit: Limit execution to specific hosts
            tags: Only run tasks with these tags
            dry_run: Check mode (don't make changes)
            verbosity: Ansible verbosity level (0-4)
        
        Returns:
            Result dictionary with status, output, and stats
        """
        playbook_path = self.playbook_dir / playbook_name
        
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")
        
        self.logger.info(f"Running playbook: {playbook_name}")
        if dry_run:
            self.logger.info("DRY RUN MODE - No changes will be made")
        
        # Prepare extra vars
        extravars = extra_vars or {}
        
        # Build command line arguments
        cmdline = []
        
        if dry_run:
            cmdline.append('--check')
        
        if limit:
            cmdline.extend(['--limit', limit])
        
        if tags:
            cmdline.extend(['--tags', ','.join(tags)])
        
        # Set verbosity
        if verbosity > 0:
            cmdline.append('-' + 'v' * verbosity)
        
        # Create temporary directory for ansible-runner
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Run playbook
                result = ansible_runner.run(
                    playbook=str(playbook_path),
                    inventory=str(self.inventory_path),
                    extravars=extravars,
                    cmdline=' '.join(cmdline) if cmdline else None,
                    private_data_dir=tmpdir,
                    quiet=verbosity == 0,
                    json_mode=True
                )
                
                # Collect results
                return self._parse_result(result, playbook_name, dry_run)
            
            except Exception as e:
                self.logger.error(f"Playbook execution failed: {e}")
                return {
                    'success': False,
                    'playbook': playbook_name,
                    'error': str(e),
                    'dry_run': dry_run
                }
    
    def _parse_result(self, result, playbook_name: str, dry_run: bool) -> Dict:
        """Parse ansible-runner result"""
        
        stats = result.stats
        events = list(result.events)
        
        # Determine success
        success = (
            result.status == 'successful' and
            stats.get('failures', {}) == {} and
            stats.get('dark', {}) == {}
        )
        
        # Collect changed hosts
        changed_hosts = []
        failed_hosts = []
        
        for host, host_stats in stats.get('changed', {}).items():
            if host_stats > 0:
                changed_hosts.append(host)
        
        for host, host_stats in stats.get('failures', {}).items():
            if host_stats > 0:
                failed_hosts.append(host)
        
        # Extract task results
        task_results = []
        for event in events:
            if event.get('event') == 'runner_on_ok':
                task_results.append({
                    'host': event.get('event_data', {}).get('host'),
                    'task': event.get('event_data', {}).get('task'),
                    'result': event.get('event_data', {}).get('res', {})
                })
        
        return {
            'success': success,
            'playbook': playbook_name,
            'dry_run': dry_run,
            'status': result.status,
            'stats': stats,
            'changed_hosts': changed_hosts,
            'failed_hosts': failed_hosts,
            'task_results': task_results,
            'rc': result.rc
        }
    
    def apply_policy(
        self,
        policy_name: str,
        target_devices: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict:
        """
        Apply a policy to devices.
        
        Args:
            policy_name: Name of policy to apply
            target_devices: List of device IDs (or None for all)
            dry_run: Check mode
        
        Returns:
            Execution result
        """
        extra_vars = {'policy_name': policy_name}
        limit = ','.join(target_devices) if target_devices else None
        
        return self.run_playbook(
            playbook_name='apply_policy.yaml',
            extra_vars=extra_vars,
            limit=limit,
            dry_run=dry_run
        )
    
    def rollback_config(
        self,
        device_id: str,
        backup_id: str
    ) -> Dict:
        """
        Rollback device configuration.
        
        Args:
            device_id: Device to rollback
            backup_id: Backup ID to restore
        
        Returns:
            Execution result
        """
        extra_vars = {
            'device_id': device_id,
            'backup_id': backup_id
        }
        
        return self.run_playbook(
            playbook_name='rollback.yaml',
            extra_vars=extra_vars,
            limit=device_id
        )
    
    def verify_state(
        self,
        target_devices: Optional[List[str]] = None
    ) -> Dict:
        """
        Verify device state matches intended configuration.
        
        Args:
            target_devices: Devices to verify (or None for all)
        
        Returns:
            Verification result
        """
        limit = ','.join(target_devices) if target_devices else None
        
        return self.run_playbook(
            playbook_name='verify_state.yaml',
            limit=limit
        )
    
    def list_playbooks(self) -> List[str]:
        """List available playbooks"""
        return [
            p.name for p in self.playbook_dir.glob('*.yaml')
            if p.is_file()
        ]


# Convenience function for integration
def run_ansible_playbook(
    playbook: str,
    inventory: Optional[str] = None,
    **kwargs
) -> Dict:
    """
    Convenience function to run a playbook.
    
    Args:
        playbook: Playbook name or path
        inventory: Inventory path (uses dynamic inventory if None)
        **kwargs: Additional arguments for run_playbook
    
    Returns:
        Execution result
    """
    runner = AnsiblePlaybookRunner()
    return runner.run_playbook(playbook, **kwargs)