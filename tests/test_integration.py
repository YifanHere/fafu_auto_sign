"""Integration tests for FAFU Auto Sign complete workflow."""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest
from pydantic import ValidationError

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig, load_config
from fafu_auto_sign.services import TaskService, SignService
from fafu_auto_sign.services.task_service import TaskDetails
from fafu_auto_sign.services.upload_service import UploadService
from fafu_auto_sign.crypto import generate_auth_header


def create_test_config(tmp_path):
    """Helper to create test config and image."""
    config_data = {
        "user_token": "2_test_token_12345",
        "jitter": 0.00005,
        "image_path": str(tmp_path / "test.jpg"),
        "base_url": "http://test.example.com",
        "heartbeat_interval": 900,
        "log_level": "INFO"
    }
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    
    (tmp_path / "test.jpg").write_bytes(b"fake image data")
    return load_config(str(config_file))


class TestIntegrationWorkflow:
    """Integration tests for complete sign-in workflow."""

    def test_complete_sign_in_workflow(self, tmp_path):
        """Test complete workflow: task -> upload -> sign."""
        config = create_test_config(tmp_path)
        
        # Create client with mocked session
        client = FAFUClient(config)
        mock_session = MagicMock()
        client.session = mock_session
        
        # Mock task response
        mock_task_response = Mock()
        mock_task_response.json.return_value = {
            "records": [{
                "id": 123,
                "name": "晚归签到",
                "beginTime": 0,
                "endTime": 9999999999999
            }]
        }
        mock_task_response.status_code = 200
        
        # Mock task details response
        mock_task_details_response = Mock()
        mock_task_details_response.json.return_value = {
            "signInPositions": [{
                "id": 516208,
                "lng": "118.237686",
                "lat": "25.077727",
                "positionName": "测试位置"
            }]
        }
        mock_task_details_response.status_code = 200
        
        # Mock upload response
        mock_upload_response = Mock()
        mock_upload_response.text = "http://qiniu.com/image.jpg"
        mock_upload_response.status_code = 200
        
        # Mock sign response
        mock_sign_response = Mock()
        mock_sign_response.status_code = 200
        mock_sign_response.json.return_value = {"success": True}
        
        mock_session.request.side_effect = [
            mock_task_response,
            mock_task_details_response,
            mock_upload_response,
            mock_sign_response
        ]
        
        task_service = TaskService(client)
        upload_service = UploadService(client)
        sign_service = SignService(client, config)
        
        # Step 1: Get task
        task_id = task_service.get_pending_task()
        assert task_id == "123"
        
        # Step 2: Get task details
        task_details = task_service.get_task_details(int(task_id))
        assert task_details is not None
        assert task_details.position_id == 516208
        assert task_details.base_lng == 118.237686
        assert task_details.base_lat == 25.077727
        
        # Step 3: Upload image
        img_url = upload_service.upload_image(config.image_path)
        assert img_url == "http://qiniu.com/image.jpg"
        
        # Step 4: Submit sign with new API
        result = sign_service.submit_sign(
            int(task_id),
            task_details.position_id,
            task_details.base_lng,
            task_details.base_lat,
            img_url
        )
        assert result is True

    def test_no_pending_task_scenario(self, tmp_path):
        """Test workflow when no tasks are available."""
        config = create_test_config(tmp_path)
        
        client = FAFUClient(config)
        mock_session = MagicMock()
        client.session = mock_session
        
        # Mock empty task response
        mock_response = Mock()
        mock_response.json.return_value = {"records": []}
        mock_response.status_code = 200
        mock_session.request.return_value = mock_response
        
        task_service = TaskService(client)
        task_id = task_service.get_pending_task()
        
        assert task_id is None

    def test_network_error_handling(self, tmp_path):
        """Test network error handling in workflow."""
        config = create_test_config(tmp_path)
        
        client = FAFUClient(config)
        mock_session = MagicMock()
        client.session = mock_session
        
        from requests.exceptions import ConnectionError
        mock_session.request.side_effect = ConnectionError("Network unreachable")
        
        task_service = TaskService(client)
        
        # Should raise ConnectionError after all retries exhausted
        with pytest.raises(ConnectionError):
            task_service.get_pending_task()

    def test_authorization_header_format(self):
        """Test Authorization header format compliance."""
        url = "http://stuhtapi.fafu.edu.cn/test"
        user_token = "2_test_token_abc123"
        
        auth_header = generate_auth_header(url, user_token)
        
        # Decode base64
        import base64
        decoded = base64.b64decode(auth_header).decode("utf-8")
        
        # Format: timestamp:nonce:sign:user_token
        parts = decoded.split(":")
        assert len(parts) == 4
        
        timestamp, nonce, sign, token = parts
        
        # Verify timestamp is numeric
        assert timestamp.isdigit()
        
        # Verify nonce is 16 characters
        assert len(nonce) == 16
        
        # Verify sign is 32 characters (MD5)
        assert len(sign) == 32
        
        # Verify token starts with '2_'
        assert token.startswith("2_")


class TestMainModuleIntegration:
    """Integration tests for main module entry point."""

    def test_main_with_config_argument(self, tmp_path):
        """Test main() with --config argument."""
        config = create_test_config(tmp_path)
        config_file = tmp_path / "test_config.json"
        with open(config_file, "w") as f:
            json.dump({
                "user_token": config.user_token,
                "jitter": config.jitter,
                "image_path": config.image_path,
                "base_url": config.base_url,
                "heartbeat_interval": config.heartbeat_interval,
                "log_level": config.log_level
            }, f)
        
        with patch("fafu_auto_sign.main.FAFUClient") as mock_client_class, \
             patch("fafu_auto_sign.main.GracefulShutdown") as mock_shutdown_class:
            
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_class.return_value.__exit__ = Mock(return_value=False)
            
            mock_shutdown = MagicMock()
            mock_shutdown_class.return_value = mock_shutdown
            mock_shutdown.is_stopped.side_effect = [False, True]
            mock_shutdown.wait.return_value = True
            
            mock_task_service = MagicMock()
            mock_task_service.get_pending_task.return_value = None
            
            with patch("fafu_auto_sign.main.TaskService", return_value=mock_task_service), \
                 patch("fafu_auto_sign.main.UploadService"), \
                 patch("fafu_auto_sign.main.SignService"):
                
                from fafu_auto_sign.main import run
                run(str(config_file))


class TestConfigIntegration:
    """Integration tests for configuration loading."""

    def test_load_config_from_file(self, tmp_path):
        """Test loading config from JSON file."""
        config = create_test_config(tmp_path)
        
        assert config.user_token == "2_test_token_12345"
        assert config.jitter == 0.00005
        assert config.image_path == str(tmp_path / "test.jpg")
        assert config.base_url == "http://test.example.com"
        assert config.heartbeat_interval == 900
        assert config.log_level == "INFO"
        
    def test_config_missing_required_fields(self, tmp_path):
        """Test config validation for missing required fields."""
        config_data = {
            "jitter": 0.00005,
            "image_path": "test.jpg"
            # Missing user_token
        }
        config_file = tmp_path / "invalid_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        with pytest.raises(ValidationError):
            load_config(str(config_file))
        """Test loading config from JSON file."""
        config = create_test_config(tmp_path)
        
        assert config.user_token == "2_test_token_12345"
        assert config.location.lng == 118.237686
        assert config.location.lat == 25.077727
        assert config.image_path == str(tmp_path / "test.jpg")
        assert config.base_url == "http://test.example.com"

    def test_config_missing_required_fields(self, tmp_path):
        """Test config validation for missing required fields."""
        config_data = {
            "location": {"lng": 118.237686, "lat": 25.077727}
            # Missing user_token, image_path, etc.
        }
        config_file = tmp_path / "invalid_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        with pytest.raises(ValidationError):
            load_config(str(config_file))
