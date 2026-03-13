"""FAFU 自动签到的通知服务模块。

本模块提供 Server酱推送通知功能，支持消息去重和
SendKey 格式自动检测。
"""
import logging
import threading
import time
from typing import Any, Optional

from serverchan_sdk import sc_send

from fafu_auto_sign.config import AppConfig


class NotificationService:
    """Server酱推送通知服务。
    
    本服务处理以下功能：
    - 发送推送通知到微信（通过 Server酱）
    - 自动检测 SendKey 格式（SC3 vs SCT）
    - 消息去重（5分钟窗口）
    - 非阻塞发送（fire-and-forget）
    
    属性:
        config: 包含通知配置的 AppConfig 实例
        logger: 本服务的日志记录器实例
        _notification_cache: 去重缓存，键为 (task_id, success)，值为时间戳
        _cache_lock: 缓存操作锁
    """
    
    # 去重窗口时间（秒）
    DEDUPLICATION_WINDOW = 300  # 5分钟
    
    def __init__(self, config: AppConfig):
        """初始化通知服务。
        
        参数:
            config: 包含通知配置的 AppConfig 实例。
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 初始化去重缓存和锁
        self._notification_cache: dict[tuple[str, bool], float] = {}
        self._cache_lock = threading.Lock()
        
        # 验证 SendKey 配置
        self._validate_sendkey()
    
    def _validate_sendkey(self) -> None:
        """验证 SendKey 配置是否有效。"""
        sendkey = getattr(self.config, 'serverchan_key', None)
        notification_enabled = getattr(self.config, 'notification_enabled', False)
        
        if notification_enabled and not sendkey:
            self.logger.warning("[!] 通知已启用但未配置 SendKey")
        elif sendkey:
            # 检测 SendKey 格式
            key_format = self._detect_key_format(sendkey)
            self.logger.info(f"[*] 检测到 {key_format} 格式的 SendKey")
    
    def _detect_key_format(self, sendkey: str) -> str:
        """检测 SendKey 格式。
        
        参数:
            sendkey: Server酱 SendKey。
            
        返回:
            SendKey 格式描述（"Server酱³(SC3)" 或 "Server酱(Turbo)"）。
        """
        if sendkey.startswith('SC3'):
            return "Server酱³(SC3)"
        elif sendkey.startswith('SCT'):
            return "Server酱(Turbo)"
        else:
            return "未知格式"
    
    def notify(self, title: str, content: str, task_id: str = None, 
               success: bool = None) -> bool:
        """发送推送通知（非阻塞）。
        
        本方法会检查去重逻辑，如果该任务在5分钟内已发送过
        相同状态的通知，则跳过发送。
        
        发送操作在后台线程中执行，不会阻塞主流程。
        
        参数:
            title: 通知标题。
            content: 通知内容。
            task_id: 任务ID（用于去重），可选。
            success: 任务状态（用于去重），可选。
            
        返回:
            如果启动发送线程成功返回 True，如果跳过或配置无效返回 False。
            
        注意:
            返回 True 仅表示成功启动发送线程，不保证通知实际送达。
        """
        # 检查通知是否启用
        notification_enabled = getattr(self.config, 'notification_enabled', False)
        if not notification_enabled:
            self.logger.debug("通知未启用，跳过发送")
            return False
        
        # 检查 SendKey 是否配置
        sendkey = getattr(self.config, 'serverchan_key', None)
        if not sendkey:
            self.logger.debug("未配置 SendKey，跳过发送")
            return False
        
        # 检查是否需要去重
        if task_id is not None and success is not None:
            if not self._should_notify(task_id, success):
                self.logger.debug(f"任务 {task_id} 在5分钟内已发送过 {success} 状态通知，跳过")
                return False
        
        # 记录发送时间（立即记录，防止并发重复发送）
        if task_id is not None and success is not None:
            with self._cache_lock:
                self._notification_cache[(task_id, success)] = time.time()
        
        # 在后台线程中发送通知（非阻塞）
        try:
            thread = threading.Thread(
                target=self._send_notification,
                args=(sendkey, title, content, task_id, success),
                daemon=True
            )
            thread.start()
            self.logger.debug(f"[*] 已启动通知发送线程: {title}")
            return True
        except Exception as e:
            self.logger.error(f"[x] 启动通知线程失败: {e}")
            return False
    
    def _send_notification(self, sendkey: str, title: str, content: str,
                           task_id: str = None, success: bool = None) -> None:
        """实际发送通知（在后台线程中执行）。
        
        参数:
            sendkey: Server酱 SendKey。
            title: 通知标题。
            content: 通知内容。
            task_id: 任务ID（仅用于日志）。
            success: 任务状态（仅用于日志）。
        """
        try:
            # 设置超时，避免长时间阻塞
            # 使用 threading.Timer 实现超时控制
            result_container: list[Any] = []
            exception_container: list[Exception] = []
            
            def do_send():
                try:
                    response = sc_send(sendkey, title, desp=content)
                    result_container.append(response)
                except Exception as e:
                    exception_container.append(e)
            
            send_thread = threading.Thread(target=do_send)
            send_thread.start()
            send_thread.join(timeout=10)  # 10秒超时
            
            if send_thread.is_alive():
                self.logger.warning(f"[!] 通知发送超时（任务 {task_id}）")
                return
            
            if exception_container:
                raise exception_container[0]
            
            response = result_container[0] if result_container else None
            
            # 检查响应
            if response and isinstance(response, dict):
                if response.get('code') == 0 or response.get('errno') == 0:
                    self.logger.info(f"✅ 通知发送成功: {title}")
                else:
                    error_msg = response.get('message', response.get('errmsg', '未知错误'))
                    self.logger.error(f"❌ 通知发送失败: {error_msg}")
            else:
                self.logger.info(f"✅ 通知发送完成: {title}")
                
        except Exception as e:
            # 只记录日志，不抛出异常，不阻塞主流程
            self.logger.error(f"[x] 发送通知时发生错误: {e}")
    
    def _should_notify(self, task_id: str, success: bool) -> bool:
        """检查是否应该发送通知（去重检查）。
        
        使用 (task_id, success) 作为键，5分钟窗口期内
        相同键的通知会被去重。
        
        参数:
            task_id: 任务ID。
            success: 任务状态（True/False）。
            
        返回:
            如果应该发送通知返回 True，如果被去重返回 False。
        """
        with self._cache_lock:
            # 先清理过期记录
            self._cleanup_expired()
            
            # 检查是否有未过期的记录
            key = (task_id, success)
            last_time = self._notification_cache.get(key)
            
            if last_time is None:
                return True
            
            # 检查是否在窗口期内
            elapsed = time.time() - last_time
            if elapsed >= self.DEDUPLICATION_WINDOW:
                return True
            
            return False
    
    def _cleanup_expired(self) -> None:
        """清理过期的去重记录。
        
        应在持有 _cache_lock 时调用。
        """
        now = time.time()
        expired_keys = [
            key for key, timestamp in self._notification_cache.items()
            if now - timestamp >= self.DEDUPLICATION_WINDOW
        ]
        for key in expired_keys:
            del self._notification_cache[key]
        
        if expired_keys:
            self.logger.debug(f"清理了 {len(expired_keys)} 条过期去重记录")
