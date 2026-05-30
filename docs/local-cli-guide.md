# 本地 CLI 使用指南

## 前置条件

```bash
cd /home/administrator/workspace/open-source/wucurcheck
uv sync  # 安装依赖
```

## 命令总览

```bash
uv run wucur --help
```

| 命令 | 用途 |
|------|------|
| `wucur checkin` | 签到（批量或单个） |
| `wucur register` | 注册新账号（wucur / kiro） |
| `wucur refresh` | 刷新 kiro OIDC token |
| `wucur callback` | 将 results.json POST 到 Worker |

## 签到

```bash
# 单个账号
uv run wucur checkin --username user@qq.com --password "123Claude&Codex" --output results.json

# 批量（从文件）
echo '[{"username":"a@qq.com","password":"123Claude&Codex"}]' > accounts.json
uv run wucur checkin --file accounts.json --output results.json
```

## 注册

```bash
# Wucur 注册（自动生成邮箱）
uv run wucur register --provider wucur --count 3 --output results.json

# Kiro 注册（需要 EMAIL_API_KEY）
EMAIL_API_KEY=xxx uv run wucur register --provider kiro --count 1 --email-domain ouraihub.com --output results.json
```

## 刷新 Token

```bash
# 单个账号
CF_ACCOUNT_ID=xxx CF_API_TOKEN=xxx KV_NAMESPACE_ID=xxx \
uv run wucur refresh --target user@ouraihub.com --output results.json

# 全部 kiro 账号
CF_ACCOUNT_ID=xxx CF_API_TOKEN=xxx KV_NAMESPACE_ID=xxx \
uv run wucur refresh --all --output results.json
```

## 回调

```bash
# 将结果 POST 到 Worker Dashboard
CALLBACK_URL=https://worker-dashboard.ouraihub.workers.dev/callback \
CALLBACK_SECRET=xxx \
uv run wucur callback --file results.json
```

## 环境变量

| 变量 | 用途 | 命令 |
|------|------|------|
| `CALLBACK_URL` | Worker 回调地址 | callback |
| `CALLBACK_SECRET` | 回调认证密钥 | callback |
| `WUCUR_DOMAIN` | Wucur 站点地址（默认 `http://wucur.com:6543`） | register |
| `PASSWORD` | 注册密码（默认 `123Claude&Codex`） | register |
| `EMAIL_API_KEY` | OurAIHub 邮箱 API Key | register --provider kiro |
| `CF_ACCOUNT_ID` | Cloudflare Account ID | refresh |
| `CF_API_TOKEN` | Cloudflare API Token | refresh |
| `KV_NAMESPACE_ID` | KV Namespace ID | refresh |
