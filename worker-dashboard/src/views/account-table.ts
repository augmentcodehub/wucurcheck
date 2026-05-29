/** Account table + toolbar — Mustache template rendering */

import Mustache from "mustache";
import { badge, timeAgo, esc } from "./helpers.js";
import type { Account } from "../types/index.js";
import toolbarTemplate from "../templates/partials/toolbar.mustache";
import wucurTableTemplate from "../templates/partials/wucur-table.mustache";
import kiroTableTemplate from "../templates/partials/kiro-table.mustache";

interface WucurViewModel {
  username: string;
  password: string;
  displayBalance: string;
  displayTime: string;
  statusBadge: string;
}

interface KiroViewModel {
  username: string;
  password: string;
  usageBadge: string;
  subBadge: string;
  displayDays: string;
  displayRefresh: string;
  statusBadge: string;
}

function prepareWucurAccount(a: Account): WucurViewModel {
  return {
    username: esc(a.username),
    password: a.password,
    displayBalance: a.balance ?? "-",
    displayTime: a.checkin_time ? timeAgo(a.checkin_time) : "-",
    statusBadge: badge(a.status),
  };
}

function prepareKiroAccount(a: Account): KiroViewModel {
  const current = a.usage_current ?? 0;
  const limit = a.usage_limit ?? 0;
  let usageBadge = `<span class="text-base-content/50">-</span>`;
  if (limit) {
    const pct = Math.round((current / limit) * 100);
    const color = pct >= 90 ? "text-error" : pct >= 70 ? "text-warning" : "text-success";
    usageBadge = `<span class="${color} font-mono text-xs">${current}/${limit}</span>`;
  }

  const sub = a.subscription_type || "Free";
  const cls = sub === "Pro" ? "badge-primary" : sub === "Enterprise" ? "badge-secondary" : "badge-ghost";
  const subBadge = `<span class="badge badge-xs ${cls}">${sub}</span>`;

  return {
    username: esc(a.username),
    password: a.password,
    usageBadge,
    subBadge,
    displayDays: a.days_remaining != null ? a.days_remaining + "d" : "-",
    displayRefresh: a.last_refresh_at ? timeAgo(a.last_refresh_at) : "-",
    statusBadge: badge(a.status),
  };
}

export function renderToolbar(totalCount: number, wucurToday: number, wucurCount: number, kiroCount: number): string {
  return Mustache.render(toolbarTemplate, {
    totalCount,
    wucurToday,
    wucurCount,
    wucurUnchecked: wucurCount - wucurToday,
    kiroCount,
  });
}

export function renderTable(accounts: Account[]): string {
  const wucurAccounts = accounts.filter((a) => !a.platform || a.platform === "wucur");
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro");

  const wucurHtml = Mustache.render(wucurTableTemplate, {
    accounts: wucurAccounts.map(prepareWucurAccount),
  });
  const kiroHtml = Mustache.render(kiroTableTemplate, {
    accounts: kiroAccounts.map(prepareKiroAccount),
  });

  return `
<div role="tablist" class="tabs tabs-lift tabs-lg">
  <a role="tab" class="tab tab-active" id="tab-btn-wucur" onclick="switchTab('wucur')">🔥 Wucur (${wucurAccounts.length})</a>
  <a role="tab" class="tab" id="tab-btn-kiro" onclick="switchTab('kiro')">🚀 Kiro (${kiroAccounts.length})</a>
</div>
<div class="bg-base-100 border border-base-300 border-t-0 rounded-b-box p-6">
  <div id="tab-wucur">${wucurHtml}</div>
  <div id="tab-kiro" class="hidden">${kiroHtml}</div>
</div>`;
}

import wucurRowsTemplate from "../templates/partials/wucur-rows.mustache";

export function renderWucurTbody(accounts: Account[]): string {
  return Mustache.render(wucurRowsTemplate, {
    accounts: accounts.map(prepareWucurAccount),
  });
}
