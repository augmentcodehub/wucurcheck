# 纯 API 注册方案设计（基于 Kiro-account-manager）

## 目标

用 Kiro-account-manager 的纯 API 注册逻辑替代当前 Playwright 浏览器方案，注册速度从 3 分钟降到 30 秒。

## 架构对比

```
当前方案（Playwright）：
  GitHub Actions → 安装 Python + Playwright + Chromium → 启动浏览器 → 填表 → 等验证码 → 3 分钟

新方案（纯 API）：
  GitHub Actions → 安装 Node.js → 跑 register.ts → 纯 HTTP 请求 → 等验证码 → 30 秒
```

## 核心模块（从 Kiro-account-manager 移植）

```
需要的文件：
├── browser-identity.ts    # 随机指纹生成（GPU/Canvas/WebGL/Math/Screen）
├── fingerprint.ts         # 指纹数据组装 + XXTEA 加密
├── xxtea.ts              # XXTEA 加密算法
├── registrar.ts          # 13 步注册流程编排
├── email-service.ts      # 邮箱验证码获取（对接 OurAIHub）
└── tlsclient-wrapper     # TLS 指纹模拟（可选，用 undici 替代）
```

## 实现方案

### 方案 A：直接在 workflow 中调用 Kiro-account-manager（最快）

```yaml
# .github/workflows/register_kiro_api.yml
name: 注册 Kiro (纯 API)
on:
  workflow_dispatch:
    inputs:
      count: { default: '1' }
      email_domain: { default: 'ouraihub.com' }
      callback_url: { default: '' }

jobs:
  register:
    runs-on: ubuntu-latest  # 不需要 Windows！不需要浏览器！
    steps:
    - uses: actions/checkout@v6
      with:
        repository: <Kiro-account-manager 仓库>

    - uses: actions/setup-node@v4
      with:
        node-version: '20'

    - run: npm install

    - name: 注册
      env:
        EMAIL_API_KEY: ${{ secrets.OURAIHUB_EMAIL_API_KEY }}
      run: |
        node dist/register.js \
          --count ${{ inputs.count }} \
          --email-domain ${{ inputs.email_domain }} \
          --email-api-key $EMAIL_API_KEY \
          --output results.json

    - name: 回调 Worker
      run: |
        curl -X POST "${{ inputs.callback_url }}" \
          -H "Content-Type: application/json" \
          -d "{\"secret\":\"${{ secrets.WORKER_CALLBACK_SECRET }}\",\"action\":\"batch_result\",\"data\":{\"results\":$(cat results.json)}}"
```

**优势**：
- `ubuntu-latest` 而非 `windows-2025`（启动快 30 秒）
- 不需要安装 Playwright/Chromium（省 1-2 分钟）
- 注册本身 30 秒 vs 3 分钟

### 方案 B：将核心模块集成到我们的仓库（更可控）

在 `wucurcheck` 仓库中新建 `node-register/` 目录，移植核心代码：

```
wucurcheck/
├── node-register/
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts           # CLI 入口
│   │   ├── registrar.ts       # 注册流程编排
│   │   ├── identity.ts        # 指纹生成
│   │   ├── crypto/
│   │   │   ├── xxtea.ts       # XXTEA
│   │   │   └── jwe.ts         # JWE 密码加密
│   │   ├── email/
│   │   │   └── ouraihub.ts    # OurAIHub 邮箱 API
│   │   └── types.ts           # 类型定义
│   └── dist/                   # 编译产物
```

对应的 workflow：

```yaml
# .github/workflows/register_kiro_api.yml
jobs:
  register:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v6
    - uses: actions/setup-node@v4
      with: { node-version: '20' }
    - run: cd node-register && npm ci && npm run build
    - run: |
        node node-register/dist/index.js \
          --count ${{ inputs.count }} \
          --email-domain ${{ inputs.email_domain }} \
          --output results.json
```

## TLS 指纹问题

Kiro-account-manager 用 `tlsclientwrapper`（native addon）模拟 Chrome TLS。替代方案：

| 方案 | 说明 | 难度 |
|------|------|------|
| 直接用 `tlsclientwrapper` | 需要在 GitHub Actions 上编译 | 中 |
| 用 `undici` + 默认 TLS | Node.js 的 TLS 指纹不像 Python 那么明显 | 低 |
| 用 `curl-impersonate` | 通过子进程调用，完美模拟 Chrome TLS | 低 |

**建议**：先用 `undici`（Node.js 内置 HTTP 客户端）试，如果被拦再加 `curl-impersonate`。

## 邮箱验证码对接

复用现有的 OurAIHub API：

```typescript
// email/ouraihub.ts
async function pollVerificationCode(emailId: string, apiKey: string, timeout = 120): Promise<string | null> {
  const deadline = Date.now() + timeout * 1000;
  while (Date.now() < deadline) {
    const resp = await fetch(`https://api.ouraihub.com/email/${emailId}/messages`, {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const messages = await resp.json();
    // 找 AWS 验证码邮件，提取 6 位数字
    for (const msg of messages) {
      const code = msg.body?.match(/(\d{6})/)?.[1];
      if (code) return code;
    }
    await sleep(3000);
  }
  return null;
}
```

## Worker 集成

Worker 的 `github.ts` 中加一个新的 workflow 映射：

```typescript
: action === "register_kiro_api"
? "register_kiro_api.yml"
```

Dashboard 注册按钮可以选择"快速注册（API）"或"浏览器注册"。

## 执行计划

1. **从 Kiro-account-manager 提取核心模块**（identity、crypto、registrar）
2. **适配邮箱接口**（对接 OurAIHub API）
3. **写 CLI 入口**（接收参数、输出 JSON 结果）
4. **本地测试**（`node dist/index.js --count 1`）
5. **写 workflow**（`register_kiro_api.yml`）
6. **Worker 集成**（新增 action 映射）

## 预期收益

| 指标 | 当前（Playwright） | 新方案（纯 API） |
|------|-------------------|-----------------|
| 注册耗时 | ~3 分钟 | ~30 秒 |
| Runner | windows-2025 | ubuntu-latest |
| 依赖安装 | Python + UV + Playwright + Chromium | Node.js（已缓存） |
| 启动开销 | ~90 秒 | ~10 秒 |
| 总耗时 | ~5 分钟/个 | ~1 分钟/个 |
| 月产能（GitHub 2000分钟） | ~400 个 | ~2000 个 |
| 反检测 | 极低（裸 Playwright） | 极高（伪造指纹） |
