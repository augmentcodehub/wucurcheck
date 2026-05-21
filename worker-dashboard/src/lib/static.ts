/**
 * Static file server — serves island JS files.
 * Files imported as text at build time (zero runtime I/O).
 */

import { log } from "./log.js";
import { CONTENT_TYPE, TTL } from "./constants.js";
import pagination from "../islands/pagination.island.js";
import bulkActions from "../islands/bulk-actions.island.js";
import registerForm from "../islands/register-form.island.js";
import settings from "../islands/settings.island.js";

const FILES: Record<string, string> = {
  "/static/islands/pagination.js": pagination,
  "/static/islands/bulk-actions.js": bulkActions,
  "/static/islands/register-form.js": registerForm,
  "/static/islands/settings.js": settings,
};

export function serveStatic(path: string): Response {
  const content = FILES[path];
  if (!content) {
    log.warn("static_not_found", { path });
    return new Response("Not Found", { status: 404 });
  }
  return new Response(content, {
    headers: {
      "Content-Type": CONTENT_TYPE.JS,
      "Cache-Control": `public, max-age=${TTL.STATIC_CACHE}`,
    },
  });
}
