/**
 * Distributed lock via KV — prevents duplicate workflow triggers.
 */

import { KV_PREFIX } from "./constants.js";

const LOCK_TTL = 300; // 5 minutes auto-expire

export async function acquireLock(env: Env, key: string): Promise<boolean> {
  const lockKey = `${KV_PREFIX.LOCK}${key}`;
  const existing = await env.KV.get(lockKey);
  if (existing) return false;
  await env.KV.put(lockKey, Date.now().toString(), { expirationTtl: LOCK_TTL });
  return true;
}

export async function releaseLock(env: Env, key: string): Promise<void> {
  await env.KV.delete(`${KV_PREFIX.LOCK}${key}`);
}
