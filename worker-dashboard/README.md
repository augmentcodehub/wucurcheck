# Worker Dashboard

Cloudflare Worker 管理后台。TypeScript + Mustache 模板 + HTMX + DaisyUI，面向接口编程 + Repository 模式。

## 技术栈

- **语言**：TypeScript（strict mode，零 any）
- **运行时**：Cloudflare Workers
- **存储**：Cloudflare KV
- **模板**：Mustache（服务端渲染）
- **交互**：HTMX（声明式）+ Islands 架构（按需加载 JS）
- **样式**：DaisyUI + Tailwind CSS（CDN）
- **类型生成**：`wrangler types`（Env 自动同步）

## 功能

- 🔐 多用户登录（基于角色：admin/viewer）
- 📊 账号列表（余额、签到状态、密码脱敏）
- ➕ 批量注册（自然用户名生成、域名校验）
- ⚡ 一键签到未签到账号
- 🔄 定时自动签到（页面可配置时间）
- 📥 导出 CSV / Kiro JSON
- 🗑 批量删除（选中/失败/全部）
- 📋 签到失败日志（按账号+日期记录）
- 🚀 Kiro 账号管理（token 刷新、用量查看）

## 项目结构

```
src/
├── index.ts                  # Worker 入口（fetch + scheduled）
├── router.ts                 # 纯路由分发（零业务逻辑）
├── types/                    # 接口定义
│   ├── account.ts            #   Account + AccountRepository
│   ├── fail-log.ts           #   FailLogEntry + FailLogRepository
│   └── handler.ts            #   RouteHandler + Route
├── repositories/             # 数据访问层（实现接口）
│   ├── kv-account-repository.ts
│   ├── kv-fail-log-repository.ts
│   └── kv-session-repository.ts
├── lib/                      # 基础设施
│   ├── constants.ts          #   KV 前缀、TTL、Content-Type
│   ├── log.ts                #   结构化 JSON 日志
│   ├── response.ts           #   Response 工厂（Res.html/json/error）
│   ├── layout.ts             #   Mustache 页面布局渲染
│   ├── crypto.ts             #   timing-safe compare
│   ├── static.ts             #   Island JS 静态文件服务
│   └── trigger-lock.ts       #   KV 分布式锁
├── services/                 # 业务服务
│   ├── auth-service.ts       #   登录/登出/session 验证
│   ├── github.ts             #   GitHub Actions dispatch
│   ├── account-manager.ts    #   Kiro 批量 token 刷新
│   ├── kiro-token.ts         #   OIDC/Social token 刷新
│   ├── kiro-api.ts           #   Kiro CBOR API 客户端
│   └── sso-device-auth.ts    #   SSO 设备认证流程
├── handlers/                 # 路由处理器
│   ├── accounts.ts           #   页面 + CSV/JSON 导出
│   ├── account-detail.ts     #   详情 HTML partial + 日志 API
│   ├── actions.ts            #   触发 API（策略模式）
│   ├── callback.ts           #   GitHub Actions 回调
│   └── settings.ts           #   设置 + 用户管理
├── views/                    # 视图层（数据 → HTML）
│   ├── helpers.ts            #   badge/timeAgo/esc
│   ├── account-table.ts      #   表格 Mustache 渲染
│   ├── modals.ts             #   弹窗模板
│   └── settings-panel.ts     #   设置面板模板
├── templates/                # Mustache 模板（纯 HTML）
│   ├── layout.mustache
│   └── partials/*.mustache
└── islands/                  # 浏览器端 JS（按需加载）
    ├── pagination.island.js
    ├── bulk-actions.island.js
    ├── register-form.island.js
    └── settings.island.js
```

## 架构分层

```
Request → index.ts（日志上下文 + 错误边界）
        → auth-service.ts（session 验证）
        → router.ts（路由分发）
        → handlers/（业务编排）
            → repositories/（KV 数据访问）
            → services/（外部服务调用）
            → views/（HTML 渲染）
```

## 快速开始

```bash
npm install
npx wrangler types          # 生成 Env 类型
npx tsc --noEmit            # 类型检查
npx wrangler dev            # 本地开发
npx wrangler deploy         # 部署
```

## 环境变量

| 变量 | 说明 | 来源 |
|------|------|------|
| `ADMIN_USER` | 管理员用户名 | wrangler.toml |
| `ADMIN_PASS` | 管理员密码 | wrangler.toml |
| `GITHUB_REPO` | GitHub 仓库 | wrangler.toml |
| `GITHUB_TOKEN` | GitHub PAT | wrangler secret |
| `GITHUB_WORKFLOW` | 默认 workflow | wrangler.toml |
| `CALLBACK_SECRET` | 回调验证密钥 | wrangler.toml |
| `WORKER_SECRET` | API 认证密钥 | wrangler secret |

## KV 数据结构

| Key 格式 | 用途 | 定义位置 |
|----------|------|----------|
| `account:{username}` | 账号数据 | `KV_PREFIX.ACCOUNT` |
| `fail_log:{username}:{date}` | 签到失败日志 | `KV_PREFIX.FAIL_LOG` |
| `session:{token}` | 登录会话（TTL 7天） | `KV_PREFIX.SESSION` |
| `user:{username}` | 用户登录信息 | `KV_PREFIX.USER` |
| `lock:{action}:{target}` | 触发锁（TTL 5分钟） | `KV_PREFIX.LOCK` |
| `config:cron_hour` | 定时签到配置 | `KV_KEY.CRON_HOUR` |
| `config:admin_pass` | 管理员密码 | `KV_KEY.ADMIN_PASS` |
