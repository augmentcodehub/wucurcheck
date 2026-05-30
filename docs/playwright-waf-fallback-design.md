# 设计：WucurProvider Playwright WAF 降级

> 状态：待实施（当 wucur.com 出现 WAF 拦截时触发）

## 触发条件

wucur API 登录返回以下任一情况：
- HTTP 403
- 响应体包含 WAF 特征（`acw_sc__v2`、验证码页面）
- 连续 3 次登录失败且非密码错误

## 改动范围

### 1. `providers/wucur.py`

```python
class WucurProvider:
    def login(self, client: httpx.Client, username: str, password: str) -> Result:
        result = self._api_login(client, username, password)
        if result.success:
            return result
        if self._is_waf_blocked(result):
            log.warning("WAF detected, fallback to Playwright", extra={"username": username})
            return self._playwright_login(client, username, password)
        return result

    def _is_waf_blocked(self, result: Result) -> bool:
        """判断是否被 WAF 拦截。"""
        if not result.message:
            return False
        return 'HTTP 403' in result.message or 'acw_sc' in result.message

    def _playwright_login(self, client: httpx.Client, username: str, password: str) -> Result:
        """通过 Playwright 获取 WAF cookie，再用 cookie 调 API 登录。"""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{self.domain}{self.login_path}")
            page.wait_for_load_state("networkidle")

            # 提取 WAF cookie
            cookies = page.context.cookies()
            waf_cookies = {c['name']: c['value'] for c in cookies if c['name'] in ('acw_tc', 'acw_sc__v2', 'cdn_sec_tc')}
            browser.close()

        if not waf_cookies:
            return Result.fail("Playwright 未获取到 WAF cookie")

        # 将 WAF cookie 注入 httpx client
        for name, value in waf_cookies.items():
            client.cookies.set(name, value, domain=self.domain.replace("http://", ""))

        # 重试 API 登录
        return self._api_login(client, username, password)

    def _api_login(self, client: httpx.Client, username: str, password: str) -> Result:
        """当前的 login 逻辑重命名为 _api_login。"""
        # ... 现有 login 代码 ...
```

### 2. `checkin_batch.yml` 增加 Playwright

```yaml
    - name: 安装依赖
      run: |
        pip install -e .
        playwright install chromium --with-deps
```

### 3. 运行环境

- 从 `ubuntu-latest` 不变（Playwright 支持 Linux headless）
- 不需要改为 Windows

## 不改动

- `cli/checkin_cmd.py` — 不感知 WAF，只调 pipeline
- `pipelines/checkin.py` — 不感知 WAF，只调 provider.login()
- `results.json` 格式 — 不变
- `checkin.yml`（旧 AnyRouter 流程）— 不动

## 测试

```python
@patch("providers.wucur.sync_playwright")
def test_playwright_fallback_on_403(mock_pw):
    provider = WucurProvider()
    client = httpx.Client()
    # mock API 返回 403
    # mock Playwright 返回 cookie
    # 验证第二次 API 调用带上了 cookie
```

## 依赖

- `playwright` 已在 pyproject.toml 中（现有依赖）
- CI 需要 `playwright install chromium --with-deps`（约 +30s）

## 回退

如果 Playwright 降级也失败，直接返回 `Result.fail()`，不影响其他账号的批量签到。
