/** D1-backed log repository */

export interface LogEntry {
  id?: number;
  type: "checkin" | "register" | "error";
  time: string;
  username?: string;
  platform?: string;
  status?: string;
  message?: string;
  data?: string;
}

export class D1LogRepository {
  constructor(private readonly db: D1Database) {}

  async insert(entry: LogEntry): Promise<void> {
    await this.db.prepare(
      "INSERT INTO logs (type, time, username, platform, status, message, data) VALUES (?, ?, ?, ?, ?, ?, ?)"
    ).bind(entry.type, entry.time, entry.username || null, entry.platform || null, entry.status || null, entry.message || null, entry.data || null).run();
  }

  async query(type: string, date: string, limit = 50, offset = 0): Promise<LogEntry[]> {
    const result = await this.db.prepare(
      "SELECT * FROM logs WHERE type = ? AND time >= ? AND time < ? ORDER BY time DESC LIMIT ? OFFSET ?"
    ).bind(type, `${date}T00:00:00Z`, `${date}T23:59:59Z`, limit, offset).all<LogEntry>();
    return result.results;
  }

  async cleanup(days = 7): Promise<number> {
    const cutoff = new Date(Date.now() - days * 86400000).toISOString();
    const result = await this.db.prepare("DELETE FROM logs WHERE time < ?").bind(cutoff).run();
    return result.meta.changes;
  }
}
