# Worker Dashboard TypeScript 迁移设计

> ✅ **已完成** — 2026-05-21 执行完毕，所有代码已迁移到 TypeScript，tsc --noEmit 零错误。

## 目标

将 worker-dashboard 从 JavaScript 迁移到 TypeScript，引入强类型约束、接口定义和面向对象设计，提升 AI 协作开发的代码质量保障。

## 设计原则

1. **面向接口编程**：所有模块间依赖通过 `interface` 定义，不依赖具体实现
2. **面向对象**：业务实体用 class/type 建模，KV 操作封装为 Repository 模式
3. **模块化**：每个文件单一职责，通过 barrel export 组织
4. **Worker 最佳实践**：`wrangler types` 生成 Env 类型，零手写 binding 类型
5. **TS 最佳实践**：strict mode、no-any、branded types for IDs
6. **日志规范**：类型安全的结构化日志
7. **代码规范**：ESLint + Prettier + strict tsconfig

## 类型系统设计

### 核心业务类型

```typescript
// types/account.ts
export interface Account {
  username: string;
  password: string;
  platform: "wucur" | "kiro";
  status: AccountStatus;
  balance?: string;
  checkin_time?: string;
  last_result?: string;
  created_at: string;
  updated_at: string;
  // Kiro-specific
  access_token?: string;
  refresh_token?: string;
  subscription_type?: string;
  usage_current?: number;
  usage_limit?: number;
  days_remaining?: number;
}

export type AccountStatus = "active" | "failed" | "pending" | "suspended";

// types/fail-log.ts
export interface FailLogEntry {
  username: string;
  date: string;       // YYYY-MM-DD
  reason: string;
  created_at: string;
}
```

### Repository 接口

```typescript
// ports/account-repository.ts
export interface AccountRepository {
  list(): Promise<Account[]>;
  get(username: string): Promise<Account | null>;
  put(username: string, data: Partial<Account>): Promise<Account>;
  delete(username: string): Promise<void>;
}

// ports/fail-log-repository.ts
export interface FailLogRepository {
  write(username: string, entry: { date: string; reason: string }): Promise<void>;
  query(username: string): Promise<FailLogEntry[]>;
}
```

### Env 类型（wrangler types 自动生成）

```typescript
// worker-configuration.d.ts (auto-generated)
interface Env {
  KV: KVNamespace;
  ADMIN_USER: string;
  ADMIN_PASS: string;
  CALLBACK_SECRET: string;
  GITHUB_REPO: string;
  GITHUB_TOKEN: string;
  GITHUB_WORKFLOW: string;
  WORKER_URL: string;
  WORKER_SECRET?: string;
}
```

### 路由类型

```typescript
// types/handler.ts
export type RouteHandler = (request: Request, env: Env) => Promise<Response>;

export interface Route {
  method: "GET" | "POST";
  path: string;
  handler: RouteHandler;
}
```

### 日志类型

```typescript
// lib/log.ts
interface LogFields {
  [key: string]: string | number | boolean | null | undefined;
}

interface Logger {
  info(msg: string, fields?: LogFields): void;
  warn(msg: string, fields?: LogFields): void;
  error(msg: string, fields?: LogFields): void;
}
```

## 目录结构

```
src/
├── index.ts                    # Worker 入口（fetch + scheduled）
├── router.ts                   # 路由分发
├── types/                      # 类型定义
│   ├── account.ts
│   ├── fail-log.ts
│   ├── handler.ts
│   └── index.ts                # barrel export
├── constants.ts                # 常量（KV 前缀、TTL、Content-Type）
├── lib/                        # 基础设施
│   ├── log.ts                  # 结构化日志
│   ├── crypto.ts               # timing-safe compare
│   ├── static.ts               # 静态文件服务
│   └── response.ts             # Response 工厂（html/json/notFound）
├── repositories/               # 数据访问层（实现 Repository 接口）
│   ├── kv-account-repository.ts
│   ├── kv-fail-log-repository.ts
│   └── kv-session-repository.ts
├── services/                   # 业务逻辑
│   ├── auth-service.ts
│   ├── account-manager.ts
│   ├── github-dispatch.ts
│   └── kiro/
│       ├── token-service.ts
│       └── sso-device-auth.ts
├── handlers/                   # 路由处理器（替代 pages/）
│   ├── accounts.ts
│   ├── account-detail.ts
│   ├── actions.ts
│   ├── callback.ts
│   └── settings.ts
├── views/                      # 视图层
│   ├── helpers.ts
│   ├── account-table.ts
│   ├── modals.ts
│   └── settings-panel.ts
├── templates/                  # Mustache 模板（不变）
│   └── ...
└── islands/                    # 客户端 JS（不变，不需要 TS）
    └── ...
```

## 关键设计模式

### 1. Repository 模式（数据访问层）

```typescript
// repositories/kv-account-repository.ts
import { KV_PREFIX } from "../constants";
import { log } from "../lib/log";
import type { Account, AccountRepository } from "../types";

export class KvAccountRepository implements AccountRepository {
  constructor(private readonly kv: KVNamespace) {}

  async list(): Promise<Account[]> {
    const { keys, list_complete } = await this.kv.list({ prefix: KV_PREFIX.ACCOUNT });
    if (!list_complete) log.warn("kv_list_truncated", { count: keys.length });

    const values = await Promise.all(
      keys.map((k) => this.kv.get<Account>(k.name, "json"))
    );
    return values.filter((v): v is Account => v !== null);
  }

  async get(username: string): Promise<Account | null> {
    if (!username) return null;
    return this.kv.get<Account>(`${KV_PREFIX.ACCOUNT}${username}`, "json");
  }

  async put(username: string, data: Partial<Account>): Promise<Account> {
    const existing = (await this.get(username)) ?? ({} as Partial<Account>);
    const merged: Account = {
      ...existing,
      ...data,
      username,
      updated_at: new Date().toISOString(),
      created_at: existing.created_at ?? new Date().toISOString(),
    } as Account;

    await this.kv.put(`${KV_PREFIX.ACCOUNT}${username}`, JSON.stringify(merged));
    log.info("account_updated", { username });
    return merged;
  }

  async delete(username: string): Promise<void> {
    if (!username) return;
    await this.kv.delete(`${KV_PREFIX.ACCOUNT}${username}`);
    log.info("account_deleted", { username });
  }
}
```

### 2. Response 工厂（消除重复）

```typescript
// lib/response.ts
import { CONTENT_TYPE } from "../constants";

export const Res = {
  html: (body: string) =>
    new Response(body, { headers: { "Content-Type": CONTENT_TYPE.HTML } }),

  json: (data: unknown, status = 200) =>
    Response.json(data, { status }),

  notFound: () =>
    new Response("Not Found", { status: 404 }),

  error: (code: string, message: string, status = 400) =>
    Response.json({ success: false, error_code: code, error: message }, { status }),
};
```

### 3. 类型安全的路由

```typescript
// router.ts
import type { Route, RouteHandler } from "./types";

const routes: Route[] = [
  { method: "GET", path: "/", handler: handleAccounts },
  { method: "GET", path: "/api/accounts", handler: handleApiAccounts },
  { method: "POST", path: "/api/trigger", handler: handleTrigger },
  // ...
];

export function router(path: string, method: string, request: Request, env: Env): Promise<Response> {
  const route = routes.find((r) => r.method === method && r.path === path);
  if (route) return route.handler(request, env);

  // Dynamic routes
  if (method === "GET" && path.startsWith("/api/account/")) return handleAccountDetail(request, env);
  if (method === "GET" && path.startsWith("/static/")) return Promise.resolve(serveStatic(path));

  return Promise.resolve(Res.notFound());
}
```

### 4. 依赖注入（通过 Env 传递）

```typescript
// index.ts
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // 每个请求创建 repository 实例（Worker 无状态，无需单例）
    const accounts = new KvAccountRepository(env.KV);
    const failLogs = new KvFailLogRepository(env.KV);
    // 传入 handler context...
  }
}
```

> 注意：Worker 是无状态的，每次请求都是独立的。不需要 DI 容器，直接在入口构造即可。

## TypeScript 配置

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ESNext"],
    "types": ["./worker-configuration.d.ts"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "exactOptionalPropertyTypes": false,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true
  },
  "include": ["src/**/*.ts", "worker-configuration.d.ts"],
  "exclude": ["node_modules", "dist"]
}
```

## ESLint 配置

```jsonc
// .eslintrc.json
{
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint"],
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/strict-type-checked"
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "@typescript-eslint/naming-convention": [
      "error",
      { "selector": "interface", "format": ["PascalCase"] },
      { "selector": "typeAlias", "format": ["PascalCase"] }
    ]
  }
}
```

## 迁移步骤

```
1. 初始化 TS 环境                          (15 min)
   - 安装 typescript, @cloudflare/workers-types, eslint 相关
   - 创建 tsconfig.json, .eslintrc.json
   - wrangler.toml main 改为 src/index.ts
   - 运行 wrangler types 生成 Env

2. 创建 types/ 目录，定义所有接口            (20 min)
   - Account, FailLogEntry, Route, RouteHandler
   - Repository interfaces

3. 迁移 lib/ 层                            (30 min)
   - constants.ts, log.ts, crypto.ts, static.ts, response.ts
   - 新建 repositories/ 实现 Repository 接口

4. 迁移 handlers/ 层                       (30 min)
   - 原 pages/*.js → handlers/*.ts
   - 使用 Repository 接口而非直接操作 KV

5. 迁移 views/ 层                          (15 min)
   - helpers.ts, account-table.ts, modals.ts

6. 迁移入口 + 路由                          (15 min)
   - index.ts, router.ts, auth-service.ts

7. 验证 + 清理                             (15 min)
   - tsc --noEmit 通过
   - wrangler dev 启动正常
   - 删除所有 .js 文件
```

**预计总耗时：2-2.5 小时**

## 迁移后的质量保障

| 保障层 | 工具 | 作用 |
|--------|------|------|
| 编译时 | `tsc --strict` | 类型错误零容忍 |
| 编码时 | ESLint strict | 禁止 any、强制返回类型 |
| 构建时 | `wrangler types` | Env binding 类型自动同步 |
| CI | `tsc --noEmit && eslint` | PR 门禁 |

## 不迁移的部分

- `templates/*.mustache` — 纯 HTML，无需 TS
- `islands/*.island.js` — 客户端脚本，浏览器运行，保持 JS（体积小、无构建）
