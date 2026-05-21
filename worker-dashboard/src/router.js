import { pageAccounts, apiAccounts, apiExportCsv, apiExportKiro } from "./pages/accounts.js";
import { apiTrigger } from "./pages/actions.js";
import { apiSettings } from "./pages/settings.js";
import { queryFailLogs } from "./lib/checkin_log.js";
import { getAccount } from "./lib/store.js";
import { badge, timeAgo, esc } from "./views/helpers.js";
import Mustache from "mustache";
import accountDetailTemplate from "./templates/partials/account-detail.mustache";

async function apiLogs(request, env) {
  const username = new URL(request.url).searchParams.get("username");
  if (!username) return Response.json({ success: false, error: "MISSING_USERNAME" }, { status: 400 });
  const logs = await queryFailLogs(env, username);
  return Response.json({ success: true, logs });
}

async function apiAccountDetail(request, env) {
  const url = new URL(request.url);
  const username = url.pathname.replace("/api/account/", "");
  if (!username) return new Response("Not Found", { status: 404 });

  const account = await getAccount(env, decodeURIComponent(username));
  if (!account) return new Response("Not Found", { status: 404 });

  const logs = await queryFailLogs(env, account.username);
  const html = Mustache.render(accountDetailTemplate, {
    username: esc(account.username),
    platform: account.platform || "-",
    statusBadge: badge(account.status),
    balance: account.balance ?? "-",
    checkinTime: account.checkin_time ? timeAgo(account.checkin_time) : "-",
    lastResult: account.last_result || "-",
    ssoToken: account.sso_token || null,
    hasLogs: logs.length > 0,
    logs,
  });

  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
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
  // Static routes
  const route = routes.find(([m, p]) => m === method && p === path);
  if (route) return route[2](request, env);

  // Dynamic routes
  if (method === "GET" && path.startsWith("/api/account/")) {
    return apiAccountDetail(request, env);
  }

  return new Response("Not Found", { status: 404 });
}
