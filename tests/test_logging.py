"""
Tests for logging configuration.
"""

import json
import logging
import os
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fafu_auto_sign.logging_config import setup_logging, JsonFormatter


class TestLoggingConfig:
    """Test logging configuration."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "test_logs"
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_logger.setLevel(logging.DEBUG)
    
    def teardown_method(self):
        """Cleanup test environment."""
        # Clear handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # Remove temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_directory_auto_created(self):
        """Test that log directory is auto-created."""
        assert not self.log_dir.exists()
        
        setup_logging(log_dir=str(self.log_dir))
        
        assert self.log_dir.exists()
        assert self.log_dir.is_dir()
    
    def test_log_file_created(self):
        """Test that log file is created."""
        setup_logging(log_dir=str(self.log_dir))
        
        log_file = self.log_dir / "fafu_sign.log"
        logger = logging.getLogger("test")
        logger.info("Test message")
        
        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        assert log_file.exists()
    
    def test_json_format(self):
        """Test JSON log format contains required fields."""
        setup_logging(log_dir=str(self.log_dir))
        
        # Clear existing log content from setup_logging's own log
        log_file = self.log_dir / "fafu_sign.log"
        if log_file.exists():
            log_file.write_text("")
        
        logger = logging.getLogger("test_json")
        logger.debug("Test JSON message")
        
        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        log_file = self.log_dir / "fafu_sign.log"
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        # Parse JSON
        log_entry = json.loads(lines[0])
        
        # Check required fields
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "name" in log_entry
        assert "message" in log_entry
        
        # Check values
        assert log_entry["level"] == "DEBUG"
        assert log_entry["name"] == "test_json"
        assert log_entry["message"] == "Test JSON message"
    
    def test_timed_rotation_config(self):
        """Test TimedRotatingFileHandler configuration."""
        setup_logging(log_dir=str(self.log_dir))
        
        # Find file handler
        file_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                file_handler = handler
                break
        
        assert file_handler is not None
        assert file_handler.when.upper() == "MIDNIGHT"
        assert file_handler.interval == 86400  # midnight = 86400 seconds
        assert file_handler.backupCount == 7
    
    def test_console_handler_info_level(self):
        """Test console handler uses INFO level by default."""
        setup_logging(log_dir=str(self.log_dir))
        
        # Find console handler
        console_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and \
               not isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                console_handler = handler
                break
        
        assert console_handler is not None
        assert console_handler.level == logging.INFO
    
    def test_file_handler_debug_level(self):
        """Test file handler uses DEBUG level."""
        setup_logging(log_dir=str(self.log_dir))
        
        # Find file handler
        file_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                file_handler = handler
                break
        
        assert file_handler is not None
        assert file_handler.level == logging.DEBUG
    
    def test_json_formatter(self):
        """Test JsonFormatter produces valid JSON."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed["level"] == "INFO"
        assert parsed["name"] == "test"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed


if __name__ == "__main__":
    # Run tests
    import pytest
    pytest.main([__file__, "-v"])
