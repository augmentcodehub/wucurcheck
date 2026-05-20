/**
 * Kiro Token Refresh Service
 *
 * Two strategies:
 * - OIDC (BuilderId): POST https://oidc.{region}.amazonaws.com/token
 * - Social (GitHub/Google): POST https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken
 */

import { log } from "../lib/log.js";

const OIDC_BASE = "https://oidc.{region}.amazonaws.com/token";
const SOCIAL_ENDPOINT = "https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken";

/**
 * Refresh token using OIDC (BuilderId/IdC accounts).
 * @param {object} creds - { refresh_token, client_id, client_secret, region }
 * @returns {Promise<{success: boolean, access_token?: string, refresh_token?: string, expires_in?: number, error?: string}>}
 */
export async function refreshOidc(creds) {
  const { refresh_token, client_id, client_secret, region = "us-east-1" } = creds;
  if (!refresh_token || !client_id || !client_secret) {
    return { success: false, error: "Missing OIDC credentials (refresh_token/client_id/client_secret)" };
  }

  const url = OIDC_BASE.replace("{region}", region);
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: client_id,
        clientSecret: client_secret,
        refreshToken: refresh_token,
        grantType: "refresh_token",
      }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("oidc_refresh_failed", { status: resp.status, body: text.substring(0, 200) });
      return { success: false, error: `HTTP ${resp.status}: ${text.substring(0, 100)}` };
    }

    const data = await resp.json();
    log.info("oidc_refresh_ok", { expires_in: data.expiresIn });
    return {
      success: true,
      access_token: data.accessToken,
      refresh_token: data.refreshToken || refresh_token,
      expires_in: data.expiresIn,
    };
  } catch (e) {
    log.error("oidc_refresh_error", { error: e.message });
    return { success: false, error: e.message };
  }
}

/**
 * Refresh token using Social login (GitHub/Google accounts).
 * @param {object} creds - { refresh_token }
 * @returns {Promise<{success: boolean, access_token?: string, refresh_token?: string, expires_in?: number, error?: string}>}
 */
export async function refreshSocial(creds) {
  const { refresh_token } = creds;
  if (!refresh_token) {
    return { success: false, error: "Missing refresh_token" };
  }

  try {
    const resp = await fetch(SOCIAL_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent": "kiro-account-manager/1.0.0",
      },
      body: JSON.stringify({ refreshToken: refresh_token }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("social_refresh_failed", { status: resp.status, body: text.substring(0, 200) });
      return { success: false, error: `HTTP ${resp.status}: ${text.substring(0, 100)}` };
    }

    const data = await resp.json();
    log.info("social_refresh_ok", { expires_in: data.expiresIn });
    return {
      success: true,
      access_token: data.accessToken,
      refresh_token: data.refreshToken || refresh_token,
      expires_in: data.expiresIn,
    };
  } catch (e) {
    log.error("social_refresh_error", { error: e.message });
    return { success: false, error: e.message };
  }
}

/**
 * Refresh token — auto-selects strategy based on auth_method.
 * @param {object} account - KV account record with credentials
 * @returns {Promise<{success: boolean, access_token?: string, refresh_token?: string, expires_in?: number, error?: string}>}
 */
export async function refreshToken(account) {
  const creds = {
    refresh_token: account.refresh_token,
    client_id: account.client_id,
    client_secret: account.client_secret,
    region: account.region || "us-east-1",
  };

  if (account.auth_method === "social") {
    return refreshSocial(creds);
  }
  return refreshOidc(creds);
}
