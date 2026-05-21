/**
 * Layout renderer — renders full page HTML with Mustache template.
 */

import Mustache from "mustache";
import { CONTENT_TYPE } from "./constants.js";
import layoutTemplate from "../templates/layout.mustache";

const THEMES = [
  "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
  "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden",
  "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black",
  "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade",
  "night", "coffee", "winter", "dim", "nord", "sunset", "caramellatte",
  "abyss", "silk",
] as const;

export function layout(title: string, content: string): Response {
  const html = Mustache.render(layoutTemplate, { title, content, themes: [...THEMES] });
  return new Response(html, { headers: { "Content-Type": CONTENT_TYPE.HTML } });
}
