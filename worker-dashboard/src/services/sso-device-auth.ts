/**
 * SSO Device Auth — exchange sso_token for refresh_token + access_token.
 */

import { log } from "../lib/log.js";

interface DeviceAuthResult {
  success: boolean;
  accessToken?: string;
  refreshToken?: string;
  clientId?: string;
  clientSecret?: string;
  region?: string;
  expiresIn?: number;
  error?: string;
}

const SCOPES = [
  "codewhisperer:analysis", "codewhisperer:completions",
  "codewhisperer:conversations", "codewhisperer:taskassist", "codewhisperer:transformations",
];

export async function ssoDeviceAuth(bearerToken: string, region = "us-east-1"): Promise<DeviceAuthResult> {
  const oidcBase = `https://oidc.${region}.amazonaws.com`;
  const portalBase = "https://portal.sso.us-east-1.amazonaws.com";
  const startUrl = "https://view.awsapps.com/start";

  try {
    const regResp = await fetch(`${oidcBase}/client/register`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clientName: "Kiro Account Manager", clientType: "public", scopes: SCOPES, grantTypes: ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"], issuerUrl: startUrl }),
    });
    if (!regResp.ok) return fail(`Register client: HTTP ${regResp.status}`);
    const reg = await regResp.json() as { clientId: string; clientSecret: string };

    const devResp = await fetch(`${oidcBase}/device_authorization`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clientId: reg.clientId, clientSecret: reg.clientSecret, startUrl }),
    });
    if (!devResp.ok) return fail(`Device auth: HTTP ${devResp.status}`);
    const dev = await devResp.json() as { userCode: string; deviceCode: string; interval?: number };
    let interval = dev.interval || 1;

    const whoResp = await fetch(`${portalBase}/token/whoAmI`, { headers: { Authorization: `Bearer ${bearerToken}`, Accept: "application/json" } });
    if (!whoResp.ok) return fail(`whoAmI: HTTP ${whoResp.status}`);

    const sessResp = await fetch(`${portalBase}/session/device`, { method: "POST", headers: { Authorization: `Bearer ${bearerToken}`, "Content-Type": "application/json" }, body: "{}" });
    if (!sessResp.ok) return fail(`Device session: HTTP ${sessResp.status}`);
    const { token: deviceSessionToken } = await sessResp.json() as { token: string };

    const acceptResp = await fetch(`${oidcBase}/device_authorization/accept_user_code`, {
      method: "POST", headers: { "Content-Type": "application/json", Referer: "https://view.awsapps.com/" },
      body: JSON.stringify({ userCode: dev.userCode, userSessionId: deviceSessionToken }),
    });
    if (!acceptResp.ok) return fail(`Accept user code: HTTP ${acceptResp.status}`);
    const { deviceContext } = await acceptResp.json() as { deviceContext?: { deviceContextId: string; clientId?: string; clientType?: string } };

    if (deviceContext?.deviceContextId) {
      const approveResp = await fetch(`${oidcBase}/device_authorization/associate_token`, {
        method: "POST", headers: { "Content-Type": "application/json", Referer: "https://view.awsapps.com/" },
        body: JSON.stringify({ deviceContext: { deviceContextId: deviceContext.deviceContextId, clientId: deviceContext.clientId || reg.clientId, clientType: deviceContext.clientType || "public" }, userSessionId: deviceSessionToken }),
      });
      if (!approveResp.ok) return fail(`Approve: HTTP ${approveResp.status}`);
    }

    const deadline = Date.now() + 60000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, interval * 1000));
      const tokenResp = await fetch(`${oidcBase}/token`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clientId: reg.clientId, clientSecret: reg.clientSecret, grantType: "urn:ietf:params:oauth:grant-type:device_code", deviceCode: dev.deviceCode }),
      });

      if (tokenResp.ok) {
        const data = await tokenResp.json() as { accessToken: string; refreshToken: string; expiresIn: number };
        log.info("sso_device_auth_ok");
        return { success: true, accessToken: data.accessToken, refreshToken: data.refreshToken, clientId: reg.clientId, clientSecret: reg.clientSecret, region, expiresIn: data.expiresIn };
      }

      if (tokenResp.status === 400) {
        const err = await tokenResp.json() as { error: string };
        if (err.error === "authorization_pending") continue;
        if (err.error === "slow_down") { interval += 5; continue; }
        return fail(`Token poll: ${err.error}`);
      }
    }
    return fail("Authorization timeout (60s)");
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("sso_device_auth_error", { error: msg });
    return fail(msg);
  }
}

function fail(error: string): DeviceAuthResult {
  log.warn("sso_device_auth_failed", { error });
  return { success: false, error };
}
