"""Graceful shutdown handler with signal processing and cleanup tasks."""

import logging
import platform
import signal
import threading
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handles graceful shutdown with signal processing and cleanup tasks.
    
    Usage:
        shutdown = GracefulShutdown()
        
        # Register cleanup tasks
        shutdown.register_cleanup(client.close)
        shutdown.register_cleanup(logger.info, "Shutting down...")
        
        # Main loop
        while not shutdown.is_stopped():
            do_work()
            shutdown.wait(900)  # Wait 15 minutes or until signal
        
        print("Graceful shutdown completed")
    """
    
    def __init__(self):
        """Initialize the graceful shutdown handler."""
        self._stop_event = threading.Event()
        self._cleanup_tasks: List[Tuple[Callable, Tuple[Any, ...], dict]] = []
        self._lock = threading.Lock()
        self._setup_signal_handlers()
    
    def is_stopped(self) -> bool:
        """Check if shutdown has been requested.
        
        Returns:
            True if shutdown signal received, False otherwise.
        """
        return self._stop_event.is_set()
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for the stop event to be set or timeout.
        
        Args:
            timeout: Maximum time to wait in seconds. None means wait forever.
            
        Returns:
            True if the event was set, False if timeout occurred.
        """
        return self._stop_event.wait(timeout)
    
    def register_cleanup(
        self, 
        func: Callable, 
        *args: Any, 
        **kwargs: Any
    ) -> None:
        """Register a cleanup task to be executed on shutdown.
        
        Cleanup tasks are executed in reverse order of registration (LIFO).
        
        Args:
            func: The callable to execute during cleanup.
            *args: Positional arguments to pass to func.
            **kwargs: Keyword arguments to pass to func.
        """
        with self._lock:
            self._cleanup_tasks.append((func, args, kwargs))
        logger.debug(f"Registered cleanup task: {func.__name__ if hasattr(func, '__name__') else func}")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        # SIGINT - Ctrl+C (Unix and Windows)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            logger.debug("Registered SIGINT handler")
        except (ValueError, OSError) as e:
            logger.warning(f"Failed to register SIGINT handler: {e}")
        
        # SIGTERM - kill command (Unix)
        if platform.system() != 'Windows':
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                logger.debug("Registered SIGTERM handler")
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to register SIGTERM handler: {e}")
        
        # SIGBREAK - Ctrl+Break (Windows)
        if platform.system() == 'Windows':
            try:
                signal.signal(signal.SIGBREAK, self._signal_handler)
                logger.debug("Registered SIGBREAK handler")
            except (ValueError, OSError, AttributeError) as e:
                logger.warning(f"Failed to register SIGBREAK handler: {e}")
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals.
        
        Args:
            signum: The signal number received.
            frame: The current stack frame.
        """
        signal_name = self._get_signal_name(signum)
        logger.info(f"Received signal {signal_name} ({signum}), initiating graceful shutdown...")
        
        # Set stop event to signal all waiting threads
        self._stop_event.set()
        
        # Execute cleanup tasks
        self._run_cleanup_tasks()
        
        logger.info("Graceful shutdown completed")
    
    def _get_signal_name(self, signum: int) -> str:
        """Get human-readable signal name.
        
        Args:
            signum: The signal number.
            
        Returns:
            String representation of the signal.
        """
        try:
            return signal.Signals(signum).name
        except (ValueError, AttributeError):
            return f"Signal({signum})"
    
    def _run_cleanup_tasks(self) -> None:
        """Execute all registered cleanup tasks in reverse order."""
        with self._lock:
            tasks = list(reversed(self._cleanup_tasks))
        
        logger.info(f"Executing {len(tasks)} cleanup task(s)...")
        
        for func, args, kwargs in tasks:
            try:
                func_name = func.__name__ if hasattr(func, '__name__') else str(func)
                logger.debug(f"Running cleanup task: {func_name}")
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}", exc_info=True)
        
        logger.info("All cleanup tasks completed")
    
    def stop(self) -> None:
        """Manually trigger shutdown (for testing or programmatic use).
        
        This sets the stop event and runs cleanup tasks without requiring a signal.
        """
        logger.info("Manual shutdown triggered")
        self._stop_event.set()
        self._run_cleanup_tasks()
    
    def __enter__(self) -> 'GracefulShutdown':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - trigger cleanup on exit."""
        if not self.is_stopped():
            self.stop()
