
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + " " + r.status);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? "{}" : JSON.stringify(body),
  });
  const t = await r.text();
  let data;
  try { data = JSON.parse(t); } catch { data = { 原文: t }; }
  if (!r.ok) throw new Error((data && (data.错误 || data.detail)) || t || String(r.status));
  return data;
}
function 行(html) {
  const tr = document.createElement("tr");
  tr.innerHTML = html;
  return tr;
}
function 徽章(文, 类) {
  const tone = 类 || 命运色(文);
  return `<span class="徽章 ${tone || ""}">${安全文本(文)}</span>`;
}
function 空态(文) { return `<p class="说明">${安全文本(文)}</p>`; }
function 安全文本(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
function 命运色(f) {
  if (["已入栏", "在栏", "已汇总", "对齐"].includes(f)) return "ok";
  if (["已坏点", "已溢出", "撕裂"].includes(f)) return "warn";
  return "";
}
function 渲染水位(el, o) {
  if (!el) return;
  el.innerHTML = "";
  for (const [标, 键] of [["观测报文","观测报文"],["在栏","在栏"],["站点汇总","站点汇总"],["坏点","坏点"]]) {
    const d = document.createElement("div");
    d.className = "水卡";
    d.innerHTML = `<div class="数">${o[键] ?? 0}</div><div class="标">${标}</div>`;
    el.appendChild(d);
  }
}
async function 渲染溢出条(el) {
  if (!el) return;
  let v;
  try { v = await getJSON("/api/溢出裁决"); }
  catch (e) { el.innerHTML = ""; return; }
  const 对账 = v.对账 || {};
  const 态 = v.启用
    ? `<span class="徽章 好">${安全文本(v.形态)}</span>`
    : `<span class="徽章">未启用（未设入栏容限）</span>`;
  const 票 = 对账.是否对齐
    ? `<span class="徽章 好">水位同票对齐</span>`
    : `<span class="徽章 危">水位撕裂</span>`;
  el.innerHTML = `
    <div class="溢出条">
      <div class="溢出头"><b class="铜字">${安全文本(v.策略名)}</b> ${态} ${票}</div>
      <div class="说明 上距8">
        栏 ${安全文本(v.当前栏号)} · 容限 ${v.容限 ?? "—"} ·
        本栏在栏 ${安全文本(v.水位 && v.水位.本栏在栏)} / ${v.容限 ?? "∞"} ·
        旁路溢出 ${安全文本(v.水位 && v.水位.溢出)} 条（只读归档，钉指纹，不回刷）
      </div>
      <div class="说明 上距8">
        同票对账：入流 ${对账.入流 ?? 0} = 在栏 ${对账.在栏 ?? 0} +
        已汇总 ${对账.已汇总 ?? 0} + 坏点 ${对账.坏点 ?? 0} + 溢出 ${对账.溢出 ?? 0}
      </div>
      <div class="说明 上距8">${安全文本(v.可点下一步 || "")}</div>
    </div>`;
}
async function 渲染溢出归档表(el, 空文) {
  if (!el) return;
  let rows = [];
  try { rows = await getJSON("/api/溢出归档"); } catch (e) {}
  el.innerHTML = "";
  if (!rows.length) {
    el.innerHTML = `<tr><td colspan="7">${空态(空文 || "溢出归档为空。设置入栏容限后超容点才会切流到此。")}</td></tr>`;
    return;
  }
  for (const r of rows) {
    el.appendChild(行(`<td>${安全文本(r.报文编号)}</td><td>${安全文本(r.站点键)}</td><td>${安全文本(r.指标键)}</td><td>${r.读数}</td><td>${安全文本(r.观测时)}</td><td><span class="徽章 警">${安全文本(r.原因)}</span></td><td><code>${安全文本(r.指纹)}</code></td>`));
  }
}
function 渲染门槛(el, 规) {
  if (!el) return;
  const r = 规 || {};
  el.innerHTML = `
    <div class="门槛卡"><div class="k">当前栏</div><div class="v">${安全文本(r["当前栏号"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">PM25 上限</div><div class="v">${安全文本(r["PM25上限"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">PM25 下限</div><div class="v">${安全文本(r["PM25下限"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">标定偏移</div><div class="v">${安全文本(r["标定偏移上限"] || "—")}</div></div>
  `;
}
function 渲染批次表(el, rows, cols) {
  if (!el) return;
  if (!rows || !rows.length) {
    el.innerHTML = `<tr><td colspan="${cols.length}">${空态("尚无批次。")}</td></tr>`;
    return;
  }
  el.innerHTML = "";
  for (const r of rows) {
    const cells = cols.map((c) => `<td>${安全文本(r[c])}</td>`).join("");
    el.appendChild(行(cells));
  }
}
function 装载摘要文(r) {
  if (!r) return "";
  return `入流 ${r["入流"]||0} · 入栏 ${r["入栏"]||0} · 坏点 ${r["坏点"]||0} · 驳回 ${r["驳回"]||0}`;
}
function 结栏摘要文(r) {
  if (!r) return "";
  return `栏 ${r["栏号"]||"?"} · 汇总 ${r["汇总数"]||0} · 缓冲消耗 ${r["缓冲消耗"]||0}`;
}
function 贯验摘要文(r) {
  if (!r) return "";
  return `${r["是否对齐"]?"对齐":"撕裂"} · 在栏 ${r["在栏"]} · 汇总报文 ${r["汇总报文"]} · 坏点 ${r["坏点"]}`;
}
function 填命运字典(el, dict) {
  if (!el || !dict) return;
  el.innerHTML = Object.entries(dict).map(([k, v]) =>
    `<div class="只读框 上距8"><b class="铜字">${安全文本(k)}</b> · ${安全文本(v)}</div>`
  ).join("");
}
window.探栏 = {
  getJSON, postJSON, 行, 徽章, 空态, 安全文本, 命运色,
  渲染水位, 渲染门槛, 渲染批次表, 渲染溢出条, 渲染溢出归档表,
  装载摘要文, 结栏摘要文, 贯验摘要文, 填命运字典,
};
