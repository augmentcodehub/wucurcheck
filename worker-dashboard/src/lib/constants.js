/**
 * Constants — 全局常量定义，消除魔法字符串和数字。
 *
 * 修改 KV key 前缀或业务参数时只需改这一个文件。
 */

// ============ KV Key Prefixes ============

export const KV_PREFIX = {
  ACCOUNT: "account:",
  FAIL_LOG: "fail_log:",
  SESSION: "session:",
  USER: "user:",
  LOCK: "lock:",
};

export const KV_KEY = {
  CRON_HOUR: "config:cron_hour",
  ADMIN_PASS: "config:admin_pass",
};

// ============ Timing ============

export const TTL = {
  SESSION: 86400 * 7,       // 7 days
  LOCK: 60,                 // 60 seconds
  STATIC_CACHE: 3600,       // 1 hour
};

// ============ Pagination ============

export const PAGE_SIZE = 10;

// ============ HTTP ============

export const CONTENT_TYPE = {
  HTML: "text/html; charset=utf-8",
  JSON: "application/json; charset=utf-8",
  JS: "application/javascript; charset=utf-8",
  CSV: "text/csv; charset=utf-8",
};

export const HEADERS_JSON = { "Content-Type": CONTENT_TYPE.JSON };
