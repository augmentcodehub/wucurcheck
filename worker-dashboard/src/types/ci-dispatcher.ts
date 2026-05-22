/** CI Dispatcher — common interface for GitHub Actions / GitLab CI / future platforms. */

export interface DispatchParams {
  action: string;
  target?: string;
  callbackUrl?: string;
  inputs?: Record<string, string>;
}

export interface DispatchResult {
  ok: boolean;
  error?: string;
  /** Platform-specific metadata */
  meta?: Record<string, unknown>;
}

export interface CIDispatcher {
  readonly platform: string;
  trigger(params: DispatchParams): Promise<DispatchResult>;
}
