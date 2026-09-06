/* ============================================================
   core/hwpxdraft.js — 고른 개정안 하나를 한/글 개정(안) 문서로
   ------------------------------------------------------------
   scripts/formdocs.py 의 build_draft 를 브라우저로 옮긴 것이다. 같은 양식
   (kit/양식/01.개정안/[양식] 규정 개정(안).hwpx)에 같은 차례로 글을 얹으므로,
   웹에서 받은 문서와 [한글문서만들기.bat] 이 지은 문서가 같아진다.

   ■ 무엇을 담고 무엇을 담지 아니하는가

     담는 것    편ㆍ장ㆍ절ㆍ관의 제목, 조문의 번호ㆍ제목ㆍ본문, 부칙
     담지 않는 것  별표ㆍ별지(따로 내는 문서다), 표ㆍ수식 개체

     표와 수식은 조문 본문에 <img id="…"> 로 자리만 있고 알맹이는
     data/objects 에 따로 있다. 그것까지 얹으려면 개체 XML 을 양식의 표 본에
     맞추어 다시 짜야 하는데, 그 일은 [보고서] 가 내는 꾸러미의 도구가
     한다(genreport_hwpx.py). 여기서는 그 자리를 한 줄로 밝혀 둔다 ——
     빠뜨린 것을 사람이 알아볼 수 있어야 하기 때문이다.

   ■ 변경 사유는 담지 아니한다

     개정(안)은 고시에 실리는 글이다. 변경 사유는 개정사유서에 실린다.
   ============================================================ */

import { Form, remake, retext, esc } from "./hwpx.js?v=20260907a";

const NL = "\n";
const RE_IMG = /<img\s+id="([\w.-]+)"\s*>(?:<\/img>)?/gi;
const RE_PROV = /<현행[^<>]*>|<신설[^<>]*>/g;      // 출처 표시는 고시에 싣지 아니한다
const RE_CHAP = /^제\s*\d+\s*(편|장|절|관)\b/;
const RE_ART = /^제\s*\d+\s*조/;
const RE_ITEM = /^\s*\d{1,2}\s*\./;
const RE_CLAUSE = /^\s*[①-⑳]/;

/** 양식에서 종류마다 본을 하나씩 뜬다 (formdocs.protos 와 같은 잣대) */
function protos(f) {
  const tops = f.topParas();
  const P = { tops, head: tops[0].blk };
  for (const p of tops) {
    if (p.nested && !P.tbl) P.tbl = p.blk;
    if (!p.text && !P.blank) P.blank = p.blk;
    if (RE_CHAP.test(p.text) && !P.chap) P.chap = p.blk;
    else if (RE_ART.test(p.text) && !P.art) P.art = p.blk;
    else if (RE_ITEM.test(p.text) && !P.item) P.item = p.blk;
    else if (RE_CLAUSE.test(p.text) && !P.clause) P.clause = p.blk;
    else if (p.text === "부칙" && !P.supp) P.supp = p.blk;
  }
  P.clause = P.clause || P.item;
  P.item = P.item || P.art;
  P.blank = P.blank || P.item;
  P.supp = P.supp || P.chap;
  // 제목은 첫 문단 다음의 글 있는 문단 가운데 장ㆍ조가 아닌 것
  for (const p of tops.slice(1)) {
    if (p.text && !p.nested && !RE_CHAP.test(p.text) && !RE_ART.test(p.text)) {
      P.title = p.blk;
      break;
    }
  }
  return P;
}

/** 조문 본문 → 줄 목록. 표ㆍ수식 자리는 {obj:id} 로 남긴다 */
function bodyLines(text) {
  const t = String(text || "").replace(RE_PROV, "");
  const out = [];
  let last = 0;
  RE_IMG.lastIndex = 0;
  let m;
  while ((m = RE_IMG.exec(t))) {
    for (const s of t.slice(last, m.index).split(NL)) {
      if (s.trim()) out.push(s.trim());
    }
    out.push({ obj: m[1] });
    last = m.index + m[0].length;
  }
  for (const s of t.slice(last).split(NL)) {
    if (s.trim()) out.push(s.trim());
  }
  return out;
}

function lineProto(P, s) {
  return RE_CLAUSE.test(s) ? P.clause : P.item;
}

/** 그 규정에 딸린 마디를 차례대로 (깊이우선) */
function* walk(nodes) {
  for (const n of nodes || []) {
    yield n;
    yield* walk(n.children);
  }
}

/**
 * 개정안 한 벌을 개정(안) 한/글 문서로 짓는다.
 * @param {object} reg   규정 마디 (project.regNode 가 낸 것)
 * @param {string} tplUrl 양식 파일 주소
 * @param {{org?:string, kind?:string, supp?:string|string[]}} opt
 * @returns {Promise<{blob:Blob, name:string, 조:number, 뺀개체:number}>}
 */
export async function buildDraftHwpx(reg, tplUrl, opt = {}) {
  const f = await Form.fetch(tplUrl);
  const P = protos(f);
  const org = opt.org || "국토지리정보원";
  const kind = opt.kind || "고시";
  const regname = reg.title || "규정";

  // 첫 문단은 쪽 설정(secPr)을 이고 있으므로 글자만 바꾼다
  const out = [
    retext(P.head, `${org} ${kind} 제○○○○-○○○○호`),
    remake(P.blank, []),
    remake(P.title, [[null, `${regname} 개정(안)`]]),
  ];

  // 조문 본문에 쓸 보통 글씨 — 호(1. 2. …) 문단의 글자모양을 가져다 쓴다
  const cm = /charPrIDRef="(\d+)"/.exec(P.item || "");
  const bodyChar = cm ? cm[1] : null;

  const nodes = [...walk(reg.children)];
  // 아래가 모두 별표뿐인 마디는 제목을 싣지 아니한다
  const onlyAnnex = new Set();
  for (const x of nodes) {
    const ch = x.children || [];
    if (ch.length && ch.every((c) => c.annexRef)) onlyAnnex.add(x);
  }

  let joCnt = 0, objCnt = 0;
  for (const x of nodes) {
    if (x.isDeleted || x.status === "삭제" || x.annexRef) continue;
    if (onlyAnnex.has(x)) continue;
    const lv = x.level, no = x.no, ti = x.title || "";
    if (["편", "장", "절", "관"].includes(lv)) {
      out.push(remake(P.chap, [[null, `제${no}${lv} ${ti}`]]));
      continue;
    }
    if (lv !== "조") continue;
    joCnt += 1;
    const br = x.branch ? `의${x.branch}` : "";
    const lead = `제${no}조${br}(${ti})`;
    const lines = bodyLines(x.body);
    // 조 제목 뒤에 첫 줄을 이어 붙인다 — 고시의 꼴이다
    let first = "";
    if (lines.length && typeof lines[0] === "string") first = lines.shift();
    const runs = [[null, lead]];
    if (first) runs.push([bodyChar, " " + first]);
    out.push(remake(P.art, runs));
    for (const s of lines) {
      if (typeof s === "object") {
        objCnt += 1;
        out.push(remake(P.item, [[null, `[표·수식은 이 문서에 담지 않았습니다 — ${s.obj}]`]]));
        continue;
      }
      out.push(remake(lineProto(P, s), [[null, s]]));
    }
  }

  if (opt.supp) {
    out.push(remake(P.blank, []));
    out.push(remake(P.supp, [[null, "부칙"]]));
    const arr = Array.isArray(opt.supp) ? opt.supp : [opt.supp];
    for (const a of arr) {
      for (const ln of String(a).split(NL)) {
        if (ln.trim()) out.push(remake(P.art, [[null, ln.trim()]]));
      }
    }
  }

  const tops = P.tops;
  f.xml = f.xml.slice(0, tops[0].s) + out.join("") + f.xml.slice(tops[tops.length - 1].e);
  return {
    blob: f.toBlob(),
    name: `${regname} 개정(안).hwpx`.replace(/[\\/:*?"<>|]/g, "_"),
    조: joCnt,
    뺀개체: objCnt,
  };
}
