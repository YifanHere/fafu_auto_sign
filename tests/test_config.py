"""Tests for configuration module."""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from pydantic import ValidationError

from fafu_auto_sign.config import AppConfig, load_config


class TestAppConfig:
    """Tests for AppConfig validation."""
    
    def test_valid_config(self):
        """Test valid configuration is accepted."""
        config = AppConfig(
            user_token="2_TEST_TOKEN_HERE"
        )
        assert config.user_token == "2_TEST_TOKEN_HERE"
        assert config.jitter == 0.00005  # Default
        assert config.image_path == "dorm.jpg"  # Default
        assert config.base_url == "http://stuhtapi.fafu.edu.cn"  # Default
        assert config.heartbeat_interval == 900  # Default
        assert config.log_level == "INFO"  # Default
    
    def test_token_not_starting_with_2_(self):
        """Test token not starting with '2_' is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token="INVALID_TOKEN"
            )
        assert "User token must start with '2_'" in str(exc_info.value)
    
    def test_empty_token(self):
        """Test empty token is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token=""
            )
        assert "User token must start with '2_'" in str(exc_info.value)
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = AppConfig(
            user_token="2_CUSTOM_TOKEN",
            jitter=0.0001,
            image_path="custom.jpg",
            base_url="http://test.example.com",
            heartbeat_interval=600,
            log_level="DEBUG"
        )
        assert config.jitter == 0.0001
        assert config.image_path == "custom.jpg"
        assert config.base_url == "http://test.example.com"
        assert config.heartbeat_interval == 600
        assert config.log_level == "DEBUG"
    
    def test_invalid_log_level(self):
        """Test invalid log level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token="2_TEST_TOKEN",
                log_level="INVALID"
            )
        assert "Log level must be one of" in str(exc_info.value)

    def test_jitter_validation(self):
        """Test jitter validation."""
        # Valid jitter values
        config = AppConfig(user_token="2_TEST", jitter=0)
        assert config.jitter == 0
        
        config = AppConfig(user_token="2_TEST", jitter=0.001)
        assert config.jitter == 0.001
        
        # Invalid jitter - too high
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST", jitter=0.002)
        assert "Jitter must be between 0 and 0.001" in str(exc_info.value)
        
        # Invalid jitter - negative
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST", jitter=-0.0001)
        assert "Jitter must be between 0 and 0.001" in str(exc_info.value)


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_from_json_file(self, tmp_path: Path):
        """Test loading configuration from JSON file."""
        config_data = {
            "user_token": "2_JSON_TOKEN",
            "jitter": 0.00003,
            "image_path": "test.jpg"
        }
        
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.user_token == "2_JSON_TOKEN"
        assert config.jitter == 0.00003
        assert config.image_path == "test.jpg"
    
    def test_load_from_nonexistent_file(self, tmp_path: Path):
        """Test loading from nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")
    
    def test_load_from_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_ENV_TOKEN")
        monkeypatch.setenv("FAFU_JITTER", "0.0001")
        monkeypatch.setenv("FAFU_IMAGE_PATH", "env.jpg")
        
        config = load_config()
        
        assert config.user_token == "2_ENV_TOKEN"
        assert config.jitter == 0.0001
        assert config.image_path == "env.jpg"
    
    def test_env_vars_override_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test environment variables override JSON file values."""
        config_data = {
            "user_token": "2_JSON_TOKEN",
            "jitter": 0.00005
        }
        
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_OVERRIDE_TOKEN")
        monkeypatch.setenv("FAFU_JITTER", "0.0001")
        
        config = load_config(config_file)
        
        # Environment variables should override JSON values
        assert config.user_token == "2_OVERRIDE_TOKEN"
        assert config.jitter == 0.0001
    
    def test_backward_compatibility_with_old_config(self, tmp_path: Path):
        """Test backward compatibility with old config containing location field."""
        # Old config format with location field
        config_data = {
            "user_token": "2_OLD_TOKEN",
            "location": {
                "lng": 118.0,
                "lat": 25.0,
                "jitter": 0.00003
            },
            "sign_in_position_id": 516208
        }
        
        config_file = tmp_path / "old_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        # Should load successfully, ignoring extra fields
        config = load_config(config_file)
        
        assert config.user_token == "2_OLD_TOKEN"
        assert config.jitter == 0.00005  # Uses default, not from old location
    
    def test_partial_config_with_defaults(self, tmp_path: Path):
        """Test partial config uses defaults for missing values."""
        config_data = {
            "user_token": "2_PARTIAL_TOKEN"
        }
        
        config_file = tmp_path / "partial.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.user_token == "2_PARTIAL_TOKEN"
        # Check defaults are used
        assert config.jitter == 0.00005
        assert config.image_path == "dorm.jpg"
        assert config.heartbeat_interval == 900
        assert config.log_level == "INFO"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_boundary_jitter_min(self):
        """Test minimum boundary jitter value."""
        config = AppConfig(user_token="2_TEST", jitter=0)
        assert config.jitter == 0
    
    def test_boundary_jitter_max(self):
        """Test maximum boundary jitter value."""
        config = AppConfig(user_token="2_TEST", jitter=0.001)
        assert config.jitter == 0.001
    
    def test_token_with_special_characters(self):
        """Test token with various characters starting with 2_."""
        token = "2_ABC123_xyz-789.TEST"
        config = AppConfig(user_token=token)
        assert config.user_token == token
