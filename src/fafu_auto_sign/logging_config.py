"""
Logging configuration for fafu_auto_sign.

Provides structured logging with console and file output,
including 7-day log rotation.
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Setup logging configuration with console and file handlers.
    
    Args:
        log_level: Minimum log level for console output (default: INFO)
        log_dir: Directory for log files (default: logs)
    
    Features:
        - Console output: INFO+ level, human-readable format
        - File output: DEBUG+ level, JSON format
        - 7-day rotation at midnight
        - Auto-creation of log directory
    """
    # Create log directory if not exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler - INFO+, human readable
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler - DEBUG+, JSON format, 7-day rotation
    log_file = log_path / "fafu_sign.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)
    
    # Log setup completion
    logging.getLogger(__name__).debug(
        f"Logging configured: console={log_level}, file=DEBUG, dir={log_dir}"
    )
