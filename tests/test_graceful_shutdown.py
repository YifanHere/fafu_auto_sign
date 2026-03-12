"""Tests for graceful shutdown handler."""

import signal
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from fafu_auto_sign.graceful_shutdown import GracefulShutdown


class TestGracefulShutdown:
    """Test cases for GracefulShutdown class."""
    
    def test_init_creates_event_and_task_list(self):
        """Test that __init__ creates necessary structures."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers') as mock_setup:
            gs = GracefulShutdown()
            assert gs._stop_event is not None
            assert gs._cleanup_tasks == []
            mock_setup.assert_called_once()
    
    def test_is_stopped_returns_false_initially(self):
        """Test that is_stopped returns False before signal."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            assert gs.is_stopped() is False
    
    def test_is_stopped_returns_true_after_stop(self):
        """Test that is_stopped returns True after stop() is called."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            gs.stop()
            assert gs.is_stopped() is True
    
    def test_wait_returns_false_on_timeout(self):
        """Test that wait returns False on timeout."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            # Wait with short timeout should return False (not stopped)
            result = gs.wait(timeout=0.01)
            assert result is False
    
    def test_wait_returns_true_after_stop(self):
        """Test that wait returns True after stop is set."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            # Set stop in another thread after a short delay
            def delayed_stop():
                time.sleep(0.05)
                gs._stop_event.set()
            
            thread = threading.Thread(target=delayed_stop)
            thread.start()
            
            # Wait should return True when stop is set
            result = gs.wait(timeout=1.0)
            
            thread.join()
            assert result is True
    
    def test_register_cleanup_adds_task(self):
        """Test that register_cleanup adds tasks to the list."""
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
        """Test that cleanup tasks run in LIFO order."""
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
            
            # Should execute in reverse order: 3, 2, 1
            assert execution_order == [3, 2, 1]
    
    def test_cleanup_task_failure_does_not_stop_others(self):
        """Test that one failing cleanup task doesn't stop others."""
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
            
            # Both tasks should have been attempted
            assert 'fail' in execution_order
            assert 'success' in execution_order
    
    def test_signal_handler_sets_stop_event(self):
        """Test that signal handler sets stop event."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            # Manually call signal handler (simulating signal)
            gs._signal_handler(signal.SIGINT, None)
            
            assert gs.is_stopped() is True
    
    def test_signal_handler_runs_cleanup_tasks(self):
        """Test that signal handler runs cleanup tasks."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            cleanup_called = []
            
            def cleanup():
                cleanup_called.append(True)
            
            gs.register_cleanup(cleanup)
            gs._signal_handler(signal.SIGINT, None)
            
            assert len(cleanup_called) == 1
    
    def test_setup_signal_handlers_registers_sigint(self):
        """Test that SIGINT handler is registered."""
        gs = GracefulShutdown()
        
        # Get the current handler for SIGINT
        current_handler = signal.getsignal(signal.SIGINT)
        
        # Should be our signal handler
        assert current_handler == gs._signal_handler
    
    def test_get_signal_name_valid_signal(self):
        """Test getting signal name for valid signal."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            name = gs._get_signal_name(signal.SIGINT)
            assert name == 'SIGINT'
    
    def test_get_signal_name_invalid_signal(self):
        """Test getting signal name for invalid signal."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            name = gs._get_signal_name(999)
            assert 'Signal(999)' in name
    
    def test_context_manager_enters_and_exits(self):
        """Test context manager properly enters and exits."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            with GracefulShutdown() as gs:
                assert isinstance(gs, GracefulShutdown)
                assert not gs.is_stopped()
            
            # After exit, should be stopped
            assert gs.is_stopped()
    
    def test_manual_stop_sets_event_and_runs_cleanup(self):
        """Test manual stop method works correctly."""
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
        """Test that cleanup registration is thread-safe."""
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
        """Test that wait can be interrupted by stop."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            wait_result = [None]
            
            def wait_thread():
                wait_result[0] = gs.wait(timeout=10.0)
            
            thread = threading.Thread(target=wait_thread)
            thread.start()
            
            # Give thread time to start waiting
            time.sleep(0.05)
            
            # Stop should interrupt the wait
            start_time = time.time()
            gs.stop()
            thread.join(timeout=1.0)
            elapsed = time.time() - start_time
            
            # Should have completed quickly, not waited 10 seconds
            assert elapsed < 1.0
            assert wait_result[0] is True


class TestGracefulShutdownIntegration:
    """Integration tests for GracefulShutdown."""
    
    def test_full_lifecycle(self):
        """Test complete lifecycle of graceful shutdown."""
        with patch.object(GracefulShutdown, '_setup_signal_handlers'):
            gs = GracefulShutdown()
            
            resource1_closed = []
            resource2_closed = []
            
            def close_resource1():
                resource1_closed.append(True)
            
            def close_resource2():
                resource2_closed.append(True)
            
            # Register cleanup tasks
            gs.register_cleanup(close_resource1)
            gs.register_cleanup(close_resource2)
            
            # Simulate main loop
            iterations = 0
            while not gs.is_stopped() and iterations < 3:
                iterations += 1
                time.sleep(0.01)
            
            # Trigger shutdown
            gs.stop()
            
            # Verify state
            assert gs.is_stopped()
            assert len(resource1_closed) == 1
            assert len(resource2_closed) == 1
    
    def test_simulated_signal_flow(self):
        """Test simulating the full signal handling flow."""
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
            
            # Simulate receiving SIGINT
            gs._signal_handler(signal.SIGINT, None)
            
            # Verify shutdown occurred
            assert gs.is_stopped()
            # Cleanup should run in reverse order: C, B, A
            assert cleanup_order == ['C', 'B', 'A']
