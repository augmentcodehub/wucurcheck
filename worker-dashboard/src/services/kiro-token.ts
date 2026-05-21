/**
 * Kiro Token Refresh Service
 *
 * Two strategies:
 * - OIDC (BuilderId): POST https://oidc.{region}.amazonaws.com/token
 * - Social (GitHub/Google): POST https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken
 */

import { log } from "../lib/log.js";
import type { Account } from "../types/index.js";

interface TokenResult {
  success: boolean;
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
}

interface OidcCreds {
  refresh_token: string;
  client_id: string;
  client_secret: string;
  region: string;
}

const OIDC_BASE = "https://oidc.{region}.amazonaws.com/token";
const SOCIAL_ENDPOINT = "https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken";

export async function refreshOidc(creds: OidcCreds): Promise<TokenResult> {
  const { refresh_token, client_id, client_secret, region } = creds;
  if (!refresh_token || !client_id || !client_secret) {
    return { success: false, error: "Missing OIDC credentials" };
  }

  const url = OIDC_BASE.replace("{region}", region);
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clientId: client_id, clientSecret: client_secret, refreshToken: refresh_token, grantType: "refresh_token" }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("oidc_refresh_failed", { status: resp.status });
      return { success: false, error: `HTTP ${resp.status}: ${text.substring(0, 100)}` };
    }

    const data = await resp.json() as { accessToken: string; refreshToken?: string; expiresIn: number };
    log.info("oidc_refresh_ok", { expires_in: data.expiresIn });
    return { success: true, access_token: data.accessToken, refresh_token: data.refreshToken || refresh_token, expires_in: data.expiresIn };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("oidc_refresh_error", { error: msg });
    return { success: false, error: msg };
  }
}

export async function refreshSocial(creds: { refresh_token: string }): Promise<TokenResult> {
  if (!creds.refresh_token) return { success: false, error: "Missing refresh_token" };

  try {
    const resp = await fetch(SOCIAL_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "User-Agent": "kiro-account-manager/1.0.0" },
      body: JSON.stringify({ refreshToken: creds.refresh_token }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("social_refresh_failed", { status: resp.status });
      return { success: false, error: `HTTP ${resp.status}: ${text.substring(0, 100)}` };
    }

    const data = await resp.json() as { accessToken: string; refreshToken?: string; expiresIn: number };
    log.info("social_refresh_ok", { expires_in: data.expiresIn });
    return { success: true, access_token: data.accessToken, refresh_token: data.refreshToken || creds.refresh_token, expires_in: data.expiresIn };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("social_refresh_error", { error: msg });
    return { success: false, error: msg };
  }
}

export async function refreshToken(account: Account & { auth_method?: string; region?: string }): Promise<TokenResult> {
  const creds: OidcCreds = {
    refresh_token: account.refresh_token || "",
    client_id: account.client_id || "",
    client_secret: account.client_secret || "",
    region: account.region || "us-east-1",
  };

  if (account.auth_method === "social") return refreshSocial(creds);
  return refreshOidc(creds);
}
