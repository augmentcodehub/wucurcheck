/** API action handlers — strategy pattern dispatch */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { triggerWorkflow } from "../services/github.js";
import { acquireLock } from "../lib/trigger-lock.js";
import { hasValidSession } from "../services/auth-service.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { Res } from "../lib/response.js";
import { isToday } from "../views/helpers.js";

async function handleDelete(target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  if (!target) return Res.error("MISSING_TARGET", "target required");
  const repo = new KvAccountRepository(env.KV);
  await repo.delete(target);
  return Res.json({ success: true, action: "delete", target });
}

async function handleDeleteAll(_target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  for (const a of accounts) await repo.delete(a.username);
  return Res.json({ success: true, action: "delete_all", count: accounts.length });
}

async function handleDeleteFailed(_target: string, _body: Record<string, unknown>, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const failed = accounts.filter((a) => a.status === "failed");
  for (const a of failed) await repo.delete(a.username);
  return Res.json({ success: true, action: "delete_failed", count: failed.length });
}

async function handleCheckinUnchecked(_target: string, _body: Record<string, unknown>, env: Env, request: Request): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const unchecked = accounts
    .filter((a) => a.status === "active" && (!a.platform || a.platform === "wucur") && !isToday(a.checkin_time))
    .map((a) => ({ username: a.username, password: a.password }));

  if (!unchecked.length) return Res.error("NO_UNCHECKED", "所有账号今日已签到");

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, {
    action: "checkin_unchecked",
    callbackUrl,
    inputs: { accounts_json: JSON.stringify(unchecked) },
  });

  if (!result.ok) return Res.error("DISPATCH_FAILED", result.error || "dispatch failed", 502);
  return Res.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id, count: unchecked.length });
}

type LocalHandler = (target: string, body: Record<string, unknown>, env: Env, request: Request) => Promise<Response>;

const LOCAL_ACTIONS: Record<string, LocalHandler> = {
  delete: handleDelete,
  delete_all: handleDeleteAll,
  delete_failed: handleDeleteFailed,
  checkin_unchecked: handleCheckinUnchecked,
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
