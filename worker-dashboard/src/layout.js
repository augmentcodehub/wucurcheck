/**
 * Layout renderer — loads Mustache template and renders full page HTML.
 */

import Mustache from "mustache";
import layoutTemplate from "./templates/layout.mustache";

const THEMES = [
  "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
  "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden",
  "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black",
  "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade",
  "night", "coffee", "winter", "dim", "nord", "sunset", "caramellatte",
  "abyss", "silk",
];

/**
 * Render a full page response.
 * @param {string} title - Page title
 * @param {string} content - Inner HTML content (unescaped)
 * @returns {Response}
 */
export function layout(title, content) {
  const html = Mustache.render(layoutTemplate, { title, content, themes: THEMES });
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}
