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
import { ssoDeviceAuth } from "./sso_device_auth.js";

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
  } else if (status.error) {
    update.usage_fetch_error = status.error;
  } else {
    update.usage_current = status.usage_current;
    update.usage_limit = status.usage_limit;
    update.subscription_type = status.subscription_type;
    update.days_remaining = status.days_remaining;
    update.usage_fetch_error = null;
  }

  await putAccount(env, account.username, update);
  return { success: true };
}

/**
 * Batch refresh all Kiro accounts.
 * Also retries Device Auth for accounts that have sso_token but no refresh_token.
 * @param {object} env - Worker env bindings
 * @returns {Promise<{total: number, success: number, failed: number, errors: Array}>}
 */
export async function refreshAllKiroAccounts(env) {
  const accounts = await listAccounts(env);
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro" && a.status !== "suspended");

  // Split: accounts with refresh_token vs those needing Device Auth
  const refreshable = kiroAccounts.filter((a) => a.refresh_token);
  const needsDeviceAuth = kiroAccounts.filter((a) => !a.refresh_token && a.sso_token);

  log.info("kiro_batch_refresh_start", {
    refreshable: refreshable.length,
    needs_device_auth: needsDeviceAuth.length,
  });

  let success = 0;
  let failed = 0;
  const errors = [];

  // 1. Normal token refresh
  for (const account of refreshable) {
    const result = await refreshSingleAccount(env, account);
    if (result.success) {
      success++;
    } else {
      failed++;
      errors.push({ username: account.username, error: result.error });
    }
  }

  // 2. Retry Device Auth for accounts missing refresh_token
  for (const account of needsDeviceAuth) {
    const result = await retrySsoDeviceAuth(env, account);
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

/**
 * Retry SSO Device Auth for an account that has sso_token but no refresh_token.
 * @param {object} env
 * @param {object} account
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function retrySsoDeviceAuth(env, account) {
  log.info("sso_device_auth_retry", { username: account.username });

  const result = await ssoDeviceAuth(account.sso_token, account.region || "us-east-1");

  if (!result.success) {
    await putAccount(env, account.username, {
      last_refresh_at: new Date().toISOString(),
      last_refresh_error: `Device Auth failed: ${result.error}`,
    });
    return { success: false, error: result.error };
  }

  // Got tokens — update KV and fetch usage
  const update = {
    access_token: result.accessToken,
    refresh_token: result.refreshToken,
    client_id: result.clientId,
    client_secret: result.clientSecret,
    region: result.region,
    expires_in: result.expiresIn,
    last_refresh_at: new Date().toISOString(),
    last_refresh_error: null,
    token_expires_at: result.expiresIn
      ? new Date(Date.now() + result.expiresIn * 1000).toISOString()
      : null,
  };

  // Fetch usage with new token
  const status = await fetchAccountStatus(result.accessToken, account.idp || "BuilderId");
  if (status.suspended) {
    update.status = "suspended";
    update.last_refresh_error = status.error;
  } else if (status.error) {
    update.usage_fetch_error = status.error;
  } else {
    update.usage_current = status.usage_current;
    update.usage_limit = status.usage_limit;
    update.subscription_type = status.subscription_type;
    update.days_remaining = status.days_remaining;
    update.usage_fetch_error = null;
  }

  await putAccount(env, account.username, update);
  return { success: true };
}
