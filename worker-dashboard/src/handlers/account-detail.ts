/** Account detail + logs API handlers */

import Mustache from "mustache";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { D1LogRepository } from "../repositories/d1-log-repository.js";
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

  const account = await accounts.get(username);
  if (!account) {
    log.warn("account_not_found", { username });
    return Res.notFound();
  }

  const todayStr = new Date().toISOString().slice(0, 10);
  const logRepo = new D1LogRepository(env.DB);
  const todayLogs = (await logRepo.query("error", todayStr)).filter((l) => l.username === username);
  const checkedToday = account.checkin_time
    ? new Date(account.checkin_time).toDateString() === new Date().toDateString()
    : false;

  const html = Mustache.render(accountDetailTemplate, {
    username: esc(account.username),
    platform: account.platform || "-",
    statusBadge: badge(account.status),
    balance: account.balance ?? "-",
    checkinTime: account.checkin_time ? timeAgo(account.checkin_time) : "-",
    checkinStatus: checkedToday ? "✅ 今日已签到" : "❌ 今日未签到",
    lastResult: account.last_result || "-",
    createdAt: account.created_at ? timeAgo(account.created_at) : "-",
    registerSource: account.register_source || null,
    ssoToken: account.sso_token || null,
    hasLogs: todayLogs.length > 0,
    logs: todayLogs,
  });

  return new Response(html, { headers: { "Content-Type": CONTENT_TYPE.HTML } });
}

export async function apiLogs(request: Request, env: Env): Promise<Response> {
  const username = new URL(request.url).searchParams.get("username");
  if (!username) return Res.error("MISSING_USERNAME", "username required");

  const todayStr = new Date().toISOString().slice(0, 10);
  const logRepo = new D1LogRepository(env.DB);
  const logs = (await logRepo.query("error", todayStr)).filter((l) => l.username === username);
  return Res.json({ success: true, logs });
}
