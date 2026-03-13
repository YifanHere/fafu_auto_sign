"""FAFU 自动签到的上传服务模块。

本模块提供图片上传到七牛云存储的功能，
使用上下文管理器进行正确的资源管理。
"""
import logging
import os
from pathlib import Path
import random
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
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
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
    
    def _get_image_files(self, image_dir: str) -> list[str]:
        """扫描目录返回所有支持的图片文件。
        
        遍历指定目录，过滤隐藏文件和不在支持列表中的扩展名，
        返回所有符合要求的图片文件的完整路径列表。
        
        参数:
            image_dir: 要扫描的目录路径。
        
        返回:
            图片文件的完整路径列表（按字母排序）。
        """
        path = Path(image_dir)
        image_files: list[str] = []
        
        for file_path in path.iterdir():
            if file_path.is_file():
                # 过滤隐藏文件（以.开头的文件）
                if file_path.name.startswith('.'):
                    continue
                # 检查扩展名是否在支持列表中
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    image_files.append(str(file_path.resolve()))
        
        # 按字母排序保证确定性
        image_files.sort()
        
        self.logger.debug(f"扫描到 {len(image_files)} 张图片: {image_files}")
        return image_files
    
    def _select_random_image(self, image_files: list[str]) -> Optional[str]:
        """从图片列表中随机选择一张。
        
        参数:
            image_files: 图片文件路径列表。
        
        返回:
            随机选择的图片路径，如果列表为空则返回 None。
        """
        if not image_files:
            return None
        
        selected = random.choice(image_files)
        self.logger.info(f"[*] 随机选择图片: {Path(selected).name}")
        return selected
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到七牛云存储。
        
        本方法将图片文件上传到服务器并返回
        七牛云 URL。它使用正确的上下文管理来
        确保文件句柄始终关闭。
        
        参数:
            image_path: 要上传的图片文件路径（当未配置 image_dir 时使用）。
        
        返回:
            如果上传成功则返回图片 URL（字符串），否则返回 None。
        """
        # 确定要上传的图片路径
        actual_image_path = image_path
        
        # 如果配置了 image_dir，则从目录随机选择图片
        if hasattr(self.client, 'config') and self.client.config.image_dir:
            image_dir = self.client.config.image_dir
            self.logger.info(f"[*] 使用图片目录: {image_dir}")
            
            image_files = self._get_image_files(image_dir)
            selected = self._select_random_image(image_files)
            
            if selected is None:
                self.logger.error(f"[x] 错误：图片目录为空或不包含支持的图片格式: {image_dir}")
                return None
            
            actual_image_path = selected
        
        # 检查文件是否存在
        if not os.path.exists(actual_image_path):
            self.logger.error(f"[!] 错误：请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片！")
            return None
        
        # 使用查询参数构建 URL
        url = (
            f"{self.UPLOAD_ENDPOINT}"
            f"?filePre={self.DEFAULT_FILE_PREFIX}"
            f"&isCompress={self.DEFAULT_COMPRESS}"
            f"&isDeleteAfterDays={self.DEFAULT_DELETE_AFTER_DAYS}"
        )
        
        self.logger.info(f"[*] 正在上传照片: {actual_image_path}")
        
        try:
            # 使用上下文管理器确保文件被正确关闭
            # 这修复了原始代码中的文件句柄泄漏问题
            with open(actual_image_path, 'rb') as f:
                files = {
                    'file': (
                        os.path.basename(actual_image_path),
                        f,
                        'image/jpeg'
                    )
                }
                # POST 请求必须在 with 代码块内
                # 以确保文件句柄仍处于打开状态
                response = self.client.post(url, files=files)
            # 文件在此处由上下文管理器自动关闭
            
            if response.status_code == 200:
                img_url: str = response.text.strip()
                self.logger.info(f"[*] 照片上传成功, 七牛云URL: {img_url}")
                return img_url
            else:
                self.logger.error(f"[!] 照片上传失败，HTTP状态码: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"[!] 上传照片时发生异常: {e}")
            return None
