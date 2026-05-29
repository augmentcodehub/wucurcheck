# AnyRouter / Wucur 消息驱动签到与存储统一 - 需求（v4）

> 目标：把“消息入口 + 指令处理 + 本地/云端存储”统一成一套可复用业务核心。  
> 规则：先定需求边界，再进入设计；消息通道先作为可插拔入口，不直接绑死业务核心。

## 使用规则

- 不允许使用“按需”“视情况而定”“通常”“类似现有逻辑”这类无法直接编码的表述。
- 每条需求必须可验证，且验证方式要能被另一个模型直接执行或检查。
- 每个外部可见行为必须给出成功、边界、失败至少 3 类契约样例。
- 任何影响接口、数据结构、错误语义、权限边界、持久化、副作用、验证标准的问题，如果未决，默认是阻断项。
- 存在未关闭阻断项时，不应继续产出 design / tasks / code。

## 1. 背景与目标

**背景：**  
当前仓库已经具备注册、签到、查库、补签到、Worker 触发、Cloudflare KV 适配等能力，但这些能力分散在脚本、Worker 和 GitHub Actions 里，主签到链路仍有老入口未彻底剥离。  
同时，飞书和 Telegram 已经在 `msgflow` 中有成熟接入模式，可以复用为消息入口，而不必为本项目重新造一套通道。

**目标：**  
把 AnyRouter / Wucur 的核心能力抽成一套统一业务层，并支持通过飞书或 Telegram 发送指令完成以下操作：
- 注册账号并自动签到
- 查看所有已注册账号
- 对今天未签到的账号执行批量签到

**成功定义：**  
同一套指令可以通过飞书或 Telegram 进入，落到同一套业务核心；本地部署用 SQLite，云端部署用 Cloudflare KV，不需要为两套入口分别维护业务逻辑。

## 2. 范围

### 本次必须完成

- 支持飞书或 Telegram 作为消息入口
- 支持三类核心指令：注册、查看账号、签到
- 注册指令要完成注册并自动签到
- 查看账号指令要列出全部注册账号信息
- 签到指令要找出今天没签到的账号并批量执行
- 本地部署使用 SQLite 作为存储后端
- Cloudflare 部署使用 KV 作为存储后端
- 业务核心要与消息通道解耦
- `site_cli` 必须支持多 provider / 多 backend / 多指令模式
- 未指定 `provider` 时默认值为 `wucur`

### 本次明确不做

- 不在本轮重新设计账号体系
- 不在本轮接入第二个网站
- 不在本轮接入除飞书 / Telegram 之外的新消息平台
- 不做复杂后台权限系统
- 不做多租户隔离
- 不把 Cloudflare Worker 做成唯一入口
- 不在本轮把所有旧脚本一次性删除

### 必须保持不变

- 现有注册、签到、查库、补签到的业务行为
- 现有本地 SQLite 查询能力
- 现有 Cloudflare KV 读写能力
- 现有脚本入口在迁移期内可保留为兼容层

## 3. 阻断项

> 任何“模型不能合理猜”的点都必须放这里。未关闭前，禁止进入设计和实现。

| ID | 事项 | 影响范围 | 是否阻断 | 是否允许默认策略 | 决策人 | 关闭条件 |
|---|---|---|---|---|---|---|
| B1 | 飞书 / Telegram 作为消息入口的具体接入顺序 | 消息入口 / Worker / CLI | 否 | 是 | 用户 | 确认先接 Telegram、飞书后接，或两者并行 |
| B2 | `checkin` 默认是否只处理“今天未签到”的账号 | CLI / 消息指令 / 补签到逻辑 | 否 | 是 | 用户 | 确认默认行为就是全量补签今天未签到账号 |
| B3 | CLI 是否按网站拆分 | 命令面 / 可维护性 | 否 | 是 | 用户 | 确认单一 `site_cli` + `provider` 参数 |
| B4 | 本地是否默认直连 KV | 存储 / 本地运行 | 否 | 是 | 用户 | 确认本地默认 SQLite、云端默认 KV |

## 4. 用户与场景

| 角色 | 触发方式 | 目标 | 失败时最关心什么 |
|---|---|---|---|
| 本地用户 | `site_cli` 命令 | 注册、查库、补签到 | 是否影响本地数据库 |
| 云端管理员 | 飞书 / Telegram | 发消息触发任务 | 是否被正确解析并执行 |
| 定时任务 | GitHub Actions | 自动签到落库 | 是否漏签、是否重复签到 |

## 5. 需求清单

> 每条需求必须写清楚：为什么做、何时触发、输入是什么、系统要返回什么、会不会改状态、怎么验收。

| ID | 优先级 | 需求 | 业务理由 | 输入/触发 | 输出/结果 | 状态变化/副作用 | 非目标 | 依赖 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| R1 | P0 | 消息入口支持“注册”指令 | 减少手工注册成本 | 飞书 / Telegram 消息，指令为 `register` | 返回注册 + 自动签到结果 | 写入账号记录 | 不做人工二次确认 | 核心注册用例 | 发一条指令即可完成注册并签到 |
| R2 | P0 | 消息入口支持“查看账号”指令 | 便于核对账号状态 | 飞书 / Telegram 消息，指令为 `list` | 返回所有账号信息 | 无 | 不做复杂筛选 | 查询用例 | 能列出全部账号字段 |
| R3 | P0 | 消息入口支持“签到”指令 | 避免漏签 | 飞书 / Telegram 消息，指令为 `checkin` | 返回批量签到汇总 | 更新今天未签到的记录 | 不重复处理今天已签账号 | 补签到用例 | 只处理到期或缺失记录 |
| R4 | P0 | 本地部署默认使用 SQLite | 本地没有 KV 依赖时也能运行 | `site_cli` 或本地消息入口 | 账号读写成功 | 写本地数据库 | 不强制云端资源 | SQLite repository | 本地能完整闭环 |
| R5 | P0 | 云端部署使用 Cloudflare KV | 云端不依赖本地文件 | Worker / Actions | KV 落库成功 | 写 KV | 不强制本地 SQLite | KV repository | 云端能查询记录 |
| R6 | P1 | 业务核心与消息通道解耦 | 飞书 / Telegram 只是入口 | 任意消息平台 | 同一套 use case 被调用 | 不把通道逻辑写进业务核心 | 不接入更多通道 | application 层 | 更换通道不改业务用例 |
| R7 | P1 | 账号记录字段保持完整 | 便于查询和回放 | 任意写库路径 | 包含注册信息、账号、密码、余额、最后签到时间 | 更新单条记录 | 不做复杂报表 | 存储层 | 查询可回放完整字段 |
| R8 | P0 | `site_cli` 支持多 provider / 多 backend | 避免网站拆 CLI 造成重复 | CLI 命令 | 通过参数选择网站与后端 | 不复制命令体系 | provider / backend 解析 | 同一 CLI 可以操作不同网站与后端 |
| R9 | P0 | `checkin` 默认覆盖所有未签到账号 | 避免漏签 | CLI / 消息指令 | 批量补签结果 | 处理所有未签到记录 | 不重复处理已签到账号 | 补签到用例 | 默认行为可直接完成全量补签 |

## 6. 契约样例

> 每个外部可见行为至少给 3 类样例：成功、边界、失败。

### 6.0 请求字段定义

> 下面的 `request` 结构对 `site_cli`、飞书和 Telegram 保持一致；`trigger` 只用于说明入口通道，不改变字段语义。

| 字段 | 适用契约 | 类型 | 必填 | 默认值 | 允许值 | 说明 |
|---|---|---|---|---|---|---|
| `command` | C1 / C2 / C3 | string | 是 | 无 | `register` / `list` / `checkin` | 指令名，决定进入哪个用例 |
| `provider` | C1 / C2 / C3 | string | 否 | `wucur` | 当前 `ProviderProfileResolver` 已注册的 provider | 站点标识；未知值返回 `UNSUPPORTED_PROVIDER` |
| `backend` | C1 / C2 / C3 | string | 否 | 本地/CLI 默认 `sqlite`，云端/Worker 默认 `kv` | `sqlite` / `kv` | 存储后端；未显式传入时由入口层按部署环境补齐 |
| `account` | C1 | object | 是 | 无 | 见下方 C1 账号载荷字段 | 注册账号载荷 |
| `scope` | C3 | string | 否 | `due` | `due` | 批量签到范围；v4 只定义补今天未签到账号 |

#### C1 账号载荷字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `name` | string | 是 | 无 | 账号显示名 |
| `username` | string | 是 | 无 | 登录用户名 |
| `password` | string | 是 | 无 | 登录密码 |
| `cookies` | string / object | 否 | 无 | 仅在后续扩展为 cookie 登录时使用 |

#### 字段校验与错误语义

| 场景 | 错误码 | 说明 |
|---|---|---|
| `account.name` / `account.username` / `account.password` 缺失或为空 | `INVALID_ACCOUNT_PAYLOAD` | 注册请求参数不完整 |
| `provider` 不存在 | `UNSUPPORTED_PROVIDER` | 未注册的站点直接失败 |
| `backend` 不存在 | `INVALID_BACKEND` | 未知存储后端直接失败 |
| `scope` 不存在或非法 | `INVALID_SCOPE` | 只接受 `due` |

### C1: 注册

#### 成功样例

```json
{
  "trigger": "飞书/Telegram 消息",
  "request": {
    "command": "register",
    "provider": "wucur",
    "backend": "sqlite",
    "account": {
      "name": "Console User",
      "username": "a@example.com",
      "password": "***"
    }
  },
  "response": { "success": true, "registered": true, "checkin": true },
  "status_code": 0,
  "error_code": null,
  "state_change": "新增或更新账号记录，并自动签到",
  "notes": "注册后立即执行签到"
}
```

#### 边界样例

```json
{
  "trigger": "重复注册同一账号",
  "request": {
    "command": "register",
    "provider": "wucur",
    "backend": "sqlite",
    "account": {
      "name": "Console User",
      "username": "a@example.com",
      "password": "***"
    }
  },
  "response": { "success": true, "updated": true },
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
  "request": {
    "command": "register",
    "provider": "wucur",
    "backend": "sqlite",
    "account": {
      "name": "Console User",
      "username": "a@example.com",
      "password": "***"
    }
  },
  "response": { "success": false, "error_code": "LOGIN_FAILED" },
  "status_code": 1,
  "error_code": "LOGIN_FAILED",
  "state_change": "不得写入签到成功结果",
  "notes": "失败要可重试"
}
```

```json
{
  "trigger": "注册成功但自动签到失败",
  "request": {
    "command": "register",
    "provider": "wucur",
    "backend": "sqlite",
    "account": {
      "name": "Console User",
      "username": "a@example.com",
      "password": "***"
    }
  },
  "response": { "success": false, "registered": true, "checkin": false, "error_code": "CHECKIN_FAILED" },
  "status_code": 1,
  "error_code": "CHECKIN_FAILED",
  "state_change": "已写入注册记录，但未写入签到成功结果",
  "notes": "注册和签到分开反馈"
}
```

```json
{
  "trigger": "缺少账号字段",
  "request": {
    "command": "register",
    "provider": "wucur",
    "backend": "sqlite",
    "account": {
      "name": "Console User",
      "username": "a@example.com"
    }
  },
  "response": { "success": false, "error_code": "INVALID_ACCOUNT_PAYLOAD" },
  "status_code": 1,
  "error_code": "INVALID_ACCOUNT_PAYLOAD",
  "state_change": "无",
  "notes": "注册请求字段不完整"
}
```

### C2: 查看账号

#### 成功样例

```json
{
  "trigger": "飞书/Telegram 消息",
  "request": { "command": "list", "provider": "wucur", "backend": "sqlite" },
  "response": {
    "rows": 20,
    "sample_row": {
      "name": "Console User",
      "username": "a@example.com",
      "password": "demo-password",
      "registered_at": "2026-05-15 10:00:00",
      "checkin_date": "2026-05-15",
      "balance_before": 1.0,
      "balance_after": 2.0,
      "balance_delta": 1.0,
      "used_quota_before": 10.0,
      "used_quota_after": 9.0,
      "checkin_reward_raw": 100,
      "last_status": "checkin_success"
    }
  },
  "status_code": 0,
  "error_code": null,
  "state_change": "无",
  "notes": "返回全部注册账号"
}
```

#### 边界样例

```json
{
  "trigger": "账号为空",
  "request": { "command": "list", "provider": "wucur", "backend": "sqlite" },
  "response": { "rows": 0 },
  "status_code": 0,
  "error_code": null,
  "state_change": "无",
  "notes": "空列表也要成功返回"
}
```

#### 失败样例

```json
{
  "trigger": "provider 不存在",
  "request": { "command": "list", "provider": "unknown", "backend": "sqlite" },
  "response": { "success": false, "error_code": "UNSUPPORTED_PROVIDER" },
  "status_code": 1,
  "error_code": "UNSUPPORTED_PROVIDER",
  "state_change": "无",
  "notes": "未知网站直接失败"
}
```

```json
{
  "trigger": "backend 不存在",
  "request": { "command": "list", "provider": "wucur", "backend": "unknown" },
  "response": { "success": false, "error_code": "INVALID_BACKEND" },
  "status_code": 1,
  "error_code": "INVALID_BACKEND",
  "state_change": "无",
  "notes": "未知后端直接失败"
}
```

### C3: 签到

#### 成功样例

```json
{
  "trigger": "飞书/Telegram 消息",
  "request": { "command": "checkin", "provider": "wucur", "backend": "sqlite", "scope": "due" },
  "response": { "succeeded": 3, "failed": 0 },
  "status_code": 0,
  "error_code": null,
  "state_change": "更新今天未签到的记录",
  "notes": "今天已签到的不重复处理"
}
```

#### 边界样例

```json
{
  "trigger": "没有待补签到账号",
  "request": { "command": "checkin", "provider": "wucur", "backend": "sqlite", "scope": "due" },
  "response": { "succeeded": 0, "failed": 0, "skipped": 12 },
  "status_code": 0,
  "error_code": null,
  "state_change": "无写入",
  "notes": "没有待补签到账号"
}
```

#### 失败样例

```json
{
  "trigger": "部分账号签到失败",
  "request": { "command": "checkin", "provider": "wucur", "backend": "sqlite", "scope": "due" },
  "response": { "success": false, "succeeded": 2, "failed": 1, "error_code": "CHECKIN_FAILED" },
  "status_code": 1,
  "error_code": "CHECKIN_FAILED",
  "state_change": "仅更新成功项，失败项保留待重试",
  "notes": "批处理允许部分失败"
}
```

```json
{
  "trigger": "非法 scope",
  "request": { "command": "checkin", "provider": "wucur", "backend": "sqlite", "scope": "all" },
  "response": { "success": false, "error_code": "INVALID_SCOPE" },
  "status_code": 1,
  "error_code": "INVALID_SCOPE",
  "state_change": "无",
  "notes": "只接受 due"
}
```

## 7. 边界、异常与负向场景

| 场景 | 条件 | 预期行为 | 是否允许重试 | 是否应有副作用 | 验证方式 |
|---|---|---|---|---|---|
| 空输入 | 消息为空或 CLI 无参数 | 返回 help 或提示，不进入用例 | 否 | 否 | `site_cli` help / 消息 help |
| 权限不足 | token / secret 无效 | 返回 `AUTH_FAILED` | 否 | 否 | Worker / 消息入口测试 |
| 外部服务失败 | GitHub / 远端站点不可达 | 返回固定错误码并可重试 | 是 | 不应写成功状态 | API 失败测试 |
| provider 不存在 | 指定未知网站 | 返回 `UNSUPPORTED_PROVIDER` | 否 | 否 | provider 解析测试 |
| backend 不存在 | 指定未知后端 | 返回配置错误 | 否 | 否 | backend 解析测试 |

## 8. 非功能需求

| 类型 | 约束/指标 | 测量方式 | 通过标准 |
|---|---|---|---|
| 性能 | 单次消息解析和指令分发不引入明显阻塞 | 单元测试 / 代码审查 | CLI / Worker 入口保持薄层 |
| 安全 | 不得输出 token / secret / 明文密码到普通日志 | 搜索日志输出和测试 | 日志中不出现敏感字段 |
| 兼容性 | 迁移期保留旧脚本入口 | 回归测试 | 旧 CLI / 工作流不被破坏 |
| 稳定性 | 外部失败不可导致脏数据 | 失败回归测试 | 失败不写成功状态 |

### 硬件/外部设备依赖声明（如适用）

| 依赖设备/服务 | 开发环境是否可用 | 无设备时的验证策略 | 有设备时的额外验证 |
|---|---|---|---|
| 飞书 / Telegram | 部分 | Mock HTTP / 消息事件样例 | 真实消息发送与回执 |
| Cloudflare KV | 部分 | 本地模拟 / 远程 bindings 测试 | 真实 Worker/KV 读写 |
| GitHub Actions | 是 | workflow_dispatch 触发测试 | 真实 workflow 日志验证 |

## 9. 不变性 / 回归保护

> 这里不是“本次不做什么”，而是“已有什么绝不能被改坏”。

| 对象 | 必须保持不变的内容 | 风险点 | 验证方式 | 通过标准 |
|---|---|---|---|---|
| 旧脚本入口 | 迁移期内仍可执行 | 新 CLI 替换过早 | 现有脚本测试 | 现有命令继续通过 |
| SQLite 查询 | 明文输出字段不变 | 新存储层误伤格式 | 查询测试 | 输出字段与现有一致 |
| Cloudflare KV | 仍可读写账号记录 | 新指令层误伤仓库 | KV repository 测试 | 读写行为不变 |
| 定时签到工作流 | 仍可通过 GitHub Actions 运行 | 新架构阻断旧定时任务 | `checkin.yml` 回归 | workflow_dispatch / schedule 继续可用 |
| `site_cli` 参数 | `provider` / `backend` 作为核心参数长期存在 | 命令面再次碎片化 | CLI 测试 | 同一 CLI 可以覆盖多个网站和后端 |

## 10. 约束与依赖策略

### 技术约束

- 单一 CLI 正式包名为 `site_cli`
- `wucur_cli` 只作为迁移兼容层
- `provider` 负责区分网站，`backend` 负责区分存储
- `site_cli` 的默认命令语义以业务动作命名，不以网站名命名

### 依赖策略

- 是否允许新增依赖：允许
- 如果允许，允许范围：只允许引入支持消息入口、参数解析、存储适配所必需的轻量依赖
- 如果禁止，必须复用的现有能力：`httpx`、`playwright`、`python-dotenv`、现有 Worker / GitHub Actions 能力

### 数据与安全约束

- 密码本地可明文保留在 SQLite，云端不得明文保存
- 消息入口必须做指令校验，非法输入直接失败
- 业务核心不能依赖具体消息平台 SDK
- 飞书 / Telegram 只是传入消息和回传结果的通道

## 11. 相关上下文

- 业务/架构文档：`docs/requirements-v4.md`
- 参考实现：`msgflow/worker/lib/command.js`、`msgflow/worker/lib/github.js`
- 现有测试：`tests/test_wucur_cli.py`、`tests/test_sync_remote_trigger_use_case.py`
- 规范文件：`CLAUDE.md` / `AGENTS.md`

## 12. 需求追踪

| Requirement | 契约样例 | 设计章节 | Task | Validation |
|---|---|---|---|---|
| R1 | C1 | 注册用例 / 消息入口 | 待拆分 | 指令注册测试 |
| R2 | C2 | 查询用例 / 消息入口 | 待拆分 | 账号列表测试 |
| R3 | C3 | 补签到用例 / 消息入口 | 待拆分 | 补签测试 |
| R4 | C1/C2/C3 | 本地存储策略 | 待拆分 | SQLite 测试 |
| R5 | C1/C2/C3 | 云端存储策略 | 待拆分 | KV 测试 |
| R6 | C1/C2/C3 | 通道解耦 | 待拆分 | provider/入口分离测试 |
| R7 | C1/C2/C3 | 记录字段 | 待拆分 | 记录字段测试 |
| R8 | C1/C2/C3 | 单一 CLI / provider / backend | 待拆分 | `site_cli` 命令测试 |
| R9 | C3 | 默认补签到语义 | 待拆分 | 默认全量补签测试 |

---

## 自检清单

- [ ] 没有未关闭的阻断项被带入 design / tasks
- [ ] 每条需求都写了业务理由、输入/输出、副作用、验收标准
- [ ] 每个外部可见行为都有成功/边界/失败契约样例
- [ ] 已明确写出“必须保持不变”的旧行为
- [ ] 非功能约束和回归保护可验证
- [ ] 已明确新增依赖是否允许
