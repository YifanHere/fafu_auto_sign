"""上传服务模块测试。"""

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
    """为测试创建mock AppConfig。"""
    return AppConfig(
        user_token="2_TEST_TOKEN",
        base_url="http://stuhtapi.fafu.edu.cn",
    )


@pytest.fixture
def client(mock_config):
    """为测试创建FAFUClient实例。"""
    return FAFUClient(mock_config)


@pytest.fixture
def upload_service(client):
    """为测试创建UploadService实例。"""
    return UploadService(client)


class TestUploadServiceInitialization:
    """测试服务初始化和基本设置。"""

    def test_upload_service_initialization(self, client):
        """测试上传服务用客户端正确初始化。"""
        service = UploadService(client)

        assert service.client == client
        assert service.logger is not None


class TestUploadImageFileNotFound:
    """测试图片文件不存在时的处理。"""

    def test_upload_image_file_not_exists(self, upload_service, caplog):
        """测试文件不存在时上传返回None。't exist."""
        with caplog.at_level("ERROR"):
            result = upload_service.upload_image("/nonexistent/path/image.jpg")

        assert result is None
        assert "请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片" in caplog.text


class TestUploadImageSuccess:
    """测试成功的图片上传场景。"""

    def test_upload_image_success_returns_url(self, upload_service, tmp_path):
        """测试成功上传返回图片URL。"""
        # 创建临时文件
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/welink/school/health/test123.jpg"

        with patch.object(upload_service.client, "post", return_value=mock_response):
            result = upload_service.upload_image(str(image_file))

        assert result == "http://qiniu.example.com/welink/school/health/test123.jpg"

    def test_upload_image_file_handle_closed(self, upload_service, tmp_path):
        """测试上传后文件句柄被正确关闭（无泄漏）。"""
        # 创建临时文件
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"

        # 跟踪文件是否被正确关闭
        original_open = open
        opened_files = []

        def tracking_open(*args, **kwargs):
            f = original_open(*args, **kwargs)
            opened_files.append(f)
            return f

        with patch("builtins.open", side_effect=tracking_open):
            with patch.object(upload_service.client, "post", return_value=mock_response):
                result = upload_service.upload_image(str(image_file))

        # 在with块之后，所有文件都应该被关闭
        assert result is not None
        for f in opened_files:
            assert f.closed, "File handle was not closed - resource leak!"

    def test_upload_image_logs_success(self, upload_service, tmp_path, caplog):
        """测试成功上传记录URL。"""
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"fake_image_data")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/success.jpg"

        with caplog.at_level("INFO"):
            with patch.object(upload_service.client, "post", return_value=mock_response):
                upload_service.upload_image(str(image_file))

        assert "照片上传成功" in caplog.text
        assert "http://qiniu.example.com/success.jpg" in caplog.text


class TestUploadImageFailure:
    """测试失败的图片上传场景。"""

    def test_upload_image_failure_returns_none(self, upload_service, tmp_path):
        """测试失败上传返回None。"""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        mock_response = Mock()
        mock_response.status_code = 500

        with patch.object(upload_service.client, "post", return_value=mock_response):
            result = upload_service.upload_image(str(image_file))

        assert result is None

    def test_upload_image_exception_returns_none(self, upload_service, tmp_path):
        """测试上传期间异常返回None。"""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        with patch.object(upload_service.client, "post", side_effect=Exception("Network error")):
            result = upload_service.upload_image(str(image_file))

        assert result is None

    def test_upload_image_failure_logs_error(self, upload_service, tmp_path, caplog):
        """测试失败上传记录适当的错误。"""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        mock_response = Mock()
        mock_response.status_code = 500

        with caplog.at_level("ERROR"):
            with patch.object(upload_service.client, "post", return_value=mock_response):
                upload_service.upload_image(str(image_file))

        assert "照片上传失败" in caplog.text


class TestUploadImageParameters:
    """测试上传使用正确的API参数。"""

    def test_upload_image_uses_correct_endpoint(self, upload_service, tmp_path):
        """测试上传使用正确的API端点。"""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"

        with patch.object(upload_service.client, "post", return_value=mock_response) as mock_post:
            upload_service.upload_image(str(image_file))

            # 验证端点被调用
            call_args = mock_post.call_args
            url = call_args[0][0]
            assert "/health-api/qiniu/image/upload" in url
            assert "filePre=welink/school/health/" in url
            assert "isCompress=1" in url
            assert "isDeleteAfterDays=1" in url

    def test_upload_image_uses_correct_file_field(self, upload_service, tmp_path):
        """测试上传使用正确的文件字段格式。"""
        image_file = tmp_path / "dorm.jpg"
        image_file.write_bytes(b"fake_image_data")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"

        with patch.object(upload_service.client, "post", return_value=mock_response) as mock_post:
            upload_service.upload_image(str(image_file))

            # 验证files参数
            call_kwargs = mock_post.call_args[1]
            files = call_kwargs["files"]
            assert "file" in files
            file_tuple = files["file"]
            assert file_tuple[0] == "dorm.jpg"  # 文件名
            assert file_tuple[2] == "image/jpeg"  # 内容类型


class TestUploadServiceLatestImage:
    """测试上传服务选择最新修改的图片。"""

    def test_get_latest_image_returns_none_when_empty(self, upload_service, tmp_path):
        """测试目录为空时返回None。"""
        image_dir = tmp_path / "latest_images"
        image_dir.mkdir()

        result = upload_service._get_latest_image(str(image_dir))
        assert result is None

    def test_get_latest_image_returns_latest_modified(self, upload_service, tmp_path):
        """测试选择最新修改的图片。"""
        image_dir = tmp_path / "latest_images"
        image_dir.mkdir()
        import os
        import time

        # 创建多张图片，设置不同修改时间
        image1 = image_dir / "image1.jpg"
        image1.write_bytes(b"data1")
        base_time = time.time()
        os.utime(str(image1), (base_time, base_time))

        image2 = image_dir / "image2.jpg"
        image2.write_bytes(b"data2")
        # 设置image2为最新（修改时间比image1晚10秒）
        os.utime(str(image2), (base_time + 10, base_time + 10))

        image3 = image_dir / "image3.jpg"
        image3.write_bytes(b"data3")
        # image3修改时间比image2晚10秒
        os.utime(str(image3), (base_time + 20, base_time + 20))

        result = upload_service._get_latest_image(str(image_dir))
        assert result == str(image3.resolve())

    def test_upload_image_uses_latest_image_dir_priority(
        self, upload_service, tmp_path, mock_config
    ):
        """测试latest_image_dir优先级最高。"""
        latest_dir = tmp_path / "latest_images"
        latest_dir.mkdir()
        random_dir = tmp_path / "random_images"
        random_dir.mkdir()

        latest_image = latest_dir / "latest.jpg"
        latest_image.write_bytes(b"latest_data")

        random_image = random_dir / "random.jpg"
        random_image.write_bytes(b"random_data")

        # 设置配置
        mock_config.latest_image_dir = str(latest_dir)
        mock_config.image_dir = str(random_dir)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "http://qiniu.example.com/test.jpg"

        with patch.object(upload_service.client, "post", return_value=mock_response) as mock_post:
            upload_service.upload_image("fallback.jpg")

            # 验证使用了latest_image
            call_kwargs = mock_post.call_args[1]
            files = call_kwargs["files"]
            assert files["file"][0] == "latest.jpg"
