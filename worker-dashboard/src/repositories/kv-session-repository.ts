/**
 * KV-backed Session Repository.
 */

import { KV_PREFIX, TTL } from "../lib/constants.js";
import { log } from "../lib/log.js";

export class KvSessionRepository {
  constructor(private readonly kv: KVNamespace) {}

  async get(token: string): Promise<string | null> {
    if (!token) return null;
    return this.kv.get(`${KV_PREFIX.SESSION}${token}`);
  }

  async create(user: string): Promise<string> {
    const token = crypto.randomUUID();
    await this.kv.put(`${KV_PREFIX.SESSION}${token}`, user, { expirationTtl: TTL.SESSION });
    log.info("session_created", { user });
    return token;
  }

  async delete(token: string): Promise<void> {
    if (!token) return;
    await this.kv.delete(`${KV_PREFIX.SESSION}${token}`);
  }
}
