# 注册模块重构 — 详细设计

## 1. 领域对象 (`core/domain.py` 扩展)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RegistrationStatus(Enum):
    SUCCESS = "active"
    FAILED = "failed"
    SUSPENDED = "suspended"


@dataclass
class Credentials:
    """Provider 返回的凭证，字段按需填充。"""
    sso_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    region: str = "us-east-1"
    expires_in: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class RegistrationResult:
    """统一注册结果，所有 provider 返回此对象。"""
    success: bool
    username: str = ""           # 邮箱/用户名
    password: str = ""
    platform: str = ""           # provider 标识
    status: RegistrationStatus = RegistrationStatus.FAILED
    name: str = ""               # 显示名
    credentials: Credentials = field(default_factory=Credentials)
    error: str | None = None

    def to_callback_dict(self) -> dict[str, Any]:
        """转换为 Worker callback 的 batch_result item 格式。"""
        d = {
            "username": self.username,
            "password": self.password,
            "platform": self.platform,
            "status": self.status.value,
            "last_result": "注册成功" if self.success else f"注册失败: {self.error}",
            "name": self.name,
        }
        d.update(self.credentials.to_dict())
        return d


@dataclass
class TokenRefreshResult:
    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    error: str | None = None
```

## 2. 端口接口 (`core/ports/`)

### 2.1 `core/ports/registration_service.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from core.domain import RegistrationResult


class RegistrationConfig:
    """注册配置基类，每个 provider 继承扩展。"""
    def __init__(self, *, proxy_url: str | None = None, headless: bool = True, code_timeout: int = 120):
        self.proxy_url = proxy_url
        self.headless = headless
        self.code_timeout = code_timeout


class RegistrationService(ABC):
    """注册服务接口。每个 provider 实现一个。"""

    @property
    @abstractmethod
    def platform(self) -> str:
        """返回 provider 标识，如 'kiro', 'wucur', 'cursor'。"""

    @abstractmethod
    async def register(self, email: str, config: RegistrationConfig, **kwargs) -> RegistrationResult:
        """
        执行单个账号注册。

        Args:
            email: 注册邮箱
            config: 注册配置（代理、超时等）
            **kwargs: provider 特有参数（如 email_client, password 等）

        Returns:
            RegistrationResult

        Raises:
            不抛异常，所有错误通过 RegistrationResult.error 返回。
        """

    def validate_prerequisites(self, **kwargs) -> str | None:
        """
        注册前校验前置条件。

        Returns:
            None 表示通过，否则返回错误信息。
        """
        return None
```

### 2.2 `core/ports/token_service.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod

from core.domain import TokenRefreshResult


class TokenService(ABC):
    """Token 刷新服务接口。"""

    @property
    @abstractmethod
    def auth_method(self) -> str:
        """认证方式标识，如 'oidc', 'social'。"""

    @abstractmethod
    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult:
        """
        刷新 token。

        Args:
            refresh_token: 刷新令牌
            client_id: OIDC 客户端 ID（oidc 方式必填）
            client_secret: OIDC 客户端密钥（oidc 方式必填）
            region: AWS 区域

        Returns:
            TokenRefreshResult
        """
```

### 2.3 `core/ports/browser_automation.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import BrowserContext, Page


class BrowserSession(ABC):
    """浏览器会话抽象，封装 Playwright 生命周期。"""

    @abstractmethod
    async def __aenter__(self) -> "BrowserSession":
        ...

    @abstractmethod
    async def __aexit__(self, *args) -> None:
        ...

    @abstractmethod
    async def new_page(self) -> Page:
        ...

    @abstractmethod
    async def get_cookies(self, url: str = "") -> list[dict[str, Any]]:
        ...


class PageFlow(ABC):
    """页面操作流程抽象（Page Object 模式）。"""

    @abstractmethod
    async def execute(self, page: Page) -> str | None:
        """
        执行页面流程。

        Returns:
            None 表示成功，否则返回 'ERROR:xxx' 错误信息。
        """
```

## 3. 适配器实现 (`adapters/registration/`)

### 3.1 `adapters/registration/base.py`

```python
from playwright.async_api import async_playwright, Page

from core.ports.browser_automation import BrowserSession
from core.ports.registration_service import RegistrationConfig


class PlaywrightSession(BrowserSession):
    """Playwright 浏览器会话实现。"""

    def __init__(self, config: RegistrationConfig):
        self._config = config
        self._playwright = None
        self._browser = None
        self._context = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        launch_opts = {
            "headless": self._config.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self._config.proxy_url:
            launch_opts["proxy"] = {"server": self._config.proxy_url}
        self._browser = await self._playwright.chromium.launch(**launch_opts)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        return await self._context.new_page()

    async def get_cookies(self, url: str = "") -> list[dict]:
        return await self._context.cookies()
```

### 3.2 `adapters/registration/kiro/`

#### `adapters/registration/kiro/__init__.py`

```python
from .service import KiroRegistrationService

__all__ = ["KiroRegistrationService"]
```

#### `adapters/registration/kiro/service.py`

```python
from core.domain import Credentials, RegistrationResult, RegistrationStatus
from core.ports.registration_service import RegistrationConfig, RegistrationService
from adapters.email.base import EmailClient

from .browser_flow import KiroBrowserFlow
from .sso_device_auth import sso_device_auth


class KiroRegistrationService(RegistrationService):
    """Kiro (AWS Builder ID) 注册服务。"""

    def __init__(self, email_client: EmailClient):
        self._email_client = email_client

    @property
    def platform(self) -> str:
        return "kiro"

    def validate_prerequisites(self, **kwargs) -> str | None:
        if not self._email_client:
            return "Email client is required for Kiro registration"
        return None

    async def register(self, email: str, config: RegistrationConfig, **kwargs) -> RegistrationResult:
        # Phase 1: Browser registration → sso_token
        flow = KiroBrowserFlow(
            email=email,
            email_client=self._email_client,
            config=config,
        )
        sso_token = await flow.execute()

        if not sso_token or sso_token.startswith("ERROR:"):
            return RegistrationResult(
                success=False,
                username=email,
                platform=self.platform,
                error=sso_token[6:] if sso_token else "Failed to get SSO Token",
            )

        # Phase 2: SSO Device Auth → refreshToken + accessToken
        auth_result = sso_device_auth(sso_token)

        credentials = Credentials(sso_token=sso_token)
        if auth_result.get("success"):
            credentials.access_token = auth_result["accessToken"]
            credentials.refresh_token = auth_result["refreshToken"]
            credentials.client_id = auth_result["clientId"]
            credentials.client_secret = auth_result["clientSecret"]
            credentials.region = auth_result.get("region", "us-east-1")
            credentials.expires_in = auth_result.get("expiresIn")

        return RegistrationResult(
            success=True,
            username=email,
            password=flow.password,
            platform=self.platform,
            status=RegistrationStatus.SUCCESS,
            name=flow.name,
            credentials=credentials,
            error=auth_result.get("error") if not auth_result.get("success") else None,
        )
```

#### `adapters/registration/kiro/browser_flow.py`

```python
"""Kiro 浏览器注册流程 — Page Object 封装。"""

import random

from playwright.async_api import Page

from adapters.email.base import EmailClient
from adapters.email.code_extractor import poll_verification_code
from adapters.registration.base import PlaywrightSession
from core.ports.registration_service import RegistrationConfig

from .constants import FIRST_NAMES, LAST_NAMES, DEFAULT_PASSWORD
from .device_code import obtain_device_code
from .page_actions import wait_and_fill, wait_and_click_with_retry, detect_flow, find_code_input


class KiroBrowserFlow:
    """封装 Kiro 浏览器注册的完整流程。"""

    def __init__(self, email: str, email_client: EmailClient, config: RegistrationConfig):
        self.email = email
        self.name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        self.password = DEFAULT_PASSWORD
        self._email_client = email_client
        self._config = config

    async def execute(self) -> str | None:
        """执行浏览器注册，返回 sso_token 或 'ERROR:xxx'。"""
        device_code = obtain_device_code()
        if not device_code:
            return "ERROR:Failed to obtain device code"

        register_url = f'https://view.awsapps.com/start/#/device?user_code={device_code["user_code"]}'

        async with PlaywrightSession(self._config) as session:
            page = await session.new_page()
            try:
                await page.goto(register_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(2000)

                # Fill email
                if not await wait_and_fill(page, 'input[placeholder="username@example.com"]', self.email):
                    return "ERROR:Email input not found"
                await page.wait_for_timeout(1000)

                # Click continue
                if not await wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                    return "ERROR:Click first continue failed"
                await page.wait_for_timeout(3000)

                # Detect and handle flow
                flow = await detect_flow(page)
                if flow == "register":
                    err = await self._register_flow(page)
                else:
                    err = await self._login_flow(page, is_verify=(flow == "verify"))

                if err:
                    return err

                # Extract sso_token
                for _ in range(30):
                    cookies = await session.get_cookies()
                    for c in cookies:
                        if c["name"] == "x-amz-sso_authn":
                            return c["value"]
                    await page.wait_for_timeout(1000)

                return "ERROR:Failed to get SSO Token cookie"
            except Exception as e:
                return f"ERROR:{e}"

    async def _register_flow(self, page: Page) -> str | None:
        """新账号注册流程。返回 None 成功，'ERROR:xxx' 失败。"""
        if not await wait_and_fill(page, 'input[placeholder="Maria José Silva"]', self.name):
            return "ERROR:Name input not found"
        await page.wait_for_timeout(1000)

        if not await wait_and_click_with_retry(page, 'button[data-testid="signup-next-button"]'):
            return "ERROR:Click signup next failed"
        await page.wait_for_timeout(3000)

        return await self._verify_code_and_set_password(page, is_register=True)

    async def _login_flow(self, page: Page, *, is_verify: bool = False) -> str | None:
        """已注册账号登录流程。"""
        if not is_verify:
            if not await wait_and_fill(page, 'input[placeholder="Enter password"]', self.password):
                return "ERROR:Login password input not found"
            await page.wait_for_timeout(1000)
            if not await wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                return "ERROR:Click login continue failed"
            await page.wait_for_timeout(3000)

        return await self._verify_code_and_set_password(page, is_register=False)

    async def _verify_code_and_set_password(self, page: Page, *, is_register: bool) -> str | None:
        """获取验证码、填入、设置密码（注册流程）。"""
        code_sel = await find_code_input(page)
        if not code_sel:
            return "ERROR:Verification code input not found"
        await page.wait_for_timeout(1000)

        code = poll_verification_code(self._email_client, timeout=self._config.code_timeout)
        if not code:
            return "ERROR:Failed to get verification code"

        if not await wait_and_fill(page, code_sel, code):
            return "ERROR:Failed to fill verification code"
        await page.wait_for_timeout(1000)

        if is_register:
            if not await wait_and_click_with_retry(page, 'button[data-testid="email-verification-verify-button"]'):
                return "ERROR:Click verify failed"
            await page.wait_for_timeout(3000)

            if not await wait_and_fill(page, 'input[placeholder="Enter password"]', self.password):
                return "ERROR:Password input not found"
            await page.wait_for_timeout(500)
            if not await wait_and_fill(page, 'input[placeholder="Re-enter password"]', self.password):
                return "ERROR:Confirm password input not found"
            await page.wait_for_timeout(1000)

            if not await wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                return "ERROR:Click final continue failed"
        else:
            if not await wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                return "ERROR:Click login verify failed"

        await page.wait_for_timeout(5000)
        return None
```

#### `adapters/registration/kiro/sso_device_auth.py`

```python
"""SSO Device Auth — 用 sso_token 换取 refreshToken + accessToken。

严格移植自 Kiro-auto-register/src/main/index.ts 的 ssoDeviceAuth 函数。
"""

import time
import httpx

OIDC_BASE = "https://oidc.us-east-1.amazonaws.com"
PORTAL_BASE = "https://portal.sso.us-east-1.amazonaws.com"
START_URL = "https://view.awsapps.com/start"
SCOPES = [
    "codewhisperer:analysis",
    "codewhisperer:completions",
    "codewhisperer:conversations",
    "codewhisperer:taskassist",
    "codewhisperer:transformations",
]


def sso_device_auth(bearer_token: str, region: str = "us-east-1") -> dict:
    """完整 7 步 SSO 设备授权流程。返回 dict 含 success, accessToken, refreshToken 等。"""
    # ... 实现同当前 register_kiro_account.py 中的 sso_device_auth 函数
    # 此处省略，逻辑不变
```

#### `adapters/registration/kiro/page_actions.py`

```python
"""Playwright 页面操作原子函数。"""

import asyncio
from playwright.async_api import Page


async def wait_and_fill(page: Page, selector: str, value: str, timeout: int = 30000) -> bool:
    """等待元素出现并填入值。"""
    ...

async def wait_and_click_with_retry(page: Page, selector: str, timeout: int = 30000, max_retries: int = 3) -> bool:
    """点击按钮，检测 AWS 错误弹窗并重试。"""
    ...

async def detect_flow(page: Page) -> str:
    """检测当前是 register/login/verify 流程。"""
    ...

async def find_code_input(page: Page) -> str | None:
    """查找验证码输入框。"""
    ...
```

#### `adapters/registration/kiro/constants.py`

```python
FIRST_NAMES = ["James", "Robert", "John", ...]
LAST_NAMES = ["Smith", "Johnson", "Williams", ...]
DEFAULT_PASSWORD = "admin123456aA!"
```

#### `adapters/registration/kiro/device_code.py`

```python
"""获取 device code 用于构造注册 URL。"""

import httpx
from .constants import SCOPES

def obtain_device_code() -> dict | None:
    """注册 OIDC 客户端并获取 user_code。返回 {'user_code': '...'} 或 None。"""
    ...
```

### 3.3 `adapters/registration/wucur/service.py`

```python
from core.domain import Credentials, RegistrationResult, RegistrationStatus
from core.ports.registration_service import RegistrationConfig, RegistrationService


class WucurRegistrationService(RegistrationService):
    """Wucur 注册服务 — 包装现有 wucur_client。"""

    def __init__(self, http_client):
        self._client = http_client

    @property
    def platform(self) -> str:
        return "wucur"

    async def register(self, email: str, config: RegistrationConfig, **kwargs) -> RegistrationResult:
        password = kwargs.get("password", "")
        # 调用现有 wucur_client.register_account
        result = self._client.register_account(email, password)
        if result.get("success"):
            return RegistrationResult(
                success=True,
                username=email,
                password=password,
                platform=self.platform,
                status=RegistrationStatus.SUCCESS,
            )
        return RegistrationResult(
            success=False,
            username=email,
            platform=self.platform,
            error=result.get("message", "Registration failed"),
        )
```

### 3.4 `adapters/token/oidc_token_service.py`

```python
import httpx
from core.domain import TokenRefreshResult
from core.ports.token_service import TokenService


class OidcTokenService(TokenService):
    """AWS OIDC token 刷新。"""

    @property
    def auth_method(self) -> str:
        return "oidc"

    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult:
        url = f"https://oidc.{region}.amazonaws.com/token"
        payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "refreshToken": refresh_token,
            "grantType": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return TokenRefreshResult(success=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return TokenRefreshResult(
                success=True,
                access_token=data["accessToken"],
                refresh_token=data.get("refreshToken", refresh_token),
                expires_in=data.get("expiresIn"),
            )
```

## 4. Use Case (`core/application/register_account_use_case.py`)

```python
from __future__ import annotations

from core.domain import RegistrationResult
from core.ports.registration_service import RegistrationConfig, RegistrationService


class RegisterAccountUseCase:
    """统一注册编排。不关心具体 provider 实现。"""

    def __init__(self, services: dict[str, RegistrationService]):
        self._services = services

    @property
    def supported_providers(self) -> list[str]:
        return list(self._services.keys())

    async def execute(
        self,
        provider: str,
        email: str,
        config: RegistrationConfig | None = None,
        **kwargs,
    ) -> RegistrationResult:
        service = self._services.get(provider)
        if not service:
            return RegistrationResult(
                success=False,
                username=email,
                platform=provider,
                error=f"Unknown provider: {provider}. Supported: {self.supported_providers}",
            )

        # 前置校验
        err = service.validate_prerequisites(**kwargs)
        if err:
            return RegistrationResult(success=False, username=email, platform=provider, error=err)

        cfg = config or RegistrationConfig()
        return await service.register(email, cfg, **kwargs)
```

## 5. 统一 CLI (`cli/register.py`)

```python
"""统一注册 CLI 入口。"""

import argparse
import asyncio
import json
import sys

from core.application.register_account_use_case import RegisterAccountUseCase
from core.ports.registration_service import RegistrationConfig


def build_services(args) -> dict:
    """根据 CLI 参数构建 provider 服务实例。"""
    services = {}

    # Kiro
    from adapters.registration.kiro import KiroRegistrationService
    from adapters.email import build_email_client
    email_client = build_email_client(args)
    if email_client:
        services["kiro"] = KiroRegistrationService(email_client)

    # Wucur
    from adapters.registration.wucur import WucurRegistrationService
    from adapters.http.wucur_client import WucurHttpClient
    services["wucur"] = WucurRegistrationService(WucurHttpClient())

    return services


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Register account for any provider.")
    parser.add_argument("--provider", required=True, choices=["kiro", "wucur"], help="Provider name")
    parser.add_argument("--email", help="Email address")
    parser.add_argument("--password", help="Password (wucur)")
    parser.add_argument("--proxy", help="Proxy URL")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--code-timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    # Email provider args
    parser.add_argument("--email-provider", choices=["ouraihub", "outlook", "generic"])
    parser.add_argument("--email-api-key")
    parser.add_argument("--email-domain", default="ouraihub.com")
    args = parser.parse_args(argv)

    services = build_services(args)
    use_case = RegisterAccountUseCase(services)
    config = RegistrationConfig(proxy_url=args.proxy, headless=args.headless, code_timeout=args.code_timeout)

    result = await use_case.execute(args.provider, args.email, config, password=args.password)

    if args.json:
        print(json.dumps(result.to_callback_dict(), ensure_ascii=False))

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

## 6. 错误处理策略

| 层级 | 策略 |
|------|------|
| PageFlow | 返回 `"ERROR:xxx"` 字符串，不抛异常 |
| RegistrationService | 捕获所有异常，转为 `RegistrationResult(success=False, error=...)` |
| UseCase | 不捕获异常（由 CLI 层处理） |
| CLI | 顶层 try/except，输出 JSON 错误 |

## 7. 配置注入链路

```
CLI args
  → build_services(args)        # 构建 email_client、http_client
    → KiroRegistrationService(email_client)
    → WucurRegistrationService(http_client)
  → RegisterAccountUseCase(services)
  → use_case.execute(provider, email, config)
    → service.register(email, config)
      → BrowserFlow(config)     # 代理、headless 从 config 传入
      → sso_device_auth(token)  # 无外部依赖
```

## 8. 测试策略

```python
# 单元测试 — mock 浏览器和 HTTP
class FakeBrowserFlow:
    async def execute(self) -> str:
        return "fake_sso_token_xxx"

class FakeSsoDeviceAuth:
    def __call__(self, token: str) -> dict:
        return {"success": True, "accessToken": "at", "refreshToken": "rt", ...}

# 集成测试 — 真实 API，mock 浏览器
async def test_sso_device_auth_with_real_token():
    result = sso_device_auth("real_sso_token_from_fixture")
    assert result["success"]
    assert result["refreshToken"]
```

## 9. 迁移计划

| 步骤 | PR | 说明 | 风险 |
|------|-----|------|------|
| 1 | `feat/registration-ports` | 新增 `core/ports/` 接口文件 | 零风险，纯新增 |
| 2 | `feat/kiro-adapter` | 拆分现有代码到 `adapters/registration/kiro/` | 中风险，需验证功能不变 |
| 3 | `feat/wucur-adapter` | 包装现有 wucur 注册为 adapter | 低风险，包装不改逻辑 |
| 4 | `feat/unified-usecase` | 实现 `RegisterAccountUseCase` + 统一 CLI | 中风险，新入口 |
| 5 | `feat/unified-workflow` | 合并 workflow，用 `--provider` 区分 | 低风险，旧 workflow 保留兼容 |
| 6 | `cleanup/remove-legacy` | 删除旧的独立脚本 | 确认新流程稳定后执行 |

每个 PR 独立可测试，合并后旧代码仍可用，直到 Step 6 清理。

## 评审修正

### 修正 1: RegistrationConfig 增加 max_retries 和 password 生成

```python
class RegistrationConfig:
    """注册配置基类，每个 provider 继承扩展。"""
    def __init__(self, *, proxy_url: str | None = None, headless: bool = True,
                 code_timeout: int = 120, max_retries: int = 2, password: str | None = None):
        self.proxy_url = proxy_url
        self.headless = headless
        self.code_timeout = code_timeout
        self.max_retries = max_retries
        self.password = password or generate_password()  # 不传则自动生成唯一密码
```

### 修正 2: RegisterAccountUseCase 增加重试逻辑

```python
TRANSIENT_ERRORS = ["timeout", "network", "browser crashed", "page closed"]

class RegisterAccountUseCase:
    async def execute(self, email: str, config: RegistrationConfig, **kwargs) -> RegistrationResult:
        last_result = None
        for attempt in range(1 + config.max_retries):
            result = await self._service.register(email, config, **kwargs)
            if result.success:
                return result
            last_result = result
            # 非瞬态错误不重试
            if not any(t in (result.error or "").lower() for t in TRANSIENT_ERRORS):
                break
            if attempt < config.max_retries:
                log.warning("Transient failure, retrying", extra={
                    "attempt": attempt + 1, "error": result.error, "email": email
                })
                await asyncio.sleep(5)
        return last_result
```

### 修正 3: EmailClient.poll_verification_code 增加时间戳过滤

```python
class EmailClient(ABC):
    @abstractmethod
    async def poll_verification_code(
        self, email: str, *, since: float, timeout: int = 120, interval: int = 5
    ) -> str | None:
        """
        轮询验证码邮件。

        Args:
            email: 目标邮箱
            since: Unix 时间戳，只处理此时间之后收到的邮件
            timeout: 最大等待秒数
            interval: 轮询间隔秒数

        Returns:
            验证码字符串，超时返回 None
        """
```

OuraihubEmailClient 实现中增加时间过滤：

```python
async def poll_verification_code(self, email: str, *, since: float, timeout: int = 120, interval: int = 5) -> str | None:
    deadline = time.time() + timeout
    checked_ids = set()
    while time.time() < deadline:
        messages = await self._fetch_messages(email)
        for msg in messages:
            if msg["id"] in checked_ids:
                continue
            checked_ids.add(msg["id"])
            # 时间戳过滤：跳过 since 之前的邮件
            msg_time = parse_timestamp(msg.get("received_at", ""))
            if msg_time and msg_time < since:
                continue
            code = extract_verification_code(msg.get("body", ""), msg.get("subject", ""))
            if code:
                return code
        await asyncio.sleep(interval)
    return None
```

### 修正 4: 浏览器流程增加重发验证码

```python
class KiroBrowserFlow:
    async def _wait_for_verification_code(self, page: Page, email: str) -> str | None:
        """等待验证码，60s 未收到则点重发按钮。"""
        since = time.time()
        code = await self._email_client.poll_verification_code(
            email, since=since, timeout=60, interval=3
        )
        if code:
            return code

        # 尝试点击重发
        resend = page.locator('[data-testid="resend-code"], :text("Resend"), :text("重新发送")')
        if await resend.count() > 0:
            await resend.first.click()
            log.info("Clicked resend code button", extra={"email": email})

        # 重发后再等 60s
        return await self._email_client.poll_verification_code(
            email, since=time.time(), timeout=60, interval=3
        )
```

### 修正 5: register_kiro.yml Workflow 加固

```yaml
jobs:
  register:
    runs-on: windows-2025
    timeout-minutes: 30          # 防止浏览器卡死
    concurrency:
      group: kiro-register       # 同一时间只跑一个注册任务
      cancel-in-progress: false  # 不取消正在运行的
    environment: production
```

回调步骤移除 `echo $output`，改为写文件：

```powershell
# 输出写文件而非 stdout
$output | Out-File -FilePath "artifacts/register_output.json" -Encoding utf8
```

### 修正 6: 密码生成工具函数

```python
# python/src/utils/password.py
import secrets
import string


def generate_password(length: int = 16) -> str:
    """生成符合 AWS Builder ID 密码策略的随机密码。
    
    要求：至少 1 大写、1 小写、1 数字、1 特殊字符，长度 >= 8。
    """
    special = "!@#$&"
    alphabet = string.ascii_letters + string.digits + special
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in special for c in pwd)):
            return pwd
```

### 修正 7: 代理策略文档化

| 场景 | 代理方式 | 说明 |
|------|---------|------|
| 本地批量注册 | `proxy_pool.py` SOCKS5 轮换 | 43+ 节点，每个注册用不同端口 |
| GitHub Actions（当前） | Runner 自带 IP | 每次运行 IP 不同，单次 ≤3 个 |
| GitHub Actions（未来） | 外部代理服务 / self-hosted runner | 需要时接入 |

`RegistrationConfig.proxy_url` 由调用方传入，Use Case 不关心代理来源。批量注册时由外层循环从 `proxy_pool.get_proxies()` 轮换选取。
