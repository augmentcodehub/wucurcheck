# 注册模块重构设计

## 背景

当前项目需要支持多个 provider（wucur、kiro，未来可能更多）的账号注册。现有代码中：
- wucur 注册有 Use Case 层和适配器分离
- kiro 注册是面向过程的脚本，浏览器操作、API 调用、流程编排混在一起

随着 provider 增多，需要统一的注册架构，使新增 provider 只需实现接口而不改动编排逻辑。

## 设计目标

1. **新增 provider 只需实现接口** — 不改动 Use Case、CLI、Workflow
2. **可测试** — 核心逻辑可 mock 浏览器和网络
3. **职责分离** — 浏览器操作、token 获取、邮箱验证各自独立
4. **保持向后兼容** — CLI 参数和 workflow 回调格式不变

## 目标架构

```
python/src/
├── core/
│   ├── ports/
│   │   ├── registration_service.py      # 注册服务接口
│   │   ├── token_service.py             # Token 获取/刷新接口
│   │   └── email_verification.py        # 邮箱验证接口（已有 EmailClient）
│   ├── application/
│   │   └── register_account_use_case.py # 统一注册编排（替代各 provider 独立脚本）
│   └── domain.py                        # RegistrationResult 等领域对象
│
├── adapters/
│   ├── registration/                    # 注册适配器（每个 provider 一个）
│   │   ├── base.py                      # RegistrationService 抽象基类
│   │   ├── kiro/
│   │   │   ├── browser_flow.py          # Playwright 页面操作（Page Object）
│   │   │   └── sso_device_auth.py       # SSO Device Auth API 流程
│   │   └── wucur/
│   │       └── api_registration.py      # Wucur HTTP API 注册
│   ├── token/                           # Token 服务适配器
│   │   ├── base.py                      # TokenService 抽象基类
│   │   ├── oidc_token_service.py        # AWS OIDC token 刷新
│   │   └── social_token_service.py      # 社交登录 token 刷新
│   └── email/                           # 已有，不变
│       ├── base.py
│       ├── ouraihub.py
│       ├── outlook_graph.py
│       └── generic_api.py
│
└── cli/
    └── register.py                      # 统一 CLI 入口（--provider kiro/wucur/...）
```

## 核心接口定义

### RegistrationService

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RegistrationResult:
    success: bool
    username: str | None = None
    password: str | None = None
    platform: str = ""
    # Token 相关（provider 按需填充）
    sso_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    region: str = "us-east-1"
    expires_in: int | None = None
    # 元数据
    name: str | None = None
    error: str | None = None

class RegistrationService(ABC):
    """每个 provider 实现此接口。"""

    @property
    @abstractmethod
    def platform(self) -> str:
        """Provider 标识，如 'kiro', 'wucur'"""

    @abstractmethod
    async def register(self, email: str, **kwargs) -> RegistrationResult:
        """执行注册，返回结果。"""
```

### TokenService

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class TokenRefreshResult:
    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    error: str | None = None

class TokenService(ABC):
    @abstractmethod
    async def refresh(self, refresh_token: str, **credentials) -> TokenRefreshResult:
        """刷新 token。"""
```

### RegisterAccountUseCase

```python
class RegisterAccountUseCase:
    def __init__(self, registry: dict[str, RegistrationService]):
        self._registry = registry

    async def execute(self, provider: str, email: str, **kwargs) -> RegistrationResult:
        service = self._registry.get(provider)
        if not service:
            raise ValueError(f"Unknown provider: {provider}")
        return await service.register(email, **kwargs)
```

## 新增 Provider 示例

假设新增 `cursor` provider：

```python
# adapters/registration/cursor/cursor_registration.py
class CursorRegistrationService(RegistrationService):
    @property
    def platform(self) -> str:
        return "cursor"

    async def register(self, email: str, **kwargs) -> RegistrationResult:
        # 实现 cursor 注册逻辑
        ...
```

注册到 Use Case：

```python
use_case = RegisterAccountUseCase({
    "kiro": KiroRegistrationService(email_client=...),
    "wucur": WucurRegistrationService(http_client=...),
    "cursor": CursorRegistrationService(...),
})
result = await use_case.execute("cursor", email="xxx@example.com")
```

## 统一 CLI

```bash
# 替代 register_kiro.py / register_wucur.py
python -m cli.register --provider kiro --email-provider ouraihub --email-api-key xxx
python -m cli.register --provider wucur --username xxx --password xxx
python -m cli.register --provider cursor --email xxx
```

## 统一 Workflow

```yaml
# .github/workflows/register.yml (统一)
inputs:
  provider:
    description: 'Provider (kiro/wucur/cursor/...)'
    required: true
  count:
    description: '注册数量'
    default: '1'
  # ... 其他通用参数
```

## 重构步骤

| 阶段 | 内容 | 影响范围 |
|------|------|----------|
| 1 | 定义 `RegistrationService` 和 `TokenService` 接口 | 新增文件，无破坏 |
| 2 | 将 kiro 注册逻辑拆分为 `browser_flow.py` + `sso_device_auth.py`，实现接口 | 重构 `register_kiro_account.py` |
| 3 | 将 wucur 注册逻辑包装为 `WucurRegistrationService` | 包装现有代码 |
| 4 | 实现 `RegisterAccountUseCase`，统一 CLI 入口 | 新增 `cli/register.py` |
| 5 | 统一 workflow，用 `--provider` 参数区分 | 合并 workflow |
| 6 | 添加 `OidcTokenService` 实现 token 刷新 | 新增适配器 |

## 不变的部分

- Worker Dashboard 前端和回调逻辑（`batch_result` handler 已通用）
- 邮箱适配器（`adapters/email/`）
- KV 存储格式（`putAccount` 用 `...item` 展开，字段自适应）
- 签到逻辑（按 `platform` 字段过滤，互不干扰）
