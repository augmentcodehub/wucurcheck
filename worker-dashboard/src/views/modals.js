/** Modal dialogs */

export function renderDetailModal() {
  return `
<dialog id="account-detail" class="modal">
  <div class="modal-box">
    <h3 class="text-lg font-bold mb-4" id="detail-title">账号详情</h3>
    <div class="space-y-2 text-sm">
      <div><span class="font-semibold">平台：</span><span id="detail-platform"></span></div>
      <div><span class="font-semibold">状态：</span><span id="detail-status" class="badge badge-sm"></span></div>
      <div><span class="font-semibold">余额：</span><span id="detail-balance"></span></div>
      <div><span class="font-semibold">签到时间：</span><span id="detail-checkin-time"></span></div>
      <div><span class="font-semibold">最近结果：</span><span id="detail-last-result"></span></div>
    </div>
    <div class="modal-action"><form method="dialog"><button class="btn">关闭</button></form></div>
  </div>
</dialog>`;
}

export function renderRegisterModal() {
  return `
<dialog id="register-modal" class="modal">
  <div class="modal-box">
    <h3 class="text-lg font-bold mb-4">➕ 批量注册账号</h3>
    <div class="space-y-3">
      <div><label class="label text-sm">数量</label><input id="reg-count" type="number" value="3" min="1" max="50" class="input input-bordered input-sm w-full" oninput="updatePreview()"/></div>
      <div><label class="label text-sm">用户名组合</label><select id="reg-prefix" class="select select-bordered select-sm w-full" onchange="updatePreview()"><option value="fruit+animal">水果+动物</option><option value="plant+animal">植物+动物</option><option value="fruit+metal">水果+金属</option><option value="plant+metal">植物+金属</option></select></div>
      <div><label class="label text-sm">邮箱域名</label><select id="reg-domain" class="select select-bordered select-sm w-full" onchange="updatePreview()"><option value="qq.com">qq.com</option><option value="163.com">163.com</option><option value="gmail.com">gmail.com</option><option value="outlook.com">outlook.com</option><option value="mailto.plus">mailto.plus</option></select></div>
      <div><label class="label text-sm">密码</label><input id="reg-password" type="text" value="123Claude&Codex" class="input input-bordered input-sm w-full" oninput="updatePreview()"/></div>
    </div>
    <div class="mt-3 p-2 bg-base-200 rounded text-xs font-mono">
      <div>样例：<span id="reg-preview"></span></div>
      <div id="reg-length" class="mt-1"></div>
    </div>
    <div class="modal-action">
      <form method="dialog"><button class="btn btn-sm">取消</button></form>
      <button id="reg-submit" class="btn btn-success btn-sm" onclick="doRegister(event)">开始注册</button>
    </div>
  </div>
</dialog>`;
}
