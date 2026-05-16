# AnyRouter / Wucur 自动签到与云端同步 — 需求（v3）

> 目标：先把行为契约和边界定死，再进入设计和 tasks。  
> 规则：如果关键问题答不清，先放进阻断项，不进入设计。

## 1. 背景与目标

**背景：**
当前仓库已经能做本地注册、签到、查库和补签到，但实现仍偏脚本化，后续需要同时支持本地 CLI 和云端 Worker/GitHub/KV 两种运行模式，并预留 `provider/profile` 抽象，避免后续只围着 `wucur` 转。

**目标：**
把“注册 + 自动签到 + 持久化 + 查库 + 补签到 + 云端触发”统一到一套可复用的业务核心里，并把站点差异收敛到 `provider/profile` 抽象上，保证未来可以扩展到其他网站。

**成功定义：**
同一套业务用例可以在本地 CLI 和云端 Worker/GitHub 场景下稳定运行，且用户记录、余额、最后签到时间都能被查询和回放。

## 2. 范围

### 本次必须完成

- CLI 支持注册账号并自动签到
- 自动把结果写入 SQLite
- CLI 支持查询数据库所有记录
- CLI 支持给今天没签到的账号补签到
- 云端模式支持把数据写入 Cloudflare KV
- 云端模式支持通过 Worker 页面触发 GitHub Actions 执行签到
- 业务核心必须以 `provider/profile` 作为抽象边界，`wucur` 只是首个落地站点，后续新增网站只补适配层
- 记录中必须包含：注册信息、用户名、密码、余额、最后签到时间

### 本次明确不做

- 不做第三方登录之外的新账号体系
- 不做与签到无关的业务扩展
- 不做复杂后台权限系统
- 不做多租户隔离
- 不在本轮直接接入第二个网站，但必须抽出可扩展的 `provider/profile` 边界

### 必须保持不变

- 现有 `wucur` 登录、签到、余额查询的外部行为
- 现有 CLI 基本可执行方式
- 现有 SQLite 本地查询能力

## 3. 关键决策

| ID | 事项 | 决策 | 影响范围 | 状态 |
|---|---|---|---|---|
| B1 | 云端是否必须明文保存密码 | 云端不得明文保存密码；如需持久化必须加密保存，本地 SQLite 可保持现有行为 | 安全 / 存储 / Worker | 已关闭 |
| B2 | Cloudflare 侧最终用 KV 还是 D1 | 首发使用 Cloudflare KV，不在本轮改为 D1 | 存储 / 设计 / 迁移 | 已关闭 |
| B3 | Worker 页面触发后是直接调 GitHub Actions 还是先入队 | 直接调 GitHub Actions 的 `workflow_dispatch`，不先入队 | 流程 / 可观测 / 回调 | 已关闭 |

## 4. 用户与场景

| 角色 | 触发方式 | 目标 | 失败时最关心什么 |
|---|---|---|---|
| 本地用户 | CLI 命令 | 注册、签到、查库、补签到 | 是否留下脏数据 |
| 云端管理员 | Worker 页面 | 触发 GitHub 签到任务 | 是否成功触发、是否可追踪 |
| 定时任务 | GitHub Actions | 自动签到和落库 | 是否漏签、是否重复签到 |

## 5. 需求清单

| ID | 优先级 | 需求 | 业务理由 | 输入/触发 | 输出/结果 | 状态变化/副作用 | 非目标 | 依赖 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| R1 | P0 | CLI 支持注册账号并自动签到 | 减少人工操作 | `uv run ... register` 类命令 | 返回注册和签到结果 | 写 SQLite / KV | 不做人工二次确认 | `wucur` 接口 | 一条命令完成注册+签到 |
| R2 | P0 | CLI 支持查询当前数据库所有记录 | 方便核对结果 | `query` 命令 | 打印记录表 | 无 | 不做条件筛选 | repository | 能列出全部记录字段；本地 SQLite 查询保持现有明文 `password` 输出 |
| R3 | P0 | CLI 支持补签到今天没签到的账号 | 避免漏签 | `check-due` 命令 | 返回处理汇总 | 更新数据库状态 | 不重复处理今天已签账号 | repository + clock | 只处理到期/缺失记录 |
| R4 | P0 | 云端部署时写 Cloudflare KV | GitHub 部署无本地 SQLite | Actions/Worker 执行 | 记录落到 KV | KV 写入 | 不强制本地文件 | Cloudflare 权限 | 云端可查询记录 |
| R5 | P0 | Worker 提供页面在 token/secret 鉴权后触发 GitHub Actions | 方便后台一键执行 | Worker 页面按钮 + token | 触发 Actions 并回显 | 鉴权通过后发出 workflow_dispatch | 不在 Worker 内直接跑签到 | GitHub PAT / worker secret | 页面能触发且鉴权失败会被拒绝 |
| R6 | P1 | 记录包含注册信息、用户名、密码（云端加密保存）、余额、最后签到时间 | 便于追踪和补签到 | 任何写库路径 | 数据完整 | 更新单条记录；云端密码加密保存 | 不做复杂报表 | 存储层 | 查询时本地 SQLite 能看到完整字段；云端 KV 只保存密文，不回显明文密码 |
| R7 | P0 | 业务核心必须通过 `provider/profile` 抽象承接站点差异 | 防止后续只围着 `wucur` 转 | 任何 use case 调用 | 新网站只新增适配层和配置 | 不把站点差异写死在核心 | provider/profile 接口 | 新增一个 provider/profile 配置后，核心 use case 源码不需要修改，且现有 provider/profile 测试继续通过 |
| R8 | P1 | Worker 直接提供管理后台 UI，用于查看账号并手动触发签到 | 后台管理需要可视化操作 | 访问 Worker 管理页 | 账号列表、详情、触发结果 | 只读查看 + 手动触发，不执行签到 | 不拆独立前端应用 | Worker / daisyUI / GitHub trigger | 页面可列出账号、展示状态和结果，并可手动触发签到 |

## 6. 契约样例

### C1: 注册并自动签到

#### 成功样例

```json
{
  "trigger": "CLI register",
  "request": {"username": "a@example.com", "password": "***"},
  "response": {"success": true, "checkin": true},
  "status_code": 0,
  "error_code": null,
  "state_change": "写入一条记录，包含注册时间、签到时间和余额",
  "notes": "注册后自动签到"
}
```

#### 边界样例

```json
{
  "trigger": "重复执行同一账号",
  "request": {"username": "a@example.com"},
  "response": {"success": true, "updated": true},
  "status_code": 0,
  "error_code": null,
  "state_change": "更新同一账号记录，不新增重复行",
  "notes": "幂等写入"
}
```

#### 失败样例

```json
{
  "trigger": "远端登录失败",
  "request": {"username": "a@example.com"},
  "response": {"success": false, "error_code": "LOGIN_FAILED"},
  "status_code": 1,
  "error_code": "LOGIN_FAILED",
  "state_change": "不得写入签到成功结果",
  "notes": "失败要可重试"
}
```

### C2: 查询数据库

#### 成功样例

```json
{
  "trigger": "query command",
  "request": {"limit": 20},
  "response": {"rows": 20, "sample_row": {"name": "我的主账号", "username": "a@example.com", "password": "demo-password", "registered_at": "2026-05-15 10:00:00", "checkin_date": "2026-05-15", "balance_before": 1.0, "balance_after": 2.0, "balance_delta": 1.0, "used_quota_before": 10.0, "used_quota_after": 9.0, "checkin_reward_raw": 100, "last_status": "checkin_success"}},
  "status_code": 0,
  "error_code": null,
  "state_change": "无；输出包含 name、username、password、registered_at、checkin_date、balance_before、balance_after、balance_delta、used_quota_before、used_quota_after、checkin_reward_raw、last_status",
  "notes": "只读"
}
```

#### 边界样例

```json
{
  "trigger": "query command",
  "request": {"limit": 1000},
  "response": {"rows": 20, "sample_row": {"name": "我的主账号", "username": "a@example.com", "password": "demo-password", "registered_at": "2026-05-15 10:00:00", "checkin_date": "2026-05-15", "balance_before": 1.0, "balance_after": 2.0, "balance_delta": 1.0, "used_quota_before": 10.0, "used_quota_after": 9.0, "checkin_reward_raw": 100, "last_status": "checkin_success"}},
  "status_code": 0,
  "error_code": null,
  "state_change": "无；输出包含 name、username、password、registered_at、checkin_date、balance_before、balance_after、balance_delta、used_quota_before、used_quota_after、checkin_reward_raw、last_status",
  "notes": "limit 大于现有记录数时返回全部记录"
}
```

#### 失败样例

```json
{
  "trigger": "query command",
  "request": {"limit": -1},
  "response": {"success": false, "error_code": "INVALID_LIMIT"},
  "status_code": 1,
  "error_code": "INVALID_LIMIT",
  "state_change": "不查询、不写库",
  "notes": "非法输入要直接失败"
}
```

### C3: 补签到

#### 成功样例

```json
{
  "trigger": "check-due command",
  "request": {"provider_scope": "wucur"},
  "response": {"succeeded": 3, "failed": 0},
  "status_code": 0,
  "error_code": null,
  "state_change": "更新今天没签到的记录",
  "notes": "今天已签到的不重复处理"
}
```

#### 边界样例

```json
{
  "trigger": "check-due command",
  "request": {"provider_scope": "wucur"},
  "response": {"succeeded": 0, "failed": 0, "skipped": 12},
  "status_code": 0,
  "error_code": null,
  "state_change": "没有到期账号时不写入任何成功状态",
  "notes": "没有待补签到账号"
}
```

#### 失败样例

```json
{
  "trigger": "check-due command",
  "request": {"provider_scope": "wucur"},
  "response": {"success": false, "succeeded": 2, "failed": 1, "error_code": "CHECKIN_FAILED"},
  "status_code": 1,
  "error_code": "CHECKIN_FAILED",
  "state_change": "仅更新成功项，失败项保留待重试",
  "notes": "批处理允许部分失败"
}
```

### C4: 云端写入 Cloudflare KV

#### 成功样例

```json
{
  "trigger": "Actions / Worker sync",
  "request": {"provider_scope": "wucur", "records": 1},
  "response": {"success": true, "backend": "kv"},
  "status_code": 0,
  "error_code": null,
  "state_change": "账号记录写入 KV",
  "notes": "云端持久化"
}
```

#### 边界样例

```json
{
  "trigger": "Actions / Worker sync",
  "request": {"provider_scope": "wucur", "records": 1, "account_key": "alice"},
  "response": {"success": true, "updated": true},
  "status_code": 0,
  "error_code": null,
  "state_change": "同一账号重复写入时覆盖同一键，不新增重复条目",
  "notes": "幂等写入"
}
```

#### 失败样例

```json
{
  "trigger": "Actions / Worker sync",
  "request": {"provider_scope": "wucur", "records": 1},
  "response": {"success": false, "error_code": "BACKEND_WRITE_FAILED"},
  "status_code": 1,
  "error_code": "BACKEND_WRITE_FAILED",
  "state_change": "不落成功状态",
  "notes": "KV 写入失败要可重试"
}
```

### C5: Worker 页面触发 GitHub Actions

#### 成功样例

```json
{
  "trigger": "Worker page button click",
  "request": {"workflow": "checkin", "token": "***"},
  "response": {"success": true, "dispatch_id": "12345678"},
  "status_code": 0,
  "error_code": null,
  "state_change": "只发出 workflow_dispatch，不在 Worker 内执行签到",
  "notes": "页面触发成功"
}
```

#### 边界样例

```json
{
  "trigger": "Worker page button click",
  "request": {},
  "response": {"success": true, "workflow": "checkin", "defaulted": true, "dispatch_id": "12345679"},
  "status_code": 0,
  "error_code": null,
  "state_change": "未显式指定 workflow 时使用默认值",
  "notes": "默认触发"
}
```

#### 失败样例

```json
{
  "trigger": "Worker page button click",
  "request": {"workflow": "checkin", "token": "***"},
  "response": {"success": false, "error_code": "AUTH_FAILED"},
  "status_code": 1,
  "error_code": "AUTH_FAILED",
  "state_change": "不触发 GitHub Actions",
  "notes": "鉴权失败直接拒绝"
}
```

### C6: Worker 管理后台查看账号

#### 成功样例

```json
{
  "trigger": "Worker admin page load",
  "request": {"token": "***"},
  "response": {"success": true, "rows": 20, "can_trigger": true},
  "status_code": 0,
  "error_code": null,
  "state_change": "仅展示账号与运行状态，不执行签到",
  "notes": "后台列表页"
}
```

#### 边界样例

```json
{
  "trigger": "Worker admin page load",
  "request": {"token": "***", "filter": "wucur"},
  "response": {"success": true, "rows": 1, "selected": "wucur"},
  "status_code": 0,
  "error_code": null,
  "state_change": "按筛选条件展示账号列表",
  "notes": "列表筛选"
}
```

#### 失败样例

```json
{
  "trigger": "Worker admin page load",
  "request": {"token": "***"},
  "response": {"success": false, "error_code": "AUTH_FAILED"},
  "status_code": 1,
  "error_code": "AUTH_FAILED",
  "state_change": "不展示后台数据",
  "notes": "鉴权失败拒绝访问"
}
```

## 7. 边界、异常与负向场景

| 场景 | 条件 | 预期行为 | 是否允许重试 | 是否应有副作用 | 验证方式 |
|---|---|---|---|---|---|
| 空数据库 | 没有记录 | 只输出空结果 | 否 | 否 | CLI 查询 |
| 今天已签到 | `checkin_date` 等于今天 | 跳过 | 否 | 否 | 补签到命令 |
| 非法输入 | `limit < 0`、`provider_scope` 不存在、缺少必要参数 | 返回校验错误码 | 否 | 否 | CLI / Worker |
| 权限不足 | Cloudflare KV / GitHub token 缺失或无权 | 返回鉴权失败或写入失败 | 是 | 否 | Worker / Actions |
| 云端保存密码 | Cloudflare KV 需要密码字段 | 云端必须先加密再写入；密钥缺失时返回配置错误并停止写入 | 否 | 否 | repository / CLI |
| 外部服务失败 | 登录/签到接口失败 | 返回失败码 | 是 | 否 | mock / 真实接口 |
| 云端 Worker 失败 | GitHub 不可达 | 返回错误信息 | 是 | 否 | Worker 页面触发 |

## 8. 非功能需求

| 类型 | 约束/指标 | 测量方式 | 通过标准 |
|---|---|---|---|
| 安全 | 密码不能直接输出到日志 | 检查日志和输出 | 不出现明文密码 |
| 安全 | 云端密码必须加密保存 | 检查仓库测试和云端写入字段 | KV 中不出现明文密码 |
| 兼容性 | 本地 CLI 仍可跑 | 执行现有命令 | 命令可用 |
| 稳定性 | 失败不写脏状态 | 查库回看 | 失败不落“签到成功” |
| 可复用性 | 核心逻辑不依赖 CLI/Worker | 代码结构检查 | 用例可被两端调用 |

## 9. 不变性 / 回归保护

| 对象 | 必须保持不变的内容 | 风险点 | 验证方式 | 通过标准 |
|---|---|---|---|---|
| `wucur` 注册和签到流程 | 原有命令行为 | 重构后流程变散 | 现有测试 | 旧命令继续可用 |
| SQLite 查询命令 | 表格输出能力 | 改成只支持云端 | CLI 测试 | 仍可查询 |

## 10. 约束与依赖策略

### 技术约束

- Python 负责本地 CLI 和核心业务
- Worker 侧只负责薄入口和页面
- 业务规则不得沉进 CLI 或 Worker

### 依赖策略

- 是否允许新增依赖：允许，但要最少化
- Cloudflare 适配优先复用官方 Worker/KV 能力

### 数据与安全约束

- 密码不得出现在普通日志
- 所有云端接口必须有鉴权
- 余额和签到结果必须可回放

## 11. 相关上下文

- `docs/checkin-due-cli.md`
- `docs/wucur-github-checkin-guide.md`
- `https://github.com/ohwiki/msgflow`

## 12. 需求追踪

| Requirement | 契约样例 | 设计章节 | Task | Validation |
|---|---|---|---|---|
| R1 | C1 | D2 / D4 | T3 | CLI 注册测试 |
| R2 | C2 | D3 | T4 | 查询命令测试 |
| R3 | C3 | D3 / D5 | T5 | 补签到测试 |
| R4 | C4 | D5 | T6 | KV repository 测试 |
| R5 | C5 | D6 | T7 | Worker 触发测试 |
| R6 | C1 / C2 / C3 / C4 | D2 / D3 / D5 / D6 | T1 / T3 / T4 / T5 / T6 | 记录字段测试 |
| R7 | 无 | D2 / D6 / D8 | T2 | provider/profile 抽象测试 |
| R8 | C6 | D6 / D8 | T8 | 后台 UI 测试 |

## 自检清单

- [ ] 没有未关闭阻断项被带入 design / tasks
- [ ] 每条需求都写了业务理由、输入/输出、副作用、验收标准
- [ ] 每个外部可见行为都有成功/边界/失败契约样例
- [ ] 已明确必须保持不变的旧行为
- [ ] 非功能约束和回归保护可验证
- [ ] 已明确未来可扩展到其他网站的 provider/profile 抽象
- [ ] 已明确新增依赖是否允许
- [ ] 已明确 Worker 后台 UI 的展示范围和交互范围
