/**
 * API action handlers — strategy pattern.
 *
 * Each action maps to a handler function.
 * Adding a new action = adding one entry to ACTION_HANDLERS.
 */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { triggerWorkflow } from "../lib/github.js";
import { acquireLock } from "../lib/trigger_lock.js";
import { hasValidSession } from "../auth.js";
import { listAccounts, deleteAccount, getAccount } from "../lib/store.js";

// ============ Action Handlers ============

async function handleDelete(target, _body, env, _request) {
  if (!target) return Response.json({ success: false, error_code: "MISSING_TARGET" }, { status: 400 });
  await deleteAccount(env, target);
  log.info("account_deleted", { target });
  return Response.json({ success: true, action: "delete", target });
}

async function handleDeleteAll(_target, _body, env, _request) {
  const accounts = await listAccounts(env);
  for (const a of accounts) await deleteAccount(env, a.username);
  log.info("all_accounts_deleted", { count: accounts.length });
  return Response.json({ success: true, action: "delete_all", count: accounts.length });
}

async function handleDeleteFailed(_target, _body, env, _request) {
  const accounts = await listAccounts(env);
  const failed = accounts.filter((a) => a.status === "failed");
  for (const a of failed) await deleteAccount(env, a.username);
  log.info("failed_accounts_deleted", { count: failed.length });
  return Response.json({ success: true, action: "delete_failed", count: failed.length });
}

async function handleCheckinUnchecked(_target, _body, env, request) {
  const accounts = await listAccounts(env);
  const today = new Date().toDateString();
  const unchecked = accounts
    .filter(
      (a) =>
        a.status === "active" &&
        (!a.platform || a.platform === "wucur") &&
        (!a.checkin_time || new Date(a.checkin_time).toDateString() !== today)
    )
    .map((a) => ({ username: a.username, password: a.password }));

  if (!unchecked.length) {
    return Response.json({ success: false, error_code: "NO_UNCHECKED", error: "所有账号今日已签到" }, { status: 400 });
  }

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, {
    action: "checkin_unchecked",
    target: "",
    callbackUrl,
    inputs: { accounts_json: JSON.stringify(unchecked) },
  });

  if (!result.ok) return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  return Response.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id, count: unchecked.length });
}

async function handleKiroRefreshAll(_target, _body, env, _request) {
  const { refreshAllKiroAccounts } = await import("../services/account_manager.js");
  const result = await refreshAllKiroAccounts(env);
  return Response.json({ success: true, ...result, count: result.total });
}

async function handleKiroRefresh(target, _body, env, _request) {
  if (!target) return Response.json({ success: false, error_code: "MISSING_TARGET" }, { status: 400 });
  const { refreshSingleAccount } = await import("../services/account_manager.js");
  const account = await getAccount(env, target);
  if (!account) return Response.json({ success: false, error_code: "NOT_FOUND" }, { status: 404 });
  const result = await refreshSingleAccount(env, account);
  return Response.json({ success: result.success, error: result.error });
}

// ============ Local Actions (no GitHub dispatch needed) ============

const LOCAL_ACTIONS = {
  delete: handleDelete,
  delete_all: handleDeleteAll,
  delete_failed: handleDeleteFailed,
  checkin_unchecked: handleCheckinUnchecked,
  kiro_refresh_all: handleKiroRefreshAll,
  kiro_refresh: handleKiroRefresh,
};

// ============ Entry Point ============

export async function apiTrigger(request, env) {
  const url = new URL(request.url);
  let body = {};
  try {
    if (request.method !== "GET") body = await request.json();
  } catch {
    return Response.json({ success: false, error_code: "INVALID_PAYLOAD" }, { status: 400 });
  }

  // Auth check
  const token = body.token || url.searchParams.get("token") || request.headers.get("x-worker-token") || "";
  const expected = env.WORKER_SECRET || env.CALLBACK_SECRET || "";
  const sessionOk = await hasValidSession(request, env);
  if (!sessionOk && (!expected || !timingSafeEqual(token, expected))) {
    return Response.json({ success: false, error_code: "AUTH_FAILED" }, { status: 401 });
  }

  const action = body.action || url.searchParams.get("action") || "checkin";
  const target = body.target || url.searchParams.get("target") || "";

  // Local actions — handled directly, no GitHub dispatch
  const localHandler = LOCAL_ACTIONS[action];
  if (localHandler) {
    return localHandler(target, body, env, request);
  }

  // GitHub dispatch actions — need repo + token configured
  if (!env.GITHUB_REPO || !env.GITHUB_TOKEN) {
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }

  // Lock protection
  const lockKey = `${action}:${target || "_all"}`;
  const acquired = await acquireLock(env, lockKey);
  if (!acquired) {
    log.info("trigger_in_progress", { action, target });
    return Response.json({ success: false, error_code: "IN_PROGRESS", error: "上一个任务还在执行中，请稍后再试" }, { status: 409 });
  }

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, {
    action,
    target,
    callbackUrl,
    inputs: body.inputs || (body.account_json ? { account_json: body.account_json } : undefined),
  });

  if (!result.ok) {
    await env.KV.delete(`lock:${lockKey}`);
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }

  return Response.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id });
}
