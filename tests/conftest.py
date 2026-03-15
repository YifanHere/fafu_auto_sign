"""
Pytest fixtures for characterization tests.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_token():
    """测试用的固定 token"""
    return "2_test_token_for_testing_only"


@pytest.fixture
def mock_time():
    """
    返回固定的 Unix 时间戳
    """
    frozen_time = 1234567890.0  # 2009-02-13 23:31:30 UTC
    return frozen_time


@pytest.fixture
def sample_tasks():
    """
    示例任务列表数据，用于测试任务识别逻辑
    """
    return {
        "records": [
            {
                "id": 1001,
                "name": "晚归签到任务 - A10号楼",
                "beginTime": 1234567800000,  # 比当前时间早 100 秒
                "endTime": 1234567980000,  # 比当前时间晚 90 秒
            },
            {
                "id": 1002,
                "name": "晚归签到任务 - B5号楼",
                "beginTime": 1234567700000,  # 比当前时间早 190 秒
                "endTime": 1234567950000,  # 比当前时间晚 60 秒
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
                "beginTime": 1234567000000,  # 很久以前
                "endTime": 1234567500000,  # 已过期
            },
            {
                "id": 1005,
                "name": "晚归签到任务 - 未开始",
                "beginTime": 1234568000000,  # 将来
                "endTime": 1234568500000,
            },
        ]
    }


@pytest.fixture
def empty_tasks():
    """空任务列表"""
    return {"records": []}


@pytest.fixture
def mock_response_success():
    """Mock 成功的 HTTP 响应"""
    mock = MagicMock()
    mock.status_code = 200
    mock.text = '{"records": []}'
    mock.json.return_value = {"records": []}
    return mock


@pytest.fixture
def mock_response_with_tasks(sample_tasks):
    """Mock 包含任务列表的 HTTP 响应"""
    mock = MagicMock()
    mock.status_code = 200
    mock.text = '{"records": [...]}'
    mock.json.return_value = sample_tasks
    return mock
