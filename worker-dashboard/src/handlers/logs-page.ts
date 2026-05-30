/** Logs sub-pages handler */

import Mustache from "mustache";
import { layout } from "../lib/layout.js";
import checkinTemplate from "../templates/partials/logs-checkin.mustache";
import registerTemplate from "../templates/partials/logs-register.mustache";
import errorsTemplate from "../templates/partials/logs-errors.mustache";

const today = () => new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);

const CHECKIN_SCRIPT = `<script>
function bjTime(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return String(t.getUTCMonth()+1).padStart(2,'0')+'/'+String(t.getUTCDate()).padStart(2,'0')+' '+String(t.getUTCHours()).padStart(2,'0')+':'+String(t.getUTCMinutes()).padStart(2,'0');}
function bjDate(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return t.getUTCFullYear()+'-'+String(t.getUTCMonth()+1).padStart(2,'0')+'-'+String(t.getUTCDate()).padStart(2,'0');}
async function loadLogs(){var date=document.getElementById("log-date").value;try{var r=await fetch("/api/cron-logs");var logs=await r.json();logs=logs.filter(function(l){return bjDate(l.time)===date;});var el=document.getElementById("log-list");if(!logs.length){el.innerHTML='<span class="text-base-content/50">当日无记录</span>';return;}el.innerHTML=logs.map(function(l){var icon=l.ok?'✅':'❌';var accts=l.accounts.map(function(a){return'<span class="badge badge-xs badge-ghost">'+a+'</span>';}).join(' ');return'<div class="bg-base-200 rounded p-3"><div class="flex gap-2 items-center mb-2"><span>'+icon+'</span><span class="font-mono text-xs">'+bjTime(l.time)+'</span><span class="font-semibold">签到 '+l.count+' 个</span>'+(l.error?'<span class="text-error text-xs">'+l.error+'</span>':'')+'</div><div class="flex flex-wrap gap-1">'+accts+'</div></div>';}).join('');}catch(e){document.getElementById("log-list").innerHTML='<span class="text-error">加载失败</span>';}}
loadLogs();
</script>`;

const REGISTER_SCRIPT = `<script>
function bjTime(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return String(t.getUTCMonth()+1).padStart(2,'0')+'/'+String(t.getUTCDate()).padStart(2,'0')+' '+String(t.getUTCHours()).padStart(2,'0')+':'+String(t.getUTCMinutes()).padStart(2,'0');}
function bjDate(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return t.getUTCFullYear()+'-'+String(t.getUTCMonth()+1).padStart(2,'0')+'-'+String(t.getUTCDate()).padStart(2,'0');}
async function loadLogs(){var date=document.getElementById("log-date").value;try{var r=await fetch("/api/register-logs");var logs=await r.json();logs=logs.filter(function(l){return bjDate(l.time)===date;});var el=document.getElementById("log-list");if(!logs.length){el.innerHTML='<span class="text-base-content/50">当日无记录</span>';return;}el.innerHTML=logs.map(function(l){var icon=l.status==='active'?'✅':'❌';var platform=l.platform==='kiro'?'<span class="badge badge-xs badge-info">Kiro</span>':'<span class="badge badge-xs badge-warning">Wucur</span>';return'<div class="flex gap-2 items-center bg-base-200 rounded px-3 py-2"><span>'+icon+'</span><span class="font-mono text-xs">'+bjTime(l.time)+'</span>'+platform+'<span class="badge badge-sm badge-ghost">'+l.username+'</span>'+(l.error?'<span class="text-error text-xs">'+l.error+'</span>':'')+'</div>';}).join('');}catch(e){document.getElementById("log-list").innerHTML='<span class="text-error">加载失败</span>';}}
loadLogs();
</script>`;

const ERRORS_SCRIPT = `<script>
function bjTime(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return String(t.getUTCMonth()+1).padStart(2,'0')+'/'+String(t.getUTCDate()).padStart(2,'0')+' '+String(t.getUTCHours()).padStart(2,'0')+':'+String(t.getUTCMinutes()).padStart(2,'0');}
function bjDate(iso){var t=new Date(new Date(iso).getTime()+8*3600000);return t.getUTCFullYear()+'-'+String(t.getUTCMonth()+1).padStart(2,'0')+'-'+String(t.getUTCDate()).padStart(2,'0');}
async function loadLogs(){var date=document.getElementById("log-date").value;try{var r=await fetch("/api/fail-logs");var logs=await r.json();logs=logs.filter(function(l){return bjDate(l.created_at)===date;});var el=document.getElementById("log-list");if(!logs.length){el.innerHTML='<span class="text-base-content/50">当日无异常</span>';return;}el.innerHTML=logs.map(function(l){return'<div class="flex gap-2 items-center bg-error/10 rounded px-3 py-2"><span class="font-mono text-xs">'+bjTime(l.created_at)+'</span><span class="badge badge-sm badge-ghost">'+(l.username||'')+'</span><span class="text-error text-sm">'+(l.reason||'')+'</span></div>';}).join('');}catch(e){document.getElementById("log-list").innerHTML='<span class="text-error">加载失败</span>';}}
loadLogs();
</script>`;

export async function pageLogsCheckin(_request: Request, _env: Env): Promise<Response> {
  const html = Mustache.render(checkinTemplate, { today: today() });
  return layout("签到记录", html + CHECKIN_SCRIPT);
}

export async function pageLogsRegister(_request: Request, _env: Env): Promise<Response> {
  const html = Mustache.render(registerTemplate, { today: today() });
  return layout("注册记录", html + REGISTER_SCRIPT);
}

export async function pageLogsErrors(_request: Request, _env: Env): Promise<Response> {
  const html = Mustache.render(errorsTemplate, { today: today() });
  return layout("异常日志", html + ERRORS_SCRIPT);
}
