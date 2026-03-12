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

from fafu_auto_sign.config import AppConfig, LocationConfig, load_config

import json
import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from fafu_auto_sign.config import AppConfig, LocationConfig, load_config


class TestLocationConfig:
    """Tests for LocationConfig validation."""
    
    def test_valid_coordinates(self):
        """Test valid coordinates are accepted."""
        loc = LocationConfig(lng=118.237686, lat=25.077727)
        assert loc.lng == 118.237686
        assert loc.lat == 25.077727
        assert loc.jitter == 0.00005  # Default value
    
    def test_valid_coordinates_with_jitter(self):
        """Test valid coordinates with custom jitter."""
        loc = LocationConfig(lng=118.237686, lat=25.077727, jitter=0.0001)
        assert loc.jitter == 0.0001
    
    def test_longitude_too_low(self):
        """Test longitude below -180 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=-181, lat=25.077727)
        assert "Longitude must be between -180 and 180" in str(exc_info.value)
    
    def test_longitude_too_high(self):
        """Test longitude above 180 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=181, lat=25.077727)
        assert "Longitude must be between -180 and 180" in str(exc_info.value)
    
    def test_latitude_too_low(self):
        """Test latitude below -90 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=118.237686, lat=-91)
        assert "Latitude must be between -90 and 90" in str(exc_info.value)
    
    def test_latitude_too_high(self):
        """Test latitude above 90 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=118.237686, lat=91)
        assert "Latitude must be between -90 and 90" in str(exc_info.value)
    
    def test_jitter_too_high(self):
        """Test jitter above 0.001 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=118.237686, lat=25.077727, jitter=0.002)
        assert "Jitter must be between 0 and 0.001" in str(exc_info.value)
    
    def test_jitter_negative(self):
        """Test negative jitter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LocationConfig(lng=118.237686, lat=25.077727, jitter=-0.0001)
        assert "Jitter must be between 0 and 0.001" in str(exc_info.value)


class TestAppConfig:
    """Tests for AppConfig validation."""
    
    def test_valid_config(self):
        """Test valid configuration is accepted."""
        config = AppConfig(
            user_token="2_TEST_TOKEN_HERE",
            location=LocationConfig(lng=118.237686, lat=25.077727)
        )
        assert config.user_token == "2_TEST_TOKEN_HERE"
        assert config.location.lng == 118.237686
        assert config.image_path == "dorm.jpg"  # Default
        assert config.base_url == "http://stuhtapi.fafu.edu.cn"  # Default
        assert config.heartbeat_interval == 900  # Default
        assert config.sign_in_position_id == 516208  # Default
        assert config.log_level == "INFO"  # Default
    
    def test_token_not_starting_with_2_(self):
        """Test token not starting with '2_' is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token="INVALID_TOKEN",
                location=LocationConfig(lng=118.237686, lat=25.077727)
            )
        assert "User token must start with '2_'" in str(exc_info.value)
    
    def test_empty_token(self):
        """Test empty token is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token="",
                location=LocationConfig(lng=118.237686, lat=25.077727)
            )
        assert "User token must start with '2_'" in str(exc_info.value)
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = AppConfig(
            user_token="2_CUSTOM_TOKEN",
            location=LocationConfig(lng=120.0, lat=30.0, jitter=0.0001),
            image_path="custom.jpg",
            base_url="http://test.example.com",
            heartbeat_interval=600,
            sign_in_position_id=123456,
            log_level="DEBUG"
        )
        assert config.image_path == "custom.jpg"
        assert config.base_url == "http://test.example.com"
        assert config.heartbeat_interval == 600
        assert config.sign_in_position_id == 123456
        assert config.log_level == "DEBUG"
    
    def test_invalid_log_level(self):
        """Test invalid log level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                user_token="2_TEST_TOKEN",
                location=LocationConfig(lng=118.237686, lat=25.077727),
                log_level="INVALID"
            )
        assert "Log level must be one of" in str(exc_info.value)


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_from_json_file(self, tmp_path: Path):
        """Test loading configuration from JSON file."""
        config_data = {
            "user_token": "2_JSON_TOKEN",
            "location": {
                "lng": 119.0,
                "lat": 26.0,
                "jitter": 0.00003
            },
            "image_path": "test.jpg"
        }
        
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.user_token == "2_JSON_TOKEN"
        assert config.location.lng == 119.0
        assert config.location.lat == 26.0
        assert config.location.jitter == 0.00003
        assert config.image_path == "test.jpg"
    
    def test_load_from_nonexistent_file(self, tmp_path: Path):
        """Test loading from nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")
    
    def test_load_from_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_ENV_TOKEN")
        monkeypatch.setenv("FAFU_LOCATION__LNG", "118.5")
        monkeypatch.setenv("FAFU_LOCATION__LAT", "25.5")
        monkeypatch.setenv("FAFU_IMAGE_PATH", "env.jpg")
        monkeypatch.setenv("FAFU_LOCATION_LNG", "118.5")
        monkeypatch.setenv("FAFU_LOCATION_LAT", "25.5")
        monkeypatch.setenv("FAFU_IMAGE_PATH", "env.jpg")
        
        config = load_config()
        
        assert config.user_token == "2_ENV_TOKEN"
        assert config.location.lng == 118.5
        assert config.location.lat == 25.5
        assert config.image_path == "env.jpg"
    
    def test_env_vars_override_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test environment variables override JSON file values."""
        config_data = {
            "user_token": "2_JSON_TOKEN",
            "location": {
                "lng": 119.0,
                "lat": 26.0
            }
        }
        
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_OVERRIDE_TOKEN")
        monkeypatch.setenv("FAFU_LOCATION__LNG", "120.0")
        monkeypatch.setenv("FAFU_LOCATION_LNG", "120.0")
        
        config = load_config(config_file)
        
        # Environment variables should override JSON values
        assert config.user_token == "2_OVERRIDE_TOKEN"
        assert config.location.lng == 120.0
        # Other values from JSON should be preserved
        assert config.location.lat == 26.0
    
    def test_invalid_json_structure(self, tmp_path: Path):
        """Test invalid JSON structure raises ValidationError."""
        config_file = tmp_path / "invalid.json"
        with open(config_file, "w") as f:
            json.dump({"invalid": "structure"}, f)
        
        with pytest.raises(ValidationError):
            load_config(config_file)
    
    def test_partial_config_with_defaults(self, tmp_path: Path):
        """Test partial config uses defaults for missing values."""
        config_data = {
            "user_token": "2_PARTIAL_TOKEN",
            "location": {
                "lng": 118.0,
                "lat": 25.0
            }
        }
        
        config_file = tmp_path / "partial.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(config_file)
        
        assert config.user_token == "2_PARTIAL_TOKEN"
        assert config.location.lng == 118.0
        # Check defaults are used
        assert config.image_path == "dorm.jpg"
        assert config.heartbeat_interval == 900
        assert config.sign_in_position_id == 516208


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_boundary_longitude_min(self):
        """Test minimum boundary longitude value."""
        loc = LocationConfig(lng=-180, lat=0)
        assert loc.lng == -180
    
    def test_boundary_longitude_max(self):
        """Test maximum boundary longitude value."""
        loc = LocationConfig(lng=180, lat=0)
        assert loc.lng == 180
    
    def test_boundary_latitude_min(self):
        """Test minimum boundary latitude value."""
        loc = LocationConfig(lng=0, lat=-90)
        assert loc.lat == -90
    
    def test_boundary_latitude_max(self):
        """Test maximum boundary latitude value."""
        loc = LocationConfig(lng=0, lat=90)
        assert loc.lat == 90
    
    def test_boundary_jitter_min(self):
        """Test minimum boundary jitter value."""
        loc = LocationConfig(lng=118, lat=25, jitter=0)
        assert loc.jitter == 0
    
    def test_boundary_jitter_max(self):
        """Test maximum boundary jitter value."""
        loc = LocationConfig(lng=118, lat=25, jitter=0.001)
        assert loc.jitter == 0.001
    
    def test_token_with_special_characters(self):
        """Test token with various characters starting with 2_."""
        token = "2_ABC123_xyz-789.TEST"
        config = AppConfig(
            user_token=token,
            location=LocationConfig(lng=118, lat=25)
        )
        assert config.user_token == token
    
    def test_location_as_dict(self):
        """Test location can be passed as dict."""
        config = AppConfig(
            user_token="2_TEST",
            location={"lng": 118.5, "lat": 25.5}
        )
        assert config.location.lng == 118.5
        assert config.location.lat == 25.5
