/**
 * GitHub Actions workflow dispatch — implements CIDispatcher.
 */

import { log } from "../lib/log.js";
import type { CIDispatcher, DispatchParams, DispatchResult } from "../types/index.js";

const WORKFLOW_MAP: Record<string, string> = {
  register: "register.yml",
  register_kiro: "register_kiro.yml",
  register_kiro_api: "register_kiro_api.yml",
  checkin_unchecked: "checkin_batch.yml",
  kiro_refresh: "kiro_refresh.yml",
  kiro_refresh_all: "kiro_refresh.yml",
};

export class GitHubDispatcher implements CIDispatcher {
  readonly platform = "github";

  constructor(private readonly env: Env) {}

  async trigger({ action, target, callbackUrl, inputs }: DispatchParams): Promise<DispatchResult> {
    const repo = this.env.GITHUB_REPO;
    const token = this.env.GITHUB_TOKEN;
    if (!repo || !token) {
      return { ok: false, error: "GITHUB_REPO or GITHUB_TOKEN not configured" };
    }

    const workflow = WORKFLOW_MAP[action] || (this.env.GITHUB_WORKFLOW || "checkin.yml");
    const workflowInputs = this.buildInputs(action, target, callbackUrl, inputs);
    const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;

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
        log.error("github_dispatch_failed", { status: resp.status });
        return { ok: false, error: `GitHub ${resp.status}: ${text.substring(0, 100)}` };
      }

      log.info("github_triggered", { action, workflow, target });
      return { ok: true, meta: { workflow: workflow.replace(".yml", ""), dispatch_id: crypto.randomUUID().slice(0, 8) } };
    } catch (e) {
      const msg = e instanceof Error ? e.message : "unknown";
      log.error("github_fetch_error", { error: msg });
      return { ok: false, error: msg };
    }
  }

  private buildInputs(action: string, target?: string, callbackUrl?: string, inputs?: Record<string, string>): Record<string, string> {
    if (action === "register") {
      return { count: inputs?.count || "10", email_prefix: inputs?.email_prefix || "fruit+animal", email_domain: inputs?.email_domain || "qq.com", password: inputs?.password || "", callback_url: callbackUrl || "" };
    }
    if (action === "register_kiro" || action === "register_kiro_api") {
      return { count: inputs?.count || "1", email_domain: inputs?.email_domain || "ouraihub.com", proxy: inputs?.proxy || "", callback_url: callbackUrl || "" };
    }
    if (action === "checkin_unchecked") {
      return { accounts_json: inputs?.accounts_json || "[]", callback_url: callbackUrl || "" };
    }
    if (action === "kiro_refresh" || action === "kiro_refresh_all") {
      return { target: target || "", callback_url: callbackUrl || "" };
    }
    return { action: action || "checkin", target: target || "", callback_url: callbackUrl || "" };
  }
}

/** Legacy function wrapper — delegates to GitHubDispatcher for backward compatibility */
export async function triggerWorkflow(env: Env, params: DispatchParams): Promise<DispatchResult & { workflow?: string; dispatch_id?: string }> {
  const dispatcher = new GitHubDispatcher(env);
  const result = await dispatcher.trigger(params);
  return {
    ...result,
    workflow: result.meta?.workflow as string | undefined,
    dispatch_id: result.meta?.dispatch_id as string | undefined,
  };
}
