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

/** Filter table rows by status badge text */
function filterByStatus(status) {
  var rows = document.querySelectorAll("#tbody-wucur tr");
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (!status) { row.style.display = ""; continue; }
    var badge = row.querySelector(".badge");
    var text = badge ? badge.textContent.trim() : "";
    row.style.display = (text === status) ? "" : "none";
  }
}
