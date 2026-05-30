/** Logs page handler */

import Mustache from "mustache";
import { layout } from "../lib/layout.js";
import logsTemplate from "../templates/partials/logs.mustache";
import logsIsland from "../islands/logs.island.js";

export async function pageLogs(_request: Request, _env: Env): Promise<Response> {
  const today = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
  const html = Mustache.render(logsTemplate, { today });
  const content = html + `<script>${logsIsland}</script>`;
  return layout("执行日志", content);
}
