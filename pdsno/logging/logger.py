"""
PDSNO Structured Logging Framework

Provides JSON-formatted structured logging for all PDSNO components.
Every log entry includes timestamp, level, controller_id, and message.
"""

import logging
import logging.config
import json
import os
from datetime import datetime, timezone
from typing import Optional

import yaml


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured log entries"""
    
    def __init__(self, controller_id: str = "system"):
        super().__init__()
        self.controller_id = controller_id
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "controller_id": self.controller_id,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields from the record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def get_logger(name: str, controller_id: str = "system", level: int = logging.INFO) -> logging.Logger:
    """
    Get a structured logger for a PDSNO component.
    
    Args:
        name: Logger name (typically module name)
        controller_id: ID of the controller using this logger
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = get_logger(__name__, controller_id="local_cntl_1")
        >>> logger.info("Device discovered", extra={'extra_fields': {'device_id': 'dev-001'}})
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(level)
        
        # Console handler with structured formatter
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(StructuredFormatter(controller_id))
        
        logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger


def configure_logging(config_path: Optional[str] = None, default_level: int = logging.INFO) -> bool:
    """
    Configure logging from a YAML file. Falls back to basicConfig on failure.

    Args:
        config_path: Path to YAML logging config
        default_level: Default log level for fallback config

    Returns:
        True if YAML config loaded, False otherwise
    """
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle)

            if not config:
                raise ValueError("Logging config is empty")

            for handler in config.get("handlers", {}).values():
                filename = handler.get("filename")
                if filename:
                    os.makedirs(os.path.dirname(filename), exist_ok=True)

            logging.config.dictConfig(config)
            return True
        except Exception:
            logging.basicConfig(level=default_level)
            return False

    logging.basicConfig(level=default_level)
    return False
