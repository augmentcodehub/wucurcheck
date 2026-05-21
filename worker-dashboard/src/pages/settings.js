import { log } from "../lib/log.js";
import { getSessionUser } from "../auth.js";
import { KV_PREFIX, KV_KEY } from "../lib/constants.js";

async function isAdmin(request, env) {
  const user = await getSessionUser(request, env);
  if (!user) return false;
  if (user === (env.ADMIN_USER || "admin")) return true;
  const kvUser = await env.KV.get(`${KV_PREFIX.USER}${user}`, "json");
  return kvUser?.role === "admin";
}

export async function apiSettings(request, env) {
  if (request.method === "GET") {
    const cronHour = await env.KV.get(KV_KEY.CRON_HOUR, "json") || [0];
    const admin = await isAdmin(request, env);
    const users = admin ? await listUsers(env) : [];
    return Response.json({ cron_hours: cronHour, users, is_admin: admin });
  }
  if (request.method === "POST") {
    const body = await request.json();

    if (body.action === "change_password") {
      if (!body.new_password || body.new_password.length < 4) {
        return Response.json({ success: false, error: "密码至少4位" }, { status: 400 });
      }
      const user = await getSessionUser(request, env);
      if (user === (env.ADMIN_USER || "admin")) {
        await env.KV.put(KV_KEY.ADMIN_PASS, body.new_password);
      } else {
        const kvUser = await env.KV.get(`${KV_PREFIX.USER}${user}`, "json");
        if (kvUser) await env.KV.put(`${KV_PREFIX.USER}${user}`, JSON.stringify({ ...kvUser, password: body.new_password }));
      }
      log.info("password_changed", { user });
      return Response.json({ success: true });
    }

    if (body.action === "add_user" || body.action === "delete_user") {
      if (!(await isAdmin(request, env))) {
        return Response.json({ success: false, error: "仅管理员可操作" }, { status: 403 });
      }
    }

    if (body.action === "add_user") {
      if (!body.username || !body.password || body.password.length < 4) {
        return Response.json({ success: false, error: "用户名和密码必填，密码至少4位" }, { status: 400 });
      }
      const existing = await env.KV.get(`${KV_PREFIX.USER}${body.username}`, "json");
      if (existing) {
        return Response.json({ success: false, error: "用户已存在" }, { status: 400 });
      }
      await env.KV.put(`${KV_PREFIX.USER}${body.username}`, JSON.stringify({
        password: body.password,
        role: body.role || "viewer",
        created_at: new Date().toISOString(),
      }));
      log.info("user_added", { username: body.username });
      return Response.json({ success: true });
    }

    if (body.action === "delete_user") {
      if (!body.username) {
        return Response.json({ success: false, error: "用户名必填" }, { status: 400 });
      }
      await env.KV.delete(`${KV_PREFIX.USER}${body.username}`);
      log.info("user_deleted", { username: body.username });
      return Response.json({ success: true });
    }

    if (body.cron_hours && Array.isArray(body.cron_hours)) {
      await env.KV.put(KV_KEY.CRON_HOUR, JSON.stringify(body.cron_hours));
      log.info("settings_updated", { cron_hours: body.cron_hours });
      return Response.json({ success: true, cron_hours: body.cron_hours });
    }

    return Response.json({ success: false, error: "Invalid request" }, { status: 400 });
  }
}

async function listUsers(env) {
  const { keys } = await env.KV.list({ prefix: KV_PREFIX.USER });
  const values = await Promise.all(keys.map((k) => env.KV.get(k.name, "json")));
  return values
    .map((data, i) => data ? { username: keys[i].name.slice(KV_PREFIX.USER.length), role: data.role, created_at: data.created_at } : null)
    .filter(Boolean);
}
