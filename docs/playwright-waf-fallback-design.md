# 设计：WucurProvider Playwright WAF 降级

> 状态：待实施（当 wucur.com 出现 WAF 拦截时触发）

## 前置上下文

- 项目根目录：`/home/administrator/workspace/open-source/wucurcheck`
- WucurProvider 位置：`python/src/providers/wucur.py`
- Workflow 位置：`.github/workflows/checkin_batch.yml`
- 现有 `login()` 方法使用 httpx 直接 POST `/api/user/login`
- `playwright` 已在 pyproject.toml dependencies 中

## 触发条件

wucur API 登录返回以下任一情况时启用 Playwright 降级：
- HTTP 403
- 响应体包含 WAF 特征字符串（`acw_sc__v2`、`cdn_sec_tc`）

## 实施步骤

### Step 1：重构 `python/src/providers/wucur.py`

将现有 `login()` 方法重命名为 `_api_login()`，新 `login()` 作为入口增加 WAF 检测和降级逻辑：

```python
def login(self, client: httpx.Client, username: str, password: str) -> Result:
    """登录入口：先尝试 API，被 WAF 拦截时降级到 Playwright。"""
    result = self._api_login(client, username, password)
    if result.success:
        return result
    if self._is_waf_blocked(result):
        log.warning("WAF detected, fallback to Playwright", extra={"username": username})
        return self._playwright_login(client, username, password)
    return result

def _is_waf_blocked(self, result: Result) -> bool:
    """判断失败是否由 WAF 引起。"""
    msg = result.message or ''
    return 'HTTP 403' in msg or 'acw_sc' in msg or 'cdn_sec' in msg

def _playwright_login(self, client: httpx.Client, username: str, password: str) -> Result:
    """通过 Playwright 获取 WAF cookie，注入 client 后重试 API 登录。"""
    from playwright.sync_api import sync_playwright

    waf_cookie_names = ('acw_tc', 'acw_sc__v2', 'cdn_sec_tc')
    login_url = f"{self.domain}{self.login_path}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(login_url, wait_until="networkidle", timeout=30000)
            cookies = page.context.cookies()
            browser.close()
    except Exception as e:
        log.error("Playwright failed", extra={"error": str(e)[:100]})
        return Result.fail(f"Playwright 异常: {str(e)[:80]}")

    waf_cookies = {c['name']: c['value'] for c in cookies if c['name'] in waf_cookie_names}
    if not waf_cookies:
        log.warning("No WAF cookies found", extra={"cookie_names": [c['name'] for c in cookies]})
        return Result.fail("Playwright 未获取到 WAF cookie")

    # 注入 cookie 到 httpx client（domain 不带协议和端口）
    domain_host = self.domain.split("://")[-1].split(":")[0]  # "wucur.com"
    for name, value in waf_cookies.items():
        client.cookies.set(name, value, domain=domain_host)

    log.info("WAF cookies injected, retrying API login", extra={"cookies": list(waf_cookies.keys())})
    return self._api_login(client, username, password)

def _api_login(self, client: httpx.Client, username: str, password: str) -> Result:
    """纯 API 登录（现有 login 代码原样移入此方法）。"""
    headers = build_headers(self.domain, self.login_path)
    resp = client.post(
        f"{self.domain}{self.login_api_path}",
        headers=headers,
        json={"username": username, "password": password},
        timeout=30,
    )
    data = parse_response(resp)
    if resp.status_code != 200 or not data.get("success"):
        msg = data.get("message", f"HTTP {resp.status_code}")
        log.warning("Login failed", extra={"username": username, "reason": msg})
        return Result.fail(msg)
    if "session" not in client.cookies:
        log.warning("Login no session cookie", extra={"username": username})
        return Result.fail("Login succeeded but session cookie not found")
    user_id = str(data.get("data", {}).get("id", ""))
    log.info("Login success", extra={"username": username})
    return Result.ok({"user_id": user_id, "raw": data})
```

**注意：** 现有 `login()` 的完整代码直接移入 `_api_login()`，一字不改。新 `login()` 只是在外面包了一层 WAF 检测。

### Step 2：修改 `.github/workflows/checkin_batch.yml`

在"安装依赖"步骤后增加 Playwright 安装：

```yaml
    - name: 安装依赖
      run: |
        pip install -e .
        playwright install chromium --with-deps
```

### Step 3：增加测试 `python/tests/test_waf_fallback.py`

```python
"""Tests for WucurProvider WAF fallback."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import httpx
from core.result import Result
from providers.wucur import WucurProvider


class TestWafFallback:
    def test_no_fallback_on_success(self):
        provider = WucurProvider()
        with patch.object(provider, '_api_login', return_value=Result.ok({"user_id": "1"})) as mock:
            result = provider.login(MagicMock(), "u", "p")
        assert result.success
        mock.assert_called_once()

    def test_no_fallback_on_password_error(self):
        provider = WucurProvider()
        with patch.object(provider, '_api_login', return_value=Result.fail("密码错误")):
            with patch.object(provider, '_playwright_login') as mock_pw:
                result = provider.login(MagicMock(), "u", "p")
        assert not result.success
        mock_pw.assert_not_called()

    def test_fallback_on_403(self):
        provider = WucurProvider()
        with patch.object(provider, '_api_login', side_effect=[
            Result.fail("HTTP 403"),  # 第一次被 WAF 拦截
            Result.ok({"user_id": "1"}),  # Playwright 注入 cookie 后重试成功
        ]):
            with patch.object(provider, '_playwright_login', wraps=lambda *a: provider._api_login(*a)):
                # 直接 mock _playwright_login 返回成功
                with patch.object(provider, '_playwright_login', return_value=Result.ok({"user_id": "1"})):
                    result = provider.login(MagicMock(), "u", "p")
        assert result.success

    def test_is_waf_blocked(self):
        provider = WucurProvider()
        assert provider._is_waf_blocked(Result.fail("HTTP 403")) is True
        assert provider._is_waf_blocked(Result.fail("acw_sc_v2 required")) is True
        assert provider._is_waf_blocked(Result.fail("密码错误")) is False
        assert provider._is_waf_blocked(Result.fail("")) is False
```

## 不改动

- `cli/checkin_cmd.py` — CLI 层不感知 WAF
- `pipelines/checkin.py` — Pipeline 层不感知 WAF
- `results.json` 格式 — 不变
- `checkin.yml`（AnyRouter 流程）— 不动
- `providers/kiro.py` — 不涉及

## 验收

```bash
# 单元测试
cd /home/administrator/workspace/open-source/wucurcheck
uv run pytest python/tests/test_waf_fallback.py -v --no-cov

# 集成验证（需要 wucur 确实有 WAF 时才能测）
uv run wucur checkin --username test@qq.com --password "123Claude&Codex" --output /tmp/r.json
```

## 回退

如果 Playwright 降级引入问题，只需将 `login()` 改回直接调用 `_api_login()` 即可（一行改动）。
