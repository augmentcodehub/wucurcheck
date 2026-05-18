/**
 * Layout system — daisyUI drawer sidebar + navbar
 * Usage: layout("Page Title", contentHTML, { env })
 */

export function layout(title, content, { nav = [] } = {}) {
  const navItems = [
    { href: "/", label: "📊 账号管理", icon: "" },
    ...nav,
  ];

  const menuHTML = navItems
    .map((n) => `<li><a href="${n.href}" class="text-base">${n.label}</a></li>`)
    .join("");

  return new Response(
    `<!DOCTYPE html>
<html data-theme="business">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} - Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/daisyui@5" rel="stylesheet" type="text/css"/>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body>
<script>var t=localStorage.getItem('theme');if(t){document.documentElement.setAttribute('data-theme',t);document.addEventListener('DOMContentLoaded',function(){var s=document.querySelector('.drawer-side select');if(s)s.value=t;});}</script>
<div class="drawer lg:drawer-open">
  <input id="drawer" type="checkbox" class="drawer-toggle"/>
  <div class="drawer-content flex flex-col">
    <!-- Navbar -->
    <div class="navbar bg-base-100 border-b border-base-300 lg:hidden">
      <label for="drawer" class="btn btn-ghost drawer-button">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
      </label>
      <span class="text-lg font-bold ml-2">${title}</span>
    </div>
    <!-- Content -->
    <main class="p-6 flex-1 bg-base-200 min-h-screen">
      ${content}
    </main>
  </div>
  <!-- Sidebar -->
  <div class="drawer-side">
    <label for="drawer" class="drawer-overlay"></label>
    <aside class="bg-base-100 w-64 min-h-screen border-r border-base-300 flex flex-col">
      <div class="p-4 border-b border-base-300">
        <h1 class="text-xl font-bold">⚡ Dashboard</h1>
      </div>
      <ul class="menu p-4 flex-1">${menuHTML}</ul>
      <div class="p-4 border-t border-base-300">
        <select class="select select-xs w-full mb-2" onchange="document.documentElement.setAttribute('data-theme',this.value);localStorage.setItem('theme',this.value)">
          <option value="business">Business</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="night">Night</option>
          <option value="dracula">Dracula</option>
          <option value="nord">Nord</option>
          <option value="dim">Dim</option>
          <option value="sunset">Sunset</option>
        </select>
        <a href="/logout" class="btn btn-ghost btn-sm w-full">退出登录</a>
      </div>
    </aside>
  </div>
</div>
</body></html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
