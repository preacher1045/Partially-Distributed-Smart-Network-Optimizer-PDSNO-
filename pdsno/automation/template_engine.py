"""
Template Engine

Manages playbook templates and inheritance.
"""

import yaml
from typing import Dict
from pathlib import Path
import logging


class TemplateEngine:
    """
    Manage playbook template inheritance.
    
    Allows user playbooks to extend base templates.
    """
    
    def __init__(self, templates_dir: str = "pdsno/automation/templates"):
        """
        Initialize template engine.
        
        Args:
            templates_dir: Directory containing base templates
        """
        self.templates_dir = Path(templates_dir)
        self.logger = logging.getLogger(__name__)
        
        # Load base templates
        self.base_templates = self._load_base_templates()
    
    def _load_base_templates(self) -> Dict:
        """Load all base templates"""
        templates = {}
        
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            return templates
        
        for template_file in self.templates_dir.glob('*.j2'):
            template_name = template_file.stem
            with open(template_file, 'r') as f:
                templates[template_name] = f.read()
        
        return templates
    
    def extend_template(
        self,
        base_template: str,
        custom_content: str
    ) -> str:
        """
        Extend base template with custom content.
        
        Args:
            base_template: Name of base template
            custom_content: Custom playbook content
        
        Returns:
            Combined playbook content
        """
        if base_template not in self.base_templates:
            raise ValueError(f"Base template not found: {base_template}")
        
        # Parse base and custom
        base = yaml.safe_load(self.base_templates[base_template])
        custom = yaml.safe_load(custom_content)
        
        # Merge
        merged = self._merge_playbooks(base, custom)
        
        return yaml.dump(merged, default_flow_style=False)
    
    def _merge_playbooks(self, base: list, custom: list) -> list:
        """Merge base and custom playbooks"""
        # For now, simple append
        # Could be more sophisticated with task injection
        
        if not isinstance(base, list) or not isinstance(custom, list):
            raise ValueError("Both base and custom must be playbook lists")
        
        merged = base.copy()
        
        # Append custom plays
        for play in custom:
            merged.append(play)
        
        return merged
    
    def validate_inheritance(self, playbook_content: str) -> bool:
        """Check if playbook properly extends a base template"""
        try:
            playbook = yaml.safe_load(playbook_content)
            
            # Check for 'extends' directive
            if isinstance(playbook, dict) and 'extends' in playbook:
                base_template = playbook['extends']
                return base_template in self.base_templates
            
            return True  # No inheritance required
        
        except:
            return False