# AnyRouter / Wucur 消息驱动签到与存储统一 - 任务（v4，双模型流水线版）

> 目标：把已合格设计拆成可独立执行、可独立验证、且不会自己发散出新需求的任务。  
> 前提：requirements / design 已无未关闭阻断项，且 task 能逐条追到具体 design 项。

## 1. 关联文档

- 需求：`docs/requirements-v4.md`
- 设计：`docs/design-v4.md`
- 任务门禁：`docs/tasks-acceptance-gate-v4.md`（如后续补充；当前以本文件为准）
- 项目规范：`CLAUDE.md` / `AGENTS.md`
- 参考实现：`msgflow/worker/lib/command.js`、`msgflow/worker/lib/github.js`
- 现有测试：`tests/test_provider_profile.py`、`tests/test_checkin_due_domain.py`、`tests/test_wucur_cli.py`、`tests/test_checkin_due_service.py`、`tests/test_checkin_due_repository.py`、`tests/test_sync_remote_trigger_use_case.py`、`tests/test_worker_layout.node.mjs`

## 2. 项目类型

### 项目类型

- 维护型项目 + 局部新结构

### 为什么属于这一类

- 仓库已经有 domain、provider/profile、注册、查询、补签到、Worker 触发和 SQLite/KV 适配的雏形，不是从零开始。
- 本次重点是把现有脚本、core、CLI、Worker 入口收敛成统一业务层与薄入口，而不是重写整个产品。

### 本次拆分重点

- 先固定 domain / profile / ports 边界，再落 request normalizer 和 command dispatcher。
- 再把注册、查询、补签到拆成稳定 application use case。
- 再把存储适配、Worker 触发和消息入口收敛到各自 adapter。
- 兼容入口保留，但不把旧脚本继续当主业务层。

## 3. 总目标

一套统一的签到核心可以同时被 `site_cli`、旧兼容脚本、Worker 管理后台和消息入口复用，本地走 SQLite，云端走 KV，且注册 / 查询 / 补签到 / 触发链路都能稳定回归。

### 3.1 任务执行看板

> 这个看板是执行过程的唯一进度来源。执行时先更新这里，再继续下一步。

| 任务ID | 设计项ID | 状态 | 当前步骤 | 最后证据 | 阻塞原因 |
|---|---|---|---|---|---|
| T1 | D7, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T2 | D6, D8, D9, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T3 | D1, D7, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T4 | D2, D7, D8, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T5 | D3, D9, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T6 | D4, D7, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T7 | D5, D7, D10, D11 | 已完成 | 验证完成 | `pytest` | - |
| T8 | D5, D8, D10, D11 | 已完成 | 验证完成 | `pytest + node` | - |
| T9 | D1, D2, D3, D6, D8, D10, D11 | 已完成 | 验证完成 | `pytest` | - |

### 3.2 状态规则

- 开始执行前，先把对应任务状态改成 `进行中`。
- 每完成一个步骤，就更新当前步骤和最后证据。
- 只有验证和回归验证都通过，任务才能改成 `已完成`。
- 卡住时必须写清阻塞原因和等待条件。
- 任意时刻默认只允许一个任务处于 `进行中`，除非执行顺序里显式标注并行。

## 4. 执行前检查

- [ ] requirements 中没有未关闭阻断项
- [ ] design 中方案已选定，patch point 已明确
- [ ] 每个 task 都能追到至少一个 design 项
- [ ] task 中没有 design 外的新外显行为
- [ ] 已明确当前是维护型项目还是新项目
- [ ] 本地环境、依赖、凭据已满足
- [ ] 已确认是否允许新增依赖
- [ ] 已确认默认禁止的外部动作是否有例外授权

## 5. 全局边界

### 默认禁止

- `git commit`
- `git push`
- 部署 / 发布
- 修改远程环境
- 顺手重构与当前需求无关的代码
- 设计中没有出现的新需求、新接口、新字段、新错误语义、新权限边界、新副作用、新持久化规则

### 如果本次允许，必须显式列出

| 动作 | 是否允许 | 授权来源 |
|---|---|---|
| `git commit` | 否 | 无 |
| `git push` | 否 | 无 |
| 部署 / 触发 CI | 否 | 无 |

## 6. 设计追踪

| 设计项ID | 来源类型 | 来源需求ID | 由哪些任务覆盖 | 是否允许新增外显行为 | 最终验证 |
|---|---|---|---|---|---|
| D1 | REQ | R1 | T3, T9 | 否 | 注册链路单测 + 消息入口测试 |
| D2 | REQ | R2 | T4, T9 | 否 | 查询链路单测 + 消息入口测试 |
| D3 | REQ | R3 | T5, T9 | 否 | 补签到链路单测 + 消息入口测试 |
| D4 | REQ | R4 | T6 | 否 | SQLite 仓库测试 |
| D5 | REQ | R5 | T7, T8 | 否 | KV 仓库测试 + Worker 触发测试 |
| D6 | REQ | R6 | T2, T9 | 否 | request normalizer / message ingress 测试 |
| D7 | REQ | R7 | T1, T3, T4, T5, T6, T7 | 否 | 记录字段与回放测试 |
| D8 | REQ | R8 | T2, T4, T8, T9 | 否 | `site_cli` / Worker / 消息入口测试 |
| D9 | REQ | R9 | T2, T5 | 否 | 默认 `due` 语义测试 |
| D10 | IMPL | R1-R9 | T1-T9 | 否 | 各 task 验证与回归验证 |
| D11 | TEST | R1-R9 | T1-T9 | 否 | 各 task 的验证命令与回归命令 |
| D12 | OUT | 无 | 无 | 否 | 不进入 tasks |

规则：
- 每个 task 必须至少映射到一个 design 项。
- 如果一个 task 无法映射到 design 项，就必须回到 design，不得进入 tasks。
- `OUT` 项不能被 task 覆盖。
- 如果一个 design 项没有被任何 task 覆盖，说明 tasks 漏项。

## 7. 执行顺序

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9
```

## 8. 拆分原则

### 如果是维护型项目

- task 应围绕现有 patch point 拆分
- task 应尽量让一个 task 对应一个现有文件中的一个关键符号或一组紧密相关符号
- task 必须显式包含回归验证
- task 不应把“改现有逻辑”和“新建大块结构”混在一起

### 如果是新项目

- task 应优先按结构落地顺序拆分
- 常见顺序通常是：
  - 先搭目录 / 模块 / 组件骨架
  - 再落关键入口和关键数据结构
  - 再补核心逻辑
  - 再补测试和回归基线
- task 不应一开始就把多个模块和多个层级混在同一个任务里
- task 必须严格继承 design 里的模块 / 组件 / 关键文件边界

### 共同规则

- 一个 task 只做一个独立目标
- 一个 task 必须有独立验证闭环
- 一个 task 不能自己补出 design 没有的新能力
- 如果一个 task 需要跨多个模块 / 组件，必须说明为什么不能再拆

## 9. Task 模板

> 为每个 task 复制以下结构。不要省略“来源设计项”“禁止修改”“目标符号”“回归验证”。

### T1: 锁定领域模型与 profile 边界

**目标：**  
把 `StoredAccountRecord`、`CheckinSuccessUpdate`、`ProviderProfile`、`ProviderProfileResolver` 的字段、默认值和错误语义固定下来，让后续 use case 只能依赖稳定边界。

**覆盖设计：**  
D7 / D10 / D11

**覆盖需求：**  
R6 / R7

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
无

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 domain / profile / port 的现有符号 | 明确哪些字段是稳定契约，哪些字段只能作为实现细节 | 已完成 | `core/domain.py` / `core/provider_profile.py` / `core/ports/*.py` |
| S2 | 收敛字段、默认值和错误语义 | `StoredAccountRecord` 与 `ProviderProfile` 的对外字段不再漂移 | 已完成 | diff / tests |
| S3 | 运行验证 | domain 与 profile 单测全绿 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`core/domain.py`
- 文件：`core/provider_profile.py`
- 文件：`core/ports/account_repository.py`
- 文件：`core/ports/checkin_client.py`
- 文件：`core/ports/github_dispatch.py`
- 为什么在这里改：这是注册、查询、补签到、Worker 触发共享的最底层契约。

**允许修改的文件：**

- `core/domain.py`
- `core/provider_profile.py`
- `core/ports/account_repository.py`
- `core/ports/checkin_client.py`
- `core/ports/github_dispatch.py`
- `tests/test_checkin_due_domain.py`
- `tests/test_provider_profile.py`
- `tests/test_auth_flow.py`

**允许修改的符号：**

- `StoredAccountRecord`
- `CheckinSuccessUpdate`
- `CheckinDueSummary`
- `ProviderProfile`
- `ProviderProfileResolver`
- `parse_checkin_date()`
- `normalize_timezone()`
- `resolve_as_of_date()`
- `classify_due_accounts()`
- `build_success_update()`

**禁止修改的文件：**

- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不新增 design 里没有的外显行为
- 不把 request 默认值塞进 domain
- 不把 message / CLI / Worker 的行为混进 core model
- 不引入第二个网站能力

**实施步骤：**

1. 固定 record / update 的字段集合和回放字段。
2. 固定 provider profile 的默认值、错误码和能力标记。
3. 补 profile 与 domain 的单测，确认字段和错误语义不会漂移。

**实现参考：**

- `core/domain.py`
- `core/provider_profile.py`
- `tests/test_checkin_due_domain.py`
- `tests/test_provider_profile.py`

**预期产物：**

- 稳定的领域模型
- 稳定的 provider/profile 边界
- 与设计一致的记录字段和错误语义

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_checkin_due_domain.py tests/test_provider_profile.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | 关键 dataclass / resolver 符号仍可导入 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 auth/provider 测试 | `uv run pytest tests/test_auth_flow.py -q` | 继续通过 |

**完成标准：**

- 领域模型字段与设计一致
- provider/profile 的默认值和错误语义稳定
- 后续 task 可以安全依赖这层契约

---

### T2: 实现 request normalizer / command dispatcher / `site_cli`

**目标：**  
把 `command/provider/backend/scope/account` 的默认值与校验收敛成统一 request 入口，再按 command 分发到对应 use case，并把 `site_cli` 作为新的本地统一入口。

**覆盖设计：**  
D6 / D8 / D9 / D10 / D11

**覆盖需求：**  
R1 / R2 / R3 / R6 / R8 / R9

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
T1

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 定义统一 request 结构 | `command/provider/backend/scope/account` 的默认与校验在一个地方完成 | 已完成 | `core/application/request_normalizer.py` |
| S2 | 定义 command dispatcher | `register` / `list` / `checkin` 能路由到稳定 use case 接口 | 已完成 | `core/application/command_dispatcher.py` |
| S3 | 落地 `site_cli` 与兼容包装 | 新入口可用，旧入口仍可转发 | 已完成 | `cli/site_cli.py` / `wucur_cli/cli.py` / `pyproject.toml` |

**如果是新项目：目标落地点**

- 模块 / 组件：`cli/site_cli.py`
- 模块 / 组件：`core/application/request_normalizer.py`
- 模块 / 组件：`core/application/command_dispatcher.py`
- 目标文件：`cli/site_cli.py`
- 目标文件：`core/application/request_normalizer.py`
- 目标文件：`core/application/command_dispatcher.py`
- 为什么先落这里：这是所有入口共享的分发层，先定这里才能避免各入口各写一套默认值和错误码。

**允许修改的文件：**

- `core/application/request_normalizer.py`
- `core/application/command_dispatcher.py`
- `cli/site_cli.py`
- `pyproject.toml`
- `wucur_cli/cli.py`
- `wucur_cli/__main__.py`
- `scripts/wucur.py`
- `tests/test_package_layout.py`
- `tests/test_wucur_cli.py`
- `tests/test_site_cli.py`（如新增）

**允许修改的符号：**

- `normalize_command_request()`
- `dispatch_command()`
- `main()`
- `format_general_help()`
- `format_command_help()`
- `run_command()`

**禁止修改的文件：**

- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不把业务规则写进 CLI
- 不在 CLI 里直接访问 SQLite / KV / Worker SDK
- 不新增 design 外的命令语义
- 不把 `provider` / `backend` 的默认值分散到多个入口

**实施步骤：**

1. 先定义统一 request schema，明确 `provider` 默认 `wucur`、`backend` 默认按本地 / 云端环境补齐、`scope` 默认 `due`。
2. 再把 command 绑定到 application use case，不让入口直接碰业务实现。
3. 最后把 `site_cli`、`wucur_cli`、`scripts/wucur.py` 统一到同一套 dispatch 逻辑。

**实现参考：**

- `wucur_cli/cli.py`
- `scripts/checkin_due_cli.py`
- `tests/test_wucur_cli.py`

**预期产物：**

- 统一 request / command 层
- 新的 `site_cli` 入口
- 旧兼容入口仍然可用

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_package_layout.py tests/test_wucur_cli.py tests/test_site_cli.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `site_cli` console script 可导入 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 旧 `wucur` 入口 | `uv run pytest tests/test_wucur_cli.py -q` | 继续通过 |

**完成标准：**

- request 默认值和校验只有一套
- `site_cli` 成为 canonical 本地入口
- 旧入口只做兼容，不再扩展业务规则

---

### T3: 抽注册 + 自动签到用例

**目标：**  
把注册、登录、自动签到和结果回放收敛成一个 application use case，让 `checkin.py`、`scripts/register_wucur.py`、`scripts/register_one_account.py` 和 `scripts/register_one_account_to_db.py` 只保留薄包装。

**覆盖设计：**  
D1 / D7 / D10 / D11

**覆盖需求：**  
R1 / R7

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
T1, T2

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 定位注册链路的现有 patch point | 明确哪些逻辑归 application，哪些逻辑留给脚本 | 已完成 | `checkin.py` / `scripts/register_wucur.py` |
| S2 | 下沉统一 use case | 注册、登录、签到和回放字段从脚本抽出 | 已完成 | `core/application/register_and_checkin_account_use_case.py` |
| S3 | 运行回归验证 | 注册脚本、数据库持久化和 use case 单测全绿 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`checkin.py`
- 文件：`scripts/register_wucur.py`
- 文件：`scripts/register_one_account.py`
- 文件：`scripts/register_one_account_to_db.py`
- 文件：`core/application/register_and_checkin_account_use_case.py`
- 为什么在这里改：这是当前注册 + 自动签到链路的主入口和主回放点。

**允许修改的文件：**

- `core/application/register_and_checkin_account_use_case.py`
- `core/ports/account_repository.py`
- `core/ports/checkin_client.py`
- `checkin.py`
- `scripts/register_wucur.py`
- `scripts/register_one_account.py`
- `scripts/register_one_account_to_db.py`
- `tests/test_wucur_client.py`
- `tests/test_register_one_account_to_db.py`
- `tests/test_register_and_checkin_account_use_case.py`（如新增）

**允许修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `RegisterAndCheckinResult`
- `append_account_record()`
- `validate_account()`
- `run_register()`
- `persist_success()`
- `main()`

**禁止修改的文件：**

- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不改变 CLI 参数名
- 不改变关键输出字段名
- 不新增 register 流程之外的外显行为
- 不在脚本里再写一套业务编排

**实施步骤：**

1. 把 register / login / check-in / user-info 的编排收敛到 application 层。
2. 把脚本保留成参数解析 + 调用 + 输出的薄层。
3. 保留结果回放字段，确保 SQLite 持久化仍可回读完整记录。

**实现参考：**

- `checkin.py`
- `scripts/register_wucur.py`
- `scripts/register_one_account_to_db.py`
- `tests/test_register_one_account_to_db.py`

**预期产物：**

- 单一注册 + 自动签到 use case
- 兼容旧脚本的薄包装
- 回放字段与设计一致

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_wucur_client.py tests/test_register_one_account_to_db.py tests/test_register_and_checkin_account_use_case.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `checkin.py` 仍可作为薄入口执行 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有注册持久化入口 | `uv run pytest tests/test_register_one_account_to_db.py -q` | 继续通过 |

**完成标准：**

- 注册 + 自动签到逻辑只在一个 use case 里编排
- SQLite 回放字段完整
- 旧脚本保留兼容能力但不承担主业务规则

---

### T4: 抽查询用例与 `list` 指令

**目标：**  
把 SQLite 查询从表格渲染脚本中抽成稳定的 `ListAccountsUseCase`，再让 CLI / 入口只做结果展示。

**覆盖设计：**  
D2 / D7 / D8 / D10 / D11

**覆盖需求：**  
R2 / R7 / R8

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
T1, T2

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定查询字段 | 输出列顺序和字段集合保持稳定 | 已完成 | `scripts/query_wucur_accounts_db.py` |
| S2 | 抽出查询用例 | 查询逻辑不再依赖表格渲染 | 已完成 | `core/application/list_accounts_use_case.py` |
| S3 | 跑回归 | 查询输出和单测都通过 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`scripts/query_wucur_accounts_db.py`
- 文件：`core/application/list_accounts_use_case.py`
- 为什么在这里改：这是当前查询展示链路的主入口。

**允许修改的文件：**

- `core/application/list_accounts_use_case.py`
- `scripts/query_wucur_accounts_db.py`
- `cli/site_cli.py`
- `tests/test_query_wucur_accounts_db.py`
- `tests/test_list_accounts_use_case.py`（如新增）

**允许修改的符号：**

- `ListAccountsUseCase`
- `fetch_rows()`
- `print_table()`
- `format_value()`
- `display_width()`
- `pad_display()`
- `main()`

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_repository.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不写入数据库
- 不修改签到逻辑
- 不改变现有查询列含义
- 不新增筛选 / 排序语义

**实施步骤：**

1. 把 SQLite 读取逻辑抽到 application use case。
2. 保持 CLI 输出格式稳定。
3. 让 `site_cli list` 和旧查询脚本调用同一套查询实现。

**实现参考：**

- `scripts/query_wucur_accounts_db.py`
- `tests/test_query_wucur_accounts_db.py`

**预期产物：**

- 查询用例
- 稳定的表格输出
- `list` 指令可复用

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_query_wucur_accounts_db.py tests/test_list_accounts_use_case.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | 旧查询脚本仍输出表格 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有查询测试 | `uv run pytest tests/test_query_wucur_accounts_db.py -q` | 继续通过 |

**完成标准：**

- 查询输出包含完整字段
- 薄入口不承担查询业务规则
- `list` 语义与设计一致

---

### T5: 抽补签到用例与默认 `due` 语义

**目标：**  
把今天未签到账号的批量补签到逻辑下沉成 `CheckDueAccountsUseCase`，并确保默认范围就是 `due`，已经签到的记录不会重复处理。

**覆盖设计：**  
D3 / D9 / D10 / D11

**覆盖需求：**  
R3 / R9

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
T1, T2, T4

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 due 规则 | `checkin_date` 解析、到期判定和跳过语义不漂移 | 已完成 | `scripts/checkin_due_domain.py` |
| S2 | 抽出补签到用例 | batch 编排与 I/O 解耦 | 已完成 | `core/application/check_due_accounts_use_case.py` |
| S3 | 跑回归 | 旧 CLI、service、repository 测试全绿 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`scripts/checkin_due_domain.py`
- 文件：`scripts/checkin_due_service.py`
- 文件：`core/application/check_due_accounts_use_case.py`
- 为什么在这里改：这是当前批量补签到的主编排点。

**允许修改的文件：**

- `core/application/check_due_accounts_use_case.py`
- `scripts/checkin_due_service.py`
- `scripts/checkin_due_domain.py`
- `scripts/checkin_due_cli.py`
- `tests/test_checkin_due_domain.py`
- `tests/test_checkin_due_service.py`
- `tests/test_checkin_due_repository.py`

**允许修改的符号：**

- `CheckDueAccountsUseCase`
- `CheckinDueService`
- `CheckinAccountResult`
- `classify_due_accounts()`
- `resolve_as_of_date()`
- `run_account_checkin()`
- `run()`
- `main()`

**禁止修改的文件：**

- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_repository.py`
- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不把 `due` 语义扩成全量重放
- 不改变今天已签到记录的跳过规则
- 不把补签到编排写回脚本层
- 不新增新的补签范围

**实施步骤：**

1. 把到期判断、跳过和错误码收敛到 application use case。
2. 保留旧 service / CLI 作为薄包装。
3. 补回归测试，确认今天已签到不会重复处理。

**实现参考：**

- `scripts/checkin_due_service.py`
- `scripts/checkin_due_domain.py`
- `tests/test_checkin_due_service.py`

**预期产物：**

- `CheckDueAccountsUseCase`
- 默认 `due` 语义稳定
- 旧补签到入口仍可用

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_checkin_due_domain.py tests/test_checkin_due_service.py tests/test_checkin_due_repository.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | today-only / due 跳过语义保持一致 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有补签到 CLI | `uv run pytest tests/test_checkin_due_cli.py -q` | 继续通过 |

**完成标准：**

- 默认补签到语义是 `due`
- 今天已签到记录不重复处理
- service 与 use case 的职责边界清楚

---

### T6: 实现 SQLite repository adapter

**目标：**  
把 SQLite 账号记录读写适配收敛成 repository adapter，确保字段映射稳定、错误码一致。

**覆盖设计：**  
D4 / D7 / D10 / D11

**覆盖需求：**  
R4 / R7

**任务类型：**  
维护型：重构存储适配

**前置依赖：**  
T1, T5

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定存储字段 | SQLite 的读写字段同构 | 已完成 | `scripts/checkin_due_repository.py` |
| S2 | 拆出 repository adapter | SQLite 实现独立落地 | 已完成 | `core/infrastructure/sqlite_account_repository.py` |
| S3 | 跑回归 | SQLite 仓库测试通过 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`scripts/checkin_due_repository.py`
- 文件：`core/infrastructure/sqlite_account_repository.py`
- 为什么在这里改：这是本轮本地 SQLite 存储的唯一适配点。

**允许修改的文件：**

- `scripts/checkin_due_repository.py`
- `core/infrastructure/sqlite_account_repository.py`
- `core/ports/account_repository.py`
- `tests/test_checkin_due_repository.py`

**允许修改的符号：**

- `SqliteCheckinDueRepository`
- `build_backend_repository()`
- `_record_from_row()`
- `_record_from_mapping()`
- `_build_success_payload()`

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

**禁止行为：**

- 不把业务规则写进 repository
- 不改变 SQLite 既有字段含义
- 不修改云端后端的实现

**实施步骤：**

1. 统一 SQLite 的记录字段映射。
2. 把 SQLite repository adapter 独立出来。
3. 补 repository 回归测试，确保本地读写同构。

**实现参考：**

- `scripts/checkin_due_repository.py`
- `tests/test_checkin_due_repository.py`
- `tests/test_cloudflare_kv_account_repository.py`

**预期产物：**

- SQLite repository adapter
- 同构的记录字段和统一错误码

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_checkin_due_repository.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `core/infrastructure/sqlite_account_repository.py` 可导入 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 SQLite 仓库测试 | `uv run pytest tests/test_checkin_due_repository.py -q` | 继续通过 |

**完成标准：**

- SQLite 字段映射稳定
- 存储适配不再混入业务编排

---

### T7: 实现 Cloudflare KV repository adapter

**目标：**  
把 Cloudflare KV 账号记录读写适配收敛成 repository adapter，确保云端读写契约、错误码和安全约束稳定。

**覆盖设计：**  
D5 / D7 / D10 / D11

**覆盖需求：**  
R5 / R7

**任务类型：**  
维护型：重构存储适配

**前置依赖：**  
T6

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定云端字段 | KV 读写 payload 和回放字段同构 | 已完成 | `core/infrastructure/cloudflare_kv_account_repository.py` |
| S2 | 独立云端 adapter | KV 实现独立落地 | 已完成 | `core/infrastructure/cloudflare_kv_account_repository.py` |
| S3 | 跑回归 | KV 仓库测试通过 | 已完成 | pytest 输出 |

**如果是维护型项目：现有改动点**

- 文件：`scripts/checkin_due_repository.py`
- 文件：`core/infrastructure/cloudflare_kv_account_repository.py`
- 为什么在这里改：这是本轮云端 KV 存储的唯一适配点。

**允许修改的文件：**

- `scripts/checkin_due_repository.py`
- `core/infrastructure/cloudflare_kv_account_repository.py`
- `tests/test_checkin_due_repository.py`
- `tests/test_cloudflare_kv_account_repository.py`

**允许修改的符号：**

- `CloudflareKvAccountRepository`
- `_record_from_mapping()`
- `_build_success_payload()`

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

**禁止行为：**

- 不把业务规则写进 repository
- 不改变 KV 既有字段含义
- 不把 KV 适配混回 SQLite 适配

**实施步骤：**

1. 固定 KV repository 的字段映射和错误语义。
2. 独立落地 KV adapter。
3. 补回归测试，确保云端读写同构。

**实现参考：**

- `scripts/checkin_due_repository.py`
- `tests/test_checkin_due_repository.py`
- `tests/test_cloudflare_kv_account_repository.py`

**预期产物：**

- Cloudflare KV repository adapter
- 云端读写契约稳定

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_checkin_due_repository.py tests/test_cloudflare_kv_account_repository.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `core/infrastructure/cloudflare_kv_account_repository.py` 可导入 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 KV 仓库测试 | `uv run pytest tests/test_cloudflare_kv_account_repository.py -q` | 继续通过 |

**完成标准：**

- KV 字段映射稳定
- 云端适配不再混入业务编排
- 云端回归测试通过

---

### T8: 打通 Worker trigger 与后台边界

**目标：**  
Worker 只负责页面、鉴权和触发 GitHub workflow，不执行签到本身；默认 workflow 为 `checkin`，触发失败和鉴权失败都要有稳定返回。

**覆盖设计：**  
D5 / D8 / D10 / D11

**覆盖需求：**  
R5 / R8

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
T2, T6

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 Worker 入口 | 页面、鉴权、触发三条线分开 | 已完成 | `worker-dashboard/src/index.js` |
| S2 | 统一触发 use case | `SyncRemoteTriggerUseCase` 只做 dispatch 编排 | 已完成 | `core/application/sync_remote_trigger_use_case.py` |
| S3 | 跑回归 | Python + Node 的 worker 测试都通过 | 已完成 | pytest / node 输出 |

**如果是维护型项目：现有改动点**

- 文件：`worker-dashboard/src/index.js`
- 文件：`worker-dashboard/src/router.js`
- 文件：`worker-dashboard/src/pages/actions.js`
- 文件：`worker-dashboard/src/pages/callback.js`
- 文件：`worker-dashboard/src/lib/store.js`
- 文件：`worker-dashboard/src/lib/github.js`
- 文件：`worker-dashboard/src/auth.js`
- 文件：`core/application/sync_remote_trigger_use_case.py`
- 为什么在这里改：这是 Worker 触发链路和后台 UI 的主边界。

**允许修改的文件：**

- `core/application/sync_remote_trigger_use_case.py`
- `core/ports/github_dispatch.py`
- `worker-dashboard/wrangler.toml`
- `worker-dashboard/src/index.js`
- `worker-dashboard/src/router.js`
- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/pages/callback.js`
- `worker-dashboard/src/lib/store.js`
- `worker-dashboard/src/lib/github.js`
- `worker-dashboard/src/auth.js`
- `tests/test_sync_remote_trigger_use_case.py`
- `tests/test_worker_layout.py`
- `tests/test_worker_layout.node.mjs`
- `tests/test_worker_admin_ui.node.mjs`

**允许修改的符号：**

- `SyncRemoteTriggerUseCase`
- `GitHubDispatchPort`
- `fetch()`
- `router()`
- `apiTrigger()`
- `handleCallback()`
- `authMiddleware()`

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

**禁止行为：**

- 不在 Worker 内执行签到
- 不把后台 UI 改成独立前端应用
- 不新增额外登录系统
- 不改默认 workflow 语义

**实施步骤：**

1. 把 Worker 入口切成薄路由 + 鉴权 + 触发。
2. 让 `SyncRemoteTriggerUseCase` 成为唯一触发编排点。
3. 用 Node 测试验证页面和触发语义，用 Python 测试验证 use case。

**实现参考：**

- `worker-dashboard/src/index.js`
- `worker-dashboard/src/pages/actions.js`
- `tests/test_worker_layout.node.mjs`
- `tests/test_worker_admin_ui.node.mjs`

**预期产物：**

- Worker 触发链路稳定
- 后台 UI 仍可查看和触发
- 触发失败语义可判定

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_sync_remote_trigger_use_case.py -q && node --test tests/test_worker_layout.node.mjs tests/test_worker_admin_ui.node.mjs` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | Worker 仍只负责页面 / 鉴权 / 触发 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 Worker 路由测试 | `node --test tests/test_worker_layout.node.mjs` | 继续通过 |

**完成标准：**

- Worker 不执行签到本身
- 默认 workflow 为 `checkin`
- 鉴权失败和 dispatch 失败都有稳定返回

---

### T9: 接入飞书 / Telegram 消息入口

**目标：**  
把飞书和 Telegram 的消息 payload 转成统一 request，再交给 `dispatch_command()`；消息平台只做 transport，不写业务规则。

**覆盖设计：**  
D1 / D2 / D3 / D6 / D8 / D10 / D11

**覆盖需求：**  
R1 / R2 / R3 / R6 / R8

**任务类型：**  
IMPL：新增消息入口骨架

**前置依赖：**  
T2, T3, T4, T5

**任务状态：**  
已完成

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 建消息 adapter 骨架 | `adapters/messages/` 下的入口可被导入 | 已完成 | 新文件 |
| S2 | 统一消息映射 | 飞书 / Telegram 都映射到同一 request schema | 已完成 | `feishu.py` / `telegram.py` |
| S3 | 跑消息入口测试 | 平台差异不会改变业务输出 | 已完成 | pytest 输出 |

**如果是新项目：目标落地点**

- 模块 / 组件：`adapters/messages`
- 目标文件：`adapters/messages/feishu.py`
- 目标文件：`adapters/messages/telegram.py`
- 目标文件：`adapters/messages/__init__.py`
- 为什么先落这里：消息平台差异只应该停留在 transport 层，不能直接穿透到业务用例。

**允许修改的文件：**

- `adapters/messages/__init__.py`
- `adapters/messages/feishu.py`
- `adapters/messages/telegram.py`
- `core/application/request_normalizer.py`
- `core/application/command_dispatcher.py`
- `tests/test_message_ingress.py`（如新增）
- `tests/test_site_cli.py`
- `pyproject.toml`

**允许修改的符号：**

- `handle_message()`
- `normalize_command_request()`
- `dispatch_command()`
- `parse_message_event()`

**禁止修改的文件：**

- `core/application/register_and_checkin_account_use_case.py`
- `core/application/list_accounts_use_case.py`
- `core/application/check_due_accounts_use_case.py`
- `core/application/sync_remote_trigger_use_case.py`
- `scripts/register_wucur.py`
- `scripts/query_wucur_accounts_db.py`
- `scripts/checkin_due_service.py`
- `worker-dashboard/`

**禁止修改的符号：**

- `RegisterAndCheckinAccountUseCase`
- `ListAccountsUseCase`
- `CheckDueAccountsUseCase`
- `SyncRemoteTriggerUseCase`

**禁止行为：**

- 不把消息平台 SDK 逻辑写进 application
- 不新增消息平台专属业务语义
- 不让 transport 改变 command 规则
- 不引入除飞书 / Telegram 之外的新消息平台

**实施步骤：**

1. 建消息 adapter 骨架。
2. 把消息内容映射成统一 request，再交给 dispatcher。
3. 用单测验证不同平台输入不会影响业务层行为。

**实现参考：**

- `msgflow/worker/lib/command.js`
- `msgflow/worker/lib/github.js`
- `core/application/command_dispatcher.py`

**预期产物：**

- 飞书消息入口
- Telegram 消息入口
- 统一 request 入口

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest tests/test_message_ingress.py tests/test_site_cli.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | 消息 adapter 只做 transport 映射 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 CLI / 用例 | `uv run pytest tests/test_wucur_cli.py tests/test_query_wucur_accounts_db.py -q` | 继续通过 |

**完成标准：**

- 飞书 / Telegram 只负责消息传输
- 业务规则仍然只在 application 层
- 平台切换不会改变用例契约

## 10. 任务编排建议

### 维护型项目常见编排

```text
T1: 锁定 domain / profile / port 边界
T2: 建 request normalizer + dispatcher + canonical CLI
T3: 修改注册 + 自动签到用例
T4: 抽查询用例与 list 指令
T5: 抽补签到用例
T6: 实现 SQLite repository adapter
T7: 实现 Cloudflare KV repository adapter
T8: 打通 Worker trigger 与后台边界
T9: 接入飞书 / Telegram 消息入口
```

### 新项目常见编排

```text
T1: 先落核心数据模型和边界
T2: 再落统一入口和分发层
T3: 再落核心 use case
T4: 再落存储适配和外部触发
T5: 再落消息入口和回归测试
```

### 硬件 / 外部设备依赖型项目补充

当项目依赖物理硬件、外部设备或不可控第三方服务时，验证无法总是端到端执行。必须在每个 task 的验证中明确标注验证层级：

| 验证层级 | 适用条件 | 验证内容 | 示例 |
|---|---|---|---|
| L1: 编译验证 | 任何时候 | 代码编译通过，接口一致 | `uv run pytest ...` / `node --test ...` |
| L2: Mock 验证 | 无外部服务时 | 用 Mock / Stub 替代真实服务，验证逻辑流程和 UI 交互 | Mock 返回预设值，UI 正确显示 |
| L3: 真实服务验证 | 有真实外部服务时 | 连接真实外部服务执行操作 | Worker 触发、真实消息回执 |

规则：
- 每个 task 至少有 L1 验证
- 涉及外部服务的 task 必须同时写 L2 验证策略
- L3 验证标注为“有条件执行”，不作为 task 完成的阻断条件
- 如果 L2 验证需要 Mock 实现，Mock 的创建应作为独立 task 或当前 task 的实施步骤之一

## 11. 验证标准汇总

| 任务ID | 工作目录 | 命令 | 预期退出码 | 必须出现 | 禁止出现 | 通过标准 |
|---|---|---|---|---|---|---|
| T1 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_domain.py tests/test_provider_profile.py -q` | `0` | `passed` | `FAILED` | 领域模型 / profile 通过 |
| T2 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_package_layout.py tests/test_wucur_cli.py tests/test_site_cli.py -q` | `0` | `passed` | `FAILED` | 统一入口通过 |
| T3 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_wucur_client.py tests/test_register_one_account_to_db.py tests/test_register_and_checkin_account_use_case.py -q` | `0` | `passed` | `FAILED` | 注册链路通过 |
| T4 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_query_wucur_accounts_db.py tests/test_list_accounts_use_case.py -q` | `0` | `passed` | `FAILED` | 查询链路通过 |
| T5 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_domain.py tests/test_checkin_due_service.py tests/test_checkin_due_repository.py -q` | `0` | `passed` | `FAILED` | 补签到通过 |
| T6 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_repository.py -q` | `0` | `passed` | `FAILED` | SQLite 适配通过 |
| T7 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_checkin_due_repository.py tests/test_cloudflare_kv_account_repository.py -q` | `0` | `passed` | `FAILED` | KV 适配通过 |
| T8 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_sync_remote_trigger_use_case.py -q && node --test tests/test_worker_layout.node.mjs tests/test_worker_admin_ui.node.mjs` | `0` | `passed` | `FAILED` | Worker 通过 |
| T9 | `E:\workspace\ai-sign-dev\anyrouter-check-in` | `uv run pytest tests/test_message_ingress.py tests/test_site_cli.py -q` | `0` | `passed` | `FAILED` | 消息入口通过 |

## 12. 交付完成定义

全部 task 完成后，必须同时满足：

1. 所有 task 的验证通过。
2. 所有回归验证通过。
3. 没有违反禁止修改范围。
4. 没有执行未授权外部动作。
5. 维护型项目：现有行为未被误伤。
6. 新结构：最终入口、模块职责、关键边界与 design 保持一致。
7. 没有任何 design 之外的新外显行为被偷偷加进来。
8. 最终端到端验证通过：

```bash
uv run pytest tests/test_package_layout.py tests/test_provider_profile.py tests/test_wucur_client.py tests/test_register_one_account_to_db.py tests/test_query_wucur_accounts_db.py tests/test_checkin_due_domain.py tests/test_checkin_due_service.py tests/test_checkin_due_repository.py tests/test_sync_remote_trigger_use_case.py tests/test_message_ingress.py -q && node --test tests/test_worker_layout.node.mjs tests/test_worker_admin_ui.node.mjs
```

## 13. 拆分质量自检

- [ ] 每个 task 都只有一个独立目标
- [ ] 已明确当前是维护型项目还是新项目
- [ ] 每个 task 都明确了允许修改 / 禁止修改的文件和符号
- [ ] 每个 task 都能追到至少一个 design 项
- [ ] 没有把 design 之外的新外显行为混进 task
- [ ] 新结构的 task 已覆盖结构落地顺序，不是直接跳到散乱实现
- [ ] 每个 task 都给了机器可判定验证格式
- [ ] 每个 task 都有回归验证，不只验证新增逻辑
- [ ] 执行顺序和依赖关系清楚
- [ ] 默认禁止的外部动作没有被偷偷放进完成定义
