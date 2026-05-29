# 代码质量重构设计文档

## 背景

代码评审发现生产风险和架构问题。本文档提供精确的修复指令，AI agent 可直接按步骤执行。

---

## Task 1: 修复 check_in_account 返回值不一致

**文件：** `python/src/cli/checkin.py`

**问题：** `check_in_account` 函数有 6 个 return 语句，其中 2 个返回 2-tuple `(False, None)`，其余返回 3-tuple `(bool, x, y)`。调用方 `main()` 解包 3 个值会 crash。

**修复：** 找到所有 `return False, None` 改为 `return False, None, None`。

具体位置（行号可能偏移，按上下文匹配）：

```python
# 位置1: provider_config 不存在时
if not provider_config:
    log.error(...)
    return False, None  # ← 改为 return False, None, None

# 位置2: 无 cookies 且非密码登录时
if not provider_config.uses_bearer_login() and not provider_config.uses_password_session() and not user_cookies:
    log.error(...)
    return False, None  # ← 改为 return False, None, None
```

**验证：** `grep -n "return False, None$" python/src/cli/checkin.py` 应返回 0 结果（所有都应是 `None, None`）。

---

## Task 2: 修复 wucur_client.py 日志字符串未插值

**文件：** `python/src/adapters/http/wucur_client.py`

**问题：** `login_with_bearer_token` 和 `login_with_session` 中的 log 消息是字面量字符串，动态值没有传入。

**修复：** 找到以下 5 处，改为 `extra={}` 传值：

```python
# login_with_bearer_token 中：

# 修复1:
# 旧: log.error('Provider missing login_api_path', extra={'account': account_name, 'provider': provider_config.name})
# ↑ 这个已经是对的，不用改

# 修复2:
# 旧: log.error('Login request failed - str(e)[:50]...', extra={'account': account_name})
# 新:
log.error('Login request failed', extra={'account': account_name, 'error': str(e)[:50]})

# 修复3:
# 旧: log.error('Login failed - HTTP response.status_code', extra={'account': account_name})
# 新:
log.error('Login failed', extra={'account': account_name, 'status': response.status_code})
```

```python
# login_with_session 中：

# 修复4:
# 旧: log.error('Login request failed - str(e)[:50]...', extra={'account': account_name})
# 新:
log.error('Login request failed', extra={'account': account_name, 'error': str(e)[:50]})

# 修复5:
# 旧: log.error('Login failed - HTTP response.status_code', extra={'account': account_name})
# 新:
log.error('Login failed', extra={'account': account_name, 'status': response.status_code})

# 修复6:
# 旧: log.error('Login failed - error_msg', extra={'account': account_name})
# 新:
log.error('Login failed', extra={'account': account_name, 'error_msg': error_msg})
```

**验证：**
```bash
# 以下命令应全部返回 0 结果：
grep -n "str(e)\[:50\]\.\.\." python/src/adapters/http/wucur_client.py
grep -n "HTTP response.status_code" python/src/adapters/http/wucur_client.py
grep -n "Login failed - error_msg" python/src/adapters/http/wucur_client.py
```

---

## Task 3: handleBatchResult 加 per-item try/catch

**文件：** `worker-dashboard/src/handlers/callback.ts`

**问题：** `handleBatchResult` 的 for 循环中，`repo.put()` 或 `repo.get()` 抛异常会中断整个循环。

**当前状态：** 循环内已有日志（之前加的），但没有 try/catch。

**修复：** 用以下代码**替换** `for (const item of items) {` 到其对应 `}` 之间的全部内容（即整个循环体）：

```typescript
for (const item of items) {
  try {
    if (!isObject(item)) continue;
    const username = str(item.username) || str(item.email);
    if (!username) continue;

    const fields = toAccountFields(item);
    fields.username = username;
    if (!fields.status) fields.status = "active";
    if (!fields.last_result) fields.last_result = str(item.error) || str(item.message) || "批量结果更新";

    const existing = await repo.get(username);
    const statusChanged = existing?.status !== fields.status;

    if (statusChanged || fields.status === "failed") {
      log.info("batch_item_update", {
        username,
        old_status: existing?.status || "unknown",
        new_status: fields.status || "unknown",
        last_result: fields.last_result || "",
        has_password: String(!!existing?.password),
      });
    }

    if (fields.status === "active") successCount++;
    else failCount++;

    await repo.put(username, fields);

    if (item.status === "failed") {
      await failLogs.write(username, { date: new Date().toISOString().slice(0, 10), reason: str(item.last_result) || str(item.error) || "未知" });
    }
  } catch (e) {
    const username = isObject(item) ? str(item.username) || str(item.email) || "unknown" : "unknown";
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("batch_item_error", { username, error: msg });
    failCount++;
  }
}
```

**验证：** `npx tsc --noEmit` 编译通过。

---

## Task 4: cron handler 加 try/catch

**文件：** `worker-dashboard/src/index.ts`

**问题：** `scheduled()` 中 `repo.list()` 或 `triggerWorkflow()` 抛异常时无日志。

**当前状态：** cron handler 已有 `cron_skip`/`cron_all_checked`/`cron_checkin_dispatch` 日志和 `DEFAULT_PASSWORD` fallback（之前加的），但没有 try/catch 错误边界。fetch handler 有 try/catch 但 scheduled 没有。

**修复：** 在 `withLogContext` 回调内部，将整个逻辑包裹在 try/catch 中：

```typescript
async scheduled(_event, env, _ctx) {
  return withLogContext({ trigger: "cron", rid: crypto.randomUUID().slice(0, 8) }, async () => {
    try {
      const config = await env.KV.get<number[]>(KV_KEY.CRON_HOUR, "json");
      // ... all existing logic unchanged ...
    } catch (e) {
      const msg = e instanceof Error ? e.message : "unknown";
      log.error("cron_error", { error: msg });
    }
  });
}
```

**验证：** `npx tsc --noEmit` 编译通过。

---

## Task 5: 提取共享签到过滤函数

**新建文件：** `worker-dashboard/src/lib/checkin-helpers.ts`

```typescript
import { DEFAULT_PASSWORD } from "./constants.js";
import { isToday } from "../views/helpers.js";
import type { Account } from "../types/index.js";

export interface UncheckedAccount {
  username: string;
  password: string;
}

export function getUncheckedWucurAccounts(accounts: Account[]): UncheckedAccount[] {
  return accounts
    .filter((a) => a.status === "active" && (!a.platform || a.platform === "wucur") && !isToday(a.checkin_time))
    .map((a) => ({ username: a.username, password: a.password || DEFAULT_PASSWORD }));
}
```

**修改 `index.ts`：**
- 添加 `import { getUncheckedWucurAccounts } from "./lib/checkin-helpers.js";`
- 当前 import 是 `import { KV_KEY, DEFAULT_PASSWORD } from "./lib/constants.js";`，改为 `import { KV_KEY } from "./lib/constants.js";`（移除 `DEFAULT_PASSWORD`，不再直接使用）
- 将 `.filter(...).map(...)` 那段替换为 `const unchecked = getUncheckedWucurAccounts(accounts);`

**修改 `handlers/actions.ts`：**
- 添加 `import { getUncheckedWucurAccounts } from "../lib/checkin-helpers.js";`
- 删除 `const wucurActive = accounts.filter(...)` 那行
- 删除 `const unchecked = wucurActive.filter(...).map(...)` 那段
- 替换为 `const unchecked = getUncheckedWucurAccounts(accounts);`
- 保留 `usingDefault` 计算逻辑（用于日志），它需要原始 `accounts` 列表来检查 password 是否存在：
  ```typescript
  const usingDefault = unchecked.filter((a) => !accounts.find((x) => x.username === a.username)?.password);
  ```

**注意：** 两个文件当前已经各自 import 了 `DEFAULT_PASSWORD` 并内联了相同的过滤逻辑。提取后只需改调用方式。

**验证：** `npx tsc --noEmit` 编译通过。

---

## Task 6: cli/checkin.py 消除重复代码

**文件：** `python/src/cli/checkin.py`

**前置条件：** Task 1 + Task 2 已完成。

**步骤：**

1. 在文件顶部添加导入：
```python
from adapters.http.wucur_client import (
    build_login_payload,
    extract_token_from_login_response,
    extract_login_user_id,
    login_with_bearer_token,
    login_with_session,
    get_user_info,
)
```

2. 删除 `cli/checkin.py` 中以下函数定义（约 120 行）：
   - `build_login_payload`（约第 82-87 行）
   - `extract_token_from_login_response`（约第 90-112 行）
   - `extract_login_user_id`（约第 115-135 行）
   - `get_user_info`（约第 138-160 行）
   - `login_with_bearer_token`（约第 163-195 行）
   - `login_with_session`（约第 198-240 行）

   **保留不删的函数（cli 独有逻辑）：**
   - `load_balance_hash` / `save_balance_hash` / `generate_balance_hash`
   - `parse_cookies`
   - `get_waf_cookies_with_playwright`
   - `prepare_cookies`
   - `execute_check_in`
   - `format_check_in_notification`
   - `check_in_account`
   - `main` / `run_main`

3. 确认 `check_in_account` 中对这些函数的调用不需要修改（函数签名一致）。

**注意事项：**
- `cli/checkin.py` 的 `get_user_info` 签名是 `(client, headers, user_info_url: str)` 无类型注解；`wucur_client.py` 的是 `(client: httpx.Client, headers: dict, user_info_url: str) -> dict`。行为一致，可以直接替换。
- `wucur_client.py` 额外有 `extract_login_user_id_from_payload` 辅助函数，cli 不需要它，不影响导入。
- `cli/checkin.py` 中 `login_with_bearer_token` 和 `login_with_session` 与 wucur_client.py 版本签名完全相同：`(client, account_name, provider_config, account)`。Task 2 修复后两者行为一致。

**验证：**
```bash
uv run python -c "from cli.checkin import run_main; print('import ok')"
uv run pytest python/tests/test_wucur_client.py -x
```

---

## Task 7: Account.password 改为 optional

**文件：** `worker-dashboard/src/types/account.ts`

**修改：**
```typescript
// 旧:
password: string;
// 新:
password?: string;
```

**文件：** `worker-dashboard/src/lib/constants.ts`

保持 `DEFAULT_PASSWORD` 不变。后续如需改密码，改这里即可。

**编译后处理：** 运行 `npx tsc --noEmit`，如果有编译错误（某处假设 password 一定存在），在该处加 `|| ""` 或 `?.` 处理。

预期需要修改的位置：
- `handlers/accounts.ts` 的 `apiExportCsv` 中 `a.password` → `a.password || ""`
- `handlers/callback.ts` 的 `STRING_FIELDS` 已包含 `"password"`，`toAccountFields` 会正确处理 optional

**验证：** `npx tsc --noEmit` 编译通过。

---

## Task 8: 提取 Python 常量

**新建文件：** `python/src/utils/constants.py`

```python
"""共享常量 — 消除魔法数字和重复字符串。"""

QUOTA_UNIT_DIVISOR = 500_000
"""wucur API 返回的 quota 原始值除以此数得到美元金额。"""

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

def build_standard_headers(origin: str, referer: str) -> dict[str, str]:
    """构建标准请求头。"""
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": origin,
        "Referer": referer,
    }
```

**修改 `adapters/http/wucur_client.py`：**
```python
from utils.constants import QUOTA_UNIT_DIVISOR, DEFAULT_USER_AGENT, build_standard_headers
```
- 替换 4 处 `/ 500000` 为 `/ QUOTA_UNIT_DIVISOR`
- 现有 `build_headers(referer_path, base_url=BASE_URL)` 函数改为调用 `build_standard_headers`：
  ```python
  def build_headers(referer_path: str, base_url: str = BASE_URL) -> dict[str, str]:
      return build_standard_headers(origin=base_url, referer=f'{base_url}{referer_path}')
  ```
- 删除函数体中内联的 UA 字符串（已移入 `build_standard_headers`）

**修改 `scripts/checkin_batch.py`：**
```python
from utils.constants import QUOTA_UNIT_DIVISOR
```
- 替换 1 处 `/ 500000` 为 `/ QUOTA_UNIT_DIVISOR`（在 `format_quota_awarded` 函数中）

**修改 `tools/register/register_one_account_to_db.py`：**
```python
from utils.constants import QUOTA_UNIT_DIVISOR
```
- 替换 2 处 `/ 500000` 为 `/ QUOTA_UNIT_DIVISOR`

**修改 `cli/checkin.py`（Task 6 之后剩余的代码）：**
```python
from utils.constants import DEFAULT_USER_AGENT
```
- 替换 headers dict 中的 UA 字符串为 `DEFAULT_USER_AGENT`
- 注意：Task 6 已删除 `get_user_info`，所以 cli/checkin.py 中不再有 `500000`
- 注意：`cli/checkin.py` 中的 headers 比 `build_standard_headers` 多几个字段（Accept-Language、Sec-Fetch-* 等），所以不能直接调用 `build_standard_headers`，只替换 UA 常量即可

**验证：**
```bash
grep -rn "500000" python/src/ --include="*.py" | grep -v constants.py | grep -v __pycache__ | grep -v tests/
# 应返回 0 结果

grep -rn "Chrome/138" python/src/ --include="*.py" | grep -v constants.py | grep -v __pycache__
# 应返回 0 结果
```

---

## 执行顺序

```
1. Task 2 (修复日志插值)
2. Task 1 (修复返回值)
3. Task 3 (batch try/catch)
4. Task 4 (cron try/catch)
5. Task 5 (提取 TS 共享函数)
6. Task 6 (消除 Python 重复)
7. Task 8 (提取 Python 常量)
8. Task 7 (password optional)
9. Task 9 (验证 + 提交)
```

## 最终验证

```bash
# Python
cd /home/administrator/workspace/open-source/wucurcheck
uv run pytest python/tests/ -x
uv run python -m py_compile python/src/cli/checkin.py
uv run python -m py_compile python/src/adapters/http/wucur_client.py
uv run python -m py_compile python/src/scripts/checkin_batch.py

# TypeScript
cd worker-dashboard
npx tsc --noEmit

# 部署（确认无误后）
npx wrangler deploy
```

## 提交规范

```bash
git add -A
git commit -m "refactor: fix production bugs + eliminate code duplication

- fix: check_in_account return tuple consistency (P0)
- fix: wucur_client log string interpolation (P0)
- fix: handleBatchResult per-item error boundary (P0)
- fix: cron handler error boundary (P0)
- refactor: extract getUncheckedWucurAccounts shared helper
- refactor: cli/checkin.py imports from wucur_client (dedup ~120 lines)
- refactor: Account.password optional, matches runtime
- refactor: extract QUOTA_UNIT_DIVISOR, DEFAULT_USER_AGENT constants"
```
