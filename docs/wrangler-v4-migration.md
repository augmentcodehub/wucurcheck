# Wrangler v3 → v4 迁移设计文档

## 概述

当前版本：`wrangler@3.99.0`  
目标版本：`wrangler@4.x`（最新 4.93.0）

Wrangler v4 是一次**低破坏性**的大版本升级，官方定义为"对大多数用户来说是 no-op upgrade"。本项目影响面较小，但需要注意 CLI 默认行为变更。

## 影响评估

### ✅ 无影响项

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Node.js 版本 | ✅ 通过 | 当前 v24.14.1，v4 要求 ≥ v18 |
| `--legacy-assets` | ✅ 无使用 | 项目未使用 |
| `--node-compat` | ✅ 无使用 | 项目未使用 |
| `wrangler publish` | ✅ 无使用 | 已用 `wrangler deploy` |
| `wrangler generate` | ✅ 无使用 | |
| `getBindingsProxy` | ✅ 无使用 | |
| Workers Sites | ✅ 无使用 | |
| Service Environments | ✅ 无使用 | |
| `wrangler.toml` 格式 | ✅ 兼容 | 无废弃配置项 |

### ⚠️ 需要调整项

| 变更 | 影响 | 操作 |
|------|------|------|
| **CLI 命令默认 local 模式** | `wrangler kv key get/put` 等命令不再默认访问远程 | 手动操作 KV 时需加 `--remote` 标志 |
| **esbuild 升级** | 内部 bundler 升级，可能影响边缘 case | 部署后验证 Worker 行为 |
| **compatibility_date** | 当前 `2024-12-01`，建议更新 | 升级后改为升级当天日期 |

## 迁移步骤

### 1. 升级依赖

```bash
cd worker-dashboard
npm install --save-dev wrangler@4
npx wrangler --version  # 确认版本
```

### 2. 调整本地 KV 操作习惯

v4 中所有 `wrangler kv`、`wrangler r2`、`wrangler d1` 命令默认操作**本地存储**。需要操作远程时必须显式加 `--remote`：

```bash
# v3（默认远程）
npx wrangler kv key get --namespace-id=xxx "account:xxx"

# v4（必须加 --remote）
npx wrangler kv key get --namespace-id=xxx "account:xxx" --remote
```

> 注意：`wrangler dev` 和 `wrangler deploy` 行为不变。

### 3. 更新 compatibility_date

```toml
# wrangler.toml
compatibility_date = "2025-05-21"  # 升级当天日期
```

### 4. 验证

- [ ] `npm run dev` 本地启动正常
- [ ] `npm run deploy` 部署成功
- [ ] 访问 Dashboard 页面功能正常
- [ ] 触发一次签到，确认 callback 写入 KV 正常
- [ ] cron 触发正常（`wrangler tail` 观察日志）

## 风险评估

**风险等级：低**

- 本项目无 CI/CD 中使用 wrangler CLI 命令（签到/注册 workflow 不涉及 wrangler）
- 代码中无废弃 API 使用
- 唯一影响是手动运维时的 `--remote` 标志

## 回滚方案

```bash
npm install --save-dev wrangler@3.99.0
```

package-lock.json 回退即可，Worker 代码无需改动。

## 建议时机

不急。等当前功能稳定运行一段时间后，找一个非高峰时段执行。预计耗时 5 分钟。
