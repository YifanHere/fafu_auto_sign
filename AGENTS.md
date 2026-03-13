# FAFU Auto Sign - 项目知识库

**项目**: 数字FAFU自动签到助手  
**技术栈**: Python 3.10+ / Pydantic / Requests  
**核心功能**: 福建农林大学数字FAFU APP自动签到（逆向工程实现）

---

## 项目结构

```
fafu_auto_sign/
├── src/fafu_auto_sign/          # 核心源代码
│   ├── __init__.py              # 包初始化
│   ├── __main__.py              # python -m 入口点
│   ├── main.py                  # 主应用逻辑（守护进程）
│   ├── config.py                # Pydantic配置管理
│   ├── client.py                # HTTP客户端（带重试）
│   ├── crypto.py                # 签名算法（MD5+Base64）
│   ├── graceful_shutdown.py     # 信号处理/优雅关闭
│   ├── logging_config.py        # 日志配置（JSON+轮转）
│   └── services/                # 业务服务层
│       ├── task_service.py      # 任务识别与管理
│       ├── sign_service.py      # 签到提交（GPS抖动）
│       └── upload_service.py    # 图片上传（七牛云）
├── tests/                       # 测试套件
├── pyproject.toml               # 项目元数据与依赖
├── config.json                  # 用户配置文件（本地）
└── config.json.example          # 配置模板
```

---

## 查找位置指引

| 任务 | 位置 | 关键文件 |
|------|------|----------|
| **添加新配置项** | `config.py` | `AppConfig` 类 |
| **修改签名算法** | `crypto.py` | `generate_auth_header()` |
| **调整重试逻辑** | `client.py` | `FAFUClient.request()` |
| **修改签到逻辑** | `services/sign_service.py` | `SignService.submit_sign()` |
| **修改任务识别** | `services/task_service.py` | `TaskService.get_pending_task()` |
| 修改图片上传 | `services/upload_service.py` | `UploadService.upload_image()`, `SUPPORTED_EXTENSIONS` |
| 添加多图片支持 | `config.py` + `upload_service.py` | `image_dir` 配置 + 目录扫描 + 随机选择 |
| **修改日志格式** | `logging_config.py` | `setup_logging()` |
| **修改关闭逻辑** | `graceful_shutdown.py` | `GracefulShutdown` 类 |
| **修改主循环** | `main.py` | `run()` 函数 |
| **添加测试** | `tests/` | 使用 `conftest.py` fixtures |

---

## 代码约定

### 导入风格
```python
# 1. 标准库
import logging
from pathlib import Path

# 2. 第三方库
import requests
from pydantic import Field

# 3. 项目内部（绝对导入）
from fafu_auto_sign.config import AppConfig
from fafu_auto_sign.client import FAFUClient
```

### 类型注解（强制）
```python
# 所有函数必须有类型注解（mypy严格要求）
def process_task(task_id: str) -> Optional[TaskDetails]:
    ...
```

### 日志使用模式
```python
# 类中使用 self.logger
self.logger = logging.getLogger(self.__class__.__name__)
self.logger.info(f"[*] 操作: {value}")     # 关键步骤
self.logger.debug(f"详情: {value}")         # 调试信息
self.logger.warning(f"[!] 警告: {value}")   # 需要注意
self.logger.error(f"[x] 错误: {value}")     # 错误信息
```

### 错误处理
```python
# 网络错误 - 在 client.py 中统一处理重试
# 业务错误 - 在服务层捕获并记录，返回 None/False 而非抛出
# 致命错误 - Token过期(401)或时间错误(408)直接 sys.exit(1)
```

---

## 反模式（禁止）

| 禁止行为 | 原因 | 正确做法 |
|----------|------|----------|
| 使用裸 `except:` | 会捕获 KeyboardInterrupt | 使用 `except Exception:` 或具体异常 |
| 相对导入 (`from . import`) | 不符合项目约定 | 使用绝对导入 `from fafu_auto_sign...` |
| 手动字符串拼接URL | 易出错 | 使用 f-string 并确保 `/` 处理正确 |
| 硬编码配置值 | 无法灵活部署 | 使用 Pydantic 配置类 |
| 忽略文件句柄关闭 | 资源泄漏 | 使用 `with open()` 上下文管理器 |
| 取消 `as any` 类型断言 | mypy会报错 | 添加正确的类型注解 |
| 修改 `SECRET_KEY` | 会导致签名失效 | 保持逆向获取的原始值 |

---

## 配置优先级

1. 环境变量 (`FAFU_USER_TOKEN` 等)
2. `.env` 文件
3. JSON 配置文件 (`config.json`)
4. 默认值（代码中定义）

---

## 常用命令

```bash
# 开发安装
pip install -e ".[dev]"

# 运行程序
python -m fafu_auto_sign
python -m fafu_auto_sign --config /path/to/config.json

# 或安装后使用脚本
fafu-auto-sign

# 测试
pytest
pytest --cov=fafu_auto_sign --cov-report=html

# 代码格式化
black src/ tests/
isort src/ tests/

# 类型检查
mypy src/
```

---

## 重要注意事项

### Token获取（必须手动）
1. 使用手机抓包工具（Stream/ProxyPin/HttpCanary）
2. 打开数字FAFU APP，进入签到页面
3. 查找 `stuhtapi.fafu.edu.cn` 域名的请求
4. 提取 Header 中的 `Authorization` 字段
5. Base64解码，取 `2_` 开头的最后一段

### 心跳保活机制
- 默认每 15 分钟运行一次循环
- 通过轻量级请求保持 Session 存活
- 支持 SIGINT/SIGTERM 优雅关闭

### GPS抖动（防检测）
- 默认抖动量: `0.00005`（约5米）
- 配置范围: 0 到 0.001
- 每次签到随机生成偏移量

### 关键密钥
```python
# crypto.py 中硬编码，来自逆向工程
SECRET_KEY = "AtPs2O1xEnhwkKDV"  # 切勿修改
```

### 生产部署建议
```bash
# Linux后台运行
nohup python -m fafu_auto_sign > sign.log 2>&1 &

# 或使用 systemd（推荐）
```

---

## 测试策略

| 测试类型 | 文件模式 | 说明 |
|----------|----------|------|
| 单元测试 | `test_*.py` | 单个函数/类测试 |
| 特性测试 | `test_*_characterization.py` | 行为验证（黄金主文件） |
| 集成测试 | `test_integration.py` | 多模块协同测试 |
| Fixtures | `conftest.py` | 共享测试数据 |

---

## 技术实现要点

### 授权头生成（逆向工程）
```
Sign = MD5(SECRET_KEY + CleanURL + Timestamp + Nonce)
Auth = Base64(Timestamp:Nonce:Sign:UserToken)
```

### 任务识别逻辑
1. 获取任务列表（POST `/health-api/sign_in/student/my/page`）
2. 过滤时间窗口：`beginTime <= now <= endTime`
3. 关键词匹配：任务名称包含"晚归"
4. 获取任务详情提取位置坐标

### 签到流程
1. 获取待办任务 → 2. 获取任务详情（含位置）→ 3. 上传图片 → 4. 提交签到（含GPS抖动）
