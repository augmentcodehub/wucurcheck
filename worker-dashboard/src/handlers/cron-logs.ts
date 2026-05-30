/** Log APIs — backed by D1 */

import { D1LogRepository } from "../repositories/d1-log-repository.js";
import { Res } from "../lib/response.js";

export async function apiCronLogs(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const date = url.searchParams.get("date") || new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
  const repo = new D1LogRepository(env.DB);
  const logs = await repo.query("checkin", date);
  return Res.json(logs);
}

export async function apiRegisterLogs(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const date = url.searchParams.get("date") || new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
  const repo = new D1LogRepository(env.DB);
  const logs = await repo.query("register", date);
  return Res.json(logs);
}

export async function apiFailLogs(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const date = url.searchParams.get("date") || new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
  const repo = new D1LogRepository(env.DB);
  const logs = await repo.query("error", date);
  return Res.json(logs);
}
