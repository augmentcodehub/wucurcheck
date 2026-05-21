/**
 * Static file server — serves island JS files.
 *
 * Files are imported as text at build time (zero runtime I/O).
 * Served with Cache-Control for edge caching.
 */

import { log } from "./log.js";
import pagination from "../islands/pagination.island.js";
import bulkActions from "../islands/bulk-actions.island.js";
import registerForm from "../islands/register-form.island.js";
import settings from "../islands/settings.island.js";

/** @type {Record<string, string>} */
const FILES = {
  "/static/islands/pagination.js": pagination,
  "/static/islands/bulk-actions.js": bulkActions,
  "/static/islands/register-form.js": registerForm,
  "/static/islands/settings.js": settings,
};

/**
 * Serve a static file by path.
 * @param {string} path
 * @returns {Response}
 */
export function serveStatic(path) {
  const content = FILES[path];
  if (!content) {
    log.warn("static_not_found", { path });
    return new Response("Not Found", { status: 404 });
  }
  return new Response(content, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
