/**
 * Worker Dashboard — 入口
 */

import { log, setContext } from "./lib/log.js";
import { handleLogin, handleLogout, authMiddleware } from "./auth.js";
import { handleCallback } from "./pages/callback.js";
import { apiTrigger } from "./pages/actions.js";
import { triggerWorkflow } from "./lib/github.js";
import { router } from "./router.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname: path, searchParams } = url;
    const method = request.method;

    // 每个请求注入上下文
    setContext({ path, method, rid: crypto.randomUUID().slice(0, 8) });

    try {
      // 公开路由
      if (path === "/login" && method === "GET") return handleLogin(env);
      if (path === "/login" && method === "POST") return handleLogin(env, request);
      if (path === "/logout") return handleLogout();
      if (path === "/callback" && method === "POST") return handleCallback(request, env);
      if (path === "/api/trigger" && method === "POST") return apiTrigger(request, env);
      if (path === "/api/trigger" && method === "GET") return apiTrigger(request, env);

      // 认证拦截
      const denied = await authMiddleware(request, env);
      if (denied) return denied;

      // 保护路由
      log.info("request");
      const resp = await router(path, method, request, env);
      return resp;
    } catch (e) {
      log.error("unhandled", { error: e.message, stack: e.stack?.substring(0, 300) });
      return new Response("Internal Server Error", { status: 500 });
    }
  },

  // 每小时检查一次，根据 KV 配置决定是否触发签到
  async scheduled(event, env, ctx) {
    setContext({ trigger: "cron", rid: crypto.randomUUID().slice(0, 8) });
    const config = await env.KV.get("config:cron_hour", "json");
    // 默认北京时间 8 点（UTC 0）
    const hours = config || [0];
    const currentHour = new Date().getUTCHours();
    if (!hours.includes(currentHour)) return;
    log.info("cron_triggered", { hour: currentHour });
    const result = await triggerWorkflow(env, { action: "checkin", target: "", callbackUrl: "https://worker-dashboard.ouraihub.workers.dev/callback" });
    log.info("cron_result", { ok: result.ok });
  },
};
