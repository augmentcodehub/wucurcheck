/**
 * Account detail API — returns HTML partial for HTMX consumption.
 */

import Mustache from "mustache";
import { getAccount } from "../lib/store.js";
import { queryFailLogs } from "../lib/checkin_log.js";
import { badge, timeAgo, esc } from "../views/helpers.js";
import { log } from "../lib/log.js";
import accountDetailTemplate from "../templates/partials/account-detail.mustache";

/**
 * GET /api/account/:username → HTML partial
 * @param {Request} request
 * @param {Object} env
 * @returns {Promise<Response>}
 */
export async function apiAccountDetail(request, env) {
  const url = new URL(request.url);
  const username = decodeURIComponent(url.pathname.replace("/api/account/", ""));
  if (!username) return new Response("Not Found", { status: 404 });

  const account = await getAccount(env, username);
  if (!account) {
    log.warn("account_not_found", { username });
    return new Response("Not Found", { status: 404 });
  }

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

/**
 * GET /api/logs?username=xxx → JSON
 * @param {Request} request
 * @param {Object} env
 * @returns {Promise<Response>}
 */
export async function apiLogs(request, env) {
  const username = new URL(request.url).searchParams.get("username");
  if (!username) return Response.json({ success: false, error: "MISSING_USERNAME" }, { status: 400 });
  const logs = await queryFailLogs(env, username);
  return Response.json({ success: true, logs });
}
