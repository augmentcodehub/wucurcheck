/** Island: Register form preview + validation + submit */
const MAX_TOTAL = 20;
const COMBO_EXAMPLES = { "fruit+animal": ["fig0cat", "plum3fox", "kiwi5owl"], "plant+animal": ["oak2fox", "fern7bee", "ivy4cat"], "fruit+metal": ["fig0tin", "plum3gold", "lime5iron"], "plant+metal": ["oak2tin", "fern7gold", "ivy4iron"] };

function updatePreview() {
  const domain = document.getElementById("reg-domain").value;
  const pwd = document.getElementById("reg-password").value;
  const combo = document.getElementById("reg-prefix").value;
  const maxLocal = MAX_TOTAL - domain.length - 2;
  const samples = COMBO_EXAMPLES[combo] || COMBO_EXAMPLES["fruit+animal"];
  const sample = samples[0] + "@" + domain;
  document.getElementById("reg-preview").textContent = sample + "  (共" + sample.length + "字符)";
  const msgs = [];
  if (maxLocal < 6) msgs.push("⚠️ 域名太长！用户名只剩 " + maxLocal + " 字符");
  else if (maxLocal < 9) msgs.push("⚠️ 域名较长，仅支持短单词组合");
  else msgs.push("✅ 可用 " + maxLocal + " 字符，组合充足");
  if (pwd.length < 8) msgs.push("⚠️ 密码至少 8 位");
  document.getElementById("reg-length").innerHTML = msgs.join("<br>");
  const ok = maxLocal >= 6 && pwd.length >= 8;
  document.getElementById("reg-submit").disabled = !ok;
  document.getElementById("reg-submit").classList.toggle("btn-disabled", !ok);
}
setTimeout(updatePreview, 0);

async function doRegister(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading", "loading-spinner");
  const body = { action: "register", inputs: { count: document.getElementById("reg-count").value, email_prefix: document.getElementById("reg-prefix").value, email_domain: document.getElementById("reg-domain").value, password: document.getElementById("reg-password").value } };
  try {
    const r = await fetch("/api/trigger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json();
    document.getElementById("register-modal").close();
    showToast(d.success ? "✅ 已触发注册 " + body.inputs.count + " 个账号" : "❌ " + (d.error_code || "FAILED"), d.success);
  } finally { btn.classList.remove("loading", "loading-spinner"); }
}

async function doRegisterKiro(event) {
  const btn = event.currentTarget;
  btn.classList.add("loading", "loading-spinner");
  const method = document.getElementById("kiro-method").value;
  const action = method === "api" ? "register_kiro_api" : "register_kiro";
  const body = { action, inputs: { count: document.getElementById("kiro-count").value, email_domain: document.getElementById("kiro-domain").value, proxy: document.getElementById("kiro-proxy").value } };
  try {
    const r = await fetch("/api/trigger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json();
    document.getElementById("register-kiro-modal").close();
    showToast(d.success ? "✅ 已触发注册 " + body.inputs.count + " 个 Kiro 账号 (" + method + ")" : "❌ " + (d.error || d.error_code || "FAILED"), d.success);
  } finally { btn.classList.remove("loading", "loading-spinner"); }
}
