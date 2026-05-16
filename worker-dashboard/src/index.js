/**
 * Worker Dashboard — 入口
 */

import { log, setContext } from "./lib/log.js";
import { handleLogin, handleLogout, authMiddleware } from "./auth.js";
import { handleCallback } from "./pages/callback.js";
import { apiTrigger } from "./pages/actions.js";
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
};
