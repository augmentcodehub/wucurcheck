/**
 * Account Manager Service — orchestrates Kiro token refresh + KV update.
 */

import { log } from "../lib/log.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { refreshToken } from "./kiro-token.js";
import { fetchAccountStatus } from "./kiro-api.js";
import { ssoDeviceAuth } from "./sso-device-auth.js";
import type { Account } from "../types/index.js";

interface RefreshResult {
  success: boolean;
  error?: string;
}

export async function refreshSingleAccount(env: Env, account: Account): Promise<RefreshResult> {
  if (!account.refresh_token) return { success: false, error: "No refresh_token" };

  const repo = new KvAccountRepository(env.KV);
  const result = await refreshToken(account);

  if (!result.success) {
    await repo.put(account.username, { last_refresh_error: result.error, last_refresh_at: new Date().toISOString() } as Partial<Account>);
    return { success: false, error: result.error };
  }

  const update: Partial<Account> = {
    access_token: result.access_token,
    refresh_token: result.refresh_token,
    last_refresh_at: new Date().toISOString(),
    last_refresh_error: null,
    token_expires_at: result.expires_in ? new Date(Date.now() + result.expires_in * 1000).toISOString() : undefined,
  };

  const accessToken = result.access_token ?? "";
  const status = await fetchAccountStatus(accessToken, account.idp || "BuilderId");
  if (status.suspended) {
    update.status = "suspended";
    update.last_refresh_error = status.error;
  } else if (!status.error) {
    update.usage_current = status.usage_current;
    update.usage_limit = status.usage_limit;
    update.subscription_type = status.subscription_type;
    update.days_remaining = status.days_remaining ?? undefined;
  }

  await repo.put(account.username, update);
  return { success: true };
}

export async function refreshAllKiroAccounts(env: Env): Promise<{ total: number; success: number; failed: number; errors: Array<{ username: string; error?: string }> }> {
  const repo = new KvAccountRepository(env.KV);
  const accounts = await repo.list();
  const kiroAccounts = accounts.filter((a) => a.platform === "kiro" && a.status !== "suspended");

  const refreshable = kiroAccounts.filter((a) => a.refresh_token);
  const needsDeviceAuth = kiroAccounts.filter((a) => !a.refresh_token && a.sso_token);

  log.info("kiro_batch_refresh_start", { refreshable: refreshable.length, needs_device_auth: needsDeviceAuth.length });

  let success = 0, failed = 0;
  const errors: Array<{ username: string; error?: string }> = [];

  for (const account of refreshable) {
    const r = await refreshSingleAccount(env, account);
    if (r.success) success++; else { failed++; errors.push({ username: account.username, error: r.error }); }
  }

  for (const account of needsDeviceAuth) {
    const r = await retrySsoDeviceAuth(env, account);
    if (r.success) success++; else { failed++; errors.push({ username: account.username, error: r.error }); }
  }

  log.info("kiro_batch_refresh_done", { total: kiroAccounts.length, success, failed });
  return { total: kiroAccounts.length, success, failed, errors };
}

async function retrySsoDeviceAuth(env: Env, account: Account): Promise<RefreshResult> {
  log.info("sso_device_auth_retry", { username: account.username });
  const repo = new KvAccountRepository(env.KV);
  if (!account.sso_token) {
    await repo.put(account.username, { last_refresh_at: new Date().toISOString(), last_refresh_error: "No sso_token" } as Partial<Account>);
    return { success: false, error: "No sso_token" };
  }
  const result = await ssoDeviceAuth(account.sso_token, account.region || "us-east-1");

  if (!result.success) {
    await repo.put(account.username, { last_refresh_at: new Date().toISOString(), last_refresh_error: `Device Auth failed: ${result.error}` } as Partial<Account>);
    return { success: false, error: result.error };
  }

  const update: Partial<Account> = {
    access_token: result.accessToken,
    refresh_token: result.refreshToken,
    client_id: result.clientId,
    client_secret: result.clientSecret,
    last_refresh_at: new Date().toISOString(),
    last_refresh_error: null,
    token_expires_at: result.expiresIn ? new Date(Date.now() + result.expiresIn * 1000).toISOString() : undefined,
  };

  const status = await fetchAccountStatus(result.accessToken ?? "", account.idp || "BuilderId");
  if (status.suspended) { update.status = "suspended"; update.last_refresh_error = status.error; }
  else if (!status.error) { update.usage_current = status.usage_current; update.usage_limit = status.usage_limit; update.subscription_type = status.subscription_type; update.days_remaining = status.days_remaining ?? undefined; }

  await repo.put(account.username, update);
  return { success: true };
}
