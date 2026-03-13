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
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fafu_auto_sign.services.notification_service import NotificationService


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


class NotificationHandler(logging.Handler):
    """
    通知处理器，检查日志消息中的特定标记并触发通知。
    
    支持的标记:
        - "✅ 签到成功" → 触发成功通知
        - "❌ 签到失败" → 触发失败通知
        - "[x] Token已过期" → 触发紧急通知
    """

    def __init__(self, notification_service: "NotificationService") -> None:
        """
        初始化通知处理器。
        
        参数:
            notification_service: 通知服务实例，用于发送通知
        """
        super().__init__()
        self.notification_service = notification_service

    def emit(self, record: logging.LogRecord) -> None:
        """
        处理日志记录，检查特定标记并触发相应通知。
        
        参数:
            record: 日志记录对象
        """
        try:
            message = record.getMessage()
            
            # 检查签到成功标记
            if "✅ 签到成功" in message:
                self.notification_service.notify(
                    title="签到成功",
                    content=message,
                    success=True
                )
            # 检查签到失败标记
            elif "❌ 签到失败" in message:
                self.notification_service.notify(
                    title="签到失败",
                    content=message,
                    success=False
                )
            # 检查Token过期标记（紧急通知）
            elif "[x] Token已过期" in message or "Token 已过期" in message:
                self.notification_service.notify(
                    title="紧急：Token已过期",
                    content=message,
                    success=False
                )
        except Exception:
            # 通知处理不应影响日志记录，静默处理异常
            self.handleError(record)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs", notification_service: Optional["NotificationService"] = None) -> None:
    """
    配置日志系统，包含控制台和文件处理器。
    
    参数:
        log_level: 控制台输出的最低日志级别（默认: INFO）
        log_dir: 日志文件存放目录（默认: logs）
        notification_service: 可选的通知服务实例，用于发送关键日志通知
    
    功能特性:
        - 控制台输出: INFO+ 级别，人类可读格式
        - 文件输出: DEBUG+ 级别，JSON 格式
        - 每日午夜轮转，保留 7 天
        - 自动创建日志目录
        - 支持通知处理器（当 notification_service 不为 None 时启用）
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
    
    # 通知处理器 - 检查特定日志标记并触发通知
    if notification_service is not None:
        notification_handler = NotificationHandler(notification_service)
        notification_handler.setLevel(logging.INFO)
        root_logger.addHandler(notification_handler)
    
    # 日志配置完成
    logging.getLogger(__name__).debug(
        f"日志已配置: 控制台={log_level}, 文件=DEBUG, 目录={log_dir}"
    )
