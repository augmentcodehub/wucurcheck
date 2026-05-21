/**
 * Static file server — serves island JS files from /static/islands/*.js
 */

import pagination from "../islands/pagination.island.js";
import bulkActions from "../islands/bulk-actions.island.js";
import registerForm from "../islands/register-form.island.js";
import settings from "../islands/settings.island.js";

const FILES = {
  "/static/islands/pagination.js": pagination,
  "/static/islands/bulk-actions.js": bulkActions,
  "/static/islands/register-form.js": registerForm,
  "/static/islands/settings.js": settings,
};

export function serveStatic(path) {
  const content = FILES[path];
  if (!content) return new Response("Not Found", { status: 404 });
  return new Response(content, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
