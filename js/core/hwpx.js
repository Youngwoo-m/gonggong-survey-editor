/* ============================================================
   core/hwpx.js — 양식 파일에 글만 갈아 끼워 한/글 문서를 짓는다
   ------------------------------------------------------------
   scripts/formfill.py 를 브라우저로 옮긴 것이다. 같은 구조라야 웹에서 받은
   문서와 [한글문서만들기.bat] 이 지은 문서가 같아진다.

   ■ 브라우저가 HWPX 를 지을 수 있는가

     지을 수 있다. HWPX 는 ZIP + XML 이고, 파이썬 쪽도 한/글(COM)을 부르지
     않는다 — 순수 ZIP 쓰기다(formfill.Form.save). 다만 **XML 을 다시 쓰면
     안 된다**. 이름공간 접두사(hp:, hh:)가 바뀌면 한/글이 거부한다. 그래서
     여기서도 글자열을 자르고 붙이는 것으로만 다룬다.

   ■ 손댈 때 조심할 것

     ㆍ <hp:linesegarray>(줄 배치 캐시)는 모두 걷어 낸다. 두면 한/글이 옛 줄
       자리를 그대로 믿어 글이 겹쳐 찍히거나 표가 통째로 밀린다.
     ㆍ 첫 문단에는 <hp:secPr>(쪽 설정)가 들어 있다. 지우면 가로쪽과 여백을
       잃는다. 그 문단만은 retext 로 글자만 바꾼다.
     ㆍ mimetype 은 꾸러미 맨 앞에 무압축으로 둔다.
     ㆍ 칸 안에 또 표가 있다. 정규식으로 훑으면 속 표의 행까지 섞이므로
       깊이를 세어 짝을 찾는다(matchClose).
   ============================================================ */

import { readZip } from "./zipreader.js?v=20260907l";
import { createZip } from "./zip.js?v=20260907l";

const RE_T = /<hp:t(?:\s[^>]*)?>([^]*?)<\/hp:t>/g;
const RE_SEG = /<hp:linesegarray>[^]*?<\/hp:linesegarray>|<hp:linesegarray\s*\/>/g;

/** 글 안에 넣을 것. 큰따옴표는 건드리지 아니한다. */
export function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function unesc(s) {
  return String(s).replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

export function stripSeg(x) { return String(x).replace(RE_SEG, ""); }

function textOf(block) {
  let out = "";
  const re = new RegExp(RE_T.source, "g");
  let m;
  while ((m = re.exec(block))) out += m[1];
  return unesc(out);
}

/** pos 부터 훑어 짝이 맞는 닫는 태그 자리 (문단 속 문단ㆍ표 속 표 때문) */
export function matchClose(x, pos, openTag, closeTag) {
  let depth = 0, i = pos;
  for (;;) {
    const a = x.indexOf(openTag, i);
    const b = x.indexOf(closeTag, i);
    if (b < 0) return x.length;
    if (a >= 0 && a < b) { depth += 1; i = a + openTag.length; continue; }
    if (depth === 0) return b;
    depth -= 1;
    i = b + closeTag.length;
  }
}

/* ────────────────────────────────── 양식 파일 */
export class Form {
  constructor(names, blobs) {
    this.names = names;
    this.blobs = blobs;                      // 이름 → Uint8Array
    this.sec = names.find((n) => /^Contents\/section\d+\.xml$/.test(n));
    if (!this.sec) throw new Error("양식에서 본문(section)을 찾지 못했습니다.");
    const dec = new TextDecoder("utf-8");
    this.xml = dec.decode(blobs.get(this.sec));
    this.hname = names.find((n) => n.endsWith("Contents/header.xml")) || null;
    this.hdr = this.hname ? dec.decode(blobs.get(this.hname)) : "";
  }

  static async fetch(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`양식을 가져오지 못했습니다 (${r.status}) — ${url}`);
    const map = await readZip(await r.arrayBuffer());
    // mimetype 은 꾸러미 맨 앞이라야 한다
    const names = [...map.keys()].sort((a, b) =>
      (a === "mimetype" ? -1 : 0) - (b === "mimetype" ? -1 : 0));
    return new Form(names, map);
  }

  /** [{s, e, pp, cp, text, blk, nested}] — 표를 담은 문단도 낸다 */
  paras(xml) {
    const x = xml === undefined ? this.xml : xml;
    const out = [];
    const re = /<hp:p\s[^>]*>/g;
    let m;
    while ((m = re.exec(x))) {
      let e = x.indexOf("</hp:p>", re.lastIndex);
      if (e < 0) continue;
      let span = x.slice(re.lastIndex, e);
      const nested = span.includes("<hp:p ");
      if (nested) {                          // 표를 담은 문단은 끝을 다시 찾는다
        e = matchClose(x, re.lastIndex, "<hp:p ", "</hp:p>");
        span = x.slice(re.lastIndex, e);
      }
      const pid = /paraPrIDRef="(\d+)"/.exec(m[0]);
      const cid = /charPrIDRef="(\d+)"/.exec(span);
      out.push({
        s: m.index, e: e + "</hp:p>".length,
        pp: pid ? pid[1] : "", cp: cid ? cid[1] : "",
        text: textOf(span).trim(),
        blk: x.slice(m.index, e + "</hp:p>".length),
        nested,
      });
    }
    return out;
  }

  /** 맨 바깥 문단만 — 표 안의 문단은 뺀다 */
  topParas() {
    const out = [];
    let last = -1;
    for (const p of this.paras()) {
      if (p.s >= last) { out.push(p); last = p.e; }
    }
    return out;
  }

  /** 있는 글자모양을 본떠 새것을 만든다 → 새 id (붉은 글씨용) */
  newCharPr(srcId, attrs = {}) {
    const m = new RegExp(`<hh:charPr\\b[^>]*\\bid="${srcId}"[^>]*>`).exec(this.hdr);
    if (!m) throw new Error(`글자모양 ${srcId} 가 없습니다`);
    const end = this.hdr.indexOf("</hh:charPr>", m.index + m[0].length)
      + "</hh:charPr>".length;
    let blk = this.hdr.slice(m.index, end);
    const ids = [...this.hdr.matchAll(/<hh:charPr\b[^>]*\bid="(\d+)"/g)]
      .map((x) => +x[1]);
    const next = String(Math.max(...ids) + 1);
    blk = blk.replace(/(\bid=")\d+(")/, `$1${next}$2`);
    for (const [k, v] of Object.entries(attrs)) {
      const head = blk.slice(0, blk.indexOf(">"));
      if (new RegExp(`\\b${k}="[^"]*"`).test(head)) {
        blk = blk.replace(new RegExp(`(\\b${k}=")[^"]*(")`), `$1${v}$2`);
      } else {
        const i = blk.indexOf(">");
        blk = `${blk.slice(0, i)} ${k}="${v}"${blk.slice(i)}`;
      }
    }
    const i = this.hdr.lastIndexOf("</hh:charProperties>");
    this.hdr = this.hdr.slice(0, i) + blk + this.hdr.slice(i);
    this.hdr = this.hdr.replace(/(<hh:charProperties itemCnt=")(\d+)(")/,
      (_a, b, c, d) => b + String(+c + 1) + d);
    return next;
  }

  /** 문단 id 를 하나씩 새로 매긴다 — 본을 복제하면 id 가 겹친다 */
  renumber() {
    let n = 0;
    this.xml = this.xml.replace(/(<hp:p id=")(\d+)(")/g,
      (_m, a, _b, c) => { n += 1; return a + n + c; });
    return n;
  }

  /** 다 채운 뒤 한꺼번에 쓴다 → Blob */
  toBlob() {
    this.renumber();
    const enc = new TextEncoder();
    const out = new Map(this.blobs);
    out.set(this.sec, enc.encode(stripSeg(this.xml)));
    if (this.hname) out.set(this.hname, enc.encode(this.hdr));
    // 탐색기 미리보기 글도 새 글로 — 옛 글이 남으면 딴 문서로 보인다
    for (const n of this.names) {
      if (n.toLowerCase().endsWith("prvtext.txt")) {
        const head = this.paras().slice(0, 40).map((p) => p.text).filter(Boolean);
        out.set(n, enc.encode(head.join("\n")));
      }
    }
    return createZip(this.names.map((n) => ({ name: n, data: out.get(n) })),
                     "application/hwp+zip");
  }
}

/* ────────────────────────────────── 본을 복제해 문단 만들기 */

/**
 * 본 문단을 그대로 베끼되 글만 갈아 끼운다.
 * @param {string} proto 본이 되는 <hp:p>…</hp:p>
 * @param {Array<[string|null,string]>} runs [글자모양 id 또는 null, 글]
 */
export function remake(proto, runs) {
  /* 본이 없으면 여는 태그 없는 문단을 내어 문서가 통째로 깨진다.
     조용히 깨지는 것보다 그 자리에서 멈추는 것이 낫다. */
  if (!proto || typeof proto !== "string" || proto.indexOf("<hp:p") < 0) {
    throw new Error("문단 본을 뜨지 못했습니다 — 양식이 바뀌었는지 보십시오.");
  }
  proto = stripSeg(proto);
  const i = proto.indexOf(">") + 1;
  const openP = proto.slice(0, i);
  const m = /<hp:run\b[^>]*?\/?>/.exec(proto);
  let openR = m ? m[0] : '<hp:run charPrIDRef="0">';
  // 본의 run 이 자기닫힘(<hp:run …/>)일 때가 있다 — 빈 문단이 그렇다
  if (openR.endsWith("/>")) openR = `${openR.slice(0, -2)}>`;
  const body = [];
  for (const [cid, t] of runs) {
    const r = cid
      ? openR.replace(/charPrIDRef="\d+"/, `charPrIDRef="${cid}"`)
      : openR;
    body.push(`${r}<hp:t>${esc(t)}</hp:t></hp:run>`);
  }
  if (!body.length) body.push(`${openR.slice(0, -1)}/>`);
  return openP + body.join("") + "</hp:p>";
}

/**
 * 본 문단의 글만 갈아 끼운다 — 딸린 것을 지켜야 할 때.
 *
 * 첫 문단에는 <hp:secPr>(쪽 설정)가 run 안에 들어 있다. remake 는 run 을
 * 새로 짓느라 그것을 버리므로, 첫 문단만은 이 함수로 글자만 바꾼다.
 */
export function retext(proto, text) {
  proto = stripSeg(proto);
  let done = false;
  return proto.replace(new RegExp(RE_T.source, "g"), () => {
    if (done) return "<hp:t></hp:t>";
    done = true;
    return `<hp:t>${esc(text)}</hp:t>`;
  });
}

/** 줄바꿈에서 문단을 가른다 → [[[글자모양, 글], …], …] */
export function splitParas(runs) {
  const out = [];
  let cur = [];
  for (const [cid, t] of runs) {
    const parts = String(t).split("\n");
    parts.forEach((s, k) => {
      if (k) { out.push(cur); cur = []; }
      if (s) cur.push([cid, s]);
    });
  }
  out.push(cur);
  const got = out.filter((p) => p.length);
  return got.length ? got : [[]];
}

/* ────────────────────────────────── 표 */

/** 겉 표의 <hp:tr> 만 — 칸 안에 또 표가 있어도 속지 않는다 */
export function topRows(tblXml) {
  const out = [];
  let i = tblXml.indexOf("<hp:tr>");
  while (i >= 0) {
    const e = matchClose(tblXml, i + "<hp:tr>".length, "<hp:tr>", "</hp:tr>");
    out.push(tblXml.slice(i, e + "</hp:tr>".length));
    i = tblXml.indexOf("<hp:tr>", e + "</hp:tr>".length);
  }
  return out;
}

/** 한 행의 <hp:tc> 만 */
export function topCells(trXml) {
  const out = [];
  let i = trXml.indexOf("<hp:tc ");
  while (i >= 0) {
    const e = matchClose(trXml, i + "<hp:tc ".length, "<hp:tc ", "</hp:tc>");
    out.push(trXml.slice(i, e + "</hp:tc>".length));
    i = trXml.indexOf("<hp:tc ", e + "</hp:tc>".length);
  }
  return out;
}

/** 양식의 한 행을 본으로 삼아 새 행을 찍어 낸다 */
export class RowProto {
  constructor(trXml) {
    this.tcs = topCells(trXml);
    this.widths = this.tcs.map((tc) => {
      const m = /<hp:cellSz width="(\d+)"/.exec(tc);
      return m ? +m[1] : 5000;
    });
  }

  paraProto(col = 0) {
    const tc = this.tcs[Math.min(col, this.tcs.length - 1)];
    const m = /<hp:p\s[^>]*>/.exec(tc);
    const e = tc.indexOf("</hp:p>", m.index + m[0].length);
    return tc.slice(m.index, e + "</hp:p>".length);
  }

  /** cols 는 칸마다의 문단 XML 묶음 → <hp:tr> 한 줄 */
  make(rowNo, cols) {
    const out = ["<hp:tr>"];
    cols.forEach((body, i) => {
      const tc = this.tcs[Math.min(i, this.tcs.length - 1)];
      const head = tc.slice(0, tc.indexOf(">") + 1);
      const sl = /<hp:subList\b[^>]*>/.exec(tc)[0];
      const mg = /<hp:cellMargin\b[^>]*\/>/.exec(tc);
      out.push(head + sl + body + "</hp:subList>"
        + `<hp:cellAddr colAddr="${i}" rowAddr="${rowNo}"/>`
        + '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        + `<hp:cellSz width="${this.widths[Math.min(i, this.widths.length - 1)]}"`
        + ' height="2000"/>'
        + (mg ? mg[0] : "")
        + "</hp:tc>");
    });
    out.push("</hp:tr>");
    return out.join("");
  }
}

/**
 * 칸마다 병합과 폭을 달리하여 한 줄을 찍는다 (formdocs 의 make_spec).
 * @param {number} rowNo 몇째 줄인가
 * @param {Array<{body:string,col:number,cs:number,rs:number,w:number}>} spec
 */
RowProto.prototype.makeSpec = function makeSpec(rowNo, spec) {
  const out = ["<hp:tr>"];
  for (const c of spec) {
    const tc = this.tcs[Math.min(c.col, this.tcs.length - 1)];
    const head = tc.slice(0, tc.indexOf(">") + 1);
    const sl = /<hp:subList\b[^>]*>/.exec(tc)[0];
    const mg = /<hp:cellMargin\b[^>]*\/>/.exec(tc);
    out.push(head + sl + c.body + "</hp:subList>"
      + `<hp:cellAddr colAddr="${c.col}" rowAddr="${rowNo}"/>`
      + `<hp:cellSpan colSpan="${c.cs || 1}" rowSpan="${c.rs || 1}"/>`
      + `<hp:cellSz width="${c.w || 5000}" height="2000"/>`
      + (mg ? mg[0] : "") + "</hp:tc>");
  }
  out.push("</hp:tr>");
  return out.join("");
};

/** n 번째 겉 <hp:tbl> 의 [시작, 끝] */
export function tableSpan(xml, n = 0) {
  let i = -1;
  for (let k = 0; k <= n; k++) {
    i = xml.indexOf("<hp:tbl ", i + 1);
    if (i < 0) return null;
  }
  const e = matchClose(xml, i + "<hp:tbl ".length, "<hp:tbl ", "</hp:tbl>");
  return [i, e + "</hp:tbl>".length];
}

/**
 * 표의 행을 통째로 갈아 끼우고 행 수를 고친다.
 *
 * 행이 많으면 '글자처럼 취급'(treatAsChar)을 푼다. 한/글은 글자처럼 취급하는
 * 표를 쪽 경계에서 쪼개지 못해, 한 쪽에도 못 들어갈 만큼 길면 아예 보이지
 * 아니한다.
 */
export function retable(tblXml, rowsXml, rowCnt, uncharOver = 10) {
  let head = tblXml.slice(0, tblXml.indexOf("<hp:tr>"));
  head = head.replace(/(\browCnt=")\d+(")/, `$1${rowCnt}$2`);
  if (rowCnt > uncharOver) {
    head = head.replace('treatAsChar="1"', 'treatAsChar="0"');
  }
  return head + rowsXml + "</hp:tbl>";
}
