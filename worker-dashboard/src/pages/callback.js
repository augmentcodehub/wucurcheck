import { log } from "../lib/log.js";
import { putAccount } from "../lib/store.js";
import { releaseLock } from "../lib/trigger_lock.js";

/**
 * POST /callback — GitHub Actions 完成后回调
 * Body: { secret, action, data }
 */
export async function handleCallback(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  if (!body.secret || body.secret !== env.CALLBACK_SECRET) {
    log.warn("callback auth failed");
    return new Response("Unauthorized", { status: 401 });
  }

  const { action, data } = body;
  if (!action || !data) return new Response("Missing action/data", { status: 400 });

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
  } else if (action === "batch_result" && Array.isArray(data.results)) {
    for (const item of data.results) {
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
