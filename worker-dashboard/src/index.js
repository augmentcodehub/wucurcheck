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
    const hours = config || [0];
    const currentHour = new Date().getUTCHours();

    // Kiro token 刷新：每小时都执行（token 1 小时过期）
    try {
      const { refreshAllKiroAccounts } = await import("./services/account_manager.js");
      const refreshResult = await refreshAllKiroAccounts(env);
      log.info("cron_kiro_refresh", { ...refreshResult });
    } catch (e) {
      log.error("cron_kiro_refresh_error", { error: e.message });
    }

    // Kiro 自动注册：每 30 分钟注册 1 个新账号
    const minute = new Date().getMinutes();
    if (minute === 0 || minute === 30) {
      try {
        const callbackUrl = `${env.WORKER_URL}/callback`;
        const r = await triggerWorkflow(env, {
          action: "register_kiro",
          target: "",
          callbackUrl,
          inputs: { count: "1", email_domain: "ouraihub.com" },
        });
        log.info("cron_kiro_register", { ok: r.ok });
      } catch (e) {
        log.error("cron_kiro_register_error", { error: e.message });
      }
    }

    // Wucur 签到：按配置的小时执行
    if (!hours.includes(currentHour)) return;
    log.info("cron_triggered", { hour: currentHour });

    const callbackUrl = `${env.WORKER_URL}/callback`;

    // 1. 触发 checkin.yml（从 ANYROUTER_ACCOUNTS secret 读账号）
    const r1 = await triggerWorkflow(env, { action: "checkin", target: "", callbackUrl });
    log.info("cron_checkin_yml", { ok: r1.ok });

    // 2. 触发 checkin_batch.yml（从 KV 读未签到账号）
    const { listAccounts } = await import("./lib/store.js");
    const accounts = await listAccounts(env);
    const today = new Date().toDateString();
    const unchecked = accounts
      .filter(a => a.status === "active" && (!a.platform || a.platform === "wucur") && (!a.checkin_time || new Date(a.checkin_time).toDateString() !== today))
      .map(a => ({ username: a.username, password: a.password }));
    if (unchecked.length > 0) {
      const r2 = await triggerWorkflow(env, {
        action: "checkin_unchecked",
        target: "",
        callbackUrl,
        inputs: { accounts_json: JSON.stringify(unchecked) },
      });
      log.info("cron_checkin_batch", { ok: r2.ok, count: unchecked.length });
    }
  },
};
