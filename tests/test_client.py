"""Tests for HTTP client module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import requests

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig


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


class TestFAFUClientInitialization:
    """Test client initialization and basic setup."""

    def test_client_initialization(self, mock_config):
        """Test that client initializes correctly with config."""
        client = FAFUClient(mock_config)

        assert client.config == mock_config
        assert client.session is not None
        assert isinstance(client.session, requests.Session)

    def test_close_session(self, client):
        """Test that close() properly closes the session."""
        with patch.object(client.session, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()


class TestFAFUClientContextManager:
    """Test context manager support."""

    def test_context_manager_entry(self, client):
        """Test that __enter__ returns the client instance."""
        with patch.object(client.session, "close"):
            entered = client.__enter__()
            assert entered is client

    def test_context_manager_exit_closes_session(self, client):
        """Test that __exit__ closes the session."""
        with patch.object(client.session, "close") as mock_close:
            client.__exit__(None, None, None)
            mock_close.assert_called_once()

    def test_with_statement_usage(self, mock_config):
        """Test that 'with' statement works correctly."""
        with patch("requests.Session.close") as mock_close:
            with FAFUClient(mock_config) as client:
                assert isinstance(client, FAFUClient)
                assert client.config == mock_config
            # After exiting, close should be called
            mock_close.assert_called_once()


class TestRequestMethod:
    """Test the main request method with various scenarios."""

    def test_successful_request(self, client):
        """Test a successful request without retry."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                mock_generate.return_value = {"Authorization": "test_auth"}

                response = client.request("GET", "/test")

                assert response == mock_response
                mock_request.assert_called_once()
                # Verify headers were generated
                mock_generate.assert_called_once()

    def test_request_with_absolute_url(self, client):
        """Test request with absolute URL is used as-is."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response):
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                mock_generate.return_value = {}

                client.request("GET", "http://example.com/test")

                # Verify generate_headers was called with the full URL
                call_args = mock_generate.call_args
                assert call_args[0][0] == "http://example.com/test"

    def test_request_with_relative_url(self, client):
        """Test request with relative URL gets base_url prepended."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response):
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                mock_generate.return_value = {}

                client.request("GET", "/api/test")

                # Verify generate_headers was called with the full URL
                call_args = mock_generate.call_args
                assert call_args[0][0] == "http://stuhtapi.fafu.edu.cn/api/test"

    def test_request_timeout_configuration(self, client):
        """Test that timeout is properly configured."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                client.request("GET", "/test")

                # Verify timeout is set correctly
                call_kwargs = mock_request.call_args[1]
                assert call_kwargs["timeout"] == (10, 30)

    def test_custom_timeout_override(self, client):
        """Test that custom timeout can override default."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                client.request("GET", "/test", timeout=(5, 15))

                call_kwargs = mock_request.call_args[1]
                assert call_kwargs["timeout"] == (5, 15)


class TestRetryLogic:
    """Test application-level retry mechanism."""

    def test_retry_on_429_status(self, client):
        """Test that 429 status triggers retry."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.raise_for_status.return_value = None

        with patch.object(
            client.session, "request", side_effect=[mock_response_429, mock_response_200]
        ) as mock_request:
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                with patch("time.sleep") as mock_sleep:
                    mock_generate.return_value = {}

                    response = client.request("GET", "/test")

                    assert response == mock_response_200
                    assert mock_request.call_count == 2
                    # Should have slept with exponential backoff (1 second)
                    mock_sleep.assert_called_once_with(1)

    def test_retry_on_500_status(self, client):
        """Test that 500 status triggers retry."""
        mock_response_500 = Mock()
        mock_response_500.status_code = 500

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.raise_for_status.return_value = None

        with patch.object(
            client.session, "request", side_effect=[mock_response_500, mock_response_200]
        ):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("time.sleep"):
                    response = client.request("GET", "/test")
                    assert response.status_code == 200

    def test_retry_on_connection_error(self, client):
        """Test that connection error triggers retry."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(
            client.session,
            "request",
            side_effect=[requests.exceptions.ConnectionError("Connection failed"), mock_response],
        ):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("time.sleep"):
                    response = client.request("GET", "/test")
                    assert response == mock_response

    def test_retry_on_timeout(self, client):
        """Test that timeout triggers retry."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(
            client.session,
            "request",
            side_effect=[requests.exceptions.Timeout("Request timed out"), mock_response],
        ):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("time.sleep"):
                    response = client.request("GET", "/test")
                    assert response == mock_response

    def test_max_retries_exhausted(self, client):
        """Test that exception is raised after max retries."""
        mock_response_503 = Mock()
        mock_response_503.status_code = 503

        with patch.object(client.session, "request", return_value=mock_response_503):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("time.sleep"):
                    # After 3 retries, the last response should trigger raise_for_status
                    mock_response_503.raise_for_status.side_effect = requests.exceptions.HTTPError(
                        "503 Error"
                    )

                    with pytest.raises(requests.exceptions.HTTPError):
                        client.request("GET", "/test")

    def test_exponential_backoff_delays(self, client):
        """Test that exponential backoff delays are correct."""
        mock_response_503 = Mock()
        mock_response_503.status_code = 503

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.raise_for_status.return_value = None

        with patch.object(
            client.session,
            "request",
            side_effect=[mock_response_503, mock_response_503, mock_response_200],
        ):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("time.sleep") as mock_sleep:
                    client.request("GET", "/test")

                    # Should have slept for 1s and 2s (exponential backoff)
                    assert mock_sleep.call_count == 2
                    mock_sleep.assert_any_call(1)
                    mock_sleep.assert_any_call(2)

    def test_fresh_headers_on_each_retry(self, client):
        """Test that Authorization header is regenerated on each retry."""
        mock_response_502 = Mock()
        mock_response_502.status_code = 502

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.raise_for_status.return_value = None

        with patch.object(
            client.session,
            "request",
            side_effect=[mock_response_502, mock_response_502, mock_response_200],
        ):
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                mock_generate.return_value = {}

                with patch("time.sleep"):
                    client.request("GET", "/test")

                    # generate_headers should be called 3 times (once per attempt)
                    assert mock_generate.call_count == 3


class TestSpecialStatusCodes:
    """Test handling of special status codes that terminate the program."""

    def test_401_triggers_exit(self, client):
        """Test that 401 status triggers sys.exit."""
        mock_response = Mock()
        mock_response.status_code = 401

        with patch.object(client.session, "request", return_value=mock_response):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("sys.exit") as mock_exit:
                    with patch.object(client.logger, "error") as mock_error:
                        client.request("GET", "/test")

                        # Verify error message was logged
                        mock_error.assert_called_once_with(
                            "Token 已过期，请重新抓包获取并更新配置文件！"
                        )
                        # Verify sys.exit was called with code 1
                        mock_exit.assert_called_once_with(1)

    def test_408_triggers_exit(self, client):
        """Test that 408 status triggers sys.exit."""
        mock_response = Mock()
        mock_response.status_code = 408

        with patch.object(client.session, "request", return_value=mock_response):
            with patch("fafu_auto_sign.client.generate_headers", return_value={}):
                with patch("sys.exit") as mock_exit:
                    with patch.object(client.logger, "error") as mock_error:
                        client.request("GET", "/test")

                        # Verify error message was logged
                        mock_error.assert_called_once_with(
                            "运行脚本的系统时间与标准北京时间不一致，签名校验失败，请校准系统时间！"
                        )
                        # Verify sys.exit was called with code 1
                        mock_exit.assert_called_once_with(1)


class TestConvenienceMethods:
    """Test GET and POST convenience methods."""

    def test_get_method(self, client):
        """Test that get() calls request() with correct method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client, "request", return_value=mock_response) as mock_request:
            client.get("/test")

            mock_request.assert_called_once_with("GET", "/test")

    def test_post_method(self, client):
        """Test that post() calls request() with correct method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client, "request", return_value=mock_response) as mock_request:
            client.post("/test", json={"key": "value"})

            mock_request.assert_called_once_with("POST", "/test", json={"key": "value"})

    def test_post_with_files(self, client):
        """Test that post() works with file uploads."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        files = {"file": ("test.jpg", b"fake_image_data")}

        with patch.object(client, "request", return_value=mock_response) as mock_request:
            client.post("/upload", files=files)

            mock_request.assert_called_once_with("POST", "/upload", files=files)


class TestHeaderOverride:
    """Test custom header handling."""

    def test_custom_headers_merge_with_generated(self, client):
        """Test that custom headers can override generated ones."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            with patch("fafu_auto_sign.client.generate_headers") as mock_generate:
                mock_generate.return_value = {
                    "Authorization": "generated_auth",
                    "User-Agent": "default_agent",
                }

                client.request(
                    "GET", "/test", headers={"X-Custom": "value", "User-Agent": "custom_agent"}
                )

                call_kwargs = mock_request.call_args[1]
                headers = call_kwargs["headers"]

                # Custom header should be present
                assert headers["X-Custom"] == "value"
                # Generated header should be preserved
                assert headers["Authorization"] == "generated_auth"
                # Custom header should override generated one
                assert headers["User-Agent"] == "custom_agent"
