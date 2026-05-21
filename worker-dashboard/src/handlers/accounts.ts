/** Accounts page + API handlers */

import Mustache from "mustache";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { isToday } from "../views/helpers.js";
import { renderToolbar, renderTable } from "../views/account-table.js";
import { renderDetailModal, renderRegisterModal, renderRegisterKiroModal } from "../views/modals.js";
import { renderSettingsPanel } from "../views/settings-panel.js";
import { Res } from "../lib/response.js";
import { CONTENT_TYPE } from "../lib/constants.js";
import layoutTemplate from "../templates/layout.mustache";
import type { Account } from "../types/index.js";

const THEMES = [
  "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
  "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden",
  "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black",
  "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade",
  "night", "coffee", "winter", "dim", "nord", "sunset", "caramellatte",
  "abyss", "silk",
];

function layout(title: string, content: string): Response {
  const html = Mustache.render(layoutTemplate, { title, content, themes: THEMES });
  return new Response(html, { headers: { "Content-Type": CONTENT_TYPE.HTML } });
}

export async function pageAccounts(_request: Request, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const wucurAccounts = accounts.filter((a) => !a.platform || a.platform === "wucur");
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro");
  const wucurToday = wucurAccounts.filter((a) => isToday(a.checkin_time)).length;

  const content = [
    renderToolbar(accounts.length, wucurToday, wucurAccounts.length, kiroAccounts.length),
    renderDetailModal(),
    renderRegisterModal(),
    renderRegisterKiroModal(),
    renderTable(accounts),
    renderSettingsPanel(),
  ].join("\n");

  return layout("账号管理", content);
}

export async function apiAccounts(_request: Request, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  return Res.json(await repo.list());
}

export async function apiExportCsv(_request: Request, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const header = "username,password,platform,status,balance,checkin_time,last_result";
  const rows = accounts.map((a: Account) =>
    [a.username, a.password, a.platform || "", a.status, a.balance ?? "", a.checkin_time || "", a.last_result || ""]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  );
  return new Response([header, ...rows].join("\n"), {
    headers: {
      "Content-Type": CONTENT_TYPE.CSV,
      "Content-Disposition": `attachment; filename="accounts_${new Date().toISOString().slice(0, 10)}.csv"`,
    },
  });
}

export async function apiExportKiro(_request: Request, env: Env): Promise<Response> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const kiro = accounts
    .filter((a) => a.platform === "kiro" && a.status !== "suspended" && a.refresh_token)
    .map((a) => ({
      refreshToken: a.refresh_token,
      clientId: a.client_id,
      clientSecret: a.client_secret,
      provider: "BuilderId",
    }));
  return new Response(JSON.stringify(kiro, null, 2), {
    headers: {
      "Content-Type": CONTENT_TYPE.JSON,
      "Content-Disposition": `attachment; filename="kiro-accounts-import.json"`,
    },
  });
}
