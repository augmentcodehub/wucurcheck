/**
 * Kiro Web Portal API client — CBOR protocol.
 *
 * Lightweight Worker-side implementation using cborg.
 */

import { encode, decode } from "cborg";

/**
 * Custom tag decoder — cborg tag decoders receive a decode() function.
 */
const TAGS = {
  1: (decode) => {
    const val = decode(); // get the tagged content (epoch timestamp)
    if (typeof val !== "number") return val;
    const ts = val > 1e12 ? val : val * 1000;
    return new Date(ts).toISOString();
  },
};

function decodeCbor(buf) {
  return decode(buf, { tags: TAGS, allowIndefinite: true });
}
import { log } from "../lib/log.js";

const API_BASE = "https://app.kiro.dev/service/KiroWebPortalService/operation";

/**
 * Make a CBOR-encoded request to Kiro API.
 * @param {string} operation - API operation name
 * @param {object} body - Request payload
 * @param {string} accessToken - Bearer token
 * @param {string} idp - Identity provider (BuilderId|Github|Google)
 * @returns {Promise<object>} Decoded response
 */
async function request(operation, body, accessToken, idp = "BuilderId") {
  const resp = await fetch(`${API_BASE}/${operation}`, {
    method: "POST",
    headers: {
      accept: "application/cbor",
      "content-type": "application/cbor",
      "smithy-protocol": "rpc-v2-cbor",
      "amz-sdk-invocation-id": crypto.randomUUID(),
      "amz-sdk-request": "attempt=1; max=1",
      "x-amz-user-agent": "aws-sdk-js/1.0.0 kiro-account-manager/1.0.0",
      authorization: `Bearer ${accessToken}`,
      cookie: `Idp=${idp}; AccessToken=${accessToken}`,
    },
    body: encode(body),
  });

  if (!resp.ok) {
    let errorMsg = `HTTP ${resp.status}`;
    try {
      const errData = decodeCbor(new Uint8Array(await resp.arrayBuffer()));
      const errType = (errData.__type || "").split("#").pop() || "";
      errorMsg = errData.message ? `${errType}: ${errData.message}` : errorMsg;
    } catch { /* ignore parse errors */ }
    throw new KiroApiError(resp.status, errorMsg);
  }

  return decodeCbor(new Uint8Array(await resp.arrayBuffer()));
}

/**
 * Fetch account usage and subscription info.
 * @param {string} accessToken
 * @param {string} idp
 * @returns {Promise<{usage_current, usage_limit, subscription_type, days_remaining, error?}>}
 */
export async function fetchAccountStatus(accessToken, idp = "BuilderId") {
  try {
    const data = await request(
      "GetUserUsageAndLimits",
      { isEmailRequired: true, origin: "KIRO_IDE" },
      accessToken,
      idp
    );
    log.info("kiro_api_usage_raw", { keys: Object.keys(data), has_breakdown: !!data.usageBreakdownList });
    return parseUsageResponse(data);
  } catch (e) {
    if (e instanceof KiroApiError && e.status === 423) {
      return { suspended: true, error: e.message };
    }
    log.error("kiro_api_error", { error: e.message, status: e.status });
    return { error: e.message };
  }
}

function parseUsageResponse(data) {
  const credit = (data.usageBreakdownList || []).find((b) => b.resourceType === "CREDIT");
  const baseLimit = credit?.usageLimit ?? 0;
  const baseCurrent = credit?.currentUsage ?? 0;

  let ftLimit = 0, ftCurrent = 0;
  const ft = credit?.freeTrialInfo;
  if (ft?.freeTrialStatus === "ACTIVE") {
    ftLimit = ft.usageLimit ?? 0;
    ftCurrent = ft.currentUsage ?? 0;
  }

  let bonusLimit = 0, bonusCurrent = 0;
  for (const b of credit?.bonuses || []) {
    if (b.status === "ACTIVE" || (b.usageLimit ?? 0) > 0) {
      bonusLimit += b.usageLimit ?? 0;
      bonusCurrent += b.currentUsage ?? 0;
    }
  }

  const totalLimit = baseLimit + ftLimit + bonusLimit;
  const totalCurrent = baseCurrent + ftCurrent + bonusCurrent;

  const subTitle = data.subscriptionInfo?.subscriptionTitle || "Free";
  let subscriptionType = "Free";
  if (subTitle.toUpperCase().includes("PRO")) subscriptionType = "Pro";
  else if (subTitle.toUpperCase().includes("ENTERPRISE")) subscriptionType = "Enterprise";

  let daysRemaining = null;
  if (data.nextDateReset) {
    try {
      const resetTs = typeof data.nextDateReset === "number"
        ? data.nextDateReset > 1e12 ? data.nextDateReset : data.nextDateReset * 1000
        : new Date(data.nextDateReset).getTime();
      if (!isNaN(resetTs)) {
        daysRemaining = Math.max(0, Math.ceil((resetTs - Date.now()) / 86400000));
      }
    } catch { /* ignore */ }
  }

  return {
    usage_current: totalCurrent,
    usage_limit: totalLimit,
    subscription_type: subscriptionType,
    days_remaining: daysRemaining,
  };
}

class KiroApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
