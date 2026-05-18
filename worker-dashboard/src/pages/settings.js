import { log } from "../lib/log.js";

export async function apiSettings(request, env) {
  if (request.method === "GET") {
    const cronHour = await env.KV.get("config:cron_hour", "json") || [0];
    return Response.json({ cron_hours: cronHour });
  }
  if (request.method === "POST") {
    const body = await request.json();

    // 修改密码
    if (body.action === "change_password") {
      if (!body.new_password || body.new_password.length < 4) {
        return Response.json({ success: false, error: "密码至少4位" }, { status: 400 });
      }
      await env.KV.put("config:admin_pass", body.new_password);
      log.info("password_changed");
      return Response.json({ success: true });
    }

    // 修改定时签到
    if (body.cron_hours && Array.isArray(body.cron_hours)) {
      await env.KV.put("config:cron_hour", JSON.stringify(body.cron_hours));
      log.info("settings_updated", { cron_hours: body.cron_hours });
      return Response.json({ success: true, cron_hours: body.cron_hours });
    }

    return Response.json({ success: false, error: "Invalid request" }, { status: 400 });
  }
}
