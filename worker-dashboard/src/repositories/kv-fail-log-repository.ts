/**
 * KV-backed Fail Log Repository.
 *
 * Key: "fail_log:{username}:{YYYY-MM-DD}"
 * Each account has at most one entry per day (overwrites on same day).
 */

import { KV_PREFIX } from "../lib/constants.js";
import { log } from "../lib/log.js";
import type { FailLogEntry, FailLogRepository } from "../types/index.js";

export class KvFailLogRepository implements FailLogRepository {
  constructor(private readonly kv: KVNamespace) {}

  async write(username: string, { date, reason }: { date: string; reason: string }): Promise<void> {
    if (!username || !date) {
      log.warn("fail_log_skip", { username, date, reason: "missing_params" });
      return;
    }

    const key = `${KV_PREFIX.FAIL_LOG}${username}:${date}`;
    const entry: FailLogEntry = {
      username,
      date,
      reason: reason || "未知错误",
      created_at: new Date().toISOString(),
    };

    await this.kv.put(key, JSON.stringify(entry));
    log.info("fail_log_written", { username, date });
  }

  async query(username: string): Promise<FailLogEntry[]> {
    if (!username) return [];

    const { keys } = await this.kv.list({ prefix: `${KV_PREFIX.FAIL_LOG}${username}:` });
    const entries = await Promise.all(
      keys.map((k) => this.kv.get<FailLogEntry>(k.name, "json"))
    );

    return entries
      .filter((v): v is FailLogEntry => v !== null)
      .sort((a, b) => b.date.localeCompare(a.date));
  }
}
