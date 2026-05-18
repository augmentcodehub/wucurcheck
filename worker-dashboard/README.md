# Worker Dashboard

Cloudflare Worker 管理后台。零构建，daisyUI + Tailwind CDN，Worker 直接渲染 HTML。

## 功能

- 🔐 多用户登录（基于角色：admin/viewer）
- 📊 账号列表（余额、签到状态、密码脱敏）
- ➕ 批量注册（自然用户名生成、域名校验）
- ⚡ 一键签到未签到账号
- 🔄 定时自动签到（页面可配置时间）
- 📥 导出 CSV
- 🗑 批量删除（选中/失败/全部）
- 🔒 触发锁保护（防重复提交）
- 📝 结构化 JSON 日志
- 👥 用户管理（admin 专属）

## 项目结构

```
src/
├── index.js              # 入口：路由 + Cron handler + 错误边界
├── router.js             # 路由注册表
├── auth.js               # 登录/登出/session/多用户验证
├── layout.js             # daisyUI drawer 布局模板
├── lib/
│   ├── log.js            # 结构化 JSON 日志
│   ├── store.js          # KV CRUD（带日志和校验）
│   ├── github.js         # GitHub Actions 触发（多 workflow）
│   └── trigger_lock.js   # KV 短 TTL 锁
├── views/
│   ├── helpers.js        # 模板工具函数（badge, timeAgo, esc）
│   ├── account_table.js  # 工具栏 + 表格
│   ├── modals.js         # 详情弹窗 + 注册弹窗
│   ├── settings_panel.js # 定时签到 + 密码 + 用户管理
│   └── client_script.js  # 前端 JS 逻辑
└── pages/
    ├── accounts.js       # 页面组装 + CSV 导出 API
    ├── actions.js        # 触发 API（签到/注册/删除）
    ├── callback.js       # Actions 回调写入 KV
    └── settings.js       # 设置 + 用户管理 API
```

## 分层设计

```
请求 → index.js（日志 + 错误边界 + Cron）
     → auth.js（session + 角色验证）
     → router.js → pages/（API 逻辑）
                       ↓
                   views/（HTML 模板）
                   lib/store.js（KV 操作）
                   lib/github.js（外部调用）
```

## 快速开始

```bash
npm install
npx wrangler dev --local    # 本地开发
npx wrangler deploy         # 部署
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `ADMIN_USER` | 管理员用户名（默认 admin） |
| `ADMIN_PASS` | 管理员密码（可被 KV 覆盖） |
| `GITHUB_REPO` | GitHub 仓库（user/repo） |
| `GITHUB_TOKEN` | GitHub PAT（secret） |
| `GITHUB_WORKFLOW` | 签到 workflow（默认 checkin.yml） |
| `CALLBACK_SECRET` | 回调验证密钥 |

## KV 数据结构

| Key 前缀 | 用途 |
|----------|------|
| `account:{username}` | 账号数据 |
| `user:{username}` | 用户登录信息（password, role） |
| `session:{token}` | 登录会话（TTL 7天） |
| `lock:{action}:{target}` | 触发锁（TTL 5分钟） |
| `config:cron_hour` | 定时签到时间配置 |
| `config:admin_pass` | 管理员密码（KV 优先） |

## 回调协议

```json
// 签到
{"secret":"xxx","action":"checkin","data":{"username":"u1","balance":"1.5","checkin_time":"...","status":"active"}}

// 批量结果
{"secret":"xxx","action":"batch_result","data":{"results":[{"username":"u1","balance":"1.5","status":"active"}]}}

// 注册
{"secret":"xxx","action":"register","data":{"username":"u1","password":"p1","platform":"wucur"}}
```
