/** Account detail + logs API handlers */

import Mustache from "mustache";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { KvFailLogRepository } from "../repositories/kv-fail-log-repository.js";
import { badge, timeAgo, esc } from "../views/helpers.js";
import { log } from "../lib/log.js";
import { Res } from "../lib/response.js";
import { CONTENT_TYPE } from "../lib/constants.js";
import accountDetailTemplate from "../templates/partials/account-detail.mustache";

export async function apiAccountDetail(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const username = decodeURIComponent(url.pathname.replace("/api/account/", ""));
  if (!username) return Res.notFound();

  const accounts = new KvAccountRepository(env.KV);
  const failLogs = new KvFailLogRepository(env.KV);

  const account = await accounts.get(username);
  if (!account) {
    log.warn("account_not_found", { username });
    return Res.notFound();
  }

  const logs = await failLogs.query(account.username);
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

  return new Response(html, { headers: { "Content-Type": CONTENT_TYPE.HTML } });
}

export async function apiLogs(request: Request, env: Env): Promise<Response> {
  const username = new URL(request.url).searchParams.get("username");
  if (!username) return Res.error("MISSING_USERNAME", "username required");

  const failLogs = new KvFailLogRepository(env.KV);
  const logs = await failLogs.query(username);
  return Res.json({ success: true, logs });
}
