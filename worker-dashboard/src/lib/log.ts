/**
 * 结构化日志 — JSON 格式，wrangler tail 友好。
 */

export interface LogFields {
  [key: string]: string | number | boolean | null | undefined;
}

let _ctx: LogFields = {};

export function setContext(ctx: LogFields): void {
  _ctx = ctx;
}

function emit(level: "info" | "warn" | "error", msg: string, fields?: LogFields): void {
  console[level](JSON.stringify({ ts: Date.now(), level, msg, ..._ctx, ...fields }));
}

export const log = {
  info: (msg: string, fields?: LogFields): void => emit("info", msg, fields),
  warn: (msg: string, fields?: LogFields): void => emit("warn", msg, fields),
  error: (msg: string, fields?: LogFields): void => emit("error", msg, fields),
} as const;
