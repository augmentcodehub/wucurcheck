/**
 * KV-backed Account Repository.
 */

import { KV_PREFIX } from "../lib/constants.js";
import { log } from "../lib/log.js";
import type { Account, AccountRepository } from "../types/index.js";

export class KvAccountRepository implements AccountRepository {
  constructor(private readonly kv: KVNamespace) {}

  async list(): Promise<Account[]> {
    const allKeys: KVNamespaceListKey<unknown>[] = [];
    let cursor: string | undefined;
    do {
      const result = await this.kv.list({ prefix: KV_PREFIX.ACCOUNT, cursor });
      allKeys.push(...result.keys);
      cursor = result.list_complete ? undefined : result.cursor;
    } while (cursor);

    const BATCH = 6;
    const values: (Account | null)[] = [];
    for (let i = 0; i < allKeys.length; i += BATCH) {
      const batch = await Promise.all(
        allKeys.slice(i, i + BATCH).map((k) => this.kv.get<Account>(k.name, "json"))
      );
      values.push(...batch);
    }
    return values.filter((v): v is Account => v !== null);
  }

  async get(username: string): Promise<Account | null> {
    if (!username) return null;
    return this.kv.get<Account>(`${KV_PREFIX.ACCOUNT}${username}`, "json");
  }

  async put(username: string, data: Partial<Account>): Promise<Account> {
    if (!username) {
      log.error("put_account_no_username");
      throw new Error("username is required");
    }

    const existing = (await this.get(username)) ?? ({} as Partial<Account>);
    const now = new Date().toISOString();
    const merged: Account = {
      ...existing,
      ...data,
      username,
      updated_at: now,
      created_at: existing.created_at ?? now,
    } as Account;

    await this.kv.put(`${KV_PREFIX.ACCOUNT}${username}`, JSON.stringify(merged));
    log.info("account_updated", { username });
    return merged;
  }

  async delete(username: string): Promise<void> {
    if (!username) return;
    await this.kv.delete(`${KV_PREFIX.ACCOUNT}${username}`);
    log.info("account_deleted", { username });
  }
}
