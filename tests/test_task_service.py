"""任务服务模块测试。

本模块包含TaskService类的测试，
验证任务识别、时间窗口过滤
和关键词匹配逻辑。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path before importing package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import requests

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.services.task_service import TaskDetails, TaskService


@pytest.fixture
def mock_config():
    """为测试创建mock AppConfig。"""
    return AppConfig(
        user_token="2_TEST_TOKEN",
        jitter=0.00005,
        base_url="http://stuhtapi.fafu.edu.cn",
    )


@pytest.fixture
def mock_client(mock_config):
    """为测试创建mock FAFUClient。"""
    return FAFUClient(mock_config)


@pytest.fixture
def task_service(mock_client, mock_config):
    """为测试创建TaskService实例。"""
    return TaskService(mock_client, mock_config)


@pytest.fixture
def sample_tasks():
    """用于测试任务识别逻辑的示例任务列表数据。"""
    return {
        "records": [
            {
                "id": 1001,
                "name": "晚归签到任务 - A10号楼",
                "beginTime": 1234567800000,  # 冻结时间前100秒
                "endTime": 1234567980000,  # 冻结时间后90秒
            },
            {
                "id": 1002,
                "name": "晚归签到任务 - B5号楼",
                "beginTime": 1234567700000,  # 冻结时间前190秒
                "endTime": 1234567950000,  # 冻结时间后60秒
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
    """空任务列表。"""
    return {"records": []}


@pytest.fixture
def mock_response_with_tasks(sample_tasks):
    """带任务列表的mock HTTP响应。"""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = sample_tasks
    return mock


@pytest.fixture
def mock_response_empty(empty_tasks):
    """带空任务列表的mock HTTP响应。"""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = empty_tasks
    return mock


@pytest.fixture
def frozen_time():
    """用于测试的固定Unix时间戳。"""
    return 1234567890.0  # 2009-02-13 23:31:30 UTC


class TestTaskServiceInitialization:
    """测试TaskService初始化。"""

    def test_initialization(self, mock_client, mock_config):
        """测试TaskService正确初始化。"""
        service = TaskService(mock_client, mock_config)

        assert service.client == mock_client
        assert service.config == mock_config
        assert service.logger is not None

    def test_default_constants(self, task_service):
        """测试默认常量设置正确。"""
        assert task_service.TASK_LIST_ENDPOINT == "/health-api/sign_in/student/my/page"
        assert task_service.DEFAULT_ROWS == 50
        assert task_service.DEFAULT_PAGE == 1
        assert task_service.DEFAULT_SIGN_STATE == 0


class TestGetPendingTasks:
    """用各种场景测试get_pending_tasks方法。"""

    def test_match_multiple_active_tasks(self, task_service, mock_response_with_tasks, frozen_time):
        """测试匹配多个活跃任务。"""
        with patch.object(task_service.client, "post", return_value=mock_response_with_tasks):
            with patch("time.time", return_value=frozen_time):
                task_ids = task_service.get_pending_tasks()

                # Should return both active "晚归" tasks (1001 and 1002)
                assert task_ids == ["1001", "1002"]

    def test_limit_to_10_tasks(self, task_service, frozen_time):
        """测试限制最多返回10个任务。"""
        # Create 15 tasks
        tasks_many = {
            "records": [
                {
                    "id": i,
                    "name": f"晚归签到任务 - {i}",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                }
                for i in range(1001, 1016)
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = tasks_many

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                task_ids = task_service.get_pending_tasks()

                assert len(task_ids) == 10
                assert task_ids == [str(i) for i in range(1001, 1011)]

    def test_use_config_task_keywords(self, task_service, mock_config, frozen_time):
        """测试使用配置中的任务关键词。"""
        # Modify config to have ["晨跑", "晚归"]
        mock_config.task_keywords = ["晨跑", "晚归"]

        tasks_with_keywords = {
            "records": [
                {
                    "id": 1001,
                    "name": "晚归签到任务 - A10号楼",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
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
        mock_response.json.return_value = tasks_with_keywords

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                task_ids = task_service.get_pending_tasks()

                assert task_ids == ["1001", "1003"]

    def test_return_empty_list_when_no_valid_tasks(
        self, task_service, mock_response_empty, frozen_time
    ):
        """测试没有有效任务时返回空列表。"""
        with patch.object(task_service.client, "post", return_value=mock_response_empty):
            with patch("time.time", return_value=frozen_time):
                task_ids = task_service.get_pending_tasks()

                assert task_ids == []


class TestGetPendingTask:
    """用各种场景测试get_pending_task方法。"""

    def test_match_active_wangui_task(self, task_service, mock_response_with_tasks, frozen_time):
        """测试匹配活跃的"晚归"任务。"""
        with patch.object(task_service.client, "post", return_value=mock_response_with_tasks):
            with patch("time.time", return_value=frozen_time):
                task_id = task_service.get_pending_task()

                # Should return the first active "晚归" task
                assert task_id == "1001"

    def test_skip_non_wangui_tasks(self, task_service, frozen_time):
        """测试跳过名称中不含"晚归"的任务。"""
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_id = task_service.get_pending_task()

                    # Should skip the non-"晚归" task and match the "晚归" one
                    assert task_id == "1001"

                    # Verify skip message was logged
                    skip_calls = [call for call in mock_log.call_args_list if "跳过" in str(call)]
                    assert len(skip_calls) > 0

    def test_filter_expired_tasks(self, task_service, frozen_time):
        """测试过滤掉已过期任务。"""
        tasks_with_expired = {
            "records": [
                {
                    "id": 1004,
                    "name": "晚归签到任务 - 已过期",
                    "beginTime": 1234567000000,
                    "endTime": 1234567500000,  # 已过期 before frozen_time
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                task_id = task_service.get_pending_task()

                # Should skip expired task and return the active one
                assert task_id == "1001"

    def test_filter_future_tasks(self, task_service, frozen_time):
        """测试过滤掉将来（未开始）的任务。"""
        tasks_with_future = {
            "records": [
                {
                    "id": 1005,
                    "name": "晚归签到任务 - 未开始",
                    "beginTime": 1234568000000,  # 将来
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                task_id = task_service.get_pending_task()

                # Should skip future task and return the active one
                assert task_id == "1001"

    def test_return_none_when_no_valid_tasks(self, task_service, mock_response_empty, frozen_time):
        """测试没有有效任务时返回None。"""
        with patch.object(task_service.client, "post", return_value=mock_response_empty):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_id = task_service.get_pending_task()

                    assert task_id is None

                    # Verify "no valid tasks" message was logged
                    no_task_calls = [
                        call
                        for call in mock_log.call_args_list
                        if "没有正在有效时间内" in str(call)
                    ]
                    assert len(no_task_calls) > 0

    def test_return_none_when_only_non_wangui_tasks(self, task_service, frozen_time):
        """测试只有非"晚归"任务活跃时返回None。"""
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                task_id = task_service.get_pending_task()

                assert task_id is None

    def test_url_construction(self, task_service, mock_response_empty, frozen_time):
        """测试URL用查询参数正确构造。"""
        with patch.object(
            task_service.client, "post", return_value=mock_response_empty
        ) as mock_post:
            with patch("time.time", return_value=frozen_time):
                task_service.get_pending_task()

                # Verify the URL was constructed correctly
                call_args = mock_post.call_args
                url = call_args[0][0]

                assert "/health-api/sign_in/student/my/page" in url
                assert "rows=50" in url
                assert "pageNum=1" in url
                assert "signState=0" in url

    def test_headers_set_correctly(self, task_service, mock_response_empty, frozen_time):
        """测试正确的头部被传递给请求。"""
        with patch.object(
            task_service.client, "post", return_value=mock_response_empty
        ) as mock_post:
            with patch("time.time", return_value=frozen_time):
                task_service.get_pending_task()

                # Verify headers were passed
                call_kwargs = mock_post.call_args[1]
                headers = call_kwargs.get("headers", {})

                assert headers.get("Content-Type") == "application/x-www-form-urlencoded"


class TestErrorHandling:
    """测试任务服务中的错误处理。"""

    def test_network_error_handling(self, task_service):
        """测试网络错误处理。"""
        with patch.object(
            task_service.client,
            "post",
            side_effect=requests.exceptions.ConnectionError("Connection failed"),
        ):
            with patch.object(task_service.logger, "error") as mock_log:
                with pytest.raises(requests.exceptions.ConnectionError):
                    task_service.get_pending_task()

                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list if "异常" in str(call)]
                assert len(error_calls) > 0

    def test_json_parsing_error(self, task_service):
        """测试JSON解析错误处理。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch.object(task_service.logger, "error") as mock_log:
                with pytest.raises(ValueError):
                    task_service.get_pending_task()

                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list if "异常" in str(call)]
                assert len(error_calls) > 0

    def test_timeout_error_handling(self, task_service):
        """测试超时错误处理。"""
        with patch.object(
            task_service.client,
            "post",
            side_effect=requests.exceptions.Timeout("Request timed out"),
        ):
            with patch.object(task_service.logger, "error") as mock_log:
                with pytest.raises(requests.exceptions.Timeout):
                    task_service.get_pending_task()

                # Verify error was logged
                error_calls = [call for call in mock_log.call_args_list if "异常" in str(call)]
                assert len(error_calls) > 0


class TestLogging:
    """测试日志输出与原始代码匹配。"""

    def test_request_url_logged(self, task_service, mock_response_empty, frozen_time):
        """测试请求URL被记录。"""
        with patch.object(task_service.client, "post", return_value=mock_response_empty):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_service.get_pending_task()

                    # Verify URL was logged
                    url_calls = [
                        call for call in mock_log.call_args_list if "请求 URL" in str(call)
                    ]
                    assert len(url_calls) > 0

    def test_match_success_logged(self, task_service, frozen_time):
        """测试成功匹配被正确记录。"""
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_service.get_pending_task()

                    # Verify match success message was logged
                    match_calls = [
                        call for call in mock_log.call_args_list if "精准匹配" in str(call)
                    ]
                    assert len(match_calls) > 0

    def test_skip_other_tasks_logged(self, task_service, frozen_time):
        """测试跳过其他任务被正确记录。"""
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

        with patch.object(task_service.client, "post", return_value=mock_response):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_service.get_pending_task()

                    # Verify skip message was logged
                    skip_calls = [call for call in mock_log.call_args_list if "跳过" in str(call)]
                    assert len(skip_calls) > 0

    def test_no_valid_task_logged(self, task_service, mock_response_empty, frozen_time):
        """测试"没有有效任务"消息被记录。"""
        with patch.object(task_service.client, "post", return_value=mock_response_empty):
            with patch("time.time", return_value=frozen_time):
                with patch.object(task_service.logger, "info") as mock_log:
                    task_service.get_pending_task()

                    # Verify no valid task message was logged
                    no_task_calls = [
                        call
                        for call in mock_log.call_args_list
                        if "没有正在有效时间内" in str(call)
                    ]
                    assert len(no_task_calls) > 0


class TestGetTaskDetails:
    """用各种场景测试get_task_details方法。"""

    def test_get_task_details_success(self, task_service):
        """测试成功获取任务详情。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {
                    "id": 516208,
                    "lng": "118.23672800",
                    "lat": "25.07728900",
                    "positionName": "福建农林大学安溪校区学生公寓A10号楼",
                    "radius": 160,
                }
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response):
            result = task_service.get_task_details(12345)

            assert result is not None
            assert isinstance(result, TaskDetails)
            assert result.task_id == 12345
            assert result.position_id == 516208
            assert result.base_lng == 118.23672800
            assert result.base_lat == 25.07728900
            assert result.position_name == "福建农林大学安溪校区学生公寓A10号楼"

    def test_get_task_details_empty_positions(self, task_service):
        """测试空signInPositions列表的处理。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"signInPositions": []}

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "warning") as mock_log:
                result = task_service.get_task_details(12345)

                assert result is None

                # Verify warning was logged
                warning_calls = [
                    call for call in mock_log.call_args_list if "没有签到位置信息" in str(call)
                ]
                assert len(warning_calls) > 0

    def test_get_task_details_none_positions(self, task_service):
        """测试None signInPositions的处理。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"signInPositions": None}

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "warning") as mock_log:
                result = task_service.get_task_details(12345)

                assert result is None

                # Verify warning was logged
                warning_calls = [
                    call for call in mock_log.call_args_list if "没有签到位置信息" in str(call)
                ]
                assert len(warning_calls) > 0

    def test_get_task_details_missing_positions_key(self, task_service):
        """测试缺少signInPositions键的处理。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "warning") as mock_log:
                result = task_service.get_task_details(12345)

                assert result is None

    def test_get_task_details_network_error(self, task_service):
        """测试网络错误处理。"""
        with patch.object(
            task_service.client,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection failed"),
        ):
            with patch.object(task_service.logger, "error") as mock_log:
                result = task_service.get_task_details(12345)

                assert result is None

                # Verify error was logged
                error_calls = [
                    call
                    for call in mock_log.call_args_list
                    if "获取任务详情时发生异常" in str(call)
                ]
                assert len(error_calls) > 0

    def test_get_task_details_invalid_coordinates(self, task_service):
        """测试无效坐标值的处理。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {"id": 516208, "lng": "invalid", "lat": "invalid", "positionName": "Test Location"}
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "error") as mock_log:
                result = task_service.get_task_details(12345)

                assert result is None

                # Verify error was logged
                error_calls = [
                    call for call in mock_log.call_args_list if "无法解析坐标" in str(call)
                ]
                assert len(error_calls) > 0

    def test_get_task_details_url_construction(self, task_service):
        """测试URL构造正确。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {"id": 516208, "lng": "118.23672800", "lat": "25.07728900", "positionName": "Test"}
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response) as mock_get:
            task_service.get_task_details(12345)

            # Verify the URL was constructed correctly
            call_args = mock_get.call_args
            url = call_args[0][0]

            assert "/health-api/sign_in/12345" in url
            assert "fromPage=0" in url

    def test_get_task_details_logs_success(self, task_service):
        """测试成功消息被记录。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {
                    "id": 516208,
                    "lng": "118.23672800",
                    "lat": "25.07728900",
                    "positionName": "Test Location",
                }
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "info") as mock_log:
                task_service.get_task_details(12345)

                # Verify success message was logged
                success_calls = [
                    call for call in mock_log.call_args_list if "成功获取任务" in str(call)
                ]
                assert len(success_calls) > 0

    def test_get_task_details_logs_url(self, task_service):
        """测试URL被记录。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {"id": 516208, "lng": "118.23672800", "lat": "25.07728900", "positionName": "Test"}
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response):
            with patch.object(task_service.logger, "info") as mock_log:
                task_service.get_task_details(12345)

                # Verify URL was logged
                url_calls = [
                    call for call in mock_log.call_args_list if "请求任务详情 URL" in str(call)
                ]
                assert len(url_calls) > 0

    def test_get_task_details_float_conversion_with_strings(self, task_service):
        """测试字符串坐标被正确转换为浮点数。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signInPositions": [
                {"id": 516208, "lng": "118.23672800", "lat": "25.07728900", "positionName": "Test"}
            ]
        }

        with patch.object(task_service.client, "get", return_value=mock_response):
            result = task_service.get_task_details(12345)

            assert result is not None
            assert isinstance(result.base_lng, float)
            assert isinstance(result.base_lat, float)
            assert result.base_lng == 118.23672800
            assert result.base_lat == 25.07728900
