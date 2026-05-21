/** Client-side JavaScript (rendered inline in page) */

const AUTO_CHECKIN_DELAY_MS = 180000;
const MAX_EMAIL_LENGTH = 20;
const EXAMPLES = {"fruit+animal":["fig0cat","plum3fox","kiwi5owl"],"plant+animal":["oak2fox","fern7bee","ivy4cat"],"fruit+metal":["fig0tin","plum3gold","lime5iron"],"plant+metal":["oak2tin","fern7gold","ivy4iron"]};

export function renderClientScript(accountsJson) {
  return `
<script>
const accounts = ${accountsJson};
const PAGE_SIZE = 10;
function switchTab(tab) {
  document.getElementById("tab-wucur").classList.toggle("hidden", tab !== "wucur");
  document.getElementById("tab-kiro").classList.toggle("hidden", tab !== "kiro");
  document.getElementById("tab-btn-wucur").classList.toggle("tab-active", tab === "wucur");
  document.getElementById("tab-btn-kiro").classList.toggle("tab-active", tab === "kiro");
}
function renderTabPage(tab, page) {
  const tbody = document.getElementById("tbody-"+tab);
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const total = rows.length;
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  rows.forEach((row, i) => { row.style.display = (i >= (page-1)*PAGE_SIZE && i < page*PAGE_SIZE) ? "" : "none"; });
  const pg = document.getElementById("tbody-"+tab+"-pagination");
  if (totalPages <= 1) { pg.innerHTML = ""; return; }
  let html = '<button class="btn btn-xs '+(page===1?'btn-disabled':'')+'" onclick="renderTabPage(\\\''+tab+'\\\','+(page-1)+')">«</button>';
  for (let p = 1; p <= totalPages; p++) { html += '<button class="btn btn-xs '+(p===page?'btn-primary':'')+'" onclick="renderTabPage(\\\''+tab+'\\\','+p+')">'+p+'</button>'; }
  html += '<button class="btn btn-xs '+(page===totalPages?'btn-disabled':'')+'" onclick="renderTabPage(\\\''+tab+'\\\','+(page+1)+')">»</button>';
  pg.innerHTML = html;
}
document.addEventListener("DOMContentLoaded", () => { renderTabPage("wucur", 1); renderTabPage("kiro", 1); });
const MAX_TOTAL = ${MAX_EMAIL_LENGTH};
const COMBO_EXAMPLES = ${JSON.stringify(EXAMPLES)};

function updatePreview() {
  const combo = document.getElementById("reg-prefix").value;
  const domain = document.getElementById("reg-domain").value;
  const pwd = document.getElementById("reg-password").value;
  const maxLocal = MAX_TOTAL - domain.length - 2;
  const samples = COMBO_EXAMPLES[combo] || COMBO_EXAMPLES["fruit+animal"];
  const sample = samples[0] + "@" + domain;
  document.getElementById("reg-preview").textContent = sample + "  (共" + sample.length + "字符)";
  const msgs = [];
  if (maxLocal < 6) msgs.push("⚠️ 域名太长！用户名只剩 " + maxLocal + " 字符，组合不够用");
  else if (maxLocal < 9) msgs.push("⚠️ 域名较长，仅支持短单词组合（如 fig0cat）");
  else msgs.push("✅ 可用 " + maxLocal + " 字符，组合充足");
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
  renderUsers(d.users || []);
}
function renderUsers(users) {
  const el = document.getElementById("user-list");
  if (!users.length) { el.innerHTML = '<span class="text-base-content/50">暂无额外用户（仅 admin）</span>'; return; }
  el.innerHTML = users.map(u => '<div class="flex items-center gap-2 mb-1"><span class="badge badge-sm">'+u.username+'</span><span class="text-xs text-base-content/50">'+u.role+'</span><button class="btn btn-xs btn-ghost btn-error" onclick="delUser(\\''+u.username+'\\')">删除</button></div>').join('');
}
async function addUser() {
  const username = document.getElementById("new-user").value;
  const password = document.getElementById("new-user-pass").value;
  const role = document.getElementById("new-user-role").value;
  if (!username || !password) { showToast("用户名和密码必填", false); return; }
  const r = await fetch("/api/settings", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add_user",username,password,role})});
  const d = await r.json();
  if (d.success) { showToast("✅ 用户已添加",true); document.getElementById("new-user").value=""; document.getElementById("new-user-pass").value=""; loadCron(); }
  else showToast("❌ "+d.error, false);
}
async function delUser(username) {
  if (!confirm("确定删除用户 "+username+" ?")) return;
  const r = await fetch("/api/settings", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"delete_user",username})});
  const d = await r.json();
  if (d.success) { showToast("✅ 已删除",true); loadCron(); }
  else showToast("❌ 失败",false);
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
  const body = { action:"register", inputs:{ count:document.getElementById("reg-count").value, email_prefix:document.getElementById("reg-prefix").value, email_domain:document.getElementById("reg-domain").value, password:document.getElementById("reg-password").value }};
  try {
    const r = await fetch("/api/trigger", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    document.getElementById("register-modal").close();
    showToast(d.success ? "✅ 已触发注册 "+body.inputs.count+" 个账号，3分钟后自动签到" : "❌ "+(d.error_code||"FAILED"), d.success);
    if (d.success) { setTimeout(() => { fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"checkin_unchecked"})}); showToast("🔄 自动触发签到未签到账号",true); }, ${AUTO_CHECKIN_DELAY_MS}); }
  } finally { btn.classList.remove("loading","loading-spinner"); }
}
async function doRegisterKiro(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  const body = { action:"register_kiro", inputs:{ count:document.getElementById("kiro-count").value, email_domain:document.getElementById("kiro-domain").value, proxy:document.getElementById("kiro-proxy").value }};
  try {
    const r = await fetch("/api/trigger", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d = await r.json();
    document.getElementById("register-kiro-modal").close();
    showToast(d.success ? "✅ 已触发注册 "+body.inputs.count+" 个 Kiro 账号" : "❌ "+(d.error||d.error_code||"FAILED"), d.success);
  } finally { btn.classList.remove("loading","loading-spinner"); }
}
async function trigger(event, target) {
  const btn = event?.currentTarget;
  if (btn) btn.classList.add("loading","loading-spinner");
  try { const r = await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"checkin",target})}); const d = await r.json(); showToast(d.success?"✅ 已触发签到":"❌ "+(d.error_code||"FAILED"),d.success); }
  finally { if (btn) btn.classList.remove("loading","loading-spinner"); }
}
async function checkinUnchecked(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  try { const r = await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"checkin_unchecked"})}); const d = await r.json(); showToast(d.success?"✅ 已触发 "+d.count+" 个账号签到":"❌ "+(d.error||d.error_code),d.success); }
  finally { btn.classList.remove("loading","loading-spinner"); }
}
function toggleAll(el) { document.querySelectorAll(".row-check").forEach(cb => cb.checked = el.checked); }
async function delSelected() {
  const checked = Array.from(document.querySelectorAll(".row-check:checked")).map(cb => cb.value);
  if (!checked.length) { showToast("请先勾选要删除的账号",false); return; }
  if (!confirm("确定删除选中的 "+checked.length+" 个账号？")) return;
  for (const u of checked) await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"delete",target:u})});
  showToast("✅ 已删除 "+checked.length+" 个账号",true); setTimeout(()=>location.reload(),500);
}
async function batchDel(action) {
  if (!confirm("确定删除"+(action==="delete_all"?"全部":"失败")+"账号？不可恢复")) return;
  const r = await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action})});
  const d = await r.json();
  if (d.success) { showToast("✅ 已删除 "+d.count+" 个",true); setTimeout(()=>location.reload(),500); }
  else showToast("❌ 失败",false);
}
function showDetail(username) {
  const a = accounts.find(i => i.username === username);
  if (!a) return;
  document.getElementById("detail-title").textContent = "账号详情 - " + a.username;
  document.getElementById("detail-platform").textContent = a.platform || "-";
  const s = document.getElementById("detail-status");
  s.className = "badge badge-sm " + ({"active":"badge-success","failed":"badge-error","pending":"badge-warning"}[a.status]||"badge-ghost");
  s.textContent = a.status || "unknown";
  document.getElementById("detail-balance").textContent = a.balance ?? "-";
  document.getElementById("detail-checkin-time").textContent = a.checkin_time || "-";
  document.getElementById("detail-last-result").textContent = a.last_result || "-";
  const ssoRow = document.getElementById("detail-sso-row");
  if (a.sso_token) { ssoRow.classList.remove("hidden"); document.getElementById("detail-sso-token").textContent = a.sso_token; } else { ssoRow.classList.add("hidden"); }
  const logsDiv = document.getElementById("detail-logs");
  const logsList = document.getElementById("detail-logs-list");
  logsDiv.classList.add("hidden"); logsList.innerHTML = "<span class='loading loading-dots loading-xs'></span>";
  document.getElementById("account-detail").showModal();
  fetch("/api/logs?username="+encodeURIComponent(username)).then(r=>r.json()).then(d=>{
    if(d.logs && d.logs.length){
      logsDiv.classList.remove("hidden");
      logsList.innerHTML = d.logs.map(l=>'<div class="flex justify-between bg-error/10 rounded px-2 py-1"><span>'+l.date+'</span><span class="text-error truncate ml-2">'+l.reason+'</span></div>').join("");
    } else { logsDiv.classList.add("hidden"); }
  }).catch(()=>{ logsDiv.classList.add("hidden"); });
}
function copyDetail() {
  const a = accounts.find(i => i.username === document.getElementById("detail-title").textContent.replace("账号详情 - ",""));
  if (!a || !a.sso_token) { showToast("❌ 无 SSO Token",false); return; }
  navigator.clipboard.writeText(a.sso_token).then(()=>showToast("✅ 已复制 SSO Token",true)).catch(()=>showToast("❌ 复制失败",false));
}
async function refreshKiro(event, username) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  try {
    const r = await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"kiro_refresh",target:username})});
    const d = await r.json();
    showToast(d.success?"✅ 已触发刷新 "+username:"❌ "+(d.error||d.error_code||"FAILED"),d.success);
  } finally { btn.classList.remove("loading","loading-spinner"); }
}
async function refreshAllKiro(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading","loading-spinner");
  try {
    const r = await fetch("/api/trigger",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"kiro_refresh_all"})});
    const d = await r.json();
    showToast(d.success?"✅ 已触发批量刷新 ("+d.count+" 个)":"❌ "+(d.error||d.error_code||"FAILED"),d.success);
  } finally { btn.classList.remove("loading","loading-spinner"); }
}
function showToast(msg, ok) {
  const t = document.getElementById("toast");
  const m = document.getElementById("toast-msg");
  m.textContent = msg; m.className = "alert "+(ok?"alert-success":"alert-error");
  t.classList.remove("hidden"); setTimeout(()=>t.classList.add("hidden"),3000);
}
<\/script>`;
}
