# FAFU Auto Sign - 核心代码

**位置**: `src/fafu_auto_sign/`  
**职责**: HTTP客户端、签名算法、业务服务、配置管理

---

## 模块关系

```
main.py
  ├─ config.py (AppConfig)
  ├─ logging_config.py
  ├─ client.py (FAFUClient)
  │   └─ crypto.py (generate_headers)
  ├─ services/
  │   ├─ task_service.py (TaskService, TaskDetails)
  │   ├─ sign_service.py (SignService)
  │   └─ upload_service.py (UploadService)
  └─ graceful_shutdown.py (GracefulShutdown)
```

---

## 核心类速查

| 类 | 文件 | 职责 |
|----|------|------|
| `AppConfig` | `config.py` | Pydantic配置，验证token格式(2_开头)、抖动范围(0-0.001) |
| `FAFUClient` | `client.py` | HTTP客户端，指数退避重试，401/408直接exit |
| `TaskService` | `services/task_service.py` | 获取任务列表，过滤"晚归"关键词，时间窗口判断 |
| `SignService` | `services/sign_service.py` | GPS抖动提交签到，坐标格式化为6位小数 |
| `UploadService` | `services/upload_service.py` | 上传图片到七牛云，支持从目录随机选择，使用`with open()`确保关闭 |
| `GracefulShutdown` | `graceful_shutdown.py` | SIGINT/SIGTERM处理，15分钟wait或立即退出 |

---

## 关键函数

### crypto.py
```python
generate_auth_header(url: str, user_token: str) -> str
# Sign = MD5(SECRET_KEY + CleanURL + Timestamp + Nonce)
# Auth = Base64(Timestamp:Nonce:Sign:UserToken)
```

### client.py
```python
FAFUClient.request()  # 最大3次重试，延迟1,2,4秒
# 401 -> sys.exit(1) "Token过期"
# 408 -> sys.exit(1) "时间不同步"
```

### task_service.py
```python
task_service.get_pending_task()  # 返回str(task_id)或None
# 匹配条件：beginTime <= now <= endTime AND "晚归" in name

task_service.get_task_details(task_id)  # 返回TaskDetails或None
# 提取signInPositions[0]的坐标和位置名称
```

### upload_service.py

```python
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}  # 支持的图片格式

UploadService._get_image_files(image_dir: str) -> list[str]  # 扫描目录获取图片列表
# 过滤隐藏文件，按扩展名筛选，返回排序后的完整路径列表

UploadService._select_random_image(image_files: list[str]) -> Optional[str]  # 随机选择
# 使用 random.choice，空列表返回 None

UploadService.upload_image(image_path: str) -> Optional[str]  # 上传图片
# 优先检查 image_dir 配置，存在则从目录随机选择，否则使用 image_path（向后兼容）
```

---

## 多图片随机选择机制

新增功能：支持从指定目录随机选择图片，避免长期使用同一张照片被识别。

### 配置方式
```python
# config.py - AppConfig 新增字段
image_dir: Optional[str] = None  # 图片目录路径
# 优先级：image_dir > image_path（向后兼容）
```

### 环境变量支持
```bash
export FAFU_IMAGE_DIR="./photos/"  # 图片目录路径
```

### 图片选择流程
1. `upload_image()` 检查 `self.client.config.image_dir`
2. 如果配置存在：调用 `_get_image_files()` 扫描目录
3. 调用 `_select_random_image()` 从列表中随机选择
4. 如果未配置 `image_dir`：使用原有的 `image_path`（向后兼容）

---



## 签名算法详情

```python
# crypto.py 第12行 - 切勿修改
SECRET_KEY = "AtPs2O1xEnhwkKDV"  # 逆向自APP

# 算法步骤：
# 1. 清理URL（去掉查询参数）
# 2. 生成16位随机nonce
# 3. 获取Unix时间戳（秒）
# 4. raw = SECRET_KEY + clean_url + timestamp + nonce
# 5. sign = MD5(raw).hexdigest()
# 6. auth = f"{timestamp}:{nonce}:{sign}:{user_token}"
# 7. 返回 Base64(auth)
```

---

## GPS抖动机制

```python
# sign_service.py 第55-58行
jitter = config.jitter  # 默认0.00005 (~5米)
lng = base_lng + random.uniform(-jitter, jitter)
lat = base_lat + random.uniform(-jitter, jitter)
# 最终格式化: f"{lng:.6f}"  # 6位小数
```

---

## 错误处理约定

| 层级 | 处理方式 | 示例 |
|------|----------|------|
| client.py | 重试后仍失败则抛出 | `raise RequestException` |
| services | 捕获记录，返回None/False | `return None` |
| main.py | 记录异常，继续下一次循环 | `except Exception: continue` |
| 致命错误 | 立即exit | `sys.exit(1)` |

---

## 日志标记约定

```python
self.logger.info("[*] 操作: ...")    # 关键步骤
self.logger.info("✅ 成功: ...")     # 操作成功
self.logger.info("❌ 失败: ...")     # 操作失败
self.logger.warning("[!] 警告: ...")  # 需要注意
self.logger.error("[x] 错误: ...")    # 错误信息
```

---

## 修改注意事项

1. **修改签名算法**: 确保与APP前端保持一致，否则401错误
2. **修改重试次数**: 修改 `client.py` 的 `MAX_RETRIES`
3. **修改心跳间隔**: 修改 `config.py` 的 `heartbeat_interval` 或环境变量
4. **添加新服务**: 继承模式参考现有服务类，注入FAFUClient
