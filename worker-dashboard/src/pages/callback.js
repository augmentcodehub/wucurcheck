import { log } from "../lib/log.js";
import { putAccount } from "../lib/store.js";
import { releaseLock } from "../lib/trigger_lock.js";

function timingSafeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

/**
 * POST /callback — GitHub Actions 完成后回调
 * Body: { secret, action, data }
 */
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

  log.info("callback received", { action, username: data.username });

  if (action === "register" && data.username) {
    await putAccount(env, data.username, {
      password: data.password || "",
      platform: data.platform || "",
      status: data.status || "active",
      last_result: data.last_result || "注册成功",
    });
    await releaseLock(env, `register:${data.username}`);
  } else if (action === "checkin" && data.username) {
    await putAccount(env, data.username, {
      balance: data.balance,
      checkin_time: data.checkin_time || new Date().toISOString(),
      status: data.status || "active",
      last_result: data.last_result || `签到成功${data.checkin_time ? ` ${data.checkin_time}` : ""}`,
    });
    await releaseLock(env, `checkin:${data.username}`);
    await releaseLock(env, "checkin:_all");
  } else if (action === "batch_result" && (Array.isArray(data.results) || (data.results && typeof data.results === "object"))) {
    const items = Array.isArray(data.results) ? data.results : [data.results];
    for (const item of items) {
      if (item.username) {
        await putAccount(env, item.username, {
          ...item,
          last_result: item.last_result || item.message || "批量结果更新",
        });
      }
    }
    await releaseLock(env, "checkin:_all");
    log.info("batch updated", { count: data.results.length });
  }

  return Response.json({ ok: true });
}
