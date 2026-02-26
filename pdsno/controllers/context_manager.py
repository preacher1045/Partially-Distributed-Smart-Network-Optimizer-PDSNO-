"""
Context Manager

Provides thread-safe access to context_runtime.yaml with file locking.
Implements atomic writes to prevent data corruption.
"""

import yaml
from pathlib import Path
from typing import Any, Dict
from filelock import FileLock
import tempfile
import shutil


class ContextManager:
    """
    Thread-safe manager for runtime context storage.
    
    Provides atomic read and write operations on context_runtime.yaml
    with file locking to prevent concurrent access issues.
    """
    
    def __init__(self, context_path: str = "config/context_runtime.yaml"):
        """
        Initialize context manager.
        
        Args:
            context_path: Path to context YAML file
        """
        self.context_path = Path(context_path)
        self.lock_path = Path(str(self.context_path) + ".lock")
        
        # Ensure parent directory exists
        self.context_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty context file if it doesn't exist
        if not self.context_path.exists():
            self.write({})
    
    def read(self) -> Dict[str, Any]:
        """
        Read context with file locking.
        
        Returns:
            Context dictionary
        
        Raises:
            FileNotFoundError: If context file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        with FileLock(self.lock_path):
            if not self.context_path.exists():
                raise FileNotFoundError(f"Context file not found: {self.context_path}")
            
            with open(self.context_path, 'r') as f:
                context = yaml.safe_load(f)
            
            return context if context is not None else {}
    
    def write(self, context: Dict[str, Any]) -> None:
        """
        Write context with file locking and atomic write.
        
        Uses atomic file write pattern (write to temp, then rename)
        to prevent corruption if process crashes mid-write.
        
        Args:
            context: Context dictionary to write
        
        Raises:
            IOError: If write fails
        """
        with FileLock(self.lock_path):
            # Write to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.context_path.parent,
                prefix=".context_tmp_",
                suffix=".yaml"
            )
            
            try:
                with open(temp_fd, 'w') as f:
                    yaml.dump(context, f, default_flow_style=False, sort_keys=False)
                
                # Atomic rename (overwrites existing file)
                shutil.move(temp_path, self.context_path)
            except Exception:
                # Clean up temp file on error
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except:
                    pass
                raise
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update context with new values (merge).
        
        Reads current context, applies updates, and writes back atomically.
        
        Args:
            updates: Dictionary of values to update
        """
        context = self.read()
        context.update(updates)
        self.write(context)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a single value from context.
        
        Args:
            key: Context key
            default: Default value if key not found
        
        Returns:
            Value for key, or default if not found
        """
        context = self.read()
        return context.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a single value in context.
        
        Args:
            key: Context key
            value: Value to set
        """
        self.update({key: value})


# Legacy alias (for backwards compatibility if needed)
class ContextBuilder(ContextManager):
    """Deprecated: Use ContextManager instead"""
