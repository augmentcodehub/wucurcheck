# Worker Dashboard 架构文档

## 技术栈

| 层 | 技术 |
|---|------|
| 语言 | TypeScript（strict mode，零 any） |
| 运行时 | Cloudflare Workers |
| 存储 | Cloudflare KV |
| 模板 | Mustache（服务端渲染） |
| 交互 | HTMX 2.0（声明式） |
| 客户端 | Islands 架构（4 个独立 JS） |
| 样式 | DaisyUI 5 + Tailwind CSS 4（CDN） |
| 类型生成 | `wrangler types` |

## 分层架构

```
Request → index.ts（日志上下文 + 错误边界）
        → auth-service.ts（session 验证）
        → router.ts（纯路由分发）
        → handlers/（业务编排）
            → repositories/（KV 数据访问，实现 Repository 接口）
            → services/（外部服务：GitHub dispatch、Kiro token）
            → views/（Mustache 模板渲染）
```

## 目录结构

```
src/
├── index.ts                  # Worker 入口（fetch + scheduled）
├── router.ts                 # 路由分发（零业务逻辑）
├── types/                    # 接口定义
│   ├── account.ts            #   Account + AccountRepository
│   ├── fail-log.ts           #   FailLogEntry + FailLogRepository
│   └── handler.ts            #   RouteHandler + Route
├── repositories/             # 数据访问层
│   ├── kv-account-repository.ts
│   ├── kv-fail-log-repository.ts
│   └── kv-session-repository.ts
├── lib/                      # 基础设施
│   ├── constants.ts          #   KV 前缀、TTL、Content-Type
│   ├── log.ts                #   结构化 JSON 日志
│   ├── response.ts           #   Response 工厂
│   ├── layout.ts             #   Mustache 页面布局
│   ├── crypto.ts             #   timing-safe compare
│   ├── static.ts             #   Island JS 静态服务
│   └── trigger-lock.ts       #   KV 分布式锁
├── services/                 # 业务服务
│   ├── auth-service.ts       #   登录/session
│   ├── github.ts             #   GitHub Actions dispatch
│   ├── account-manager.ts    #   Kiro 批量刷新
│   ├── kiro-token.ts         #   OIDC/Social token
│   ├── kiro-api.ts           #   CBOR API 客户端
│   └── sso-device-auth.ts    #   SSO 设备认证
├── handlers/                 # 路由处理器
│   ├── accounts.ts           #   页面 + 导出
│   ├── account-detail.ts     #   详情 partial + 日志
│   ├── actions.ts            #   触发 API（策略模式）
│   ├── callback.ts           #   GitHub 回调
│   └── settings.ts           #   设置 + 用户管理
├── views/                    # 视图层
│   ├── helpers.ts            #   badge/timeAgo/esc
│   ├── account-table.ts      #   表格渲染
│   ├── modals.ts             #   弹窗
│   └── settings-panel.ts     #   设置面板
├── templates/                # Mustache 模板（纯 HTML）
└── islands/                  # 浏览器端 JS（按需加载）
```

## KV 数据结构

| Key 格式 | 用途 | 常量 |
|----------|------|------|
| `account:{username}` | 账号数据 | `KV_PREFIX.ACCOUNT` |
| `fail_log:{username}:{date}` | 签到失败日志 | `KV_PREFIX.FAIL_LOG` |
| `session:{token}` | 登录会话（TTL 7天） | `KV_PREFIX.SESSION` |
| `user:{username}` | 用户信息 | `KV_PREFIX.USER` |
| `lock:{action}:{target}` | 触发锁（TTL 5分钟） | `KV_PREFIX.LOCK` |
| `config:cron_hour` | 定时签到配置 | `KV_KEY.CRON_HOUR` |
| `config:admin_pass` | 管理员密码 | `KV_KEY.ADMIN_PASS` |

## 环境变量

| 变量 | 说明 | 来源 |
|------|------|------|
| `ADMIN_USER` | 管理员用户名 | wrangler.toml |
| `ADMIN_PASS` | 管理员密码 | wrangler.toml |
| `GITHUB_REPO` | GitHub 仓库 | wrangler.toml |
| `GITHUB_TOKEN` | GitHub PAT | wrangler secret |
| `CALLBACK_SECRET` | 回调验证密钥 | wrangler.toml |
| `WORKER_SECRET` | API 认证密钥 | wrangler secret |

## 设计原则

- **面向接口**：Repository 接口定义在 `types/`，实现在 `repositories/`
- **面向对象**：KvAccountRepository 等 class 封装 KV 操作
- **模块化**：7 层分离，每个文件单一职责
- **日志规范**：所有模块通过 `log.info/warn/error` 输出结构化 JSON
- **常量集中**：`lib/constants.ts` 统一管理 KV 前缀、TTL、Content-Type
