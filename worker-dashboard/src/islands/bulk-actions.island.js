/** Island: Checkbox selection + bulk delete actions */

function toggleAll(el) { document.querySelectorAll(".row-check").forEach(cb => cb.checked = el.checked); }

async function delSelected() {
  const checked = Array.from(document.querySelectorAll(".row-check:checked")).map(cb => cb.value);
  if (!checked.length) { showToast("请先勾选要删除的账号", false); return; }
  if (!confirm("确定删除选中的 " + checked.length + " 个账号？")) return;
  for (const u of checked) await fetch("/api/trigger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete", target: u }) });
  showToast("✅ 已删除 " + checked.length + " 个账号", true);
  setTimeout(() => location.reload(), 500);
}

async function batchDel(action) {
  if (!confirm("确定删除" + (action === "delete_all" ? "全部" : "失败") + "账号？不可恢复")) return;
  const r = await fetch("/api/trigger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
  const d = await r.json();
  if (d.success) { showToast("✅ 已删除 " + d.count + " 个", true); setTimeout(() => location.reload(), 500); }
  else showToast("❌ 失败", false);
}

/** Filter table rows by status — fetch from API and re-render */
function filterByStatus(status) {
  fetch("/api/accounts")
    .then(function(r) { return r.json(); })
    .then(function(accounts) {
      var filtered = status ? accounts.filter(function(a) { return a.status === status; }) : accounts;
      filtered = filtered.filter(function(a) { return !a.platform || a.platform === "wucur"; });
      var tbody = document.getElementById("tbody-wucur");
      if (!tbody) return;
      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-base-content/50">无匹配账号</td></tr>';
        return;
      }
      tbody.innerHTML = filtered.map(function(a) {
        var statusCls = a.status === "active" ? "badge-success" : a.status === "failed" ? "badge-error" : "badge-ghost";
        var time = a.checkin_time ? new Date(a.checkin_time).toLocaleDateString("zh-CN", {month:"2-digit",day:"2-digit",hour:"2-digit"}).replace("/", "/") : "-";
        return '<tr>' +
          '<td><input type="checkbox" class="checkbox checkbox-xs row-check" value="' + a.username + '"/></td>' +
          '<td class="font-mono">' + a.username + '</td>' +
          '<td class="font-mono text-xs"><span class="inline-flex items-center gap-1"><span class="pwd-mask" data-p="' + (a.password||"") + '">••••••</span><button type="button" class="btn btn-ghost btn-xs px-1" onclick="togglePwd(this)">👁</button><button type="button" class="btn btn-ghost btn-xs px-1" onclick="copyPwd(this)">📋</button></span></td>' +
          '<td>' + (a.balance || "-") + '</td>' +
          '<td>' + time + '</td>' +
          '<td><span class="badge badge-sm ' + statusCls + '">' + a.status + '</span></td>' +
          '<td class="flex gap-1"><button type="button" class="btn btn-xs btn-ghost" hx-get="/api/account/' + a.username + '" hx-target="#detail-body" hx-swap="innerHTML" onclick="document.getElementById(\'account-detail\').showModal()">详情</button><button type="button" class="btn btn-xs btn-primary" hx-post="/api/trigger" hx-vals=\'{"action":"checkin","target":"' + a.username + '"}\' hx-swap="none">签到</button></td>' +
          '</tr>';
      }).join("");
    });
}
