"""
Crypto 模块测试。

测试 generate_auth_header() 和 generate_headers() 函数。
"""

import base64
import hashlib
import os
import re
import sys
from unittest.mock import patch

import pytest
from freezegun import freeze_time

# 确保导入 src 目录下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fafu_auto_sign.crypto import SECRET_KEY, generate_auth_header, generate_headers


class TestAuthHeaderFormat:
    """测试 Authorization 头格式和结构"""

    @freeze_time("2009-02-13 23:31:30")
    def test_auth_header_is_valid_base64(self, sample_token):
        """
        验证 generate_auth_header 输出是有效的 Base64 字符串
        """
        auth_header = generate_auth_header("http://test.com/api", sample_token)

        # 验证是有效的 Base64
        assert isinstance(auth_header, str)
        decoded = base64.b64decode(auth_header).decode("utf-8")
        assert ":" in decoded

    @freeze_time("2009-02-13 23:31:30")
    def test_auth_header_decoded_format(self, sample_token):
        """
        验证解码后格式为: timestamp:nonce:sign:token
        """
        auth_header = generate_auth_header("http://test.com/api", sample_token)

        decoded = base64.b64decode(auth_header).decode("utf-8")
        parts = decoded.split(":")

        # 验证有4个部分
        assert len(parts) == 4

        timestamp, nonce, sign, token = parts

        # 验证各部分格式
        assert timestamp.isdigit()  # timestamp 是数字
        assert len(nonce) == 16  # nonce 是16位
        assert len(sign) == 32  # sign 是32位 MD5
        assert token == sample_token  # token 正确

    @freeze_time("2009-02-13 23:31:30")
    def test_timestamp_is_unix_seconds(self, sample_token):
        """
        验证 timestamp 是秒级 Unix 时间戳
        """
        frozen_time = 1234567890

        auth_header = generate_auth_header("http://test.com/api", sample_token)

        decoded = base64.b64decode(auth_header).decode("utf-8")
        timestamp = decoded.split(":")[0]

        assert int(timestamp) == frozen_time

    @freeze_time("2009-02-13 23:31:30")
    def test_nonce_is_16_char_alphanumeric(self, sample_token):
        """
        验证 nonce 是16位字母数字组合
        """
        auth_header = generate_auth_header("http://test.com/api", sample_token)

        decoded = base64.b64decode(auth_header).decode("utf-8")
        nonce = decoded.split(":")[1]

        assert len(nonce) == 16
        assert re.match(r"^[a-zA-Z0-9]{16}$", nonce)

    @freeze_time("2009-02-13 23:31:30")
    def test_sign_is_32_char_hex_md5(self, sample_token):
        """
        验证 sign 是32位十六进制 MD5 哈希
        """
        auth_header = generate_auth_header("http://test.com/api", sample_token)

        decoded = base64.b64decode(auth_header).decode("utf-8")
        sign = decoded.split(":")[2]

        assert len(sign) == 32
        assert re.match(r"^[a-f0-9]{32}$", sign)


class TestAuthHeaderUrlCleanup:
    """测试 URL 清理和参数排除"""

    @freeze_time("2009-02-13 23:31:30")
    def test_url_query_params_are_excluded(self, sample_token):
        """
        验证 URL 查询参数被正确排除
        """
        # 使用带参数的 URL
        auth_header = generate_auth_header(
            "http://stuhtapi.fafu.edu.cn/api?param1=value1&param2=value2", sample_token
        )

        # 解码并检查 sign
        decoded = base64.b64decode(auth_header).decode("utf-8")
        parts = decoded.split(":")
        timestamp, nonce, sign, token = parts

        # 手动计算预期的 sign（不带参数）
        clean_url = "http://stuhtapi.fafu.edu.cn/api"
        expected_raw = f"{SECRET_KEY}{clean_url}{timestamp}{nonce}"
        expected_sign = hashlib.md5(expected_raw.encode("utf-8")).hexdigest()

        assert sign == expected_sign

    @freeze_time("2009-02-13 23:31:30")
    def test_url_with_multiple_path_segments(self, sample_token):
        """
        验证多路径段的 URL 被正确处理
        """
        auth_header = generate_auth_header(
            "http://stuhtapi.fafu.edu.cn/health-api/sign_in/student/my/page?rows=10", sample_token
        )

        decoded = base64.b64decode(auth_header).decode("utf-8")
        parts = decoded.split(":")
        timestamp, nonce, sign, token = parts

        # 验证 sign 是基于清理后的 URL
        clean_url = "http://stuhtapi.fafu.edu.cn/health-api/sign_in/student/my/page"
        expected_raw = f"{SECRET_KEY}{clean_url}{timestamp}{nonce}"
        expected_sign = hashlib.md5(expected_raw.encode("utf-8")).hexdigest()

        assert sign == expected_sign

    @freeze_time("2009-02-13 23:31:30")
    def test_http_and_https_urls_both_work(self, sample_token):
        """
        验证 HTTP 和 HTTPS URL 都能正确处理并产生不同的签名
        """
        auth_http = generate_auth_header("http://example.com/api", sample_token)
        auth_https = generate_auth_header("https://example.com/api", sample_token)

        # 两者都应该能成功解码为有效的格式
        decoded_http = base64.b64decode(auth_http).decode("utf-8")
        decoded_https = base64.b64decode(auth_https).decode("utf-8")

        # 验证格式正确
        parts_http = decoded_http.split(":")
        parts_https = decoded_https.split(":")

        assert len(parts_http) == 4
        assert len(parts_https) == 4

        # 验证协议不同导致签名不同
        assert parts_http[2] != parts_https[2]  # sign 不同


class TestAuthHeaderSignAlgorithm:
    """测试签名算法本身"""

    @freeze_time("2009-02-13 23:31:30")
    def test_sign_algorithm_with_fixed_values(self):
        """
        使用固定值验证签名算法输出（确定性测试）

        这个测试验证整个算法流程
        """
        # Mock random.choices 返回固定值
        with patch("fafu_auto_sign.crypto.random.choices", return_value=list("fixednonce123456")):
            auth_header = generate_auth_header("http://test.com/api", "test_token_123")

        # 解码并验证
        decoded = base64.b64decode(auth_header).decode("utf-8")
        parts = decoded.split(":")
        timestamp, nonce, sign, token = parts

        # 验证各部分
        assert timestamp == "1234567890"
        assert nonce == "fixednonce123456"
        assert token == "test_token_123"

        # 验证 sign 计算正确
        clean_url = "http://test.com/api"
        expected_raw = f"{SECRET_KEY}{clean_url}{timestamp}{nonce}"
        expected_sign = hashlib.md5(expected_raw.encode("utf-8")).hexdigest()
        assert sign == expected_sign

    @freeze_time("2009-02-13 23:31:30")
    def test_different_urls_produce_different_signs(self, sample_token):
        """
        验证不同 URL 产生不同的签名
        """
        auth1 = generate_auth_header("http://test.com/api1", sample_token)
        auth2 = generate_auth_header("http://test.com/api2", sample_token)

        decoded1 = base64.b64decode(auth1).decode("utf-8")
        decoded2 = base64.b64decode(auth2).decode("utf-8")

        sign1 = decoded1.split(":")[2]
        sign2 = decoded2.split(":")[2]

        assert sign1 != sign2

    @freeze_time("2009-02-13 23:31:30")
    def test_same_inputs_produce_consistent_structure(self, sample_token):
        """
        验证相同输入产生一致的结构（nonce 除外）
        """
        auth1 = generate_auth_header("http://test.com/api", sample_token)
        auth2 = generate_auth_header("http://test.com/api", sample_token)

        decoded1 = base64.b64decode(auth1).decode("utf-8")
        decoded2 = base64.b64decode(auth2).decode("utf-8")

        parts1 = decoded1.split(":")
        parts2 = decoded2.split(":")

        # timestamp 和 token 相同，nonce 和 sign 不同
        assert parts1[0] == parts2[0]  # timestamp
        assert parts1[1] != parts2[1]  # nonce (随机)
        assert parts1[2] != parts2[2]  # sign (因 nonce 不同而不同)
        assert parts1[3] == parts2[3]  # token


class TestGenerateHeaders:
    """测试 generate_headers 函数"""

    @freeze_time("2009-02-13 23:31:30")
    def test_headers_contain_required_fields(self, sample_token):
        """
        验证生成的 headers 包含所有必需字段
        """
        headers = generate_headers("http://test.com/api", sample_token)

        required_fields = [
            "Host",
            "X-Requested-With",
            "Authorization",
            "User-Agent",
            "Referer",
            "Origin",
            "Accept-Encoding",
        ]

        for field in required_fields:
            assert field in headers, f"Missing required field: {field}"

    @freeze_time("2009-02-13 23:31:30")
    def test_authorization_header_is_base64(self, sample_token):
        """
        验证 Authorization 头是 Base64 编码
        """
        headers = generate_headers("http://test.com/api", sample_token)

        auth = headers["Authorization"]

        # 验证是有效的 Base64
        decoded = base64.b64decode(auth).decode("utf-8")
        assert ":" in decoded
        parts = decoded.split(":")
        assert len(parts) == 4

    @freeze_time("2009-02-13 23:31:30")
    def test_header_values_match_expected(self, sample_token):
        """
        验证 headers 各字段值正确
        """
        headers = generate_headers("http://test.com/api", sample_token)

        assert headers["Host"] == "stuhtapi.fafu.edu.cn"
        assert headers["X-Requested-With"] == "cn.edu.fafu.iportal"
        assert (
            headers["User-Agent"]
            == "Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 HuaWei-AnyOffice/1.0.0/cn.edu.fafu.iportal"
        )
        assert headers["Referer"] == "http://stuhealth.fafu.edu.cn/"
        assert headers["Origin"] == "http://stuhealth.fafu.edu.cn"
        assert headers["Accept-Encoding"] == "gzip, deflate"

    def test_secret_key_is_correct(self):
        """
        验证 Secret Key 与原始代码一致
        """
        assert SECRET_KEY == "AtPs2O1xEnhwkKDV"
