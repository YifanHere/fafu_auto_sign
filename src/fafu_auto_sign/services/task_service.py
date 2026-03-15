"""FAFU 自动签到的任务服务模块。

本模块提供任务识别和管理功能，
包括获取待办任务以及基于时间窗口和关键词的过滤。
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from fafu_auto_sign.client import FAFUClient
from fafu_auto_sign.config import AppConfig


@dataclass
class TaskDetails:
    """包含位置信息的任务详情数据类。

    属性:
        task_id: 任务的 ID
        position_id: 签到位置的 ID
        base_lng: 基准经度坐标（浮点数）
        base_lat: 基准纬度坐标（浮点数）
        position_name: 人类可读的位置名称
    """

    task_id: int
    position_id: int
    base_lng: float
    base_lat: float
    position_name: str


class TaskService:
    """任务识别和管理服务。

    本服务处理：
    - 从 API 获取任务列表
    - 基于时间窗口过滤任务
    - 通过关键词匹配任务（如 "晚归"）
    - 任务处理的详细日志记录

    属性:
        client: 用于发起 HTTP 请求的 FAFUClient 实例
        logger: 本服务的日志记录器实例
    """

    # 获取任务列表的 API 端点
    TASK_LIST_ENDPOINT = "/health-api/sign_in/student/my/page"

    # 默认分页参数
    DEFAULT_ROWS = 50
    DEFAULT_PAGE = 1
    DEFAULT_SIGN_STATE = 0  # 未签到的任务

    def __init__(self, client: FAFUClient, config: AppConfig):
        """初始化任务服务。

        参数:
            client: 用于发起 HTTP 请求的 FAFUClient 实例。
            config: 应用程序配置（包含任务关键词列表）。
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_pending_tasks(self) -> list[str]:
        """获取所有匹配的待办任务 ID。

        本方法从 API 获取任务列表，然后基于以下条件过滤任务：
        1. 时间窗口：begin_time <= 当前时间 <= end_time
        2. 关键词匹配：任务名称中包含任一配置中的关键词

        返回:
            匹配的任务 ID 列表（字符串），最多返回 10 个。

        异常:
            RequestException: 如果 HTTP 请求失败（由客户端处理）
        """
        # 使用查询参数构建 URL
        url = (
            f"{self.TASK_LIST_ENDPOINT}"
            f"?rows={self.DEFAULT_ROWS}"
            f"&pageNum={self.DEFAULT_PAGE}"
            f"&signState={self.DEFAULT_SIGN_STATE}"
        )

        self.logger.info(f"[*] 请求 URL: {url}")

        try:
            # 发起 POST 请求获取任务列表
            # 注意：API 需要使用 POST 方法和表单编码的请求体，
            # 但这个端点不需要请求体参数
            response = self.client.post(
                url, headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            # 解析 JSON 响应
            data = response.json()
            records = data.get("records", [])

            self.logger.debug(f"从 API 获取了 {len(records)} 个任务")

            # 获取当前时间的毫秒数（Unix 时间戳）
            current_time_ms = int(time.time() * 1000)

            # 收集所有匹配的任务
            matching_task_ids: list[str] = []

            # 遍历任务列表并查找匹配的任务
            for task in records:
                if len(matching_task_ids) >= 10:
                    break

                task_id = task.get("id")
                task_name = task.get("name", "")
                begin_time = task.get("beginTime", 0)
                end_time = task.get("endTime", 0)

                # 检查任务当前是否处于活动状态（在时间窗口内）
                is_active = begin_time <= current_time_ms <= end_time

                # 检查任务名称是否包含任一配置中的关键词
                is_target_type = any(keyword in task_name for keyword in self.config.task_keywords)

                self.logger.debug(
                    f"任务: {task_name} (ID: {task_id}), "
                    f"活跃: {is_active}, 目标: {is_target_type}"
                )

                if is_active and is_target_type:
                    # 找到匹配的任务
                    self.logger.info(
                        f"[*] 精准匹配到进行中的签到任务: 【{task_name}】 (ID: {task_id})"
                    )
                    matching_task_ids.append(str(task_id))
                elif is_active and not is_target_type:
                    # 任务处于活动状态但不是目标类型
                    self.logger.info(f"[!] 发现进行中的其他签到，跳过: 【{task_name}】")

            # 未找到匹配的任务
            if not matching_task_ids:
                self.logger.info("[-] 列表中没有正在有效时间内的签到任务。")

            return matching_task_ids

        except Exception as e:
            # 记录错误并重新抛出供调用方处理
            self.logger.error(f"[!] 获取任务列表时发生异常: {e}")
            raise

    def get_pending_task(self) -> Optional[str]:
        """获取第一个匹配的待办任务 ID（向后兼容）。

        本方法是 get_pending_tasks() 的向后兼容版本，
        返回第一个匹配的任务 ID。

        返回:
            如果找到匹配的任务则返回任务 ID（字符串），否则返回 None。
        """
        task_ids = self.get_pending_tasks()
        return task_ids[0] if task_ids else None

    def get_task_details(self, task_id: int) -> Optional[TaskDetails]:
        """获取包含位置信息的任务详情。

        本方法从 API 获取任务详情，并提取签到位置信息，
        包括坐标和位置 ID。

        参数:
            task_id: 要获取详情的任务 ID

        返回:
            如果成功则返回 TaskDetails 对象，否则返回 None：
            - 如果 signInPositions 为空或 None 则返回 None
            - 如果 API 请求失败则返回 None
            - 如果响应解析失败则返回 None
        """
        url = f"/health-api/sign_in/{task_id}?fromPage=0"

        self.logger.info(f"[*] 请求任务详情 URL: {url}")

        try:
            # 发起 GET 请求获取任务详情
            response = self.client.get(url)

            # 解析 JSON 响应
            data = response.json()
            sign_in_positions = data.get("signInPositions", [])

            # 边界检查：如果 signInPositions 为空或 None 则返回 None
            if not sign_in_positions:
                self.logger.warning(f"[!] 任务 {task_id} 没有签到位置信息")
                return None

            # 提取第一个位置
            position = sign_in_positions[0]

            # 解析并转换字段
            position_id = position.get("id")
            lng_str = position.get("lng", "0")
            lat_str = position.get("lat", "0")
            position_name = position.get("positionName", "")

            # 将经度/纬度转换为浮点数，使用防御式编程
            try:
                base_lng = float(lng_str)
                base_lat = float(lat_str)
            except (ValueError, TypeError) as e:
                self.logger.error(f"[!] 无法解析坐标: lng={lng_str}, lat={lat_str}, 错误: {e}")
                return None

            self.logger.info(f"[*] 成功获取任务 {task_id} 的位置信息: {position_name}")

            return TaskDetails(
                task_id=task_id,
                position_id=position_id,
                base_lng=base_lng,
                base_lat=base_lat,
                position_name=position_name,
            )

        except Exception as e:
            # 记录错误并返回 None
            self.logger.error(f"[!] 获取任务详情时发生异常: {e}")
            return None
