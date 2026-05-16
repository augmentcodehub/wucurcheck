# AnyRouter / Wucur GitHub Actions 协作闭环 - 任务（v4.1，双模型流水线版）

> 目标：把已合格设计拆成可独立执行、可独立验证、且不会自己发散出新需求的任务。  
> 前提：requirements-v4.1 / design-v4.1 已无未关闭阻断项，且 task 能逐条追到具体 design 项。

## 1. 关联文档

- 需求：`requirements-v4.1.md`
- 设计：`design-v4.1.md`
- 任务门禁：本文件 + 需求 / 设计门禁规则（如后续补充独立门禁文档，可再补链接）
- 项目规范：`CLAUDE.md` / `AGENTS.md`
- 参考实现：`worker-dashboard/src/lib/github.js`、`worker-dashboard/src/pages/actions.js`、`worker-dashboard/src/pages/callback.js`、`python/src/cli/checkin.py`
- 现有测试：`python/tests/test_worker_layout.node.mjs`、`python/tests/test_worker_admin_ui.node.mjs`、`python/tests/test_package_layout.py`
- 新增测试：`python/tests/test_worker_dispatch.node.mjs`、`python/tests/test_worker_callback.node.mjs`、`python/tests/test_workflow_bridge.py`、`python/tests/test_workflow_summary.py`、`python/tests/test_checkin_workflow_yaml.py`

## 2. 项目类型

### 项目类型

- 维护型项目 + 局部新结构

### 为什么属于这一类

- `worker-dashboard`、`checkin.py` 和 GitHub Actions 工作流都已经存在，不是从零开始。
- 本次重点是补 GitHub workflow bridge、回调写回和 summary artifact，而不是重写签到核心。

### 本次拆分重点

- 先固定 Worker 侧 dispatch 输入与 callback 入口。
- 再固定 `checkin.py` 的机器可读 summary。
- 再落地 `workflow-checkin` 桥接层和 workflow 输入。
- 最后补齐 dispatch / callback / bridge 的回归验证。

## 3. 总目标

Worker 发起的 `workflow_dispatch` 能携带 `workflow / action / target / callback_url`，GitHub Actions 通过 `workflow-checkin` 执行既有 `checkin.py`，再把结果回调到 Worker `/callback` 并写回 KV；`schedule` 和手动 `workflow_dispatch` 仍可直接运行。

### 3.1 任务执行看板

> 这个看板是执行过程的唯一进度来源。执行时先更新这里，再继续下一步。

| 任务ID | 设计项ID | 状态 | 当前步骤 | 最后证据 | 阻塞原因 |
|---|---|---|---|---|---|
| T1 | D13 | 待办 | S1 | - | - |
| T2 | D14 | 待办 | S1 | - | - |
| T3 | D15 | 待办 | S1 | - | - |
| T4 | D15 | 待办 | S1 | - | - |
| T5 | D16 | 待办 | S1 | - | - |

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
| D13 | REQ | R10 | T1 | 是 | Worker dispatch 输入测试 |
| D14 | REQ | R11 | T2 | 是 | callback 写回测试 |
| D15 | IMPL | R10, R11 | T3, T4 | 否 | bridge / summary / target 过滤测试 |
| D16 | TEST | R10, R11 | T5 | 否 | workflow YAML 断言 |
| D17 | OUT | 无 | 无 | 否 | 不进入 tasks |

规则：

- 每个 task 必须至少映射到一个 design 项。
- 如果一个 task 无法映射到 design 项，就必须回到 design，不得进入 tasks。
- `OUT` 项不能被 task 覆盖。
- 如果一个 design 项没有被任何 task 覆盖，说明 tasks 漏项。

## 7. 执行顺序

```text
T1 -> T2 -> T3 -> T4 -> T5
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

### T1: 归一 Worker 触发输入与 dispatch 请求

**目标：**  
让 `apiTrigger()` 统一归一 `workflow / action / target / callback_url`，并让 `triggerWorkflow()` 把这些输入真实送进 GitHub dispatch 请求体。对外仍保留 `checkin` 别名和现有回执形状，不新增别的触发语义。

**覆盖设计：**  
D13

**覆盖需求：**  
R10

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
无

**任务状态：**  
待办

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 Worker 触发入口 | 明确 `actions.js` / `github.js` 里哪些字段要透传，哪些字段只做归一化 | 待办 | `worker-dashboard/src/pages/actions.js` / `worker-dashboard/src/lib/github.js` |
| S2 | 实现 dispatch 输入归一 | `workflow` 选择、`callback_url` 默认值、`target` 透传都落在同一条链路上 | 待办 | diff |
| S3 | 运行验证 | 现有 Worker 触发 UI / API 测试继续通过，并新增 dispatch 输入断言 | 待办 | 测试输出 |

**如果是维护型项目：现有改动点**

- 文件：`worker-dashboard/src/pages/actions.js`
- 文件：`worker-dashboard/src/lib/github.js`
- 为什么在这里改：这里是 Worker 触发 GitHub dispatch 的唯一出口。

**允许修改的文件：**

- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/lib/github.js`
- `python/tests/test_worker_dispatch.node.mjs`

**允许修改的符号：**

- `apiTrigger()`
- `triggerWorkflow()`

**禁止修改的文件：**

- `worker-dashboard/src/pages/callback.js`
- `.github/workflows/checkin.yml`
- `python/src/cli/checkin.py`
- `python/src/tools/workflow/`
- `pyproject.toml`

**禁止修改的符号：**

- `handleCallback()`
- `run_main()`

**禁止行为：**

- 不新增新的触发入口或新的 action 语义
- 不把 callback 写回逻辑混进 dispatch 代码
- 不把 workflow 选择拆成多套默认规则
- 不引入新的外部依赖

**实施步骤：**

1. 在 `apiTrigger()` 内统一归一 `workflow`、`action`、`target` 和 `callback_url`。
2. 明确 `callback_url` 的默认生成方式和显式输入校验。
3. 让 `triggerWorkflow()` 使用归一后的 `workflow` 文件名和 inputs 发起 dispatch。
4. 保留当前 Worker 对外回执字段，不把实现细节泄露到 response 里。

**实现参考：**

- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/lib/github.js`
- `python/tests/test_worker_dispatch.node.mjs`

**预期产物：**

- 真实透传 workflow inputs 的 Worker 触发链路
- 保持现有 `checkin` 别名兼容
- 保持现有触发页面/回执测试可回归

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `node --test python/tests/test_worker_layout.node.mjs python/tests/test_worker_admin_ui.node.mjs python/tests/test_worker_dispatch.node.mjs` |
| 预期退出码 | `0` |
| 必须出现 | `pass` |
| 禁止出现 | `FAIL`, `ERROR` |
| 产物检查 | Worker 触发 response 仍保留 `workflow` / `defaulted` / `dispatch_id` |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 现有 Worker 页面触发 | `node --test python/tests/test_worker_layout.node.mjs` | 继续通过 |
| 现有 Worker 管理页面 | `node --test python/tests/test_worker_admin_ui.node.mjs` | 继续通过 |
| dispatch 输入断言 | `node --test python/tests/test_worker_dispatch.node.mjs` | 新增断言通过 |

**完成标准：**

- Worker 触发请求能带上明确的 workflow / action / target / callback_url
- 触发链路不再依赖隐藏默认值
- 现有 Worker 触发回归不破坏

---

### T2: 修正 callback 落库语义与 batch_result 兼容路径

**目标：**  
让 `handleCallback()` 真实按 payload 写回 KV：`checkin` 结果不能再被默认写成成功，`batch_result` 必须逐条处理，缺少 `username` 的条目跳过，`success=false` 或 `status=failed` 的结果必须写成失败态。

**覆盖设计：**  
D14

**覆盖需求：**  
R11

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
无

**任务状态：**  
待办

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 callback 入口 | 明确 `checkin` / `batch_result` / 失败态的写回规则 | 待办 | `worker-dashboard/src/pages/callback.js` |
| S2 | 修正落库逻辑 | 失败 payload 不再伪装成 active，批量结果逐条 upsert | 待办 | diff |
| S3 | 运行验证 | 新增 callback 回归测试通过 | 待办 | 测试输出 |

**如果是维护型项目：现有改动点**

- 文件：`worker-dashboard/src/pages/callback.js`
- 为什么在这里改：这里是 Worker 回调写 KV 的唯一入口。

**允许修改的文件：**

- `worker-dashboard/src/pages/callback.js`
- `worker-dashboard/src/lib/store.js`（如确有必要）
- `python/tests/test_worker_callback.node.mjs`

**允许修改的符号：**

- `handleCallback()`
- `putAccount()`

**禁止修改的文件：**

- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/lib/github.js`
- `.github/workflows/checkin.yml`
- `python/src/cli/checkin.py`
- `python/src/tools/workflow/`

**禁止修改的符号：**

- `apiTrigger()`
- `triggerWorkflow()`

**禁止行为：**

- 不把失败结果写成 active
- 不丢弃 `checkin_time` / `last_result` / `message` 这类回放字段
- 不把合法的 `batch_result` 兼容 payload 拒之门外
- 不新增新的回调 action

**实施步骤：**

1. 按 `action === "checkin"` 和 `action === "batch_result"` 分开处理。
2. 对 `batch_result` 逐条检查 `username`，缺失则跳过。
3. 对失败态按失败态写回，不补写成成功。
4. 保留 secret / body 非法时才返回 400/401 且不写 KV 的规则。

**实现参考：**

- `worker-dashboard/src/pages/callback.js`
- `design-v4.1.md`
- `worker-dashboard/README.md`

**预期产物：**

- 兼容旧 payload 的 callback 写回逻辑
- 失败态不会被伪装成 active
- 批量结果可以安全逐条落库

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `node --test python/tests/test_worker_callback.node.mjs` |
| 预期退出码 | `0` |
| 必须出现 | `pass` |
| 禁止出现 | `FAIL`, `ERROR` |
| 产物检查 | `checkin` / `batch_result` 的失败态仍然按失败态写回 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 旧 `checkin` payload | `node --test python/tests/test_worker_callback.node.mjs` | 继续通过 |
| 旧 `batch_result` payload | `node --test python/tests/test_worker_callback.node.mjs` | 继续通过 |
| 失败态落库 | `node --test python/tests/test_worker_callback.node.mjs` | `success=false` / `status=failed` 保持失败态 |

**完成标准：**

- 回调不再把失败结果伪装成成功
- `batch_result` 兼容路径稳定可回写
- 旧 payload 兼容性不退化

---

### T3: 落地 workflow-checkin 桥接入口与 workflow_dispatch 输入

**目标：**  
新增 `python/src/tools/workflow/` 作为 GitHub Actions 专用桥接层，定义 `workflow-checkin` 入口并接入 workflow inputs。

**覆盖设计：**  
D15

**覆盖需求：**  
R11

**任务类型：**  
维护型：新增薄结构

**前置依赖：**  
T4

**任务状态：**  
待办

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 bridge 边界 | 明确 `workflow-checkin` 只做 orchestration，不碰 Worker KV | 待办 | `python/src/tools/workflow/` |
| S2 | 接入 workflow inputs | `workflow` / `action` / `target` 能从 workflow 进入 bridge | 待办 | `.github/workflows/checkin.yml` / diff |
| S3 | 运行验证 | package import 和 bridge 单测通过 | 待办 | 测试输出 |

**如果是维护型项目：现有改动点**

- 文件：`.github/workflows/checkin.yml`
- 文件：`python/src/tools/workflow/__init__.py`
- 文件：`python/src/tools/workflow/run_checkin_workflow.py`
- 文件：`pyproject.toml`
- 为什么在这里改：这里是 GitHub Actions 专用 orchestration 层。
- 为什么不能再拆：workflow 入口名、workflow step、环境变量和 bridge 参数必须一起对齐，否则会出现 dispatch 输入与执行入口不一致。

**允许修改的文件：**

- `.github/workflows/checkin.yml`
- `python/src/tools/workflow/__init__.py`
- `python/src/tools/workflow/run_checkin_workflow.py`
- `pyproject.toml`
- `python/tests/test_workflow_bridge.py`

**允许修改的符号：**

- `main()`
- `run_checkin_workflow()`
- `filter_accounts_by_target()`

**禁止修改的文件：**

- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/pages/callback.js`
- `worker-dashboard/src/lib/github.js`
- `python/src/cli/checkin.py`

**禁止修改的符号：**

- `apiTrigger()`
- `handleCallback()`
- `triggerWorkflow()`

**禁止行为：**

- 不解析 `checkin.py` 的 stdout
- 不新增队列、轮询或长连接
- 不把 GitHub workflow 做成新的业务执行层
- 不把 Worker KV 写入挪到 bridge 之外

**实施步骤：**

1. 定义 `workflow-checkin` 的参数和环境变量入口。
2. 在 bridge 内按 `target` 精确过滤 `ANYROUTER_ACCOUNTS`。
3. 在 `.github/workflows/checkin.yml` 中把 schedule / manual / dispatch 输入接到 bridge。

**实现参考：**

- `design-v4.1.md`
- `python/src/cli/checkin.py`
- `python/tests/test_package_layout.py`

**预期产物：**

- `workflow-checkin` 可直接作为 GitHub Actions 入口调用
- workflow inputs 能被读取并透传
- `target` 过滤可单独验证

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest python/tests/test_package_layout.py python/tests/test_workflow_bridge.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `tools.workflow` 可导入，`workflow-checkin` 入口可解析 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| `tools.workflow` 包结构 | `uv run pytest python/tests/test_package_layout.py -q` | 继续通过 |
| GitHub workflow 输入 | `.github/workflows/checkin.yml` 手工检查 | `schedule` / `workflow_dispatch` 仍保留 |

**完成标准：**

- bridge 层不解析 stdout，只读 summary artifact
- `target` 过滤都在 `workflow-checkin` 内闭环
- schedule/manual 仍可直接跑

---

### T4: 为 `checkin.py` 补 summary artifact 写入

**目标：**  
让 `python/src/cli/checkin.py` 在 workflow 模式下写出稳定的机器可读 summary 到 `python/artifacts/workflow/checkin-result.json`（或由 `WORKFLOW_SUMMARY_PATH` 覆盖），内容必须能被 bridge 直接读取，不再依赖 stdout 猜结果。

**覆盖设计：**  
D15

**覆盖需求：**  
R11

**任务类型：**  
维护型：修改现有逻辑

**前置依赖：**  
无

**任务状态：**  
待办

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定 summary 结构 | 明确 `WorkflowCheckinSummary` 字段和默认值 | 待办 | `python/src/cli/checkin.py` |
| S2 | 落地 summary 写入 | `checkin.py` 能按路径写出 UTF-8 JSON | 待办 | diff |
| S3 | 运行验证 | summary roundtrip 单测通过 | 待办 | 测试输出 |

**如果是维护型项目：现有改动点**

- 文件：`python/src/cli/checkin.py`
- 为什么在这里改：这里是批量签到引擎本体，summary 必须由它写出。

**允许修改的文件：**

- `python/src/cli/checkin.py`
- `python/tests/test_workflow_summary.py`
- `python/artifacts/workflow/`（运行产物）

**允许修改的符号：**

- `run_main()`
- `write_workflow_summary()`
- `load_workflow_summary()`

**禁止修改的文件：**

- `.github/workflows/checkin.yml`
- `python/src/tools/workflow/`
- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/pages/callback.js`

**禁止修改的符号：**

- `main()` 之外的 Worker 入口
- `handleCallback()`
- `triggerWorkflow()`

**禁止行为：**

- 不改动现有直接运行的主逻辑语义
- 不把 summary 写入和 stdout 输出混成一套逻辑
- 不在 summary 里泄露密码、token、cookie
- 不新增新的执行通道

**实施步骤：**

1. 定义 summary 文件路径和环境变量优先级。
2. 在 `checkin.py` 内把 workflow 结果整理为 JSON 对象。
3. 写文件时保持 UTF-8、覆盖写和可重复执行。
4. 保证 summary 里的失败态不会丢失。

**实现参考：**

- `python/src/cli/checkin.py`
- `design-v4.1.md`
- `python/tests/test_package_layout.py`

**预期产物：**

- 稳定的 summary artifact 文件
- `checkin.py` 的机器可读输出和人类日志解耦
- bridge 能直接读取 summary 而不解析 stdout

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest python/tests/test_workflow_summary.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED` |
| 产物检查 | `python/artifacts/workflow/checkin-result.json` 可写且可重读 |
| 清理步骤 | 删除临时 summary 文件（如测试创建） |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| 直接运行 `checkin.py` | `uv run python checkin.py`（如测试环境可用） | 仍保持原有退出行为 |
| summary 路径覆盖 | `uv run pytest python/tests/test_workflow_summary.py -q` | 可覆盖自定义路径 |

**完成标准：**

- `checkin.py` 能稳定写出 summary artifact
- summary 内容足以被 bridge 直接消费
- 不破坏现有直接运行方式

---

### T5: 校验 checkin.yml YAML 断言

**目标：**  
验证 `checkin.yml` 的 `schedule` / `workflow_dispatch` / inputs 契约不回退。

**覆盖设计：**  
D16

**覆盖需求：**  
R10

**任务类型：**  
TEST：验证与回归

**前置依赖：**  
T3, T4

**任务状态：**  
待办

**执行清单：**

| 步骤ID | 检查点 | 完成标准 | 状态 | 证据 |
|---|---|---|---|---|
| S1 | 锁定测试范围 | 明确只检查 `schedule` / `workflow_dispatch` / inputs | 待办 | 测试清单 |
| S2 | 补齐测试 | 只维护 `python/tests/test_checkin_workflow_yaml.py` | 待办 | 新测试文件 |
| S3 | 运行验证 | YAML 断言通过 | 待办 | 测试输出 |

**如果是维护型项目：现有改动点**

- 文件：`python/tests/test_checkin_workflow_yaml.py`
- 为什么在这里改：这份测试负责把 workflow 配置的触发输入和兼容性变成机器可判定断言。

**允许修改的文件：**

- `python/tests/test_checkin_workflow_yaml.py`

**允许修改的符号：**

- `test_checkin_workflow_yaml()`

**禁止修改的文件：**

- `worker-dashboard/src/pages/actions.js`
- `worker-dashboard/src/pages/callback.js`
- `worker-dashboard/src/lib/github.js`
- `python/src/cli/checkin.py`
- `python/src/tools/workflow/`
- `.github/workflows/checkin.yml`

**禁止修改的符号：**

- 生产代码中的任何业务入口

**禁止行为：**

- 不把测试写成新的产品行为
- 不在测试里偷偷修业务逻辑
- 不新增新的需求语义

**实施步骤：**

1. 断言 workflow YAML 中的 `schedule` / `workflow_dispatch` / inputs 没有回退。
2. 保持触发输入契约与工作流配置一致。

**实现参考：**

- `.github/workflows/checkin.yml`
- `design-v4.1.md`
- `requirements-v4.1.md`

**预期产物：**  

- workflow YAML 的输入和触发语义可机器验证

**验证：**

| 项目 | 内容 |
|---|---|
| 工作目录 | `E:\workspace\ai-sign-dev\anyrouter-check-in` |
| 前置准备 | 无 |
| 命令 | `uv run pytest python/tests/test_checkin_workflow_yaml.py -q` |
| 预期退出码 | `0` |
| 必须出现 | `passed` |
| 禁止出现 | `FAILED`, `ERROR` |
| 产物检查 | `schedule` / `workflow_dispatch` / inputs 断言通过 |
| 清理步骤 | 无 |

**回归验证：**

| 对象 | 命令/检查方式 | 通过标准 |
|---|---|---|
| workflow YAML | `uv run pytest python/tests/test_checkin_workflow_yaml.py -q` | 继续通过 |

**完成标准：**

- `schedule` / `workflow_dispatch` / inputs 都被断言到
- `checkin.yml` 配置未退化
