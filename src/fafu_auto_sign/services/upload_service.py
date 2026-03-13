"""FAFU 自动签到的上传服务模块。

本模块提供图片上传到七牛云存储的功能，
使用上下文管理器进行正确的资源管理。
"""
import logging
import os
from typing import Optional

from fafu_auto_sign.client import FAFUClient


class UploadService:
    """用于上传图片到七牛云存储的服务。
    
    本服务处理：
    - 文件存在性验证
    - 使用正确资源管理的图片上传
    - 从响应中提取 URL
    
    属性:
        client: 用于发起 HTTP 请求的 FAFUClient 实例
        logger: 本服务的日志记录器实例
    """
    
    # 图片上传的 API 端点
    UPLOAD_ENDPOINT = "/health-api/qiniu/image/upload"
    
    # 默认上传参数
    DEFAULT_FILE_PREFIX = "welink/school/health/"
    DEFAULT_COMPRESS = 1
    DEFAULT_DELETE_AFTER_DAYS = 1
    
    def __init__(self, client: FAFUClient):
        """初始化上传服务。
        
        参数:
            client: 用于发起 HTTP 请求的 FAFUClient 实例。
        """
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到七牛云存储。
        
        本方法将图片文件上传到服务器并返回
        七牛云 URL。它使用正确的上下文管理来
        确保文件句柄始终关闭。
        
        参数:
            image_path: 要上传的图片文件路径。
        
        返回:
            如果上传成功则返回图片 URL（字符串），否则返回 None。
        """
        # 检查文件是否存在
        if not os.path.exists(image_path):
            self.logger.error("[!] 错误：请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片！")
            return None
        
        # 使用查询参数构建 URL
        url = (
            f"{self.UPLOAD_ENDPOINT}"
            f"?filePre={self.DEFAULT_FILE_PREFIX}"
            f"&isCompress={self.DEFAULT_COMPRESS}"
            f"&isDeleteAfterDays={self.DEFAULT_DELETE_AFTER_DAYS}"
        )
        
        self.logger.info(f"[*] 正在上传照片: {image_path}")
        
        try:
            # 使用上下文管理器确保文件被正确关闭
            # 这修复了原始代码中的文件句柄泄漏问题
            with open(image_path, 'rb') as f:
                files = {
                    'file': (
                        os.path.basename(image_path),
                        f,
                        'image/jpeg'
                    )
                }
                # POST 请求必须在 with 代码块内
                # 以确保文件句柄仍处于打开状态
                response = self.client.post(url, files=files)
            # 文件在此处由上下文管理器自动关闭
            
            if response.status_code == 200:
                img_url = response.text.strip()
                self.logger.info(f"[*] 照片上传成功, 七牛云URL: {img_url}")
                return img_url
            else:
                self.logger.error(f"[!] 照片上传失败，HTTP状态码: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"[!] 上传照片时发生异常: {e}")
            return None
