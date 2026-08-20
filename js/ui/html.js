/* ============================================================
   ui/html.js — 화면을 그릴 때 늘 쓰는 잔손질 몇 가지
   ------------------------------------------------------------
   esc · fmtDT · fmtDate 가 화면 파일마다 똑같이 베껴져 있었다
   (esc 만 여덟 벌). 한 군데가 고쳐지면 나머지가 뒤처지므로 모아 둔다.

   core/xlsx.js 의 esc 는 여기 것과 다르다 — 표 파일(XML)에 넣을 때에는
   XML 이 금하는 제어문자까지 걷어내야 하므로 거기 것을 그대로 둔다.
   ui/versions.js 의 fmtDT 도 줄을 바꿔 두 줄로 보이려는 것이라 따로 둔다.
   ============================================================ */

/** 화면에 글자 그대로 보이도록 — 태그로 읽히지 않게 감싼다 */
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** ISO 시각 → “2026.08.20 14:35” · 읽을 수 없으면 빈 글 */
export function fmtDT(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} `
       + `${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 고시 날짜 “20260423” → “2026. 4. 23.” · 달까지만 있으면 달까지 */
export function fmtDate(d) {
  if (!d) return "";
  if (d.length === 8) return `${d.slice(0, 4)}. ${+d.slice(4, 6)}. ${+d.slice(6, 8)}.`;
  if (d.length === 6) return `${d.slice(0, 4)}. ${+d.slice(4, 6)}.`;
  return d;
}
