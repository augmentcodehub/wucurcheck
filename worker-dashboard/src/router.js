import { pageAccounts, apiAccounts, apiExportCsv, apiExportKiro } from "./pages/accounts.js";
import { apiTrigger } from "./pages/actions.js";
import { apiSettings } from "./pages/settings.js";
import { queryFailLogs } from "./lib/checkin_log.js";

async function apiLogs(request, env) {
  const username = new URL(request.url).searchParams.get("username");
  if (!username) return Response.json({ success: false, error: "MISSING_USERNAME" }, { status: 400 });
  const logs = await queryFailLogs(env, username);
  return Response.json({ success: true, logs });
}

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
  const route = routes.find(([m, p]) => m === method && p === path);
  if (route) return route[2](request, env);
  return new Response("Not Found", { status: 404 });
}
