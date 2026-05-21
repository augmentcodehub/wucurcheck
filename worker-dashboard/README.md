# Worker Dashboard

Cloudflare Worker 管理后台。TypeScript + Mustache + HTMX + DaisyUI。

## 快速开始

```bash
npm install
npx wrangler types          # 生成 Env 类型
npx tsc --noEmit            # 类型检查
npx wrangler dev            # 本地开发
npx wrangler deploy         # 部署
```

## 功能

- 🔐 多用户登录（admin/viewer 角色）
- 📊 Wucur / Kiro 账号管理
- ⚡ 一键签到 + 定时自动签到
- 📋 签到失败日志
- 📥 导出 CSV / JSON
- 🚀 Kiro token 刷新

## 文档

- [DESIGN.md](./DESIGN.md) — UI 设计规范 + 架构详情
