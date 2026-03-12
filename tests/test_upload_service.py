"""Tests for upload service module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.services.upload_service import UploadService


@pytest.fixture
def mock_config():
    """Create a mock AppConfig for testing."""
    return AppConfig(
        user_token="2_TEST_TOKEN",
        base_url="http://stuhtapi.fafu.edu.cn",
    )


@pytest.fixture
def client(mock_config):
    """Create a FAFUClient instance for testing."""
    return FAFUClient(mock_config)


@pytest.fixture
def upload_service(client):
    """Create an UploadService instance for testing."""
    return UploadService(client)


class TestUploadServiceInitialization:
    """Test service initialization and basic setup."""
    
    def test_upload_service_initialization(self, client):
        """Test that upload service initializes correctly with client."""
        service = UploadService(client)
        
        assert service.client == client
        assert service.logger is not None


class TestUploadImageFileNotFound:
    """Test handling when image file does not exist."""
    
    def test_upload_image_file_not_exists(self, upload_service, caplog):
        """Test that upload returns None when file doesn't exist."""
        with caplog.at_level("ERROR"):
            result = upload_service.upload_image("/nonexistent/path/image.jpg")
        
        assert result is None
        assert "请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片" in caplog.text


class TestUploadImageSuccess:
    """Test successful image upload scenarios."""
    
    def test_upload_image_success_returns_url(self, upload_service, tmp_path):
        """Test that successful upload returns the image URL."""
        # Create a temporary file
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/welink/school/health/test123.jpg"
        
        with patch.object(upload_service.client, 'post', return_value=mock_response):
            result = upload_service.upload_image(str(image_file))
        
        assert result == "http://qiniu.example.com/welink/school/health/test123.jpg"
    
    def test_upload_image_file_handle_closed(self, upload_service, tmp_path):
        """Test that file handle is properly closed after upload (no leak)."""
        # Create a temporary file
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"
        
        # Track if file was properly closed
        original_open = open
        opened_files = []
        
        def tracking_open(*args, **kwargs):
            f = original_open(*args, **kwargs)
            opened_files.append(f)
            return f
        
        with patch('builtins.open', side_effect=tracking_open):
            with patch.object(upload_service.client, 'post', return_value=mock_response):
                result = upload_service.upload_image(str(image_file))
        
        # After the with block, all files should be closed
        assert result is not None
        for f in opened_files:
            assert f.closed, "File handle was not closed - resource leak!"
    
    def test_upload_image_logs_success(self, upload_service, tmp_path, caplog):
        """Test that successful upload logs the URL."""
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/success.jpg"
        
        with caplog.at_level("INFO"):
            with patch.object(upload_service.client, 'post', return_value=mock_response):
                upload_service.upload_image(str(image_file))
        
        assert "照片上传成功" in caplog.text
        assert "http://qiniu.example.com/success.jpg" in caplog.text


class TestUploadImageFailure:
    """Test failed image upload scenarios."""
    
    def test_upload_image_failure_returns_none(self, upload_service, tmp_path):
        """Test that failed upload returns None."""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        mock_response = Mock()
        mock_response.status_code = 500
        
        with patch.object(upload_service.client, 'post', return_value=mock_response):
            result = upload_service.upload_image(str(image_file))
        
        assert result is None
    
    def test_upload_image_exception_returns_none(self, upload_service, tmp_path):
        """Test that exception during upload returns None."""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        with patch.object(upload_service.client, 'post', side_effect=Exception("Network error")):
            result = upload_service.upload_image(str(image_file))
        
        assert result is None
    
    def test_upload_image_failure_logs_error(self, upload_service, tmp_path, caplog):
        """Test that failed upload logs appropriate error."""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        mock_response = Mock()
        mock_response.status_code = 500
        
        with caplog.at_level("ERROR"):
            with patch.object(upload_service.client, 'post', return_value=mock_response):
                upload_service.upload_image(str(image_file))
        
        assert "照片上传失败" in caplog.text


class TestUploadImageParameters:
    """Test that upload uses correct API parameters."""
    
    def test_upload_image_uses_correct_endpoint(self, upload_service, tmp_path):
        """Test that upload uses the correct API endpoint."""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"
        
        with patch.object(upload_service.client, 'post', return_value=mock_response) as mock_post:
            upload_service.upload_image(str(image_file))
            
            # Verify the endpoint was called
            call_args = mock_post.call_args
            url = call_args[0][0]
            assert "/health-api/qiniu/image/upload" in url
            assert "filePre=welink/school/health/" in url
            assert "isCompress=1" in url
            assert "isDeleteAfterDays=1" in url
    
    def test_upload_image_uses_correct_file_field(self, upload_service, tmp_path):
        """Test that upload uses correct file field format."""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"
        
        with patch.object(upload_service.client, 'post', return_value=mock_response) as mock_post:
            upload_service.upload_image(str(image_file))
            
            # Verify files parameter
            call_kwargs = mock_post.call_args[1]
            files = call_kwargs['files']
            assert 'file' in files
            file_tuple = files['file']
            assert file_tuple[0] == "dorm.jpg"  # filename
            assert file_tuple[2] == "image/jpeg"  # content type
