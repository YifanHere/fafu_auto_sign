# FAFU Auto Sign - 福建农林大学自动签到助手

__version__ = "0.1.0"

from fafu_auto_sign.config import AppConfig, LocationConfig, load_config

__all__ = ["AppConfig", "LocationConfig", "load_config"]
from fafu_auto_sign.logging_config import setup_logging

__all__ = ["AppConfig", "LocationConfig", "load_config", "setup_logging"]