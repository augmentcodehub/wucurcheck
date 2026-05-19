# Kiro 账号注册流程说明

## 概述

Kiro 注册基于 AWS Builder ID，完整流程分为两个阶段：

1. **浏览器自动化注册** — 通过 Playwright 操作浏览器完成账号注册，获取 `sso_token`
2. **SSO Device Auth** — 用 `sso_token` 作为 bearer token，通过 AWS OIDC API 获取可刷新的 `refreshToken` + `accessToken`

## Phase 1: 浏览器注册

### 流程

```
获取 device code → 打开注册页面 → 填写邮箱 → 检测流程(注册/登录)
  ├─ 注册流程: 填姓名 → 获取邮箱验证码 → 填验证码 → 设置密码
  └─ 登录流程: 填密码 → 获取邮箱验证码 → 填验证码
→ 等待页面跳转 → 从 cookie 提取 x-amz-sso_authn (sso_token)
```

### 关键接口

| 步骤 | URL | 说明 |
|------|-----|------|
| 注册 OIDC 客户端 | `POST https://oidc.us-east-1.amazonaws.com/client/register` | 获取临时 clientId 用于生成 user_code |
| 设备授权 | `POST https://oidc.us-east-1.amazonaws.com/device_authorization` | 获取 user_code 构造注册 URL |
| 注册页面 | `https://view.awsapps.com/start/#/device?user_code={code}` | 浏览器打开此 URL |

### 输出

- `sso_token`: `x-amz-sso_authn` cookie 值（bearer token，有效期有限，不可刷新）

## Phase 2: SSO Device Auth

用 Phase 1 获取的 `sso_token` 作为 bearer token，执行完整的设备授权流程，获取可无限刷新的 token。

### 流程（7 步）

```
Step 1: 注册 OIDC 客户端
  POST https://oidc.{region}.amazonaws.com/client/register
  → clientId, clientSecret

Step 2: 发起设备授权
  POST https://oidc.{region}.amazonaws.com/device_authorization
  Body: { clientId, clientSecret, startUrl }
  → deviceCode, userCode, interval

Step 3: 验证 bearer token
  GET https://portal.sso.us-east-1.amazonaws.com/token/whoAmI
  Header: Authorization: Bearer {sso_token}

Step 4: 获取设备会话令牌
  POST https://portal.sso.us-east-1.amazonaws.com/session/device
  Header: Authorization: Bearer {sso_token}
  → deviceSessionToken

Step 5: 接受用户代码
  POST https://oidc.{region}.amazonaws.com/device_authorization/accept_user_code
  Body: { userCode, userSessionId: deviceSessionToken }
  → deviceContext

Step 6: 批准授权
  POST https://oidc.{region}.amazonaws.com/device_authorization/associate_token
  Body: { deviceContext, userSessionId: deviceSessionToken }

Step 7: 轮询获取 Token
  POST https://oidc.{region}.amazonaws.com/token
  Body: { clientId, clientSecret, grantType: "urn:ietf:params:oauth:grant-type:device_code", deviceCode }
  → accessToken, refreshToken, expiresIn
```

### 输出

| 字段 | 说明 |
|------|------|
| `accessToken` | 访问令牌，用于调用 Kiro API，有效期约 1 小时 |
| `refreshToken` | 刷新令牌，用于获取新的 accessToken，可无限续期 |
| `clientId` | OIDC 客户端 ID，刷新 token 时需要 |
| `clientSecret` | OIDC 客户端密钥，刷新 token 时需要 |
| `region` | 区域，默认 `us-east-1` |
| `expiresIn` | accessToken 有效期（秒） |

## Token 刷新

```
POST https://oidc.{region}.amazonaws.com/token
Body: {
  clientId,
  clientSecret,
  refreshToken,
  grantType: "refresh_token"
}
→ { accessToken, refreshToken (可能更新), expiresIn }
```

## 触发方式

### Worker Dashboard 触发

```
POST /api/trigger
Body: { "action": "register_kiro", "inputs": { "count": "1" } }
```

Worker → GitHub API dispatch `register_kiro.yml` → Actions 执行注册 → 回调 `/callback` 写入 KV

### 回调数据格式

```json
{
  "secret": "...",
  "action": "batch_result",
  "data": {
    "results": [{
      "username": "xxx@ouraihub.com",
      "password": "admin123456aA!",
      "platform": "kiro",
      "status": "active",
      "name": "James Williams",
      "sso_token": "eyJ...",
      "access_token": "eyJ...",
      "refresh_token": "...",
      "client_id": "...",
      "client_secret": "...",
      "region": "us-east-1",
      "expires_in": 3600
    }]
  }
}
```

## 文件结构

| 文件 | 说明 |
|------|------|
| `python/src/tools/register/register_kiro_account.py` | 核心注册逻辑（浏览器 + SSO Device Auth） |
| `python/src/cli/register_kiro.py` | CLI 入口 |
| `.github/workflows/register_kiro.yml` | GitHub Actions workflow |
| `worker-dashboard/src/lib/github.js` | Worker 触发 workflow |

## 参考

基于 [Kiro-auto-register](https://github.com/chaogei/Kiro-account-manager) 项目的 `src/main/autoRegister.ts`（浏览器注册）和 `src/main/index.ts`（ssoDeviceAuth 流程）严格移植。
