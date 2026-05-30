/**
 * Worker Dashboard — entry point (fetch + scheduled handlers).
 */

import { log, withLogContext } from "./lib/log.js";
import { KV_KEY, DEFAULT_PASSWORD } from "./lib/constants.js";
import { handleLogin, handleLogout, authMiddleware } from "./services/auth-service.js";
import { handleCallback } from "./handlers/callback.js";
import { apiTrigger } from "./handlers/actions.js";
import { triggerWorkflow } from "./services/github.js";
import { KvAccountRepository } from "./repositories/kv-account-repository.js";
import { router } from "./router.js";
import { isToday } from "./views/helpers.js";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const { pathname: path } = url;
    const method = request.method;

    return withLogContext({ path, method, rid: crypto.randomUUID().slice(0, 8) }, async () => {
      try {
        // Public routes
        if (path === "/login" && method === "GET") return handleLogin(env);
        if (path === "/login" && method === "POST") return handleLogin(env, request);
        if (path === "/logout") return handleLogout();
        if (path === "/callback" && method === "POST") return handleCallback(request, env);
        if (path === "/api/trigger" && method === "POST") return apiTrigger(request, env);
        if (path === "/api/trigger" && method === "GET") return apiTrigger(request, env);

        // Auth middleware
        const denied = await authMiddleware(request, env);
        if (denied) return denied;

        // Protected routes
        log.info("request");
        return await router(path, method, request, env);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "unknown";
        log.error("unhandled", { error: msg });
        return new Response("Internal Server Error", { status: 500 });
      }
    });
  },

  async scheduled(_event: ScheduledController, env: Env, _ctx: ExecutionContext): Promise<void> {
    return withLogContext({ trigger: "cron", rid: crypto.randomUUID().slice(0, 8) }, async () => {
      try {
      const config = await env.KV.get<number[]>(KV_KEY.CRON_HOUR, "json");
      const hours = config || [0];
      const currentHour = new Date().getUTCHours();

      if (!hours.includes(currentHour)) {
        log.info("cron_skip", { hour: String(currentHour), configured: hours.join(",") });
        return;
      }
      log.info("cron_triggered", { hour: String(currentHour) });

    const callbackUrl = `${env.WORKER_URL}/callback`;
    const repo = new KvAccountRepository(env.KV);
    const accounts = await repo.list();
    const unchecked = accounts
      .filter((a) => a.status === "active" && (!a.platform || a.platform === "wucur") && !isToday(a.checkin_time))
      .map((a) => ({ username: a.username, password: a.password || DEFAULT_PASSWORD }))
      .slice(0, 15);

    if (unchecked.length === 0) {
      log.info("cron_all_checked", { total_active: String(accounts.filter((a) => a.status === "active").length) });
      return;
    }

    const result = await triggerWorkflow(env, {
      action: "checkin_unchecked",
      callbackUrl,
      inputs: { accounts_json: JSON.stringify(unchecked) },
    });
    log.info("cron_checkin_dispatch", { ok: String(result.ok), count: String(unchecked.length), error: result.error || "" });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "unknown";
        log.error("cron_error", { error: msg });
      }
    });
  },
} satisfies ExportedHandler<Env>;
