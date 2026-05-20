/**
 * Account Manager Service — orchestrates Kiro token refresh + KV update.
 *
 * Responsibilities:
 * - Batch refresh all Kiro accounts
 * - Update KV with new tokens and refresh timestamps
 * - Detect expired/suspended accounts
 */

import { log } from "../lib/log.js";
import { listAccounts, putAccount } from "../lib/store.js";
import { refreshToken } from "./kiro_token.js";
import { fetchAccountStatus } from "./kiro_api.js";

/**
 * Refresh a single Kiro account's token and update KV.
 * @param {object} env - Worker env bindings
 * @param {object} account - KV account record
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function refreshSingleAccount(env, account) {
  if (!account.refresh_token) {
    return { success: false, error: "No refresh_token" };
  }

  const result = await refreshToken(account);

  if (!result.success) {
    await putAccount(env, account.username, {
      last_refresh_error: result.error,
      last_refresh_at: new Date().toISOString(),
    });
    return { success: false, error: result.error };
  }

  // Update KV with new credentials
  const update = {
    access_token: result.access_token,
    refresh_token: result.refresh_token,
    expires_in: result.expires_in,
    last_refresh_at: new Date().toISOString(),
    last_refresh_error: null,
    token_expires_at: result.expires_in
      ? new Date(Date.now() + result.expires_in * 1000).toISOString()
      : null,
  };

  // Fetch usage with new token
  const status = await fetchAccountStatus(result.access_token, account.idp || "BuilderId");
  if (status.suspended) {
    update.status = "suspended";
    update.last_refresh_error = status.error;
  } else if (!status.error) {
    update.usage_current = status.usage_current;
    update.usage_limit = status.usage_limit;
    update.subscription_type = status.subscription_type;
    update.days_remaining = status.days_remaining;
  }

  await putAccount(env, account.username, update);
  return { success: true };
}

/**
 * Batch refresh all Kiro accounts.
 * @param {object} env - Worker env bindings
 * @returns {Promise<{total: number, success: number, failed: number, errors: Array}>}
 */
export async function refreshAllKiroAccounts(env) {
  const accounts = await listAccounts(env);
  const kiroAccounts = accounts.filter(
    (a) => a.platform === "kiro" && a.status !== "suspended" && a.refresh_token
  );

  log.info("kiro_batch_refresh_start", { count: kiroAccounts.length });

  let success = 0;
  let failed = 0;
  const errors = [];

  for (const account of kiroAccounts) {
    const result = await refreshSingleAccount(env, account);
    if (result.success) {
      success++;
    } else {
      failed++;
      errors.push({ username: account.username, error: result.error });
    }
  }

  log.info("kiro_batch_refresh_done", { total: kiroAccounts.length, success, failed });
  return { total: kiroAccounts.length, success, failed, errors };
}
