"""Task service module for FAFU Auto Sign.

This module provides task identification and management functionality,
including fetching pending tasks and filtering based on time windows
and keywords.
"""

import logging
import time
from typing import Optional

from fafu_auto_sign.client import FAFUClient


class TaskService:
    """Service for task identification and management.
    
    This service handles:
    - Fetching task lists from the API
    - Filtering tasks based on time windows
    - Matching tasks by keywords (e.g., "晚归")
    - Detailed logging of task processing
    
    Attributes:
        client: FAFUClient instance for making HTTP requests
        logger: Logger instance for this service
    """
    
    # API endpoint for fetching task list
    TASK_LIST_ENDPOINT = "/health-api/sign_in/student/my/page"
    
    # Default pagination parameters
    DEFAULT_ROWS = 50
    DEFAULT_PAGE = 1
    DEFAULT_SIGN_STATE = 0  # Unsigned tasks
    
    def __init__(self, client: FAFUClient):
        """Initialize the task service.
        
        Args:
            client: FAFUClient instance for making HTTP requests.
        """
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_pending_task(self) -> Optional[str]:
        """Get the pending task ID for "晚归" sign-in.
        
        This method fetches the task list from the API, then filters
        tasks based on:
        1. Time window: begin_time <= current_time <= end_time
        2. Keyword matching: "晚归" in task_name
        
        Returns:
            The task ID (str) if a matching task is found, None otherwise.
            
        Raises:
            RequestException: If the HTTP request fails (handled by client)
        """
        # Build the URL with query parameters
        url = (
            f"{self.TASK_LIST_ENDPOINT}"
            f"?rows={self.DEFAULT_ROWS}"
            f"&pageNum={self.DEFAULT_PAGE}"
            f"&signState={self.DEFAULT_SIGN_STATE}"
        )
        
        self.logger.info(f"[*] 请求 URL: {url}")
        
        try:
            # Make the POST request to fetch task list
            # Note: The API requires POST method with form-encoded body,
            # but no body parameters are needed for this endpoint
            response = self.client.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Parse the JSON response
            data = response.json()
            records = data.get('records', [])
            
            self.logger.debug(f"Retrieved {len(records)} tasks from API")
            
            # Get current time in milliseconds (Unix timestamp)
            current_time_ms = int(time.time() * 1000)
            
            # Iterate through tasks and find matching one
            for task in records:
                task_id = task.get('id')
                task_name = task.get('name', '')
                begin_time = task.get('beginTime', 0)
                end_time = task.get('endTime', 0)
                
                # Check if task is currently active (within time window)
                is_active = begin_time <= current_time_ms <= end_time
                
                # Check if task name contains the target keyword
                is_target_type = "晚归" in task_name
                
                self.logger.debug(
                    f"Task: {task_name} (ID: {task_id}), "
                    f"active: {is_active}, target: {is_target_type}"
                )
                
                if is_active and is_target_type:
                    # Found a matching task
                    self.logger.info(
                        f"[*] 精准匹配到进行中的晚归签到任务: 【{task_name}】 (ID: {task_id})"
                    )
                    return str(task_id)
                elif is_active and not is_target_type:
                    # Task is active but not the target type
                    self.logger.info(
                        f"[!] 发现进行中的其他签到，跳过: 【{task_name}】"
                    )
            
            # No matching task found
            self.logger.info("[-] 列表中没有正在有效时间内的晚归签到任务。")
            return None
            
        except Exception as e:
            # Log the error and re-raise for caller to handle
            self.logger.error(f"[!] 获取任务列表时发生异常: {e}")
            raise
