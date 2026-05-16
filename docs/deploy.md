# wucurcheck 完整部署手册

## 前置条件

- Node.js 18+
- Python 3.11+（本地开发用）
- [uv](https://docs.astral.sh/uv/)（Python 包管理）
- Cloudflare 账号
- GitHub 账号（有仓库写权限）

## 一、克隆仓库

```bash
git clone https://github.com/augmentcodehub/wucurcheck.git
cd wucurcheck
```

## 二、Cloudflare Worker 部署

### 2.1 登录 Cloudflare

```bash
cd worker-dashboard
npm install
npx wrangler login
```

浏览器弹出授权页面，点击允许。

### 2.2 创建 KV Namespace

```bash
npx wrangler kv namespace create KV
```

输出类似：
```
✨ Success! id = "937c4aa1f8ea4c219117d44f13dbe9cc"
```

编辑 `worker-dashboard/wrangler.toml`，填入你的值：

```toml
name = "worker-dashboard"
main = "src/index.js"
compatibility_date = "2024-12-01"
account_id = "你的_ACCOUNT_ID"

[vars]
ADMIN_USER = "admin"
ADMIN_PASS = "kiro"
CALLBACK_SECRET = "你的随机密钥"
GITHUB_REPO = "augmentcodehub/wucurcheck"
GITHUB_WORKFLOW = "checkin.yml"

[[kv_namespaces]]
binding = "KV"
id = "你的_KV_ID"
preview_id = "你的_KV_ID"

[triggers]
crons = ["0 * * * *"]
```

### 2.3 配置 Secrets（生产环境）

```bash
# GitHub Token（用于触发 Actions）
npx wrangler secret put GITHUB_TOKEN
# 粘贴你的 GitHub PAT

# 生产密码（覆盖 wrangler.toml 明文）
npx wrangler secret put ADMIN_PASS
# 输入强密码

# 回调密钥
npx wrangler secret put CALLBACK_SECRET
# 输入随机字符串
```

### 2.4 部署

```bash
npx wrangler deploy
```

部署成功后输出访问地址，如：
```
https://worker-dashboard.你的子域.workers.dev
```

### 2.5 验证

浏览器访问上述地址，用 admin + 你设置的密码登录。

## 三、GitHub Token 创建

1. 打开：https://github.com/settings/personal-access-tokens/new
2. 填写：
   - **Token name**: `worker-dashboard`
   - **Expiration**: 90 days 或 No expiration
   - **Repository access**: Only select repositories → `augmentcodehub/wucurcheck`
   - **Permissions** → Repository permissions:
     - **Actions**: Read and write
     - **Contents**: Read and write
3. 点击 "Generate token"
4. 复制 token 用于上面的 `wrangler secret put GITHUB_TOKEN`

## 四、GitHub 仓库 Secrets 配置

打开：https://github.com/augmentcodehub/wucurcheck/settings/secrets/actions

添加以下 Repository secrets：

| Secret 名 | 值 | 说明 |
|-----------|-----|------|
| `WORKER_CALLBACK_SECRET` | 与 Worker 的 CALLBACK_SECRET 一致 | 回调认证 |
| `WORKER_CALLBACK_URL` | `https://你的worker地址/callback` | 备用回调地址（定时签到用） |
| `ANYROUTER_ACCOUNTS` | 账号 JSON（可选，旧签到方式用） | 兼容旧 checkin.yml |
| `PROVIDERS` | Provider 配置 JSON（可选） | 自定义平台配置 |

## 五、Python 环境（本地开发/调试）

```bash
cd wucurcheck

# 安装依赖
uv sync

# 验证
uv run python -c "from cli.checkin import run_main; print('OK')"

# 本地测试注册（3个账号）
uv run python python/src/tools/account_generation/gen_natural_accounts.py 3 qq.com "123Claude&Codex" "fruit+animal"

# 本地测试签到
uv run python checkin.py
```

## 六、功能使用

### 6.1 批量注册

1. 登录 Dashboard
2. 点击「➕ 批量注册」
3. 选择：数量、用户名组合、邮箱域名（推荐 qq.com）、密码
4. 确认预览无误后点击「开始注册」
5. 等待 GitHub Actions 完成（约 数量×10 秒）
6. 刷新页面查看结果

### 6.2 一键签到未签到

1. 点击「⚡ 一键签到未签到」
2. Worker 自动筛选今日未签到账号
3. 传给 Actions 逐个签到（间隔 5-10 秒）
4. 完成后自动回写结果

### 6.3 定时签到设置

1. 页面底部「⏰ 定时签到设置」
2. 多选签到时间点（北京时间）
3. 点击「保存」
4. Worker 每小时检查，匹配时间自动触发

### 6.4 导出数据

点击「📥 导出CSV」下载所有账号信息。

### 6.5 批量删除

点击「🗑 删除」下拉菜单：
- 勾选账号后「删除选中的」
- 「删除失败的」清理注册失败账号
- 「删除全部」清空

## 七、Workflow 说明

| 文件 | 触发方式 | 功能 |
|------|---------|------|
| `checkin.yml` | 定时 / 手动 / Worker Cron | 全量签到（从 ANYROUTER_ACCOUNTS 读取） |
| `checkin_batch.yml` | Worker「一键签到未签到」 | 从 KV 读取未签到账号逐个签到 |
| `register.yml` | Worker「批量注册」 | 生成自然用户名 + 注册 + 首次签到 |

## 八、目录结构

```
wucurcheck/
├── worker-dashboard/           # Cloudflare Worker 管理后台
│   ├── src/
│   │   ├── index.js            # 入口 + Cron handler
│   │   ├── router.js           # 路由
│   │   ├── auth.js             # 登录/Session
│   │   ├── layout.js           # daisyUI 页面布局
│   │   ├── lib/
│   │   │   ├── log.js          # 结构化日志
│   │   │   ├── store.js        # KV CRUD
│   │   │   ├── github.js       # Actions 触发
│   │   │   └── trigger_lock.js # 重复触发保护
│   │   └── pages/
│   │       ├── accounts.js     # 账号页面 + API
│   │       ├── actions.js      # 触发 API
│   │       ├── callback.js     # 回调处理
│   │       └── settings.js     # 设置 API
│   ├── wrangler.toml
│   └── package.json
├── python/src/                  # Python 后端
│   ├── cli/                     # CLI 入口
│   ├── adapters/                # HTTP 客户端、持久化
│   ├── core/                    # 领域模型、用例
│   ├── tools/
│   │   ├── account_generation/  # 账号生成（规则引擎）
│   │   └── register/           # 注册工具
│   ├── scripts/
│   │   └── checkin_batch.py    # 批量签到脚本
│   └── utils/                   # 配置、通知、日志
├── .github/workflows/
│   ├── checkin.yml             # 定时签到
│   ├── checkin_batch.yml       # 批量签到未签到
│   └── register.yml            # 批量注册
├── checkin.py                   # 签到入口
└── docs/
    ├── features.md             # 功能介绍
    └── deploy.md               # 本文档
```

## 九、故障排查

### 查看 Worker 日志

```bash
cd worker-dashboard
npx wrangler tail --format json
```

### 查看 Actions 日志

https://github.com/augmentcodehub/wucurcheck/actions

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 登录后跳回登录页 | Cookie 问题 | 确认用 HTTPS 或 localhost |
| 触发返回 DISPATCH_FAILED | Token 无效或仓库名错误 | 检查 GITHUB_TOKEN 权限 |
| 注册返回 Username max tag | 用户名+域名超 20 字符 | 换短域名（qq.com） |
| 注册返回 HTTP 429 | 频率限制 | 减少数量或增大间隔 |
| 回调返回 401 | Secret 不匹配 | 检查 WORKER_CALLBACK_SECRET |
| 一键签到提示「所有已签到」 | 今日都签过了 | 正常，明天再试 |
| 定时签到没触发 | 未配置时间 | 页面底部设置签到时间并保存 |

## 十、安全建议

1. 生产环境用 `wrangler secret` 存密码，不要明文写在 wrangler.toml
2. GitHub Token 用 Fine-grained，只授权单个仓库
3. CALLBACK_SECRET 用随机强密钥
4. 定期轮换 Token 和密码
5. 不要在公开仓库暴露 wrangler.toml 中的 account_id 和 KV id
