/** Shared template helpers */

export function badge(status) {
  const m = { active: "badge-success", pending: "badge-warning", failed: "badge-error", expired: "badge-ghost" };
  return `<span class="badge badge-sm ${m[status] || "badge-ghost"}">${esc(status || "unknown")}</span>`;
}

export function isToday(ts) {
  if (!ts) return false;
  return new Date(ts).toDateString() === new Date().toDateString();
}

export function timeAgo(ts) {
  if (!ts) return "-";
  const d = new Date(ts);
  const now = new Date();
  const diff = Math.floor((now - d) / 60000);
  if (diff < 60) return `${diff}分钟前`;
  if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
  return d.toLocaleDateString("zh-CN");
}

export function esc(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
