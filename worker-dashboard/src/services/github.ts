/**
 * GitHub Actions workflow dispatch service.
 */

import { log } from "../lib/log.js";

interface DispatchParams {
  action: string;
  target?: string;
  callbackUrl?: string;
  inputs?: Record<string, string>;
}

interface DispatchResult {
  ok: boolean;
  workflow?: string;
  dispatch_id?: string;
  error?: string;
}

export async function triggerWorkflow(env: Env, { action, target, callbackUrl, inputs }: DispatchParams): Promise<DispatchResult> {
  const repo = env.GITHUB_REPO;
  const token = (env as Record<string, unknown>).GITHUB_TOKEN as string | undefined;

  const workflow = action === "register"
    ? "register.yml"
    : action === "register_kiro"
    ? "register_kiro.yml"
    : action === "checkin_unchecked"
    ? "checkin_batch.yml"
    : action === "kiro_refresh" || action === "kiro_refresh_all"
    ? "kiro_refresh.yml"
    : (env.GITHUB_WORKFLOW || "checkin.yml");

  if (!repo || !token) {
    log.error("github_not_configured");
    return { ok: false, error: "GITHUB_REPO or GITHUB_TOKEN not configured" };
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;

  let workflowInputs: Record<string, string>;
  if (action === "register") {
    workflowInputs = {
      count: inputs?.count || "10",
      email_prefix: inputs?.email_prefix || "fruit+animal",
      email_domain: inputs?.email_domain || "qq.com",
      password: inputs?.password || "",
      callback_url: callbackUrl || "",
    };
  } else if (action === "register_kiro") {
    workflowInputs = {
      count: inputs?.count || "1",
      email_domain: inputs?.email_domain || "ouraihub.com",
      proxy: inputs?.proxy || "",
      callback_url: callbackUrl || "",
    };
  } else if (action === "checkin_unchecked") {
    workflowInputs = {
      accounts_json: inputs?.accounts_json || "[]",
      callback_url: callbackUrl || "",
    };
  } else if (action === "kiro_refresh" || action === "kiro_refresh_all") {
    workflowInputs = {
      target: target || "",
      callback_url: callbackUrl || "",
    };
  } else {
    workflowInputs = { action: action || "checkin", target: target || "", callback_url: callbackUrl || "" };
  }

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "worker-dashboard",
      },
      body: JSON.stringify({ ref: "main", inputs: workflowInputs }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("dispatch_failed", { status: resp.status, body: text.substring(0, 200) });
      return { ok: false, error: `GitHub ${resp.status}` };
    }

    log.info("workflow_triggered", { action, workflow, target });
    return { ok: true, workflow: workflow.replace(".yml", ""), dispatch_id: crypto.randomUUID().slice(0, 8) };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("github_fetch_error", { error: msg });
    return { ok: false, error: msg };
  }
}
