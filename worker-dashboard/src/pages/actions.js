import { log } from "../lib/log.js";
import { triggerWorkflow } from "../lib/github.js";
import { acquireLock } from "../lib/trigger_lock.js";
import { hasValidSession } from "../auth.js";

export async function apiTrigger(request, env) {
  const url = new URL(request.url);
  let body = {};
  try {
    if (request.method !== "GET") body = await request.json();
  } catch {
    return Response.json({ success: false, error_code: "INVALID_PAYLOAD" }, { status: 400 });
  }

  const token = body.token || url.searchParams.get("token") || request.headers.get("x-worker-token") || "";
  const expected = env.WORKER_SECRET || env.CALLBACK_SECRET || "";
  const sessionOk = await hasValidSession(request, env);
  if (!sessionOk && (!expected || token !== expected)) {
    return Response.json({ success: false, error_code: "AUTH_FAILED" }, { status: 401 });
  }

  const action = body.action || url.searchParams.get("action") || "checkin";
  const target = body.target || url.searchParams.get("target") || "";

  // 本地操作：删除不需要走 GitHub
  if (action === "delete" && target) {
    const { deleteAccount } = await import("../lib/store.js");
    await deleteAccount(env, target);
    log.info("account_deleted", { target });
    return Response.json({ success: true, action, target });
  }

  // 批量删除
  if (action === "delete_all") {
    const { listAccounts, deleteAccount } = await import("../lib/store.js");
    const accounts = await listAccounts(env);
    for (const a of accounts) await deleteAccount(env, a.username);
    log.info("all_accounts_deleted", { count: accounts.length });
    return Response.json({ success: true, action, count: accounts.length });
  }

  // 删除失败的
  if (action === "delete_failed") {
    const { listAccounts, deleteAccount } = await import("../lib/store.js");
    const accounts = await listAccounts(env);
    const failed = accounts.filter(a => a.status === "failed");
    for (const a of failed) await deleteAccount(env, a.username);
    log.info("failed_accounts_deleted", { count: failed.length });
    return Response.json({ success: true, action, count: failed.length });
  }

  // 批量签到未签到的：从 KV 读取未签到账号传给 workflow
  if (action === "checkin_unchecked") {
    const { listAccounts } = await import("../lib/store.js");
    const accounts = await listAccounts(env);
    const today = new Date().toDateString();
    const unchecked = accounts
      .filter(a => a.status === "active" && (!a.checkin_time || new Date(a.checkin_time).toDateString() !== today))
      .map(a => ({ username: a.username, password: a.password }));
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

  if (!env.GITHUB_REPO || !env.GITHUB_TOKEN) {
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }

  // 锁保护：同一 action+target 未完成时不重复触发
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
    // 触发失败，释放锁允许重试
    await env.KV.delete(`lock:${lockKey}`);
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }
  return Response.json({ success: true, workflow: result.workflow, dispatch_id: result.dispatch_id });
}
