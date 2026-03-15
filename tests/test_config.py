"""配置模块测试。"""

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
    """AppConfig验证测试。"""

    def test_valid_config(self):
        """测试有效配置被接受。"""
        config = AppConfig(user_token="2_TEST_TOKEN_HERE")
        assert config.user_token == "2_TEST_TOKEN_HERE"
        assert config.jitter == 0.00005  # Default
        assert config.image_path == "dorm.jpg"  # Default
        assert config.base_url == "http://stuhtapi.fafu.edu.cn"  # Default
        assert config.heartbeat_interval == 900  # Default
        assert config.log_level == "INFO"  # Default

    def test_token_not_starting_with_2_(self):
        """测试不以 '2_' 开头的令牌被拒绝。"""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="INVALID_TOKEN")
        assert "用户令牌必须以 '2_' 开头" in str(exc_info.value)

    def test_empty_token(self):
        """Test empty token 开头的令牌被拒绝。"""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="")
        assert "用户令牌必须以 '2_' 开头" in str(exc_info.value)

    def test_custom_values(self):
        """测试自定义配置值。"""
        config = AppConfig(
            user_token="2_CUSTOM_TOKEN",
            jitter=0.0001,
            image_path="custom.jpg",
            base_url="http://test.example.com",
            heartbeat_interval=600,
            log_level="DEBUG",
        )
        assert config.jitter == 0.0001
        assert config.image_path == "custom.jpg"
        assert config.base_url == "http://test.example.com"
        assert config.heartbeat_interval == 600
        assert config.log_level == "DEBUG"

    def test_invalid_log_level(self):
        """Test invalid log level 开头的令牌被拒绝。"""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", log_level="INVALID")
        assert "日志级别必须是" in str(exc_info.value)

    def test_jitter_validation(self):
        """测试抖动验证。"""
        # 有效的抖动值
        config = AppConfig(user_token="2_TEST", jitter=0)
        assert config.jitter == 0

        config = AppConfig(user_token="2_TEST", jitter=0.001)
        assert config.jitter == 0.001

        # 无效的抖动 - 过高
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST", jitter=0.002)
        assert "抖动量必须在 0 到 0.001 之间" in str(exc_info.value)

        # 无效的抖动 - 负数
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST", jitter=-0.0001)
        assert "抖动量必须在 0 到 0.001 之间" in str(exc_info.value)


class TestLoadConfig:
    """load_config函数测试。"""

    def test_load_from_json_file(self, tmp_path: Path):
        """测试从JSON文件加载配置。"""
        config_data = {"user_token": "2_JSON_TOKEN", "jitter": 0.00003, "image_path": "test.jpg"}

        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config = load_config(config_file)

        assert config.user_token == "2_JSON_TOKEN"
        assert config.jitter == 0.00003
        assert config.image_path == "test.jpg"

    def test_load_from_nonexistent_file(self, tmp_path: Path):
        """测试从不存在文件加载时引发FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")

    def test_load_from_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        """测试从环境变量加载配置。"""
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_ENV_TOKEN")
        monkeypatch.setenv("FAFU_JITTER", "0.0001")
        monkeypatch.setenv("FAFU_IMAGE_PATH", "env.jpg")

        config = load_config()

        assert config.user_token == "2_ENV_TOKEN"
        assert config.jitter == 0.0001
        assert config.image_path == "env.jpg"

    def test_env_vars_override_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量覆盖JSON文件值。"""
        config_data = {"user_token": "2_JSON_TOKEN", "jitter": 0.00005}

        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        monkeypatch.setenv("FAFU_USER_TOKEN", "2_OVERRIDE_TOKEN")
        monkeypatch.setenv("FAFU_JITTER", "0.0001")

        config = load_config(config_file)

        # 环境变量应该覆盖JSON值
        assert config.user_token == "2_OVERRIDE_TOKEN"
        assert config.jitter == 0.0001

    def test_backward_compatibility_with_old_config(self, tmp_path: Path):
        """测试包含location字段的旧配置的向后兼容性。"""
        # 带location字段的旧配置格式
        config_data = {
            "user_token": "2_OLD_TOKEN",
            "location": {"lng": 118.0, "lat": 25.0, "jitter": 0.00003},
            "sign_in_position_id": 516208,
        }

        config_file = tmp_path / "old_config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # 应该成功加载，忽略额外字段
        config = load_config(config_file)

        assert config.user_token == "2_OLD_TOKEN"
        assert config.jitter == 0.00005  # Uses default, not from old location

    def test_partial_config_with_defaults(self, tmp_path: Path):
        """测试部分配置对缺失值使用默认值。"""
        config_data = {"user_token": "2_PARTIAL_TOKEN"}

        config_file = tmp_path / "partial.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config = load_config(config_file)

        assert config.user_token == "2_PARTIAL_TOKEN"
        # 检查是否使用默认值
        assert config.jitter == 0.00005
        assert config.image_path == "dorm.jpg"
        assert config.heartbeat_interval == 900
        assert config.log_level == "INFO"


class TestEdgeCases:
    """边界条件和边界情况测试。"""

    def test_boundary_jitter_min(self):
        """测试最小边界抖动值。"""
        config = AppConfig(user_token="2_TEST", jitter=0)
        assert config.jitter == 0

    def test_boundary_jitter_max(self):
        """测试最大边界抖动值。"""
        config = AppConfig(user_token="2_TEST", jitter=0.001)
        assert config.jitter == 0.001

    def test_token_with_special_characters(self):
        """测试以2_开头、包含各种字符的令牌。"""
        token = "2_ABC123_xyz-789.TEST"
        config = AppConfig(user_token=token)
        assert config.user_token == token

    def test_task_keywords_default(self):
        """测试任务关键词默认值。"""
        config = AppConfig(user_token="2_TEST_TOKEN")
        assert config.task_keywords == ["晚归"]

    def test_task_keywords_custom(self):
        """测试自定义任务关键词。"""
        config = AppConfig(user_token="2_TEST_TOKEN", task_keywords=["晚归", "查寝", "签到"])
        assert config.task_keywords == ["晚归", "查寝", "签到"]

    def test_task_keywords_validation(self):
        """测试任务关键词验证。"""
        # 测试空列表
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", task_keywords=[])
        assert "任务关键词" in str(exc_info.value)

        # 测试包含空字符串的列表
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", task_keywords=["晚归", "", "查寝"])
        assert "任务关键词" in str(exc_info.value)

        # 测试包含空白字符串的列表
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", task_keywords=["晚归", "   ", "查寝"])
        assert "任务关键词" in str(exc_info.value)

    def test_latest_image_dir_config(self, tmp_path: Path):
        """测试最新图片目录配置。"""
        # 创建一个临时目录
        test_dir = tmp_path / "latest_images"
        test_dir.mkdir()

        config = AppConfig(user_token="2_TEST_TOKEN", latest_image_dir=str(test_dir))
        assert config.latest_image_dir == str(test_dir)

    def test_latest_image_dir_validation(self, tmp_path: Path):
        """测试最新图片目录验证。"""
        # 测试不存在的目录
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", latest_image_dir="/nonexistent/path")
        assert "最新图片目录不存在" in str(exc_info.value)

        # 测试文件而非目录
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_token="2_TEST_TOKEN", latest_image_dir=str(test_file))
        assert "路径不是目录" in str(exc_info.value)


class TestLoadConfigNewFeatures:
    """测试新加载配置功能。"""

    def test_task_keywords_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """测试从环境变量加载任务关键词。"""
        monkeypatch.setenv("FAFU_USER_TOKEN", "2_ENV_TOKEN")
        monkeypatch.setenv("FAFU_TASK_KEYWORDS", "keyword1,keyword2, keyword3 , ")

        config = load_config()

        assert config.task_keywords == ["keyword1", "keyword2", "keyword3"]

    def test_latest_image_dir_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """测试从环境变量加载最新图片目录。"""
        test_dir = tmp_path / "latest_images"
        test_dir.mkdir()

        monkeypatch.setenv("FAFU_USER_TOKEN", "2_ENV_TOKEN")
        monkeypatch.setenv("FAFU_LATEST_IMAGE_DIR", str(test_dir))

        config = load_config()

        assert config.latest_image_dir == str(test_dir)
