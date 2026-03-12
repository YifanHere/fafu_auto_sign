"""
Task identification characterization tests.

These tests capture the current behavior of the get_pending_task() function
and serve as regression tests after refactoring.
"""
import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os
from freezegun import freeze_time

# 如果已经加载了 fafu_auto_sign 模块，先移除它
if 'fafu_auto_sign' in sys.modules:
    del sys.modules['fafu_auto_sign']
# 将项目根目录添加到路径最前面
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fafu_auto_sign


class TestTaskIdentification:
    """测试任务识别逻辑"""
    
    @freeze_time("2009-02-13 23:31:30")  # Unix timestamp 1234567890
    def test_identify_active_task_with_keyword(self, sample_tasks, sample_token):
        """
        测试能正确识别包含"晚归"关键词且在时间窗口内的有效任务
        """
        # Mock 网络响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(sample_tasks)
        mock_response.json.return_value = sample_tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 应该返回第一个匹配的晚归任务
        assert task_id == 1001
    
    @freeze_time("2009-02-13 23:31:30")
    def test_skip_non_target_keyword_tasks(self, sample_token):
        """
        测试跳过非"晚归"关键词的任务
        """
        # 创建只包含非目标任务的列表
        non_target_tasks = {
            "records": [
                {
                    "id": 1003,
                    "name": "晨跑签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
                {
                    "id": 1006,
                    "name": "课堂签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(non_target_tasks)
        mock_response.json.return_value = non_target_tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 没有匹配的任务
        assert task_id is None
    
    @freeze_time("2009-02-13 23:31:30")
    def test_filter_expired_tasks(self, sample_token):
        """
        测试过滤已过期的任务
        """
        # 修改任务，使所有任务都过期
        expired_tasks = {
            "records": [
                {
                    "id": 1004,
                    "name": "晚归签到任务 - 已过期",
                    "beginTime": 1234567000000,
                    "endTime": 1234567500000,  # 过期
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(expired_tasks)
        mock_response.json.return_value = expired_tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 任务已过期，不应返回
        assert task_id is None
    
    @freeze_time("2009-02-13 23:31:30")
    def test_filter_not_started_tasks(self, sample_token):
        """
        测试过滤尚未开始的任务
        """
        # 修改任务，使所有任务都还未开始
        future_tasks = {
            "records": [
                {
                    "id": 1005,
                    "name": "晚归签到任务 - 未开始",
                    "beginTime": 1234568000000,  # 将来
                    "endTime": 1234568500000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(future_tasks)
        mock_response.json.return_value = future_tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 任务还未开始，不应返回
        assert task_id is None


class TestTaskTimeFiltering:
    """测试时间过滤逻辑"""
    
    @freeze_time("2009-02-13 23:30:00")  # Unix timestamp 1234567800
    def test_task_at_exact_begin_time_is_active(self, sample_token):
        """
        测试在 begin_time 精确时刻任务是活跃的
        """
        tasks = {
            "records": [
                {
                    "id": 2001,
                    "name": "晚归签到任务",
                    "beginTime": 1234567800000,  # 精确匹配
                    "endTime": 1234567900000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id == 2001
    
    @freeze_time("2009-02-13 23:31:40")  # Unix timestamp 1234567900
    def test_task_at_exact_end_time_is_active(self, sample_token):
        """
        测试在 end_time 精确时刻任务是活跃的（包含边界）
        """
        tasks = {
            "records": [
                {
                    "id": 2002,
                    "name": "晚归签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567900000,  # 精确匹配
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id == 2002
    
    @freeze_time("2009-02-13 23:31:41")  # Unix timestamp 1234567901
    def test_task_one_second_after_end_is_inactive(self, sample_token):
        """
        测试 end_time 后一秒任务不活跃
        """
        tasks = {
            "records": [
                {
                    "id": 2003,
                    "name": "晚归签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567900000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id is None
    
    @freeze_time("2009-02-13 23:29:59")  # Unix timestamp 1234567799
    def test_task_one_second_before_begin_is_inactive(self, sample_token):
        """
        测试 begin_time 前一秒任务不活跃
        """
        tasks = {
            "records": [
                {
                    "id": 2004,
                    "name": "晚归签到任务",
                    "beginTime": 1234567800000,
                    "endTime": 1234567900000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id is None


class TestTaskKeywordFiltering:
    """测试关键词过滤逻辑"""
    
    @freeze_time("2009-02-13 23:31:30")
    def test_keyword_matching_is_partial(self, sample_token):
        """
        测试"晚归"关键词是部分匹配（只要包含即可）
        """
        # 包含"晚归"的各种变体
        tasks = {
            "records": [
                {
                    "id": 3001,
                    "name": "今日晚归签到",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
                {
                    "id": 3002,
                    "name": "晚归任务 - 测试",
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 应该返回第一个匹配的任务
        assert task_id == 3001
    
    @freeze_time("2009-02-13 23:31:30")
    def test_keyword_matching_is_case_sensitive(self, sample_token):
        """
        测试关键词匹配是否区分大小写（当前实现是区分大小写的）
        """
        # 大小写变体
        tasks = {
            "records": [
                {
                    "id": 3003,
                    "name": "晚歸签到",  # 繁体字，不是"晚归"
                    "beginTime": 1234567800000,
                    "endTime": 1234567980000,
                },
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(tasks)
        mock_response.json.return_value = tasks
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        # 繁体字"晚歸"不匹配简体字"晚归"
        assert task_id is None


class TestTaskEdgeCases:
    """测试边界情况"""
    
    @freeze_time("2009-02-13 23:31:30")
    def test_empty_records_returns_none(self, sample_token):
        """
        测试空任务列表返回 None
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"records": []}'
        mock_response.json.return_value = {"records": []}
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id is None
    
    @freeze_time("2009-02-13 23:31:30")
    def test_missing_records_field(self, sample_token):
        """
        测试缺少 records 字段返回 None
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": []}'
        mock_response.json.return_value = {"data": []}
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id is None
    
    def test_network_error_returns_none(self, sample_token):
        """
        测试网络错误返回 None
        """
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', side_effect=Exception("Connection error")):
                task_id = fafu_auto_sign.get_pending_task()
        
        assert task_id is None


class TestTaskApiRequest:
    """测试 API 请求行为"""
    
    @freeze_time("2009-02-13 23:31:30")
    def test_request_url_is_correct(self, sample_token):
        """
        验证请求的 URL 是正确的
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"records": []}'
        mock_response.json.return_value = {"records": []}
        
        expected_url = "http://stuhtapi.fafu.edu.cn/health-api/sign_in/student/my/page?rows=10&pageNum=1&signState=0"
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response) as mock_post:
                fafu_auto_sign.get_pending_task()
                
                # 验证调用的 URL
                call_args = mock_post.call_args
                assert call_args[0][0] == expected_url
    
    @freeze_time("2009-02-13 23:31:30")
    def test_request_includes_content_type_header(self, sample_token):
        """
        验证请求包含 Content-Type header
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"records": []}'
        mock_response.json.return_value = {"records": []}
        
        with patch('fafu_auto_sign.USER_TOKEN', sample_token):
            with patch('requests.post', return_value=mock_response) as mock_post:
                fafu_auto_sign.get_pending_task()
                
                # 验证 headers 中包含 Content-Type
                call_kwargs = mock_post.call_args[1]
                headers = call_kwargs.get('headers', {})
                assert headers.get('Content-Type') == 'application/x-www-form-urlencoded'
