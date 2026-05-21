# DESIGN.md — Worker Dashboard 设计规范

## 1. Visual Theme & Atmosphere

- **风格**: 管理后台，信息密度中等，功能优先
- **基调**: 简洁、专业、可切换主题（35 个 daisyUI 主题）
- **默认主题**: light（浅色）
- **密度**: 紧凑表格 + 宽松卡片混合

## 2. Technology Stack

| 层 | 技术 | 说明 |
|---|------|------|
| 语言 | TypeScript (strict) | 零 any，Repository 模式 |
| CSS 框架 | Tailwind CSS 4 (Browser CDN) | 实用类优先 |
| 组件库 | daisyUI 5 (CDN) | 语义化 class |
| 模板 | Mustache | 服务端渲染，HTML 与逻辑分离 |
| 交互 | HTMX 2.0 (CDN) | 声明式 hx-post/hx-get |
| 客户端 JS | Islands 架构 | 4 个独立小文件，按需加载 |
| 构建 | wrangler (esbuild) | TS → 单文件 bundle |
| 类型生成 | `wrangler types` | Env 接口自动同步 |

### CDN 引入

```html
<link href="https://cdn.jsdelivr.net/npm/daisyui@5" rel="stylesheet" type="text/css"/>
<link href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css" rel="stylesheet" type="text/css"/>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
```

## 3. Layout Principles

### 页面骨架

```
┌─────────────────────────────────────────┐
│ Drawer (lg:drawer-open)                 │
│ ┌──────────┬────────────────────────────┤
│ │ Sidebar  │ Content                    │
│ │ w-64     │ p-4 md:p-6                 │
│ │          │ bg-base-200                │
│ │ menu     │ min-h-screen               │
│ │          │                            │
│ │ ──────── │                            │
│ │ theme    │                            │
│ │ logout   │                            │
│ └──────────┴────────────────────────────┤
└─────────────────────────────────────────┘
```

- 侧边栏: `drawer-side` + `w-64` + `bg-base-100`
- 内容区: `drawer-content` + `bg-base-200`
- 移动端: navbar 顶部 + drawer toggle

### 间距规则

| 用途 | Class |
|------|-------|
| 页面内边距 | `p-4 md:p-6` |
| 卡片间距 | `mt-4` 或 `mt-6` |
| 卡片内边距 | `p-4` |
| 表格行间距 | `table-sm`（daisyUI 紧凑） |
| 按钮组间距 | `gap-2` |

## 4. Component Catalog

### 按钮

| 用途 | Class | 示例 |
|------|-------|------|
| 主操作 | `btn btn-primary btn-sm` | 签到、保存 |
| 成功操作 | `btn btn-success btn-sm` | 注册 |
| 强调操作 | `btn btn-accent btn-sm` | 一键签到 |
| 危险操作 | `btn btn-error btn-sm btn-outline` | 删除 |
| 次要操作 | `btn btn-ghost btn-sm` | 导出、详情 |
| 警告操作 | `btn btn-warning btn-sm` | 修改密码 |
| 加载中 | 追加 `loading loading-spinner` | — |

### 表格

```html
<div class="overflow-x-auto bg-base-100 rounded-box shadow">
  <table class="table table-sm">
    <thead><tr><th>...</th></tr></thead>
    <tbody><tr>...</tr></tbody>
  </table>
</div>
```

- 始终包裹 `overflow-x-auto`（移动端横向滚动）
- 使用 `table-sm` 紧凑模式
- 外层 `rounded-box shadow` 提供卡片感

### 统计卡片

```html
<div class="stats shadow mb-4">
  <div class="stat">
    <div class="stat-title">标题</div>
    <div class="stat-value">数值</div>
  </div>
</div>
```

- 数值颜色: 成功用 `text-success`，警告用 `text-warning`

### 徽章 (Badge)

| 状态 | Class |
|------|-------|
| active | `badge badge-sm badge-success` |
| pending | `badge badge-sm badge-warning` |
| failed | `badge badge-sm badge-error` |
| expired/unknown | `badge badge-sm badge-ghost` |

### 弹窗 (Modal/Dialog)

```html
<dialog id="xxx" class="modal">
  <div class="modal-box">
    <h3 class="text-lg font-bold mb-4">标题</h3>
    <!-- 内容 -->
    <div class="modal-action">
      <form method="dialog"><button class="btn btn-sm">关闭</button></form>
      <button class="btn btn-success btn-sm" onclick="...">确认</button>
    </div>
  </div>
</dialog>
```

- 使用原生 `<dialog>` + daisyUI `modal` class
- 通过 `.showModal()` / `.close()` 控制

### 下拉菜单

```html
<div class="dropdown dropdown-end">
  <label tabindex="0" class="btn btn-sm">触发</label>
  <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box shadow w-48 z-10">
    <li><a onclick="...">选项</a></li>
  </ul>
</div>
```

### Toast 通知

```html
<div id="toast" class="toast toast-end z-50 hidden">
  <div class="alert" id="toast-msg"></div>
</div>
```

- 成功: `alert-success`
- 失败: `alert-error`
- 3 秒后自动隐藏

### 表单输入

| 类型 | Class |
|------|-------|
| 文本输入 | `input input-bordered input-sm w-full` |
| 数字输入 | `input input-bordered input-sm w-full` + `type="number"` |
| 下拉选择 | `select select-bordered select-sm w-full` |
| 密码输入 | `input input-bordered input-sm w-48` + `type="password"` |
| 复选框 | `checkbox checkbox-xs` |

### 设置面板

```html
<div class="mt-4 bg-base-100 rounded-box shadow p-4">
  <h3 class="font-bold mb-2">🔑 标题</h3>
  <!-- 内容 -->
</div>
```

## 5. Color Roles

由 daisyUI 主题自动管理，不硬编码颜色值：

| 语义 | CSS 变量 | 用途 |
|------|---------|------|
| `base-100` | 卡片/表格背景 | 内容容器 |
| `base-200` | 页面背景 | 内容区底色 |
| `base-300` | 边框 | 分隔线 |
| `base-content` | 文字 | 正文 |
| `primary` | 主色 | 主按钮、链接 |
| `success` | 绿色 | 成功状态 |
| `warning` | 黄色 | 警告状态 |
| `error` | 红色 | 错误/危险 |

## 6. Typography

- 标题: `text-2xl font-bold`（页面标题）
- 副标题: `font-bold mb-2`（卡片标题）
- 正文: 默认（14-16px，由主题决定）
- 等宽: `font-mono`（用户名、密码）
- 小字: `text-xs`（提示、时间）
- 超小: `text-xs text-base-content/50`（辅助说明）

## 7. Responsive Behavior

| 断点 | 行为 |
|------|------|
| `lg:` (1024px+) | Drawer 常开，侧边栏可见 |
| `< lg` | Drawer 收起，顶部 navbar + hamburger |
| 表格 | `overflow-x-auto` 横向滚动 |
| 按钮组 | `flex flex-wrap gap-2` 自动换行 |
| Stats | 默认横排，小屏可加 `stats-vertical` |

## 8. Do's and Don'ts

### ✅ Do

- 用 daisyUI 语义 class（`btn-primary`），不用原始 Tailwind 颜色（`bg-blue-500`）
- 用 `data-theme` 切换主题，不硬编码颜色
- 表格外层包 `overflow-x-auto`
- 危险操作加 `confirm()` 二次确认
- 密码默认脱敏（`••••••`），点击才显示
- Toast 3 秒自动消失
- 按钮操作中加 `loading loading-spinner`

### ❌ Don't

- 不要用内联 style
- 不要硬编码 hex 颜色值
- 不要用 `alert()` 替代 Toast
- 不要在表格里放太多按钮（最多 2-3 个）
- 不要让弹窗内容超过屏幕高度

## 9. File Structure (Views)

```
src/views/
├── helpers.js        → badge(), timeAgo(), esc() 等模板工具
├── account_table.js  → renderToolbar() + renderTable()
├── modals.js         → renderDetailModal() + renderRegisterModal()
├── settings_panel.js → renderSettingsPanel()
└── client_script.js  → renderClientScript() 所有前端 JS
```

新增 UI 组件时：
1. 在 `views/` 下创建对应文件，导出 `render*()` 函数
2. 在 `pages/accounts.js` 中 import 并组装到 content 数组
3. 前端 JS 逻辑统一放 `client_script.js`

## 10. Custom Component Rules

自定义组件必须与 daisyUI 风格一致，遵守以下规则：

### 颜色：只用 daisyUI CSS 变量

```css
/* ✅ 正确：跟随主题自动变 */
.custom-widget {
  background: oklch(var(--b1));        /* base-100 */
  color: oklch(var(--bc));             /* base-content */
  border: 1px solid oklch(var(--b3));  /* base-300 */
}

/* ❌ 禁止：硬编码颜色 */
.custom-widget {
  background: #ffffff;
  color: #333333;
}
```

### 可用 CSS 变量

| 变量 | 语义 | 对应 class |
|------|------|-----------|
| `--b1` | 基础背景 | `bg-base-100` |
| `--b2` | 次级背景 | `bg-base-200` |
| `--b3` | 边框/分隔 | `border-base-300` |
| `--bc` | 基础文字 | `text-base-content` |
| `--p` | 主色 | `bg-primary` |
| `--su` | 成功 | `bg-success` |
| `--wa` | 警告 | `bg-warning` |
| `--er` | 错误 | `bg-error` |
| `--rounded-box` | 统一圆角 | `rounded-box` |

### 组合优先，不造新轮子

```html
<!-- ✅ 组合 daisyUI 现有 class -->
<div class="card bg-base-100 shadow">
  <div class="card-body p-4">
    <span class="badge badge-success badge-sm">状态</span>
    <button class="btn btn-primary btn-xs">操作</button>
  </div>
</div>

<!-- ❌ 不要自己写一套样式 -->
<div style="background:#fff; border-radius:8px; padding:16px;">
```

### 圆角和阴影

- 圆角统一用 `rounded-box`（跟随主题），不用 `rounded-lg`
- 阴影用 `shadow`（daisyUI 标准），不用 `shadow-md`

### 验证方法

自定义组件写完后，切换到以下主题检查是否正常：
- `light`（浅色）→ `dark`（深色）→ `dracula`（高对比）→ `pastel`（低对比）

四个主题下都可读、不破版，说明颜色用对了。

## 11. Agent Prompt Guide

当需要 AI 修改 UI 时，可以这样提示：

```
参考项目根目录的 DESIGN.md，使用 daisyUI 5 组件。
- 按钮用 btn btn-{variant} btn-sm
- 表格用 table table-sm + overflow-x-auto 包裹
- 弹窗用 <dialog> + modal class
- 状态用 badge badge-sm badge-{success/error/warning/ghost}
- 不要硬编码颜色，用 daisyUI 语义色
- 新组件放 src/views/ 下，导出 render 函数
```
