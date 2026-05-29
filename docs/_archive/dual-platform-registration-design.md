# 双平台并行注册设计方案

## 目标

Worker 同时向 GitHub Actions + GitLab CI 发起注册请求，一次操作注册 2 个 Kiro 账号，产出翻倍。

## 架构

```
用户点"注册 Kiro"
       │
       ▼
  Worker /api/trigger (action: register_kiro)
       │
       ├──→ GitHub Actions (register_kiro.yml)
       │      邮箱域名: ouraihub.com
       │      注册完 → 回调 Worker /callback
       │
       └──→ GitLab CI (register_kiro pipeline)
              邮箱域名: <第二个域名>
              注册完 → 回调 Worker /callback
```

## 前置条件

1. **第二个邮箱域名**：需要一个不同于 `ouraihub.com` 的域名，配置到 OurAIHub 或其他临时邮箱服务
2. **GitLab 账号**：免费版即可（400 分钟/月）
3. **GitLab Runner**：用 GitLab 共享 Runner（免费，有 Chromium）

## 实现步骤

### 1. GitLab 仓库设置

- 在 GitLab 创建一个私有仓库（如 `kiro-register`）
- 只放注册相关代码（精简版，不需要整个项目）
- 或者直接 mirror GitHub 仓库

### 2. GitLab CI 配置

```yaml
# .gitlab-ci.yml
stages:
  - register

register_kiro:
  stage: register
  image: mcr.microsoft.com/playwright/python:v1.40.0-jammy
  rules:
    - if: $CI_PIPELINE_SOURCE == "trigger"
  variables:
    PYTHONIOENCODING: utf-8
  script:
    - pip install uv && uv sync
    - |
      uv run python python/src/cli/register_kiro.py \
        --email-provider ouraihub \
        --email-api-key $EMAIL_API_KEY \
        --email-domain $EMAIL_DOMAIN \
        --headless \
        --code-timeout 180 \
        --json > result.json
    - cat result.json
  after_script:
    - |
      if [ -f result.json ] && [ -n "$CALLBACK_URL" ]; then
        curl -X POST "$CALLBACK_URL" \
          -H "Content-Type: application/json" \
          -d "{\"secret\":\"$CALLBACK_SECRET\",\"action\":\"batch_result\",\"data\":{\"results\":[$(cat result.json)]}}"
      fi
  artifacts:
    paths:
      - result.json
```

### 3. GitLab CI Variables（在 GitLab 项目 Settings > CI/CD > Variables 设置）

| 变量 | 值 |
|------|-----|
| `EMAIL_API_KEY` | OurAIHub API Key |
| `EMAIL_DOMAIN` | 第二个邮箱域名 |
| `CALLBACK_URL` | `https://worker-dashboard.ouraihub.workers.dev/callback` |
| `CALLBACK_SECRET` | 和 Worker 的 CALLBACK_SECRET 一致 |

### 4. GitLab Pipeline Trigger Token

在 GitLab 项目 Settings > CI/CD > Pipeline trigger tokens 创建一个 token。

### 5. Worker 新增 GitLab dispatch 模块

```typescript
// services/gitlab.ts
export async function triggerGitlabPipeline(env: Env, inputs: Record<string, string>): Promise<{ ok: boolean; error?: string }> {
  const projectId = env.GITLAB_PROJECT_ID;  // e.g. "12345678"
  const token = env.GITLAB_TRIGGER_TOKEN;

  if (!projectId || !token) return { ok: false, error: "GitLab not configured" };

  const resp = await fetch(
    `https://gitlab.com/api/v4/projects/${projectId}/trigger/pipeline`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        ref: "main",
        variables: inputs,
      }),
    }
  );

  if (!resp.ok) return { ok: false, error: `GitLab ${resp.status}` };
  return { ok: true };
}
```

### 6. Worker 注册逻辑改造

```typescript
// handlers/actions.ts 中 register_kiro 处理
async function handleRegisterKiro(target, body, env, request) {
  const callbackUrl = new URL("/callback", request.url).toString();
  const count = parseInt(body.inputs?.count || "1");

  // 分配：一半给 GitHub，一半给 GitLab
  const githubCount = Math.ceil(count / 2);
  const gitlabCount = count - githubCount;

  const results = await Promise.allSettled([
    // GitHub: 用 ouraihub.com
    triggerWorkflow(env, {
      action: "register_kiro",
      callbackUrl,
      inputs: { count: String(githubCount), email_domain: "ouraihub.com" },
    }),
    // GitLab: 用第二个域名
    gitlabCount > 0
      ? triggerGitlabPipeline(env, {
          EMAIL_DOMAIN: "second-domain.com",
          COUNT: String(gitlabCount),
          CALLBACK_URL: callbackUrl,
          CALLBACK_SECRET: env.CALLBACK_SECRET,
        })
      : Promise.resolve({ ok: true }),
  ]);

  return Res.json({ success: true, github: githubCount, gitlab: gitlabCount });
}
```

### 7. Worker 新增环境变量

| 变量 | 说明 | 设置方式 |
|------|------|----------|
| `GITLAB_PROJECT_ID` | GitLab 项目 ID | wrangler.toml [vars] |
| `GITLAB_TRIGGER_TOKEN` | Pipeline trigger token | wrangler secret |

## 风控注意事项

- **不同域名**：GitHub 用 `ouraihub.com`，GitLab 用另一个域名，避免同域名频率限制
- **时间间隔**：两边同时触发没问题（不同 IP、不同邮箱）
- **IP 差异**：GitHub Actions 和 GitLab CI 出口 IP 不同，天然分散

## 成本

| 平台 | 免费额度 | 每次注册耗时 | 每月可注册 |
|------|----------|-------------|-----------|
| GitHub Actions | 2000 分钟 | ~3 分钟 | ~660 个 |
| GitLab CI | 400 分钟 | ~3 分钟 | ~130 个 |
| **合计** | | | **~790 个/月** |

## 执行计划

1. 准备第二个邮箱域名（配置到 OurAIHub）
2. 创建 GitLab 仓库 + CI 配置
3. Worker 新增 `gitlab.ts` + 修改注册逻辑
4. 测试：单独触发 GitLab pipeline 验证注册成功
5. 联调：Worker 同时触发两边
