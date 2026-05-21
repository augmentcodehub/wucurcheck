/**
 * Router — pure request dispatch, no business logic.
 *
 * Responsibilities:
 *   1. Match path + method to handler
 *   2. Delegate to handler
 *   3. Return 404 for unmatched routes
 */

import { pageAccounts, apiAccounts, apiExportCsv, apiExportKiro } from "./pages/accounts.js";
import { apiAccountDetail, apiLogs } from "./pages/account_detail.js";
import { apiTrigger } from "./pages/actions.js";
import { apiSettings } from "./pages/settings.js";
import { serveStatic } from "./lib/static.js";

/** @type {[string, string, Function][]} */
const routes = [
  ["GET", "/", pageAccounts],
  ["GET", "/api/accounts", apiAccounts],
  ["GET", "/api/export/csv", apiExportCsv],
  ["GET", "/api/export/kiro", apiExportKiro],
  ["GET", "/api/logs", apiLogs],
  ["POST", "/api/trigger", apiTrigger],
  ["GET", "/api/settings", apiSettings],
  ["POST", "/api/settings", apiSettings],
];

export async function router(path, method, request, env) {
  // Static routes (exact match)
  const route = routes.find(([m, p]) => m === method && p === path);
  if (route) return route[2](request, env);

  // Dynamic routes (prefix match)
  if (method === "GET" && path.startsWith("/api/account/")) {
    return apiAccountDetail(request, env);
  }
  if (method === "GET" && path.startsWith("/static/")) {
    return serveStatic(path);
  }

  return new Response("Not Found", { status: 404 });
}
