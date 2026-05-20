import { layout } from "../layout.js";
import { listAccounts } from "../lib/store.js";
import { isToday } from "../views/helpers.js";
import { renderToolbar, renderTable } from "../views/account_table.js";
import { renderDetailModal, renderRegisterModal, renderRegisterKiroModal } from "../views/modals.js";
import { renderSettingsPanel } from "../views/settings_panel.js";
import { renderClientScript } from "../views/client_script.js";

export async function pageAccounts(request, env) {
  const accounts = await listAccounts(env);
  const accountsJson = JSON.stringify(accounts).replace(/</g, "\\u003c");
  const todayCount = accounts.filter((a) => isToday(a.checkin_time)).length;
  const wucurAccounts = accounts.filter((a) => !a.platform || a.platform === "wucur");
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro");
  const wucurToday = wucurAccounts.filter((a) => isToday(a.checkin_time)).length;

  const content = [
    renderToolbar(accounts.length, wucurToday, wucurAccounts.length, kiroAccounts.length),
    renderDetailModal(),
    renderRegisterModal(),
    renderRegisterKiroModal(),
    renderTable(accounts),
    '<div id="toast" class="toast toast-end hidden"><div class="alert" id="toast-msg"></div></div>',
    renderSettingsPanel(),
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

export async function apiExportKiro(request, env) {
  const accounts = await listAccounts(env);
  const kiro = accounts
    .filter(a => a.platform === "kiro" && a.status !== "suspended" && a.refresh_token)
    .map(a => ({
      refreshToken: a.refresh_token,
      clientId: a.client_id,
      clientSecret: a.client_secret,
      provider: "BuilderId",
    }));
  return new Response(JSON.stringify(kiro, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="kiro-accounts-import.json"`,
    },
  });
}
