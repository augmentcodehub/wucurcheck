import { layout } from "../layout.js";
import { listAccounts } from "../lib/store.js";

export async function pageAccounts(request, env) {
  const accounts = await listAccounts(env);
  const accountsJson = JSON.stringify(accounts).replace(/</g, "\\u003c");

  const rows = accounts
    .map(
      (a) => `<tr>
    <td class="font-mono">${esc(a.username)}</td>
    <td class="font-mono text-xs">${esc(a.password)}</td>
    <td>${esc(a.platform || "-")}</td>
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

  const todayCount = accounts.filter((a) => isToday(a.checkin_time)).length;

  const content = `
<div class="flex items-center justify-between mb-4">
  <h2 class="text-2xl font-bold">账号管理</h2>
  <button type="button" class="btn btn-primary btn-sm" onclick="trigger(event, '')">🔄 手动触发签到</button>
</div>

<div class="stats shadow mb-4">
  <div class="stat"><div class="stat-title">总账号</div><div class="stat-value">${accounts.length}</div></div>
  <div class="stat"><div class="stat-title">今日签到</div><div class="stat-value text-success">${todayCount}</div></div>
  <div class="stat"><div class="stat-title">未签到</div><div class="stat-value text-warning">${accounts.length - todayCount}</div></div>
</div>

<div class="overflow-x-auto bg-base-100 rounded-box shadow">
<table class="table table-sm">
  <thead><tr>
    <th>用户名</th><th>密码</th><th>平台</th><th>余额</th><th>签到时间</th><th>状态</th><th>操作</th>
  </tr></thead>
  <tbody>${rows || '<tr><td colspan="7" class="text-center py-8 text-base-content/50">暂无账号</td></tr>'}</tbody>
</table>
</div>

<div id="toast" class="toast toast-end hidden"><div class="alert" id="toast-msg"></div></div>
<dialog id="account-detail" class="modal">
  <div class="modal-box">
    <h3 class="text-lg font-bold mb-4" id="detail-title">账号详情</h3>
    <div class="space-y-2 text-sm">
      <div><span class="font-semibold">平台：</span><span id="detail-platform"></span></div>
      <div><span class="font-semibold">状态：</span><span id="detail-status" class="badge badge-sm"></span></div>
      <div><span class="font-semibold">余额：</span><span id="detail-balance"></span></div>
      <div><span class="font-semibold">签到时间：</span><span id="detail-checkin-time"></span></div>
      <div><span class="font-semibold">最近结果：</span><span id="detail-last-result"></span></div>
    </div>
    <div class="modal-action">
      <form method="dialog"><button class="btn">关闭</button></form>
    </div>
  </div>
</dialog>
<script>
const accounts = ${accountsJson};
async function trigger(event, target) {
  const btn = event?.currentTarget;
  if (btn) btn.classList.add("loading","loading-spinner");
  try {
    const r = await fetch("/api/trigger", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ action: "checkin", target })
    });
    const d = await r.json();
    showToast(d.success ? "✅ 已触发签到" : "❌ "+(d.error_code || "FAILED"), d.success);
  } finally {
    if (btn) btn.classList.remove("loading","loading-spinner");
  }
}
function showDetail(username) {
  const account = accounts.find((item) => item.username === username);
  if (!account) return;
  document.getElementById("detail-title").textContent = "账号详情 - " + account.username;
  document.getElementById("detail-platform").textContent = account.platform || "-";
  const statusEl = document.getElementById("detail-status");
  statusEl.className = "badge badge-sm " + statusClass(account.status);
  statusEl.textContent = account.status || "unknown";
  document.getElementById("detail-balance").textContent = account.balance ?? "-";
  document.getElementById("detail-checkin-time").textContent = account.checkin_time ? timeAgo(account.checkin_time) : "-";
  document.getElementById("detail-last-result").textContent = account.last_result || "-";
  document.getElementById("account-detail").showModal();
}
function showToast(msg, ok) {
  const t = document.getElementById("toast");
  const m = document.getElementById("toast-msg");
  m.textContent = msg;
  m.className = "alert " + (ok ? "alert-success" : "alert-error");
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 3000);
}
</script>`;

  return layout("账号管理", content);
}

export async function apiAccounts(request, env) {
  return Response.json(await listAccounts(env));
}

function badge(status) {
  const m = { active: "badge-success", pending: "badge-warning", failed: "badge-error", expired: "badge-ghost" };
  return `<span class="badge badge-sm ${m[status] || "badge-ghost"}">${esc(status || "unknown")}</span>`;
}

function statusClass(status) {
  const m = { active: "badge-success", pending: "badge-warning", failed: "badge-error", expired: "badge-ghost" };
  return m[status] || "badge-ghost";
}

function isToday(ts) {
  if (!ts) return false;
  return new Date(ts).toDateString() === new Date().toDateString();
}

function timeAgo(ts) {
  const d = new Date(ts);
  const now = new Date();
  const diff = Math.floor((now - d) / 60000);
  if (diff < 60) return `${diff}分钟前`;
  if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
  return d.toLocaleDateString("zh-CN");
}

function esc(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
