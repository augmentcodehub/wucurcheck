/** Shared template helpers */

import type { AccountStatus } from "../types/index.js";

const STATUS_CLASS: Record<string, string> = {
  active: "badge-success",
  pending: "badge-warning",
  failed: "badge-error",
  expired: "badge-ghost",
};

export function badge(status: AccountStatus | string | undefined): string {
  const cls = STATUS_CLASS[status || ""] || "badge-ghost";
  return `<span class="badge badge-sm ${cls}">${esc(status || "unknown")}</span>`;
}

export function isToday(ts: string | undefined): boolean {
  if (!ts) return false;
  return new Date(ts).toDateString() === new Date().toDateString();
}

export function timeAgo(ts: string | undefined): string {
  if (!ts) return "-";
  const d = new Date(ts);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (diff < 60) return `${diff}分钟前`;
  if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
  return d.toLocaleDateString("zh-CN");
}

export function esc(s: string | undefined | null): string {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
