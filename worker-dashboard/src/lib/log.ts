/**
 * 结构化日志 — JSON 格式，wrangler tail 友好。
 * 使用 AsyncLocalStorage 保证并发请求 context 隔离。
 */

import { AsyncLocalStorage } from "node:async_hooks";

export interface LogFields {
  [key: string]: string | number | boolean | null | undefined;
}

const store = new AsyncLocalStorage<LogFields>();

/** 在请求生命周期内设置 context（需包裹在 withLogContext 中） */
export function setContext(ctx: LogFields): void {
  const current = store.getStore();
  if (current) Object.assign(current, ctx);
}

/** 包裹请求处理，提供隔离的日志 context */
export function withLogContext<T>(ctx: LogFields, fn: () => T): T {
  return store.run({ ...ctx }, fn);
}

function emit(level: "info" | "warn" | "error", msg: string, fields?: LogFields): void {
  console[level](JSON.stringify({ ts: Date.now(), level, msg, ...store.getStore(), ...fields }));
}

export const log = {
  info: (msg: string, fields?: LogFields): void => emit("info", msg, fields),
  warn: (msg: string, fields?: LogFields): void => emit("warn", msg, fields),
  error: (msg: string, fields?: LogFields): void => emit("error", msg, fields),
} as const;
