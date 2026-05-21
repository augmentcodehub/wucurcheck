/**
 * POST /callback — GitHub Actions / internal services callback handler.
 *
 * Strategy pattern: each action maps to a handler function.
 * Adding a new action = adding one entry to ACTION_HANDLERS.
 */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { putAccount } from "../lib/store.js";
import { writeFailLog } from "../lib/checkin_log.js";
import { releaseLock } from "../lib/trigger_lock.js";

// ============ Action Handlers ============

async function handleRegister(data, env) {
  if (!data.username) return;
  await putAccount(env, data.username, {
    password: data.password || "",
    platform: data.platform || "",
    status: data.status || "active",
    last_result: data.last_result || "注册成功",
  });
  await releaseLock(env, `register:${data.username}`);
}

async function handleCheckin(data, env) {
  if (!data.username) return;
  await putAccount(env, data.username, {
    balance: data.balance,
    checkin_time: data.checkin_time || new Date().toISOString(),
    status: data.status || "active",
    last_result: data.last_result || `签到成功${data.checkin_time ? ` ${data.checkin_time}` : ""}`,
  });
  if (data.status === "failed") {
    await writeFailLog(env, data.username, { date: new Date().toISOString().slice(0, 10), reason: data.last_result || "未知" });
  }
  await releaseLock(env, `checkin:${data.username}`);
  await releaseLock(env, "checkin:_all");
}

async function handleBatchResult(data, env) {
  const items = Array.isArray(data.results) ? data.results : [data.results];
  for (const item of items) {
    if (item.username) {
      await putAccount(env, item.username, {
        ...item,
        last_result: item.last_result || item.message || "批量结果更新",
      });
      if (item.status === "failed") {
        await writeFailLog(env, item.username, { date: new Date().toISOString().slice(0, 10), reason: item.last_result || item.message || "未知" });
      }
    }
  }
  await releaseLock(env, "checkin:_all");
  log.info("batch_updated", { count: items.length });
}

async function handleRefreshResult(data, env) {
  const items = Array.isArray(data.results) ? data.results : [data.results];
  for (const item of items) {
    if (!item.username) continue;
    const update = {
      last_refresh_at: new Date().toISOString(),
    };
    if (item.success && item.access_token) {
      update.access_token = item.access_token;
      update.refresh_token = item.refresh_token;
      update.expires_in = item.expires_in;
      update.token_expires_at = item.expires_in
        ? new Date(Date.now() + item.expires_in * 1000).toISOString()
        : null;
      update.last_refresh_error = null;
      // Usage/subscription data if provided
      if (item.usage_current !== undefined) update.usage_current = item.usage_current;
      if (item.usage_limit !== undefined) update.usage_limit = item.usage_limit;
      if (item.subscription_type) update.subscription_type = item.subscription_type;
      if (item.days_remaining !== undefined) update.days_remaining = item.days_remaining;
      if (item.suspended) update.status = "suspended";
    } else {
      update.last_refresh_error = item.error || "Refresh failed";
    }
    await putAccount(env, item.username, update);
  }
  await releaseLock(env, "kiro_refresh:_all");
  log.info("refresh_result_updated", { count: items.length });
}

// ============ Strategy Map ============

const ACTION_HANDLERS = {
  register: handleRegister,
  checkin: handleCheckin,
  batch_result: handleBatchResult,
  refresh_result: handleRefreshResult,
};

// ============ Entry Point ============

export async function handleCallback(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    log.warn("callback_bad_json");
    return Response.json({ ok: false, error: "INVALID_JSON" }, { status: 400 });
  }

  if (!body.secret || !timingSafeEqual(body.secret, env.CALLBACK_SECRET || "")) {
    log.warn("callback_auth_failed");
    return Response.json({ ok: false, error: "UNAUTHORIZED" }, { status: 401 });
  }

  const { action, data } = body;
  if (!action || !data) {
    return Response.json({ ok: false, error: "MISSING_FIELDS" }, { status: 400 });
  }

  log.info("callback_received", { action, username: data.username });

  const handler = ACTION_HANDLERS[action];
  if (!handler) {
    log.warn("callback_unknown_action", { action });
    return Response.json({ ok: false, error: `UNKNOWN_ACTION: ${action}` }, { status: 400 });
  }

  await handler(data, env);
  return Response.json({ ok: true });
}
