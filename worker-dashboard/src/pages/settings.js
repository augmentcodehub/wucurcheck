import { log } from "../lib/log.js";

export async function apiSettings(request, env) {
  if (request.method === "GET") {
    const cronHour = await env.KV.get("config:cron_hour", "json") || [0];
    return Response.json({ cron_hours: cronHour });
  }
  if (request.method === "POST") {
    const body = await request.json();
    if (body.cron_hours && Array.isArray(body.cron_hours)) {
      await env.KV.put("config:cron_hour", JSON.stringify(body.cron_hours));
      log.info("settings_updated", { cron_hours: body.cron_hours });
      return Response.json({ success: true, cron_hours: body.cron_hours });
    }
    return Response.json({ success: false, error: "Invalid cron_hours" }, { status: 400 });
  }
}
