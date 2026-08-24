/* ============================================================
   ui/report.js — 지금 화면에 있는 그대로 보고서 한 벌을 짓는다
   ------------------------------------------------------------
   여태 [보고서] 는 미리 만들어 둔 zip 을 내려받기만 했다. 그것은 이 컴퓨터의
   python scripts/genreport.py 가 한/글을 불러 만든 것이라, 만든 날 뒤에 고친
   것은 하나도 담기지 아니한다. 실제로 날짜가 여러 날 뒤처져 있었다.

   그래서 누르는 그 자리에서 지금 상태로 새로 짓는다. 규정마다 여섯 벌이다.

     개정안_전문.html         편ㆍ장ㆍ절ㆍ관 차례대로 담은 조문 전문
     신구조문_대비표.html      현행 ↔ 개정안 두 칸
     신구조문_대비표.xlsx      같은 것을 엑셀로
     개정사유서.html          조문마다 [변경 사유]
     개정문.html              개정 지시문
     별표별지_목록.html        번호ㆍ제목ㆍ상태ㆍ파일

   대비표를 그리는 규칙(officialCells)은 화면과 함께 쓴다 — 두 벌을 두면
   화면에서 본 것과 내려받은 것이 서로 달라진다.

   ■ HWPX 는 여기서 만들지 아니한다

     HWPX(ZIP+XML)를 손으로 조립하면 한/글이 '손상된 파일' 로 본다. 한/글에게
     맡겨야 하고, 그것은 브라우저가 할 수 없는 일이다. 한/글 문서가 필요하면
     지금도 python scripts/genreport.py 를 돌려야 한다 — 읽어보기.txt 에
     그렇게 적어 둔다.
   ============================================================ */

import { buildComparison, KIND_LIST } from "../core/diff.js?v=20260824d";
import { buildAmendment } from "../core/amend.js?v=20260824d";
import { writeXlsx } from "../core/xlsx.js?v=20260824d";
import { createZip } from "../core/zip.js?v=20260824d";
import { stripImgTags } from "../core/objects.js?v=20260824d";
import { officialCells, cellsHtml } from "./compare.js?v=20260824d";
import { esc } from "./html.js?v=20260824d";

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
  u.mk { text-decoration:underline; text-underline-offset:2px; }
  u.mk-old { text-decoration:underline; color:#1B4F72; }
  .mk-new { font-weight:700; }
  .mk-omit { color:#444; }
  .amd { margin:0 0 8px 10px; }
  .amd .tag { font-size:8.5pt; border:1px solid #bbb; border-radius:8px;
              padding:1px 6px; margin-right:6px; }
`;

function page(title, headHtml, bodyHtml, footHtml) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>${esc(title)}</title><style>${CSS}</style></head><body>
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
        hwp: a.hwp || "", pages: a.pages || "",
        note: a.gen ? "본문 글로 지음" : (a.src || ""),
      });
    }
    annexRows(n.children, out);
  }
  return out;
}

/* ---------------------------------------------------------------- 대비표 */
function tableHtml(rows) {
  const tr = rows.map((r) => {
    const c = officialCells(r);
    return `<tr><td>${cellsHtml(c.cur)}</td><td>${cellsHtml(c.rev)}</td></tr>`;
  }).join("");
  return `<table><thead><tr><th style="width:50%">현 행</th>`
    + `<th style="width:50%">개 정 안</th></tr></thead><tbody>${tr}</tbody></table>`;
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
  sheetRows.push(["현행", "개정안"].map((v) => ({ v, s: S.HEAD })));
  for (const r of rows) {
    const c = officialCells(r);
    sheetRows.push([
      { runs: cellRuns(c.cur), s: S.CELL },
      { runs: cellRuns(c.rev), s: S.CELL },
    ]);
  }
  return writeXlsx({ cols: [{ w: 58 }, { w: 58 }], rows: sheetRows });
}

/* ================================================================ 짓기 */

/**
 * 지금 프로젝트 상태로 보고서 한 벌을 짓는다.
 * @param {object} project
 * @param {{targetId?:string|null}} [opt] targetId 를 주면 그 규정만
 * @returns {{blob:Blob, name:string, items:string[], regs:number}}
 */
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
    files.push({
      name: `${name}/신구조문_대비표.html`,
      data: page(`${name} 신구조문 대비표`, head + cnt, tableHtml(rows), foot),
    });
    files.push({ name: `${name}/신구조문_대비표.xlsx`, data: await bytesOf(xlsxOf(rows, pair)) });

    const rs = reasonHtml(workTree);
    files.push({
      name: `${name}/개정사유서.html`,
      data: page(`${name} 개정사유서`, head + `<div class="m">사유가 적힌 항목 ${rs.length}개</div>`,
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
      "  신구조문_대비표.html     현행 ↔ 개정안 두 칸",
      "  신구조문_대비표.xlsx     같은 것을 엑셀로",
      "  개정사유서.html         조문마다 [변경 사유]",
      "  개정문.html             개정 지시문",
      "  별표별지_목록.html       번호ㆍ제목ㆍ상태ㆍ파일",
      "",
      "이 꾸러미는 [보고서] 를 누른 그때의 편집 상태를 그대로 뽑은 것입니다.",
      "",
      "── 한/글(HWPX) 문서가 필요하시면 ──────────────────────────",
      "HWPX 는 브라우저에서 만들 수 없습니다. 손으로 조립한 꾸러미는 한/글이",
      "'손상된 파일' 로 보므로 한/글에게 저장을 맡겨야 하고, 그것은 이 컴퓨터의",
      "python scripts/genreport.py 가 합니다.",
      "",
      "  python scripts/genreport.py",
      "",
      "돌리고 나면 개정(안).hwpx · 개정사유서.hwpx · 신구대조표.hwpx 와",
      "별표ㆍ별지 모음이 data/report/ 에 만들어집니다.",
      "",
      "별표ㆍ별지의 한/글 파일과 PDF 는 이미 갖추어져 있습니다 —",
      "화면에서 별표를 고르면 [HWP 내려받기] · [PDF 내려받기] 로 받으실 수 있습니다.",
    ].join("\r\n"),
  });

  const one = opt.targetId ? safe(regs[0].short || regs[0].title) + "_" : "";
  return {
    blob: createZip(files),
    name: `개정보고서_${one}${stamp(now)}.zip`,
    items, regs: regs.length,
  };
}
