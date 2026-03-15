"""FAFU 自动签到的 HTTP 客户端模块。

本模块提供自定义 HTTP 客户端，支持重试逻辑、
会话管理和适当的错误处理。
"""

import logging
import sys
import time
from typing import Any

import requests
from requests import Response
from requests.exceptions import RequestException

from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.crypto import generate_headers


class FAFUClient:
    """支持重试逻辑和会话管理的 HTTP 客户端。

    特性:
    - 应用级别的指数退避重试
    - 每次重试时动态生成授权头
    - 特殊处理 401（令牌过期）和 408（时间同步错误）
    - 支持上下文管理器
    - 可配置超时时间
    """

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1  # 基础延迟秒数（1, 2, 4...）
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

    # 超时配置（连接，读取）
    TIMEOUT = (10, 30)

    def __init__(self, config: AppConfig):
        """初始化 HTTP 客户端。

        参数:
            config: 包含 base_url 和 user_token 的应用程序配置。
        """
        self.config = config
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        """发起带重试逻辑的 HTTP 请求。

        本方法实现应用级别的指数退避重试。
        每次重试时，使用新的时间戳生成新的授权头。

        特殊状态码:
        - 401: 令牌过期 - 终止程序
        - 408: 时间同步错误 - 终止程序

        参数:
            method: HTTP 方法（GET, POST 等）
            url: 请求 URL（相对或绝对）
            **kwargs: 传递给 requests 的额外参数

        返回:
            成功请求的响应对象。

        抛出:
            RequestException: 如果所有重试都耗尽。
            SystemExit: 如果收到 401 或 408 状态码。
        """
        # 确保 URL 是绝对路径
        if not url.startswith("http"):
            full_url = f"{self.config.base_url.rstrip('/')}/{url.lstrip('/')}"
        else:
            full_url = url

        # 如果未提供则合并超时设置
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.TIMEOUT

        last_exception: RequestException | None = None

        for attempt in range(self.MAX_RETRIES):
            # 每次尝试生成新的请求头（对重试很重要！）
            headers = generate_headers(full_url, self.config.user_token)

            # 允许自定义请求头覆盖生成的请求头
            if "headers" in kwargs:
                custom_headers = kwargs.pop("headers")
                headers.update(custom_headers)

            try:
                self.logger.debug(f"请求 {attempt + 1}/{self.MAX_RETRIES}: {method} {full_url}")
                response = self.session.request(method, full_url, headers=headers, **kwargs)

                # 处理会终止程序的特殊状态码
                if response.status_code == 401:
                    self.logger.error("[x] Token已过期，请重新抓包获取并更新配置文件！")
                    # 发送通知（如果启用）
                    if getattr(self.config, "notification_enabled", False):
                        from fafu_auto_sign.services.notification_service import NotificationService

                        notification_service = NotificationService(self.config)
                        notification_service.notify(
                            title="紧急：Token已过期",
                            content="Token已过期，请重新抓包获取并更新配置文件！",
                            success=False,
                        )
                    sys.exit(1)

                if response.status_code == 408:
                    self.logger.error("[x] 系统时间不同步，请校准系统时间！")
                    # 发送通知（如果启用）
                    if getattr(self.config, "notification_enabled", False):
                        from fafu_auto_sign.services.notification_service import NotificationService

                        notification_service = NotificationService(self.config)
                        notification_service.notify(
                            title="紧急：系统时间不同步",
                            content="运行脚本的系统时间与标准北京时间不一致，签名校验失败，请校准系统时间！",
                            success=False,
                        )
                    sys.exit(1)

                # 根据状态码检查是否应该重试
                if response.status_code in self.RETRY_STATUS_CODES:
                    if attempt < self.MAX_RETRIES - 1:
                        delay = self.RETRY_DELAY_BASE * (2**attempt)
                        self.logger.warning(
                            f"收到状态码 {response.status_code}, "
                            f"{delay}秒后重试... (尝试 {attempt + 1}/{self.MAX_RETRIES})"
                        )
                        time.sleep(delay)
                        continue

                # 对其他 HTTP 错误抛出异常（4xx, 5xx 不在重试列表中）
                response.raise_for_status()

                self.logger.debug(f"请求成功: {response.status_code}")
                return response

            except RequestException as e:
                last_exception = e

                # 检查是否应该重试连接错误或超时
                should_retry = False
                if isinstance(e, requests.exceptions.Timeout):
                    should_retry = True
                    self.logger.warning(f"请求 {attempt + 1} 超时")
                elif isinstance(e, requests.exceptions.ConnectionError):
                    should_retry = True
                    self.logger.warning(f"请求 {attempt + 1} 连接错误")
                elif hasattr(e, "response") and e.response is not None:
                    # 上面已经处理过，但以防万一
                    if e.response.status_code in self.RETRY_STATUS_CODES:
                        should_retry = True

                if should_retry and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_BASE * (2**attempt)
                    self.logger.warning(f"{delay}秒后重试...")
                    time.sleep(delay)
                else:
                    # 不重试，重新抛出异常
                    raise

        # 所有重试已耗尽
        if last_exception:
            raise last_exception

        # 这不应该发生，但以防万一
        raise RequestException(f"{self.MAX_RETRIES} 次尝试后失败")

    def get(self, url: str, **kwargs: Any) -> Response:
        """发起 GET 请求。"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        """发起 POST 请求。"""
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        """关闭会话并释放资源。"""
        self.session.close()
        self.logger.debug("会话已关闭")

    def __enter__(self) -> "FAFUClient":
        """进入上下文管理器。"""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出上下文管理器并关闭会话。"""
        self.close()
