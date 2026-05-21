/** Checkin failure log entry. */

export interface FailLogEntry {
  username: string;
  date: string; // YYYY-MM-DD
  reason: string;
  created_at: string;
}

/** Repository interface for failure log persistence. */
export interface FailLogRepository {
  write(username: string, payload: { date: string; reason: string }): Promise<void>;
  query(username: string): Promise<FailLogEntry[]>;
}
