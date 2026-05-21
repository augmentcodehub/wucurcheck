/** Settings API handler */

import { log } from "../lib/log.js";
import { getSessionUser } from "../services/auth-service.js";
import { KV_PREFIX, KV_KEY } from "../lib/constants.js";
import { Res } from "../lib/response.js";

async function isAdmin(request: Request, env: Env): Promise<boolean> {
  const user = await getSessionUser(request, env);
  if (!user) return false;
  if (user === (env.ADMIN_USER || "admin")) return true;
  const kvUser = await env.KV.get<{ role: string }>(`${KV_PREFIX.USER}${user}`, "json");
  return kvUser?.role === "admin";
}

export async function apiSettings(request: Request, env: Env): Promise<Response> {
  if (request.method === "GET") {
    const cronHour = await env.KV.get<number[]>(KV_KEY.CRON_HOUR, "json") || [0];
    const admin = await isAdmin(request, env);
    const users = admin ? await listUsers(env) : [];
    return Res.json({ cron_hours: cronHour, users, is_admin: admin });
  }

  const body = await request.json() as Record<string, unknown>;

  if (body.action === "change_password") {
    const newPass = body.new_password as string;
    if (!newPass || newPass.length < 4) return Res.error("INVALID", "密码至少4位", 400);
    const user = await getSessionUser(request, env);
    if (user === (env.ADMIN_USER || "admin")) {
      await env.KV.put(KV_KEY.ADMIN_PASS, newPass);
    } else if (user) {
      const kvUser = await env.KV.get<Record<string, unknown>>(`${KV_PREFIX.USER}${user}`, "json");
      if (kvUser) await env.KV.put(`${KV_PREFIX.USER}${user}`, JSON.stringify({ ...kvUser, password: newPass }));
    }
    log.info("password_changed", { user: user || "" });
    return Res.json({ success: true });
  }

  if (body.action === "add_user" || body.action === "delete_user") {
    if (!(await isAdmin(request, env))) return Res.error("FORBIDDEN", "仅管理员可操作", 403);
  }

  if (body.action === "add_user") {
    const username = body.username as string;
    const password = body.password as string;
    if (!username || !password || password.length < 4) return Res.error("INVALID", "用户名和密码必填", 400);
    const existing = await env.KV.get(`${KV_PREFIX.USER}${username}`);
    if (existing) return Res.error("EXISTS", "用户已存在", 400);
    await env.KV.put(`${KV_PREFIX.USER}${username}`, JSON.stringify({
      password,
      role: (body.role as string) || "viewer",
      created_at: new Date().toISOString(),
    }));
    log.info("user_added", { username });
    return Res.json({ success: true });
  }

  if (body.action === "delete_user") {
    const username = body.username as string;
    if (!username) return Res.error("INVALID", "用户名必填", 400);
    await env.KV.delete(`${KV_PREFIX.USER}${username}`);
    log.info("user_deleted", { username });
    return Res.json({ success: true });
  }

  if (Array.isArray(body.cron_hours)) {
    await env.KV.put(KV_KEY.CRON_HOUR, JSON.stringify(body.cron_hours));
    log.info("settings_updated", { cron_hours: String(body.cron_hours) });
    return Res.json({ success: true, cron_hours: body.cron_hours });
  }

  return Res.error("INVALID", "Invalid request", 400);
}

async function listUsers(env: Env): Promise<{ username: string; role: string; created_at?: string }[]> {
  const { keys } = await env.KV.list({ prefix: KV_PREFIX.USER });
  const values = await Promise.all(keys.map((k) => env.KV.get<{ role: string; created_at?: string }>(k.name, "json")));
  return values
    .map((data, i) => data ? { username: keys[i]!.name.slice(KV_PREFIX.USER.length), role: data.role, created_at: data.created_at } : null)
    .filter((v): v is NonNullable<typeof v> => v !== null);
}
