/** Island: Logs page — date filter + load logs */

function bjTime(iso) {
  var t = new Date(new Date(iso).getTime() + 8*3600000);
  return String(t.getUTCMonth()+1).padStart(2,'0') + '/' + String(t.getUTCDate()).padStart(2,'0') + ' ' + String(t.getUTCHours()).padStart(2,'0') + ':' + String(t.getUTCMinutes()).padStart(2,'0');
}
function bjDate(iso) {
  var t = new Date(new Date(iso).getTime() + 8*3600000);
  return t.getUTCFullYear() + '-' + String(t.getUTCMonth()+1).padStart(2,'0') + '-' + String(t.getUTCDate()).padStart(2,'0');
}
function matchDate(iso, target) { return bjDate(iso) === target; }

async function loadAllLogs() {
  var date = document.getElementById("log-date").value;

  try {
    var r = await fetch("/api/cron-logs"); var logs = await r.json();
    logs = logs.filter(function(l){ return matchDate(l.time, date); });
    var el = document.getElementById("checkin-logs");
    if (!logs.length) { el.innerHTML = '<span class="text-base-content/50">当日无记录</span>'; }
    else {
      el.innerHTML = logs.map(function(l) {
        var icon = l.ok ? '✅' : '❌';
        var accts = l.accounts.map(function(a){ return '<span class="badge badge-xs badge-ghost">' + a + '</span>'; }).join(' ');
        return '<div class="bg-base-200 rounded p-2"><div class="flex gap-2 items-center mb-1"><span>' + icon + '</span><span class="font-mono text-xs">' + bjTime(l.time) + '</span><span class="font-semibold">签到 ' + l.count + ' 个</span>' + (l.error ? '<span class="text-error text-xs">' + l.error + '</span>' : '') + '</div><div class="flex flex-wrap gap-1">' + accts + '</div></div>';
      }).join('');
    }
  } catch(e) { document.getElementById("checkin-logs").innerHTML = '<span class="text-error">加载失败</span>'; }

  try {
    var r = await fetch("/api/register-logs"); var logs = await r.json();
    logs = logs.filter(function(l){ return matchDate(l.time, date); });
    var el = document.getElementById("register-logs");
    if (!logs.length) { el.innerHTML = '<span class="text-base-content/50">当日无记录</span>'; }
    else {
      el.innerHTML = logs.map(function(l) {
        var icon = l.status === 'active' ? '✅' : '❌';
        var platform = l.platform === 'kiro' ? '<span class="badge badge-xs badge-info">Kiro</span>' : '<span class="badge badge-xs badge-warning">Wucur</span>';
        return '<div class="flex gap-2 items-center bg-base-200 rounded px-2 py-1"><span>' + icon + '</span><span class="font-mono text-xs">' + bjTime(l.time) + '</span>' + platform + '<span class="badge badge-xs badge-ghost">' + l.username + '</span>' + (l.error ? '<span class="text-error text-xs">' + l.error + '</span>' : '') + '</div>';
      }).join('');
    }
  } catch(e) { document.getElementById("register-logs").innerHTML = '<span class="text-error">加载失败</span>'; }

  try {
    var r = await fetch("/api/fail-logs"); var logs = await r.json();
    logs = logs.filter(function(l){ return matchDate(l.created_at, date); });
    var el = document.getElementById("fail-logs");
    if (!logs.length) { el.innerHTML = '<span class="text-base-content/50">当日无异常</span>'; }
    else {
      el.innerHTML = logs.map(function(l) {
        return '<div class="flex gap-2 items-center bg-error/10 rounded px-2 py-1"><span class="font-mono text-xs">' + bjTime(l.created_at) + '</span><span class="badge badge-xs badge-ghost">' + (l.username||'') + '</span><span class="text-error text-xs truncate">' + (l.reason||'') + '</span></div>';
      }).join('');
    }
  } catch(e) { document.getElementById("fail-logs").innerHTML = '<span class="text-error">加载失败</span>'; }
}
loadAllLogs();
