/** Island: Tab switching + table pagination */
const PAGE_SIZE = 10;

function switchTab(tab) {
  document.getElementById("tab-wucur").classList.toggle("hidden", tab !== "wucur");
  document.getElementById("tab-kiro").classList.toggle("hidden", tab !== "kiro");
  document.getElementById("tab-btn-wucur").classList.toggle("tab-active", tab === "wucur");
  document.getElementById("tab-btn-kiro").classList.toggle("tab-active", tab === "kiro");
}

function renderTabPage(tab, page) {
  const tbody = document.getElementById("tbody-" + tab);
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const total = rows.length;
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  rows.forEach((row, i) => { row.style.display = (i >= (page - 1) * PAGE_SIZE && i < page * PAGE_SIZE) ? "" : "none"; });
  const pg = document.getElementById("tbody-" + tab + "-pagination");
  if (totalPages <= 1) { pg.innerHTML = ""; return; }
  let html = '<button class="btn btn-xs ' + (page === 1 ? "btn-disabled" : "") + '" onclick="renderTabPage(\'' + tab + '\',' + (page - 1) + ')">«</button>';
  for (let p = 1; p <= totalPages; p++) { html += '<button class="btn btn-xs ' + (p === page ? "btn-primary" : "") + '" onclick="renderTabPage(\'' + tab + '\',' + p + ')">' + p + '</button>'; }
  html += '<button class="btn btn-xs ' + (page === totalPages ? "btn-disabled" : "") + '" onclick="renderTabPage(\'' + tab + '\',' + (page + 1) + ')">»</button>';
  pg.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", () => { renderTabPage("wucur", 1); renderTabPage("kiro", 1); });
