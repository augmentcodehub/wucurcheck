/**
 * Checkin Failure Log — 签到失败记录持久化
 *
 * KV Schema:
 *   Key:   "fail_log:{username}:{YYYY-MM-DD}"
 *   Value: { username, date, reason, created_at }
 *
 * 每个账号每天最多一条记录（同日重复失败会覆盖）。
 */

import { log } from "./log.js";
import { KV_PREFIX } from "./constants.js";

const PREFIX = KV_PREFIX.FAIL_LOG;

/**
 * @typedef {Object} FailLogEntry
 * @property {string} username
 * @property {string} date      - ISO date (YYYY-MM-DD)
 * @property {string} reason    - 失败原因描述
 * @property {string} created_at
 */

/**
 * 写入一条签到失败记录。
 * @param {Object} env - Worker env bindings
 * @param {string} username
 * @param {{ date: string, reason: string }} payload
 */
export async function writeFailLog(env, username, { date, reason }) {
  if (!username || !date) {
    log.warn("fail_log_skip", { username, date, reason: "missing_params" });
    return;
  }

  const key = `${PREFIX}${username}:${date}`;
  /** @type {FailLogEntry} */
  const entry = {
    username,
    date,
    reason: reason || "未知错误",
    created_at: new Date().toISOString(),
  };

  await env.KV.put(key, JSON.stringify(entry));
  log.info("fail_log_written", { username, date });
}

/**
 * 查询某账号的所有失败记录（按日期倒序）。
 * @param {Object} env
 * @param {string} username
 * @returns {Promise<FailLogEntry[]>}
 */
export async function queryFailLogs(env, username) {
  if (!username) return [];

  const { keys } = await env.KV.list({ prefix: `${PREFIX}${username}:` });
  const entries = await Promise.all(
    keys.map((k) => env.KV.get(k.name, "json"))
  );

  return entries
    .filter(Boolean)
    .sort((a, b) => b.date.localeCompare(a.date));
}
