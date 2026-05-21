/**
 * Kiro Web Portal API client — CBOR protocol.
 */

import { encode, decode } from "cborg";
import { log } from "../lib/log.js";

/** Custom CBOR tag decoders — tag 1 = epoch timestamp → ISO string */
const TAGS: Record<number, (decode: () => unknown) => unknown> = {
  1: (decode) => {
    const val = decode();
    if (typeof val !== "number") return val;
    const ts = val > 1e12 ? val : val * 1000;
    return new Date(ts).toISOString();
  },
};

function decodeCbor(buf: Uint8Array): Record<string, unknown> {
  return decode(buf, { tags: TAGS, allowIndefinite: true }) as Record<string, unknown>;
}

interface UsageResult {
  usage_current?: number;
  usage_limit?: number;
  subscription_type?: string;
  days_remaining?: number | null;
  suspended?: boolean;
  error?: string;
}

class KiroApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

const API_BASE = "https://app.kiro.dev/service/KiroWebPortalService/operation";

async function request(operation: string, body: object, accessToken: string, idp = "BuilderId"): Promise<Record<string, unknown>> {
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
      const errData = decodeCbor(new Uint8Array(await resp.arrayBuffer())) as Record<string, string>;
      const errType = (errData.__type || "").split("#").pop() || "";
      errorMsg = errData.message ? `${errType}: ${errData.message}` : errorMsg;
    } catch { /* ignore */ }
    throw new KiroApiError(resp.status, errorMsg);
  }

  return decodeCbor(new Uint8Array(await resp.arrayBuffer()));
}

export async function fetchAccountStatus(accessToken: string, idp = "BuilderId"): Promise<UsageResult> {
  try {
    const data = await request("GetUserUsageAndLimits", { isEmailRequired: true, origin: "KIRO_IDE" }, accessToken, idp);
    return parseUsageResponse(data);
  } catch (e) {
    if (e instanceof KiroApiError && e.status === 423) {
      return { suspended: true, error: e.message };
    }
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("kiro_api_error", { error: msg });
    return { error: msg };
  }
}

interface UsageBreakdown {
  resourceType?: string;
  usageLimit?: number;
  currentUsage?: number;
  freeTrialInfo?: { freeTrialStatus?: string; usageLimit?: number; currentUsage?: number };
  bonuses?: Array<{ status?: string; usageLimit?: number; currentUsage?: number }>;
}

function parseUsageResponse(data: Record<string, unknown>): UsageResult {
  const list = (data.usageBreakdownList as UsageBreakdown[] | undefined) || [];
  const credit = list.find((b) => b.resourceType === "CREDIT");
  const baseLimit = credit?.usageLimit ?? 0;
  const baseCurrent = credit?.currentUsage ?? 0;

  let ftLimit = 0, ftCurrent = 0;
  const ft = credit?.freeTrialInfo;
  if (ft?.freeTrialStatus === "ACTIVE") { ftLimit = ft.usageLimit ?? 0; ftCurrent = ft.currentUsage ?? 0; }

  let bonusLimit = 0, bonusCurrent = 0;
  for (const b of credit?.bonuses || []) {
    if (b.status === "ACTIVE" || (b.usageLimit ?? 0) > 0) { bonusLimit += b.usageLimit ?? 0; bonusCurrent += b.currentUsage ?? 0; }
  }

  const subInfo = data.subscriptionInfo as { subscriptionTitle?: string } | undefined;
  const subTitle = subInfo?.subscriptionTitle || "Free";
  let subscriptionType = "Free";
  if (subTitle.toUpperCase().includes("PRO")) subscriptionType = "Pro";
  else if (subTitle.toUpperCase().includes("ENTERPRISE")) subscriptionType = "Enterprise";

  let daysRemaining: number | null = null;
  if (data.nextDateReset) {
    try {
      const raw = data.nextDateReset as number | string;
      const resetTs = typeof raw === "number" ? (raw > 1e12 ? raw : raw * 1000) : new Date(raw).getTime();
      if (!isNaN(resetTs)) daysRemaining = Math.max(0, Math.ceil((resetTs - Date.now()) / 86400000));
    } catch { /* ignore */ }
  }

  return { usage_current: baseCurrent + ftCurrent + bonusCurrent, usage_limit: baseLimit + ftLimit + bonusLimit, subscription_type: subscriptionType, days_remaining: daysRemaining };
}
