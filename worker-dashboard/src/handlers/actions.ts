/** API action handlers — strategy pattern dispatch */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { triggerWorkflow } from "../services/github.js";
import { triggerGitlabPipeline } from "../services/gitlab.js";
import { acquireLock } from "../lib/trigger-lock.js";
import { hasValidSession } from "../services/auth-service.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { Res } from "../lib/response.js";
import { isToday } from "../views/helpers.js";
import { DEFAULT_PASSWORD } from "../lib/constants.js";

async function handleDelete(target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  if (!target) return Res.error("MISSING_TARGET", "target required");
  const repo = new KvAccountRepository(env.KV);
  log.info("action_delete", { target });
  await repo.delete(target);
  return Res.json({ success: true, action: "delete", target });
}

async function handleDeleteAll(_target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  log.warn("action_delete_all", { count: String(accounts.length) });
  for (const a of accounts) await repo.delete(a.username);
  return Res.json({ success: true, action: "delete_all", count: accounts.length });
}

async function handleDeleteFailed(_target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const failed = accounts.filter((a) => a.status === "failed");
  log.info("action_delete_failed", { count: String(failed.length) });
  for (const a of failed) await repo.delete(a.username);
  return Res.json({ success: true, action: "delete_failed", count: failed.length });
}

async function handleCheckinUnchecked(_target: string, _body: Record<string, unknown>, env: Env, request: Request): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const wucurActive = accounts.filter((a) => (!a.platform || a.platform === "wucur") && a.status !== "suspended");
  const unchecked = wucurActive
    .filter((a) => !isToday(a.checkin_time))
    .map((a) => ({ username: a.username, password: a.password || DEFAULT_PASSWORD }));

  const usingDefault = unchecked.filter((a) => !accounts.find((x) => x.username === a.username)?.password);
  log.info("checkin_unchecked_select", {
    total_accounts: String(accounts.length),
    wucur_active: String(wucurActive.length),
    unchecked: String(unchecked.length),
    using_default_password: usingDefault.map((a) => a.username).join(",") || "none",
  });

  if (!unchecked.length) return Res.error("NO_UNCHECKED", "所有账号今日已签到");

  const callbackUrl = new URL("/callback", request.url).toString();
  const payload = JSON.stringify(unchecked);
  log.info("checkin_unchecked_dispatch", { payload_bytes: String(payload.length), count: String(unchecked.length) });
  const result = await triggerWorkflow(env, {
    action: "checkin_unchecked",
    callbackUrl,
    inputs: { accounts_json: payload },
  });

  if (!result.ok) {
    log.error("checkin_unchecked_dispatch_failed", { error: result.error || "" });
    return Res.error("DISPATCH_FAILED", result.error || "dispatch failed", 502);
  }
  return Res.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id, count: unchecked.length });
}

// NOTE: 直接从 Worker 刷新 token 会被 AWS OIDC 拦截（Cloudflare Workers 出口 IP 被限制，返回 520）。
// 改为触发 GitHub Actions 执行刷新，由 Actions 回调写入结果。
// 原始直接刷新逻辑保留在 account-manager.ts 中供参考。

async function handleKiroRefresh(target: string, _body: Record<string, unknown>, env: Env, request: Request): Promise<Response> {
  if (!target) return Res.error("MISSING_TARGET", "target required");
  const repo = new KvAccountRepository(env.KV);
  const account = await repo.get(target);
  if (!account) return Res.error("NOT_FOUND", "账号不存在", 404);

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, { action: "kiro_refresh", target, callbackUrl });
  if (!result.ok) return Res.error("DISPATCH_FAILED", result.error || "failed", 502);
  return Res.json({ success: true, message: "已触发刷新（GitHub Actions）", workflow: result.workflow });
}

async function handleKiroRefreshAll(_target: string, _body: Record<string, unknown>, env: Env, request: Request): Promise<Response> {
  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, { action: "kiro_refresh_all", callbackUrl });
  if (!result.ok) return Res.error("DISPATCH_FAILED", result.error || "failed", 502);
  return Res.json({ success: true, message: "已触发全量刷新（GitHub Actions）", workflow: result.workflow });
}

async function handleRegisterKiroApi(_target: string, body: Record<string, unknown>, env: Env, request: Request): Promise<Response> {
  const callbackUrl = new URL("/callback", request.url).toString();
  const inputs = (body.inputs as Record<string, string>) || {};
  const count = parseInt(inputs.count || "1");
  const platform = inputs.platform || "both"; // "github" | "gitlab" | "both"

  // Read email API key from KV if not provided
  if (!inputs.email_api_key) {
    const key = await env.KV.get("config:email_api_key");
    if (key) inputs.email_api_key = key;
  }

  const useGithub = platform === "github" || platform === "both";
  const useGitlab = platform === "gitlab" || platform === "both";
  const githubCount = useGithub ? (useGitlab ? Math.ceil(count / 2) : count) : 0;
  const gitlabCount = useGitlab ? (useGithub ? count - githubCount : count) : 0;

  const tasks: Promise<{ ok: boolean; error?: string }>[] = [];
  if (useGithub) {
    tasks.push(triggerWorkflow(env, { action: "register_kiro_api", callbackUrl, inputs: { ...inputs, count: String(githubCount) } }));
  }
  if (useGitlab) {
    tasks.push(triggerGitlabPipeline(env, { action: "register_kiro_api", callbackUrl, inputs: { ...inputs, count: String(gitlabCount) } }));
  }

  const results = await Promise.allSettled(tasks);
  const outcomes = results.map((r) => r.status === "fulfilled" ? r.value : { ok: false, error: "rejected" });
  const allFailed = outcomes.every((o) => !o.ok);

  if (allFailed) {
    return Res.error("DISPATCH_FAILED", outcomes.map((o) => o.error).join(", "), 502);
  }

  return Res.json({
    success: true,
    platform,
    github: useGithub ? { ok: outcomes[0]!.ok, count: githubCount } : null,
    gitlab: useGitlab ? { ok: outcomes[useGithub ? 1 : 0]!.ok, count: gitlabCount } : null,
  });
}

type LocalHandler = (target: string, body: Record<string, unknown>, env: Env, request: Request) => Promise<Response>;

const LOCAL_ACTIONS: Record<string, LocalHandler> = {
  delete: handleDelete,
  delete_all: handleDeleteAll,
  delete_failed: handleDeleteFailed,
  checkin_unchecked: handleCheckinUnchecked,
  register_kiro_api: handleRegisterKiroApi,
  kiro_refresh: handleKiroRefresh,
  kiro_refresh_all: handleKiroRefreshAll,
};

export async function apiTrigger(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  let body: Record<string, unknown> = {};
  try {
    if (request.method !== "GET") body = await request.json() as Record<string, unknown>;
  } catch {
    return Res.error("INVALID_PAYLOAD", "invalid JSON", 400);
  }

  const token = (body.token as string) || url.searchParams.get("token") || request.headers.get("x-worker-token") || "";
  const expected = env.WORKER_SECRET || env.CALLBACK_SECRET || "";
  const sessionOk = await hasValidSession(request, env);
  if (!sessionOk && (!expected || !timingSafeEqual(token, expected))) {
    return Res.error("AUTH_FAILED", "unauthorized", 401);
  }

  const action = (body.action as string) || url.searchParams.get("action") || "checkin";
  const target = (body.target as string) || url.searchParams.get("target") || "";
  log.info("trigger_dispatch", { action, target });

  const localHandler = LOCAL_ACTIONS[action];
  if (localHandler) return localHandler(target, body, env, request);

  if (!env.GITHUB_REPO || !env.GITHUB_TOKEN) {
    return Res.error("DISPATCH_FAILED", "GitHub not configured", 502);
  }

  const lockKey = `${action}:${target || "_all"}`;
  const acquired = await acquireLock(env, lockKey);
  if (!acquired) {
    return Res.error("IN_PROGRESS", "上一个任务还在执行中", 409);
  }

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, {
    action,
    target,
    callbackUrl,
    inputs: body.inputs as Record<string, string> | undefined,
  });

  if (!result.ok) {
    await env.KV.delete(`lock:${lockKey}`);
    return Res.error("DISPATCH_FAILED", result.error || "failed", 502);
  }

  return Res.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id });
}
