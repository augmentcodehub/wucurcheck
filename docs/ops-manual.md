# 运维手册（AI Agent 参考）

> 编码规范见 [coding-standards.md](./coding-standards.md)

## 项目概览

wucurcheck 是一个自动签到 + Kiro 账号注册系统。

**架构：**
- **Worker Dashboard**（Cloudflare Worker）：管理面板 + 定时触发 + 回调接收
- **GitHub Actions**：执行签到、注册、Token 刷新
- **GitLab CI**：执行 Kiro 纯 API 注册（双平台并行）
- **Cloudflare KV**：存储账号数据
- **MoeMail**（Cloudflare Email Routing）：临时邮箱服务，用于 Kiro 注册

**流程：**
```
签到：Worker cron → 筛选未签到账号 → GitHub Actions → 回调写入 KV
注册：Dashboard UI → Worker 触发 GitHub/GitLab → CI 执行注册 → 回调写入 KV
刷新：Dashboard UI → GitHub Actions → 读 KV 凭据 → 调 AWS OIDC → 回调写入 KV
```

---

## 关键路径

| 组件 | 路径 |
|------|------|
| Worker Dashboard 源码 | `worker-dashboard/src/` |
| 签到脚本（批量） | `python/src/scripts/checkin_batch.py` |
| Kiro Token 刷新脚本 | `python/src/scripts/kiro_refresh.py` |
| Kiro 纯 API 注册 | `node-register/src/` |
| HTTP 客户端 | `python/src/adapters/http/wucur_client.py` |
| 账号 KV 存储 | `worker-dashboard/src/repositories/kv-account-repository.ts` |
| 回调处理 | `worker-dashboard/src/handlers/callback.ts` |
| CI 触发（GitHub） | `worker-dashboard/src/services/github.ts` |
| CI 触发（GitLab） | `worker-dashboard/src/services/gitlab.ts` |
| GitLab CI 配置 | GitLab 仓库 `gitlab.com/kiro.dev/kiro` → `.gitlab-ci.yml` |

---

## KV 数据结构

### 账号记录

Key：`account:{username}`

**Wucur 账号：**
```json
{
  "username": "xxx@qq.com",
  "password": "（见 DEFAULT_PASSWORD 常量）",
  "platform": "wucur",
  "status": "active",
  "balance": "6.9",
  "checkin_time": "2026-05-28T00:59:25Z",
  "last_result": "今日已签到",
  "created_at": "2026-05-18T...",
  "updated_at": "2026-05-28T..."
}
```

**Kiro 账号：**
```json
{
  "username": "xxx@ouraihub.com",
  "password": "...",
  "platform": "kiro",
  "status": "active",
  "refresh_token": "aorAAAAA...",
  "access_token": "aoaAAAAA...",
  "client_id": "iRW-...",
  "client_secret": "eyJraWQ...",
  "region": "us-east-1",
  "subscription_type": "Free",
  "usage_current": 0,
  "usage_limit": 50,
  "last_refresh_at": "2026-05-22T...",
  "created_at": "2026-05-21T...",
  "updated_at": "2026-05-22T..."
}
```

**status 取值：** `active` | `failed` | `pending` | `suspended`  
**platform 判断规则：** 邮箱包含 `ouraihub.com` → `kiro`，其他 → `wucur`

### 配置项

| Key | 说明 |
|-----|------|
| `config:cron_hour` | 签到触发小时列表，如 `[0,1,2,...,23]` |
| `config:email_api_key` | OurAIHub 邮箱 API Key |

### 失败日志

Key：`fail_log:{username}:{date}`

---

## 邮箱域名配置

Kiro 注册使用 MoeMail 临时邮箱，通过 Cloudflare Email Routing 接收。

| 域名 | 用途 | Email Routing 规则 |
|------|------|-------------------|
| `ouraihub.com` | GitHub Actions 注册 | Catch-all → `email-receiver-worker` |
| `mail.ouraihub.com` | GitLab CI 注册 | `*@mail.ouraihub.com` → `email-receiver-worker` |
| `dev.ouraihub.com` | 备用 | `*@dev.ouraihub.com` → `email-receiver-worker` |
| `reg.ouraihub.com` | 备用 | `*@reg.ouraihub.com` → `email-receiver-worker` |

子域名路由规则通过 Cloudflare API 创建（Dashboard UI 不支持子域名通配）。

MoeMail 允许域名列表存储在 KV `SITE_CONFIG` namespace 的 `EMAIL_DOMAINS` key 中。

---

## 双平台注册（GitHub + GitLab）

Dashboard 触发 `register_kiro_api` 时：
- 前端可选平台：GitHub / GitLab / 两者并行
- Worker 将 count 分配给选中的平台
- GitHub 用 `ouraihub.com`，GitLab 用 `mail.ouraihub.com`

**GitLab 配置：**
- 项目：`gitlab.com/kiro.dev/kiro`（Project ID: 82408215）
- 触发方式：Pipeline Trigger Token（FormData 格式）
- CI Variables：`EMAIL_API_KEY`、`EMAIL_DOMAIN`
- Worker secret：`GITLAB_TRIGGER_TOKEN`

**注意：** Worker 直接调 AWS OIDC 刷新 Token 会被拦截（520），必须通过 GitHub Actions 执行。

---

## 常用运维命令

### 查询账号

```bash
cd worker-dashboard
npx wrangler kv key list --binding KV --remote --preview false --prefix "account:"
npx wrangler kv key get "account:xxx@qq.com" --binding KV --remote --preview false
```

### 部署 Worker

```bash
cd worker-dashboard
npx tsc --noEmit && npx wrangler deploy
```

### 手动触发签到

```bash
curl -X POST "https://worker-dashboard.ouraihub.workers.dev/api/trigger" \
  -H "Content-Type: application/json" \
  -d '{"action":"checkin_unchecked","token":"<CALLBACK_SECRET>"}'
```

### 手动触发 Kiro 注册

```bash
curl -X POST "https://worker-dashboard.ouraihub.workers.dev/api/trigger" \
  -H "Content-Type: application/json" \
  -d '{"action":"register_kiro_api","token":"<CALLBACK_SECRET>","inputs":{"count":"2","platform":"both"}}'
```

### 手动刷新 Kiro Token

```bash
curl -X POST "https://worker-dashboard.ouraihub.workers.dev/api/trigger" \
  -H "Content-Type: application/json" \
  -d '{"action":"kiro_refresh","target":"xxx@ouraihub.com","token":"<CALLBACK_SECRET>"}'
```

---

## 常见问题排查

### 签到失败："登录失败: Invalid parameters"

**原因：** wucur 服务器限流（同一 IP 短时间大量请求），返回非标准错误。  
**处理：** status 保持 active，下次 cron 自动重试。如果持续失败，从本机手动测试确认账号是否正常。

### 账号不参与自动签到

**筛选条件：** `status === "active"` + `platform === "wucur"` + `checkin_time` 不是今天。  
**常见原因：** status 为 `failed` 没被重置。

### Kiro Token 刷新失败 (401)

**原因：** `client_secret` 不完整（被截断）或 `refresh_token` 过期。  
**排查：** 检查 KV 中 `client_secret` 长度是否 ~4800 字符。

### Kiro 注册 GitLab 失败

**排查：** 查看 GitLab pipeline 日志 → 常见问题：
- `connection reset by peer`：GitLab Runner IP 被 AWS 风控，需加代理
- `jq: command not found`：已修复，用 node 替代 jq 构造回调 JSON

---

## 签到流程详解

```
Worker cron (每30分钟，每小时都检查)
  → 从 KV 读取 status=active 且今天未签到的 wucur 账号
  → 有未签到的 → 触发 GitHub Actions checkin_batch.yml
    → checkin_batch.py：
      - 每个账号间隔 15-30 秒
      - 每 15 个暂停 2 分钟（防限流）
      - 签到成功 → build_checkin_result()
      - 已签到 → build_already_checked_result()
    → 回调 POST /callback → handleBatchResult() → 更新 KV
  → 无未签到的 → 不触发，等下次 cron
```

---

## Wucur API

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 登录 | POST | `/api/user/login` | `{username, password}`，返回 session + user_id |
| 签到 | POST | `/api/user/checkin` | 需 session cookie + `new-api-user: {id}` |
| 用户信息 | GET | `/api/user/self` | 返回 quota（原始值），`get_user_info()` 已转为美元 |

**注意：** `get_user_info()` 返回的 `quota` 已经是美元 float（内部做了 `/500000`），调用方不要再次转换。

---

## 部署注意事项

- Worker 已通过 OAuth 登录（`ouraihub@gmail.com`）
- wrangler v4 命令格式：`npx wrangler kv key get "key" --binding KV --remote --preview false`
- 部署前必须 `npx tsc --noEmit` 检查编译
- Worker 使用 `nodejs_compat` flag（支持 AsyncLocalStorage）
- 静态资源缓存 1 小时，改 JS 后需 `Ctrl+Shift+R` 强刷
