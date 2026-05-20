/** Account table + toolbar + stats */

import { badge, timeAgo, esc, isToday } from "./helpers.js";

export function renderToolbar(totalCount, wucurToday, wucurCount, kiroCount) {
  return `
<div class="flex items-center justify-between mb-4">
  <h2 class="text-2xl font-bold">账号管理</h2>
  <div class="flex gap-2">
    <button type="button" class="btn btn-success btn-sm" onclick="document.getElementById('register-modal').showModal()">➕ 批量注册</button>
    <button type="button" class="btn btn-info btn-sm" onclick="document.getElementById('register-kiro-modal').showModal()">🚀 注册 Kiro</button>
    <button type="button" class="btn btn-primary btn-sm" onclick="trigger(event, '')">🔄 手动触发签到</button>
    <button type="button" class="btn btn-accent btn-sm" onclick="checkinUnchecked(event)">⚡ 一键签到未签到</button>
    <a href="/api/export/csv" class="btn btn-ghost btn-sm">📥 导出CSV</a>
    <div class="dropdown dropdown-end">
      <label tabindex="0" class="btn btn-error btn-sm btn-outline">🗑 删除</label>
      <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box shadow w-48 z-10">
        <li><a onclick="delSelected()">删除选中的</a></li>
        <li><a onclick="batchDel('delete_failed')">删除失败的</a></li>
        <li><a onclick="batchDel('delete_all')">删除全部</a></li>
      </ul>
    </div>
  </div>
</div>
<div class="stats shadow mb-4">
  <div class="stat"><div class="stat-title">总账号</div><div class="stat-value">${totalCount}</div></div>
  <div class="stat"><div class="stat-title">Wucur 签到</div><div class="stat-value text-success">${wucurToday}/${wucurCount}</div></div>
  <div class="stat"><div class="stat-title">Wucur 未签</div><div class="stat-value text-warning">${wucurCount - wucurToday}</div></div>
  <div class="stat"><div class="stat-title">Kiro</div><div class="stat-value text-info">${kiroCount}</div></div>
</div>`;
}

// ============ Wucur Table ============

function renderWucurRows(accounts) {
  return accounts
    .map(
      (a) => `<tr>
    <td><input type="checkbox" class="checkbox checkbox-xs row-check" value="${esc(a.username)}"/></td>
    <td class="font-mono">${esc(a.username)}</td>
    <td class="font-mono text-xs"><span class="cursor-pointer" onclick="if(this.textContent==='••••••'){this.textContent=this.dataset.p}else{this.textContent='••••••'}" data-p="${esc(a.password)}">••••••</span></td>
    <td>${a.balance ?? "-"}</td>
    <td>${a.checkin_time ? timeAgo(a.checkin_time) : "-"}</td>
    <td>${badge(a.status)}</td>
    <td class="flex gap-1">
      <button type="button" class="btn btn-xs btn-ghost" onclick="showDetail('${esc(a.username)}')">详情</button>
      <button type="button" class="btn btn-xs btn-primary" onclick="trigger(event, '${esc(a.username)}')">签到</button>
    </td>
  </tr>`
    )
    .join("");
}

// ============ Kiro Table ============

function kiroUsageBadge(account) {
  const current = account.usage_current ?? 0;
  const limit = account.usage_limit ?? 0;
  if (!limit) return `<span class="text-base-content/50">-</span>`;
  const pct = Math.round((current / limit) * 100);
  const color = pct >= 90 ? "text-error" : pct >= 70 ? "text-warning" : "text-success";
  return `<span class="${color} font-mono text-xs">${current}/${limit}</span>`;
}

function kiroSubBadge(account) {
  const sub = account.subscription_type || "Free";
  const cls = sub === "Pro" ? "badge-primary" : sub === "Enterprise" ? "badge-secondary" : "badge-ghost";
  return `<span class="badge badge-xs ${cls}">${sub}</span>`;
}

function renderKiroRows(accounts) {
  return accounts
    .map(
      (a) => `<tr>
    <td><input type="checkbox" class="checkbox checkbox-xs row-check" value="${esc(a.username)}"/></td>
    <td class="font-mono text-xs">${esc(a.username)}</td>
    <td class="font-mono text-xs"><span class="cursor-pointer" onclick="if(this.textContent==='••••••'){this.textContent=this.dataset.p}else{this.textContent='••••••'}" data-p="${esc(a.password)}">••••••</span></td>
    <td>${kiroUsageBadge(a)}</td>
    <td>${kiroSubBadge(a)}</td>
    <td class="text-xs">${a.days_remaining != null ? a.days_remaining + "d" : "-"}</td>
    <td class="text-xs">${a.last_refresh_at ? timeAgo(a.last_refresh_at) : "-"}</td>
    <td>${badge(a.status)}</td>
    <td class="flex gap-1">
      <button type="button" class="btn btn-xs btn-ghost" onclick="showDetail('${esc(a.username)}')">详情</button>
      <button type="button" class="btn btn-xs btn-secondary" onclick="refreshKiro(event, '${esc(a.username)}')">刷新</button>
    </td>
  </tr>`
    )
    .join("");
}

// ============ Table Blocks ============

function renderWucurTable(accounts) {
  const rows = renderWucurRows(accounts);
  return `
<div class="overflow-x-auto bg-base-100 rounded-box shadow">
<table class="table table-sm">
  <thead><tr>
    <th><input type="checkbox" class="checkbox checkbox-xs" onchange="toggleAll(this)"/></th>
    <th>用户名</th><th>密码</th><th>余额</th><th>签到时间</th><th>状态</th><th>操作</th>
  </tr></thead>
  <tbody id="tbody-wucur">${rows || '<tr><td colspan="7" class="text-center py-8 text-base-content/50">暂无账号</td></tr>'}</tbody>
</table>
</div>
<div class="flex justify-center mt-4 gap-1" id="tbody-wucur-pagination"></div>`;
}

function renderKiroTable(accounts) {
  const rows = renderKiroRows(accounts);
  return `
<div class="flex justify-end mb-2">
  <button type="button" class="btn btn-xs btn-outline btn-secondary" onclick="refreshAllKiro(event)">🔄 批量刷新 Token</button>
</div>
<div class="overflow-x-auto bg-base-100 rounded-box shadow">
<table class="table table-sm">
  <thead><tr>
    <th><input type="checkbox" class="checkbox checkbox-xs" onchange="toggleAll(this)"/></th>
    <th>邮箱</th><th>密码</th><th>用量</th><th>订阅</th><th>剩余</th><th>刷新时间</th><th>状态</th><th>操作</th>
  </tr></thead>
  <tbody id="tbody-kiro">${rows || '<tr><td colspan="9" class="text-center py-8 text-base-content/50">暂无 Kiro 账号</td></tr>'}</tbody>
</table>
</div>
<div class="flex justify-center mt-4 gap-1" id="tbody-kiro-pagination"></div>`;
}

// ============ Export ============

export function renderTable(accounts) {
  const wucurAccounts = accounts.filter((a) => !a.platform || a.platform === "wucur");
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro");

  return `
<div role="tablist" class="tabs tabs-lift tabs-lg">
  <a role="tab" class="tab tab-active" id="tab-btn-wucur" onclick="switchTab('wucur')">🔥 Wucur (${wucurAccounts.length})</a>
  <a role="tab" class="tab" id="tab-btn-kiro" onclick="switchTab('kiro')">🚀 Kiro (${kiroAccounts.length})</a>
</div>
<div class="bg-base-100 border border-base-300 border-t-0 rounded-b-box p-6">
  <div id="tab-wucur">${renderWucurTable(wucurAccounts)}</div>
  <div id="tab-kiro" class="hidden">${renderKiroTable(kiroAccounts)}</div>
</div>`;
}
