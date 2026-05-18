import { layout } from "../layout.js";
import { listAccounts } from "../lib/store.js";

export async function pageAccounts(request, env) {
  const accounts = await listAccounts(env);
  const accountsJson = JSON.stringify(accounts).replace(/</g, "\\u003c");

  const rows = accounts
    .map(
      (a) => `<tr>
    <td><input type="checkbox" class="checkbox checkbox-xs row-check" value="${esc(a.username)}"/></td>
    <td class="font-mono">${esc(a.username)}</td>
    <td class="font-mono text-xs"><span class="cursor-pointer" onclick="this.textContent=this.dataset.p" data-p="${esc(a.password)}">••••••</span></td>
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
  <div class="flex gap-2">
    <button type="button" class="btn btn-success btn-sm" onclick="document.getElementById('register-modal').showModal()">➕ 批量注册</button>
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
  <div class="stat"><div class="stat-title">总账号</div><div class="stat-value">${accounts.length}</div></div>
  <div class="stat"><div class="stat-title">今日签到</div><div class="stat-value text-success">${todayCount}</div></div>
  <div class="stat"><div class="stat-title">未签到</div><div class="stat-value text-warning">${accounts.length - todayCount}</div></div>
</div>

<div class="overflow-x-auto bg-base-100 rounded-box shadow">
<table class="table table-sm">
  <thead><tr>
    <th><input type="checkbox" class="checkbox checkbox-xs" id="select-all" onchange="toggleAll(this)"/></th>
    <th>用户名</th><th>密码</th><th>平台</th><th>余额</th><th>签到时间</th><th>状态</th><th>操作</th>
  </tr></thead>
  <tbody>${rows || '<tr><td colspan="8" class="text-center py-8 text-base-content/50">暂无账号</td></tr>'}</tbody>
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
<div class="mt-6 bg-base-100 rounded-box shadow p-4">
  <h3 class="font-bold mb-2">⏰ 定时签到设置</h3>
  <div class="flex flex-wrap gap-2 items-center">
    <span class="text-sm">每天签到时间（北京时间）：</span>
    <select id="cron-hours" class="select select-bordered select-sm" multiple size="3">
      <option value="0">08:00</option><option value="4">12:00</option><option value="6">14:00</option><option value="8">16:00</option><option value="10">18:00</option><option value="12">20:00</option><option value="14">22:00</option><option value="16">00:00</option>
    </select>
    <button class="btn btn-sm btn-primary" onclick="saveCron()">保存</button>
    <span id="cron-status" class="text-xs"></span>
  </div>
  <p class="text-xs text-base-content/50 mt-1">可多选，按住 Ctrl 选多个时间点</p>
</div>

<div class="mt-4 bg-base-100 rounded-box shadow p-4">
  <h3 class="font-bold mb-2">🔑 修改密码</h3>
  <div class="flex gap-2 items-center">
    <input id="new-pass" type="password" placeholder="输入新密码" class="input input-bordered input-sm w-48"/>
    <button class="btn btn-sm btn-warning" onclick="changePass()">修改</button>
    <span id="pass-status" class="text-xs"></span>
  </div>
</div>

<dialog id="register-modal" class="modal">
  <div class="modal-box">
    <h3 class="text-lg font-bold mb-4">➕ 批量注册账号</h3>
    <div class="space-y-3">
      <div><label class="label text-sm">数量</label><input id="reg-count" type="number" value="3" min="1" max="50" class="input input-bordered input-sm w-full" oninput="updatePreview()"/></div>
      <div><label class="label text-sm">用户名组合</label><select id="reg-prefix" class="select select-bordered select-sm w-full" onchange="updatePreview()"><option value="fruit+animal">水果+动物</option><option value="plant+animal">植物+动物</option><option value="fruit+metal">水果+金属</option><option value="plant+metal">植物+金属</option></select></div>
      <div><label class="label text-sm">邮箱域名</label><select id="reg-domain" class="select select-bordered select-sm w-full" onchange="updatePreview()"><option value="qq.com">qq.com</option><option value="163.com">163.com</option><option value="gmail.com">gmail.com</option><option value="outlook.com">outlook.com</option><option value="mailto.plus">mailto.plus</option></select></div>
      <div><label class="label text-sm">密码</label><input id="reg-password" type="text" value="123Claude&Codex" class="input input-bordered input-sm w-full" oninput="updatePreview()"/></div>
    </div>
    <div class="mt-3 p-2 bg-base-200 rounded text-xs font-mono">
      <div>样例：<span id="reg-preview"></span></div>
      <div id="reg-length" class="mt-1"></div>
    </div>
    <div class="modal-action">
      <form method="dialog"><button class="btn btn-sm">取消</button></form>
      <button id="reg-submit" class="btn btn-success btn-sm" onclick="doRegister(event)">开始注册</button>
    </div>
  </div>
</dialog>
<script>
const accounts = ${accountsJson};
const MAX_TOTAL = 20;
const EXAMPLES = {"fruit+animal":["fig0cat","plum3fox","kiwi5owl"],"plant+animal":["oak2fox","fern7bee","ivy4cat"],"fruit+metal":["fig0tin","plum3gold","lime5iron"],"plant+metal":["oak2tin","fern7gold","ivy4iron"]};
function updatePreview() {
  const combo = document.getElementById("reg-prefix").value;
  const domain = document.getElementById("reg-domain").value;
  const pwd = document.getElementById("reg-password").value;
  const maxLocal = MAX_TOTAL - domain.length - 2;
  const samples = EXAMPLES[combo] || EXAMPLES["fruit+animal"];
  const sample = samples[0] + "@" + domain;
  document.getElementById("reg-preview").textContent = sample + "  (共" + sample.length + "字符)";
  const msgs = [];
  if (maxLocal < 6) {
    msgs.push("⚠️ 域名太长！用户名只剩 " + maxLocal + " 字符，组合不够用");
  } else if (maxLocal < 9) {
    msgs.push("⚠️ 域名较长，仅支持短单词组合（如 fig0cat）");
  } else {
    msgs.push("✅ 可用 " + maxLocal + " 字符，组合充足");
  }
  if (pwd.length < 8) msgs.push("⚠️ 密码至少 8 位");
  document.getElementById("reg-length").innerHTML = msgs.join("<br>");
  const ok = maxLocal >= 6 && pwd.length >= 8;
  document.getElementById("reg-submit").disabled = !ok;
  document.getElementById("reg-submit").classList.toggle("btn-disabled", !ok);
}
setTimeout(updatePreview, 0);
async function loadCron() {
  const r = await fetch("/api/settings");
  const d = await r.json();
  const sel = document.getElementById("cron-hours");
  (d.cron_hours||[]).forEach(h => { const opt = sel.querySelector('option[value="'+h+'"]'); if(opt) opt.selected=true; });
}
async function saveCron() {
  const sel = document.getElementById("cron-hours");
  const hours = Array.from(sel.selectedOptions).map(o => parseInt(o.value));
  const r = await fetch("/api/settings", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cron_hours:hours})});
  const d = await r.json();
  document.getElementById("cron-status").textContent = d.success ? "✅ 已保存" : "❌ 失败";
}
async function changePass() {
  const pass = document.getElementById("new-pass").value;
  if (!pass || pass.length < 4) { document.getElementById("pass-status").textContent = "❌ 至少4位"; return; }
  const r = await fetch("/api/settings", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"change_password",new_password:pass})});
  const d = await r.json();
  document.getElementById("pass-status").textContent = d.success ? "✅ 已修改，下次登录生效" : "❌ "+d.error;
  document.getElementById("new-pass").value = "";
}
loadCron();
async function doRegister(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  const body = {
    action: "register",
    inputs: {
      count: document.getElementById("reg-count").value,
      email_prefix: document.getElementById("reg-prefix").value,
      email_domain: document.getElementById("reg-domain").value,
      password: document.getElementById("reg-password").value,
    }
  };
  try {
    const r = await fetch("/api/trigger", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
    const d = await r.json();
    document.getElementById("register-modal").close();
    showToast(d.success ? "✅ 已触发注册 "+body.inputs.count+" 个账号，3分钟后自动签到" : "❌ "+(d.error_code||"FAILED"), d.success);
    if (d.success) {
      setTimeout(() => {
        fetch("/api/trigger", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action:"checkin_unchecked"}) });
        showToast("🔄 自动触发签到未签到账号", true);
      }, 180000);
    }
  } finally {
    btn.classList.remove("loading","loading-spinner");
  }
}
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
async function checkinUnchecked(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  try {
    const r = await fetch("/api/trigger", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action:"checkin_unchecked"}) });
    const d = await r.json();
    showToast(d.success ? "✅ 已触发 "+d.count+" 个账号签到（间隔5-10秒）" : "❌ "+(d.error||d.error_code), d.success);
  } finally {
    btn.classList.remove("loading","loading-spinner");
  }
}
function toggleAll(el) {
  document.querySelectorAll(".row-check").forEach(cb => cb.checked = el.checked);
}
async function delSelected() {
  const checked = Array.from(document.querySelectorAll(".row-check:checked")).map(cb => cb.value);
  if (!checked.length) { showToast("请先勾选要删除的账号", false); return; }
  if (!confirm("确定删除选中的 " + checked.length + " 个账号？")) return;
  for (const username of checked) {
    await fetch("/api/trigger", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action:"delete",target:username}) });
  }
  showToast("✅ 已删除 " + checked.length + " 个账号", true);
  setTimeout(() => location.reload(), 500);
}
async function batchDel(action) {
  const label = action === "delete_all" ? "全部账号" : "所有失败账号";
  if (!confirm("确定删除" + label + "？此操作不可恢复")) return;
  const r = await fetch("/api/trigger", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action}) });
  const d = await r.json();
  if (d.success) { showToast("✅ 已删除 " + d.count + " 个账号", true); setTimeout(() => location.reload(), 500); }
  else showToast("❌ 删除失败", false);
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

export async function apiExportCsv(request, env) {
  const accounts = await listAccounts(env);
  const header = "username,password,platform,status,balance,checkin_time,last_result";
  const rows = accounts.map(a =>
    [a.username, a.password, a.platform || a.provider || "", a.status, a.balance ?? "", a.checkin_time || "", a.last_result || ""]
      .map(v => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  );
  const csv = [header, ...rows].join("\n");
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="accounts_${new Date().toISOString().slice(0,10)}.csv"`,
    },
  });
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
