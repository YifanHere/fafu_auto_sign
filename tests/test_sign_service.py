"""Tests for the sign-in service.

This module tests the SignService class, including:
- Successful and failed sign-in submissions
- GPS jitter calculation and range validation
- Correct parameter passing (URL query params)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig, LocationConfig
from fafu_auto_sign.services.sign_service import SignService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = MagicMock(spec=AppConfig)
    config.location = MagicMock(spec=LocationConfig)
    config.location.lng = 118.237686
    config.location.lat = 25.077727
    config.sign_in_position_id = 516208
    return config


@pytest.fixture
def mock_client():
    """Create a mock HTTP client for testing."""
    client = MagicMock(spec=FAFUClient)
    return client


@pytest.fixture
def sign_service(mock_client, mock_config):
    """Create a SignService instance with mocked dependencies."""
    return SignService(mock_client, mock_config)


class TestSubmitSign:
    """Tests for the submit_sign method."""
    
    def test_submit_sign_success_returns_true(self, sign_service, mock_client):
        """Test that successful sign-in returns True."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"code": 200, "message": "success"}'
        mock_client.post.return_value = mock_response
        
        # Act
        result = sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        assert result is True
    
    def test_submit_sign_failure_returns_false(self, sign_service, mock_client):
        """Test that failed sign-in returns False."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"code": 400, "message": "bad request"}'
        mock_client.post.return_value = mock_response
        
        # Act
        result = sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        assert result is False
    
    def test_submit_sign_uses_url_query_params(self, sign_service, mock_client):
        """Test that parameters are passed as URL query params, not JSON body."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        # Act
        sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        call_args = mock_client.post.call_args
        
        # Check URL
        assert call_args[0][0] == "/health-api/sign_in/task_123/student/sign"
        
        # Check that params kwarg was used (URL query params)
        assert "params" in call_args.kwargs
        params = call_args.kwargs["params"]
        
        # Verify required parameters are present
        assert "lng" in params
        assert "lat" in params
        assert params["signImg"] == "http://example.com/image.jpg"
        assert params["signInPositionId"] == 516208
    
    def test_submit_sign_formats_coordinates_to_6_decimal_places(self, sign_service, mock_client):
        """Test that coordinates are formatted to 6 decimal places."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        # Act
        sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        call_args = mock_client.post.call_args
        params = call_args.kwargs["params"]
        
        # Check that lng and lat are formatted to 6 decimal places
        lng_value = params["lng"]
        lat_value = params["lat"]
        
        # They should be strings with 6 decimal places
        assert isinstance(lng_value, str)
        assert isinstance(lat_value, str)
        
        # Verify decimal places (split by dot and check fractional part)
        lng_decimals = lng_value.split(".")[1] if "." in lng_value else ""
        lat_decimals = lat_value.split(".")[1] if "." in lat_value else ""
        
        assert len(lng_decimals) == 6
        assert len(lat_decimals) == 6


class TestGPSJitter:
    """Tests for GPS coordinate jitter functionality."""
    
    def test_gps_jitter_within_range(self, sign_service, mock_client):
        """Test that GPS jitter is within ±0.00005 degrees."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        base_lng = 118.237686
        base_lat = 25.077727
        
        # Act - Run multiple times to test randomness
        for _ in range(100):
            mock_client.reset_mock()
            sign_service.submit_sign("task_123", "http://example.com/image.jpg")
            
            call_args = mock_client.post.call_args
            params = call_args.kwargs["params"]
            
            actual_lng = float(params["lng"])
            actual_lat = float(params["lat"])
            
            # Assert - Check jitter is within expected range
            lng_diff = abs(actual_lng - base_lng)
            lat_diff = abs(actual_lat - base_lat)
            
            assert lng_diff <= 0.000051, f"Longitude jitter {lng_diff} exceeds max 0.00005"
            assert lat_diff <= 0.000051, f"Latitude jitter {lat_diff} exceeds max 0.00005"

    
    def test_gps_jitter_is_randomized(self, sign_service, mock_client):
        """Test that GPS coordinates are randomized (not always the same)."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        coordinates = []
        
        # Act - Collect multiple coordinate pairs
        for _ in range(10):
            mock_client.reset_mock()
            sign_service.submit_sign("task_123", "http://example.com/image.jpg")
            
            call_args = mock_client.post.call_args
            params = call_args.kwargs["params"]
            
            coordinates.append((float(params["lng"]), float(params["lat"])))
        
        # Assert - Check that not all coordinates are identical
        unique_coordinates = set(coordinates)
        assert len(unique_coordinates) > 1, "GPS coordinates should be randomized"
    
    def test_calculate_jittered_coordinates_returns_tuple(self, sign_service):
        """Test the helper method returns correct tuple format."""
        # Act
        lng, lat = sign_service._calculate_jittered_coordinates()
        
        # Assert
        assert isinstance(lng, float)
        assert isinstance(lat, float)
        
        # Check jitter range
        base_lng = 118.237686
        base_lat = 25.077727
        
        assert abs(lng - base_lng) <= 0.00005
        assert abs(lat - base_lat) <= 0.00005


class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    def test_submit_sign_handles_exception_returns_false(self, sign_service, mock_client):
        """Test that exceptions are handled and return False."""
        # Arrange
        mock_client.post.side_effect = Exception("Network error")
        
        # Act
        result = sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        assert result is False
    
    def test_submit_sign_logs_success_message(self, sign_service, mock_client, caplog):
        """Test that success message is logged."""
        # Arrange
        import logging
        caplog.set_level(logging.INFO)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        # Act
        sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        assert "✅ 签到成功" in caplog.text
    
    def test_submit_sign_logs_failure_message(self, sign_service, mock_client, caplog):
        """Test that failure message is logged."""
        # Arrange
        import logging
        caplog.set_level(logging.ERROR)
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response
        
        # Act
        sign_service.submit_sign("task_123", "http://example.com/image.jpg")
        
        # Assert
        assert "❌ 签到失败" in caplog.text
        assert "500" in caplog.text
