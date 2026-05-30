/**
 * Worker Dashboard — entry point (fetch + scheduled handlers).
 */

import { log, withLogContext } from "./lib/log.js";
import { DEFAULT_PASSWORD } from "./lib/constants.js";
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
      log.info("cron_triggered");

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

    // 写入执行日志到 D1
    const { D1LogRepository } = await import("./repositories/d1-log-repository.js");
    const logRepo = new D1LogRepository(env.DB);
    await logRepo.insert({
      type: "checkin",
      time: new Date().toISOString(),
      status: result.ok ? "success" : "failed",
      message: `签到 ${unchecked.length} 个账号`,
      data: JSON.stringify(unchecked.map((a) => a.username)),
    });

    // 每天清理 7 天前的日志
    if (new Date().getUTCHours() === 0) {
      await logRepo.cleanup(7);
    }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "unknown";
        log.error("cron_error", { error: msg });
      }
    });
  },
} satisfies ExportedHandler<Env>;
