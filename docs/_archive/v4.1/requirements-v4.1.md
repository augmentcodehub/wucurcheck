# AnyRouter / Wucur 消息驱动签到与存储统一 - 需求补充（v4.1）

> 说明：本文件只补 GitHub Actions 协作闭环，v4 的 R1-R9 保持不变。
> 目标：让 Worker 发起的 workflow dispatch 具备明确输入、明确回调、明确回写，而不是只触发固定签到任务。

## 1. 范围

### 本次必须完成

- Worker 后台触发 GitHub workflow dispatch 时，必须支持 `workflow` / `action` / `target` / `callback_url`
- GitHub workflow 必须能读取这些 inputs
- workflow 完成后必须回调 Worker `/callback`
- Worker 必须把回调结果写回 KV / 状态
- 旧的 `schedule` 和手动 `workflow_dispatch` 仍要可用

### 本次明确不做

- 不在 Worker 内直接执行注册或签到
- 不把 Worker 变成唯一执行入口
- 不新增除 GitHub Actions 之外的执行通道
- 不改动 v4 的 R1-R9 业务含义

### 必须保持不变

- `checkin.yml` 的 `schedule` 触发仍可运行
- 手动 `workflow_dispatch` 仍可运行
- Worker `/callback` 仍兼容现有 `register` / `checkin` / `batch_result` payload
- Worker `/api/trigger` 仍保留默认 `checkin.yml` 语义

## 2. 新增需求

| ID | 优先级 | 需求 | 业务理由 | 输入/触发 | 输出/结果 | 状态变化/副作用 | 非目标 | 依赖 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| R10 | P0 | Worker 触发的 GitHub Actions 必须支持 `workflow_dispatch` 输入，并把 `action` / `target` / `callback_url` 透传到 workflow | 让 Worker 触发的不是固定死任务，而是可携带参数的协作任务 | Worker 后台发起 GitHub workflow dispatch；`workflow` 选择 YAML 文件，`action` / `target` / `callback_url` 作为 dispatch inputs | GitHub 创建 workflow run，job 内可读取这些 inputs | 仅创建 workflow run，不写 Worker KV | 不在 Worker 内直接执行注册或签到 | `workflow_dispatch`、`GITHUB_TOKEN` | Actions 日志能看见 inputs 被读取；`target` 为空时走默认批量流程 |
| R11 | P0 | GitHub workflow 完成后必须 POST 结果到 Worker `/callback`，并由 Worker 写回 KV | 把执行结果回写后台，形成闭环 | workflow run 完成后向 `callback_url` 发起 POST | Worker 更新 KV / 状态并返回 2xx | 写回对应账号记录 | 不在 Worker 内重跑签到 | `CALLBACK_SECRET`、Worker `/callback` | Worker 日志可见回调；secret 错误或 body 非法返回失败；回调不可达时 workflow 失败但不伪造写回成功 |

## 3. 请求字段定义

> 下面的 `request` 结构对 Worker 触发与 workflow 消费保持一致；`workflow` 用于选择 YAML 文件，`action` / `target` / `callback_url` 作为 dispatch inputs。

| 字段 | 适用契约 | 类型 | 必填 | 默认值 | 允许值 | 说明 |
|---|---|---|---|---|---|---|
| `workflow` | C4 | string | 否 | `checkin.yml` | 现有 workflow 文件名 | GitHub Actions workflow 文件名，Worker 通过它选择要 dispatch 的 workflow |
| `action` | C4 / C5 | string | 否 | `checkin` | `checkin` | 协作任务动作名；v4.1 只要求 `checkin` |
| `target` | C4 / C5 | string | 否 | 空字符串 | 账号用户名或空 | 目标账号用户名；空字符串表示默认批量流程，非空表示单账号目标 |
| `callback_url` | C4 / C5 | string | 否（Worker 协作触发时必填） | 空字符串 | 绝对 HTTPS URL | workflow 完成后 POST 的回调地址；schedule / 手动触发可留空 |

## 4. 负向场景

- `workflow` 指向不存在的文件时，Worker 触发失败，返回 `DISPATCH_FAILED`
- `callback_url` 为空但请求来自 Worker 协作触发时，触发失败，返回 `INVALID_CALLBACK_URL`
- GitHub dispatch 返回 403 / 5xx 时，Worker 触发失败，返回 `DISPATCH_FAILED`
- 回调地址不可达或超时，workflow 失败，但不得伪造回写成功
- 回调 secret 错误或 body 非法时，Worker `/callback` 返回失败且不写 KV

## 5. 契约样例

### C4: GitHub Actions 触发

#### 成功样例

```json
{
  "trigger": "Worker 后台触发",
  "request": {
    "workflow": "checkin.yml",
    "action": "checkin",
    "target": "alice",
    "callback_url": "https://worker.example.com/callback"
  },
  "response": {
    "success": true,
    "workflow": "checkin",
    "dispatch_id": "dispatch-123"
  },
  "status_code": 0,
  "error_code": null,
  "state_change": "GitHub workflow run created; job can read inputs",
  "notes": "target 非空时进入单账号目标模式"
}
```

#### 边界样例

```json
{
  "trigger": "批量签到",
  "request": {
    "workflow": "checkin.yml",
    "action": "checkin",
    "target": "",
    "callback_url": "https://worker.example.com/callback"
  },
  "response": {
    "success": true,
    "workflow": "checkin",
    "defaulted": true,
    "dispatch_id": "dispatch-124"
  },
  "status_code": 0,
  "error_code": null,
  "state_change": "默认批量流程被触发",
  "notes": "空 target 仍必须可用"
}
```

#### 失败样例

```json
{
  "trigger": "Worker 触发但 callback_url 缺失",
  "request": {
    "workflow": "checkin.yml",
    "action": "checkin",
    "target": "alice",
    "callback_url": ""
  },
  "response": {
    "success": false,
    "error_code": "INVALID_CALLBACK_URL"
  },
  "status_code": 1,
  "error_code": "INVALID_CALLBACK_URL",
  "state_change": "不发起 GitHub dispatch",
  "notes": "Worker 协作触发必须带回调地址"
}
```

### C5: GitHub Actions 回调

#### 成功样例

```json
{
  "trigger": "workflow 完成",
  "request": {
    "secret": "xxx",
    "action": "checkin",
    "data": {
      "username": "alice",
      "balance": "128.5",
      "checkin_time": "2026-05-15T10:00:00Z"
    }
  },
  "response": { "ok": true },
  "status_code": 200,
  "error_code": null,
  "state_change": "Worker 写回 KV",
  "notes": "回调必须携带正确 secret"
}
```

#### 边界样例

```json
{
  "trigger": "checkin 回调缺少时间戳",
  "request": {
    "secret": "xxx",
    "action": "checkin",
    "data": {
      "username": "alice",
      "balance": "128.5"
    }
  },
  "response": { "ok": true },
  "status_code": 200,
  "error_code": null,
  "state_change": "Worker 以当前时间补齐签到时间并写回 KV",
  "notes": "缺少 checkin_time 仍应可处理"
}
```

#### 失败样例

```json
{
  "trigger": "回调 secret 错误或 body 非法",
  "request": {
    "secret": "bad",
    "action": "checkin",
    "data": {
      "username": "alice"
    }
  },
  "response": { "ok": false },
  "status_code": 401,
  "error_code": "UNAUTHORIZED",
  "state_change": "不写入成功状态",
  "notes": "secret 不匹配或缺少必填字段都应失败"
}
```

## 6. 回归保护

| 对象 | 必须保持不变的内容 | 风险点 | 验证方式 | 通过标准 |
|---|---|---|---|---|
| `checkin.yml` 定时任务 | `schedule` 仍可运行 | 新输入把定时任务卡死 | 现有 schedule 日志 / 成功退出 | 定时运行不受影响 |
| 手动 `workflow_dispatch` | 无输入时仍可默认跑 `checkin` | 新输入变成强制项 | 手动触发 workflow | 手动运行成功 |
| Worker `/api/trigger` | 未传 `workflow` 时仍默认 `checkin.yml` | 默认值被破坏 | API 测试 | 仍返回 `defaulted: true` |
| Worker `/callback` 兼容性 | 现有 `register` / `checkin` / `batch_result` payload 仍可处理 | 新回调格式误伤旧 payload | 回调测试 | 旧 payload 继续可写 KV |

## 7. 需求追踪

| Requirement | 契约样例 | 设计章节 | Task | Validation |
|---|---|---|---|---|
| R10 | C4 | 待拆分 | 待拆分 | `workflow_dispatch` 输入测试 |
| R11 | C5 | 待拆分 | 待拆分 | callback / KV 写回测试 |

## 8. 自检清单

- [x] `workflow` / `action` / `target` / `callback_url` 已写成正式需求
- [x] callback 失败语义明确，且不会伪造 KV 写回成功
- [x] 不影响 v4 中 R1-R9 的既有语义
