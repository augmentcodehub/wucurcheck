import { log } from "./lib/log.js";

const SESSION_COOKIE = "session";
const SESSION_TTL = 86400 * 7;

function timingSafeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

export async function authMiddleware(request, env) {
  const valid = await hasValidSession(request, env);
  if (!valid) return redirect(request);
  return null;
}

export async function hasValidSession(request, env) {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(/session=([^;]+)/);
  if (!match) return false;
  if (!env?.KV?.get) return false;
  const stored = await env.KV.get(`session:${match[1]}`);
  return Boolean(stored);
}

export async function getSessionUser(request, env) {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(/session=([^;]+)/);
  if (!match) return null;
  return env.KV.get(`session:${match[1]}`);
}

export async function handleLogin(env, request) {
  if (!request) {
    return html(LOGIN_HTML);
  }

  const form = await request.formData();
  const user = form.get("user") || "";
  const pass = form.get("pass") || "";

  // 从 KV 读用户表，没有则用环境变量的 admin
  const kvUser = await env.KV.get(`user:${user}`, "json");
  let valid = false;
  if (kvUser) {
    valid = timingSafeEqual(pass, kvUser.password || "");
  } else if (timingSafeEqual(user, env.ADMIN_USER || "admin")) {
    const kvPass = await env.KV.get("config:admin_pass");
    valid = timingSafeEqual(pass, kvPass || env.ADMIN_PASS || "");
  }

  if (!valid) {
    log.warn("login failed", { user });
    return html(LOGIN_HTML.replace("<!--ERR-->", '<div class="alert alert-error mt-4">用户名或密码错误</div>'), 401);
  }

  const token = crypto.randomUUID();
  await env.KV.put(`session:${token}`, user, { expirationTtl: SESSION_TTL });
  log.info("login success", { user });

  const isLocal = new URL(request.url).hostname === "localhost";
  const cookieFlags = isLocal
    ? `Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_TTL}`
    : `Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_TTL}`;

  return new Response(null, {
    status: 302,
    headers: {
      Location: "/",
      "Set-Cookie": `${SESSION_COOKIE}=${token}; ${cookieFlags}`,
    },
  });
}

export function handleLogout() {
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/login",
      "Set-Cookie": `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; Max-Age=0`,
    },
  });
}

function redirect(request) {
  return Response.redirect(new URL("/login", request.url).toString(), 302);
}

function html(body, status = 200) {
  return new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8" } });
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
