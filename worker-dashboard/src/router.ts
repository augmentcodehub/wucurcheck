/**
 * Router — pure request dispatch, no business logic.
 */

import { pageAccounts, apiAccounts, apiAccountsTable, apiExportCsv, apiExportKiro } from "./handlers/accounts.js";
import { apiAccountDetail, apiLogs } from "./handlers/account-detail.js";
import { apiTrigger } from "./handlers/actions.js";
import { apiSettings } from "./handlers/settings.js";
import { apiCronLogs, apiFailLogs, apiRegisterLogs } from "./handlers/cron-logs.js";
import { pageLogsCheckin, pageLogsRegister, pageLogsErrors } from "./handlers/logs-page.js";
import { serveStatic } from "./lib/static.js";
import { Res } from "./lib/response.js";
import type { Route, RouteHandler } from "./types/index.js";

const routes: Route[] = [
  { method: "GET", path: "/", handler: pageAccounts },
  { method: "GET", path: "/logs", handler: pageLogsCheckin },
  { method: "GET", path: "/logs/checkin", handler: pageLogsCheckin },
  { method: "GET", path: "/logs/register", handler: pageLogsRegister },
  { method: "GET", path: "/logs/errors", handler: pageLogsErrors },
  { method: "GET", path: "/api/accounts", handler: apiAccounts },
  { method: "GET", path: "/api/accounts/table", handler: apiAccountsTable },
  { method: "GET", path: "/api/export/csv", handler: apiExportCsv },
  { method: "GET", path: "/api/export/kiro", handler: apiExportKiro },
  { method: "GET", path: "/api/logs", handler: apiLogs },
  { method: "POST", path: "/api/trigger", handler: apiTrigger },
  { method: "GET", path: "/api/settings", handler: apiSettings },
  { method: "POST", path: "/api/settings", handler: apiSettings },
  { method: "GET", path: "/api/cron-logs", handler: apiCronLogs },
  { method: "GET", path: "/api/fail-logs", handler: apiFailLogs },
  { method: "GET", path: "/api/register-logs", handler: apiRegisterLogs },
];

export async function router(path: string, method: string, request: Request, env: Env): Promise<Response> {
  const route = routes.find((r) => r.method === method && r.path === path);
  if (route) return route.handler(request, env);

  if (method === "GET" && path.startsWith("/api/account/")) return apiAccountDetail(request, env);
  if (method === "GET" && path.startsWith("/static/")) return serveStatic(path);

  return Res.notFound();
}
