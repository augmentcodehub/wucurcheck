# AGENTS.md

wucurcheck — 多平台账号管理（注册、签到、刷新）。Python + Worker + Node。

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
│   ├── src/             # 源码（六边形架构）
│   │   ├── core/        # 领域层（domain + ports + application）
│   │   ├── adapters/    # 适配器层（实现 ports）
│   │   ├── cli/         # CLI 入口
│   │   ├── scripts/     # 独立脚本
│   │   ├── tools/       # 工具（账号生成、导出等）
│   │   ├── utils/       # 通用工具
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
- ❌ 在 `python/src/` 下创建新的顶层子目录（已有 core/adapters/cli/scripts/tools/utils/wucur_cli）
- ❌ 修改 `python/src/core/ports/` 的接口签名（除非明确要求）
- ❌ 在 Worker 代码里放 Python，或反过来

**Python 架构约束（六边形架构）：**

- `core/ports/` — Protocol 接口定义（只有接口，无实现）
- `core/application/` — Use Case（依赖注入，不直接 import adapter）
- `core/domain.py` — 纯值对象（frozen dataclass）
- `adapters/` — 实现 ports 接口
- 依赖方向：adapters → core，永远不能反过来
