"""Configuration module for FAFU Auto Sign.

This module provides Pydantic-based configuration management with support for
JSON files, environment variables, and .env files.
"""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocationConfig(BaseModel):
    """Location configuration with coordinate validation."""
    
    lng: float = Field(..., description="Longitude (-180 to 180)")
    lat: float = Field(..., description="Latitude (-90 to 90)")
    jitter: float = Field(default=0.00005, description="Maximum jitter amount (0 to 0.001)")
    
    @field_validator("lng")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within valid range."""
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v
    
    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within valid range."""
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v
    
    @field_validator("jitter")
    @classmethod
    def validate_jitter(cls, v: float) -> float:
        """Validate jitter is within valid range."""
        if not 0 <= v <= 0.001:
            raise ValueError(f"Jitter must be between 0 and 0.001, got {v}")
        return v


class AppConfig(BaseSettings):
    """Application configuration with validation.
    
    Configuration priority (highest to lowest):
    1. Environment variables (FAFU_*)
    2. .env file
    3. JSON config file
    4. Default values
    """
    
    model_config = SettingsConfigDict(
        env_prefix="FAFU_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )
    
    # Required fields
    user_token: str = Field(..., description="User token (must start with '2_')")
    location: LocationConfig = Field(..., description="Location configuration")
    
    # Optional fields with defaults
    image_path: str = Field(default="dorm.jpg", description="Path to dormitory image")
    base_url: str = Field(default="http://stuhtapi.fafu.edu.cn", description="API base URL")
    heartbeat_interval: int = Field(default=900, description="Heartbeat interval in seconds")
    sign_in_position_id: int = Field(default=516208, description="Sign-in position ID")
    log_level: str = Field(default="INFO", description="Logging level")
    
    @field_validator("user_token")
    @classmethod
    def validate_token_format(cls, v: str) -> str:
        """Validate user token starts with '2_'."""
        if not v.startswith("2_"):
            raise ValueError(f"User token must start with '2_', got: {v[:20]}...")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}, got {v}")
        return v.upper()


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from file and environment.
    
    Args:
        config_path: Path to JSON config file. If None, only environment variables
                     and .env file are used.
    
    Returns:
        AppConfig: Validated configuration object.
    
    Raises:
        FileNotFoundError: If config file is specified but doesn't exist.
        ValueError: If configuration validation fails.
    
    Example:
        >>> config = load_config("config.json")
        >>> config = load_config()  # Use env vars and .env only
    """
    config_dict: dict[str, Any] = {}
    
    # Load from JSON file if provided
    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    
    # Environment variables take precedence over JSON file values
    # Check for environment variables and override JSON values
    if os.environ.get("FAFU_USER_TOKEN"):
        config_dict["user_token"] = os.environ.get("FAFU_USER_TOKEN")
    
    # Handle nested location config from environment variables
    location = config_dict.get("location", {})
    if os.environ.get("FAFU_LOCATION__LNG"):
        location["lng"] = float(os.environ.get("FAFU_LOCATION__LNG"))
    if os.environ.get("FAFU_LOCATION__LAT"):
        location["lat"] = float(os.environ.get("FAFU_LOCATION__LAT"))
    if os.environ.get("FAFU_LOCATION__JITTER"):
        location["jitter"] = float(os.environ.get("FAFU_LOCATION__JITTER"))
    if location:
        config_dict["location"] = location
    
    # Handle other top-level environment variables
    if os.environ.get("FAFU_IMAGE_PATH"):
        config_dict["image_path"] = os.environ.get("FAFU_IMAGE_PATH")
    if os.environ.get("FAFU_BASE_URL"):
        config_dict["base_url"] = os.environ.get("FAFU_BASE_URL")
    if os.environ.get("FAFU_HEARTBEAT_INTERVAL"):
        config_dict["heartbeat_interval"] = int(os.environ.get("FAFU_HEARTBEAT_INTERVAL"))
    if os.environ.get("FAFU_SIGN_IN_POSITION_ID"):
        config_dict["sign_in_position_id"] = int(os.environ.get("FAFU_SIGN_IN_POSITION_ID"))
    if os.environ.get("FAFU_LOG_LEVEL"):
        config_dict["log_level"] = os.environ.get("FAFU_LOG_LEVEL")
    
    return AppConfig(**config_dict)


def create_example_config(path: str | Path = "config.json.example") -> None:
    """Create an example configuration file.
    
    Args:
        path: Path where to create the example config file.
    """
    example_config = {
        "user_token": "2_YOUR_TOKEN_HERE",
        "location": {
            "lng": 118.237686,
            "lat": 25.077727,
            "jitter": 0.00005
        },
        "image_path": "dorm.jpg",
        "base_url": "http://stuhtapi.fafu.edu.cn",
        "heartbeat_interval": 900,
        "sign_in_position_id": 516208,
        "log_level": "INFO"
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(example_config, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Create example config for reference
    create_example_config()
    print("Example config created at config.json.example")
