# FAFU Auto Sign - 测试套件

**位置**: `tests/`  
**框架**: pytest  
**覆盖率**: 目标 > 80%

---

## 测试文件命名

| 模式 | 用途 | 示例 |
|------|------|------|
| `test_*.py` | 标准单元测试 | `test_client.py` |
| `test_*_characterization.py` | 特性/黄金主文件测试 | `test_crypto_characterization.py` |
| `conftest.py` | 共享fixtures | `conftest.py` |

---

## Fixtures (conftest.py)

```python
@pytest.fixture
def sample_token():
    return "2_test_token_for_testing_only"  # 必须以2_开头

@pytest.fixture
def mock_time():
    return 1234567890.0  # 2009-02-13 23:31:30 UTC

@pytest.fixture
def sample_tasks():
    # 包含有效/过期/非目标任务的测试数据
    return {"records": [...]}

@pytest.fixture
def mock_response_success():
    # MagicMock(status_code=200, json=lambda: {...})
    return mock
```

---

## 测试类型

### 1. 单元测试
- 目标: 单个函数/类
- 工具: `unittest.mock.patch`, `responses` mock HTTP
- 位置: `test_*.py` (不含characterization)

### 2. 特性测试 (Characterization)
- 目标: 记录当前行为作为基准
- 特点: 捕获当前输出，变更时提醒
- 位置: `test_*_characterization.py`

### 3. 集成测试
- 目标: 多模块协同
- 文件: `test_integration.py`
- 特点: 可能调用真实API或使用复杂mock

---

## 关键测试模式

### 测试时间相关功能
```python
from freezegun import freeze_time

@freeze_time("2009-02-13 23:31:30")
def test_time_sensitive_function():
    # 时间被冻结，时间戳永远为1234567890
    result = function_that_uses_time()
    assert result == expected
```

### 测试HTTP请求
```python
import responses

@responses.activate
def test_api_call():
    responses.add(
        responses.POST,
        "http://stuhtapi.fafu.edu.cn/api",
        json={"records": []},
        status=200
    )
    # 执行测试...
```

### 测试配置验证
```python
def test_invalid_token_format():
    with pytest.raises(ValueError, match="必须以 '2_' 开头"):
        AppConfig(user_token="invalid_token")

def test_jitter_out_of_range():
    with pytest.raises(ValueError, match="0 到 0.001"):
        AppConfig(user_token="2_valid", jitter=0.01)
```

---

## 运行测试

```bash
# 全部测试
pytest

# 带覆盖率
pytest --cov=fafu_auto_sign --cov-report=html

# 特定文件
pytest tests/test_crypto.py -v

# 特定测试
pytest tests/test_config.py::TestAppConfig::test_token_validation -v
```

---

## 添加新测试指南

1. **创建文件**: 遵循 `test_<module>.py` 命名
2. **使用fixtures**: 优先使用 `conftest.py` 中的共享fixtures
3. **mock外部依赖**: HTTP请求使用 `responses`，时间使用 `freezegun`
4. **断言类型**: 返回值、副作用、异常抛出
5. **测试数据**: 放在fixtures中，不要在测试函数内硬编码

---

## 测试配置 (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--cov=fafu_auto_sign --cov-report=term-missing"
pythonpath = ["src"]
```
