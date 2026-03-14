"""通知服务单元测试。

本模块测试 NotificationService 类，包括：
- 通知发送的基本功能
- 5分钟去重逻辑
- 无效配置的处理
- 通知失败的处理
"""

import sys
import time
import os
import types
import importlib.util
from unittest.mock import MagicMock, patch
import pytest

# 预处理：创建一个假的 fafu_auto_sign 包结构，避免循环导入
# 首先检查是否已存在，如果存在则移除
if 'fafu_auto_sign' in sys.modules:
    del sys.modules['fafu_auto_sign']
if 'fafu_auto_sign.services' in sys.modules:
    del sys.modules['fafu_auto_sign.services']
if 'fafu_auto_sign.services.notification_service' in sys.modules:
    del sys.modules['fafu_auto_sign.services.notification_service']

# 创建包结构
fafu_pkg = types.ModuleType('fafu_auto_sign')
fafu_pkg.__path__ = [os.path.join(os.path.dirname(__file__), '..', 'src', 'fafu_auto_sign')]
sys.modules['fafu_auto_sign'] = fafu_pkg

# 直接加载 notification_service 模块
spec = importlib.util.spec_from_file_location(
    'fafu_auto_sign.services.notification_service',
    os.path.join(os.path.dirname(__file__), '..', 'src', 'fafu_auto_sign', 'services', 'notification_service.py')
)
if spec is None or spec.loader is None:
    raise ImportError("无法加载 notification_service 模块")
notification_module = importlib.util.module_from_spec(spec)

# 创建 services 包
services_pkg = types.ModuleType('fafu_auto_sign.services')
services_pkg.__path__ = [os.path.join(os.path.dirname(__file__), '..', 'src', 'fafu_auto_sign', 'services')]
sys.modules['fafu_auto_sign.services'] = services_pkg
sys.modules['fafu_auto_sign.services.notification_service'] = notification_module

# 注入必要的依赖
# 1. config 模块
config_spec = importlib.util.spec_from_file_location(
    'fafu_auto_sign.config',
    os.path.join(os.path.dirname(__file__), '..', 'src', 'fafu_auto_sign', 'config.py')
)
if config_spec is None or config_spec.loader is None:
    raise ImportError("无法加载 config 模块")
config_module = importlib.util.module_from_spec(config_spec)
sys.modules['fafu_auto_sign.config'] = config_module
config_spec.loader.exec_module(config_module)

# 2. serverchan_sdk - 使用 mock
serverchan_sdk = types.ModuleType('serverchan_sdk')
setattr(serverchan_sdk, 'sc_send', MagicMock(return_value={'code': 0}))
sys.modules['serverchan_sdk'] = serverchan_sdk

# 加载 notification_service
spec.loader.exec_module(notification_module)
NotificationService = notification_module.NotificationService


@pytest.fixture
def mock_config_with_notification():
    """创建启用通知的 mock 配置。"""
    config = MagicMock()
    config.notification_enabled = True
    config.serverchan_key = "SCT12345"
    return config


@pytest.fixture
def mock_config_disabled():
    """创建禁用通知的 mock 配置。"""
    config = MagicMock()
    config.notification_enabled = False
    config.serverchan_key = "SCT12345"
    return config


@pytest.fixture
def mock_config_no_key():
    """创建未配置 SendKey 的 mock 配置。"""
    config = MagicMock()
    config.notification_enabled = True
    config.serverchan_key = None
    return config


@pytest.fixture
def notification_service(mock_config_with_notification):
    """使用启用通知的配置创建 NotificationService 实例。"""
    return NotificationService(mock_config_with_notification)


class TestNotificationInitialization:
    """通知服务初始化测试。"""

    def test_init_with_valid_config(self, mock_config_with_notification):
        """测试使用有效配置初始化。"""
        service = NotificationService(mock_config_with_notification)
        assert service.config == mock_config_with_notification
        assert service._notification_cache == {}
        assert service.DEDUPLICATION_WINDOW == 300

    def test_init_logs_warning_when_no_key(self, mock_config_no_key, caplog):
        """测试未配置 SendKey 时记录警告。"""
        import logging
        with caplog.at_level(logging.WARNING):
            NotificationService(mock_config_no_key)
        assert "通知已启用但未配置 SendKey" in caplog.text


class TestSendKeyFormatDetection:
    """SendKey 格式检测测试。"""

    def test_detect_sc3_format(self, notification_service):
        """测试检测 Server酱³(SC3) 格式。"""
        result = notification_service._detect_key_format("SC31234567890")
        assert result == "Server酱³(SC3)"

    def test_detect_sct_format(self, notification_service):
        """测试检测 Server酱(Turbo) 格式。"""
        result = notification_service._detect_key_format("SCT1234567890")
        assert result == "Server酱(Turbo)"

    def test_detect_unknown_format(self, notification_service):
        """测试检测未知格式。"""
        result = notification_service._detect_key_format("UNKNOWN")
        assert result == "未知格式"


class TestNotifyBasicFunctionality:
    """notify() 基本功能测试。"""

    @patch.object(serverchan_sdk, 'sc_send')
    def test_notify_success_returns_true(self, mock_sc_send, notification_service):
        """测试成功发送通知返回 True。"""
        mock_sc_send.return_value = {'code': 0}
        result = notification_service.notify("测试标题", "测试内容")
        assert result is True

    def test_notify_disabled_returns_false(self, mock_config_disabled):
        """测试通知禁用时返回 False。"""
        service = NotificationService(mock_config_disabled)
        result = service.notify("测试标题", "测试内容")
        assert result is False

    def test_notify_no_key_returns_false(self, mock_config_no_key):
        """测试未配置 SendKey 时返回 False。"""
        service = NotificationService(mock_config_no_key)
        result = service.notify("测试标题", "测试内容")
        assert result is False

    def test_notify_with_task_id_and_success(self, notification_service):
        """测试带 task_id 和 success 参数的 notify。"""
        result = notification_service.notify(
            "签到完成", "任务已执行", 
            task_id="task_123", 
            success=True
        )
        assert result is True


class TestDeduplicationLogic:
    """5分钟去重逻辑测试。"""

    @patch.object(serverchan_sdk, 'sc_send')
    def test_duplicate_within_5min_blocked(self, mock_sc_send, notification_service):
        """测试 5 分钟内重复通知被去重。"""
        # 第一次发送
        result1 = notification_service.notify(
            "第一次", "内容", task_id="task_1", success=True
        )
        assert result1 is True

        # 相同任务和状态的第二次发送应该被去重
        result2 = notification_service.notify(
            "第二次", "内容", task_id="task_1", success=True
        )
        assert result2 is False

    @patch.object(serverchan_sdk, 'sc_send')
    def test_same_task_different_success_not_blocked(self, mock_sc_send, notification_service):
        """测试相同任务不同 success 状态不被去重。"""
        # 第一次发送（成功）
        result1 = notification_service.notify(
            "成功通知", "内容", task_id="task_1", success=True
        )
        assert result1 is True

        # 相同任务但失败状态的第二次发送应该允许
        result2 = notification_service.notify(
            "失败通知", "内容", task_id="task_1", success=False
        )
        assert result2 is True

    @patch.object(serverchan_sdk, 'sc_send')
    def test_different_task_id_not_blocked(self, mock_sc_send, notification_service):
        """测试不同 task_id 的通知不被去重。"""
        # 第一个任务
        result1 = notification_service.notify(
            "任务1", "内容", task_id="task_1", success=True
        )
        assert result1 is True

        # 第二个任务的通知应该允许
        result2 = notification_service.notify(
            "任务2", "内容", task_id="task_2", success=True
        )
        assert result2 is True

    @patch.object(serverchan_sdk, 'sc_send')
    def test_after_5min_same_task_allowed(self, mock_sc_send, notification_service):
        """测试 5 分钟后相同任务可以再次通知。"""
        # 第一次发送
        result1 = notification_service.notify(
            "第一次", "内容", task_id="task_1", success=True
        )
        assert result1 is True

        # 修改缓存时间为 5 分钟前
        key = ("task_1", True)
        notification_service._notification_cache[key] = time.time() - 301

        # 5 分钟后应该允许再次发送
        result2 = notification_service.notify(
            "第二次", "内容", task_id="task_1", success=True
        )
        assert result2 is True


class TestShouldNotify:
    """_should_notify() 方法测试。"""

    def test_should_notify_returns_true_for_new_task(self, notification_service):
        """测试新任务返回 True。"""
        result = notification_service._should_notify("task_new", True)
        assert result is True

    def test_should_notify_returns_false_for_duplicate(self, notification_service):
        """测试重复任务返回 False。"""
        # 添加缓存记录
        key = ("task_dup", True)
        notification_service._notification_cache[key] = time.time()

        result = notification_service._should_notify("task_dup", True)
        assert result is False

    def test_should_notify_returns_true_after_window(self, notification_service):
        """测试窗口期后返回 True。"""
        # 添加过期的缓存记录
        key = ("task_old", True)
        notification_service._notification_cache[key] = time.time() - 301

        result = notification_service._should_notify("task_old", True)
        assert result is True


class TestCleanupExpired:
    """_cleanup_expired() 方法测试。"""

    def test_cleanup_removes_expired(self, notification_service):
        """测试清理过期记录。"""
        # 添加过期记录
        notification_service._notification_cache[("task_old", True)] = time.time() - 301
        # 添加有效记录
        notification_service._notification_cache[("task_new", True)] = time.time()

        notification_service._cleanup_expired()

        # 过期记录应该被删除
        assert ("task_old", True) not in notification_service._notification_cache
        # 有效记录应该保留
        assert ("task_new", True) in notification_service._notification_cache

    def test_cleanup_keeps_valid(self, notification_service):
        """测试保留有效记录。"""
        # 添加多个有效记录
        notification_service._notification_cache[("task1", True)] = time.time() - 100
        notification_service._notification_cache[("task2", False)] = time.time() - 200

        notification_service._cleanup_expired()

        # 都应该保留
        assert ("task1", True) in notification_service._notification_cache
        assert ("task2", False) in notification_service._notification_cache


class TestSendNotification:
    """_send_notification() 方法测试。"""

    @patch.object(serverchan_sdk, 'sc_send')
    def test_send_success_logs_info(self, mock_sc_send, notification_service, caplog):
        """测试成功发送记录日志。"""
        import logging
        mock_sc_send.return_value = {'code': 0}
        
        with caplog.at_level(logging.INFO):
            notification_service._send_notification(
                "SCT12345", "测试标题", "测试内容"
            )
        
        assert "✅ 通知发送成功" in caplog.text

    @patch.object(notification_module, 'sc_send')
    def test_send_failure_calls_sc_send(self, mock_sc_send, notification_service):
        """测试发送失败时调用了 sc_send。"""
        mock_sc_send.return_value = {'code': 1, 'message': '错误信息'}
        
        notification_service._send_notification(
            "SCT12345", "测试标题", "测试内容"
        )
        
        # 验证 sc_send 被调用
        mock_sc_send.assert_called_once_with("SCT12345", "测试标题", desp="测试内容")

    @patch.object(notification_module, 'sc_send')
    def test_send_exception_handled(self, mock_sc_send, notification_service):
        """测试异常被处理不抛出。"""
        mock_sc_send.side_effect = Exception("网络错误")
        
        # 不应该抛出异常
        notification_service._send_notification(
            "SCT12345", "测试标题", "测试内容"
        )
        
        # 验证 sc_send 被调用
        mock_sc_send.assert_called_once()

    @patch.object(notification_module, 'sc_send')
    def test_send_with_errno_zero(self, mock_sc_send, notification_service, caplog):
        """测试 errno=0 也视为成功。"""
        import logging
        mock_sc_send.return_value = {'errno': 0}
        
        with caplog.at_level(logging.INFO):
            notification_service._send_notification(
                "SCT12345", "测试标题", "测试内容"
            )
        
        assert "✅ 通知发送成功" in caplog.text

class TestNotifyWithoutDeduplicationParams:
    """不带去重参数的 notify 测试。"""

    @patch.object(serverchan_sdk, 'sc_send')
    def test_notify_without_task_id_allows_repeats(self, mock_sc_send, notification_service):
        """测试不带 task_id 时不进行去重。"""
        # 第一次发送
        result1 = notification_service.notify("标题1", "内容")
        assert result1 is True

        # 没有 task_id，应该允许重复
        result2 = notification_service.notify("标题2", "内容")
        assert result2 is True

        # 再次发送
        result3 = notification_service.notify("标题3", "内容")
        assert result3 is True


class TestThreading:
    """多线程相关测试。"""

    @patch.object(serverchan_sdk, 'sc_send')
    def test_notify_starts_thread(self, mock_sc_send, notification_service):
        """测试 notify 启动后台线程。"""
        result = notification_service.notify("标题", "内容")
        assert result is True
        # 给线程一点时间启动
        time.sleep(0.1)

    def test_cache_thread_safety(self, notification_service):
        """测试缓存线程安全。"""
        import threading
        
        def add_to_cache(i):
            with notification_service._cache_lock:
                notification_service._notification_cache[(f"task_{i}", True)] = time.time()
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_to_cache, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 所有记录都应该存在
        assert len(notification_service._notification_cache) == 10
