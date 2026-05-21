/**
 * Constants — 全局常量定义，消除魔法字符串和数字。
 */

export const KV_PREFIX = {
  ACCOUNT: "account:",
  FAIL_LOG: "fail_log:",
  SESSION: "session:",
  USER: "user:",
  LOCK: "lock:",
} as const;

export const KV_KEY = {
  CRON_HOUR: "config:cron_hour",
  ADMIN_PASS: "config:admin_pass",
} as const;

export const TTL = {
  SESSION: 86400 * 7,
  LOCK: 60,
  STATIC_CACHE: 3600,
} as const;

export const CONTENT_TYPE = {
  HTML: "text/html; charset=utf-8",
  JSON: "application/json; charset=utf-8",
  JS: "application/javascript; charset=utf-8",
  CSV: "text/csv; charset=utf-8",
} as const;
