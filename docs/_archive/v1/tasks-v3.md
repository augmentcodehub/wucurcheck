# AnyRouter / Wucur 自动签到与云端同步 — Tasks（v3）

> 目标：把设计切成可独立执行、可独立验证的任务。  
> 前提：requirements / design 无阻断项。

## 1. 关联文档

- 需求：`requirements-v3.md`
- 设计：`design-v3.md`
- 项目规范：`CLAUDE.md` / `AGENTS.md`
- 外部后端参考实现（GitHub）：`https://github.com/ohwiki/msgflow`
- 现有测试：`tests/test_wucur_client.py`、`tests/test_checkin_due_service.py`

## 2. 项目类型

- 维护型项目 + 新结构落地

## 3. 总目标

完成本地 CLI / SQLite / 补签到 / provider/profile / 云端触发 / KV 适配的统一业务骨架，并把核心能力落到 `core/domain`、`core/application`、`core/ports`、`core/infrastructure`、`cli/`、`worker-dashboard/`（Cloudflare Worker 管理后台目录）上，同时保持现有可用入口不坏。

## 4. 执行前检查

- [ ] requirements 没有未关闭阻断项
- [ ] design 已选定方案
- [ ] 已明确维护型与新结构并存
- [ ] 本地测试可运行
- [ ] 云端部署动作默认不执行

## 5. 全局边界

### 默认禁止

- `git commit`
- `git push`
- 部署 / 发布
- 修改远程环境
- 改动无关脚本

### 如果本次允许，必须显式列出

| 动作 | 是否允许 | 授权来源 |
|---|---|---|
| `git commit` | 否 | 无 |
| `git push` | 否 | 无 |
| 部署/触发 CI | 否 | 无 |

## 6. 需求追踪

| Requirement | 由哪些 task 覆盖 | 最终验证 |
|---|---|---|
| 基座 | T0 | 包导入测试 |
| R1 | T3 | 注册测试 |
| R2 | T4 | 查询测试 |
| R3 | T5 | 补签到测试 |
| R4 | T6 | KV 仓库测试 |
| R5 | T7 | Worker 触发测试 |
| R6 | T1, T3, T4, T5, T6 | 记录字段测试 |
| R7 | T2 | provider/profile 抽象测试 |
| R8 | T8 | Worker 管理后台 UI |

## 7. 执行顺序

```text
T0 -> T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8
```

## 8. 拆分原则

- 每个 task 只做一个可独立验证目标
- 先补项目骨架，再抽公共模型，再抽 provider/profile，再接存储，再接入口
- 维护型入口脚本负责薄包装，核心逻辑下沉到 `core/`
- Worker 和 GitHub 触发放到最后

## 9. Task 0: 补项目骨架与 Cloudflare Worker 入口

**目标：**
把 `core/`、`cli/`、`worker-dashboard/` 先补成可落地的项目骨架，确保后续分层任务有稳定落点。

**覆盖需求：**
R1-R7

**任务类型：**
维护型：补最小基座

**前置依赖：**
无

**允许修改的文件：**

- `pyproject.toml`
- `core/__init__.py`
- `core/application/__init__.py`
- `core/infrastructure/__init__.py`
- `core/ports/__init__.py`
- `cli/__init__.py`
- `tests/test_package_layout.py`
- `tests/test_worker_layout.py`
- `worker-dashboard/wrangler.toml`
- `worker-dashboard/src/index.js`

**允许修改的符号：**

- `test_core_cli_packages_are_importable`
- `test_worker_layout_has_cloudflare_entrypoint`

**禁止修改的文件：**

- `checkin.py`
- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `tests/test_worker_layout.node.mjs`

**禁止修改的符号：**

- `run_main`
- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`
- `CheckinDueService`

**禁止行为：**

- 不引入业务规则
- 不改现有 CLI 行为

**实施步骤：**

1. 让 `pyproject.toml` 识别 `core/`、`cli/` Python 包，并保持 `worker-dashboard/` 只作为 Cloudflare Worker 管理后台目录。
2. 补齐 `core/`、`cli/` 的包级 `__init__.py`，并落地 `worker-dashboard/wrangler.toml` 与 `worker-dashboard/src/index.js`。
3. 增加包/入口检查测试。

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run pytest tests/test_package_layout.py tests/test_worker_layout.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/`、`cli/`、`worker-dashboard/` 目录存在且入口文件齐全，Worker 先只落骨架

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 CLI 入口 | `uv run pytest tests/test_wucur_cli.py -q` | 继续通过 |
| Worker 合约 | `node --test tests/test_worker_layout.node.mjs` | 继续通过 |

**完成标准：**

- 新分层目录可被测试和后续代码直接引用
- 任务 1-7 有稳定落点

**清理步骤：**

- 无

## 9. Task 1: 抽统一领域模型

**目标：**
定义账户、余额、签到结果、到期判断的统一数据结构。

**覆盖需求：**
R3, R6

**任务类型：**
维护型：抽统一模型

**前置依赖：**
无

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**如果是维护型项目：现有改动点**

- 文件：`scripts/checkin_due_domain.py`
- 符号：现有 domain dataclass
- 为什么在这里改：这是目前最接近领域层的代码

**允许修改的文件：**

- `core/domain.py`
- `scripts/checkin_due_domain.py`
- `tests/test_checkin_due_domain.py`

**允许修改的符号：**

- `StoredAccountRecord`
- `CheckinDuePlanItem`
- `CheckinSuccessUpdate`
- `CheckinDueSummary`
- `parse_checkin_date`
- `normalize_timezone`
- `resolve_as_of_date`
- `classify_due_accounts`
- `build_success_update`

**禁止修改的文件：**

- `checkin.py`
- `utils/notify.py`

**禁止行为：**

- 不引入存储实现
- 不引入 CLI 逻辑

**实施步骤：**

1. 把现有 domain dataclass 整理成 `core/domain.py` 的统一记录模型。
2. 补足余额、签到、到期判断、`provider` / `registration_info` / `last_checkin_at` 的字段说明。
3. 新增/更新单元测试，验证字段和规则。

**预期产物：**

- 统一的 domain 数据模型
- domain 单测通过

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 命令 | `uv run pytest tests/test_checkin_due_domain.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 domain 测试 | `uv run pytest tests/test_checkin_due_domain.py -q` | 全绿 |

**产物检查：**

- `core/domain.py` 存在
- `scripts/checkin_due_domain.py` 仍可作为回归入口

**清理步骤：**

- 无

**完成标准：**

- 统一模型字段明确
- 到期判定逻辑可复用

## 10. Task 2: 抽 provider/profile 适配边界

**目标：**
把站点能力、路径、默认值和账号约束从业务用例里抽成统一的 `ProviderProfile` / `ProviderProfileResolver`，让 `wucur` 只是当前验证对象之一，而不是硬编码依赖。

**覆盖需求：**
R7

**前置依赖：**

T1

**任务类型：**
维护型：抽现有 provider 配置结构

**允许修改的文件：**

- `core/provider_profile.py`
- `utils/config.py`
- `tests/test_provider_profile.py`
- `tests/test_auth_flow.py`

**允许修改的符号：**

- `ProviderProfile`
- `ProviderProfileResolver`
- `AppConfig`
- `ProviderConfig`

**禁止修改的符号：**

- `run_main`
- `CheckinDueService`
- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `CloudflareKvAccountRepository`
- `SyncRemoteTriggerUseCase`

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/register_one_account.py`
- `scripts/register_one_account_to_db.py`
- `scripts/checkin_due_service.py`

**禁止行为：**

- 不把 `wucur` 写死在新 use case 中
- 不接入第二个网站实现
- 不改 CLI 参数名

**实施步骤：**

1. 抽出 profile 数据结构和 resolver。
2. 把现有 provider 配置迁移到 profile 定义或映射表。
3. 补测试，验证新增网站只需要新增 profile 配置，不需要改业务用例。

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run pytest tests/test_provider_profile.py tests/test_auth_flow.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**产物检查：**

- `core/provider_profile.py` 存在
- `utils/config.py` 仍可加载内置 provider

**清理步骤：**

- 无

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 provider 配置 | 现有测试 | 继续通过 |

**完成标准：**

- 站点能力和默认值不再散落在 use case 里
- 新网站只需要新增 profile/adapter

## 11. Task 3: 抽注册+签到用例

**目标：**
把注册、登录、签到、余额拉取收敛成一个 application use case。

**覆盖需求：**
R1, R6

**任务类型：**
维护型：抽应用层用例

**前置依赖：**
T2

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**允许修改的文件：**

- `core/application/register_and_checkin_account_use_case.py`
- `core/ports/account_repository.py`
- `core/ports/checkin_client.py`
- `checkin.py`
- `scripts/register_wucur.py`
- `scripts/register_one_account.py`
- `scripts/register_one_account_to_db.py`
- `scripts/wucur_client.py`
- `tests/test_register_one_account_to_db.py`
- `tests/test_register_and_checkin_account_use_case.py`（如新增）

**允许修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `append_account_record`
- `build_authenticated_headers`
- `register_account`
- `login_account`
- `checkin_account`
- `get_user_info`
- `extract_login_user_id_from_payload`
- `extract_balance_summary`
- `main`（`checkin.py`）
- `main`（`scripts/register_wucur.py`）

**禁止修改的文件：**

- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/infrastructure/cloudflare_kv_account_repository.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `CloudflareKvAccountRepository`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不改变 CLI 参数名
- 不改变已有输出中关键字段名

**实施步骤：**

1. 把注册、登录、签到、余额拉取收敛到 `core/application/register_and_checkin_account_use_case.py`。
2. 统一 payload 归一化逻辑，并把站点调用收敛到 `core/ports/checkin_client.py`。
3. 把余额提取改为兼容 summary / raw payload，并补回归测试。

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run pytest tests/test_wucur_client.py tests/test_register_one_account_to_db.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/application/register_and_checkin_account_use_case.py` 存在
- `core/ports/checkin_client.py` 存在
- `core/ports/account_repository.py` 存在
- `checkin.py` 仍保持薄入口

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 注册脚本输出 | 现有测试 | 继续通过 |

| 现有注册入口 | `uv run pytest tests/test_register_one_account_to_db.py -q` | 继续通过 |

**清理步骤：**

- 无

## 12. Task 4: 抽查询用例与 CLI 查询

**目标：**
把数据库查询从脚本输出中抽成稳定查询用例。

**覆盖需求：**
R2, R6

**前置依赖：**

T3

**允许修改的文件：**

- `core/application/list_accounts_use_case.py`
- `cli/query.py`（如新增）
- `scripts/query_wucur_accounts_db.py`
- `tests/test_query_wucur_accounts_db.py`（如新增）

**允许修改的符号：**

- `ListAccountsUseCase`
- `fetch_rows`
- `print_table`
- `format_value`
- `display_width`
- `pad_display`
- `main`（`scripts/query_wucur_accounts_db.py`）

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `CheckDueAccountsUseCase`
- `CloudflareKvAccountRepository`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不写入数据库
- 不修改签到逻辑

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/infrastructure/cloudflare_kv_account_repository.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `CheckDueAccountsUseCase`
- `CloudflareKvAccountRepository`
- `SyncRemoteTriggerUseCase`

**实施步骤：**

1. 把数据库查询抽成 `core/application/list_accounts_use_case.py`。
2. 保持 CLI 输出格式稳定，并把脚本收敛成薄入口。
3. 补测试，并确保查询输出包含完整字段。

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run scripts/query_wucur_accounts_db.py --limit 3` |
| 预期退出码 | `0` |
| 必须出现 | 表格输出 |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/application/list_accounts_use_case.py` 存在
- `scripts/query_wucur_accounts_db.py` 仍可作为薄入口运行

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有查询测试 | `uv run pytest tests/test_query_wucur_accounts_db.py -q` | 继续通过 |

**完成标准：**

- 查询输出包含完整字段
- 薄入口不承担查询业务规则

**清理步骤：**

- 无

## 13. Task 5: 抽补签到用例

**目标：**
把今天没签到的账号批量补签到，并保证今天已签到的记录不重复处理。

**覆盖需求：**
R3, R6

**前置依赖：**

T4

**允许修改的文件：**

- `core/application/check_due_accounts_use_case.py`
- `scripts/checkin_due_service.py`
- `tests/test_checkin_due_service.py`

**允许修改的符号：**

- `CheckDueAccountsUseCase`
- `CheckinDueService`
- `CheckinAccountResult`
- `run_account_checkin`
- `run`（`scripts/checkin_due_service.py`）
- `main`（`scripts/checkin_due_service.py`）

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CloudflareKvAccountRepository`
- `SyncRemoteTriggerUseCase`

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_repository.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/infrastructure/cloudflare_kv_account_repository.py`
- `worker-dashboard/`

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run pytest tests/test_checkin_due_service.py tests/test_checkin_due_repository.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/application/check_due_accounts_use_case.py` 存在
- `scripts/checkin_due_service.py` 仍作为回归入口存在

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有补签到测试 | `uv run pytest tests/test_checkin_due_service.py tests/test_checkin_due_repository.py -q` | 继续通过 |

**完成标准：**

- 到期判断和补签到编排落到 `core/application/check_due_accounts_use_case.py`
- 今天已签到的记录不会重复处理

**清理步骤：**

- 无

## 14. Task 6: 增加 Cloudflare KV repository

**目标：**
增加云端存储适配，实现和 SQLite 同构的账号记录读写。

**覆盖需求：**
R4, R6

**前置依赖：**

T5

**允许修改的文件：**

- `core/infrastructure/cloudflare_kv_account_repository.py`
- `scripts/checkin_due_repository.py`
- `tests/test_checkin_due_repository.py`
- `tests/test_cloudflare_kv_account_repository.py`（如新增）

**允许修改的符号：**

- `SqliteCheckinDueRepository`
- `CloudflareKvAccountRepository`
- `build_backend_repository`
- `_record_from_row`
- `_record_from_mapping`
- `_build_success_payload`

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_domain.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**清理步骤：**

- 无

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `uv run pytest tests/test_checkin_due_repository.py tests/test_cloudflare_kv_account_repository.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/infrastructure/cloudflare_kv_account_repository.py` 存在
- `tests/test_cloudflare_kv_account_repository.py` 存在且通过

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有仓库测试 | `uv run pytest tests/test_checkin_due_repository.py -q` | 继续通过 |

**完成标准：**

- Cloudflare KV 仓库实现与 SQLite 同构
- 云端写入字段与设计中的 `AccountRecord` 一致
- 仓库符号名对齐设计中的 `CloudflareKvAccountRepository`
- 云端写入前必须加密密码，密钥缺失时返回配置错误并停止写入

**清理步骤：**

- 无

## 15. Task 7: 增加 Worker 触发入口

**目标：**
Worker 只做页面、鉴权、触发 GitHub Actions，不执行签到；默认 workflow 和 dispatch 失败都要可判定。

**覆盖需求：**
R5

**前置依赖：**

T6

**允许修改的文件：**

- `core/application/sync_remote_trigger_use_case.py`
- `core/ports/github_dispatch.py`
- `worker-dashboard/` 新增骨架
- `worker-dashboard/wrangler.toml`
- `worker-dashboard/src/index.js`
- `tests/test_worker_layout.py`
- `tests/test_worker_layout.node.mjs`

**允许修改的符号：**

- `SyncRemoteTriggerUseCase`
- `GitHubDispatchPort`
- `fetch`
- `ok`
- `unauthorized`

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/infrastructure/cloudflare_kv_account_repository.py`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `CloudflareKvAccountRepository`

**清理步骤：**

- 无

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `node --test tests/test_worker_layout.node.mjs` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |

**产物检查：**

- `core/application/sync_remote_trigger_use_case.py` 存在
- `worker-dashboard/` 目录存在并包含触发入口

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| Worker 合约检查 | `node --test tests/test_worker_layout.node.mjs` | 继续保留页面/鉴权/触发语义 |

**完成标准：**

- `SyncRemoteTriggerUseCase` 和 worker handler 负责触发链路
- Worker 只负责页面、鉴权和触发
- 不在 Worker 内执行签到
- 默认 workflow 为 `checkin`，鉴权失败和 dispatch 失败都有稳定返回

**清理步骤：**

- 无

## 16. Task 8: 增加 Worker 管理后台 UI

**目标：**
Worker 直接提供可视化管理页，能查看账号列表、账号详情、执行结果，并手动触发签到。

**覆盖需求：**
R8

**前置依赖：**

T7

**允许修改的文件：**

- `worker-dashboard/`
- `tests/test_worker_layout.node.mjs`
- `tests/test_worker_admin_ui.node.mjs`
- `design-v3.md`

**允许修改的符号：**

- `worker-dashboard` admin UI 相关入口
- 账号列表渲染
- 详情抽屉 / 弹窗
- 手动触发按钮
- `renderAdminPage`
- `renderAccountList`
- `renderAccountDetail`

**前置准备：**

- 工作目录：`E:\workspace\ai-sign-dev\anyrouter-check-in`
- 确认 `uv run` 可用

**禁止行为：**

- 不把 UI 拆成独立前端应用
- 不在 UI 里直接执行签到
- 不引入额外登录系统

**验证：**

| 项目 | 内容 |
|---|---|
| 命令 | `node --test tests/test_worker_admin_ui.node.mjs` |
| 预期退出码 | `0` |
| 必须出现 | 页面可见信息与触发控件 |
| 禁止出现 | `FAILED` |

**产物检查：**

- `worker-dashboard` 直接返回后台页面
- 页面包含账号列表和手动触发入口

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| UI 页面 | `node --test tests/test_worker_admin_ui.node.mjs` | 页面能展示账号并触发 |

**完成标准：**

- 后台 UI 可用于查看账号和触发签到
- UI 交互与 `daisyUI` / Nexus 风格保持一致

**清理步骤：**

- 无

## 17. 验证标准汇总

| Task | 工作目录 | 命令 | 预期退出码 | 必须出现 | 禁止出现 | 通过标准 |
|---|---|---|---|---|---|---|
| T0 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_package_layout.py -q` | `0` | `passed` | `FAILED` | 包骨架通过 |
| T1 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_domain.py -q` | `0` | `passed` | `FAILED` | domain 通过 |
| T2 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_provider_profile.py tests/test_auth_flow.py tests/test_wucur_client.py -q` | `0` | `passed` | `FAILED` | provider/profile 通过 |
| T3 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_wucur_client.py tests/test_register_one_account_to_db.py -q` | `0` | `passed` | `FAILED` | 注册链路通过 |
| T4 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run scripts/query_wucur_accounts_db.py --limit 3` | `0` | 表格输出 | `FAILED` | 查询可用 |
| T5 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_service.py tests/test_checkin_due_repository.py -q` | `0` | `passed` | `FAILED` | 补签到通过 |
| T6 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_repository.py -q` | `0` | `passed` | `FAILED` | Cloudflare KV 仓库通过 |
| T7 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `node --test tests/test_worker_layout.node.mjs` | `0` | `passed` | `FAILED` | Worker 触发通过 |
| T8 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `node --test tests/test_worker_admin_ui.node.mjs` | `0` | `passed` | `FAILED` | Worker 管理后台 UI 通过 |

## 17. 交付完成定义

全部 task 完成后，必须同时满足：

1. 核心用例已统一。
2. provider/profile 已作为独立边界落地。
3. SQLite 和 KV 适配都存在。
4. CLI、Worker、GitHub Actions 的边界明确。
5. 现有可用命令未被误伤。
6. 最终端到端验证通过。

## 18. 拆分质量自检

- [ ] 每个 task 都只有一个独立目标
- [ ] 已明确当前是维护型项目还是新项目
- [ ] 每个 task 都明确了允许修改 / 禁止修改的文件和符号
- [ ] 每个 task 都给了机器可判定验证格式
- [ ] 每个 task 都有回归验证
- [ ] 执行顺序和依赖关系清楚

## 19. 完成判定 Checklist

> 这个清单用于判断某个 task 是否“真的完成”，不是只看文档有没有写完。

- [ ] 任务要求的文件或符号已经存在，或已明确标注为 `如新增`
- [ ] 任务要求的验证命令在本地实际跑过，且退出码为 `0`
- [ ] 输出里没有 `FAILED`
- [ ] 回归验证对应的既有测试也通过
- [ ] 产物检查里的关键路径/文件名都能在仓库中找到
- [ ] 完成标准里的每一条都能被代码或测试直接佐证
- [ ] 如果任务依赖前置任务，前置任务的产物已存在
- [ ] 如果任务涉及 UI 或 Worker，页面/路由/触发链路已被测试覆盖
- [ ] 如果任务涉及云端仓库，写入/读取/错误码都有测试

### 当前状态速览

- [x] T0: 基座与 Worker 骨架
- [x] T1: domain 统一模型
- [x] T2: provider/profile 边界
- [x] T3: 注册 + 签到用例
- [x] T4: 查询用例与 CLI
- [x] T5: 补签到用例
- [x] T6: Cloudflare KV repository
- [x] T7: Worker 触发入口
- [x] T8: Worker 管理后台 UI
