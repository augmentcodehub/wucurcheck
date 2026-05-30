/** Cron execution logs + failure logs API */

import { KV_PREFIX } from "../lib/constants.js";
import { Res } from "../lib/response.js";

interface CronLogEntry {
  time: string;
  count: number;
  accounts: string[];
  ok: boolean;
  error: string | null;
}

interface FailLogEntry {
  username: string;
  date: string;
  reason: string;
  created_at: string;
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

export async function apiFailLogs(_request: Request, env: Env): Promise<Response> {
  const { keys } = await env.KV.list({ prefix: KV_PREFIX.FAIL_LOG, limit: 50 });
  const logs: FailLogEntry[] = [];

  for (const key of keys.reverse()) {
    const entry = await env.KV.get<FailLogEntry>(key.name, "json");
    if (entry) logs.push(entry);
  }

  return Res.json(logs);
}

export async function apiRegisterLogs(_request: Request, env: Env): Promise<Response> {
  const { keys } = await env.KV.list({ prefix: KV_PREFIX.REGISTER_LOG, limit: 30 });
  const logs: Array<{ time: string; username: string; platform: string; status: string; error: string | null }> = [];

  for (const key of keys.reverse()) {
    const entry = await env.KV.get<typeof logs[number]>(key.name, "json");
    if (entry) logs.push(entry);
  }

  return Res.json(logs);
}
