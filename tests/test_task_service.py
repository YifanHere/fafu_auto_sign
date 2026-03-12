"""Tests for task service module.

This module contains tests for the TaskService class,
verifying task identification, time window filtering,
and keyword matching logic.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import requests

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig, LocationConfig
from fafu_auto_sign.services.task_service import TaskService


@pytest.fixture
def mock_config():
    """Create a mock AppConfig for testing."""
    return AppConfig(
        user_token="2_TEST_TOKEN",
        location=LocationConfig(lng=118.237686, lat=25.077727, jitter=0.00005),
        base_url="http://stuhtapi.fafu.edu.cn",
    )


@pytest.fixture
def mock_client(mock_config):
    """Create a mock FAFUClient for testing."""
    return FAFUClient(mock_config)


@pytest.fixture
def task_service(mock_client):
    """Create a TaskService instance for testing."""
    return TaskService(mock_client)


@pytest.fixture
def sample_tasks():
    """Sample task list data for testing task identification logic."""
    return {
        "records": [
            {
                "id": 1001,
                "name": "晚归签到任务 - A10号楼",
                "beginTime": 1234567800000,  # 100 seconds before frozen time
                "endTime": 1234567980000,    # 90 seconds after frozen time
            },
            {
                "id": 1002,
                "name": "晚归签到任务 - B5号楼",
                "beginTime": 1234567700000,  # 190 seconds before frozen time
                "endTime": 1234567950000,    # 60 seconds after frozen time
            },
            {
                "id": 1003,
                "name": "晨跑签到任务",
                "beginTime": 1234567800000,
                "endTime": 1234567980000,
            },
            {
                "id": 1004,
                "name": "晚归签到任务 - 已过期",
                "beginTime": 1234567000000,  # long time ago
                "endTime": 1234567500000,    # expired
            },
            {
                "id": 1005,
                "name": "晚归签到任务 - 未开始",
                "beginTime": 1234568000000,  # future
                "endTime": 1234568500000,
            },
        ]
    }


@pytest.fixture
def empty_tasks():
    """Empty task list."""
    return {"records": []}


@pytest.fixture
def mock_response_with_tasks(sample_tasks):
    """Mock HTTP response with task list."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = sample_tasks
    return mock


@pytest.fixture
def mock_response_empty(empty_tasks):
    """Mock HTTP response with empty task list."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = empty_tasks
    return mock


@pytest.fixture
def frozen_time():
    """Fixed Unix timestamp for testing."""
    return 1234567890.0  # 2009-02-13 23:31:30 UTC


class TestTaskServiceInitialization:
    """Test TaskService initialization."""
    
    def test_initialization(self, mock_client):
        """Test that TaskService initializes correctly."""
        service = TaskService(mock_client)
        
        assert service.client == mock_client
        assert service.logger is not None
    
    def test_default_constants(self, task_service):
        """Test that default constants are set correctly."""
        assert task_service.TASK_LIST_ENDPOINT == "/health-api/sign_in/student/my/page"
        assert task_service.DEFAULT_ROWS == 50
        assert task_service.DEFAULT_PAGE == 1
        assert task_service.DEFAULT_SIGN_STATE == 0


class TestGetPendingTask:
    """Test get_pending_task method with various scenarios."""
    
    def test_match_active_wangui_task(self, task_service, mock_response_with_tasks, frozen_time):
        """Test matching active '晚归' task."""
        with patch.object(task_service.client, 'post', return_value=mock_response_with_tasks):
            with patch('time.time', return_value=frozen_time):
                task_id = task_service.get_pending_task()
                
                # Should return the first active "晚归" task
                assert task_id == "1001"
    
    def test_skip_non_wangui_tasks(self, task_service, frozen_time):
        """Test skipping tasks without '晚归' in name."""
        tasks_with_non_wangui = {
            "records": [
                {
                    "id": 1003,
                    "name": "晨跑签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
                {
                    "id": 1001,
                    "name": "晚归签到任务 - A10号楼",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks_with_non_wangui
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_id = task_service.get_pending_task()
                    
                    # Should skip the non-"晚归" task and match the "晚归" one
                    assert task_id == "1001"
                    
                    # Verify skip message was logged
                    skip_calls = [call for call in mock_log.call_args_list 
                                  if '跳过' in str(call)]
                    assert len(skip_calls) > 0
    
    def test_filter_expired_tasks(self, task_service, frozen_time):
        """Test filtering out expired tasks."""
        tasks_with_expired = {
            "records": [
                {
                    "id": 1004,
                    "name": "晚归签到任务 - 已过期",
                    "beginTime": 1234567000000,
                    "endTime": 1234567500000,  # expired before frozen_time
                },
                {
                    "id": 1001,
                    "name": "晚归签到任务 - A10号楼",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks_with_expired
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                task_id = task_service.get_pending_task()
                
                # Should skip expired task and return the active one
                assert task_id == "1001"
    
    def test_filter_future_tasks(self, task_service, frozen_time):
        """Test filtering out future (not started) tasks."""
        tasks_with_future = {
            "records": [
                {
                    "id": 1005,
                    "name": "晚归签到任务 - 未开始",
                    "beginTime": 1234568000000,  # future
                    "endTime": 1234568500000,
                },
                {
                    "id": 1001,
                    "name": "晚归签到任务 - A10号楼",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks_with_future
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                task_id = task_service.get_pending_task()
                
                # Should skip future task and return the active one
                assert task_id == "1001"
    
    def test_return_none_when_no_valid_tasks(self, task_service, mock_response_empty, frozen_time):
        """Test returning None when no valid tasks exist."""
        with patch.object(task_service.client, 'post', return_value=mock_response_empty):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_id = task_service.get_pending_task()
                    
                    assert task_id is None
                    
                    # Verify "no valid tasks" message was logged
                    no_task_calls = [call for call in mock_log.call_args_list 
                                     if '没有正在有效时间内' in str(call)]
                    assert len(no_task_calls) > 0
    
    def test_return_none_when_only_non_wangui_tasks(self, task_service, frozen_time):
        """Test returning None when only non-'晚归' tasks are active."""
        tasks_only_non_wangui = {
            "records": [
                {
                    "id": 1003,
                    "name": "晨跑签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks_only_non_wangui
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                task_id = task_service.get_pending_task()
                
                assert task_id is None
    
    def test_url_construction(self, task_service, mock_response_empty, frozen_time):
        """Test that URL is constructed correctly with query parameters."""
        with patch.object(task_service.client, 'post', return_value=mock_response_empty) as mock_post:
            with patch('time.time', return_value=frozen_time):
                task_service.get_pending_task()
                
                # Verify the URL was constructed correctly
                call_args = mock_post.call_args
                url = call_args[0][0]
                
                assert "/health-api/sign_in/student/my/page" in url
                assert "rows=50" in url
                assert "pageNum=1" in url
                assert "signState=0" in url
    
    def test_headers_set_correctly(self, task_service, mock_response_empty, frozen_time):
        """Test that correct headers are passed to the request."""
        with patch.object(task_service.client, 'post', return_value=mock_response_empty) as mock_post:
            with patch('time.time', return_value=frozen_time):
                task_service.get_pending_task()
                
                # Verify headers were passed
                call_kwargs = mock_post.call_args[1]
                headers = call_kwargs.get('headers', {})
                
                assert headers.get('Content-Type') == 'application/x-www-form-urlencoded'


class TestErrorHandling:
    """Test error handling in task service."""
    
    def test_network_error_handling(self, task_service):
        """Test handling of network errors."""
        with patch.object(
            task_service.client, 'post',
            side_effect=requests.exceptions.ConnectionError("Connection failed")
        ):
            with patch.object(task_service.logger, 'error') as mock_log:
                with pytest.raises(requests.exceptions.ConnectionError):
                    task_service.get_pending_task()
                
                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list 
                               if '异常' in str(call)]
                assert len(error_calls) > 0
    
    def test_json_parsing_error(self, task_service):
        """Test handling of JSON parsing errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch.object(task_service.logger, 'error') as mock_log:
                with pytest.raises(ValueError):
                    task_service.get_pending_task()
                
                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list 
                               if '异常' in str(call)]
                assert len(error_calls) > 0
    
    def test_timeout_error_handling(self, task_service):
        """Test handling of timeout errors."""
        with patch.object(
            task_service.client, 'post',
            side_effect=requests.exceptions.Timeout("Request timed out")
        ):
            with patch.object(task_service.logger, 'error') as mock_log:
                with pytest.raises(requests.exceptions.Timeout):
                    task_service.get_pending_task()
                
                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list 
                               if '异常' in str(call)]
                assert len(error_calls) > 0


class TestLogging:
    """Test logging output matches original code."""
    
    def test_request_url_logged(self, task_service, mock_response_empty, frozen_time):
        """Test that request URL is logged."""
        with patch.object(task_service.client, 'post', return_value=mock_response_empty):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_service.get_pending_task()
                    
                    # Verify URL was logged
                    url_calls = [call for call in mock_log.call_args_list 
                                 if '请求 URL' in str(call)]
                    assert len(url_calls) > 0
    
    def test_match_success_logged(self, task_service, frozen_time):
        """Test that successful match is logged correctly."""
        tasks = {
            "records": [
                {
                    "id": 1001,
                    "name": "晚归签到任务 - A10号楼",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_service.get_pending_task()
                    
                    # Verify match success message was logged
                    match_calls = [call for call in mock_log.call_args_list 
                                   if '精准匹配' in str(call)]
                    assert len(match_calls) > 0
    
    def test_skip_other_tasks_logged(self, task_service, frozen_time):
        """Test that skipping other tasks is logged correctly."""
        tasks = {
            "records": [
                {
                    "id": 1003,
                    "name": "晨跑签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks
        
        with patch.object(task_service.client, 'post', return_value=mock_response):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_service.get_pending_task()
                    
                    # Verify skip message was logged
                    skip_calls = [call for call in mock_log.call_args_list 
                                  if '跳过' in str(call)]
                    assert len(skip_calls) > 0
    
    def test_no_valid_task_logged(self, task_service, mock_response_empty, frozen_time):
        """Test that "no valid task" message is logged."""
        with patch.object(task_service.client, 'post', return_value=mock_response_empty):
            with patch('time.time', return_value=frozen_time):
                with patch.object(task_service.logger, 'info') as mock_log:
                    task_service.get_pending_task()
                    
                    # Verify no valid task message was logged
                    no_task_calls = [call for call in mock_log.call_args_list 
                                     if '没有正在有效时间内' in str(call)]
                    assert len(no_task_calls) > 0
