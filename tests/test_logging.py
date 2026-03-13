"""
日志配置测试。
"""

import json
import logging
import logging.handlers  # noqa: F401
import os
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fafu_auto_sign.logging_config import setup_logging, JsonFormatter


class TestLoggingConfig:
    """测试日志配置。"""
    
    def setup_method(self):
        """设置测试环境。"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "test_logs"
        
        # 清除现有的处理器
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_logger.setLevel(logging.DEBUG)
    
    def teardown_method(self):
        """清理测试环境。"""
        # 清除处理器
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # 移除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_directory_auto_created(self):
        """测试日志目录自动创建。"""
        assert not self.log_dir.exists()
        
        setup_logging(log_dir=str(self.log_dir))
        
        assert self.log_dir.exists()
        assert self.log_dir.is_dir()
    
    def test_log_file_created(self):
        """测试日志文件被创建。"""
        setup_logging(log_dir=str(self.log_dir))
        
        log_file = self.log_dir / "fafu_sign.log"
        logger = logging.getLogger("test")
        logger.info("Test message")
        
        # 刷新处理器
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        assert log_file.exists()
    
    def test_json_format(self):
        """测试JSON日志格式包含必需字段。"""
        setup_logging(log_dir=str(self.log_dir))
        
        # 清除setup_logging自身日志的现有日志内容
        log_file = self.log_dir / "fafu_sign.log"
        if log_file.exists():
            log_file.write_text("")
        
        logger = logging.getLogger("test_json")
        logger.debug("Test JSON message")
        
        # 刷新处理器
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        log_file = self.log_dir / "fafu_sign.log"
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        
        # 解析JSON
        log_entry = json.loads(lines[0])
        
        # 检查必需字段
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "name" in log_entry
        assert "message" in log_entry
        
        # 检查值
        assert log_entry["level"] == "DEBUG"
        assert log_entry["name"] == "test_json"
        assert log_entry["message"] == "Test JSON message"
    
    def test_timed_rotation_config(self):
        """测试TimedRotatingFileHandler配置。"""
        setup_logging(log_dir=str(self.log_dir))
        
        # 查找文件处理器
        file_handler: logging.handlers.TimedRotatingFileHandler | None = None
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
        """测试控制台处理器默认使用INFO级别。"""
        setup_logging(log_dir=str(self.log_dir))
        
        # 查找控制台处理器
        console_handler: logging.StreamHandler | None = None
        console_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and \
               not isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                console_handler = handler
                break
        
        assert console_handler is not None
        assert console_handler.level == logging.INFO
    
    def test_file_handler_debug_level(self):
        """测试文件处理器使用DEBUG级别。"""
        setup_logging(log_dir=str(self.log_dir))
        
        # 查找文件处理器
        file_handler: logging.handlers.TimedRotatingFileHandler | None = None
        file_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                file_handler = handler
                break
        
        assert file_handler is not None
        assert file_handler.level == logging.DEBUG
    
    def test_json_formatter(self):
        """测试JsonFormatter生成有效的JSON。"""
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
    # 运行测试
    import pytest
    pytest.main([__file__, "-v"])
