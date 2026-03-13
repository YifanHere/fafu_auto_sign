"""
fafu_auto_sign 的日志配置模块。

提供结构化日志输出，支持控制台和文件输出，
包括 7 天日志轮转机制。
"""
import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """结构化日志的 JSON 格式化器。"""
    
    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为 JSON 格式。"""
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_obj, ensure_ascii=False)



def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    配置日志系统，包含控制台和文件处理器。
    
    参数:
        log_level: 控制台输出的最低日志级别（默认: INFO）
        log_dir: 日志文件存放目录（默认: logs）
    
    功能特性:
        - 控制台输出: INFO+ 级别，人类可读格式
        - 文件输出: DEBUG+ 级别，JSON 格式
        - 每日午夜轮转，保留 7 天
        - 自动创建日志目录
    """
    # 如果日志目录不存在则创建
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 捕获所有级别的日志
    
    # 清除已有的处理器
    root_logger.handlers = []
    
    # 控制台处理器 - INFO+ 级别，人类可读格式
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # 文件处理器 - DEBUG+ 级别，JSON 格式，7 天轮转
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
    
    # 日志配置完成
    logging.getLogger(__name__).debug(
        f"日志已配置: 控制台={log_level}, 文件=DEBUG, 目录={log_dir}"
    )
