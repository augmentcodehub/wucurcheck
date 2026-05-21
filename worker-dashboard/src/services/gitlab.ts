/**
 * GitLab CI pipeline trigger service.
 */

import { log } from "../lib/log.js";

interface GitlabTriggerParams {
  callbackUrl?: string;
  inputs?: Record<string, string>;
}

interface GitlabTriggerResult {
  ok: boolean;
  pipeline_id?: number;
  error?: string;
}

export async function triggerGitlabPipeline(env: Env, { callbackUrl, inputs }: GitlabTriggerParams): Promise<GitlabTriggerResult> {
  const projectId = env.GITLAB_PROJECT_ID;
  const token = env.GITLAB_TRIGGER_TOKEN;

  if (!projectId || !token) {
    return { ok: false, error: "GitLab not configured" };
  }

  const variables: Record<string, string> = {
    EMAIL_DOMAIN: inputs?.email_domain || "ouraihub.com",
    COUNT: inputs?.count || "1",
    CALLBACK_URL: callbackUrl || "",
    CALLBACK_SECRET: env.CALLBACK_SECRET || "",
  };
  if (inputs?.proxy) variables.PROXY = inputs.proxy;
  if (inputs?.email_api_key) variables.EMAIL_API_KEY = inputs.email_api_key;

  const body: Record<string, unknown> = { token, ref: "main", variables };

  try {
    const resp = await fetch(
      `https://gitlab.com/api/v4/projects/${encodeURIComponent(projectId)}/trigger/pipeline`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );

    if (!resp.ok) {
      const text = await resp.text();
      log.error("gitlab_trigger_failed", { status: resp.status, body: text.substring(0, 200) });
      return { ok: false, error: `GitLab ${resp.status}` };
    }

    const data = await resp.json() as { id?: number };
    log.info("gitlab_pipeline_triggered", { pipeline_id: data.id });
    return { ok: true, pipeline_id: data.id };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "unknown";
    log.error("gitlab_fetch_error", { error: msg });
    return { ok: false, error: msg };
  }
}
