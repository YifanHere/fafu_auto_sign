"""FAFU 自动签到的服务模块。

本模块提供各种服务类，用于处理
签到自动化的不同方面。
"""

from fafu_auto_sign.services.notification_service import NotificationService
from fafu_auto_sign.services.sign_service import SignService
from fafu_auto_sign.services.task_service import TaskService

__all__ = ["SignService", "TaskService", "NotificationService"]
