/**
 * GitLab CI pipeline trigger — implements CIDispatcher.
 */

import { log } from "../lib/log.js";
import type { CIDispatcher, DispatchParams, DispatchResult } from "../types/index.js";

export class GitLabDispatcher implements CIDispatcher {
  readonly platform = "gitlab";

  constructor(private readonly env: Env) {}

  async trigger({ callbackUrl, inputs }: DispatchParams): Promise<DispatchResult> {
    const projectId = this.env.GITLAB_PROJECT_ID;
    const token = this.env.GITLAB_TRIGGER_TOKEN;
    if (!projectId || !token) {
      return { ok: false, error: "GitLab not configured" };
    }

    const variables: Record<string, string> = {
      EMAIL_DOMAIN: inputs?.email_domain || "ouraihub.com",
      COUNT: inputs?.count || "1",
      CALLBACK_URL: callbackUrl || "",
      CALLBACK_SECRET: this.env.CALLBACK_SECRET || "",
    };
    if (inputs?.proxy) variables.PROXY = inputs.proxy;
    if (inputs?.email_api_key) variables.EMAIL_API_KEY = inputs.email_api_key;

    const body = new FormData();
    body.append("token", token);
    body.append("ref", "main");
    for (const [k, v] of Object.entries(variables)) {
      body.append(`variables[${k}]`, v);
    }

    try {
      const resp = await fetch(
        `https://gitlab.com/api/v4/projects/${encodeURIComponent(projectId)}/trigger/pipeline`,
        { method: "POST", body }
      );

      if (!resp.ok) {
        const text = await resp.text();
        log.error("gitlab_trigger_failed", { status: resp.status });
        return { ok: false, error: `GitLab ${resp.status}: ${text.substring(0, 100)}` };
      }

      const data = await resp.json() as { id?: number };
      log.info("gitlab_triggered", { pipeline_id: data.id });
      return { ok: true, meta: { pipeline_id: data.id } };
    } catch (e) {
      const msg = e instanceof Error ? e.message : "unknown";
      log.error("gitlab_fetch_error", { error: msg });
      return { ok: false, error: msg };
    }
  }
}

/** Legacy function wrapper for backward compatibility */
export async function triggerGitlabPipeline(env: Env, params: DispatchParams): Promise<DispatchResult> {
  return new GitLabDispatcher(env).trigger(params);
}
