/**
 * GitHub Actions 触发封装
 */

import { log } from "./log.js";

export async function triggerWorkflow(env, { action, target, callbackUrl }) {
  const repo = env.GITHUB_REPO;
  const token = env.GITHUB_TOKEN;
  const workflow = env.GITHUB_WORKFLOW || "checkin.yml";
  const workflowName = "checkin";

  if (!repo || !token) {
    return { ok: false, error: "GITHUB_REPO or GITHUB_TOKEN not configured" };
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "worker-dashboard",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          action: action || "checkin",
          target: target || "",
          callback_url: callbackUrl || "",
        },
      }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      log.error("github dispatch failed", { status: resp.status, body: text.substring(0, 200) });
      return { ok: false, error: `GitHub ${resp.status}` };
    }

    log.info("workflow triggered", { action, target });
    return {
      ok: true,
      workflow: workflowName,
      defaulted: true,
      dispatch_id: "dispatch-placeholder",
    };
  } catch (e) {
    log.error("github fetch error", { error: e.message });
    return { ok: false, error: e.message };
  }
}
