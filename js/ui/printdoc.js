/* ============================================================
   ui/printdoc.js — 참조 규정을 통째로 PDF 로 뽑는다
   ------------------------------------------------------------
   별표ㆍ별지는 원본 파일이 있어 내려받기가 되지만, 참조 규정은 조문을
   색인해 둔 것이라 내려받을 파일이 없었다. 화면으로만 볼 수 있었다.

   그래서 색인한 조문으로 인쇄용 쪽을 지어 새 창에 띄우고 인쇄를 부른다.
   브라우저의 '대상 → PDF 로 저장' 이 그대로 PDF 가 된다.
   따로 붙이는 라이브러리가 없어 어느 자리에서나 똑같이 된다.

   국외 규정처럼 한글 대역이 있는 것은 원문 아래에 대역을 함께 싣는다.
   ============================================================ */

import { esc, fmtDate } from "./html.js?v=20260906d";

/**
 * 조문 하나를 인쇄용 마디로.
 *
 * @param {object} n     조문 마디
 * @param {number} depth 깊이 (지금은 쓰지 아니하나 차례를 지키려고 남긴다)
 * @param {"orig"|"trans"|"both"} mode  화면에서 고른 표시 갈래
 *
 * 국외 규정에는 한글 대역이 붙어 있다. 화면에서 원문ㆍ번역ㆍ대역을 고를 수
 * 있으므로, 뽑아 낼 때에도 고른 그대로 나와야 한다. 여태는 대역이 있으면
 * 늘 둘 다 실었다.
 *
 * 번역만 고른 자리에 번역이 없으면 원문을 싣는다 — 빈 쪽을 내주는 것보다
 * 낫고, 대역이 없는 국내 규정에서도 그대로 돈다.
 */
function nodeHtml(n, depth, mode = "both") {
  const lv = n.level || "";
  const no = n.no
    ? `제${n.no}${lv || "조"}${n.branch ? `의${n.branch}` : ""}`
    : "";
  const isJo = lv === "조" || !n.children?.length;
  const cls = isJo ? "jo" : `hd hd-${esc(lv || "편")}`;
  const hasT = !!(n.transTitle || n.transBody);
  const only = (mode === "trans" && hasT);

  const title = only ? (n.transTitle || n.title || "") : (n.title || "");
  const head = [no, title].filter(Boolean).join(" ");

  let h = "";
  if (head) {
    h += `<div class="${cls}${only ? " ko" : ""}">${esc(head)}`;
    if (mode === "both" && n.transTitle && n.transTitle !== n.title) {
      h += ` <span class="ko">${esc(n.transTitle)}</span>`;
    }
    h += `</div>`;
  }
  const bd = (t, ko) =>
    `<div class="bd${ko ? " ko" : ""}">${esc(t).replace(/\n/g, "<br>")}</div>`;
  if (only) {
    if (n.transBody) h += bd(n.transBody, true);
    else if (n.body) h += bd(n.body, false);
  } else {
    if (n.body) h += bd(n.body, false);
    if (mode === "both" && n.transBody) h += bd(n.transBody, true);
  }
  for (const c of n.children || []) h += nodeHtml(c, depth + 1, mode);
  return h;
}

function countJo(ns) {
  let k = 0;
  for (const n of ns || []) {
    if (n.level === "조" || n.annexRef) k += 1;
    k += countJo(n.children);
  }
  return k;
}

/**
 * 규정 하나를 인쇄용 창에 띄우고 인쇄를 부른다.
 * @param {object} doc  규정 문서 (data/regNN.json 을 읽은 것)
 * @param {object} [opt] {autoPrint:true}
 * @returns {boolean} 창을 띄웠는가
 */
export function printReg(doc, opt = {}) {
  if (!doc) return false;
  const w = window.open("", "_blank", "noopener,width=900,height=1000");
  if (!w) {
    alert("새 창이 막혀 있습니다 — 이 사이트의 팝업을 허용한 뒤 다시 눌러 주십시오.");
    return false;
  }
  w.document.write(regHtml(doc, { ...opt, bar: true }));
  w.document.close();
  if (opt.autoPrint !== false) {
    w.addEventListener("load", () => setTimeout(() => w.print(), 250));
    // 이미 다 그려졌으면 load 가 오지 아니한다
    setTimeout(() => { try { w.print(); } catch { /* 사용자가 닫았다 */ } }, 700);
  }
  return true;
}

/**
 * 규정 하나를 통째로 담은 HTML 한 장을 돌려준다.
 *
 * 인쇄 창에도 쓰고, 파일로 내려받는 데에도 쓴다. 한 자리에서 지어야 화면과
 * 파일이 어긋나지 아니한다.
 *
 * @param {object} doc  규정 문서
 * @param {object} [opt] {mode:"orig"|"trans"|"both", bar:boolean}
 *   bar 는 인쇄 안내 띠를 넣을 것인가 —— 파일로 내려받을 때에는 뺀다.
 */
export function regHtml(doc, opt = {}) {
  const mode = opt.mode || "both";
  const stat = doc.stats || {};
  const meta = [
    doc.org, doc.kind, doc.no,
    doc.effective ? `시행 ${fmtDate(String(doc.effective))}` : "",
  ].filter(Boolean).join(" · ");
  const counts = ["편", "장", "절", "관", "조"]
    .filter((k) => stat[k]).map((k) => `${k} ${stat[k]}`).join(" · ");

  const body = (doc.tree || []).map((n) => nodeHtml(n, 0, mode)).join("");
  const anx = (doc.annexTree && doc.annexTree.length)
    ? `<h2 class="anx-h">별표ㆍ별지</h2>`
      + doc.annexTree.map((n) => nodeHtml(n, 0, mode)).join("")
    : "";
  const MODE_NAME = { orig: "원문", trans: "번역", both: "대역" };
  const hasT = /"trans(Title|Body)"/.test(JSON.stringify(doc.tree || []).slice(0, 200000));
  const modeNote = hasT ? ` · ${MODE_NAME[mode] || "대역"}` : "";

  return (`<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>${esc(doc.name || "규정")}</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font: 10.5pt/1.75 "함초롬바탕","맑은 고딕",serif; color:#111; margin:0; }
  .cover { border-bottom:1.5px solid #333; padding-bottom:10px; margin-bottom:16px; }
  .cover h1 { font-size:16pt; margin:0 0 6px; line-height:1.4; }
  .cover .m { font-size:9pt; color:#555; }
  .hd { font-weight:700; margin:14px 0 4px; page-break-after:avoid; }
  .hd-편 { font-size:14pt; margin-top:22px; border-top:1px solid #999; padding-top:10px; }
  .hd-장 { font-size:12.5pt; }
  .hd-절, .hd-관 { font-size:11pt; }
  .jo { font-weight:700; margin:10px 0 2px; page-break-after:avoid; }
  .bd { margin:0 0 6px 10px; text-align:justify; }
  .ko { color:#1F5C4E; font-weight:400; }
  .anx-h { font-size:13pt; margin-top:26px; border-top:1px solid #999; padding-top:10px; }
  .foot { margin-top:20px; border-top:1px solid #bbb; padding-top:6px;
          font-size:8.5pt; color:#666; }
  @media print { .noprint { display:none } }
</style></head><body>
${opt.bar ? `<div class="noprint" style="background:#F4F6F5;border:1px solid #ccc;padding:8px 12px;
     margin-bottom:14px;font-size:12px">
  인쇄 창에서 <b>대상</b>을 <b>PDF로 저장</b>으로 고르면 PDF 파일이 됩니다.
  <button onclick="window.print()" style="margin-left:8px">인쇄</button>
</div>` : ""}
<div class="cover">
  <h1>${esc(doc.name || "")}</h1>
  <div class="m">${esc(meta)}</div>
  <div class="m">${esc(counts)}${
    doc.annexTree?.length ? ` · 별표ㆍ별지 ${doc.annexTree.length}` : ""}${modeNote}</div>
</div>
${body}${anx}
<div class="foot">
  ${esc(doc.source || "")}<br>
  공공측량 규정 개정 편집기에서 색인한 조문으로 뽑았습니다 — 조문 ${countJo(doc.tree)}개.
  ${doc.copyright ? `<br>${esc(doc.copyright)}` : ""}
</div>
</body></html>`);
}
