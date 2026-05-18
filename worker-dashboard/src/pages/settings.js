import { log } from "../lib/log.js";
import { getSessionUser } from "../auth.js";

async function isAdmin(request, env) {
  const user = await getSessionUser(request, env);
  return user === (env.ADMIN_USER || "admin");
}

export async function apiSettings(request, env) {
  if (request.method === "GET") {
    const cronHour = await env.KV.get("config:cron_hour", "json") || [0];
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
        await env.KV.put("config:admin_pass", body.new_password);
      } else {
        const kvUser = await env.KV.get(`user:${user}`, "json");
        if (kvUser) await env.KV.put(`user:${user}`, JSON.stringify({ ...kvUser, password: body.new_password }));
      }
      log.info("password_changed", { user });
      return Response.json({ success: true });
    }

    // 以下操作仅管理员
    if (body.action === "add_user" || body.action === "delete_user") {
      if (!(await isAdmin(request, env))) {
        return Response.json({ success: false, error: "仅管理员可操作" }, { status: 403 });
      }
    }

    if (body.action === "add_user") {
      if (!body.username || !body.password || body.password.length < 4) {
        return Response.json({ success: false, error: "用户名和密码必填，密码至少4位" }, { status: 400 });
      }
      const existing = await env.KV.get(`user:${body.username}`, "json");
      if (existing) {
        return Response.json({ success: false, error: "用户已存在" }, { status: 400 });
      }
      await env.KV.put(`user:${body.username}`, JSON.stringify({
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
      await env.KV.delete(`user:${body.username}`);
      log.info("user_deleted", { username: body.username });
      return Response.json({ success: true });
    }

    if (body.cron_hours && Array.isArray(body.cron_hours)) {
      await env.KV.put("config:cron_hour", JSON.stringify(body.cron_hours));
      log.info("settings_updated", { cron_hours: body.cron_hours });
      return Response.json({ success: true, cron_hours: body.cron_hours });
    }

    return Response.json({ success: false, error: "Invalid request" }, { status: 400 });
  }
}

async function listUsers(env) {
  const list = await env.KV.list({ prefix: "user:" });
  const users = [];
  for (const key of list.keys) {
    const username = key.name.slice(5);
    const data = await env.KV.get(key.name, "json");
    if (data) users.push({ username, role: data.role, created_at: data.created_at });
  }
  return users;
}
