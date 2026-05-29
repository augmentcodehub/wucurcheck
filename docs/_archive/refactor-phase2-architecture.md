# 阶段 2：架构重构设计文档

## 目标

借鉴 msgflow 的架构模式，将 wucurcheck Python 端从"脚本堆砌"升级为"面向接口的管道架构"。

## 现状问题

1. **入口分散** — `cli/checkin.py`、`scripts/checkin_batch.py`、`scripts/kiro_refresh.py` 各自独立，重复逻辑
2. **接口定义了但没用** — `core/ports/` 定义了 Protocol，但主要脚本直接调自由函数
3. **Use Case 层过度设计** — `core/application/` 有 9 个 use case 文件，但实际只有 `register_and_checkin_account_use_case.py` 被使用
4. **ProviderConfig 重复** — `utils/config.py` 和 `core/provider_profile.py` 是同一个东西的两份定义
5. **400 行 god module** — `cli/checkin.py` 混合了认证、WAF 绕过、签到、通知、余额追踪

## 设计原则（借鉴 msgflow）

| 原则 | msgflow 做法 | wucurcheck 适配 |
|------|-------------|----------------|
| 统一入口 | `run_task.py` + typer | 统一 CLI 入口，子命令分发 |
| Registry 自动发现 | `@registry.register` 装饰器 | Provider 用 registry 注册 |
| Pipeline 组合 | `FetchPipeline.execute(target)` → `Result` | `CheckinPipeline.execute(account)` → `Result` |
| 单一职责 | 每个文件 < 50 行 | 拆分 god module |
| 统一返回值 | `Result(success, data, artifacts)` | 同 |
| 结构化日志 | `pycore.logger` | 已有 `utils.logger`，保持 |

## 目标架构

```
python/src/
├── run.py                    # 统一 CLI 入口（typer）
├── core/
│   ├── result.py             # Result 值对象
│   ├── provider.py           # Provider 数据类（合并 ProviderConfig + ProviderProfile）
│   └── account.py            # Account 数据类
├── providers/
│   ├── __init__.py           # Registry + auto-import
│   ├── _registry.py          # Provider registry
│   ├── wucur.py              # @register: login/checkin/get_info 实现
│   ├── anyrouter.py          # @register: WAF + cookie 模式
│   └── kiro.py               # @register: OIDC token refresh
├── pipelines/
│   ├── __init__.py           # Pipeline registry
│   ├── checkin.py            # login → checkin → get_info → Result
│   ├── register.py           # register → login → checkin → Result
│   ├── batch_checkin.py      # 批量签到（带限流、重试）
│   └── kiro_refresh.py       # OIDC refresh → Result
├── lib/
│   ├── constants.py          # QUOTA_UNIT_DIVISOR, DEFAULT_USER_AGENT, DEFAULT_PASSWORD
│   ├── http.py               # parse_response, build_headers（不创建 Client）
│   └── registry.py           # Registry 类（Provider 注册用）
├── utils/
│   ├── logger.py             # 结构化日志（保持现有，所有模块共用）
│   ├── notify.py             # 通知（保持现有）
│   └── config.py             # AccountConfig 等（保持现有，逐步废弃）
└── scripts/                  # GitHub Actions 入口脚本（薄壳，调用 pipeline）
    ├── checkin_batch.py      # 读 JSON → 调 batch_checkin pipeline → 输出结果
    └── kiro_refresh.py       # 读 KV → 调 kiro_refresh pipeline → 回调
```

## 核心设计

### 1. Result 值对象

```python
# core/result.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Result:
    success: bool
    data: dict | None = None
    message: str = ""

    @classmethod
    def ok(cls, data: dict | None = None, message: str = "") -> Result:
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, message: str, data: dict | None = None) -> Result:
        return cls(success=False, data=data, message=message)
```

### 2. Provider Registry

**关键设计决策：** Provider 是无状态的策略对象，HTTP session 由调用方（Pipeline）管理并传入。这样 Provider 可以安全注册为单例，同时支持 wucur 的 session cookie 需求。

```python
# lib/registry.py
from __future__ import annotations
from typing import Any

class Registry:
    def __init__(self, kind: str) -> None:
        self._items: dict[str, Any] = {}

    def register(self, cls: type) -> type:
        instance = cls()
        self._items[getattr(instance, "name", cls.__name__)] = instance
        return cls

    def get(self, name: str) -> Any | None:
        return self._items.get(name)
```

```python
# providers/_registry.py
from lib.registry import Registry

provider_registry: Registry = Registry("provider")
```

```python
# providers/__init__.py
"""Provider auto-discovery."""
from providers._registry import provider_registry
from providers.wucur import WucurProvider  # noqa: F401

def get_provider(name: str):
    return provider_registry.get(name)
```

```python
# providers/wucur.py
"""Wucur provider — login/checkin/get_balance 实现。

关键：所有方法接收 httpx.Client 参数，由 Pipeline 管理 client 生命周期。
这样 login 设置的 session cookie 会自动在后续 checkin/get_balance 中复用。
"""
import httpx
from providers._registry import provider_registry
from core.result import Result
from lib.http import build_headers, parse_response
from lib.constants import QUOTA_UNIT_DIVISOR, DEFAULT_USER_AGENT
from utils.logger import get_logger

log = get_logger("provider.wucur")


@provider_registry.register
class WucurProvider:
    name = "wucur"
    domain = "http://wucur.com:6543"
    login_path = "/login"
    login_api_path = "/api/user/login"
    checkin_path = "/api/user/checkin"
    user_info_path = "/api/user/self"
    api_user_key = "new-api-user"

    def login(self, client: httpx.Client, username: str, password: str) -> Result:
        """登录并设置 session cookie 到 client 上。"""
        headers = build_headers(self.domain, self.login_path)
        resp = client.post(
            f"{self.domain}{self.login_api_path}",
            headers=headers,
            json={"username": username, "password": password},
            timeout=30,
        )
        data = parse_response(resp)
        if resp.status_code != 200 or not data.get("success"):
            return Result.fail(data.get("message", f"HTTP {resp.status_code}"))
        if "session" not in client.cookies:
            return Result.fail("Login succeeded but session cookie not found")
        user_id = str(data.get("data", {}).get("id", ""))
        log.info("Login success", extra={"username": username})
        return Result.ok({"user_id": user_id, "raw": data})

    def checkin(self, client: httpx.Client, headers: dict) -> Result:
        """执行签到。需要 login 后的 session cookie（已在 client 中）。"""
        checkin_headers = {**headers, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
        resp = client.post(f"{self.domain}{self.checkin_path}", headers=checkin_headers, timeout=30)
        data = parse_response(resp)
        if not data.get("success"):
            msg = data.get("message", "")
            if "已签到" in msg or "已经签到" in msg:
                return Result.ok(data, message="今日已签到")
            return Result.fail(msg, data)
        quota_awarded = data.get("data", {}).get("quota_awarded", 0)
        return Result.ok(data, message=f"签到成功 +${quota_awarded / QUOTA_UNIT_DIVISOR:.2f}")

    def get_balance(self, client: httpx.Client, headers: dict) -> Result:
        """获取余额。需要 login 后的 session cookie。"""
        resp = client.get(f"{self.domain}{self.user_info_path}", headers=headers, timeout=30)
        data = parse_response(resp)
        if resp.status_code != 200 or not data.get("success"):
            return Result.fail(f"HTTP {resp.status_code}")
        user = data.get("data", {})
        return Result.ok({
            "quota": round(user.get("quota", 0) / QUOTA_UNIT_DIVISOR, 2),
            "used": round(user.get("used_quota", 0) / QUOTA_UNIT_DIVISOR, 2),
        })

    def build_auth_headers(self, user_id: str) -> dict:
        """构建认证后的请求头。"""
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }
        if self.api_user_key and user_id:
            headers[self.api_user_key] = user_id
        return headers
```

### 3. Pipeline

```python
# pipelines/checkin.py
"""单账号签到 Pipeline：login → checkin → get_balance。"""
import httpx
from core.result import Result
from providers import get_provider
from utils.logger import get_logger

log = get_logger("pipeline.checkin")


class CheckinPipeline:
    def execute(self, username: str, password: str, provider_name: str = "wucur") -> Result:
        provider = get_provider(provider_name)
        if not provider:
            return Result.fail(f"未知 provider: {provider_name}")

        # 使用同一个 client 保持 session cookie
        with httpx.Client(http2=True, timeout=30.0) as client:
            # 1. Login
            login_result = provider.login(client, username, password)
            if not login_result.success:
                log.warning("Login failed", extra={"username": username, "error": login_result.message})
                return Result.fail(f"登录失败: {login_result.message}")

            # 2. Build auth headers
            user_id = login_result.data.get("user_id", "") if login_result.data else ""
            headers = provider.build_auth_headers(user_id)

            # 3. Checkin
            checkin_result = provider.checkin(client, headers)
            log.info("Checkin done", extra={"username": username, "message": checkin_result.message})

            # 4. Get balance
            balance_result = provider.get_balance(client, headers)
            balance = str(balance_result.data.get("quota", 0)) if balance_result.success and balance_result.data else None

        return Result.ok({
            "checkin_message": checkin_result.message,
            "balance": balance,
            "checkin_time": None,  # 由调用方填充时间戳
        }, message=checkin_result.message)
```

### 4. Scripts 薄壳

```python
# scripts/checkin_batch.py（重构后）
"""GitHub Actions 入口：读 JSON → 逐个签到 → 输出结果。

输出格式必须匹配 Worker Dashboard callback 期望的 schema：
{
  "username": str,
  "status": "active" | "failed",
  "last_result": str,       # 如 "签到成功 +$1.00" 或 "今日已签到"
  "balance": str | None,    # 如 "9.24"
  "checkin_time": str | None  # ISO 时间戳
}
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.checkin import CheckinPipeline
from utils.logger import get_logger

log = get_logger("scripts.checkin_batch")

ACCOUNTS_FILE = Path("artifacts/checkin_accounts.json")
RESULTS_FILE = Path("artifacts/checkin_results.json")


def run():
    if not ACCOUNTS_FILE.exists():
        log.error("No accounts file found")
        return

    accounts = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    log.info("Batch checkin started", extra={"count": len(accounts)})

    pipeline = CheckinPipeline()
    results = []

    for i, acct in enumerate(accounts):
        username = acct.get("username", "")
        password = acct.get("password", "")
        log.info("Processing", extra={"username": username, "has_password": bool(password)})

        result = pipeline.execute(username, password)
        results.append({
            "username": username,
            "status": "active" if result.success else "failed",
            "last_result": result.message or ("签到成功" if result.success else "签到失败"),
            "balance": result.data.get("balance") if result.data else None,
            "checkin_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if result.success else None,
        })

        if i < len(accounts) - 1:
            if (i + 1) % 15 == 0:
                time.sleep(120)
            else:
                time.sleep(random.randint(15, 30))

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    success = sum(1 for r in results if r["status"] == "active")
    log.info("Batch complete", extra={"success": success, "total": len(results)})


if __name__ == "__main__":
    run()
```

### 5. HTTP 工具函数（非独立 Client）

```python
# lib/http.py
"""HTTP 工具函数 — 不创建 Client，只提供辅助方法。Client 由调用方管理。"""
import json as _json
import httpx
from lib.constants import DEFAULT_USER_AGENT


def parse_response(resp: httpx.Response) -> dict:
    """安全解析 JSON 响应。"""
    try:
        return resp.json()
    except (_json.JSONDecodeError, Exception):
        return {"success": False, "message": f"HTTP {resp.status_code}: invalid JSON"}


def build_headers(origin: str, referer_path: str) -> dict[str, str]:
    """构建标准登录/API 请求头。"""
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": origin,
        "Referer": f"{origin}{referer_path}",
    }
```

### 6. 其他必需模块

```python
# lib/constants.py
"""共享常量。"""

QUOTA_UNIT_DIVISOR = 500_000
"""wucur API 返回的 quota 原始值除以此数得到美元金额。"""

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

DEFAULT_PASSWORD = "123Claude&Codex"
"""KV 中缺少 password 字段时的 fallback。"""
```

```python
# pipelines/__init__.py
"""Pipeline registry — 目前不使用 registry，直接 import 使用。"""
```

**注意：** `lib/logger.py` 不需要新建。所有模块使用现有的 `utils/logger.py`：
```python
from utils.logger import get_logger
```

### 7. 测试兼容性

现有 `tests/test_checkin_batch.py` import 了当前 `scripts/checkin_batch.py` 中的 helper 函数：
```python
from scripts.checkin_batch import build_checkin_result, format_quota_awarded, build_already_checked_result
```

**处理方式：** 步骤 4 重写 script 时，将这些 helper 函数保留在 `scripts/checkin_batch.py` 中（它们是纯函数，不依赖旧架构），或将测试同步更新为测试新的 Pipeline。

推荐：保留 helper 函数作为输出格式化工具，Pipeline 返回原始数据，script 薄壳调用 helper 格式化输出。

## 迁移策略

**渐进式迁移，不一步到位：**

| 步骤 | 内容 | 风险 |
|------|------|------|
| 0 | 更新 `pyproject.toml` 的 packages include 列表，添加 `"providers*"`, `"pipelines*"`, `"lib*"` | 零风险 |
| 1 | 新建 `core/result.py`、`lib/__init__.py`、`lib/http.py`、`lib/constants.py`、`lib/registry.py` | 零风险，纯新增 |
| 2 | 新建 `providers/__init__.py`、`providers/_registry.py`、`providers/wucur.py` | 零风险，纯新增 |
| 3 | 新建 `pipelines/__init__.py`、`pipelines/checkin.py`，调用 provider | 零风险，纯新增 |
| 4 | 重写 `scripts/checkin_batch.py` 使用新 pipeline（用文档代码完全替换） | 中风险，需验证 GitHub Actions |
| 5 | （后续）重写 `scripts/kiro_refresh.py` 使用新 pipeline | 中风险，本次不执行 |
| 6 | （后续）废弃 `cli/checkin.py` 中的重复逻辑，改为调用 provider | 高风险，本次不执行 |
| 7 | （后续）清理旧代码（删除 `core/application/` 中未使用的 use case） | 低风险，本次不执行 |

**注意事项：**
- `scripts/checkin_batch.py` 保留 `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` 以支持直接执行
- 输出 JSON 必须包含 `username`、`status`、`last_result`、`balance`（字符串）、`checkin_time`（ISO 时间戳）
- Provider 的 domain/path 配置后续应支持 `PROVIDERS` 环境变量覆盖（与现有行为一致），初期先硬编码
- `lib/__init__.py` 为空文件（仅标记为 Python 包）
- `pipelines/__init__.py` 为空文件（仅标记为 Python 包）
- 步骤 4 "重写"含义：用本文档"4. Scripts 薄壳"一节的代码**完全替换**现有 `scripts/checkin_batch.py` 的全部内容
- 步骤 5 和步骤 6 本次不执行（scope 限定为步骤 0-4），后续单独设计
- 现有 `tests/test_checkin_batch.py` 中 import 的 `build_checkin_result`、`format_quota_awarded`、`build_already_checked_result` 函数在重写后不再存在，需同步更新测试文件：删除对这些函数的测试，改为测试 `CheckinPipeline.execute()` 的返回值

## 不做的事情

- 不改 TypeScript Worker Dashboard（阶段 2 只重构 Python 端）
- 不改 GitHub Actions workflow 文件（保持入口脚本路径不变）
- 不引入新的外部依赖（不用 pycore，保持自包含）
- 不改通知模块（`utils/notify.py` 保持不动）
- 不改 WAF/Playwright 逻辑（`cli/checkin.py` 中 anyrouter 的 WAF 绕过保留）

## 验证计划

```bash
# 每步完成后：
uv run pytest python/tests/ -x
uv run python -m py_compile python/src/pipelines/checkin.py

# 步骤 4 完成后额外验证：
echo '[{"username":"test@test.com","password":"test"}]' > artifacts/checkin_accounts.json
uv run python python/src/scripts/checkin_batch.py  # 预期：登录失败但不 crash
```

## 与现有代码的兼容

- `scripts/checkin_batch.py` 路径不变（GitHub Actions 依赖此路径）
- `scripts/kiro_refresh.py` 路径不变
- `cli/checkin.py` 保留（`checkin.yml` 依赖），但内部改为调用 provider
- 现有测试全部保持通过
