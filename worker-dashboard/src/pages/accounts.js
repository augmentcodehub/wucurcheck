import { layout } from "../layout.js";
import { listAccounts } from "../lib/store.js";
import { isToday } from "../views/helpers.js";
import { renderToolbar, renderTable } from "../views/account_table.js";
import { renderDetailModal, renderRegisterModal } from "../views/modals.js";
import { renderSettingsPanel } from "../views/settings_panel.js";
import { renderClientScript } from "../views/client_script.js";

export async function pageAccounts(request, env) {
  const accounts = await listAccounts(env);
  const accountsJson = JSON.stringify(accounts).replace(/</g, "\\u003c");
  const todayCount = accounts.filter((a) => isToday(a.checkin_time)).length;

  const content = [
    renderToolbar(accounts.length, todayCount),
    renderTable(accounts),
    '<div id="toast" class="toast toast-end hidden"><div class="alert" id="toast-msg"></div></div>',
    renderDetailModal(),
    renderSettingsPanel(),
    renderRegisterModal(),
    renderClientScript(accountsJson),
  ].join("\n");

  return layout("账号管理", content);
}

export async function apiAccounts(request, env) {
  return Response.json(await listAccounts(env));
}

export async function apiExportCsv(request, env) {
  const accounts = await listAccounts(env);
  const header = "username,password,platform,status,balance,checkin_time,last_result";
  const rows = accounts.map(a =>
    [a.username, a.password, a.platform || "", a.status, a.balance ?? "", a.checkin_time || "", a.last_result || ""]
      .map(v => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  );
  return new Response([header, ...rows].join("\n"), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="accounts_${new Date().toISOString().slice(0,10)}.csv"`,
    },
  });
}
