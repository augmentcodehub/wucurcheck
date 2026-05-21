# Cloudflare KV 数据库设计教程

> 结合 wucurcheck（纯 KV）和 moemail（D1 + KV 混合）两个项目的实践经验。

## 一、KV vs D1：什么时候用哪个

| 特性 | KV | D1 |
|------|----|----|
| 数据模型 | Key-Value（无 schema） | SQL 关系型（有表结构） |
| 查询能力 | 只能按 key 精确查找或前缀扫描 | 支持 JOIN、WHERE、聚合等 |
| 一致性 | 最终一致（全球边缘缓存） | 强一致（单 region 主库） |
| 延迟 | 读极快（边缘缓存命中时 <1ms） | 稍慢（需回源） |
| 写入 | 每秒约 1000 次/namespace | 无硬限制 |
| 适合场景 | 配置、缓存、session、简单状态 | 复杂业务数据、需要关联查询 |
| 迁移 | 无 schema，随时改 key 格式 | 需要 migration 文件 |

**moemail 的选择**：
- D1 存核心业务数据（用户、邮件、消息）— 需要关联查询
- KV 存站点配置（`SITE_CONFIG`）— 简单键值，读多写少

**wucurcheck 的选择**：
- KV 存所有数据（账号、日志）— 数据简单，不需要 JOIN

## 二、KV 的 Key 设计原则

KV 没有表，你的 **key 命名规则就是你的 schema**。

### 核心原则

```
{entity}:{identifier}[:{sub_key}]
```

### wucurcheck 实际使用的 Key 设计

```
account:{username}          → 账号主数据
fail_log:{username}:{date}  → 签到失败日志
config:cron_hour            → 定时任务配置
lock:{action}:{target}      → 操作锁
```

### moemail 的 KV 使用（SITE_CONFIG namespace）

```
site:title                  → 站点标题
site:domain                 → 站点域名
email:max_count             → 最大邮箱数
```

## 三、设计模式

### 模式 1：实体存储（类似数据库行）

```javascript
// Key: account:{username}
// Value: JSON 对象
{
  "username": "ivy9eel@outlook.com",
  "password": "123Claude&Codex",
  "platform": "wucur",
  "status": "active",
  "balance": "2.89",
  "checkin_time": "2026-05-21T00:05:10.080Z",
  "created_at": "2026-05-18T12:10:09.451Z",
  "updated_at": "2026-05-21T00:20:53.000Z"
}
```

**读写**：
```javascript
// 读
const account = await env.KV.get("account:ivy9eel@outlook.com", "json");

// 写（merge 模式）
const existing = await env.KV.get(key, "json") || {};
const merged = { ...existing, ...newData, updated_at: new Date().toISOString() };
await env.KV.put(key, JSON.stringify(merged));
```

### 模式 2：前缀扫描（模拟 SELECT * FROM table）

```javascript
// 列出所有账号
const { keys } = await env.KV.list({ prefix: "account:" });
// keys = [{ name: "account:ivy9eel@outlook.com" }, { name: "account:kiwi9lead@163.com" }, ...]

// 逐个读取值
const accounts = await Promise.all(
  keys.map(k => env.KV.get(k.name, "json"))
);
```

⚠️ **注意**：`list()` 每次最多返回 1000 个 key。超过需要用 `cursor` 分页。

### 模式 3：时间序列日志

```javascript
// Key: fail_log:{username}:{date}
// 同一账号同一天只有一条记录（天然去重）
await env.KV.put(
  `fail_log:ivy9eel@outlook.com:2026-05-21`,
  JSON.stringify({ reason: "HTTP 429", created_at: "..." })
);

// 查询某账号所有失败记录
const { keys } = await env.KV.list({ prefix: "fail_log:ivy9eel@outlook.com:" });
```

### 模式 4：配置/单值存储

```javascript
// 简单值
await env.KV.put("config:cron_hour", JSON.stringify([0, 8, 16]));
const hours = await env.KV.get("config:cron_hour", "json"); // [0, 8, 16]
```

### 模式 5：TTL 自动过期（锁/缓存）

```javascript
// 60 秒后自动删除的锁
await env.KV.put("lock:checkin:_all", "1", { expirationTtl: 60 });

// 检查锁是否存在
const locked = await env.KV.get("lock:checkin:_all");
if (locked) return "操作进行中";
```

## 四、KV 的局限性与应对

### 局限 1：无法按 value 查询

❌ 不能做：`SELECT * FROM accounts WHERE status = 'failed'`

✅ 应对：读出所有数据后在代码中过滤

```javascript
const accounts = await listAccounts(env);
const failed = accounts.filter(a => a.status === "failed");
```

### 局限 2：无事务

❌ 不能做：原子性地同时更新两个 key

✅ 应对：设计上避免需要事务的场景，或用乐观锁模式

### 局限 3：最终一致性

写入后，全球其他边缘节点可能需要 60 秒才能看到新值。

✅ 应对：对一致性要求高的数据用 D1

### 局限 4：value 大小限制 25MB

✅ 应对：单个 value 不要存太多数据，拆分成多个 key

## 五、何时该从 KV 升级到 D1

当你发现以下情况时，考虑迁移到 D1：

1. **频繁需要按条件筛选** — 每次都要 list 全部再 filter
2. **需要关联查询** — 比如"查询某用户的所有邮件及其消息"
3. **数据量超过几千条** — list 分页变得麻烦
4. **需要聚合统计** — COUNT、SUM、AVG 等
5. **需要强一致性** — 写入后立即需要读到最新值

moemail 就是典型例子：邮件系统需要 `emails → messages` 的关联查询，用 D1 + Drizzle ORM 是正确选择。

## 六、wucurcheck 的 KV 数据架构总览

```
Namespace: worker-dashboard KV
├── account:{username}           # 账号主数据（~30 条）
├── fail_log:{username}:{date}   # 签到失败日志
├── config:cron_hour             # 定时签到小时配置
├── config:users                 # 多用户配置
└── lock:{action}:{target}       # 操作防重锁（TTL 自动过期）
```

这个规模用 KV 完全够用。如果未来账号数量增长到几百上千，且需要复杂查询（如"按余额排序"、"统计每日签到成功率"），再考虑迁移到 D1。
