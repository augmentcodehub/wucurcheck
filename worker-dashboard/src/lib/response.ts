/**
 * Response factory — eliminates repetitive Response construction.
 */

import { CONTENT_TYPE } from "./constants.js";

export const Res = {
  html: (body: string): Response =>
    new Response(body, { headers: { "Content-Type": CONTENT_TYPE.HTML } }),

  json: (data: unknown, status = 200): Response =>
    Response.json(data, { status }),

  notFound: (): Response =>
    new Response("Not Found", { status: 404 }),

  error: (code: string, message: string, status = 400): Response =>
    Response.json({ success: false, error_code: code, error: message }, { status }),
} as const;
