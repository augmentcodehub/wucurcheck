/** POST /callback — GitHub Actions callback handler */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { KvFailLogRepository } from "../repositories/kv-fail-log-repository.js";
import { releaseLock } from "../lib/trigger-lock.js";
import { Res } from "../lib/response.js";
import type { Account, AccountStatus, AccountPlatform } from "../types/index.js";

// --- Type Guards ---

function str(v: unknown): string | undefined {
  return typeof v === "string" && v ? v : undefined;
}

function isStatus(v: unknown): v is AccountStatus {
  return v === "active" || v === "failed" || v === "suspended";
}

function isPlatform(v: unknown): v is AccountPlatform {
  return v === "wucur" || v === "kiro";
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// --- Handlers ---

async function handleCheckin(data: Record<string, unknown>, env: Env): Promise<void> {
  const username = str(data.username);
  if (!username) return;

  const repo = new KvAccountRepository(env.KV);
  await repo.put(username, {
    balance: str(data.balance),
    checkin_time: str(data.checkin_time) || new Date().toISOString(),
    status: isStatus(data.status) ? data.status : "active",
    last_result: str(data.last_result) || "签到成功",
  });
  if (data.status === "failed") {
    const failLogs = new KvFailLogRepository(env.KV);
    await failLogs.write(username, { date: new Date().toISOString().slice(0, 10), reason: str(data.last_result) || "未知" });
  }
  await releaseLock(env, `checkin:${username}`);
  await releaseLock(env, "checkin:_all");
}

async function handleBatchResult(data: Record<string, unknown>, env: Env): Promise<void> {
  const raw = data.results;
  const items = Array.isArray(raw) ? raw : [raw];
  const repo = new KvAccountRepository(env.KV);
  const failLogs = new KvFailLogRepository(env.KV);

  for (const item of items) {
    if (!isObject(item)) continue;
    const username = str(item.username) || str(item.email);
    if (!username) continue;

    await repo.put(username, {
      username,
      password: str(item.password),
      platform: isPlatform(item.platform) ? item.platform : "kiro",
      status: isStatus(item.status) ? item.status : "active",
      last_result: str(item.last_result) || str(item.error) || str(item.message) || "批量结果更新",
      refresh_token: str(item.refreshToken) || str(item.refresh_token),
      access_token: str(item.accessToken) || str(item.access_token),
      client_id: str(item.clientId) || str(item.client_id),
      client_secret: str(item.clientSecret) || str(item.client_secret),
      region: str(item.region),
    });
    if (item.status === "failed") {
      await failLogs.write(username, { date: new Date().toISOString().slice(0, 10), reason: str(item.last_result) || str(item.error) || "未知" });
    }
  }
  await releaseLock(env, "checkin:_all");
  log.info("batch_updated", { count: items.length });
}

async function handleRegister(data: Record<string, unknown>, env: Env): Promise<void> {
  const username = str(data.username);
  if (!username) return;

  const repo = new KvAccountRepository(env.KV);
  await repo.put(username, {
    password: str(data.password) || "",
    platform: isPlatform(data.platform) ? data.platform : "wucur",
    status: isStatus(data.status) ? data.status : "active",
    last_result: str(data.last_result) || "注册成功",
  });
  await releaseLock(env, `register:${username}`);
}

// --- Dispatch ---

const ACTION_HANDLERS: Record<string, (data: Record<string, unknown>, env: Env) => Promise<void>> = {
  register: handleRegister,
  checkin: handleCheckin,
  batch_result: handleBatchResult,
};

export async function handleCallback(request: Request, env: Env): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    log.warn("callback_bad_json");
    return Res.error("INVALID_JSON", "invalid JSON", 400);
  }

  if (!isObject(body)) return Res.error("INVALID_JSON", "expected object", 400);

  const secret = env.CALLBACK_SECRET || "";
  if (!str(body.secret) || !timingSafeEqual(body.secret as string, secret)) {
    log.warn("callback_auth_failed");
    return Res.error("UNAUTHORIZED", "unauthorized", 401);
  }

  const action = str(body.action);
  const data = isObject(body.data) ? body.data : null;
  if (!action || !data) return Res.error("MISSING_FIELDS", "action and data required", 400);

  log.info("callback_received", { action, username: str(data.username) || "" });

  const handler = ACTION_HANDLERS[action];
  if (!handler) {
    log.warn("callback_unknown_action", { action });
    return Res.error("UNKNOWN_ACTION", `unknown: ${action}`, 400);
  }

  await handler(data, env);
  return Res.json({ ok: true });
}
