/**
 * Authentication service — session-based auth with KV storage.
 */

import { log } from "../lib/log.js";
import { timingSafeEqual } from "../lib/crypto.js";
import { KV_PREFIX, KV_KEY, TTL, CONTENT_TYPE } from "../lib/constants.js";

const SESSION_COOKIE = "session";

export async function authMiddleware(request: Request, env: Env): Promise<Response | null> {
  const valid = await hasValidSession(request, env);
  if (!valid) return Response.redirect(new URL("/login", request.url).toString(), 302);
  return null;
}

export async function hasValidSession(request: Request, env: Env): Promise<boolean> {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(/session=([^;]+)/);
  if (!match?.[1]) return false;
  const stored = await env.KV.get(`${KV_PREFIX.SESSION}${match[1]}`);
  return Boolean(stored);
}

export async function getSessionUser(request: Request, env: Env): Promise<string | null> {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(/session=([^;]+)/);
  if (!match?.[1]) return null;
  return env.KV.get(`${KV_PREFIX.SESSION}${match[1]}`);
}

export async function handleLogin(env: Env, request?: Request): Promise<Response> {
  if (!request) {
    return new Response(LOGIN_HTML, { headers: { "Content-Type": CONTENT_TYPE.HTML } });
  }

  const form = await request.formData();
  const user = (form.get("user") as string) || "";
  const pass = (form.get("pass") as string) || "";

  let valid = false;
  const kvUser = await env.KV.get<{ password: string; role: string }>(`${KV_PREFIX.USER}${user}`, "json");
  if (kvUser) {
    valid = timingSafeEqual(pass, kvUser.password || "");
  } else if (timingSafeEqual(user, env.ADMIN_USER || "admin")) {
    const kvPass = await env.KV.get(KV_KEY.ADMIN_PASS);
    valid = timingSafeEqual(pass, kvPass || env.ADMIN_PASS || "");
  }

  if (!valid) {
    log.warn("login_failed", { user });
    return new Response(
      LOGIN_HTML.replace("<!--ERR-->", '<div class="alert alert-error mt-4">用户名或密码错误</div>'),
      { status: 401, headers: { "Content-Type": CONTENT_TYPE.HTML } }
    );
  }

  const token = crypto.randomUUID();
  await env.KV.put(`${KV_PREFIX.SESSION}${token}`, user, { expirationTtl: TTL.SESSION });
  log.info("login_success", { user });

  const isLocal = new URL(request.url).hostname === "localhost";
  const cookieFlags = isLocal
    ? `Path=/; HttpOnly; SameSite=Lax; Max-Age=${TTL.SESSION}`
    : `Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${TTL.SESSION}`;

  return new Response(null, {
    status: 302,
    headers: {
      Location: "/",
      "Set-Cookie": `${SESSION_COOKIE}=${token}; ${cookieFlags}`,
    },
  });
}

export function handleLogout(): Response {
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/login",
      "Set-Cookie": `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; Max-Age=0`,
    },
  });
}

const LOGIN_HTML = `<!DOCTYPE html>
<html data-theme="business">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login</title>
<link href="https://cdn.jsdelivr.net/npm/daisyui@5" rel="stylesheet" type="text/css"/>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="min-h-screen flex items-center justify-center bg-base-200">
<div class="card w-96 bg-base-100 shadow-xl">
<div class="card-body">
  <h2 class="card-title justify-center text-2xl">🔐 Dashboard</h2>
  <!--ERR-->
  <form method="POST" action="/login" class="mt-4">
    <fieldset class="fieldset">
      <label class="fieldset-label">用户名</label>
      <input name="user" type="text" class="input input-bordered w-full" required autofocus/>
      <label class="fieldset-label mt-3">密码</label>
      <input name="pass" type="password" class="input input-bordered w-full" required/>
    </fieldset>
    <button type="submit" class="btn btn-primary w-full mt-6">登录</button>
  </form>
</div>
</div>
</body></html>`;
