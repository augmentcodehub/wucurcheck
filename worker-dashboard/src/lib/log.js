/**
 * 结构化日志 — JSON 格式，wrangler tail 友好
 */

let _ctx = {};

export function setContext(ctx) {
  _ctx = ctx;
}

function emit(level, msg, fields) {
  console[level](JSON.stringify({ ts: Date.now(), level, msg, ..._ctx, ...fields }));
}

export const log = {
  info: (msg, fields) => emit("info", msg, fields),
  warn: (msg, fields) => emit("warn", msg, fields),
  error: (msg, fields) => emit("error", msg, fields),
};
