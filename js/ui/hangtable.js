/* ============================================================
   ui/hangtable.js — 항별 신구대조표 (전문 수록)
   ------------------------------------------------------------
   신구대조표 창(ui/compare.js)의 한 양식이다. 기술검토위원회에 낸
   항별 신구대조표의 꼴을 따른다.

     · 세 칸 —— 현 행 / 개정(안) / 개정 사유
     · 조마다 항(①②③)을 한 행씩 나누어, 현행과 개정안의 전문을 싣는다
       (「_」 줄임, (생략), (현행과 같음)을 쓰지 아니한다)
     · 개정안에서 새로 쓴 문구는 붉은 밑줄, 현행에서 바뀔 문구는 파란 밑줄
     · 개정 사유는 그 조의 행을 모두 아우르는 한 칸

   견주기는 core/diff.js 의 buildComparison 이 만든 줄(row)을 그대로 받는다.
   항끼리는 번호가 같으면 짝짓고, 번호가 밀린 것은 글이 닮은 쪽과 짝짓는다.
   ============================================================ */
import { wordDiff } from "../core/textdiff.js?v=20261112a";
import { writeXlsx } from "../core/xlsx.js?v=20261112a";
import { esc } from "./html.js?v=20261112a";

const HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";
const NL = "\n";

/* ------------------------------------------------------------ 주제로 고르기 */

/**
 * 주제 낱말로 조를 고른다.
 *   · 쉼표나 띄어쓰기로 나눈 낱말 가운데 하나라도 들어 있으면 고른다
 *   · 「제29조」 처럼 조 번호를 적으면 현행이나 개정안의 그 조를 고른다
 *   · 현행과 개정안의 제목과 본문을 모두 본다
 * @returns {{rows:Array, words:string[]}}
 */
export function pickByTopic(rows, topic) {
  const words = String(topic || "").split(/[,\s]+/).map((w) => w.trim()).filter(Boolean);
  if (!words.length) return { rows, words };
  const nos = [], terms = [];
  for (const w of words) {
    const m = /^제?(\d+)조(?:의(\d+))?$/.exec(w);
    if (m) nos.push(`제${m[1]}조${m[2] ? `의${m[2]}` : ""}`);
    else terms.push(w);
  }
  const squash = (s) => String(s || "").replace(/\s+/g, "");
  const hit = (r) => {
    const sides = [r.before, r.after].filter(Boolean);
    if (sides.some((x) => nos.includes(squash(x.label)))) return true;
    const hay = squash(sides.map((x) => `${x.title || ""} ${x.body || ""}`).join(" "));
    return terms.some((t) => hay.includes(squash(t)));
  };
  return { rows: rows.filter(hit), words };
}

/* ------------------------------------------------------------ 항 나누기 */

/** 본문을 항 단위로 — 줄 머리의 ①②③ 에서 끊는다. 항 표시가 없으면 한 덩이 */
function units(body) {
  const out = [];
  for (const ln of String(body || "").split(NL)) {
    const mk = HANG.includes(ln.charAt(0)) ? ln.charAt(0) : null;
    if (mk || !out.length) out.push({ mark: mk || "", text: ln });
    else out[out.length - 1].text += NL + ln;
  }
  return out.filter((u) => u.text.trim() || out.length === 1);
}

/** 글이 얼마나 닮았는가 — 어절 모음의 겹침 (0~1) */
function sim(a, b) {
  const A = new Set(String(a || "").split(/\s+/).filter(Boolean));
  const B = new Set(String(b || "").split(/\s+/).filter(Boolean));
  if (!A.size || !B.size) return 0;
  let n = 0;
  for (const x of A) if (B.has(x)) n += 1;
  return n / Math.max(A.size, B.size);
}

/**
 * 현행 항과 개정안 항을 짝짓는다 → [[old|null, new|null], …]
 * 번호가 같거나 글이 닮았으면 짝, 아니면 한쪽만 있는 항(신설 또는 삭제)으로 본다.
 */
function pairUnits(olds, news) {
  const out = [];
  let i = 0, j = 0;
  /* 글이 닮은 것을 먼저 본다. 항 하나를 끼워 넣으면 뒤 항의 번호가 하나씩
     밀리므로, 번호만 보고 짝지으면 서로 다른 항이 한 행에 선다. */
  const like = (o, n) => sim(o.text, n.text) >= 0.4;
  while (i < olds.length || j < news.length) {
    const o = olds[i], n = news[j];
    if (o && n && like(o, n)) { out.push([o, n]); i += 1; j += 1; continue; }
    if (o && n) {
      // 한쪽에 항이 끼어들었는지 본다 — 다음 것과 닮았으면 지금 것은 짝이 없다
      if (news[j + 1] && like(o, news[j + 1])) { out.push([null, n]); j += 1; continue; }
      if (olds[i + 1] && like(olds[i + 1], n)) { out.push([o, null]); i += 1; continue; }
      out.push([o, n]); i += 1; j += 1; continue;     // 많이 고친 항 — 같은 자리끼리
    }
    if (o) { out.push([o, null]); i += 1; } else { out.push([null, n]); j += 1; }
  }
  return out;
}

/** 두 글을 견주어 현행 쪽 도막과 개정안 쪽 도막으로 */
function sides(a, b) {
  const runs = wordDiff(a || "", b || "");
  return {
    cur: runs.filter((r) => r.t !== "+").map((r) => ({ t: r.t === "-" ? "-" : "=", s: r.s })),
    rev: runs.filter((r) => r.t !== "-").map((r) => ({ t: r.t === "+" ? "+" : "=", s: r.s })),
  };
}

/** 조 머리 — 「제12조(제목) 」. 번호나 제목이 바뀌었으면 그 대목을 짚는다 */
function heads(b, a) {
  const head = (x, lab, title) => {
    const out = [lab];
    if (x.title) out.push({ t: "=", s: "(" }, ...title, { t: "=", s: ")" });
    out.push({ t: "=", s: " " });
    return out;
  };
  if (b && a) {
    const t = sides(b.title, a.title);
    const numMoved = b.label !== a.label;
    return {
      cur: head(b, { t: numMoved ? "-" : "=", s: b.label }, t.cur),
      rev: head(a, { t: numMoved ? "+" : "=", s: a.label }, t.rev),
    };
  }
  const x = b || a;
  return { one: head(x, { t: "=", s: x.label }, [{ t: "=", s: x.title || "" }]) };
}

/**
 * 비교 줄(row) 하나를 항별 행들로.
 * @returns {{row:object, lines:Array<{cur:Array, rev:Array}>}}
 */
export function hangBlock(r) {
  const b = r.before, a = r.after;
  const lines = [];
  if (!b || !a) {
    // 통째로 새로 두거나 통째로 없앤 조
    const x = b || a;
    const h = heads(b, a).one;
    const us = units(x.body);
    us.forEach((u, k) => {
      const text = [...(k === 0 ? h : []), { t: b ? "-" : "=", s: u.text }];
      const tag = b ? "삭제" : r.splitFrom ? `<현행 ${r.splitFrom}에서 나눔>` : `<${a.label} 신설>`;
      lines.push(b
        ? { cur: text, rev: k === 0 ? [{ t: "mark", s: tag }] : [] }
        : { cur: k === 0 ? [{ t: "mark", s: tag }] : [], rev: text });
    });
    return { row: r, lines };
  }
  const h = heads(b, a);
  pairUnits(units(b.body), units(a.body)).forEach(([o, n], k) => {
    let cur, rev;
    if (o && n) ({ cur, rev } = sides(o.text, n.text));
    else if (o) { cur = [{ t: "-", s: o.text }]; rev = [{ t: "mark", s: "<삭제>" }]; }
    else { cur = [{ t: "mark", s: "<신설>" }]; rev = [{ t: "+", s: n.text }]; }
    if (k === 0) { cur = [...h.cur, ...cur]; rev = [...h.rev, ...rev]; }
    lines.push({ cur, rev });
  });
  return { row: r, lines };
}

/* ------------------------------------------------------------ 그리기 */

function partsHtml(parts) {
  return (parts || []).map((p) => {
    if (p.t === "mark") return `<span class="mk-tag">${esc(p.s)}</span>`;
    if (p.t === "+") return `<u class="mk">${esc(p.s)}</u>`;
    if (p.t === "-") return `<u class="mk-old">${esc(p.s)}</u>`;
    return esc(p.s);
  }).join("").replace(/\n/g, "<br>");
}

/** 표 몸통 — 화면과 새 창이 함께 쓴다. why(row) 는 사유 줄들을 돌려준다 */
export function hangTbody(blocks, why) {
  return blocks.map(({ row, lines }) => lines.map((ln, k) => {
    const w = k === 0
      ? `<td class="why" rowspan="${lines.length}">${why(row).map((s) => `○ ${esc(s)}`).join("<br>")}</td>`
      : "";
    return `<tr class="${k === 0 ? "jo-first" : ""}"><td>${partsHtml(ln.cur)}</td>`
      + `<td>${partsHtml(ln.rev)}</td>${w}</tr>`;
  }).join("")).join("");
}

const PAGE_CSS = `
@page { size: A3 landscape; margin: 14mm 14mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "맑은 고딕", "Malgun Gothic", sans-serif; color: #000; margin: 0;
       background: #fff; }
.bar { position: sticky; top: 0; display: flex; gap: 8px; align-items: center;
       padding: 10px 24px; background: #1F2C35; color: #fff; font-size: 13px; z-index: 2; }
.bar .sp { flex: 1; }
.bar a, .bar button { font: inherit; padding: 6px 14px; border-radius: 4px; border: 0;
       background: #fff; color: #1F2C35; text-decoration: none; cursor: pointer; }
.bar a.pri { background: #2E7D6B; color: #fff; }
main { padding: 20px 24px 40px; }
h1 { font-size: 20pt; text-align: center; margin: 0 0 6px; }
p.sub { text-align: center; color: #333; font-size: 10pt; margin: 0 0 12px; line-height: 1.6; }
.rule { border: 1px solid #bbb; background: #FAFAF7; padding: 6px 10px; font-size: 9.5pt;
        color: #333; margin: 0 0 10px; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; }
thead { display: table-header-group; }
th, td { border: 1px solid #000; padding: 6px 8px; vertical-align: top; font-size: 10pt;
         line-height: 1.7; word-break: break-all; }
th { text-align: center; background: #EFEFEF; font-size: 11pt; }
tr { page-break-inside: avoid; }
tr.jo-first td { border-top: 2px solid #000; }
td.why { font-size: 9.5pt; line-height: 1.65; word-break: keep-all; }
u.mk { text-decoration: underline; text-underline-offset: 2px; color: #C00000; }
u.mk-old { text-decoration: underline; color: #1B4F72; }
.mk-tag { font-weight: 700; }
.foot { margin-top: 14px; font-size: 9pt; color: #555; }
@media print { .bar { display: none; } main { padding: 0; } }
`;

/**
 * 새 창에 띄울 문서 한 벌.
 * @param {object} meta { title, sub:[줄…], xlsxUrl, xlsxName, count }
 */
export function hangPageHtml(blocks, why, meta) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>${esc(meta.title)}</title><style>${PAGE_CSS}</style></head><body>
<div class="bar"><b>${esc(meta.title)}</b><span>${meta.count}개 조</span><span class="sp"></span>
  ${meta.xlsxUrl ? `<a class="pri" href="${esc(meta.xlsxUrl)}" download="${esc(meta.xlsxName)}">엑셀로 내려받기</a>` : ""}
  <button onclick="window.print()">인쇄 (A3 가로)</button></div>
<main>
<h1>${esc(meta.title)}</h1>
<p class="sub">${meta.sub.map(esc).join("<br>")}</p>
<div class="rule"><b>표기 원칙</b> — 항마다 행을 나누어 현행과 개정안의 전문을 싣고,
 개정안의 새 문구는 <u class="mk">붉은색 밑줄</u>, 현행에서 바뀔 문구는 <u class="mk-old">파란색 밑줄</u>로 표시함.</div>
<table><colgroup><col style="width:38%"><col style="width:38%"><col style="width:24%"></colgroup>
<thead><tr><th>현 행</th><th>개 정 (안)</th><th>개 정 사 유</th></tr></thead>
<tbody>${hangTbody(blocks, why)}</tbody></table>
<div class="foot">공공측량 규정 개정 편집기에서 ${esc(new Date().toLocaleString("ko-KR"))} 의 편집 상태로 지음.</div>
</main></body></html>`;
}

/* ------------------------------------------------------------ 엑셀 */

const COLW = [62, 62, 40];

/** 칸 하나가 몇 줄을 차지할지 — 한글 한 자를 너비 1.9 로 어림 */
function lineCount(text, w) {
  let n = 0;
  for (const ln of String(text || "").split(NL)) {
    let u = 0;
    for (const ch of ln) u += ch.charCodeAt(0) > 0x3000 ? 1.9 : 1;
    n += Math.max(1, Math.ceil(u / (w - 1)));
  }
  return n;
}

const toRuns = (parts) => (parts || []).map((p) =>
  ({ s: p.s, mark: p.t === "+" ? true : p.t === "-" ? "old" : false }));
const plain = (parts) => (parts || []).map((p) => p.s).join("");

/** @param {object} meta { title, sub:[줄…], sheet } */
export function hangXlsx(blocks, why, meta) {
  const S = { HEAD: 1, CELL: 2, TITLE: 4, SUB: 5 };
  const rows = [], merges = [], hts = {};
  rows.push([{ v: meta.title, s: S.TITLE }]);
  hts[0] = 26;
  for (const s of meta.sub) rows.push([{ v: s, s: S.SUB }]);
  rows.push([{ v: "표기 원칙 — 항마다 행을 나누어 전문을 싣고, 개정안의 새 문구는 붉은 밑줄, 현행에서 바뀔 문구는 파란 밑줄로 표시함.", s: S.SUB }]);
  rows.push([]);
  rows.push(["현 행", "개 정 (안)", "개 정 사 유"].map((v) => ({ v, s: S.HEAD })));
  const freeze = rows.length;
  for (const { row, lines } of blocks) {
    const first = rows.length;
    const w = why(row).map((s) => `○ ${s}`).join(NL);
    let total = 0;
    lines.forEach((ln, k) => {
      rows.push([
        { runs: toRuns(ln.cur), s: S.CELL },
        { runs: toRuns(ln.rev), s: S.CELL },
        k === 0 ? { v: w, s: S.CELL } : { v: "", s: S.CELL },
      ]);
      const h = Math.max(lineCount(plain(ln.cur), COLW[0]), lineCount(plain(ln.rev), COLW[1])) * 15.5 + 8;
      hts[rows.length - 1] = h;
      total += h;
    });
    const last = rows.length - 1;
    // 사유 칸은 조의 행을 모두 아우른다 — 사유가 더 길면 마지막 행을 늘린다
    const need = lineCount(w, COLW[2]) * 15.5 + 8;
    if (need > total) hts[last] += need - total;
    if (last > first) merges.push(`C${first + 1}:C${last + 1}`);
  }
  return writeXlsx({
    name: meta.sheet || "항별 신구대조표",
    cols: COLW.map((w) => ({ w })),
    rows, rowHeights: hts, merges, freeze, paper: 8,
  });
}
