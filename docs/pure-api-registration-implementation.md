# 纯 API 注册实现详细设计

> 本文档包含完整上下文，供新会话继续执行。

## 当前状态

- 分支：`feat/pure-api-register`（已创建，基于 main）
- 目录：`wucurcheck/node-register/src/`（已创建，空）
- 源码位置：`/home/administrator/workspace/open-source/Kiro-account-manager/Kiro-account-manager/src/main/registration/`

## 目标

从 Kiro-account-manager 项目移植纯 API 注册模块到 `wucurcheck/node-register/`，作为现有 Playwright 方案的**并行选项**（不替代）。

## 源文件清单（需移植）

```
Kiro-account-manager/Kiro-account-manager/src/main/registration/
├── registrar.ts          # 49KB - 13步注册流程主逻辑（核心）
├── fingerprint.ts        # 13KB - 指纹数据组装 + XXTEA 加密
├── browser-identity.ts   # 10KB - 随机指纹生成（GPU/Canvas/WebGL/Math/Screen）
├── xxtea.ts              # 5KB  - XXTEA 加密算法
├── jwe.ts                # 2KB  - JWE/RSA 密码加密
├── email-service.ts      # 19KB - 邮箱验证码（MoEmail/TempMail/Outlook）
├── http-utils.ts         # 4KB  - HTTP 请求工具
├── config.ts             # 2KB  - 配置常量
└── index.ts              # 285B - 导出
```

## 关键依赖

### tlsclientwrapper（TLS 指纹模拟）

- 用途：所有 HTTP 请求通过它发送，模拟 Chrome 144 的 TLS 握手
- 实现：Go 编译的共享库（`.dll`/`.so`），通过 Node.js FFI 调用
- 当前只有 Windows DLL：`resources/tls-client-xgo-1.14.0-windows-amd64.dll`
- **需要下载 Linux 版本**：从 https://github.com/bogdanfinn/tls-client/releases 下载 `tls-client-linux-amd64-v1.14.0.so`
- npm 包：`tlsclientwrapper`（需要 `npm install tlsclientwrapper`）

### 其他依赖

- `undici`：HTTP 客户端（邮箱 API 调用，不走 TLS 模拟）
- `node-forge` 或 Node.js `crypto`：RSA/JWE 加密

## 适配要点

### 1. 去除 Electron 依赖

`registrar.ts` 中有 Electron 特有的代码需要替换：

```typescript
// 原代码
import { app } from 'electron'
const tmpDir = app.getPath('temp')

// 替换为
import { tmpdir } from 'os'
const tmpDir = tmpdir()
```

### 2. tls-client 共享库路径

```typescript
// 原代码：从 resources/ 复制 dll 到 tmpdir
// 适配：直接指定 Linux .so 路径
const libPath = path.join(__dirname, '../lib/tls-client-linux-amd64.so')
```

### 3. 邮箱服务适配

原代码支持 MoEmail、TempMail.Plus、Outlook。我们只需要 OurAIHub：

```typescript
// 新增 OurAIHub 适配
class OuraihubEmailService implements EmailService {
  constructor(private apiKey: string, private domain: string) {}
  
  async createEmail(prefix: string): Promise<string> { ... }
  async pollVerificationCode(timeout: number): Promise<string | null> { ... }
}
```

### 4. 代理支持

```typescript
// registrar.ts 中的 sessionOpts
this.sessionOpts = {
  clientIdentifier: 'chrome_144',
  proxyUrl: process.env.HTTPS_PROXY || '',
}
```

## 目标目录结构

```
wucurcheck/node-register/
├── package.json
├── tsconfig.json
├── lib/
│   └── tls-client-linux-amd64.so    # 从 GitHub releases 下载
├── src/
│   ├── index.ts                      # CLI 入口
│   ├── registrar.ts                  # 移植自 Kiro-account-manager（去 Electron）
│   ├── fingerprint.ts                # 直接复制
│   ├── browser-identity.ts           # 直接复制
│   ├── xxtea.ts                      # 直接复制
│   ├── jwe.ts                        # 直接复制
│   ├── email/
│   │   └── ouraihub.ts              # OurAIHub 邮箱适配
│   ├── http-utils.ts                 # 移植（去 Electron）
│   └── config.ts                     # 移植
└── dist/                             # 编译产物
```

## CLI 接口设计

```bash
node dist/index.js \
  --count 1 \
  --email-domain ouraihub.com \
  --email-api-key <KEY> \
  --proxy socks5://... \
  --output results.json
```

输出 JSON：
```json
[{
  "success": true,
  "email": "xxx@ouraihub.com",
  "password": "随机生成",
  "sso_token": "...",
  "access_token": "...",
  "refresh_token": "...",
  "client_id": "...",
  "client_secret": "...",
  "region": "us-east-1",
  "expires_in": 3600
}]
```

## 执行步骤

### Step 1: 初始化项目
```bash
cd wucurcheck/node-register
npm init -y
npm install typescript tlsclientwrapper undici
npm install -D @types/node
```

### Step 2: 下载 tls-client Linux 共享库
```bash
mkdir -p lib
wget -O lib/tls-client-linux-amd64.so \
  https://github.com/bogdanfinn/tls-client/releases/download/v1.14.0/tls-client-linux-amd64-v1.14.0.so
```

### Step 3: 复制核心文件
```bash
cp Kiro-account-manager/.../registration/{fingerprint,browser-identity,xxtea,jwe,config}.ts src/
cp Kiro-account-manager/.../registration/registrar.ts src/
cp Kiro-account-manager/.../registration/http-utils.ts src/
```

### Step 4: 适配代码
- 去除所有 `import { app } from 'electron'`
- 替换 `app.getPath('temp')` → `os.tmpdir()`
- 替换 tls-client 库路径为 `./lib/tls-client-linux-amd64.so`
- 新增 `email/ouraihub.ts`
- 写 `index.ts` CLI 入口

### Step 5: 本地测试
```bash
npx tsc
node dist/index.js --count 1 --email-domain ouraihub.com --email-api-key mk_w-FBheYGFY-nmW-sR6IxCUAlyaPanM2W
```

### Step 6: 写 GitHub Actions workflow
```yaml
# .github/workflows/register_kiro_api.yml
runs-on: ubuntu-latest
steps:
  - checkout
  - setup-node 20
  - cd node-register && npm ci && npm run build
  - node dist/index.js --count ${{ inputs.count }} ...
  - 回调 Worker
```

### Step 7: Worker 集成
在 `services/github.ts` 中加映射：
```typescript
: action === "register_kiro_api"
? "register_kiro_api.yml"
```

Dashboard 注册弹窗加一个"注册方式"选择：浏览器 / 纯 API。

## 注意事项

1. **tls-client .so 文件约 25MB**，不要提交到 git，用 GitHub Releases 或 workflow 中下载
2. **OurAIHub API Key**：`mk_w-FBheYGFY-nmW-sR6IxCUAlyaPanM2W`（设为 secret）
3. **registrar.ts 很大（49KB/900行）**，移植时重点关注：
   - `register()` 方法（主流程）
   - `initWorkflow()` / `submitEmail()` / `signupWorkflow()` / `createIdentity()` / `setPassword()`
   - `ssoDeviceAuth()` 方法（获取 token）
4. **现有 Playwright 方案保留不动**，纯 API 是新增的并行选项
