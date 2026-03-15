"""FAFU 自动签到的配置模块。

本模块提供基于 Pydantic 的配置管理，支持
JSON 文件、环境变量和 .env 文件。
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """应用程序配置（带验证）。

    配置优先级（从高到低）：
    1. 环境变量 (FAFU_*)
    2. .env 文件
    3. JSON 配置文件
    4. 默认值
    """

    model_config = SettingsConfigDict(
        env_prefix="FAFU_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # 必填字段
    user_token: str = Field(..., description="用户令牌（必须以 '2_' 开头）")

    # 可选字段（带默认值）
    jitter: float = Field(default=0.00005, description="位置最大抖动量（0 到 0.001）")
    image_path: str = Field(default="dorm.jpg", description="宿舍照片路径")
    image_dir: Optional[str] = Field(default=None, description="图片目录路径（随机选择图片）")
    base_url: str = Field(default="http://stuhtapi.fafu.edu.cn", description="API 基础 URL")
    heartbeat_interval: int = Field(default=900, description="心跳间隔（秒）")
    log_level: str = Field(default="INFO", description="日志级别")
    # 通知配置
    notification_enabled: bool = Field(default=False, description="启用通知")
    serverchan_key: Optional[str] = Field(default=None, description="Server酱 SendKey")
    # 任务识别配置
    task_keywords: list[str] = Field(default=["晚归"], description="任务关键词列表")
    latest_image_dir: Optional[str] = Field(
        default=None, description="最新图片目录路径（选择最新修改的图片）"
    )

    @staticmethod
    def _parse_task_keywords(v: Any) -> Any:
        """解析任务关键词，支持字符串（逗号分隔）和列表。"""
        if isinstance(v, str):
            # 从环境变量或 JSON 字符串解析
            if v.strip().startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # 逗号分隔的字符串
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

    @field_validator("task_keywords", mode="before")
    @classmethod
    def parse_task_keywords_before_validation(cls, v: Any) -> Any:
        """在验证前解析任务关键词。"""
        return cls._parse_task_keywords(v)

    @field_validator("task_keywords")
    @classmethod
    def validate_task_keywords(cls, v: list[str]) -> list[str]:
        """验证任务关键词列表非空且每个元素是非空字符串。"""
        if not isinstance(v, list):
            raise ValueError(f"任务关键词必须是列表类型，当前值: {type(v)}")
        if len(v) == 0:
            raise ValueError("任务关键词列表不能为空")
        for i, keyword in enumerate(v):
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError(f"任务关键词第 {i+1} 个元素必须是非空字符串，当前值: {keyword}")
        return v

    @field_validator("latest_image_dir")
    @classmethod
    def validate_latest_image_dir(cls, v: Optional[str]) -> Optional[str]:
        """验证最新图片目录存在且可读。"""
        if v is not None:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"最新图片目录不存在: {v}")
            if not path.is_dir():
                raise ValueError(f"路径不是目录: {v}")
            if not os.access(path, os.R_OK):
                raise ValueError(f"最新图片目录不可读: {v}")
        return v

    @field_validator("image_dir")
    @classmethod
    def validate_image_dir(cls, v: Optional[str]) -> Optional[str]:
        """验证图片目录存在且可读。"""
        if v is not None:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"图片目录不存在: {v}")
            if not path.is_dir():
                raise ValueError(f"路径不是目录: {v}")
            if not os.access(path, os.R_OK):
                raise ValueError(f"图片目录不可读: {v}")
        return v

    @field_validator("user_token")
    @classmethod
    def validate_token_format(cls, v: str) -> str:
        """验证用户令牌以 '2_' 开头。"""
        if not v.startswith("2_"):
            raise ValueError(f"用户令牌必须以 '2_' 开头，当前值: {v[:20]}...")
        return v

    @field_validator("jitter")
    @classmethod
    def validate_jitter(cls, v: float) -> float:
        """验证抖动量在有效范围内。"""
        if not 0 <= v <= 0.001:
            raise ValueError(f"抖动量必须在 0 到 0.001 之间，当前值: {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别是否有效。"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是 {valid_levels} 之一，当前值: {v}")
        return v.upper()

    @field_validator("serverchan_key")
    @classmethod
    def validate_serverchan_key(cls, v: Optional[str]) -> Optional[str]:
        """验证 Server酱 SendKey 格式（以 SCT 或 sctp 开头）。"""
        if v is not None:
            if not v.startswith(("SCT", "sctp")):
                raise ValueError(
                    f"Server酱 SendKey 必须以 'SCT' 或 'sctp' 开头，当前值: {v[:20]}..."
                )
        return v


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """从文件和环境加载配置。

    参数:
        config_path: JSON 配置文件路径。如果为 None，则只使用环境变量
                     和 .env 文件。

    返回:
        AppConfig: 已验证的配置对象。

    抛出:
        FileNotFoundError: 如果指定了配置文件但不存在。
        ValueError: 如果配置验证失败。

    示例:
        >>> config = load_config("config.json")
        >>> config = load_config()  # 仅使用环境变量和 .env 文件
    """
    config_dict: dict[str, Any] = {}

    # 如果提供了 JSON 文件则从文件加载
    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

    # 环境变量优先级高于 JSON 文件值
    # 检查环境变量并覆盖 JSON 值
    if os.environ.get("FAFU_USER_TOKEN"):
        config_dict["user_token"] = os.environ.get("FAFU_USER_TOKEN")

    # 处理其他顶层环境变量
    jitter_env = os.environ.get("FAFU_JITTER")
    if jitter_env:
        config_dict["jitter"] = float(jitter_env)
    if os.environ.get("FAFU_IMAGE_PATH"):
        config_dict["image_path"] = os.environ.get("FAFU_IMAGE_PATH")
    if os.environ.get("FAFU_IMAGE_DIR"):
        config_dict["image_dir"] = os.environ.get("FAFU_IMAGE_DIR")
    if os.environ.get("FAFU_BASE_URL"):
        config_dict["base_url"] = os.environ.get("FAFU_BASE_URL")
    interval_env = os.environ.get("FAFU_HEARTBEAT_INTERVAL")
    if interval_env:
        config_dict["heartbeat_interval"] = int(interval_env)
    if os.environ.get("FAFU_LOG_LEVEL"):
        config_dict["log_level"] = os.environ.get("FAFU_LOG_LEVEL")
    notification_enabled_env = os.environ.get("FAFU_NOTIFICATION_ENABLED")
    if notification_enabled_env:
        config_dict["notification_enabled"] = notification_enabled_env.lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
    if os.environ.get("FAFU_SERVERCHAN_KEY"):
        config_dict["serverchan_key"] = os.environ.get("FAFU_SERVERCHAN_KEY")
    # 处理新配置项
    task_keywords_env = os.environ.get("FAFU_TASK_KEYWORDS")
    if task_keywords_env:
        config_dict["task_keywords"] = [
            k.strip() for k in task_keywords_env.split(",") if k.strip()
        ]
    if os.environ.get("FAFU_LATEST_IMAGE_DIR"):
        config_dict["latest_image_dir"] = os.environ.get("FAFU_LATEST_IMAGE_DIR")

    # 临时移除环境变量，防止 pydantic-settings 尝试解析
    saved_env = {}
    env_vars_to_remove = ["FAFU_TASK_KEYWORDS", "FAFU_LATEST_IMAGE_DIR"]
    for key in env_vars_to_remove:
        if key in os.environ:
            saved_env[key] = os.environ.pop(key)

    try:
        return AppConfig(**config_dict)
    finally:
        # 恢复环境变量
        os.environ.update(saved_env)


def create_example_config(path: str | Path = "config.json.example") -> None:
    """创建示例配置文件。

    参数:
        path: 创建示例配置文件的路径。
    """
    example_config = {
        "user_token": "2_YOUR_TOKEN_HERE",
        "jitter": 0.00005,
        "image_path": "dorm.jpg",
        "image_dir": None,  # 设置为图片目录路径以启用随机选择功能
        "base_url": "http://stuhtapi.fafu.edu.cn",
        "heartbeat_interval": 900,
        "log_level": "INFO",
        "notification_enabled": False,
        "serverchan_key": None,  # Server酱 SendKey（以 SCT 开头）
        "task_keywords": ["晚归"],  # 任务关键词列表，匹配任一关键词即可
        "latest_image_dir": None,  # 最新图片目录路径（选择最新修改的图片）
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(example_config, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # 创建示例配置供参考
    create_example_config()
    print("示例配置已创建于 config.json.example")
