"""
Configuration Loader

Utilities for loading YAML configuration files with validation.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import os


class ConfigLoader:
    """
    Load and validate YAML configuration files.
    """
    
    @staticmethod
    def load(config_path: str, required_keys: Optional[list] = None) -> Dict[str, Any]:
        """
        Load a YAML configuration file.
        
        Args:
            config_path: Path to YAML file
            required_keys: List of keys that must be present in config
        
        Returns:
            Configuration dictionary
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required keys are missing
            yaml.YAMLError: If YAML is invalid
        """
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            config = {}
        
        # Validate required keys
        if required_keys:
            missing = [key for key in required_keys if key not in config]
            if missing:
                raise ValueError(f"Missing required configuration keys: {missing}")
        
        return config
    
    @staticmethod
    def load_with_env_override(config_path: str, env_prefix: str = "PDSNO_") -> Dict[str, Any]:
        """
        Load config and override with environment variables.
        
        Environment variables matching env_prefix will override config values.
        For example, PDSNO_CONTROLLER_ID will override config['controller_id'].
        
        Args:
            config_path: Path to YAML file
            env_prefix: Prefix for environment variables
        
        Returns:
            Configuration dictionary with env overrides applied
        """
        config = ConfigLoader.load(config_path)
        
        # Apply environment variable overrides
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                config_key = key[len(env_prefix):].lower()
                config[config_key] = value
        
        return config
