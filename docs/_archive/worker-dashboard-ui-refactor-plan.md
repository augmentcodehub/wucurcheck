# Worker Dashboard UI 重构方案

> ✅ **已完成** — 2026-05-21 三个 Phase 全部执行完毕（Mustache + HTMX + Islands）。

## 目标

将当前手拼 HTML 字符串的方式，升级为 **Mustache 模板 + HTMX 局部更新 + Islands 交互**，提升可维护性和开发体验。

## 现状分析

```
当前架构：
  views/*.js  → 导出函数，返回 HTML 字符串（手拼模板字面量）
  client_script.js → 200 行内联 <script>，手写 fetch + DOM 操作
  layout.js → 整页 HTML 骨架

问题：
  1. HTML 和 JS 逻辑混在一起，难以维护
  2. client_script.js 是一个巨大的内联脚本，无法复用
  3. 每次操作都要手写 fetch → 解析 → 更新 DOM → toast
  4. 无法局部刷新，很多操作后直接 location.reload()
```

## 目标架构

```
src/
├── templates/           # Mustache 模板（纯 HTML，关注点分离）
│   ├── layout.mustache
│   ├── partials/
│   │   ├── toolbar.mustache
│   │   ├── wucur-table.mustache
│   │   ├── kiro-table.mustache
│   │   ├── detail-modal.mustache
│   │   └── settings.mustache
│   └── pages/
│       └── accounts.mustache
├── islands/             # 只在需要交互的地方加 JS（Islands 架构）
│   ├── toast.js         # 全局 toast 通知
│   ├── password-toggle.js
│   └── register-form.js # 注册表单验证逻辑
├── lib/                 # 不变
├── services/            # 不变
├── pages/               # 路由处理器（只负责数据准备 + 渲染模板）
└── index.js             # 不变
```

## 三步执行计划

### Phase 1：引入 Mustache 模板（1-2 小时）

**改动范围**：`views/` → `templates/`

**原则**：模板只负责展示，逻辑在路由处理器中完成。

Before（当前）：
```javascript
// views/account_table.js
export function renderWucurRows(accounts) {
  return accounts.map(a => `<tr>
    <td>${esc(a.username)}</td>
    <td>${badge(a.status)}</td>
    ...
  </tr>`).join("");
}
```

After（Mustache）：
```html
<!-- templates/partials/wucur-table.mustache -->
{{#accounts}}
<tr>
  <td>{{username}}</td>
  <td><span class="badge badge-sm {{statusClass}}">{{status}}</span></td>
  <td>{{balance}}</td>
  <td>{{timeAgo}}</td>
  <td>
    <button class="btn btn-xs btn-ghost"
      hx-get="/api/account/{{username}}"
      hx-target="#detail-body"
      hx-swap="innerHTML"
      onclick="document.getElementById('account-detail').showModal()">
      详情
    </button>
    <button class="btn btn-xs btn-primary"
      hx-post="/api/trigger"
      hx-vals='{"action":"checkin","target":"{{username}}"}'
      hx-swap="none">
      签到
    </button>
  </td>
</tr>
{{/accounts}}
```

**渲染方式**：
```javascript
// pages/accounts.js
import Mustache from "mustache";
import tableTemplate from "../templates/partials/wucur-table.mustache";

export async function pageAccounts(request, env) {
  const accounts = await listAccounts(env);
  const data = accounts.map(a => ({
    ...a,
    statusClass: { active: "badge-success", failed: "badge-error" }[a.status] || "badge-ghost",
    timeAgo: formatTimeAgo(a.checkin_time),
  }));
  const html = Mustache.render(tableTemplate, { accounts: data });
  return layout("账号管理", html);
}
```

**模板加载方式**：Worker 中用 `import` 导入文本文件：
```toml
# wrangler.toml
[rules]
  - { type = "Text", globs = ["**/*.mustache"] }
```

### Phase 2：引入 HTMX（1 小时）

**改动范围**：删除 `client_script.js` 中 80% 的 fetch 代码

**原则**：用 HTML 属性声明交互行为，不写 JS。

**layout.mustache 加载 HTMX**：
```html
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
```

**典型交互改造**：

Before（手写 fetch）：
```javascript
async function checkinUnchecked(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  const r = await fetch("/api/trigger", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({action:"checkin_unchecked"})
  });
  const d = await r.json();
  showToast(d.success ? "✅ 已触发" : "❌ 失败", d.success);
  btn.classList.remove("loading","loading-spinner");
}
```

After（HTMX 声明式）：
```html
<button class="btn btn-accent btn-sm"
  hx-post="/api/trigger"
  hx-vals='{"action":"checkin_unchecked"}'
  hx-swap="none"
  hx-indicator=".htmx-indicator"
  hx-on::after-request="showToast(event)">
  ⚡ 一键签到未签到
</button>
```

**需要新增的 API 端点**（返回 HTML 片段而非 JSON）：

| 端点 | 用途 | 返回 |
|------|------|------|
| `GET /api/account/:username` | 详情弹窗内容 | HTML partial |
| `GET /partials/wucur-table` | 刷新表格 | HTML partial |
| `POST /api/trigger` | 保持不变 | JSON（HTMX 用 `hx-swap="none"`） |

**HTMX 事件处理（toast 通知）**：
```javascript
// islands/toast.js — 唯一需要的全局 JS
document.body.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail.xhr;
  if (!xhr) return;
  try {
    const d = JSON.parse(xhr.responseText);
    if (d.success !== undefined) {
      showToast(d.success ? "✅ 操作成功" : `❌ ${d.error || "失败"}`, d.success);
    }
  } catch {}
});

function showToast(msg, ok) {
  const t = document.getElementById("toast");
  const m = document.getElementById("toast-msg");
  m.textContent = msg;
  m.className = "alert " + (ok ? "alert-success" : "alert-error");
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 3000);
}
```

### Phase 3：Islands 架构（30 分钟）

**原则**：页面默认是纯 HTML（零 JS），只在需要客户端交互的"岛屿"加载少量 JS。

**识别出的 Islands**：

| Island | 功能 | 大小 |
|--------|------|------|
| `toast.js` | 全局通知 | ~15 行 |
| `password-toggle.js` | 密码显示/隐藏 | ~5 行 |
| `register-form.js` | 注册表单预览 + 验证 | ~30 行 |
| `theme.js` | 主题切换持久化 | ~5 行 |

**加载方式**：
```html
<!-- 只在需要的页面底部加载对应 island -->
<script src="/static/islands/toast.js"></script>
<script src="/static/islands/register-form.js"></script>
```

**静态文件服务**（Worker 中）：
```javascript
// 在 router 中加一条
if (path.startsWith("/static/")) return serveStatic(path, env);
```

用 KV 或内联方式存储这些小 JS 文件（总共不到 100 行）。

## 迁移策略

**渐进式，不一次性重写**：

```
Week 1: Phase 1 — 模板化
  ├── 把 layout.js 改为 Mustache
  ├── 把 account_table.js 改为模板
  └── 验证：页面渲染结果不变

Week 2: Phase 2 — HTMX 化
  ├── 加载 HTMX CDN
  ├── 改造"签到"、"删除"等按钮为 hx-post
  ├── 新增 HTML partial 端点
  └── 删除 client_script.js 中对应的 fetch 代码

Week 3: Phase 3 — Islands 拆分
  ├── 把剩余 JS 拆成独立 island 文件
  ├── 删除 client_script.js（整个文件）
  └── 最终验证
```

## 预期收益

| 指标 | 当前 | 重构后 |
|------|------|--------|
| client JS 体积 | ~200 行内联 | ~60 行（4 个 island） |
| 模板可读性 | HTML 混在 JS 中 | 纯 HTML 文件 |
| 新增页面成本 | 写 JS 函数拼字符串 | 写 .mustache 模板 |
| 局部刷新 | 无（reload） | HTMX 自动 |
| 首屏 JS 阻塞 | 200 行 script 解析 | 接近零 |

## 依赖变更

```json
// package.json 新增
"dependencies": {
  "mustache": "^4.2.0"  // 已安装，无需新增
}
// CDN 引入（无需安装）
// htmx: https://unpkg.com/htmx.org@2.0.4
```

## 风险与注意事项

1. **Mustache 无逻辑限制**：复杂条件判断需要在渲染前预处理数据（如 `statusClass`），不能在模板里写 if-else
2. **HTMX 学习曲线**：团队需要熟悉 `hx-*` 属性，但文档简洁，1 小时可上手
3. **SEO 无影响**：管理后台不需要 SEO
4. **兼容性**：HTMX 支持所有现代浏览器
