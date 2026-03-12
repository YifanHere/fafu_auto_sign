"""HTTP client module for FAFU Auto Sign.

This module provides a custom HTTP client with retry logic,
session management, and proper error handling.
"""

import logging
import sys
import time
from typing import Any

import requests
from requests import Response
from requests.exceptions import RequestException

from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.crypto import generate_headers


class FAFUClient:
    """HTTP client with retry logic and session management.
    
    Features:
    - Application-level retry with exponential backoff
    - Dynamic Authorization header generation on each retry
    - Special handling for 401 (token expired) and 408 (time sync error)
    - Context manager support
    - Configurable timeouts
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1  # Base delay in seconds (1, 2, 4...)
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
    
    # Timeout configuration (connect, read)
    TIMEOUT = (10, 30)
    
    def __init__(self, config: AppConfig):
        """Initialize the HTTP client.
        
        Args:
            config: Application configuration containing base_url and user_token.
        """
        self.config = config
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        """Make an HTTP request with retry logic.
        
        This method implements application-level retry with exponential backoff.
        On each retry, a new Authorization header is generated with a fresh timestamp.
        
        Special status codes:
        - 401: Token expired - terminates the program
        - 408: Time sync error - terminates the program
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL (relative or absolute)
            **kwargs: Additional arguments passed to requests
        
        Returns:
            Response object from the successful request.
            
        Raises:
            RequestException: If all retries are exhausted.
            SystemExit: If 401 or 408 status code is received.
        """
        # Ensure URL is absolute
        if not url.startswith("http"):
            full_url = f"{self.config.base_url.rstrip('/')}/{url.lstrip('/')}"
        else:
            full_url = url
        
        # Merge timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.TIMEOUT
        
        last_exception: RequestException | None = None
        
        for attempt in range(self.MAX_RETRIES):
            # Generate fresh headers on each attempt (important for retry!)
            headers = generate_headers(full_url, self.config.user_token)
            
            # Allow custom headers to override generated ones
            if "headers" in kwargs:
                custom_headers = kwargs.pop("headers")
                headers.update(custom_headers)
            
            try:
                self.logger.debug(f"Request {attempt + 1}/{self.MAX_RETRIES}: {method} {full_url}")
                response = self.session.request(method, full_url, headers=headers, **kwargs)
                
                # Handle special status codes that terminate the program
                if response.status_code == 401:
                    self.logger.error("Token 已过期，请重新抓包获取并更新配置文件！")
                    sys.exit(1)
                
                if response.status_code == 408:
                    self.logger.error("运行脚本的系统时间与标准北京时间不一致，签名校验失败，请校准系统时间！")
                    sys.exit(1)
                
                # Check if we should retry based on status code
                if response.status_code in self.RETRY_STATUS_CODES:
                    if attempt < self.MAX_RETRIES - 1:
                        delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                        self.logger.warning(
                            f"Received status {response.status_code}, "
                            f"retrying in {delay}s... (attempt {attempt + 1}/{self.MAX_RETRIES})"
                        )
                        time.sleep(delay)
                        continue
                
                # Raise for other HTTP errors (4xx, 5xx not in retry list)
                response.raise_for_status()
                
                self.logger.debug(f"Request successful: {response.status_code}")
                return response
                
            except RequestException as e:
                last_exception = e
                
                # Check if it's a connection error or timeout that we should retry
                should_retry = False
                if isinstance(e, requests.exceptions.Timeout):
                    should_retry = True
                    self.logger.warning(f"Request timeout on attempt {attempt + 1}")
                elif isinstance(e, requests.exceptions.ConnectionError):
                    should_retry = True
                    self.logger.warning(f"Connection error on attempt {attempt + 1}")
                elif hasattr(e, 'response') and e.response is not None:
                    # Already handled above, but just in case
                    if e.response.status_code in self.RETRY_STATUS_CODES:
                        should_retry = True
                
                if should_retry and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    self.logger.warning(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    # Don't retry, re-raise the exception
                    raise
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        
        # This should never happen, but just in case
        raise RequestException(f"Failed after {self.MAX_RETRIES} attempts")
    
    def get(self, url: str, **kwargs: Any) -> Response:
        """Make a GET request."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs: Any) -> Response:
        """Make a POST request."""
        return self.request("POST", url, **kwargs)
    
    def close(self) -> None:
        """Close the session and release resources."""
        self.session.close()
        self.logger.debug("Session closed")
    
    def __enter__(self) -> "FAFUClient":
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close session."""
        self.close()
