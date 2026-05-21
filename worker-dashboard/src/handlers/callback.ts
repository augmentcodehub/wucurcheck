/** POST /callback — GitHub Actions callback handler */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { KvFailLogRepository } from "../repositories/kv-fail-log-repository.js";
import { releaseLock } from "../lib/trigger-lock.js";
import { Res } from "../lib/response.js";
import type { Account } from "../types/index.js";

type CallbackData = Record<string, unknown>;

async function handleCheckin(data: CallbackData, env: Env): Promise<void> {
  if (!data.username) return;
  const repo = new KvAccountRepository(env.KV);
  await repo.put(data.username as string, {
    balance: data.balance as string | undefined,
    checkin_time: (data.checkin_time as string) || new Date().toISOString(),
    status: (data.status as Account["status"]) || "active",
    last_result: (data.last_result as string) || "签到成功",
  });
  if (data.status === "failed") {
    const failLogs = new KvFailLogRepository(env.KV);
    await failLogs.write(data.username as string, { date: new Date().toISOString().slice(0, 10), reason: (data.last_result as string) || "未知" });
  }
  await releaseLock(env, `checkin:${data.username}`);
  await releaseLock(env, "checkin:_all");
}

async function handleBatchResult(data: CallbackData, env: Env): Promise<void> {
  const items = Array.isArray(data.results) ? data.results : [data.results];
  const repo = new KvAccountRepository(env.KV);
  const failLogs = new KvFailLogRepository(env.KV);
  for (const item of items as CallbackData[]) {
    if (item.username) {
      await repo.put(item.username as string, {
        ...(item as Partial<Account>),
        last_result: (item.last_result as string) || (item.message as string) || "批量结果更新",
      });
      if (item.status === "failed") {
        await failLogs.write(item.username as string, { date: new Date().toISOString().slice(0, 10), reason: (item.last_result as string) || "未知" });
      }
    }
  }
  await releaseLock(env, "checkin:_all");
  log.info("batch_updated", { count: items.length });
}

async function handleRegister(data: CallbackData, env: Env): Promise<void> {
  if (!data.username) return;
  const repo = new KvAccountRepository(env.KV);
  await repo.put(data.username as string, {
    password: (data.password as string) || "",
    platform: (data.platform as Account["platform"]) || "wucur",
    status: (data.status as Account["status"]) || "active",
    last_result: (data.last_result as string) || "注册成功",
  });
  await releaseLock(env, `register:${data.username}`);
}

const ACTION_HANDLERS: Record<string, (data: CallbackData, env: Env) => Promise<void>> = {
  register: handleRegister,
  checkin: handleCheckin,
  batch_result: handleBatchResult,
};

export async function handleCallback(request: Request, env: Env): Promise<Response> {
  let body: { secret?: string; action?: string; data?: CallbackData };
  try {
    body = await request.json() as typeof body;
  } catch {
    log.warn("callback_bad_json");
    return Res.error("INVALID_JSON", "invalid JSON", 400);
  }

  const secret = env.CALLBACK_SECRET || "";
  if (!body.secret || !timingSafeEqual(body.secret, secret)) {
    log.warn("callback_auth_failed");
    return Res.error("UNAUTHORIZED", "unauthorized", 401);
  }

  const { action, data } = body;
  if (!action || !data) return Res.error("MISSING_FIELDS", "action and data required", 400);

  log.info("callback_received", { action, username: data.username as string });

  const handler = ACTION_HANDLERS[action];
  if (!handler) {
    log.warn("callback_unknown_action", { action });
    return Res.error("UNKNOWN_ACTION", `unknown: ${action}`, 400);
  }

  await handler(data, env);
  return Res.json({ ok: true });
}
