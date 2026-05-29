# 重构回退与修复指南

> 适用于 commit `9d4c803`（merge into main）之后出现的 CI 问题。

## 快速回退

如果需要完全回退本次重构：

```bash
git revert HEAD  # 回退 merge commit
```

## 按模块回退

### register.yml 注册失败

**症状**: Worker 触发「批量注册」后 workflow 报错。

**原因**: `cli/register.py` 的新参数或 `_resolve_email` 逻辑有问题。

**修复**: 将 register.yml 的注册步骤改回调老脚本：

```yaml
    - name: 注册账号
      id: register
      env:
        PROVIDERS: ${{ secrets.PROVIDERS }}
      run: |
        New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null
        uv run python python/src/tools/account_generation/gen_natural_accounts.py ${{ inputs.count }} "${{ inputs.email_domain }}" "${{ inputs.password }}" "${{ inputs.email_prefix }}" | Out-File -FilePath artifacts/generated_accounts.json -Encoding utf8
        $accounts = Get-Content artifacts/generated_accounts.json | ConvertFrom-Json
        $results = @()
        foreach ($account in $accounts) {
          $accountJson = $account | ConvertTo-Json -Compress
          $exitCode = 0
          try {
            uv run python python/src/cli/register_wucur.py --username $account.username --password $account.password --json
            $exitCode = $LASTEXITCODE
          } catch { $exitCode = 1 }
          $results += @{
            username = $account.username
            password = $account.password
            platform = "wucur"
            status = if ($exitCode -eq 0) { "active" } else { "failed" }
            last_result = if ($exitCode -eq 0) { "注册成功" } else { "注册失败" }
          }
          Start-Sleep -Seconds 10
        }
        $results | ConvertTo-Json -Depth 3 | Out-File -FilePath artifacts/register_results.json -Encoding utf8
```

**注意**: `cli/register_wucur.py` 仍然存在（标记 deprecated 但未删除），可以直接调用。

---

### register_kiro.yml 注册失败

**症状**: Worker 触发「注册 Kiro」后 workflow 报错。

**修复**: 将 register_kiro.yml 的注册步骤改回调老脚本：

```yaml
    - name: 批量注册 Kiro 账号
      id: register
      env:
        EMAIL_API_KEY: ${{ secrets.OURAIHUB_EMAIL_API_KEY }}
      run: |
        New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null
        $count = [int]"${{ inputs.count }}"
        $results = @()
        for ($i = 0; $i -lt $count; $i++) {
          $args = @(
            "python/src/cli/register_kiro.py",
            "--email-provider", "${{ inputs.email_provider }}",
            "--email-api-key", $env:EMAIL_API_KEY,
            "--email-domain", "${{ inputs.email_domain }}",
            "--code-timeout", "180",
            "--json"
          )
          $proxy = "${{ inputs.proxy }}"
          if ($proxy) { $args += @("--proxy", $proxy) }
          $output = uv run python @args 2>&1 | Out-String
          try {
            $result = $output.Trim().Split("`n") | Where-Object { $_.StartsWith("{") } | Select-Object -Last 1 | ConvertFrom-Json
            $results += @{
              username = $result.email
              password = $result.password
              platform = "kiro"
              status = if ($result.success) { "active" } else { "failed" }
              last_result = if ($result.success) { "注册成功" } else { "注册失败: $($result.error)" }
              name = $result.name
              sso_token = $result.sso_token
              access_token = $result.access_token
              refresh_token = $result.refresh_token
              client_id = $result.client_id
              client_secret = $result.client_secret
              region = $result.region
              expires_in = $result.expires_in
            }
          } catch {
            $results += @{ username = "unknown"; platform = "kiro"; status = "failed"; last_result = "输出解析失败" }
          }
          if ($i -lt $count - 1) { Start-Sleep -Seconds 15 }
        }
        $results | ConvertTo-Json -Depth 3 -AsArray | Out-File -FilePath artifacts/kiro_register_results.json -Encoding utf8
```

**注意**: `cli/register_kiro.py` 仍然存在（标记 deprecated 但未删除）。

---

### checkin.yml 签到失败（ImportError）

**症状**: 定时签到报 `ModuleNotFoundError: No module named 'lib.balance_tracker'` 或 `lib.notify_formatter`。

**原因**: `cli/checkin.py` 的 import 路径问题。

**修复**: 将 `cli/checkin.py` 顶部的两行 import 替换回内联函数。从 git 历史恢复：

```bash
# 查看原来的函数定义
git show HEAD~1:python/src/cli/checkin.py | grep -A 30 "def load_balance_hash"
git show HEAD~1:python/src/cli/checkin.py | grep -A 50 "def format_check_in_notification"
```

然后：
1. 删除 `from lib.balance_tracker import ...` 和 `from lib.notify_formatter import ...`
2. 恢复 `BALANCE_HASH_FILE = 'balance_hash.txt'`
3. 恢复 `load_balance_hash`、`save_balance_hash`、`generate_balance_hash` 三个函数
4. 恢复 `format_check_in_notification` 函数

---

## 文件对照表

| 新路径 | 原路径/来源 | 说明 |
|--------|-------------|------|
| `lib/notify_formatter.py` | 从 `cli/checkin.py` 提取 | 可删除，把函数放回 checkin.py |
| `lib/balance_tracker.py` | 从 `cli/checkin.py` 提取 | 可删除，把函数放回 checkin.py |
| `cli/register.py`（新 _run） | 替换了原 _run | 原版：`git show HEAD~1:python/src/cli/register.py` |
| `cli/register_kiro.py` | 未删除，标记 deprecated | 可直接调用 |
| `cli/register_wucur.py` | 未删除，标记 deprecated | 可直接调用 |
| `tools/register/register_one_account.py` | 已删除 | 恢复：`git checkout HEAD~1 -- python/src/tools/register/register_one_account.py` |
