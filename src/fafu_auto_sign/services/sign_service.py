"""Sign-in service module for FAFU Auto Sign.

This module provides sign-in submission functionality with GPS jitter
to prevent detection of automated sign-ins.
"""

import logging
import random

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig


class SignService:
    """Service for sign-in submission with GPS jitter.
    
    This service handles:
    - Submitting sign-in requests with randomized GPS coordinates
    - Formatting coordinates to 6 decimal places
    - Handling API responses and logging results
    
    Attributes:
        client: FAFUClient instance for making HTTP requests
        config: AppConfig instance containing location and settings
        logger: Logger instance for this service
    """
    
    def __init__(self, client: FAFUClient, config: AppConfig):
        """Initialize the sign-in service.
        
        Args:
            client: FAFUClient instance for making HTTP requests.
            config: AppConfig instance containing location and settings.
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def submit_sign(self, task_id: str, image_url: str) -> bool:
        """Submit a sign-in request with GPS jitter.
        
        This method generates randomized GPS coordinates by adding a small
        random offset to the base coordinates, then submits the sign-in
        request to the API.
        
        Args:
            task_id: The task ID to sign in for.
            image_url: The URL of the uploaded sign-in image.
        
        Returns:
            True if the sign-in was successful (HTTP 200), False otherwise.
        """
        # Generate randomized GPS coordinates with jitter
        base_lng = self.config.location.lng
        base_lat = self.config.location.lat
        
        # Apply random offset to prevent detection (±0.00005 degrees)
        lng = base_lng + random.uniform(-0.00005, 0.00005)
        lat = base_lat + random.uniform(-0.00005, 0.00005)
        
        # Build the API endpoint URL
        url = f"/health-api/sign_in/{task_id}/student/sign"
        
        # Prepare query parameters (must be URL query params, not JSON body)
        params = {
            "lng": f"{lng:.6f}",
            "lat": f"{lat:.6f}",
            "signImg": image_url,
            "signInPositionId": self.config.sign_in_position_id
        }
        
        self.logger.debug(f"Submitting sign-in for task {task_id} at coordinates [{lng:.6f}, {lat:.6f}]")
        
        try:
            # Make the POST request with query parameters
            response = self.client.post(url, params=params)
            
            # Check if the request was successful
            if response.status_code == 200:
                self.logger.info(f"✅ 签到成功！当前提交坐标：[{lng:.6f}, {lat:.6f}]")
                return True
            else:
                self.logger.error(f"❌ 签到失败，状态码: {response.status_code}, 返回: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 签到请求发生异常: {e}")
            return False
    
    def _calculate_jittered_coordinates(self) -> tuple[float, float]:
        """Calculate GPS coordinates with random jitter.
        
        This is a helper method that can be used for testing or
        when you need just the coordinates without submitting.
        
        Returns:
            Tuple of (longitude, latitude) with jitter applied.
        """
        base_lng = self.config.location.lng
        base_lat = self.config.location.lat
        
        lng = base_lng + random.uniform(-0.00005, 0.00005)
        lat = base_lat + random.uniform(-0.00005, 0.00005)
        
        return lng, lat
