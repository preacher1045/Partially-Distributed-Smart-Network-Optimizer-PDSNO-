"""
Playbook Validator

Validates user-submitted Ansible playbooks for security and correctness.
"""

import yaml
import re
from typing import Dict, List, Tuple
import logging


class PlaybookValidator:
    """
    Validate Ansible playbooks for security and correctness.
    
    Checks:
    - Only allowed modules
    - No dangerous operations
    - Proper structure
    - Template inheritance
    """
    
    # Allowed Ansible modules
    ALLOWED_MODULES = {
        # Network modules
        'ios_config', 'ios_command', 'ios_facts', 'ios_vlan', 'ios_interface',
        'junos_config', 'junos_command', 'junos_facts',
        'eos_config', 'eos_command', 'eos_facts',
        'cli_config', 'cli_command',
        
        # Utility modules
        'debug', 'set_fact', 'assert', 'fail', 'pause',
        'include_role', 'include_tasks', 'import_tasks',
        'template', 'copy',
        
        # Logic
        'block', 'rescue', 'always'
    }
    
    # Forbidden modules (security risks)
    FORBIDDEN_MODULES = {
        'shell', 'command', 'raw', 'script',  # Arbitrary code execution
        'file', 'synchronize', 'fetch',  # File system access
        'uri', 'get_url',  # Network requests
        'package', 'yum', 'apt',  # Package management
        'user', 'group',  # User management
        'cron', 'at',  # Scheduled tasks
        'service', 'systemd'  # Service management
    }
    
    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf',  # Recursive delete
        r'>\s*/dev/',  # Write to devices
        r'curl.*\|.*sh',  # Pipe to shell
        r'wget.*\|.*sh',
        r'eval\s*\(',  # Code evaluation
        r'exec\s*\(',
        r'__import__',  # Python imports
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self, playbook_content: str) -> Tuple[bool, Dict]:
        """
        Validate playbook content.
        
        Args:
            playbook_content: YAML playbook content
        
        Returns:
            (is_valid, result) tuple
        """
        self.errors = []
        self.warnings = []
        
        # Parse YAML
        try:
            playbook = yaml.safe_load(playbook_content)
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML: {e}")
            return False, self._get_result()
        
        # Validate structure
        if not isinstance(playbook, list):
            self.errors.append("Playbook must be a list of plays")
            return False, self._get_result()
        
        # Validate each play
        for i, play in enumerate(playbook):
            self._validate_play(play, i)
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(playbook_content)
        
        is_valid = len(self.errors) == 0
        
        return is_valid, self._get_result()
    
    def _validate_play(self, play: Dict, play_index: int):
        """Validate individual play"""
        if not isinstance(play, dict):
            self.errors.append(f"Play {play_index} must be a dictionary")
            return
        
        # Check required fields
        if 'hosts' not in play:
            self.errors.append(f"Play {play_index} missing 'hosts' field")
        
        # Validate tasks
        if 'tasks' in play:
            for task_index, task in enumerate(play['tasks']):
                self._validate_task(task, play_index, task_index)
        
        # Validate roles
        if 'roles' in play:
            for role in play['roles']:
                self._validate_role(role, play_index)
    
    def _validate_task(self, task: Dict, play_index: int, task_index: int):
        """Validate individual task"""
        if not isinstance(task, dict):
            self.errors.append(
                f"Task {task_index} in play {play_index} must be a dictionary"
            )
            return
        
        # Find module being used
        module = self._get_module_name(task)
        
        if not module:
            self.warnings.append(
                f"Task {task_index} in play {play_index} has no module"
            )
            return
        
        # Check if module is allowed
        if module in self.FORBIDDEN_MODULES:
            self.errors.append(
                f"Forbidden module '{module}' in task {task_index} of play {play_index}"
            )
        
        elif module not in self.ALLOWED_MODULES:
            self.warnings.append(
                f"Unknown module '{module}' in task {task_index} of play {play_index}"
            )
        
        # Check for privilege escalation
        if task.get('become') or task.get('become_user'):
            self.errors.append(
                f"Privilege escalation not allowed in task {task_index} of play {play_index}"
            )
    
    def _validate_role(self, role, play_index: int):
        """Validate role reference"""
        # Only allow roles from approved list
        approved_roles = ['common', 'policy_deployment', 'network_discovery']
        
        role_name = role if isinstance(role, str) else role.get('name', role.get('role'))
        
        if role_name not in approved_roles:
            self.warnings.append(
                f"Role '{role_name}' in play {play_index} is not in approved list"
            )
    
    def _get_module_name(self, task: Dict) -> str:
        """Extract module name from task"""
        # Skip meta keys
        skip_keys = {'name', 'when', 'with_items', 'loop', 'register', 'tags', 'become', 'become_user'}
        
        for key in task.keys():
            if key not in skip_keys:
                return key
        
        return ''
    
    def _check_dangerous_patterns(self, content: str):
        """Check for dangerous patterns in content"""
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                self.errors.append(f"Dangerous pattern detected: {pattern}")
    
    def _get_result(self) -> Dict:
        """Get validation result"""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings
        }