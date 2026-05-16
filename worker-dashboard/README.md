# Worker Dashboard

通用 Cloudflare Worker 管理后台框架。零构建，daisyUI + Tailwind CDN，Worker 直接渲染 HTML。

## 功能

- 🔐 Cookie session 登录（crypto.randomUUID token，KV 存储带 TTL）
- 📊 KV 数据表格展示（账号、余额、签到状态、时间）
- 🚀 一键触发 GitHub Actions（注册、签到、批量签到）
- 📥 回调接口自动写入 KV
- 🎨 daisyUI drawer 侧边栏布局
- 📝 结构化 JSON 日志（wrangler tail 友好）

## 项目结构

```
src/
├── index.js              # 入口：请求上下文注入 + 错误边界 + 路由分发
├── router.js             # 路由注册表
├── auth.js               # 登录/登出/session 验证
├── layout.js             # daisyUI drawer 侧边栏布局模板
├── lib/
│   ├── log.js            # 结构化 JSON 日志（每请求带 rid）
│   ├── store.js          # KV 数据层（账号 CRUD 抽象）
│   └── github.js         # GitHub Actions 触发封装
└── pages/
    ├── accounts.js       # 账号管理页面 + API
    ├── actions.js        # 触发操作 API（本地/远程分流）
    └── callback.js       # Actions 回调写入 KV
```

## 分层设计

```
请求 → index.js（日志 + 错误边界）
     → auth.js（session 拦截）
     → router.js → pages/（UI 渲染 + API）
                       ↓
                   lib/store.js（KV 操作）
                   lib/github.js（外部调用）
                   lib/log.js（日志基础设施）
```

- `lib/` — 基础设施层，无业务逻辑
- `pages/` — 业务层，只调用 lib 方法
- `layout.js` — UI 模板，页面传 title + content 即可

## 快速开始

```bash
# 1. 安装
npm install

# 2. 创建 KV namespace
npx wrangler kv namespace create KV
# 把返回的 id 填入 wrangler.toml

# 3. 配置 secrets
npx wrangler secret put ADMIN_PASS
npx wrangler secret put SESSION_SECRET
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put CALLBACK_SECRET

# 4. 本地开发
npx wrangler dev --local

# 5. 部署
npx wrangler deploy
```

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `ADMIN_USER` | 登录用户名（默认 admin） | vars |
| `ADMIN_PASS` | 登录密码 | secret |
| `SESSION_SECRET` | 预留（当前用 randomUUID） | secret |
| `GITHUB_REPO` | GitHub 仓库（user/repo） | vars |
| `GITHUB_TOKEN` | GitHub PAT（workflow 权限） | secret |
| `GITHUB_WORKFLOW` | Workflow 文件名（默认 task.yml） | vars |
| `CALLBACK_SECRET` | 回调验证密钥 | secret |

## 回调协议

GitHub Actions 完成后 POST 到 `/callback`：

```json
// 注册
{ "secret": "xxx", "action": "register", "data": { "username": "u1", "password": "p1", "platform": "aipulse" } }

// 签到
{ "secret": "xxx", "action": "checkin", "data": { "username": "u1", "balance": "128.5", "checkin_time": "2026-05-15T10:00:00Z" } }

// 批量
{ "secret": "xxx", "action": "batch_result", "data": { "results": [{ "username": "u1", "balance": "100" }, ...] } }
```

## 日志

所有日志为 JSON 格式，通过 `wrangler tail` 查看：

```bash
npx wrangler tail --format json
```

输出示例：
```json
{"ts":1715760000,"level":"info","msg":"request","path":"/","method":"GET","rid":"a1b2c3d4"}
{"ts":1715760001,"level":"info","msg":"workflow triggered","action":"checkin","target":"user1","path":"/api/trigger","rid":"e5f6g7h8"}
```

## 扩展新页面

1. 创建 `src/pages/xxx.js`，导出 handler
2. 在 `src/router.js` 添加路由
3. 在 `src/layout.js` 的 `navItems` 添加菜单项

## 后期规划

- 多用户：KV 存 `user:{id}`，auth.js 改查 KV
- 定时签到：添加 `[triggers] crons` 配置
- 操作日志：KV 存 `log:{timestamp}` 审计记录
