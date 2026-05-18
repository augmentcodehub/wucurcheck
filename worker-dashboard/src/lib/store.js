/**
 * KV Store — 账号数据 CRUD
 */

import { log } from "./log.js";

const PREFIX = "account:";

export async function listAccounts(env) {
  const list = await env.KV.list({ prefix: PREFIX });
  const accounts = [];
  for (const key of list.keys) {
    const val = await env.KV.get(key.name, "json");
    if (val) accounts.push({ id: key.name.slice(PREFIX.length), ...val });
  }
  if (list.list_complete === false) {
    log.warn("kv_list_truncated", { count: accounts.length });
  }
  return accounts;
}

export async function getAccount(env, username) {
  if (!username) return null;
  return env.KV.get(`${PREFIX}${username}`, "json");
}

export async function putAccount(env, username, data) {
  if (!username) { log.error("put_account_no_username"); return null; }
  const existing = (await getAccount(env, username)) || {};
  const merged = { ...existing, ...data, username, updated_at: new Date().toISOString() };
  if (!merged.created_at) merged.created_at = merged.updated_at;
  await env.KV.put(`${PREFIX}${username}`, JSON.stringify(merged));
  log.info("account_updated", { username });
  return merged;
}

export async function deleteAccount(env, username) {
  if (!username) return;
  await env.KV.delete(`${PREFIX}${username}`);
  log.info("account_deleted", { username });
}
