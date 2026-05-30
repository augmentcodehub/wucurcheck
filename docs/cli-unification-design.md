# 设计：统一 CLI 重构

## 目标

将散落在多个 workflow 和脚本中的逻辑统一为一个 `wucur` CLI 工具，使 CI workflow 只负责环境准备和调用 CLI，不包含业务逻辑。

## 现状代码位置

| 功能 | 当前实现 | 语言 | 说明 |
|------|----------|------|------|
| Wucur 签到 | `python/src/scripts/checkin_batch.py` | Python | 调用 `pipelines/checkin.py` → `providers/wucur.py` |
| Wucur 注册 | `python/src/cli/register_wucur.py` | Python | HTTP POST 注册 |
| Kiro 注册 | `node-register/src/index.ts` | TypeScript/Node | 依赖 `tlsclientwrapper`（native 模块），**不能改为 Python** |
| Kiro Token 刷新 | `python/src/scripts/kiro_refresh.py` | Python | 调 AWS OIDC + Cloudflare KV API |
| AnyRouter 签到 | `checkin.py`（根目录） | Python | Playwright 浏览器签到 |
| 回调 Worker | 各 workflow 内联 curl/PowerShell | Shell | 每个 workflow 重复实现 |

### 关键依赖

- `python/src/providers/wucur.py` — Wucur HTTP 客户端（login/checkin/get_balance）
- `python/src/pipelines/checkin.py` — CheckinPipeline（login → balance → checkin → balance → 比较）
- `node-register/` — Kiro 注册（Node.js，依赖 tls-client native .so）
- `python/src/core/result.py` — Result 类型

## results.json 格式规范

所有命令输出统一格式，`wucur callback` 读取此文件：

```json
[
  {
    "username": "xxx@qq.com",
    "password": "123Claude&Codex",
    "platform": "wucur",
    "status": "active",
    "last_result": "签到成功 +$0.88",
    "balance": "9.24",
    "checkin_time": "2026-05-30T08:00:00Z",
    "register_source": "github"
  },
  {
    "username": "yyy@qq.com",
    "status": "active",
    "last_result": "登录失败: HTTP 429",
    "register_source": "gitlab"
  }
]
```

**规则：**
- 数组，每个元素一个账号结果
- `username` 必填
- 其他字段可选，有值才写入 KV（undefined 不覆盖已有数据）
- `status` 永远写 `"active"`（除非账号被封才写 `"suspended"`）
- `platform` 根据邮箱自动判断（包含 `ouraihub.com` → kiro，其他 → wucur）

## 环境变量清单

### 通用（所有命令）

| 变量 | 说明 | 来源 |
|------|------|------|
| `CALLBACK_URL` | Worker 回调地址 | CI secret / 触发时传入 |
| `CALLBACK_SECRET` | 回调认证密钥 | CI secret |

### `wucur checkin`

| 变量 | 说明 |
|------|------|
| 无额外变量 | 账号信息从 `--file` 读取 |

### `wucur register --provider wucur`

| 变量 | 说明 |
|------|------|
| `WUCUR_DOMAIN` | 可选，默认 `http://wucur.com:6543` |
| `PASSWORD` | 可选，默认 `123Claude&Codex` |

### `wucur register --provider kiro`

| 变量 | 说明 |
|------|------|
| `EMAIL_API_KEY` | OurAIHub 邮箱 API Key |
| `EMAIL_DOMAIN` | 邮箱域名，如 `ouraihub.com` |

### `wucur refresh`

| 变量 | 说明 |
|------|------|
| `CF_ACCOUNT_ID` | Cloudflare Account ID |
| `CF_API_TOKEN` | Cloudflare API Token |
| `KV_NAMESPACE_ID` | KV Namespace ID |

## CLI 命令设计

### `wucur checkin`

```bash
# 批量签到（从文件读取账号列表）
wucur checkin --file accounts.json --output results.json

# 单个签到
wucur checkin --username xxx@qq.com --password xxx --output results.json
```

### `wucur register`

```bash
# Wucur 注册（纯 Python HTTP）
wucur register --provider wucur --count 3 --output results.json

# Kiro 注册（调用 node-register 子进程）
wucur register --provider kiro --count 1 --email-domain ouraihub.com --output results.json
```

**注意：** Kiro 注册内部通过 `subprocess` 调用 `node dist/index.js`，不是纯 Python 实现。CLI 负责参数转换和结果收集。

### `wucur refresh`

```bash
# 刷新单个账号（从 KV 读取凭据）
wucur refresh --target xxx@ouraihub.com --output results.json

# 全部 kiro 账号
wucur refresh --all --output results.json
```

### `wucur callback`

```bash
# 读取 results.json，POST 到 Worker /callback
wucur callback --file results.json
```

环境变量 `CALLBACK_URL` 和 `CALLBACK_SECRET` 必须设置。

## Provider Protocol

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class Result:
    success: bool
    message: str = ""
    data: dict | None = None

    @staticmethod
    def ok(data=None, message="") -> "Result": ...
    @staticmethod
    def fail(message="") -> "Result": ...


class Provider(Protocol):
    name: str
    domain: str

    def register(self, username: str, password: str) -> Result: ...
    def login(self, client, username: str, password: str) -> Result: ...
    def checkin(self, client, headers: dict) -> Result: ...
    def get_balance(self, client, headers: dict) -> Result: ...
    def build_auth_headers(self, user_id: str) -> dict: ...
```

### WucurProvider

- `register`: POST `/api/user/register`
- `login`: POST `/api/user/login`
- `checkin`: POST `/api/user/checkin`
- `get_balance`: GET `/api/user/self`，返回 `quota / 500000` 美元值

### KiroProvider

- `register`: 调用 `node node-register/dist/index.js` 子进程
- 其他方法不实现（Kiro 不需要签到）

## 目录结构

```
python/
├── pyproject.toml          # [project.scripts] wucur = "src.cli:main"
├── src/
│   ├── cli/
│   │   ├── __init__.py     # typer app, main()
│   │   ├── checkin.py      # wucur checkin 命令
│   │   ├── register.py     # wucur register 命令
│   │   ├── refresh.py      # wucur refresh 命令
│   │   └── callback.py     # wucur callback 命令
│   ├── providers/
│   │   ├── __init__.py     # Registry + get_provider()
│   │   ├── protocol.py     # Provider Protocol 定义
│   │   ├── wucur.py        # WucurProvider 实现
│   │   └── kiro.py         # KiroProvider 实现（subprocess 调 node）
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── checkin.py      # CheckinPipeline（现有，保持不变）
│   └── lib/
│       ├── http.py         # httpx client 工厂
│       ├── config.py       # 环境变量读取
│       └── result.py       # Result dataclass
└── tests/
    ├── test_checkin.py     # 迁移自 test_checkin_batch.py
    ├── test_register.py    # 新增
    └── test_callback.py    # 新增
```

## Workflow 改造后示例

### checkin_batch.yml

```yaml
jobs:
  checkin:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e python/
      - run: |
          echo '${{ inputs.accounts_json }}' > accounts.json
          wucur checkin --file accounts.json --output results.json
      - if: always()
        run: wucur callback --file results.json
        env:
          CALLBACK_URL: ${{ inputs.callback_url || secrets.WORKER_CALLBACK_URL }}
          CALLBACK_SECRET: ${{ secrets.WORKER_CALLBACK_SECRET }}
```

### GitLab .gitlab-ci.yml

```yaml
.base:
  image: python:3.11-slim
  before_script:
    - pip install -e python/
  after_script:
    - wucur callback --file results.json

register_wucur:
  extends: .base
  rules:
    - if: $ACTION == "register_wucur"
  script:
    - wucur register --provider wucur --count ${COUNT:-3} --output results.json

register_kiro_api:
  extends: .base
  image: node:20
  before_script:
    - cd node-register && npm ci && npm run build
    - pip install -e python/  # for callback
  rules:
    - if: $ACTION == "register_kiro_api" || $ACTION == null
  script:
    - wucur register --provider kiro --count ${COUNT:-1} --email-domain ${EMAIL_DOMAIN:-ouraihub.com} --output results.json
```

## 测试迁移

| 现有测试 | 迁移到 | 说明 |
|----------|--------|------|
| `tests/test_checkin_batch.py` | `tests/test_checkin.py` | `format_balance`、`build_checkin_result` 等纯函数测试保留 |
| 无 | `tests/test_register.py` | 新增：mock HTTP 测试 wucur 注册 |
| 无 | `tests/test_callback.py` | 新增：测试 results.json 解析 + HTTP POST 构造 |

## 实施步骤

### Phase 1：统一 callback（最小改动，立即收益）

1. 写 `src/cli/callback.py`（读 results.json → POST Worker）
2. `pyproject.toml` 注册 `wucur` 命令
3. 所有 workflow 的回调改为 `wucur callback --file results.json`
4. 删除各 workflow 中重复的 curl/PowerShell 回调代码

### Phase 2：统一 register

1. 写 `src/cli/register.py` + `src/providers/wucur.py`
2. Kiro provider 通过 subprocess 调 node-register
3. 替换 GitLab CI 内联脚本 + GitHub `register_kiro_api.yml`

### Phase 3：统一 checkin

1. 写 `src/cli/checkin.py`，内部调用现有 `CheckinPipeline`
2. 替换 `checkin_batch.yml` 中的直接 Python 调用

### Phase 4：统一 refresh

1. 写 `src/cli/refresh.py`
2. 替换 `kiro_refresh.yml`

### Phase 5：清理

1. 删除旧的独立脚本（`scripts/checkin_batch.py`、`scripts/kiro_refresh.py`）
2. 统一 Windows/Linux workflow 为 Linux（去掉 PowerShell）
3. 更新运维手册

## 约束

- CLI 必须可本地运行（`pip install -e python/ && wucur checkin --help`）
- 每个命令必须有单元测试
- Provider 通过 Protocol 定义接口，新增 provider 只需实现接口 + 注册
- results.json 格式固定，callback 命令不关心内容语义
- Kiro 注册保持 Node.js 实现，Python CLI 通过 subprocess 调用
- 不依赖 CI 环境特有的东西（如 PowerShell），统一用 Python
- `status` 字段：签到/注册失败不标记 `failed`，保持 `active`（只有手动封禁才用 `suspended`）

## 现有 pyproject.toml 入口

```toml
[project.scripts]
wucur = "wucur_cli.cli:main"        # 已存在，当前是旧版 CLI
checkin-due = "cli.checkin_due_cli:main"
site_cli = "cli.site_cli:main"
```

**改造方式：** 保留 `wucur` 入口名，将 `wucur_cli.cli:main` 替换为新的 typer app。旧的 `wucur_cli/` 目录废弃删除。

## GitLab 仓库的特殊处理

GitLab 仓库（`gitlab.com/kiro.dev/kiro`）只有 `node-register/`，没有 Python 代码。

**方案：**
- `register_wucur` job：不依赖 Python CLI，保持 alpine + curl + jq 的 shell 脚本（当前实现已可用，逻辑简单无需 CLI 化）
- `register_kiro_api` job：保持 Node.js 直接运行
- 回调逻辑：GitLab 保持 shell 实现（`curl -X POST`），不引入 Python 依赖
- **只有 GitHub 仓库的 workflow 改为使用 `wucur` CLI**

## 现有代码复用说明

| 模块 | 处理方式 |
|------|----------|
| `python/src/providers/wucur.py` | **直接复用**，已实现 Provider 接口 |
| `python/src/pipelines/checkin.py` | **直接复用**，CheckinPipeline 调用 provider |
| `python/src/core/result.py` | **直接复用**，Result 类型 |
| `python/src/scripts/checkin_batch.py` | Phase 3 完成后**删除**，被 `wucur checkin` 替代 |
| `python/src/scripts/kiro_refresh.py` | Phase 4 完成后**删除**，被 `wucur refresh` 替代 |
| `python/src/wucur_cli/` | Phase 1 完成后**删除**，被新 CLI 替代 |

## Phase 依赖关系

```
Phase 1 (callback) ← 无依赖，可立即开始
Phase 2 (register) ← 依赖 Phase 1（注册完需要 callback）
Phase 3 (checkin)  ← 依赖 Phase 1（签到完需要 callback）
Phase 4 (refresh)  ← 依赖 Phase 1
Phase 5 (清理)    ← 依赖 Phase 1-4 全部完成

Phase 2 和 Phase 3 可并行。
```

## 验收标准

### Phase 1 验收

```bash
# 本地测试
echo '[{"username":"test@qq.com","status":"active","last_result":"测试"}]' > /tmp/test_results.json
CALLBACK_URL=https://worker-dashboard.ouraihub.workers.dev/callback \
CALLBACK_SECRET=test_secret \
wucur callback --file /tmp/test_results.json
# 预期：输出 {"ok":true}

# CI 验证：任意 workflow 触发后，Worker Dashboard 日志页面能看到回调记录
```

### Phase 2 验收

```bash
# 本地测试 wucur 注册
wucur register --provider wucur --count 1 --output /tmp/reg.json
cat /tmp/reg.json
# 预期：[{"username":"xxx@qq.com","password":"123Claude&Codex","status":"active",...}]

# CI 验证：GitHub Actions register workflow 触发后，Worker Dashboard 账号列表出现新账号
```

### Phase 3 验收

```bash
# 本地测试签到
echo '[{"username":"basil8ox@qq.com","password":"123Claude&Codex"}]' > /tmp/accts.json
wucur checkin --file /tmp/accts.json --output /tmp/checkin.json
cat /tmp/checkin.json
# 预期：[{"username":"basil8ox@qq.com","status":"active","balance":"12.26",...}]

# 单元测试通过
cd python && pytest tests/test_checkin.py -v
```

### Phase 4 验收

```bash
# 本地测试刷新
CF_ACCOUNT_ID=xxx CF_API_TOKEN=xxx KV_NAMESPACE_ID=xxx \
wucur refresh --target xxx@ouraihub.com --output /tmp/refresh.json
# 预期：results.json 包含新的 access_token

# CI 验证：Dashboard 点刷新后，kiro 账号的 last_refresh_at 更新
```

### Phase 5 验收

```bash
# 确认旧文件已删除
test ! -f python/src/scripts/checkin_batch.py
test ! -f python/src/scripts/kiro_refresh.py
test ! -d python/src/wucur_cli

# 全部测试通过
cd python && pytest -v

# 所有 workflow 正常运行（手动触发一次验证）
```
