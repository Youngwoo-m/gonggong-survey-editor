/* ============================================================
   core/hwpxcompare.js — 신구대조표를 양식에 얹어 한/글 문서로
   ------------------------------------------------------------
   scripts/formdocs.py 의 build_compare 를 브라우저로 옮긴 것이다.

   ■ 무엇이 다른가

     파이썬 쪽은 글자를 스스로 견주어(diff_runs) 붉은 자리를 정한다. 여기서는
     **화면이 이미 만든 도막을 그대로 쓴다**(officialCells). 견주기를 두 벌
     두면 화면에서 본 대비표와 내려받은 한/글 문서가 서로 달라진다.

       t === "+"   새로 쓴 글      → 붉은 글씨
       t === "-"   없어질 글       → 그대로 (양식은 현행 칸에 색을 쓰지 않는다)
       그 밖        바뀌지 않은 글 → 그대로 ("_" 로 줄인 것도 여기에 든다)

   ■ 양식

     Form\02.신구대조표\[양식] 규정.신구대조표.hwpx — 가로쪽, 세 칸.
     꾸러미에도 같은 것이 kit/양식/02.신구대조표/ 에 있다. 웹에서는 그것을
     가져온다 (Form 폴더는 서버에 올라가지 않는다).
   ============================================================ */

import { Form, RowProto, remake, retext, splitParas, tableSpan, topRows, retable }
  from "./hwpx.js?v=20260907a";

export const TPL_COMPARE =
  "kit/양식/02.신구대조표/[양식] 규정.신구대조표.hwpx";

/** 양식이 적어 둔 표기 원칙 — 문서에도 그대로 적는다 */
export const RULE_LINE =
  "표기 원칙 — 변경 없는 부분은 “_”로 생략 표기, 개정안 문구는 붉은색 표시";

/**
 * @param {Array} rows        buildComparison 이 낸 줄들 (조문만 골라 넣을 것)
 * @param {object} opt
 *   - regname   규정 이름
 *   - cells     (row) => {cur:[{t,s}], rev:[{t,s}]}   officialCells
 *   - why       (row) => string[]                     개조식 사유 줄
 *   - tplUrl    양식 자리 (없으면 TPL_COMPARE)
 * @returns {Promise<{blob:Blob, name:string, rows:number}>}
 */
export async function buildCompareHwpx(rows, opt = {}) {
  const { regname = "규정", cells, why } = opt;
  if (typeof cells !== "function") throw new Error("cells 를 주셔야 합니다.");

  const f = await Form.fetch(opt.tplUrl || TPL_COMPARE);
  const tops = f.topParas();
  if (!tops.length) throw new Error("양식에서 문단을 찾지 못했습니다.");
  const title = tops[0].blk;
  const tblP = tops.find((p) => p.nested);
  if (!tblP) throw new Error("양식에서 표를 찾지 못했습니다.");

  const span = tableSpan(tblP.blk);
  const tbl = tblP.blk.slice(span[0], span[1]);
  const trs = topRows(tbl);
  if (trs.length < 2) throw new Error("양식의 표에 본으로 쓸 행이 없습니다.");

  const headRow = trs[0];
  /* 본으로 쓸 행은 칸 안에 표가 없는 것을 고른다 — 양식의 몇몇 행은 칸 안에
     또 표를 담고 있어(시료 보존방법 표 따위) 본으로 삼으면 그 표까지 딸려
     온다. */
  const plain = trs.slice(1).find((t) => !t.includes("<hp:tbl ")) || trs[1];
  const proto = new RowProto(plain);

  const bodyChar = (/charPrIDRef="(\d+)"/.exec(proto.paraProto(2)) || [])[1] || null;
  const headChar = (/charPrIDRef="(\d+)"/.exec(headRow) || [])[1] || bodyChar;
  const red = f.newCharPr(bodyChar || "0", { textColor: "#FF0000" });

  /* 화면 도막 → 한/글 run.
     본으로 뜬 문단의 글자모양은 굵을 수 있다(양식에서 그 자리가 소제목이라
     그렇다). 본문은 보통 글씨로 맞춘다. */
  /* allRed 는 신설 조문에 쓴다. 신설은 견줄 현행이 없어 도막이 모두 '그대로'
     로 나오지만, 글 전체가 새로 쓴 것이므로 통째로 붉게 적는다. */
  const toRuns = (parts, redden, allRed) => (parts || []).map((p) => [
    (allRed || (redden && p.t === "+")) ? red : bodyChar,
    String(p.s || ""),
  ]).filter(([, s]) => s !== "");

  /* 첫 조각은 조 제목이다 — 「제2조(정의)」. 뒤에 붙는 '(생략)ㆍ(현행과
     같음)' 도 같은 줄에 있어야 하므로 함께 묶는다. 여기를 잘못 잘라
     제목이 통째로 사라진 적이 있다. */
  const headAndRest = (parts) => {
    const ps = parts || [];
    let head = ps.length ? String(ps[0].s || "") : "";
    let i = 1;
    while (i < ps.length && ps[i].t === "omit") {
      head += String(ps[i].s || ""); i += 1;
    }
    return [head.replace(/\n/g, " ").trim(), ps.slice(i)];
  };

  const cellXml = (col, parts, redden, headStyle, allRed) => {
    const [head, rest] = headAndRest(parts);
    const p = proto.paraProto(col);
    const out2 = [remake(p, [[headStyle, head]])];
    for (const g of splitParas(toRuns(rest, redden, allRed))) {
      if (g.length) out2.push(remake(p, g));
    }
    return out2.join("");
  };

  const out = [headRow];
  let n = 0;
  for (const r of rows) {
    n += 1;
    const c = cells(r);

    const c0 = [cellXml(0, c.cur, false, headChar)];
    const isNew = r.kind === "신설";
    const c1 = [cellXml(1, c.rev, true, isNew ? red : headChar, isNew)];
    const lines = (why ? why(r) : []) || [];
    const c2 = (lines.length ? lines : [r.kind || r.status || ""])
      .map((s) => remake(proto.paraProto(2), [[bodyChar, `- ${s}`]]));

    out.push(proto.make(n, [c0.join(""), c1.join(""), c2.join("")]));
  }

  const newTbl = retable(tbl, out.join(""), out.length);
  // 제목 문단도 쪽 설정(가로쪽)을 이고 있다 — 글자만 바꾼다
  const body = retext(title, `[붙임] ${regname} 일부 개정(안) 신·구대조표`)
    + remake(title, [[bodyChar, RULE_LINE]])
    + tblP.blk.slice(0, span[0]) + newTbl + tblP.blk.slice(span[1]);
  f.xml = f.xml.slice(0, tops[0].s) + body + f.xml.slice(tops[tops.length - 1].e);

  return {
    blob: f.toBlob(),
    name: `${regname} 신구대조표.hwpx`,
    rows: n,
  };
}
