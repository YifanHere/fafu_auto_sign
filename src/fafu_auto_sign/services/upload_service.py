"""Upload service module for FAFU Auto Sign.

This module provides image upload functionality to Qiniu cloud storage,
with proper resource management using context managers.
"""

import logging
import os
from typing import Optional

from fafu_auto_sign.client import FAFUClient


class UploadService:
    """Service for image upload to Qiniu cloud storage.
    
    This service handles:
    - File existence validation
    - Image upload with proper resource management
    - URL extraction from response
    
    Attributes:
        client: FAFUClient instance for making HTTP requests
        logger: Logger instance for this service
    """
    
    # API endpoint for image upload
    UPLOAD_ENDPOINT = "/health-api/qiniu/image/upload"
    
    # Default upload parameters
    DEFAULT_FILE_PREFIX = "welink/school/health/"
    DEFAULT_COMPRESS = 1
    DEFAULT_DELETE_AFTER_DAYS = 1
    
    def __init__(self, client: FAFUClient):
        """Initialize the upload service.
        
        Args:
            client: FAFUClient instance for making HTTP requests.
        """
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """Upload an image to Qiniu cloud storage.
        
        This method uploads an image file to the server and returns
        the Qiniu cloud URL. It uses proper context management to
        ensure file handles are always closed.
        
        Args:
            image_path: Path to the image file to upload.
        
        Returns:
            The image URL (str) if upload is successful, None otherwise.
        """
        # Check if file exists
        if not os.path.exists(image_path):
            self.logger.error("[!] 错误：请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片！")
            return None
        
        # Build the URL with query parameters
        url = (
            f"{self.UPLOAD_ENDPOINT}"
            f"?filePre={self.DEFAULT_FILE_PREFIX}"
            f"&isCompress={self.DEFAULT_COMPRESS}"
            f"&isDeleteAfterDays={self.DEFAULT_DELETE_AFTER_DAYS}"
        )
        
        self.logger.info(f"[*] 正在上传照片: {image_path}")
        
        try:
            # Use context manager to ensure file is properly closed
            # This fixes the file handle leak in the original code
            with open(image_path, 'rb') as f:
                files = {
                    'file': (
                        os.path.basename(image_path),
                        f,
                        'image/jpeg'
                    )
                }
                # The post request must be inside the with block
                # to ensure the file handle is still open
                response = self.client.post(url, files=files)
            # File is automatically closed here by the context manager
            
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
