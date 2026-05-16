import { log } from "../lib/log.js";
import { triggerWorkflow } from "../lib/github.js";
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

  const target = body.target || url.searchParams.get("target") || "";
  const workflow = body.workflow || url.searchParams.get("workflow") || "checkin";
  const defaulted = !body.workflow && !url.searchParams.get("workflow");

  if (!env.GITHUB_REPO || !env.GITHUB_TOKEN) {
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }

  const callbackUrl = new URL("/callback", request.url).toString();
  const result = await triggerWorkflow(env, { action: "checkin", target, callbackUrl, workflow });
  if (!result.ok) {
    return Response.json({ success: false, error_code: "DISPATCH_FAILED" }, { status: 502 });
  }
  return Response.json(
    {
      success: true,
      workflow: result.workflow,
      defaulted: result.defaulted,
      dispatch_id: result.dispatch_id,
    },
    { status: 200 }
  );
}
