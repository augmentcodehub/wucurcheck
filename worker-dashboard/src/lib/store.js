/**
 * KV Store — 账号数据 CRUD
 *
 * Interface:
 *   listAccounts(env)          → Account[]
 *   getAccount(env, username)  → Account | null
 *   putAccount(env, username, data) → Account
 *   deleteAccount(env, username)    → void
 */

import { log } from "./log.js";
import { KV_PREFIX } from "./constants.js";

const PREFIX = KV_PREFIX.ACCOUNT;

/**
 * List all accounts (parallel KV reads).
 * @param {Object} env
 * @returns {Promise<Object[]>}
 */
export async function listAccounts(env) {
  const { keys, list_complete } = await env.KV.list({ prefix: PREFIX });

  if (!list_complete) {
    log.warn("kv_list_truncated", { count: keys.length });
  }

  const values = await Promise.all(
    keys.map((k) => env.KV.get(k.name, "json"))
  );

  return values
    .filter(Boolean)
    .map((val, i) => ({ id: keys[i].name.slice(PREFIX.length), ...val }));
}

/**
 * Get a single account by username.
 * @param {Object} env
 * @param {string} username
 * @returns {Promise<Object|null>}
 */
export async function getAccount(env, username) {
  if (!username) return null;
  return env.KV.get(`${PREFIX}${username}`, "json");
}

/**
 * Create or update an account (merge semantics).
 * @param {Object} env
 * @param {string} username
 * @param {Object} data - Fields to merge
 * @returns {Promise<Object|null>}
 */
export async function putAccount(env, username, data) {
  if (!username) {
    log.error("put_account_no_username");
    return null;
  }

  const existing = (await getAccount(env, username)) || {};
  const merged = { ...existing, ...data, username, updated_at: new Date().toISOString() };
  if (!merged.created_at) merged.created_at = merged.updated_at;

  await env.KV.put(`${PREFIX}${username}`, JSON.stringify(merged));
  log.info("account_updated", { username });
  return merged;
}

/**
 * Delete an account.
 * @param {Object} env
 * @param {string} username
 */
export async function deleteAccount(env, username) {
  if (!username) return;
  await env.KV.delete(`${PREFIX}${username}`);
  log.info("account_deleted", { username });
}
