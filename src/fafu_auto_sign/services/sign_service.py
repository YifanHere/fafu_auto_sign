"""FAFU 自动签到的签到服务模块。

本模块提供带 GPS 抖动的签到提交功能，
以防止被检测到是自动签到。
"""
import logging
import random

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig


class SignService:
    """带 GPS 抖动的签到提交服务。
    
    本服务处理以下功能：
    - 提交带随机 GPS 坐标的签到请求
    - 将坐标格式化为 6 位小数
    - 处理 API 响应并记录结果
    
    属性:
        client: 用于发起 HTTP 请求的 FAFUClient 实例
        config: 包含抖动设置的 AppConfig 实例
        logger: 本服务的日志记录器实例
    """
    
    def __init__(self, client: FAFUClient, config: AppConfig):
        """初始化签到服务。
        
        参数:
            client: 用于发起 HTTP 请求的 FAFUClient 实例。
            config: 包含位置和设置的 AppConfig 实例。
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def submit_sign(self, task_id: int, position_id: int,
                    base_lng: float, base_lat: float, image_url: str) -> bool:
        """提交带 GPS 抖动的签到请求。
        
        本方法通过为基础坐标添加小的随机偏移量来生成随机 GPS 坐标，
        然后向 API 提交签到请求。
        
        参数:
            task_id: 要签到的任务 ID。
            position_id: 来自任务详情的签到位置 ID。
            base_lng: 来自任务详情的基础经度坐标。
            base_lat: 来自任务详情的基础纬度坐标。
            image_url: 上传的签到图片 URL。
        
        返回:
            如果签到成功（HTTP 200）返回 True，否则返回 False。
        """
        # 使用抖动生成随机化的 GPS 坐标
        jitter = self.config.jitter
        lng = base_lng + random.uniform(-jitter, jitter)
        lat = base_lat + random.uniform(-jitter, jitter)
        
        # 构建 API 端点 URL（干净的基 URL，无查询参数）
        url = f"/health-api/sign_in/{task_id}/student/sign"
        
        # 准备查询参数（必须是 URL 查询参数，不能是 JSON 请求体）
        params = {
            "lng": f"{lng:.6f}",
            "lat": f"{lat:.6f}",
            "signImg": image_url,
            "signInPositionId": position_id
        }
        
        self.logger.debug(f"正在为任务 {task_id} 提交签到，坐标 [{lng:.6f}, {lat:.6f}]")
        
        try:
            # 使用查询参数发起 POST 请求
            response = self.client.post(url, params=params)
            
            # 检查请求是否成功
            if response.status_code == 200:
                self.logger.info(f"✅ 签到成功！当前提交坐标：[{lng:.6f}, {lat:.6f}]")
                return True
            else:
                self.logger.error(f"❌ 签到失败，状态码: {response.status_code}, 返回: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 签到请求发生异常: {e}")
            return False
    
    def _calculate_jittered_coordinates(self, base_lng: float, base_lat: float) -> tuple[float, float]:
        """计算带随机抖动的 GPS 坐标。
        
        这是一个辅助方法，可用于测试或
        当你只需要坐标而不需要提交时。
        
        参数:
            base_lng: 基础经度坐标。
            base_lat: 基础纬度坐标。
        
        返回:
            应用抖动后的（经度，纬度）元组。
        """
        jitter = self.config.jitter
        
        lng = base_lng + random.uniform(-jitter, jitter)
        lat = base_lat + random.uniform(-jitter, jitter)
        
        return lng, lat
