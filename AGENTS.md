# AGENTS.md

wucurcheck — 多平台账号管理（注册、签到、刷新）。Python + Worker + Node。

## 必读规范

- **日志与异常规范**：[docs/logging-standards.md](docs/logging-standards.md) — 所有代码必须遵守
- **运维手册**：[docs/ops-manual.md](docs/ops-manual.md) — KV 查询、部署、问题排查

## 开发

```bash
# Python
cd python && uv sync && uv run pytest

# Worker
cd worker-dashboard && npm install && npx wrangler dev

# Node register
cd node-register && npm install && npm test
```

## 文件放置规范（严格遵守）

**白名单制 — 只允许在以下位置创建/修改文件：**

| 路径 | 允许放什么 |
|------|-----------|
| `python/src/` | Python 源码（唯一 Python 源码目录） |
| `python/tests/` | Python 测试 |
| `worker-dashboard/src/` | Worker TypeScript 源码 |
| `node-register/` | Node.js 注册脚本 |
| `docs/` | 项目文档（Markdown） |
| `.github/workflows/` | GitHub Actions |

**已有的目录结构（不得新增顶层目录）：**

```
wucurcheck/
├── python/              # Python 主代码
│   ├── src/             # 源码
│   │   ├── core/        # 领域层（Result, domain, ports）
│   │   ├── providers/   # Provider 实现（wucur, anyrouter, kiro）
│   │   ├── pipelines/   # Pipeline 编排（checkin, register）
│   │   ├── lib/         # 共享基础设施（constants, http, registry）
│   │   ├── adapters/    # 旧适配器层（逐步迁移到 providers）
│   │   ├── cli/         # CLI 入口
│   │   ├── scripts/     # GitHub Actions 入口脚本（薄壳）
│   │   ├── tools/       # 工具（账号生成、导出等）
│   │   ├── utils/       # 通用工具（logger, notify, config）
│   │   └── wucur_cli/   # 统一 CLI 包
│   └── tests/           # 测试
├── worker-dashboard/    # Cloudflare Worker 管理面板
├── node-register/       # Node.js 注册自动化
├── docs/                # 文档
├── assets/              # 静态资源
├── artifacts/           # 生成产物（数据库等）
└── .github/             # CI/CD
```

**根目录允许的文件（不得新增）：**

```
README.md
AGENTS.md
pyproject.toml
uv.lock
checkin.py
.gitignore
.env.example
.python-version
.editorconfig
.pre-commit-config.yaml
.codecov.yml
CONTRIBUTING.md
LICENSE
```

**绝对禁止：**

- ❌ 创建新的顶层目录
- ❌ 在 `python/src/` 外放 Python 源码
- ❌ 修改 `python/src/core/ports/` 的接口签名（除非明确要求）
- ❌ 在 Worker 代码里放 Python，或反过来

**Python 架构约束：**

- `providers/` — Provider 实现（@registry.register 装饰器注册，无状态策略对象）
- `pipelines/` — Pipeline 编排（组合 Provider 方法，管理 httpx.Client 生命周期）
- `lib/` — 共享基础设施（constants, http 工具函数, registry, balance_tracker, notify_formatter）
- `core/result.py` — 统一返回值（Result.ok / Result.fail）
- `cli/register.py` — 统一注册入口（`--provider kiro|wucur`，替代独立的 register_kiro.py / register_wucur.py）
- `cli/checkin.py` — 全功能签到（WAF 绕过 + 多登录模式，由 checkin.yml 调用）
- `scripts/checkin_batch.py` — 轻量批量签到（Pipeline 模式，由 checkin_batch.yml 调用）
- `scripts/` — GitHub Actions 入口（薄壳，只做 IO，业务逻辑在 pipeline）
- 依赖方向：scripts → pipelines → providers → lib/core
