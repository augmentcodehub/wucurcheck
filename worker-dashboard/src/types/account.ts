/** Account entity — represents a managed account in KV. */

export type AccountStatus = "active" | "failed" | "pending" | "suspended";
export type AccountPlatform = "wucur" | "kiro";

export interface Account {
  username: string;
  password: string;
  platform: AccountPlatform;
  status: AccountStatus;
  balance?: string;
  checkin_time?: string;
  last_result?: string;
  created_at: string;
  updated_at: string;
  // Kiro-specific fields
  access_token?: string;
  refresh_token?: string;
  client_id?: string;
  client_secret?: string;
  token_expires_at?: string;
  last_refresh_at?: string;
  last_refresh_error?: string | null;
  subscription_type?: string;
  usage_current?: number;
  usage_limit?: number;
  days_remaining?: number;
  sso_token?: string;
  auth_method?: string;
  idp?: string;
  region?: string;
  register_source?: string;
}

/** Repository interface for account persistence. */
export interface AccountRepository {
  list(): Promise<Account[]>;
  get(username: string): Promise<Account | null>;
  put(username: string, data: Partial<Account>): Promise<Account>;
  delete(username: string): Promise<void>;
}
