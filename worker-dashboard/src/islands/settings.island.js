/** Island: Settings panel — cron, password, user management */

async function loadCron() {
  const r = await fetch("/api/settings"); const d = await r.json();
  const sel = document.getElementById("cron-hours");
  (d.cron_hours || []).forEach(h => { const opt = sel.querySelector('option[value="' + h + '"]'); if (opt) opt.selected = true; });
  renderUsers(d.users || []);
}

function renderUsers(users) {
  const el = document.getElementById("user-list");
  if (!users.length) { el.innerHTML = '<span class="text-base-content/50">暂无额外用户（仅 admin）</span>'; return; }
  el.innerHTML = users.map(u => '<div class="flex items-center gap-2 mb-1"><span class="badge badge-sm">' + u.username + '</span><span class="text-xs text-base-content/50">' + u.role + '</span><button class="btn btn-xs btn-ghost btn-error" onclick="delUser(\'' + u.username + '\')">删除</button></div>').join('');
}

async function saveCron() {
  const sel = document.getElementById("cron-hours");
  const hours = Array.from(sel.selectedOptions).map(o => parseInt(o.value));
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cron_hours: hours }) });
  const d = await r.json();
  document.getElementById("cron-status").textContent = d.success ? "✅ 已保存" : "❌ 失败";
}

async function changePass() {
  const pass = document.getElementById("new-pass").value;
  if (!pass || pass.length < 4) { document.getElementById("pass-status").textContent = "❌ 至少4位"; return; }
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "change_password", new_password: pass }) });
  const d = await r.json();
  document.getElementById("pass-status").textContent = d.success ? "✅ 已修改" : "❌ " + d.error;
  document.getElementById("new-pass").value = "";
}

async function addUser() {
  const username = document.getElementById("new-user").value;
  const password = document.getElementById("new-user-pass").value;
  const role = document.getElementById("new-user-role").value;
  if (!username || !password) { showToast("用户名和密码必填", false); return; }
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "add_user", username, password, role }) });
  const d = await r.json();
  if (d.success) { showToast("✅ 用户已添加", true); document.getElementById("new-user").value = ""; document.getElementById("new-user-pass").value = ""; loadCron(); }
  else showToast("❌ " + d.error, false);
}

async function delUser(username) {
  if (!confirm("确定删除用户 " + username + " ?")) return;
  const r = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete_user", username }) });
  const d = await r.json();
  if (d.success) { showToast("✅ 已删除", true); loadCron(); } else showToast("❌ 失败", false);
}

loadCron();
loadCronLogs();

async function loadCronLogs() {
  const el = document.getElementById("cron-logs");
  try {
    const r = await fetch("/api/cron-logs"); const logs = await r.json();
    if (!logs.length) { el.innerHTML = '<span class="text-base-content/50">暂无记录</span>'; return; }
    el.innerHTML = logs.map(function(l) {
      const t = new Date(new Date(l.time).getTime() + 8*3600000);
      const ts = String(t.getUTCMonth()+1).padStart(2,'0') + '/' + String(t.getUTCDate()).padStart(2,'0') + ' ' + String(t.getUTCHours()).padStart(2,'0') + ':' + String(t.getUTCMinutes()).padStart(2,'0');
      const icon = l.ok ? '✅' : '❌';
      return '<div class="flex gap-2 items-center bg-base-200 rounded px-2 py-1"><span>' + icon + '</span><span class="font-mono">' + ts + '</span><span>签到 ' + l.count + ' 个</span><span class="text-base-content/50 truncate">' + l.accounts.slice(0,3).join(', ') + (l.count > 3 ? '...' : '') + '</span></div>';
    }).join('');
  } catch(e) { el.innerHTML = '<span class="text-error">加载失败</span>'; }
}
