# 日志与异常规范

## 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 不可恢复的错误，需要人工介入 | 网络超时、未知异常、数据丢失 |
| WARNING | 可恢复的失败，系统继续运行 | 登录失败、签到失败、余额获取失败 |
| INFO | 关键业务节点，正常流程 | 开始处理、登录成功、签到完成、批量结束 |

## 日志格式

使用结构化 JSON 日志，通过 `extra={}` 传递上下文字段：

```python
from utils.logger import get_logger
log = get_logger("module.name")

# ✅ 正确
log.info("Login success", extra={"username": username})
log.warning("Login failed", extra={"username": username, "reason": msg})
log.error("Request timeout", extra={"username": username, "provider": name})

# ❌ 错误 — 不要用 f-string 拼接动态值到 msg
log.error(f"Login failed: {msg}")

# ❌ 错误 — 不要用 'message' 作为 extra key（Python logging 保留字）
log.warning("Failed", extra={"message": msg})  # KeyError!
```

## 保留字段名

以下 key 不能用在 `extra={}` 中（Python logging 内部使用）：
- `message`, `msg`, `args`, `asctime`, `created`, `filename`, `funcName`
- `levelname`, `levelno`, `lineno`, `module`, `msecs`, `name`
- `pathname`, `process`, `processName`, `relativeCreated`
- `stack_info`, `thread`, `threadName`, `taskName`

推荐替代：`reason`、`error`、`error_msg`、`result_msg`、`status`

## 日志打点位置

### Pipeline 层
- 每个步骤完成后打 INFO（含结果摘要）
- 网络异常打 ERROR（含异常类型和消息）

### Provider 层
- 登录成功：INFO
- 登录失败：WARNING（含 username + reason）
- 签到失败（非"已签到"）：WARNING（含 HTTP status + msg）
- 余额获取失败：WARNING（含 HTTP status）

### Script 层
- 开始处理每个账号：INFO（含 username + has_password）
- 单账号异常：ERROR（含 username + error）
- 批量完成：INFO（含 success/total 计数）

## 异常处理规范

### 原则
1. **不吞异常** — 每个 catch 必须有日志
2. **不中断批量** — 单个账号失败不影响后续，用 per-item try/catch
3. **分层捕获** — Pipeline 捕获网络异常，Script 捕获所有异常作为兜底
4. **返回 Result** — 不抛异常给调用方，用 `Result.fail()` 传递错误信息

### 模式

```python
# Pipeline 层：捕获已知网络异常，转为 Result
try:
    with httpx.Client(...) as client:
        result = provider.login(client, username, password)
        ...
except httpx.TimeoutException:
    log.error("Request timeout", extra={"username": username})
    return Result.fail("请求超时")
except httpx.ConnectError as e:
    log.error("Connection failed", extra={"username": username, "error": str(e)[:100]})
    return Result.fail(f"连接失败: {str(e)[:50]}")
except Exception as e:
    log.error("Unexpected error", extra={"username": username, "error": str(e)[:100]})
    return Result.fail(f"异常: {str(e)[:50]}")
```

```python
# Script 层：兜底 catch，保证批量不中断
for acct in accounts:
    try:
        result = pipeline.execute(...)
        results.append(...)
    except Exception as e:
        log.error("Account exception", extra={"username": username, "error": str(e)[:100]})
        results.append({"username": username, "status": "failed", ...})
```

### TypeScript（Worker Dashboard）

```typescript
// 批量操作：per-item try/catch
for (const item of items) {
  try {
    await repo.put(username, fields);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("batch_item_error", { username, error: msg });
  }
}

// Cron handler：顶层 try/catch
async scheduled(...) {
  try {
    // business logic
  } catch (e) {
    log.error("cron_error", { error: e.message });
  }
}
```

## 运维排查流程

1. **Worker 日志**：`npx wrangler tail`（实时）或 Cloudflare Dashboard → Workers → Logs
2. **GitHub Actions 日志**：GitHub repo → Actions → 对应 workflow run
3. **KV 失败记录**：`npx wrangler kv key list --binding KV --remote --preview false --prefix "fail_log:"`

### 常见日志模式

签到成功：
```
INFO  scripts.checkin_batch | Processing | username=xxx | has_password=true
INFO  provider.wucur       | Login success | username=xxx
INFO  pipeline.checkin     | Checkin done | username=xxx | result_msg=签到成功 +$1.00
INFO  scripts.checkin_batch | Batch completed | success=1 | total=1
```

密码缺失导致失败：
```
INFO  scripts.checkin_batch | Processing | username=xxx | has_password=false
WARN  provider.wucur       | Login failed | username=xxx | reason=Invalid parameters
INFO  scripts.checkin_batch | Batch completed | success=0 | total=1
```

网络超时：
```
INFO  scripts.checkin_batch | Processing | username=xxx | has_password=true
ERROR pipeline.checkin     | Request timeout | username=xxx | provider=wucur
INFO  scripts.checkin_batch | Batch completed | success=0 | total=1
```
