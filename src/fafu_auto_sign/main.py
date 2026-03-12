"""Main entry point for FAFU Auto Sign application.

This module provides the main entry point for the automatic sign-in daemon,
integrating all modules: config, logging, client, services, and graceful shutdown.
"""

import logging

from requests.exceptions import ConnectionError, RequestException

from fafu_auto_sign.config import load_config
from fafu_auto_sign.logging_config import setup_logging
from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.services import TaskService, SignService
from fafu_auto_sign.services.upload_service import UploadService
from fafu_auto_sign.graceful_shutdown import GracefulShutdown


def run(config_path: str = "config.json") -> None:
    """Run the automatic sign-in daemon.
    
    This function initializes all components and runs the main loop that:
    1. Fetches pending tasks
    2. Uploads sign-in images
    3. Submits sign-in requests
    4. Waits for the next heartbeat interval
    
    The daemon can be gracefully stopped via SIGINT (Ctrl+C) or SIGTERM.
    Network errors are handled gracefully without crashing the daemon.
    
    Args:
        config_path: Path to the JSON configuration file.
    """
    # 1. 加载配置
    config = load_config(config_path)
    
    # 2. 设置日志
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    
    # 3. 创建客户端和服务
    with FAFUClient(config) as client:
        task_service = TaskService(client)
        upload_service = UploadService(client)
        sign_service = SignService(client, config)
        
        # 4. 创建优雅退出处理器
        shutdown = GracefulShutdown()
        shutdown.register_cleanup(client.close)
        
        logger.info("启动自动保活与签到守护进程...")
        
        # 5. 主循环
        while not shutdown.is_stopped():
            try:
                # 获取任务
                task_id = task_service.get_pending_task()
                
                if task_id:
                    # 获取任务详情（包含位置信息）
                    task_details = task_service.get_task_details(task_id)
                    if task_details is None:
                        logger.warning(f"任务 {task_id} 无地理位置限制，跳过签到")
                        if shutdown.wait(900):
                            break
                        continue
                    
                    logger.info(f"获取到签到位置：{task_details.position_name}")
                    
                    # 上传图片
                    img_url = upload_service.upload_image(config.image_path)
                    if not img_url:
                        continue
                    
                    # 提交签到（使用动态位置参数）
                    success = sign_service.submit_sign(
                        task_id=task_id,
                        position_id=task_details.position_id,
                        base_lng=task_details.base_lng,
                        base_lat=task_details.base_lat,
                        image_url=img_url
                    )
                    
                    if success:
                        logger.info(f"签到成功！位置：{task_details.position_name}")
                else:
                    logger.info("心跳保活成功，未发现任务。睡眠 15 分钟...")
                
            except ConnectionError as e:
                logger.error(f"网络连接错误: {e}")
            except RequestException as e:
                logger.error(f"请求错误: {e}")
            except Exception as e:
                logger.error(f"发生异常: {e}")
            
            # 等待15分钟或直到收到退出信号
            if shutdown.wait(900):
                break
        
        logger.info("守护进程已停止")


if __name__ == "__main__":
    run()
