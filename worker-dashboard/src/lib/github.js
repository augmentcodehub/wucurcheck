/**
 * GitHub Actions dispatch
 */

import { log } from "./log.js";

export async function triggerWorkflow(env, { action, target, callbackUrl, inputs }) {
  const repo = env.GITHUB_REPO;
  const token = env.GITHUB_TOKEN;

  // 根据 action 选择 workflow
  const workflow = action === "register"
    ? "register.yml"
    : action === "checkin_unchecked"
    ? "checkin_batch.yml"
    : (env.GITHUB_WORKFLOW || "checkin.yml");

  if (!repo || !token) {
    log.error("github_not_configured");
    return { ok: false, error: "GITHUB_REPO or GITHUB_TOKEN not configured" };
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;

  // 构建 inputs
  let workflowInputs;
  if (action === "register") {
    workflowInputs = {
      count: inputs?.count || "10",
      email_prefix: inputs?.email_prefix || "fruit+animal",
      email_domain: inputs?.email_domain || "qq.com",
      password: inputs?.password || "123Claude&Codex",
      callback_url: callbackUrl || "",
    };
  } else if (action === "checkin_unchecked") {
    workflowInputs = {
      accounts_json: inputs?.accounts_json || "[]",
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
    log.error("github_fetch_error", { error: e.message });
    return { ok: false, error: e.message };
  }
}
