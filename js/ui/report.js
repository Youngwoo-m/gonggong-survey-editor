/* ============================================================
   ui/report.js — 지금 화면에 있는 그대로 보고서 한 벌을 짓는다
   ------------------------------------------------------------
   여태 [보고서] 는 미리 만들어 둔 zip 을 내려받기만 했다. 그것은 이 컴퓨터의
   python scripts/genreport.py 가 한/글을 불러 만든 것이라, 만든 날 뒤에 고친
   것은 하나도 담기지 아니한다. 실제로 날짜가 여러 날 뒤처져 있었다.

   그래서 누르는 그 자리에서 지금 상태로 새로 짓는다. 규정마다 여섯 벌이다.

     개정안_전문.html         편ㆍ장ㆍ절ㆍ관 차례대로 담은 조문 전문
     신구조문_대비표.html      현 행 / 수정(안) / 개정 사유 세 칸 (양식대로)
     신구조문_대비표.xlsx      같은 것을 엑셀로
     조문별_개정사유.html      조문마다 [변경 사유] — 개정사유서 그 자체는 아니다
     개정문.html              개정 지시문
     별표별지_목록.html        번호ㆍ제목ㆍ상태ㆍ파일

   대비표를 그리는 규칙(officialCells)은 화면과 함께 쓴다 — 두 벌을 두면
   화면에서 본 것과 내려받은 것이 서로 달라진다.

   ■ HWPX 는 여기서 만들지 아니한다 — 대신 만들 수 있게 담아 보낸다

     HWPX(ZIP+XML)를 손으로 조립하면 한/글이 '손상된 파일' 로 본다. 한/글에게
     맡겨야 하고, 그것은 브라우저가 할 수 없는 일이다.

     그래서 꾸러미에 도구(kit/도구)와 양식(kit/양식)과 지금 편집 상태
     (개정안.json)를 함께 담는다. 한/글이 깔린 PC 에서 [한글문서만들기.bat]
     을 누르면 그 자리에서 개정(안)ㆍ신구대조표ㆍ개정사유서가 지어진다.
     담을 것의 목록은 kit/kit.json 에 있다 (scripts/synckit.py 가 만든다).
   ============================================================ */

import { buildComparison, KIND_LIST, kindLabel } from "../core/diff.js?v=20260907u";
import { buildAmendment } from "../core/amend.js?v=20260907u";
import { writeXlsx } from "../core/xlsx.js?v=20260907u";
import { createZip } from "../core/zip.js?v=20260907u";
import { stripImgTags } from "../core/objects.js?v=20260907u";
import { officialCells, cellsHtml, whyLines, whyHtml }
  from "./compare.js?v=20260907u";
import { esc } from "./html.js?v=20260907u";

const nl2br = (s) => esc(s).replace(/\n/g, "<br>");
/** 파일 이름에 쓸 수 없는 글자를 걷어낸다 */
const safe = (s) => String(s || "").replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim();

function stamp(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`
       + `_${p(d.getHours())}${p(d.getMinutes())}`;
}

const CSS = `
  @page { size: A4; margin: 18mm 16mm; }
  body { font: 10.5pt/1.75 "함초롬바탕","맑은 고딕",serif; color:#111; margin:24px; }
  h1 { font-size:17pt; margin:0 0 4px; }
  .m { font-size:9pt; color:#555; margin-bottom:2px; }
  .head { border-bottom:1.5px solid #333; padding-bottom:10px; margin-bottom:18px; }
  .hd { font-weight:700; margin:14px 0 4px; page-break-after:avoid; }
  .hd-편 { font-size:14pt; margin-top:22px; border-top:1px solid #999; padding-top:10px; }
  .hd-장 { font-size:12.5pt; }
  .hd-절,.hd-관 { font-size:11pt; }
  .jo { font-weight:700; margin:12px 0 2px; page-break-after:avoid; }
  .bd { margin:0 0 6px 10px; text-align:justify; }
  .rs { margin:2px 0 10px 10px; font-size:9.5pt; color:#33553f; background:#F4F8F5;
        border-left:3px solid #9CC3AC; padding:7px 10px; }
  table { border-collapse:collapse; width:100%; table-layout:fixed; }
  th,td { border:1px solid #666; padding:6px 8px; vertical-align:top;
          font-size:9.5pt; line-height:1.7; word-break:break-all; }
  th { background:#EFEFEF; font-weight:700; text-align:center; }
  td.c { text-align:center; word-break:keep-all; }
  .k { font-size:8.5pt; border:1px solid #bbb; border-radius:8px; padding:1px 6px; }
  .foot { margin-top:22px; border-top:1px solid #bbb; padding-top:6px; font-size:8.5pt; color:#666; }
  /* 양식의 표기 원칙 — 수정(안)의 새 문구는 붉은색, 현행에서 없어질 대목은 파란색 */
  u.mk { text-decoration:underline; text-underline-offset:2px; color:#C00000; }
  u.mk-old { text-decoration:underline; color:#1B4F72; }
  .rule { border:1px solid #bbb; background:#FAFAF7; padding:6px 10px;
          font-size:9pt; color:#444; margin-bottom:10px; }
  td.why { font-size:9pt; line-height:1.65; word-break:keep-all; }
  col.c1 { width:36%; } col.c2 { width:37%; } col.c3 { width:27%; }
  .mk-new { font-weight:700; }
  .mk-omit { color:#444; }
  .amd { margin:0 0 8px 10px; }
  .amd .tag { font-size:8.5pt; border:1px solid #bbb; border-radius:8px;
              padding:1px 6px; margin-right:6px; }
`;

/* 신구대조표는 가로쪽이라야 세 칸이 들어간다 — 양식도 가로쪽(NARROWLY)이다 */
const LAND = `@page { size: A4 landscape; margin: 12mm 10mm; }
  body { margin:14px; }`;

function page(title, headHtml, bodyHtml, footHtml, moreCss = "") {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>${esc(title)}</title><style>${CSS}${moreCss}</style></head><body>
<div class="head">${headHtml}</div>
${bodyHtml}
<div class="foot">${esc(footHtml)}</div>
</body></html>`;
}

/* ---------------------------------------------------------------- 조문 전문 */
function nodeHtml(n) {
  const lv = n.level || "";
  const isAnx = !!n.annexRef;
  const no = n.no ? `제${n.no}${lv || "조"}${n.branch ? `의${n.branch}` : ""}` : "";
  const head = isAnx
    ? `[${n.annexRef.gubun || "별표"} ${n.annexRef.no}] ${n.title || ""}`
    : [no, n.title ? `(${n.title})` : ""].filter(Boolean).join(" ");
  const cls = (lv === "조" || isAnx) ? "jo" : `hd hd-${esc(lv || "편")}`;

  let h = "";
  if (head.trim()) h += `<div class="${cls}">${esc(head)}</div>`;
  if (n.body) h += `<div class="bd">${nl2br(stripImgTags(n.body, (i) => `[표 ${i}]`))}</div>`;
  for (const c of n.children || []) h += nodeHtml(c);
  return h;
}

/* ---------------------------------------------------------------- 개정사유서 */
function reasonHtml(ns, out = []) {
  for (const n of ns || []) {
    const r = (n.reason || "").trim();
    if (r) {
      const lab = n.annexRef
        ? `[${n.annexRef.gubun || "별표"} ${n.annexRef.no}] ${n.title || ""}`
        : `${n.no ? `제${n.no}${n.level || "조"}${n.branch ? `의${n.branch}` : ""}` : ""}`
          + `${n.title ? `(${n.title})` : ""}`;
      out.push(`<div class="jo">${esc(lab)}`
        + `${n.status ? ` <span class="k">${esc(n.status)}</span>` : ""}</div>`
        + `<div class="rs">${nl2br(r)}</div>`);
    }
    reasonHtml(n.children, out);
  }
  return out;
}

/* ---------------------------------------------------------------- 별표 목록 */
function annexRows(ns, out = []) {
  for (const n of ns || []) {
    if (n.annexRef) {
      const a = n.annexRef;
      out.push({
        gubun: a.gubun || "별표", no: a.no, title: n.title || "",
        status: n.status || "유지", legacy: n.legacyNo || "",
        hwp: a.hwpx || a.hwp || "", pages: a.pages || "",
        note: a.gen ? "본문 글로 지음" : (a.src || ""),
      });
    }
    annexRows(n.children, out);
  }
  return out;
}

/* 셋째 칸에 넣을 개정 사유는 compare.js 의 whyLines/whyHtml 을 그대로 쓴다 —
   화면과 보고서가 한 벌을 써야 서로 달라지지 아니한다. */

/* ---------------------------------------------------------------- 대비표 */
/* 양식은 세 칸이다 — 현 행 36% · 수정(안) 37% · 개정 사유 27%.
   Form\02.신구대조표\[양식] 규정.신구대조표.hwpx 의 칸 폭(25510/26339/18981)
   에서 온 몫이다. 가로쪽이라야 세 칸이 들어간다. */
function tableHtml(rows) {
  const tr = rows.map((r) => {
    const c = officialCells(r);
    return `<tr><td>${cellsHtml(c.cur)}</td><td>${cellsHtml(c.rev)}</td>`
      + `<td class="why">${whyHtml(r)}</td></tr>`;
  }).join("");
  return `<div class="rule"><b>표기 원칙</b> — 변경 없는 부분은 “_” 로 줄여 적고, `
    + `수정(안)의 새 문구는 <u class="mk">붉은색 밑줄</u>로 표시하며, `
    + `개정 사유는 개조식으로 적습니다.</div>`
    + `<table><colgroup><col class="c1"><col class="c2"><col class="c3"></colgroup>`
    + `<thead><tr><th>현 행</th><th>수정(안)</th><th>개정 사유</th></tr></thead>`
    + `<tbody>${tr}</tbody></table>`;
}

/** 대비표 한 칸을 엑셀에 넣을 글로 — 밑줄은 {mark} 도막으로 넘긴다 */
function cellRuns(parts) {
  return (parts || []).map((p) => ({ s: p.s, mark: p.t === "+" || p.t === "-" }));
}

/* writeXlsx 는 Blob 을 돌려주는데 createZip 은 글이나 바이트만 받는다.
   Blob 을 그대로 넣으면 길이를 재지 못해 꾸러미가 깨진다. */
async function bytesOf(blob) {
  return new Uint8Array(await blob.arrayBuffer());
}

function xlsxOf(rows, meta) {
  const S = { HEAD: 1, CELL: 2, CEN: 3, TITLE: 4, SUB: 5 };
  const sheetRows = [];
  sheetRows.push([{ v: "신구조문 대비표", s: S.TITLE }]);
  sheetRows.push([{ v: `대상 규정: ${meta.reg}`, s: S.SUB }]);
  sheetRows.push([{ v: `현행: ${meta.from}   ↔   개정안: ${meta.to}`, s: S.SUB }]);
  sheetRows.push([{ v: `작성 ${new Date().toLocaleString("ko-KR")}`, s: S.SUB }]);
  sheetRows.push([]);
  sheetRows.push(["현 행", "수정(안)", "개정 사유"].map((v) => ({ v, s: S.HEAD })));
  for (const r of rows) {
    const c = officialCells(r);
    const why = whyLines(r.reason, kindLabel(r) || r.status);
    sheetRows.push([
      { runs: cellRuns(c.cur), s: S.CELL },
      { runs: cellRuns(c.rev), s: S.CELL },
      { v: why.map((s) => `- ${s}`).join("\n"), s: S.CELL },
    ]);
  }
  return writeXlsx({ cols: [{ w: 52 }, { w: 54 }, { w: 40 }], rows: sheetRows });
}

/* ================================================================ 짓기 */

/**
 * 지금 프로젝트 상태로 보고서 한 벌을 짓는다.
 * @param {object} project
 * @param {{targetId?:string|null}} [opt] targetId 를 주면 그 규정만
 * @returns {{blob:Blob, name:string, items:string[], regs:number}}
 */
/* ── 꾸러미만으로 한/글 문서를 지을 수 있게 ─────────────────────────────
   HWPX 는 브라우저가 만들지 못한다. 손으로 조립한 꾸러미를 한/글이 '손상된
   파일' 로 보기 때문이다. 그래서 도구와 양식과 지금 편집 상태를 zip 에 함께
   담아 두고, 한/글이 깔린 PC 에서 [한글문서만들기.bat] 을 누르면 그 자리에서
   지어지게 한다. 담을 것의 목록은 kit/kit.json 에 있다
   (scripts/synckit.py 가 만든다). */
const KITROOT = new URL("../../", import.meta.url);
const MAX_ANNEX = 30 * 1024 * 1024;         // 별표를 담는 한도

async function grab(rel) {
  const r = await fetch(new URL(rel, KITROOT));
  if (!r.ok) throw new Error(`${rel} — ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

/** 조문 본문에 박힌 표의 id 를 모은다 */
function objectIds(tree) {
  const ids = new Set();
  const rec = (ns) => ns.forEach((n) => {
    const s = String(n.body || "");
    for (const m of s.matchAll(/<img\s+id="([^"]+)"/g)) ids.add(m[1]);
    rec(n.children || []);
  });
  rec(tree);
  return [...ids];
}

/** 규정 이름 → 등록부의 규정 id (reg12 …). 한 번 읽어 두고 되쓴다.
 *
 * 처음에는 별표 파일 길에서 뽑았다(data/annex/reg12/…). 그런데 양식에서
 * 잘라 낸 별표가 data/annex/form/uav/ 로 옮겨 가면서 'form' 이 잡혔고,
 * 그 뒤로는 아예 뽑을 것이 없어졌다. 길이 아니라 등록부에서 푼다. */
let _regIds = null;
async function regIdBook() {
  if (_regIds) return _regIds;
  _regIds = new Map();
  try {
    const r = await fetch(new URL("data/library.json", KITROOT));
    if (r.ok) {
      const lib = await r.json();
      for (const g of lib.regulations || []) _regIds.set(g.name, g.id);
    }
  } catch { /* 못 읽으면 빈 채로 둔다 */ }
  return _regIds;
}

async function addKit(project, regs, files) {
  const r = { tools: 0, forms: 0, objects: 0, annex: 0, miss: [] };
  let man = null;
  try {
    const res = await fetch(new URL("kit/kit.json", KITROOT));
    if (res.ok) man = await res.json();
  } catch { /* 아래에서 알린다 */ }
  if (!man) { r.miss.push("kit/kit.json"); return r; }

  for (const f of man.files || []) {
    try {
      files.push({ name: f.path, data: await grab("kit/" + f.path) });
      if (f.path.startsWith("양식/")) r.forms += 1; else r.tools += 1;
    } catch { r.miss.push(f.path); }
  }

  const metaOf = (id) => ((project.baseMeta && project.baseMeta.targets) || [])
    .find((t) => t.id === id) || {};

  const book = await regIdBook();
  const pack = [];
  let annexBytes = 0;
  for (const reg of regs) {
    const tree = reg.children || [];
    const m = metaOf(reg.targetId);
    const regId = book.get(m.name || "") || book.get(reg.title || "") || "";
    pack.push({
      regname: m.name || reg.title || reg.short,
      short: reg.short || "", regId,
      org: m.org || "", kind: m.kind || "고시",
      revLabel: reg.revLabel || "", supplement: reg.supplement || null,
      tree,
    });

    // 조문에 박힌 표 — 꾸러미에서는 평평하게 둔다 (objects/<id>.xml)
    for (const oid of objectIds(tree)) {
      let done = false;
      for (const rid of [regId, "reg01", "reg12", "reg29"].filter(Boolean)) {
        try {
          files.push({ name: `objects/${oid}.xml`,
            data: await grab(`data/objects/${rid}/${oid}.xml`) });
          r.objects += 1; done = true; break;
        } catch { /* 다음 자리를 본다 */ }
      }
      if (!done) r.miss.push(`objects/${oid}.xml`);
    }

    // 별표ㆍ별지의 한/글 파일과 PDF
    const ax = [];
    (function walkAx(ns) {
      ns.forEach((n) => { if (n.annexRef) ax.push(n); walkAx(n.children || []); });
    })(tree);
    for (const n of ax) {
      const a = n.annexRef;
      const base = `[${a.gubun || "별표"} ${a.no}] ${safe(n.title || "")}`
        + `(${safe(reg.short || reg.title || "")})`;
      // 원본을 모두 .hwpx 로 바꾸었다. 옛 자료가 .hwp 를 이고 있을 수도
      // 있으므로 함께 보되, 있는 것만 담는다.
      for (const ext of ["hwpx", "hwp", "pdf"]) {
        if (!a[ext] || annexBytes > MAX_ANNEX) continue;
        try {
          const data = await grab(a[ext]);
          annexBytes += data.length;
          files.push({ name: `별표및별지모음/${base}.${ext}`, data });
          r.annex += 1;
        } catch { r.miss.push(a[ext]); }
      }
    }
  }

  files.push({ name: "개정안.json", data: JSON.stringify(pack) });
  return r;
}

export async function buildReport(project, opt = {}) {
  const files = [];
  const items = [];
  const now = new Date();

  const regs = opt.targetId
    ? project.regNodes.filter((n) => n.targetId === opt.targetId)
    : project.regNodes;
  if (!regs.length) throw new Error("담을 규정이 없습니다.");

  // 기준(현행) 판 — 읽기 전용으로 잡아 둔 첫 판
  const base = project.versions.find((v) => v.readonly) || project.versions[0];

  for (const reg of regs) {
    const name = safe(reg.short || reg.title || reg.targetId);
    const to = project.versionOf(reg.targetId) || project.current;
    const baseReg = base ? project.regIn(base, reg.targetId) : null;
    const baseTree = baseReg ? (baseReg.children || []) : [];
    const workTree = reg.children || [];

    const { rows, summary } = buildComparison(baseTree, workTree, { onlyChanged: true });
    const pair = {
      reg: reg.title || name,
      from: (base && (base.title || base.label)) || "현행",
      to: (to && (to.title || to.label)) || "개정안",
    };
    const head = `<h1>${esc(reg.title || name)}</h1>
      <div class="m">현행: ${esc(pair.from)} &nbsp;↔&nbsp; 개정안: ${esc(pair.to)}</div>
      <div class="m">작성 ${esc(now.toLocaleString("ko-KR"))}</div>`;
    const foot = "공공측량 규정 개정 편집기에서 지금 편집 상태 그대로 뽑았습니다.";

    files.push({
      name: `${name}/개정안_전문.html`,
      data: page(`${name} 개정안 전문`, head, workTree.map(nodeHtml).join(""), foot),
    });

    const cnt = `<div class="m">전체 ${summary.총} · 조 ${summary.조}`
      + `${summary.별표 ? ` · 별표ㆍ별지 ${summary.별표}` : ""} · 변경 ${summary.변경}`
      + ` — ${KIND_LIST.filter((k) => summary[k]).map((k) => `${k} ${summary[k]}`).join(" · ")}</div>`;
    /* 대비표에 싣는 것은 **조문뿐**이다 — 한/글 생성기(formdocs.build_compare)와
       같은 잣대라야 웹에서 본 것과 [한글문서만들기.bat] 이 지은 것이 같아진다.
       편ㆍ장 마디는 본문이 아니라 개편 설명이 담겨 있어 대비표에 들어가면
       수정(안) 칸이 연구 메모로 채워진다. 별표는 따로 목록을 낸다. */
    const cmpRows = rows.filter((r) => r.level === "조" && !r.annex);
    files.push({
      name: `${name}/신구조문_대비표.html`,
      data: page(`${name} 신구조문 대비표`, head + cnt, tableHtml(cmpRows), foot, LAND),
    });
    files.push({ name: `${name}/신구조문_대비표.xlsx`,
                 data: await bytesOf(xlsxOf(cmpRows, pair)) });

    const rs = reasonHtml(workTree);
    files.push({
      name: `${name}/조문별_개정사유.html`,
      data: page(`${name} 조문별 개정사유`, head + `<div class="m">사유가 적힌 항목 ${rs.length}개</div>`,
        rs.join("") || "<p>적어 둔 변경 사유가 없습니다.</p>", foot),
    });

    let amd = "<p>만들 수 있는 개정 지시문이 없습니다.</p>";
    try {
      const am = buildAmendment(rows, { regName: reg.title || name, whole: false });
      amd = `<div class="m">지시문 ${am.items.length}개</div>`
        + `<div class="bd">${nl2br(am.head || "")}</div>`
        + am.items.map((it) => `<div class="amd">`
            + `<span class="tag">${esc(it.kind || "")}</span>${nl2br(it.text || "")}`
            + `${it.body ? `<div class="bd">${nl2br(it.body)}</div>` : ""}</div>`).join("");
    } catch (e) {
      amd = `<p>개정문을 만들지 못했습니다 — ${esc(e.message)}</p>`;
    }
    files.push({ name: `${name}/개정문.html`, data: page(`${name} 개정문`, head, amd, foot) });

    const ax = annexRows(workTree);
    const axTr = ax.map((a) => `<tr>
        <td class="c">${esc(a.gubun)} ${esc(a.no)}</td>
        <td>${esc(a.title)}</td>
        <td class="c"><span class="k">${esc(a.status)}</span></td>
        <td class="c">${esc(a.legacy)}</td>
        <td class="c">${a.pages ? `${esc(a.pages)}쪽` : ""}</td>
        <td>${a.hwp ? esc(decodeURIComponent(a.hwp.split("/").pop())) : "—"}</td>
        <td>${esc(a.note)}</td>
      </tr>`).join("");
    files.push({
      name: `${name}/별표별지_목록.html`,
      data: page(`${name} 별표ㆍ별지 목록`, head + `<div class="m">모두 ${ax.length}건</div>`,
        `<table><colgroup><col style="width:9%"><col><col style="width:9%">
          <col style="width:10%"><col style="width:7%"><col style="width:24%">
          <col style="width:13%"></colgroup>
        <thead><tr><th>구분</th><th>제목</th><th>상태</th><th>현행번호</th>
          <th>쪽</th><th>파일</th><th>비고</th></tr></thead><tbody>${axTr}</tbody></table>`, foot),
    });

    items.push(`${name} (조 ${summary.조}${summary.별표 ? ` · 별표ㆍ별지 ${summary.별표}` : ""})`);
  }

  // 도구ㆍ양식ㆍ편집 상태를 함께 담는다 — 이것이 있어야 bat 이 돈다
  const kit = await addKit(project, regs, files);

  files.unshift({
    name: "읽어보기.txt",
    data: [
      "공공측량 규정 개정 보고서",
      "",
      `만든 때 : ${now.toLocaleString("ko-KR")}`,
      `담긴 규정 : ${items.join(" / ")}`,
      "",
      "규정마다 여섯 벌이 들어 있습니다.",
      "  개정안_전문.html        편ㆍ장ㆍ절ㆍ관 차례대로 담은 조문 전문",
      "  신구조문_대비표.html     현 행 / 수정(안) / 개정 사유 세 칸 (양식대로)",
      "  신구조문_대비표.xlsx     같은 것을 엑셀로",
      "  조문별_개정사유.html    조문마다 [변경 사유] — 양식을 갖춘 개정사유서는",
      "                          아래 [한글문서만들기.bat] 으로 지으십시오",
      "  개정문.html             개정 지시문",
      "  별표별지_목록.html       번호ㆍ제목ㆍ상태ㆍ파일",
      "",
      "이 꾸러미는 [보고서] 를 누른 그때의 편집 상태를 그대로 뽑은 것입니다.",
      "",
      "── 한/글(HWPX) 문서를 만들려면 ─────────────────────────────",
      "HWPX 는 브라우저가 만들지 못합니다. 손으로 조립한 꾸러미를 한/글이",
      "'손상된 파일' 로 보기 때문에, 한/글에게 저장을 맡겨야 합니다.",
      "",
      "그래서 이 꾸러미 안에 도구와 양식과 지금 편집 상태를 함께 담았습니다.",
      "한/글이 깔린 PC 에서 다음 하나만 누르시면 됩니다.",
      "",
      "    한글문서만들기.bat        ← 두 번 누르십시오",
      "",
      "출력\ 폴더에 세 벌이 만들어집니다.",
      "    개정(안).hwpx             편ㆍ장ㆍ절 차례대로 담은 조문 전문과 부칙",
      "    개정(안)_신구대조표.hwpx   현 행 / 수정(안) / 개정 사유 세 칸",
      "    개정사유서.hwpx           일곱 절 (6ㆍ7절은 직접 쓰셔야 합니다)",
      "",
      "셋 다 Form 폴더의 양식을 그대로 입힌 것이라 글꼴ㆍ표 테두리ㆍ칸 폭이",
      "양식과 어긋나지 않습니다.",
      "",
      "미리 갖추실 것 —",
      "    한글과컴퓨터 한/글 (2018 이상)",
      "    파이썬 3.9 이상   https://www.python.org/downloads/",
      "                     설치 화면의 'Add python.exe to PATH' 를 켜 주십시오",
      "    pip install pywin32",
      "",
      "꾸러미 안의 자리 —",
      "    개정안.json      [보고서 생성] 을 누른 그때의 편집 상태",
      "    도구\           만드는 스크립트 (formfill·formdocs·genreport 등)",
      "    도구\hwpx\      뒤처리ㆍ검증 스크립트",
      "    양식\           Form 폴더의 양식 그대로",
      "    objects\        조문 본문에 박힌 표",
      "    별표및별지모음\  별표ㆍ별지의 한/글 파일(.hwpx)과 PDF",
    ].join("\r\n"),
  });

  /* 규정 하나만 담을 때에는 그 규정의 개정안 이름(vC-1.01 따위)도 파일 이름에
     넣는다. 개정안이 여러 벌인 규정이 있어(무인비행장치가 그렇다) 넣지
     아니하면 판만 다른 꾸러미가 같은 이름으로 나온다. */
  let one = "";
  if (opt.targetId) {
    one = safe(regs[0].short || regs[0].title) + "_";
    if (regs[0].revLabel) one += safe(regs[0].revLabel) + "_";
  }
  return {
    blob: createZip(files),
    name: `개정보고서_${one}${stamp(now)}.zip`,
    items, regs: regs.length,
  };
}
