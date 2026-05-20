# Kiro 账号技术文档

## 概述

Kiro 基于 AWS Builder ID 认证体系，使用 OIDC Device Flow 获取 token。本文档记录注册、登录、Token 管理、API 调用、Trial 激活的完整技术细节。

---

## 1. Token 体系

| Token | 作用 | 有效期 | 可刷新 |
|-------|------|--------|--------|
| `sso_token` (x-amz-sso_authn) | 浏览器注册后的 cookie，用于 Device Auth | 几小时 | ❌ |
| `accessToken` | 调用 Kiro API 的访问令牌 | ~1 小时 | ✅ |
| `refreshToken` | 获取新 accessToken 的长期凭证 | 无限（定期使用） | ✅ |
| `clientId` | OIDC 客户端 ID，刷新时必须 | 跟随客户端注册（~90天） | — |
| `clientSecret` | OIDC 客户端密钥，刷新时必须 | 同上 | — |

**永久凭证组合**：`refreshToken` + `clientId` + `clientSecret`（三者缺一不可）

---

## 2. 注册流程

### Phase 1: 浏览器自动化 → sso_token

```
注册 OIDC 临时客户端 → 获取 user_code
  → 构造 URL: https://view.awsapps.com/start/#/device?user_code={code}
  → 浏览器打开 → 填邮箱 → 检测流程(注册/登录/验证)
    ├─ 注册: 填姓名 → 邮箱验证码 → 设密码
    └─ 登录: 填密码 → 邮箱验证码
  → 从 cookie 提取 x-amz-sso_authn (sso_token)
```

### Phase 2: SSO Device Auth → refreshToken (7 步)

```
Step 1: POST oidc.{region}.amazonaws.com/client/register → clientId, clientSecret
Step 2: POST oidc.{region}.amazonaws.com/device_authorization → deviceCode, userCode
Step 3: GET  portal.sso.us-east-1.amazonaws.com/token/whoAmI (Bearer: sso_token)
Step 4: POST portal.sso.us-east-1.amazonaws.com/session/device → deviceSessionToken
Step 5: POST oidc.{region}.amazonaws.com/device_authorization/accept_user_code
Step 6: POST oidc.{region}.amazonaws.com/device_authorization/associate_token
Step 7: POST oidc.{region}.amazonaws.com/token (轮询) → accessToken, refreshToken
```

---

## 3. Token 刷新

### BuilderId / IdC 账号

```
POST https://oidc.{region}.amazonaws.com/token
Body: { clientId, clientSecret, refreshToken, grantType: "refresh_token" }
→ { accessToken, refreshToken (可能更新), expiresIn }
```

### Social 账号 (GitHub/Google)

```
POST https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken
Body: { refreshToken }
Headers: { Content-Type: application/json, User-Agent: kiro-account-manager/1.0.0 }
→ { accessToken, refreshToken, expiresIn }
```

---

## 4. Kiro API

### 4.1 CBOR 端点 (KiroWebPortalService)

```
POST https://app.kiro.dev/service/KiroWebPortalService/operation/{operation}
Headers:
  accept: application/cbor
  content-type: application/cbor
  smithy-protocol: rpc-v2-cbor
  authorization: Bearer {accessToken}
  cookie: Idp={BuilderId|Github|Google}; AccessToken={accessToken}
```

**操作**：
- `GetUserInfo` → email, userId, idp, status, featureFlags
- `GetUserUsageAndLimits` → usageBreakdownList, subscriptionInfo, nextDateReset

### 4.2 REST 端点 (CodeWhisperer/Q)

```
GET https://q.us-east-1.amazonaws.com/getUsageLimits
Params: origin=AI_EDITOR&resourceType=AGENTIC_REQUEST&isEmailRequired=true
Headers:
  Accept: application/json
  Authorization: Bearer {accessToken}
  User-Agent: aws-sdk-js/1.0.18 ua/2.1 os/windows lang/js md/nodejs#20.16.0 api/codewhispererstreaming#1.0.18 m/E KiroIDE-{version}-{machineId}
```

### 4.3 Usage 响应结构

```json
{
  "usageBreakdownList": [{
    "resourceType": "CREDIT",
    "usageLimit": 50,
    "currentUsage": 0,
    "freeTrialInfo": {
      "usageLimit": 500,
      "currentUsage": 0,
      "freeTrialStatus": "ACTIVE",
      "freeTrialExpiry": "2026-06-15T00:00:00Z"
    },
    "bonuses": [{ "bonusCode": "...", "usageLimit": 100, "currentUsage": 0, "expiresAt": "..." }]
  }],
  "subscriptionInfo": { "subscriptionTitle": "KIRO FREE", "type": "Q_DEVELOPER_STANDALONE_FREE" },
  "nextDateReset": "2026-06-01T00:00:00Z"
}
```

**总额度** = `usageLimit` + `freeTrialInfo.usageLimit` + Σ`bonuses[].usageLimit`

### 4.4 封禁检测

- HTTP 423 → `AccountSuspendedException`（账号被封）
- HTTP 401 → Token 过期，需刷新

---

## 5. Kiro IDE 本地 Token 存储

### 路径

```
~/.aws/sso/cache/
├── kiro-auth-token.json          # 主 token 文件
└── {clientIdHash}.json           # 客户端凭证文件
```

### clientIdHash 计算方式

```python
import hashlib
start_url = "https://view.awsapps.com/start"  # BuilderId 固定值
input_str = '{"startUrl":"' + start_url + '"}'
client_id_hash = hashlib.sha1(input_str.encode()).hexdigest()
# 结果: e909a0580879b06ece1202964fbe9dda95ea4ce3
```

### kiro-auth-token.json 格式

**BuilderId (IdC) 账号**：
```json
{
  "accessToken": "aoaAAAAA...",
  "refreshToken": "aorAAAAA...",
  "expiresAt": "2026-05-20T03:00:00.000Z",
  "clientIdHash": "e909a0580879b06ece1202964fbe9dda95ea4ce3",
  "authMethod": "IdC",
  "provider": "BuilderId",
  "region": "us-east-1"
}
```

**Social (GitHub/Google) 账号**：
```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "expiresAt": "...",
  "authMethod": "social",
  "provider": "Github",
  "profileArn": "arn:aws:codewhisperer:us-east-1:..."
}
```

### {clientIdHash}.json 格式

```json
{
  "clientId": "4NxSXCiADDVL...",
  "clientSecret": "eyJraWQiOi...",
  "expiresAt": "2026-08-20T00:00:00.000Z"
}
```

---

## 6. Trial 激活 (500 Credits)

### 条件

新用户首次"使用" Kiro 时自动发放 500 bonus credits（14-30 天有效）。

### 触发方式

**已确认无效**：
- ❌ 调用 `GetUserInfo` API
- ❌ 调用 `GetUserUsageAndLimits` API
- ❌ 调用 REST `getUsageLimits` API（即使带 KiroIDE User-Agent）
- ❌ 仅启动 Kiro IDE 15 秒

**推测有效**（待验证）：
- 在 Kiro IDE 中完成首次 AI 交互（发送 chat 消息或触发代码补全）
- 正确写入 token 到 `~/.aws/sso/cache/` 后启动 IDE 并等待更长时间
- 通过 `codewhispererstreaming` API 发起一次 `SendMessage` 请求

### 当前状态

每个 BuilderId 账号基础额度 50 credits/月。Trial 激活方案仍在实验中。

---

## 7. 代理策略

| 场景 | 方式 | 限制 |
|------|------|------|
| 本地批量注册 | proxy_pool.py SOCKS5 轮换 | Kiro 1 个/IP |
| GitHub Actions | Runner 自带 IP | 每次运行 IP 不同 |
| Token 刷新 | 无需代理 | API 无 IP 限制 |

---

## 8. 参考项目

| 项目 | 语言 | 功能 |
|------|------|------|
| [chaogei/Kiro-account-manager](https://github.com/chaogei/Kiro-account-manager) | TypeScript/Electron | 注册 + 管理 + API 代理 |
| [hj01857655/kiro-account-manager](https://github.com/hj01857655/kiro-account-manager) | Rust/Tauri | 管理 + 切换 + IDE 集成 |
| wucurcheck (本项目) | Python + Worker | 注册 + 管理 + 自动刷新 |

---

## 9. 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Worker Dashboard                           │
│  (Cloudflare Worker + KV)                                    │
│  - 账号列表/状态展示                                          │
│  - Token 自动刷新 (Cron 每小时)                               │
│  - 用量查询 (Kiro CBOR API)                                  │
│  - 触发 GitHub Actions                                       │
└──────────────┬──────────────────────────────────┬────────────┘
               │ callback                         │ dispatch
               ▼                                  ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│   GitHub Actions          │    │   Python CLI                  │
│   - register_kiro.yml     │    │   - cli/register.py           │
│   - activate_kiro_trial   │    │   - cli/kiro_manager.py       │
│   (Windows + Playwright)  │    │   (本地/服务器)                │
└──────────────────────────┘    └──────────────────────────────┘
```
