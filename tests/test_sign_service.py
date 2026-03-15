"""签到服务测试。

本模块测试SignService类，包括：
- 成功和失败的签到提交
- GPS抖动计算和范围验证
- 正确的参数传递（URL查询参数）
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.services.sign_service import SignService


@pytest.fixture
def mock_config():
    """为测试创建mock配置。"""
    config = MagicMock(spec=AppConfig)
    config.jitter = 0.00005
    return config


@pytest.fixture
def mock_client():
    """为测试创建mock HTTP客户端。"""
    client = MagicMock(spec=FAFUClient)
    return client


@pytest.fixture
def sign_service(mock_client, mock_config):
    """使用mock依赖创建SignService实例。"""
    return SignService(mock_client, mock_config)


class TestSubmitSign:
    """submit_sign方法测试。"""

    def test_submit_sign_success_returns_true(self, sign_service, mock_client):
        """测试成功签到返回True。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"code": 200, "message": "success"}'
        mock_client.post.return_value = mock_response

        # 执行
        result = sign_service.submit_sign(
            123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg"
        )

        # 验证
        assert result is True

    def test_submit_sign_failure_returns_false(self, sign_service, mock_client):
        """测试失败签到返回False。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"code": 400, "message": "bad request"}'
        mock_client.post.return_value = mock_response

        # 执行
        result = sign_service.submit_sign(
            123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg"
        )

        # 验证
        assert result is False

    def test_submit_sign_uses_url_query_params(self, sign_service, mock_client):
        """测试参数作为URL查询参数传递，而非JSON body。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        # 执行
        sign_service.submit_sign(123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg")

        # 验证
        call_args = mock_client.post.call_args

        # 检查URL
        assert call_args[0][0] == "/health-api/sign_in/123/student/sign"

        # 检查使用了params kwargs（URL查询参数）
        assert "params" in call_args.kwargs
        params = call_args.kwargs["params"]

        # 验证必需参数存在
        assert "lng" in params
        assert "lat" in params
        assert params["signImg"] == "http://example.com/image.jpg"
        assert params["signInPositionId"] == 516208

    def test_submit_sign_formats_coordinates_to_6_decimal_places(self, sign_service, mock_client):
        """测试坐标格式化为6位小数。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        # 执行
        sign_service.submit_sign(123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg")

        # 验证
        call_args = mock_client.post.call_args
        params = call_args.kwargs["params"]

        # 检查lng和lat格式化为6位小数
        lng_value = params["lng"]
        lat_value = params["lat"]

        # 它们应该是带6位小数的字符串
        assert isinstance(lng_value, str)
        assert isinstance(lat_value, str)

        # 验证小数位数（用小数点分割并检查小数部分）
        lng_decimals = lng_value.split(".")[1] if "." in lng_value else ""
        lat_decimals = lat_value.split(".")[1] if "." in lat_value else ""

        assert len(lng_decimals) == 6
        assert len(lat_decimals) == 6


class TestGPSJitter:
    """GPS坐标抖动功能测试。"""

    def test_gps_jitter_within_range(self, sign_service, mock_client):
        """测试GPS抖动在±0.00005度范围内。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        base_lng = 118.237686
        base_lat = 25.077727
        jitter = 0.00005

        # 执行 - Run multiple times to test randomness
        for _ in range(100):
            mock_client.reset_mock()
            sign_service.submit_sign(
                123, 516208, base_lng, base_lat, "http://example.com/image.jpg"
            )

            call_args = mock_client.post.call_args
            params = call_args.kwargs["params"]

            actual_lng = float(params["lng"])
            actual_lat = float(params["lat"])

            # 验证 - Check jitter is within expected range
            lng_diff = abs(actual_lng - base_lng)
            lat_diff = abs(actual_lat - base_lat)

            assert lng_diff <= jitter * 1.01, f"Longitude jitter {lng_diff} exceeds max {jitter}"
            assert lat_diff <= jitter * 1.01, f"Latitude jitter {lat_diff} exceeds max {jitter}"

    def test_gps_jitter_is_randomized(self, sign_service, mock_client):
        """测试GPS坐标是随机的（不总是相同）。"""
        # 准备
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        coordinates = []

        # 执行 - Collect multiple coordinate pairs
        for _ in range(10):
            mock_client.reset_mock()
            sign_service.submit_sign(
                123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg"
            )

            call_args = mock_client.post.call_args
            params = call_args.kwargs["params"]

            coordinates.append((float(params["lng"]), float(params["lat"])))

        # 验证 - Check that not all coordinates are identical
        unique_coordinates = set(coordinates)
        assert len(unique_coordinates) > 1, "GPS coordinates should be randomized"

    def test_calculate_jittered_coordinates_returns_tuple(self, sign_service):
        """测试辅助方法返回正确的元组格式。"""
        base_lng = 118.237686
        base_lat = 25.077727
        jitter = 0.00005

        # 执行
        lng, lat = sign_service._calculate_jittered_coordinates(base_lng, base_lat)

        # 验证
        assert isinstance(lng, float)
        assert isinstance(lat, float)

        # 检查抖动范围
        assert abs(lng - base_lng) <= jitter
        assert abs(lat - base_lat) <= jitter


class TestErrorHandling:
    """错误处理场景测试。"""

    def test_submit_sign_handles_exception_returns_false(self, sign_service, mock_client):
        """测试异常被捕获并返回False。"""
        # 准备
        mock_client.post.side_effect = Exception("Network error")

        # 执行
        result = sign_service.submit_sign(
            123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg"
        )

        # 验证
        assert result is False

    def test_submit_sign_logs_success_message(self, sign_service, mock_client, caplog):
        """测试成功消息被记录。"""
        # 准备
        import logging

        caplog.set_level(logging.INFO)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        # 执行
        sign_service.submit_sign(123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg")

        # 验证
        assert "✅ 签到成功" in caplog.text

    def test_submit_sign_logs_failure_message(self, sign_service, mock_client, caplog):
        """测试失败消息被记录。"""
        # 准备
        import logging

        caplog.set_level(logging.ERROR)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        # 执行
        sign_service.submit_sign(123, 516208, 118.237686, 25.077727, "http://example.com/image.jpg")

        # 验证
        assert "❌ 签到失败" in caplog.text
        assert "500" in caplog.text
