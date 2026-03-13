"""优雅关闭处理器测试。"""

import signal
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from fafu_auto_sign.graceful_shutdown import GracefulShutdown


class TestGracefulShutdown:
    """GracefulShutdown类测试用例。"""
    
    def test_init_creates_event_and_task_list(self):
        """测试__init__创建必要的结构。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers') as mock_setup:
            gs = GracefulShutdown()
            assert gs._stop_event is not None
            assert gs._cleanup_tasks == []
            mock_setup.assert_called_once()
    
    def test_is_stopped_returns_false_initially(self):
        """测试is_stopped在信号前返回False。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            assert gs.is_stopped() is False
    
    def test_is_stopped_returns_true_after_stop(self):
        """测试is_stopped在stop()调用后返回True。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            gs.stop()
            assert gs.is_stopped() is True
    
    def test_wait_returns_false_on_timeout(self):
        """测试wait在超时时返回False。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            # 短时间等待应该返回False（未停止）
            result = gs.wait(timeout=0.01)
            assert result is False
    
    def test_wait_returns_true_after_stop(self):
        """测试stop设置后wait返回True。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            # 在另一个线程中短暂延迟后设置stop
            def delayed_stop():
                time.sleep(0.05)
                gs._stop_event.set()
            
            thread = threading.Thread(target=delayed_stop)
            thread.start()
            
            # wait应该在stop设置时返回True
            result = gs.wait(timeout=1.0)
            
            thread.join()
            assert result is True
    
    def test_register_cleanup_adds_task(self):
        """测试register_cleanup将任务添加到列表。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            mock_func = MagicMock()
            gs.register_cleanup(mock_func, 'arg1', 'arg2', key='value')
            
            assert len(gs._cleanup_tasks) == 1
            func, args, kwargs = gs._cleanup_tasks[0]
            assert func == mock_func
            assert args == ('arg1', 'arg2')
            assert kwargs == {'key': 'value'}
    
    def test_cleanup_tasks_executed_in_reverse_order(self):
        """测试清理任务按后进先出顺序运行。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            execution_order = []
            
            def task1():
                execution_order.append(1)
            
            def task2():
                execution_order.append(2)
            
            def task3():
                execution_order.append(3)
            
            gs.register_cleanup(task1)
            gs.register_cleanup(task2)
            gs.register_cleanup(task3)
            
            gs.stop()
            
            # 应该按相反顺序执行：3, 2, 1
            assert execution_order == [3, 2, 1]
    
    def test_cleanup_task_failure_does_not_stop_others(self):
        """测试一个失败的清理任务不会停止其他任务。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            execution_order = []
            
            def failing_task():
                execution_order.append('fail')
                raise ValueError("Cleanup failed")
            
            def success_task():
                execution_order.append('success')
            
            gs.register_cleanup(success_task)
            gs.register_cleanup(failing_task)
            
            gs.stop()
            
            # 两个任务都应该已被尝试
            assert 'fail' in execution_order
            assert 'success' in execution_order
    
    def test_signal_handler_sets_stop_event(self):
        """测试信号处理器设置stop事件。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            # 手动调用信号处理器（模拟信号）
            gs._signal_handler(signal.SIGINT, None)
            
            assert gs.is_stopped() is True
    
    def test_signal_handler_runs_cleanup_tasks(self):
        """测试信号处理器运行清理任务。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            cleanup_called = []
            
            def cleanup():
                cleanup_called.append(True)
            
            gs.register_cleanup(cleanup)
            gs._signal_handler(signal.SIGINT, None)
            
            assert len(cleanup_called) == 1
    
    def test_setup_signal_handlers_registers_sigint(self):
        """测试SIGINT处理器已注册。"""
        gs = GracefulShutdown()
        
        # 获取SIGINT的当前处理器
        current_handler = signal.getsignal(signal.SIGINT)
        
        # 应该是我们的信号处理器
        assert current_handler == gs._signal_handler
    
    def test_get_signal_name_valid_signal(self):
        """测试获取有效信号的信号名称。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            name = gs._get_signal_name(signal.SIGINT)
            assert name == 'SIGINT'
    
    def test_get_signal_name_invalid_signal(self):
        """测试获取无效信号的信号名称。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            name = gs._get_signal_name(999)
            assert 'Signal(999)' in name
    
    def test_context_manager_enters_and_exits(self):
        """测试上下文管理器正确进入和退出。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            with GracefulShutdown() as gs:
                assert isinstance(gs, GracefulShutdown)
                assert not gs.is_stopped()
            
            # 退出后，应该已停止
            assert gs.is_stopped()
    
    def test_manual_stop_sets_event_and_runs_cleanup(self):
        """测试手动stop方法工作正常。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            cleanup_called = []
            
            def cleanup():
                cleanup_called.append(True)
            
            gs.register_cleanup(cleanup)
            gs.stop()
            
            assert gs.is_stopped()
            assert len(cleanup_called) == 1
    
    def test_thread_safety_cleanup_registration(self):
        """测试清理注册是线程安全的。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            errors = []
            
            def register_tasks():
                try:
                    for i in range(100):
                        gs.register_cleanup(lambda: None)
                except Exception as e:
                    errors.append(e)
            
            threads = [threading.Thread(target=register_tasks) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            assert len(errors) == 0
            assert len(gs._cleanup_tasks) == 500
    
    def test_wait_is_interruptible(self):
        """测试wait可以被stop中断。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            wait_result = [None]
            
            def wait_thread():
                wait_result[0] = gs.wait(timeout=10.0)
            
            thread = threading.Thread(target=wait_thread)
            thread.start()
            
            # 让线程有时间开始等待
            time.sleep(0.05)
            
            # stop应该中断wait
            start_time = time.time()
            gs.stop()
            thread.join(timeout=1.0)
            elapsed = time.time() - start_time
            
            # 应该很快完成，而不是等待10秒
            assert elapsed < 1.0
            assert wait_result[0] is True


class TestGracefulShutdownIntegration:
    """GracefulShutdown集成测试。"""
    
    def test_full_lifecycle(self):
        """测试优雅关闭的完整生命周期。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            resource1_closed = []
            resource2_closed = []
            
            def close_resource1():
                resource1_closed.append(True)
            
            def close_resource2():
                resource2_closed.append(True)
            
            # 注册清理任务
            gs.register_cleanup(close_resource1)
            gs.register_cleanup(close_resource2)
            
            # 模拟主循环
            iterations = 0
            while not gs.is_stopped() and iterations < 3:
                iterations += 1
                time.sleep(0.01)
            
            # 触发关闭
            gs.stop()
            
            # 验证状态
            assert gs.is_stopped()
            assert len(resource1_closed) == 1
            assert len(resource2_closed) == 1
    
    def test_simulated_signal_flow(self):
        """测试模拟完整的信号处理流程。"""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            cleanup_order = []
            
            def cleanup_a():
                cleanup_order.append('A')
            
            def cleanup_b():
                cleanup_order.append('B')
            
            def cleanup_c():
                cleanup_order.append('C')
            
            gs.register_cleanup(cleanup_a)
            gs.register_cleanup(cleanup_b)
            gs.register_cleanup(cleanup_c)
            
            # 模拟接收SIGINT
            gs._signal_handler(signal.SIGINT, None)
            
            # 验证关闭已发生
            assert gs.is_stopped()
            # 清理应该按相反顺序运行：C, B, A
            assert cleanup_order == ['C', 'B', 'A']
