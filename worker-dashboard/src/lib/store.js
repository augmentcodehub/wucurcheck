/**
 * KV Store — 账号数据的 CRUD 抽象
 * 所有 KV 操作集中在这里，页面层只调用 store 方法
 */

const PREFIX = "account:";

export async function listAccounts(env) {
  const list = await env.KV.list({ prefix: PREFIX });
  const accounts = [];
  for (const key of list.keys) {
    const val = await env.KV.get(key.name, "json");
    if (val) accounts.push({ id: key.name.slice(PREFIX.length), ...val });
  }
  return accounts;
}

export async function getAccount(env, username) {
  return env.KV.get(`${PREFIX}${username}`, "json");
}

export async function putAccount(env, username, data) {
  const existing = (await getAccount(env, username)) || {};
  const merged = { ...existing, ...data, username, updated_at: new Date().toISOString() };
  if (!merged.created_at) merged.created_at = merged.updated_at;
  await env.KV.put(`${PREFIX}${username}`, JSON.stringify(merged));
  return merged;
}

export async function deleteAccount(env, username) {
  await env.KV.delete(`${PREFIX}${username}`);
}
