# 重构执行设计文档

> 目标：完成 god module 拆分 + 注册入口统一。本文档供 AI agent 直接按步骤执行。

## 现状总结

### 签到模块

- `cli/checkin.py`（663 行）是 god module，混合了：余额 hash、cookie 解析、bearer 登录、session 登录、WAF 绕过(Playwright)、签到执行、通知格式化、主流程编排
- `scripts/checkin_batch.py` 是新入口，使用 Pipeline+Provider 模式
- `pipelines/checkin.py` 实现 login → checkin → get_balance
- `providers/wucur.py` 实现 WucurProvider（仅 session 登录）
- `checkin.yml` 调老的 `cli/checkin.py`，`checkin_batch.yml` 调新的 `scripts/checkin_batch.py`

### 注册模块

- `cli/register.py` 已是统一入口（RegisterAccountUseCase + RegistrationService 接口）
- `cli/register_kiro.py` 独立脚本，直接调 `tools/register/register_kiro_account.py`
- `cli/register_wucur.py` 独立脚本，使用 RegisterAndCheckinAccountUseCase
- `tools/register/register_one_account.py` 是 subprocess 包装层
- `register.yml` → `tools/register/register_one_account.py` → subprocess → `cli/register_wucur.py`
- `register_kiro.yml` → `cli/register_kiro.py`
- `register_kiro_api.yml` → `node-register/`（不涉及本次重构）

---

## Phase A: 注册入口统一

### A1. 增强 `cli/register.py`

**文件**: `python/src/cli/register.py`

**需要新增的能力**:

1. `--count N` 参数：循环注册 N 个账号
2. `--output FILE` 参数：将结果写入 JSON 文件
3. `--checkin` 参数：wucur 注册成功后自动签到（替代 register_and_checkin_account_use_case）
4. `--email-prefix` 参数：传给账号生成逻辑

**修改 `_run` 函数逻辑**（完全替换现有 `_run` 函数）:

```python
async def _run(args) -> int:
    services = _build_services(args)
    use_case = RegisterAccountUseCase(services)
    config = RegistrationConfig(
        proxy_url=args.proxy,
        headless=args.headless,
        code_timeout=args.code_timeout,
        max_retries=args.max_retries,
        password=args.password,
    )

    results = []
    count = args.count or 1

    # kiro 批量注册涉及 email client 状态管理，本次只支持 wucur 批量
    if args.provider == "kiro" and count > 1:
        log.warning("Kiro batch registration not yet supported, registering 1 account")
        count = 1

    for i in range(count):
        # 生成 email（每次不同）
        email = _resolve_email(args, i)
        if not email:
            log.error("Failed to resolve email for iteration %d", i)
            results.append(RegistrationResult(success=False, platform=args.provider, error="email resolution failed"))
            continue

        result = await use_case.execute(args.provider, email, config, password=args.password)
        results.append(result)
        _output_result(result, json_mode=args.json)

        # 注册后签到（仅 wucur）
        if args.checkin and result.success and args.provider == "wucur":
            _do_post_register_checkin(result)

        # 间隔
        if i < count - 1:
            await asyncio.sleep(15)

    # 写结果文件
    if args.output:
        _write_results(results, Path(args.output))

    return 0 if any(r.success for r in results) else 1
```

**新增 `_resolve_email` 函数**:

```python
def _resolve_email(args, iteration: int) -> str | None:
    """为每次注册生成/获取 email 地址。"""
    if args.provider == "kiro":
        # kiro 保持现有行为：调 _build_email_client 获取地址
        # 注意：kiro 目前只支持 count=1（_run 中已限制）
        _, email = _build_email_client(args)
        return email
    elif args.provider == "wucur":
        if args.email:
            # 如果指定了 email，第一个用原始值，后续加序号
            if iteration == 0:
                return args.email
            base, domain = args.email.split("@")
            return f"{base}{iteration}@{domain}"
        # 用 gen_natural_accounts 的 generate 函数生成
        from tools.account_generation.gen_natural_accounts import generate
        accounts = generate(1, args.email_domain or "qq.com", args.password or "123Claude&Codex", args.email_prefix or "fruit+animal")
        return accounts[0]["username"] if accounts else None
    return args.email
```

**新增 `_do_post_register_checkin` 函数**:

```python
def _do_post_register_checkin(result: RegistrationResult) -> None:
    """注册成功后执行签到。"""
    from pipelines.checkin import CheckinPipeline
    pipeline = CheckinPipeline()
    checkin_result = pipeline.execute(result.username, result.password)
    if checkin_result.success:
        log.info("Post-register checkin OK", extra={"username": result.username})
    else:
        log.warning("Post-register checkin failed", extra={"username": result.username, "msg": checkin_result.message})
```

**新增 `_write_results` 函数**:

```python
def _write_results(results: list[RegistrationResult], path: Path) -> None:
    """写结果到 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [r.to_callback_dict() for r in results]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Results written", extra={"path": str(path), "count": len(data)})
```

**新增 argparse 参数**（在现有 parser 中添加）:

```python
parser.add_argument("--count", type=int, default=1, help="Number of accounts to register")
parser.add_argument("--output", help="Output JSON file path")
parser.add_argument("--checkin", action="store_true", help="Auto checkin after wucur registration")
parser.add_argument("--email-prefix", default="fruit+animal", help="Email prefix pattern for generation")
# 注意：--email-domain 已存在（default="ouraihub.com"），无需新增
```

### A2. 修改 `register.yml`

**文件**: `.github/workflows/register.yml`

**替换「生成并注册账号」步骤**（注意：此 workflow 跑在 `windows-2025`，shell 是 PowerShell）:

将原来的生成账号 + 逐个调 `register_one_account.py` 的循环，改为：
```powershell
- name: 注册账号
  id: register
  env:
    PROVIDERS: ${{ secrets.PROVIDERS }}
  run: |
    New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null
    $args = @(
      "python/src/cli/register.py",
      "--provider", "wucur",
      "--count", "${{ inputs.count }}",
      "--email-domain", "${{ inputs.email_domain }}",
      "--email-prefix", "${{ inputs.email_prefix }}",
      "--password", "${{ inputs.password }}",
      "--checkin",
      "--output", "artifacts/register_results.json",
      "--json"
    )
    uv run python @args
```

### A3. 修改 `register_kiro.yml`

**文件**: `.github/workflows/register_kiro.yml`

**替换「批量注册 Kiro 账号」步骤**（保留 `env` 中的 `EMAIL_API_KEY`）:

将原来的 for 循环调 `cli/register_kiro.py` 改为：
```yaml
    - name: 批量注册 Kiro 账号
      id: register
      env:
        EMAIL_API_KEY: ${{ secrets.OURAIHUB_EMAIL_API_KEY }}
      run: |
        New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null
        $args = @(
          "python/src/cli/register.py",
          "--provider", "kiro",
          "--count", "${{ inputs.count }}",
          "--email-provider", "${{ inputs.email_provider }}",
          "--email-api-key", $env:EMAIL_API_KEY,
          "--email-domain", "${{ inputs.email_domain }}",
          "--code-timeout", "180",
          "--output", "artifacts/kiro_register_results.json",
          "--json"
        )
        $proxy = "${{ inputs.proxy }}"
        if ($proxy) { $args += @("--proxy", $proxy) }
        uv run python @args
```

**同时删除原来的「上传结果」步骤中的文件名判断**（如果有），确保 `artifacts/kiro_register_results.json` 路径和回调步骤中读取的路径一致。回调步骤保持不变（它已经读 `artifacts/kiro_register_results.json`）。

### A4. 清理废弃文件

执行完 A1-A3 并验证通过后：

1. **删除** `python/src/tools/register/register_one_account.py`
2. **在文件顶部添加 deprecated 注释**:
   - `python/src/cli/register_kiro.py` → `# DEPRECATED: Use cli/register.py --provider kiro`
   - `python/src/cli/register_wucur.py` → `# DEPRECATED: Use cli/register.py --provider wucur`
3. **删除** `python/src/core/application/register_and_checkin_account_use_case.py`
4. **删除** 对应测试 `python/tests/test_register_and_checkin_account_use_case.py`

---

## Phase B: 签到 God Module 渐进式拆分

> **约束**: `cli/checkin.py` 必须保留 Playwright WAF 绕过能力。anyrouter 的风控需要真实浏览器获取 cookie（`acw_tc`、`cdn_sec_tc`、`acw_sc__v2`），纯 HTTP 请求无法绕过。因此不能将 `cli/checkin.py` 完全重写为纯 Pipeline 模式。
>
> **策略**: 提取独立关注点到 lib 模块，`cli/checkin.py` 保留主流程但改为调用提取出的函数。目标从 663 行缩减到 ~400 行。
>
> **`checkin.yml` 不做任何改动**，继续保留 Playwright 安装步骤。

### B1. 新建 `lib/notify_formatter.py`

**文件**: `python/src/lib/notify_formatter.py`

从 `cli/checkin.py` **剪切** `format_check_in_notification` 函数（搜索 `def format_check_in_notification`）。

另外新增 `format_batch_summary` 辅助函数（这是新写的，`cli/checkin.py` 当前不调用它，供 `scripts/checkin_batch.py` 未来使用）：

```python
"""签到通知格式化。"""
from datetime import datetime


def format_check_in_notification(detail: dict) -> str:
    """格式化单个账号的签到通知消息。

    Args:
        detail: 包含以下 key 的字典:
            - name: str
            - before_quota: float
            - before_used: float
            - after_quota: float
            - after_used: float
            - check_in_reward: float
            - usage_increase: float
            - balance_change: float
    """
    lines = [
        f'[CHECK-IN] {detail["name"]}',
        '  ━━━━━━━━━━━━━━━━━━━━',
        '  📍 签到前',
        f'     💵 余额: ${detail["before_quota"]:.2f}  |  📊 累计消耗: ${detail["before_used"]:.2f}',
        '  📍 签到后',
        f'     💵 余额: ${detail["after_quota"]:.2f}  |  📊 累计消耗: ${detail["after_used"]:.2f}',
    ]

    has_reward = detail['check_in_reward'] != 0
    has_usage = detail['usage_increase'] != 0

    if has_reward or has_usage:
        lines.append('  ━━━━━━━━━━━━━━━━━━━━')
        if not has_reward and has_usage:
            lines.append('  ℹ️  今日已签到（期间有使用）')
        if has_reward:
            lines.append(f'  🎁 签到获得: +${detail["check_in_reward"]:.2f}')
        if has_usage:
            lines.append(f'  📉 期间消耗: ${detail["usage_increase"]:.2f}')
        if detail['balance_change'] != 0:
            change_symbol = '+' if detail['balance_change'] > 0 else ''
            change_emoji = '📈' if detail['balance_change'] > 0 else '📉'
            lines.append(f'  {change_emoji} 余额变化: {change_symbol}${detail["balance_change"]:.2f}')
    else:
        lines.extend(['  ━━━━━━━━━━━━━━━━━━━━', '  ℹ️  今日已签到，无变化'])

    return '\n'.join(lines)


def format_batch_summary(success_count: int, total_count: int) -> str:
    """格式化批量签到汇总（新增辅助函数，cli/checkin.py 当前不调用）。"""
    lines = [
        '[STATS] Check-in result statistics:',
        f'[SUCCESS] Success: {success_count}/{total_count}',
        f'[FAIL] Failed: {total_count - success_count}/{total_count}',
    ]
    if success_count == total_count:
        lines.append('[SUCCESS] All accounts check-in successful!')
    elif success_count > 0:
        lines.append('[WARN] Some accounts check-in successful')
    else:
        lines.append('[ERROR] All accounts check-in failed')

    time_info = f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    return '\n'.join([time_info] + lines)
```

### B2. 新建 `lib/balance_tracker.py`

**文件**: `python/src/lib/balance_tracker.py`

从 `cli/checkin.py` **剪切**以下三个函数（搜索 `def load_balance_hash`、`def save_balance_hash`、`def generate_balance_hash`）：

```python
"""余额变化追踪 — 通过 hash 比较判断是否需要发通知。"""
import hashlib
import json
import os

from utils.logger import get_logger

log = get_logger("lib.balance_tracker")

BALANCE_HASH_FILE = "balance_hash.txt"


def load_balance_hash() -> str | None:
    try:
        if os.path.exists(BALANCE_HASH_FILE):
            with open(BALANCE_HASH_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def save_balance_hash(balance_hash: str) -> None:
    try:
        with open(BALANCE_HASH_FILE, "w", encoding="utf-8") as f:
            f.write(balance_hash)
    except Exception as e:
        log.warning("Failed to save balance hash", extra={"error": str(e)})


def generate_balance_hash(balances: dict[str, dict]) -> str | None:
    """生成余额数据的 hash。balances 格式: {key: {"quota": float, "used": float}}"""
    if not balances:
        return None
    simple = {k: v["quota"] for k, v in balances.items()}
    balance_json = json.dumps(simple, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(balance_json.encode("utf-8")).hexdigest()[:16]


def has_balance_changed(current_balances: dict[str, dict]) -> bool:
    """比较当前余额和上次保存的 hash，返回是否有变化。同时保存新 hash。"""
    current_hash = generate_balance_hash(current_balances)
    if not current_hash:
        return False
    last_hash = load_balance_hash()
    changed = last_hash is None or current_hash != last_hash
    save_balance_hash(current_hash)
    return changed
```

### B3. 修改 `cli/checkin.py` — 替换为 import 调用

**文件**: `python/src/cli/checkin.py`

**不重写主流程**，只做以下替换：

1. 删除 `def load_balance_hash`、`def save_balance_hash`、`def generate_balance_hash` 三个函数定义及其函数体，在文件顶部 import 区域添加：
```python
from lib.balance_tracker import load_balance_hash, save_balance_hash, generate_balance_hash
```

2. 删除 `def format_check_in_notification` 函数定义及其完整函数体，在文件顶部 import 区域添加：
```python
from lib.notify_formatter import format_check_in_notification
```

3. 删除 `BALANCE_HASH_FILE = 'balance_hash.txt'` 常量（已移到 lib 中）。

**其余代码（WAF 绕过、登录、签到、main 编排）全部保留不动。**

### B4. 不改动 `checkin.yml` 和 `pipelines/checkin.py`

**`checkin.yml` 保持原样**：
- 继续安装 Playwright（anyrouter WAF 绕过需要）
- 继续调 `uv run checkin.py` → `cli/checkin.py`
- `cli/checkin.py` 保留完整的 WAF 绕过 + bearer 登录 + session 登录逻辑

---

## Phase C: 验证

### C1. 单元测试

**需要新增的测试**:

1. `tests/test_notify_formatter.py` — 测试 `format_check_in_notification` 和 `format_batch_summary`
2. `tests/test_balance_tracker.py` — 测试 hash 生成和变化检测

**需要确认不破坏的测试**:

- `tests/test_checkin_batch.py` — `pipelines/checkin.py` 未改动，不受影响

**需要删除的测试**:

- `tests/test_register_and_checkin_account_use_case.py`（对应 UseCase 已删除）

### C2. 集成验证

```bash
# 1. 运行全部测试
cd /home/administrator/workspace/open-source/wucurcheck
uv run pytest python/tests/ -v

# 2. 验证 cli/register.py 新参数可以正常解析
uv run python python/src/cli/register.py --help

# 3. 验证 cli/checkin.py import 不报错（会因为没有 ANYROUTER_ACCOUNTS 而退出 1，但不应有 ImportError）
ANYROUTER_ACCOUNTS='[]' uv run python python/src/cli/checkin.py; echo "exit: $?"

# 4. 验证 checkin_batch.py 仍然正常
echo '[]' > artifacts/checkin_accounts.json
uv run python python/src/scripts/checkin_batch.py
```

### C3. Lint 检查

```bash
uv run ruff check python/src/
uv run mypy python/src/ --ignore-missing-imports
```

---

## 执行顺序

```
Step 1: Phase A1 — 增强 cli/register.py（新增参数和函数）
Step 2: Phase A2 — 修改 register.yml（注意 PowerShell 语法）
Step 3: Phase A3 — 修改 register_kiro.yml
Step 4: Phase C2 — 验证注册模块
Step 5: Phase B1 — 新建 lib/notify_formatter.py
Step 6: Phase B2 — 新建 lib/balance_tracker.py
Step 7: Phase B3 — 修改 cli/checkin.py（删除已提取的函数，改为 import）
Step 8: Phase C1 + C2 + C3 — 运行测试和 lint
Step 9: Phase A4 — 清理废弃文件（确认一切正常后）
```

---

## 风险和回退

| 风险 | 缓解 |
|------|------|
| register.yml 改动后注册失败 | 回退：workflow 改回调老脚本即可，老脚本标记 deprecated 但不删除 |
| `cli/checkin.py` 提取函数后 import 出错 | 提取是纯机械操作（剪切函数 → 新文件 → 加 import），风险极低。验证：`ANYROUTER_ACCOUNTS='[]' uv run python python/src/cli/checkin.py` |
| `_resolve_email` 调用 `gen_natural_accounts` | 调 `generate(1, domain, password, combo)[0]["username"]`，函数签名已确认 |

---

## 重要约束

1. **`checkin.yml` 不做任何改动** — Playwright 安装必须保留，anyrouter WAF 绕过需要真实浏览器
2. **`cli/checkin.py` 不完全重写** — 只提取独立函数到 lib，主流程（WAF 绕过、多种登录模式）保留
3. **`register_kiro_api.yml` 不动** — Node.js 纯 API 方案独立运行
4. **PowerShell 语法** — `register.yml` 和 `register_kiro.yml` 跑在 `windows-2025`，命令必须用 PowerShell 语法
5. **kiro 批量注册不支持** — `--count > 1` 仅对 wucur 生效。kiro 的 email client 有状态（create_email 绑定 email_id），批量需要额外设计，本次不做
6. **`pipelines/checkin.py` 不改动** — 保持现有行为，不新增功能

---

## 文件变更清单

### 新建

- `python/src/lib/notify_formatter.py`
- `python/src/lib/balance_tracker.py`
- `python/tests/test_notify_formatter.py`
- `python/tests/test_balance_tracker.py`

### 修改

- `python/src/cli/checkin.py`（删除已提取的函数，加 import，~663 行 → ~580 行）
- `python/src/cli/register.py`（新增 --count/--output/--checkin 参数）
- `.github/workflows/register.yml`（改调 cli/register.py，PowerShell 语法）
- `.github/workflows/register_kiro.yml`（改调 cli/register.py，PowerShell 语法）

### 删除

- `python/src/tools/register/register_one_account.py`
- `python/src/core/application/register_and_checkin_account_use_case.py`
- `python/tests/test_register_and_checkin_account_use_case.py`

### 标记 Deprecated

- `python/src/cli/register_kiro.py`
- `python/src/cli/register_wucur.py`
