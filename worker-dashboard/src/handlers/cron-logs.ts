/** Cron execution logs API */

import { KV_PREFIX } from "../lib/constants.js";
import { Res } from "../lib/response.js";

interface CronLogEntry {
  time: string;
  count: number;
  accounts: string[];
  ok: boolean;
  error: string | null;
}

export async function apiCronLogs(_request: Request, env: Env): Promise<Response> {
  const { keys } = await env.KV.list({ prefix: KV_PREFIX.CRON_LOG, limit: 20 });
  const logs: CronLogEntry[] = [];

  for (const key of keys.reverse()) {
    const entry = await env.KV.get<CronLogEntry>(key.name, "json");
    if (entry) logs.push(entry);
  }

  return Res.json(logs);
}
