"""FAFU 自动签到的配置模块。

本模块提供基于 Pydantic 的配置管理，支持
JSON 文件、环境变量和 .env 文件。
"""
import json
import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
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
    base_url: str = Field(default="http://stuhtapi.fafu.edu.cn", description="API 基础 URL")
    heartbeat_interval: int = Field(default=900, description="心跳间隔（秒）")
    log_level: str = Field(default="INFO", description="日志级别")
    
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
    if os.environ.get("FAFU_BASE_URL"):
        config_dict["base_url"] = os.environ.get("FAFU_BASE_URL")
    interval_env = os.environ.get("FAFU_HEARTBEAT_INTERVAL")
    if interval_env:
        config_dict["heartbeat_interval"] = int(interval_env)
    if os.environ.get("FAFU_LOG_LEVEL"):
        config_dict["log_level"] = os.environ.get("FAFU_LOG_LEVEL")
    
    return AppConfig(**config_dict)



def create_example_config(path: str | Path = "config.json.example") -> None:
    """创建示例配置文件。
    
    参数:
        path: 创建示例配置文件的路径。
    """
    example_config = {
        "user_token": "2_YOUR_TOKEN_HERE",
        "jitter": 0.00005,
        "image_path": "dorm.jpg",
        "base_url": "http://stuhtapi.fafu.edu.cn",
        "heartbeat_interval": 900,
        "log_level": "INFO"
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(example_config, f, indent=2, ensure_ascii=False)



if __name__ == "__main__":
    # 创建示例配置供参考
    create_example_config()
    print("示例配置已创建于 config.json.example")
