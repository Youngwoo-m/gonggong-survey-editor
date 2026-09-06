/* ============================================================
   core/annexhwpx.js — 올린 한/글 파일(.hwpx)에서 별표의 표를 뽑는다
   ------------------------------------------------------------
   별표ㆍ별지의 「서식 표」 는 미리 뽑아 둔 XML
   (data/objects/<규정>/annex/<구분><번호>.xml) 을 그려 온 것이다. 사람이
   [바뀐 서식 파일] 로 새 한/글 파일을 올리면 그것이 현행 서식을 갈음하므로,
   화면도 그 파일에서 표를 뽑아 보여야 한다.

   scripts/annexxml_hwpx.py 를 옮긴 것이다. HWPX 는 ZIP + XML 이고 표가
   이미 XML 로 적혀 있으므로 짐작할 것이 없다.

       <hp:tbl rowCnt colCnt>
         <hp:tr><hp:tc><hp:cellAddr colAddr rowAddr/>
                       <hp:cellSpan colSpan rowSpan/> … <hp:t>글</hp:t>

   칸 안에 또 표가 있어도 속지 않도록 깊이를 세어 겉 표만 센다.
   ============================================================ */
import { readZip } from "./zipreader.js?v=20260907m";

const RE_T = /<hp:t(?:\s[^>]*)?>([^]*?)<\/hp:t>/g;

const unesc = (s) => String(s)
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");

const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

/** 겹치지 않는 겉 덩이의 [시작, 끝] 목록 — 깊이를 세어 속엣것은 건너뛴다 */
function spans(xml, open, close, from = 0, to = -1) {
  const end = to < 0 ? xml.length : to;
  const out = [];
  let i = from;
  while (i < end) {
    const s = xml.indexOf(open, i);
    if (s < 0 || s >= end) break;
    let depth = 0;
    let j = s;
    while (j < end) {
      const a = xml.indexOf(open, j + 1);
      const b = xml.indexOf(close, j + 1);
      if (b < 0) return out;                     // 짝이 맞지 아니한다 — 여기까지
      if (a >= 0 && a < b) { depth += 1; j = a; continue; }
      if (depth === 0) { out.push([s, b + close.length]); i = b + close.length; break; }
      depth -= 1;
      j = b;
    }
    if (j >= end) break;
  }
  return out;
}

/** 칸의 글 — 속 표의 글은 빼고 이 칸의 문단만 모은다 */
function cellText(tc) {
  const inner = spans(tc, "<hp:tbl ", "</hp:tbl>");
  const keep = [];
  let last = 0;
  for (const [s, e] of inner) { keep.push(tc.slice(last, s)); last = e; }
  keep.push(tc.slice(last));
  const body = keep.join("");
  const out = [];
  RE_T.lastIndex = 0;
  let m;
  while ((m = RE_T.exec(body))) out.push(unesc(m[1]));
  return out.join("").replace(/[ \t]+/g, " ").trim();
}

/** hwpx 꾸러미 → [{rows, cols, cells:[{col,row,cs,rs,text}]}] (겉 표만) */
export async function tablesOfHwpx(buf) {
  const files = await readZip(buf);
  const secs = [...files.keys()]
    .filter((n) => /Contents\/section\d+\.xml$/i.test(n))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  if (!secs.length) throw new Error("한/글 문서에서 본문을 찾지 못했습니다.");
  const dec = new TextDecoder("utf-8");
  const xml = secs.map((n) => dec.decode(files.get(n))).join("");

  const out = [];
  for (const [s, e] of spans(xml, "<hp:tbl ", "</hp:tbl>")) {
    const tbl = xml.slice(s, e);
    const head = tbl.slice(0, tbl.indexOf(">") + 1);
    const rc = /rowCnt="(\d+)"/.exec(head);
    const cc = /colCnt="(\d+)"/.exec(head);
    const cells = [];
    for (const [rs, re] of spans(tbl, "<hp:tr>", "</hp:tr>")) {
      for (const [cs, ce] of spans(tbl, "<hp:tc ", "</hp:tc>", rs, re)) {
        const tc = tbl.slice(cs, ce);
        const addr = /<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"/.exec(tc);
        if (!addr) continue;
        const span = /<hp:cellSpan colSpan="(\d+)" rowSpan="(\d+)"/.exec(tc);
        cells.push({
          col: +addr[1], row: +addr[2],
          cs: span ? +span[1] : 1, rs: span ? +span[2] : 1,
          text: cellText(tc),
        });
      }
    }
    if (!cells.length) continue;
    out.push({
      rows: rc ? +rc[1] : Math.max(...cells.map((c) => c.row)) + 1,
      cols: cc ? +cc[1] : Math.max(...cells.map((c) => c.col)) + 1,
      cells,
    });
  }
  return out;
}

/**
 * 올린 한/글 파일에서 별표 XML 을 짓는다 —— 미리 뽑아 둔 것과 같은 꼴이라
 * 화면 그리는 코드를 그대로 쓸 수 있다.
 * @param {ArrayBuffer} buf
 * @param {{key?:string, gubun?:string, no?:string, title?:string, source?:string}} meta
 * @returns {Promise<string>} <annex …> XML
 */
export async function annexXmlFromHwpx(buf, meta = {}) {
  const tbls = await tablesOfHwpx(buf);
  const L = ['<?xml version="1.0" encoding="UTF-8"?>',
    `<annex id="${esc(meta.key)}" gubun="${esc(meta.gubun || "별표")}"`
    + ` no="${esc(meta.no)}" title="${esc(meta.title)}" source="${esc(meta.source)}">`];
  for (const t of tbls) {
    L.push(`  <table rows="${t.rows}" cols="${t.cols}">`);
    const byRow = new Map();
    for (const c of t.cells) {
      if (!byRow.has(c.row)) byRow.set(c.row, []);
      byRow.get(c.row).push(c);
    }
    for (const r of [...byRow.keys()].sort((a, b) => a - b)) {
      L.push("    <row>");
      for (const c of byRow.get(r).sort((a, b) => a.col - b.col)) {
        let at = `col="${c.col}" row="${c.row}"`;
        if (c.cs > 1) at += ` colspan="${c.cs}"`;
        if (c.rs > 1) at += ` rowspan="${c.rs}"`;
        L.push(`      <cell ${at}>${esc(c.text)}</cell>`);
      }
      L.push("    </row>");
    }
    L.push("  </table>");
  }
  L.push("</annex>");
  return L.join("\n");
}

/** data: 주소로 담긴 자산을 바이트로 —— 올린 파일은 프로젝트에 data: 로 담긴다 */
export async function assetBuffer(asset) {
  if (!asset || !asset.data) return null;
  const r = await fetch(asset.data);
  return r.arrayBuffer();
}
