"""优雅关闭处理器，支持信号处理和清理任务。"""

import logging
import platform
import signal
import threading
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """优雅关闭处理器，支持信号处理和清理任务。

    使用方式:
        shutdown = GracefulShutdown()

        # 注册清理任务
        shutdown.register_cleanup(client.close)
        shutdown.register_cleanup(logger.info, "正在关闭...")

        # 主循环
        while not shutdown.is_stopped():
            do_work()
            shutdown.wait(900)  # 等待 15 分钟或直到收到信号

        print("优雅关闭完成")
    """

    def __init__(self):
        """初始化优雅关闭处理器。"""
        self._stop_event = threading.Event()
        self._cleanup_tasks: List[Tuple[Callable, Tuple[Any, ...], dict]] = []
        self._lock = threading.Lock()
        self._setup_signal_handlers()

    def is_stopped(self) -> bool:
        """检查是否已请求关闭。

        返回:
            如果收到关闭信号返回 True，否则返回 False。
        """
        return self._stop_event.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """等待停止事件被设置或超时。

        参数:
            timeout: 最大等待时间（秒）。None 表示永久等待。

        返回:
            如果事件被设置返回 True，如果超时返回 False。
        """
        return self._stop_event.wait(timeout)

    def register_cleanup(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """注册一个在关闭时执行的清理任务。

        清理任务按注册顺序的逆序执行（后进先出）。

        参数:
            func: 清理期间要执行的可调用对象。
            *args: 传递给 func 的位置参数。
            **kwargs: 传递给 func 的关键字参数。
        """
        with self._lock:
            self._cleanup_tasks.append((func, args, kwargs))
        logger.debug(f"已注册清理任务: {func.__name__ if hasattr(func, '__name__') else func}")

    def _setup_signal_handlers(self) -> None:
        """为优雅关闭设置信号处理器。"""
        # SIGINT - Ctrl+C（Unix 和 Windows）
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            logger.debug("已注册 SIGINT 处理器")
        except (ValueError, OSError) as e:
            logger.warning(f"注册 SIGINT 处理器失败: {e}")

        # SIGTERM - kill 命令（Unix）
        if platform.system() != "Windows":
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                logger.debug("已注册 SIGTERM 处理器")
            except (ValueError, OSError) as e:
                logger.warning(f"注册 SIGTERM 处理器失败: {e}")

        # SIGBREAK - Ctrl+Break（Windows）
        if platform.system() == "Windows":
            try:
                signal.signal(signal.SIGBREAK, self._signal_handler)
                logger.debug("已注册 SIGBREAK 处理器")
            except (ValueError, OSError, AttributeError) as e:
                logger.warning(f"注册 SIGBREAK 处理器失败: {e}")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """处理关闭信号。

        参数:
            signum: 接收到的信号编号。
            frame: 当前堆栈帧。
        """
        signal_name = self._get_signal_name(signum)
        logger.info(f"收到信号 {signal_name} ({signum})，正在启动优雅关闭...")

        # 设置停止事件以通知所有等待的线程
        self._stop_event.set()

        # 执行清理任务
        self._run_cleanup_tasks()

        logger.info("优雅关闭完成")

    def _get_signal_name(self, signum: int) -> str:
        """获取人类可读的信号名称。

        参数:
            signum: 信号编号。

        返回:
            信号的字符串表示。
        """
        try:
            return signal.Signals(signum).name
        except (ValueError, AttributeError):
            return f"Signal({signum})"

    def _run_cleanup_tasks(self) -> None:
        """按逆序执行所有已注册的清理任务。"""
        with self._lock:
            tasks = list(reversed(self._cleanup_tasks))

        logger.info(f"正在执行 {len(tasks)} 个清理任务...")

        for func, args, kwargs in tasks:
            try:
                func_name = func.__name__ if hasattr(func, "__name__") else str(func)
                logger.debug(f"正在运行清理任务: {func_name}")
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"清理任务失败: {e}", exc_info=True)

        logger.info("所有清理任务已完成")

    def stop(self) -> None:
        """手动触发关闭（用于测试或编程使用）。

        这会设置停止事件并运行清理任务，无需信号。
        """
        logger.info("手动关闭已触发")
        self._stop_event.set()
        self._run_cleanup_tasks()

    def __enter__(self) -> "GracefulShutdown":
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口 - 退出时触发清理。"""
        if not self.is_stopped():
            self.stop()
