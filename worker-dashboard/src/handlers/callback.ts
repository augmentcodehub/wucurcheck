/** POST /callback — GitHub Actions callback handler */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { KvAccountRepository } from "../repositories/kv-account-repository.js";
import { releaseLock } from "../lib/trigger-lock.js";
import { Res } from "../lib/response.js";
import type { Account, AccountStatus, AccountPlatform } from "../types/index.js";

// --- Type Guards ---

function str(v: unknown): string | undefined {
  return typeof v === "string" && v ? v : undefined;
}

function isStatus(v: unknown): v is AccountStatus {
  return v === "active" || v === "failed" || v === "suspended" || v === "pending";
}

function isPlatform(v: unknown): v is AccountPlatform {
  return v === "wucur" || v === "kiro";
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function detectPlatform(email: string): AccountPlatform {
  return email.includes("ouraihub.com") ? "kiro" : "wucur";
}

// --- Automatic Field Mapping ---
// 外部输入字段名（驼峰）→ Account 属性名（下划线）
const FIELD_ALIASES: Record<string, keyof Account> = {
  email: "username",
  refreshToken: "refresh_token",
  accessToken: "access_token",
  clientId: "client_id",
  clientSecret: "client_secret",
  tokenExpiresAt: "token_expires_at",
  lastRefreshAt: "last_refresh_at",
  subscriptionType: "subscription_type",
  usageCurrent: "usage_current",
  usageLimit: "usage_limit",
  daysRemaining: "days_remaining",
  ssoToken: "sso_token",
  authMethod: "auth_method",
};

// Account 中所有 string 类型字段
const STRING_FIELDS: ReadonlySet<string> = new Set([
  "username", "password", "balance", "checkin_time", "last_result",
  "access_token", "refresh_token", "client_id", "client_secret",
  "token_expires_at", "last_refresh_at", "subscription_type",
  "sso_token", "auth_method", "idp", "region",
]);

// Account 中所有 number 类型字段
const NUMBER_FIELDS: ReadonlySet<string> = new Set([
  "usage_current", "usage_limit", "days_remaining",
]);

/**
 * 将外部输入自动映射为 Partial<Account>。
 * - 处理驼峰/下划线别名
 * - 只提取 Account 中定义的字段
 * - 自动根据邮箱判断 platform
 */
function toAccountFields(input: Record<string, unknown>): Partial<Account> {
  const result: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(input)) {
    const field = FIELD_ALIASES[key] || key;

    if (STRING_FIELDS.has(field) && typeof value === "string" && value) {
      result[field] = value;
    } else if (NUMBER_FIELDS.has(field) && typeof value === "number") {
      result[field] = value;
    }
  }

  // Platform: 显式传入优先，否则根据邮箱自动判断
  if (isPlatform(input.platform)) {
    result.platform = input.platform;
  } else {
    const username = (result.username as string) || "";
    if (username) result.platform = detectPlatform(username);
  }

  // Status
  if (isStatus(input.status)) result.status = input.status;

  return result as Partial<Account>;
}

// --- Handlers ---

async function handleCheckin(data: Record<string, unknown>, env: Env): Promise<void> {
  const username = str(data.username);
  if (!username) {
    log.warn("callback_checkin_no_username", { keys: Object.keys(data).join(",") });
    return;
  }

  const fields = toAccountFields(data);
  if (!fields.checkin_time) fields.checkin_time = new Date().toISOString();
  if (!fields.status) fields.status = "active";
  if (!fields.last_result) fields.last_result = "签到成功";

  const repo = new KvAccountRepository(env.KV);
  await repo.put(username, fields);
  log.info("callback_checkin_done", { username, status: fields.status || "" });

  if (data.status === "failed") {
    const { D1LogRepository } = await import("../repositories/d1-log-repository.js");
    await new D1LogRepository(env.DB).insert({ type: "error", time: new Date().toISOString(), username, message: str(data.last_result) || "未知" });
  }
  await releaseLock(env, `checkin:${username}`);
  await releaseLock(env, "checkin:_all");
}

async function handleBatchResult(data: Record<string, unknown>, env: Env): Promise<void> {
  const raw = data.results;
  const items = Array.isArray(raw) ? raw : [raw];
  const repo = new KvAccountRepository(env.KV);

  let successCount = 0;
  let failCount = 0;

  for (const item of items) {
    try {
      if (!isObject(item)) continue;
      const username = str(item.username) || str(item.email);
      if (!username) continue;

      const fields = toAccountFields(item);
      fields.username = username;
      if (!fields.status) fields.status = "active";
      if (!fields.last_result) fields.last_result = str(item.error) || str(item.message) || "批量结果更新";

      const existing = await repo.get(username);
      const statusChanged = existing?.status !== fields.status;

      if (statusChanged || fields.status === "failed") {
        log.info("batch_item_update", {
          username,
          old_status: existing?.status || "unknown",
          new_status: fields.status || "unknown",
          last_result: fields.last_result || "",
          has_password: String(!!existing?.password),
        });
      }

      if (fields.status === "active") successCount++;
      else failCount++;

      await repo.put(username, fields);

      // 新注册的 kiro 账号写入注册日志
      if (!existing && fields.platform === "kiro") {
        const { D1LogRepository } = await import("../repositories/d1-log-repository.js");
        const logRepo = new D1LogRepository(env.DB);
        await logRepo.insert({ type: "register", time: new Date().toISOString(), username, platform: "kiro", status: fields.status || "active", message: fields.last_result || undefined });
      }

      if (item.status === "failed") {
        const { D1LogRepository } = await import("../repositories/d1-log-repository.js");
        await new D1LogRepository(env.DB).insert({ type: "error", time: new Date().toISOString(), username, message: str(item.last_result) || str(item.error) || "未知" });
      }
    } catch (e) {
      const username = isObject(item) ? str(item.username) || str(item.email) || "unknown" : "unknown";
      const msg = e instanceof Error ? e.message : "unknown";
      log.error("batch_item_error", { username, error: msg });
      failCount++;
    }
  }
  await releaseLock(env, "checkin:_all");
  log.info("batch_result_done", { total: String(items.length), success: String(successCount), failed: String(failCount) });
}

async function handleRegister(data: Record<string, unknown>, env: Env): Promise<void> {
  const username = str(data.username);
  if (!username) {
    log.warn("callback_register_no_username", { keys: Object.keys(data).join(",") });
    return;
  }

  const fields = toAccountFields(data);
  fields.username = username;
  if (!fields.status) fields.status = "active";
  if (!fields.last_result) fields.last_result = "注册成功";

  const repo = new KvAccountRepository(env.KV);
  await repo.put(username, fields);
  log.info("callback_register_done", { username, platform: fields.platform || "", has_password: String(!!fields.password) });

  // 写入注册日志到 D1
  const { D1LogRepository } = await import("../repositories/d1-log-repository.js");
  const logRepo = new D1LogRepository(env.DB);
  await logRepo.insert({ type: "register", time: new Date().toISOString(), username, platform: fields.platform || "unknown", status: fields.status || "active", message: fields.last_result || undefined });

  await releaseLock(env, `register:${username}`);
}

// --- Dispatch ---

const ACTION_HANDLERS: Record<string, (data: Record<string, unknown>, env: Env) => Promise<void>> = {
  register: handleRegister,
  checkin: handleCheckin,
  batch_result: handleBatchResult,
};

export async function handleCallback(request: Request, env: Env): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    log.warn("callback_bad_json");
    return Res.error("INVALID_JSON", "invalid JSON", 400);
  }

  if (!isObject(body)) return Res.error("INVALID_JSON", "expected object", 400);

  const secret = env.CALLBACK_SECRET || "";
  if (!str(body.secret) || !timingSafeEqual(body.secret as string, secret)) {
    log.warn("callback_auth_failed");
    return Res.error("UNAUTHORIZED", "unauthorized", 401);
  }

  const action = str(body.action);
  const data = isObject(body.data) ? body.data : null;
  if (!action || !data) return Res.error("MISSING_FIELDS", "action and data required", 400);

  log.info("callback_received", { action, username: str(data.username) || "" });

  const handler = ACTION_HANDLERS[action];
  if (!handler) {
    log.warn("callback_unknown_action", { action });
    return Res.error("UNKNOWN_ACTION", `unknown: ${action}`, 400);
  }

  await handler(data, env);
  return Res.json({ ok: true });
}
