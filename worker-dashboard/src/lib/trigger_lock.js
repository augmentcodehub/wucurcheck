const LOCK_PREFIX = "lock:";
const LOCK_TTL = 300; // 5分钟自动过期（注册最长时间）

export async function acquireLock(env, key) {
  const lockKey = `${LOCK_PREFIX}${key}`;
  const existing = await env.KV.get(lockKey);
  if (existing) return false;
  await env.KV.put(lockKey, Date.now().toString(), { expirationTtl: LOCK_TTL });
  return true;
}

export async function releaseLock(env, key) {
  await env.KV.delete(`${LOCK_PREFIX}${key}`);
}
