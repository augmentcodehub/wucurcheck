/**
 * SSO Device Auth — exchange sso_token for refresh_token + access_token.
 *
 * 7-step flow executed directly in Worker (no GitHub Actions needed).
 */

import { log } from "../lib/log.js";

const SCOPES = [
  "codewhisperer:analysis",
  "codewhisperer:completions",
  "codewhisperer:conversations",
  "codewhisperer:taskassist",
  "codewhisperer:transformations",
];

/**
 * Execute SSO Device Auth using a bearer token (sso_token).
 * @param {string} bearerToken - x-amz-sso_authn cookie value
 * @param {string} region
 * @returns {Promise<{success: boolean, accessToken?, refreshToken?, clientId?, clientSecret?, region?, expiresIn?, error?}>}
 */
export async function ssoDeviceAuth(bearerToken, region = "us-east-1") {
  const oidcBase = `https://oidc.${region}.amazonaws.com`;
  const portalBase = "https://portal.sso.us-east-1.amazonaws.com";
  const startUrl = "https://view.awsapps.com/start";

  try {
    // Step 1: Register OIDC client
    const regResp = await fetch(`${oidcBase}/client/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientName: "Kiro Account Manager",
        clientType: "public",
        scopes: SCOPES,
        grantTypes: ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
        issuerUrl: startUrl,
      }),
    });
    if (!regResp.ok) return fail(`Register client: HTTP ${regResp.status}`);
    const reg = await regResp.json();
    const { clientId, clientSecret } = reg;

    // Step 2: Device authorization
    const devResp = await fetch(`${oidcBase}/device_authorization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clientId, clientSecret, startUrl }),
    });
    if (!devResp.ok) return fail(`Device auth: HTTP ${devResp.status}`);
    const dev = await devResp.json();
    let interval = dev.interval || 1;

    // Step 3: Verify bearer token
    const whoResp = await fetch(`${portalBase}/token/whoAmI`, {
      headers: { Authorization: `Bearer ${bearerToken}`, Accept: "application/json" },
    });
    if (!whoResp.ok) return fail(`whoAmI: HTTP ${whoResp.status} (sso_token expired?)`);

    // Step 4: Get device session token
    const sessResp = await fetch(`${portalBase}/session/device`, {
      method: "POST",
      headers: { Authorization: `Bearer ${bearerToken}`, "Content-Type": "application/json" },
      body: "{}",
    });
    if (!sessResp.ok) return fail(`Device session: HTTP ${sessResp.status}`);
    const { token: deviceSessionToken } = await sessResp.json();

    // Step 5: Accept user code
    const acceptResp = await fetch(`${oidcBase}/device_authorization/accept_user_code`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Referer: "https://view.awsapps.com/" },
      body: JSON.stringify({ userCode: dev.userCode, userSessionId: deviceSessionToken }),
    });
    if (!acceptResp.ok) return fail(`Accept user code: HTTP ${acceptResp.status}`);
    const { deviceContext } = await acceptResp.json();

    // Step 6: Approve authorization
    if (deviceContext?.deviceContextId) {
      const approveResp = await fetch(`${oidcBase}/device_authorization/associate_token`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Referer: "https://view.awsapps.com/" },
        body: JSON.stringify({
          deviceContext: {
            deviceContextId: deviceContext.deviceContextId,
            clientId: deviceContext.clientId || clientId,
            clientType: deviceContext.clientType || "public",
          },
          userSessionId: deviceSessionToken,
        }),
      });
      if (!approveResp.ok) return fail(`Approve: HTTP ${approveResp.status}`);
    }

    // Step 7: Poll for token (max 60s in Worker context)
    const deadline = Date.now() + 60000;
    while (Date.now() < deadline) {
      await sleep(interval * 1000);
      const tokenResp = await fetch(`${oidcBase}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clientId,
          clientSecret,
          grantType: "urn:ietf:params:oauth:grant-type:device_code",
          deviceCode: dev.deviceCode,
        }),
      });

      if (tokenResp.ok) {
        const data = await tokenResp.json();
        log.info("sso_device_auth_ok");
        return {
          success: true,
          accessToken: data.accessToken,
          refreshToken: data.refreshToken,
          clientId,
          clientSecret,
          region,
          expiresIn: data.expiresIn,
        };
      }

      if (tokenResp.status === 400) {
        const err = await tokenResp.json();
        if (err.error === "authorization_pending") continue;
        if (err.error === "slow_down") { interval += 5; continue; }
        return fail(`Token poll: ${err.error}`);
      }
    }

    return fail("Authorization timeout (60s)");
  } catch (e) {
    log.error("sso_device_auth_error", { error: e.message });
    return fail(e.message);
  }
}

function fail(error) {
  log.warn("sso_device_auth_failed", { error });
  return { success: false, error };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
