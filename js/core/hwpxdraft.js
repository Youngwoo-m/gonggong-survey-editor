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

import { Form, remake, retext, esc, RowProto, tableSpan, topRows, retable }
  from "./hwpx.js?v=20260907l";

const NL = "\n";
const RE_IMG = /<img\s+id="([\w.-]+)"\s*>(?:<\/img>)?/gi;
const RE_PROV = /<현행[^<>]*>|<신설[^<>]*>/g;      // 출처 표시는 고시에 싣지 아니한다
/* 자바스크립트의 \b 는 낱말 글자를 [A-Za-z0-9_] 로만 본다. 한글은 낱말
   글자가 아니어서 「제1장 통칙」 의 장과 빈칸 사이에 경계가 서지 아니하고,
   그래서 이 자가 하나도 걸리지 아니하였다 —— 본을 못 뜨면 remake 가 여는
   태그 없는 문단을 내어 문서가 깨진다. */
const RE_CHAP = /^제\s*\d+\s*(편|장|절|관)(?:\s|$)/;
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
function bodyLines(text, keep) {
  /* 한/글로 낼 때에는 출처 표시를 지우지 아니한다 —— 지우면 되읽어 올 때
     본문이 줄어 그만큼 잃는다(제2조가 1,299자에서 1,208자가 되었다). */
  const t = keep ? String(text || "")
                 : String(text || "").replace(RE_PROV, "");
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


/* ────────────────────────────────── 본문 속 개체 (표ㆍ수식)

   조문 본문에는 <img id="…"> 로 자리만 있고 알맹이는 data/objects 에
   XML 로 있다. formdocs.object_table / object_equation 을 옮긴 것이다.
   원본의 칸 폭과 병합(colspan/rowspan)과 머리 칸을 그대로 살린다. */

const BODYW = 45356;                 // 본문 폭 (양식과 같은 값)

const OBJ_DIRS = ["draft2025", "draftSimsa", "draftUav", "reg01", "reg12"];
const PIC_EXT = { gif: "image/gif", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", bmp: "image/bmp" };

/**
 * 개체를 받아 온다 —— 규정 자리를 차례로 짚어 본다.
 * 표ㆍ수식은 XML 이므로 글로, 그림은 그림 파일이므로 바이트로 낸다.
 * @returns {Promise<string|{pic:Uint8Array, ext:string}|null>}
 */
async function fetchObject(oid, regId) {
  const rids = [regId, ...OBJ_DIRS].filter(Boolean);
  const seen = new Set();
  const dirs = rids.filter((r) => (seen.has(r) ? false : seen.add(r)));
  const at = (dir, ext) => `data/objects/${encodeURIComponent(dir)}/${encodeURIComponent(oid)}.${ext}`;
  const urls = dirs.map((d) => at(d, "xml"));
  urls.push(`data/objects/${encodeURIComponent(oid)}.xml`);   // 꾸러미는 평평하다
  for (const e of Object.keys(PIC_EXT)) for (const d of dirs) urls.push(at(d, e));
  for (const u of urls) {
    try {
      const r = await fetch(new URL(u, document.baseURI).href, { cache: "no-cache" });
      if (!r.ok) continue;
      if (u.endsWith(".xml")) return await r.text();
      const ext = u.slice(u.lastIndexOf(".") + 1).toLowerCase();
      return { pic: new Uint8Array(await r.arrayBuffer()), ext };
    } catch { /* 다음 자리를 본다 */ }
  }
  return null;
}

/** 그림의 가로ㆍ세로 (낱눈) —— 못 읽으면 null */
function picSize(b) {
  const be = (i, n) => { let v = 0; for (let k = 0; k < n; k++) v = v * 256 + b[i + k]; return v; };
  if (b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46) {          // GIF
    return { w: b[6] | (b[7] << 8), h: b[8] | (b[9] << 8) };
  }
  if (b[0] === 0x89 && b[1] === 0x50) {                            // PNG
    return { w: be(16, 4), h: be(20, 4) };
  }
  if (b[0] === 0xff && b[1] === 0xd8) {                            // JPEG
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xff) { i += 1; continue; }
      const m = b[i + 1];
      if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
        return { h: be(i + 5, 2), w: be(i + 7, 2) };
      }
      i += 2 + be(i + 2, 2);
    }
  }
  return null;
}

/* 그림 하나를 꾸러미에 넣고 <hp:pic> 문단을 낸다. 낱눈 하나는 75 이다
   (한 치가 7200 이고 한 치에 96 낱눈이 든다). */
let picNo = 0;
function objectPicture(P, f, src, oid) {
  if (!src || !src.pic || !PIC_EXT[src.ext]) return null;
  const sz = picSize(src.pic);
  if (!sz || !sz.w || !sz.h) return null;
  picNo += 1;
  const iid = `image${picNo}_${oid}`;
  const name = `BinData/${iid}.${src.ext}`;
  if (!f.blobs.has(name)) {
    f.blobs.set(name, src.pic);
    f.names.push(name);
    const hpf = f.names.find((n) => n.endsWith("content.hpf"));
    if (!hpf) return null;
    const dec = new TextDecoder("utf-8");
    let x = dec.decode(f.blobs.get(hpf));
    const i = x.lastIndexOf("</opf:manifest>");
    if (i < 0) return null;
    x = x.slice(0, i) + `<opf:item id="${iid}" href="${name}"`
      + ` media-type="${PIC_EXT[src.ext]}" isEmbeded="1"/>` + x.slice(i);
    f.blobs.set(hpf, new TextEncoder().encode(x));
  }
  const ow = sz.w * 75, oh = sz.h * 75;
  const k = ow > BODYW ? BODYW / ow : 1;
  const cw = Math.round(ow * k), ch = Math.round(oh * k);
  const pic = `<hp:pic id="${1790000000 + picNo}" zOrder="${200 + picNo}"`
    + ` numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES"`
    + ` lock="0" dropcapstyle="None" href="" groupLevel="0"`
    + ` instid="${1890000000 + picNo}" reverse="0">`
    + `<hp:offset x="0" y="0"/><hp:orgSz width="${ow}" height="${oh}"/>`
    + `<hp:curSz width="${cw}" height="${ch}"/>`
    + `<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0"/>`
    + `<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>`
    + `<hc:scaMatrix e1="${k.toFixed(4)}" e2="0" e3="0" e4="0" e5="${k.toFixed(4)}" e6="0"/>`
    + `<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>`
    + `<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="${ow}" y="0"/>`
    + `<hc:pt2 x="${ow}" y="${oh}"/><hc:pt3 x="0" y="${oh}"/></hp:imgRect>`
    + `<hp:imgClip left="0" right="${ow}" top="0" bottom="${oh}"/>`
    + `<hp:inMargin left="0" right="0" top="0" bottom="0"/>`
    + `<hp:imgDim dimwidth="${ow}" dimheight="${oh}"/>`
    + `<hc:img binaryItemIDRef="${iid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>`
    + `<hp:effects/>`
    + `<hp:sz width="${cw}" widthRelTo="ABSOLUTE" height="${ch}" heightRelTo="ABSOLUTE" protect="0"/>`
    + `<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0"`
    + ` holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP"`
    + ` horzAlign="LEFT" vertOffset="0" horzOffset="0"/>`
    + `<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic>`;
  return wrapInline(P.item, pic);
}

/** 본 문단 안에 개체 한 덩이만 넣은 <hp:p> 를 낸다 */
function wrapInline(proto, inner) {
  const i = proto.indexOf(">") + 1;
  const r = /<hp:run\b[^>]*?\/?>/.exec(proto);
  let run = r ? r[0] : '<hp:run charPrIDRef="0">';
  if (run.endsWith("/>")) run = run.slice(0, -2) + ">";
  return proto.slice(0, i) + run + inner + "</hp:run></hp:p>";
}

const unesc = (s) => String(s)
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");

/** 개체 XML → {cw, rows} —— 칸은 {t, col, cs, rs, head} */
function parseTable(src) {
  const tag = /<table\s[^>]*>/.exec(src);
  let cw = null;
  if (tag) {
    const m = /cw="([^"]*)"/.exec(tag[0]);
    if (m) cw = m[1].split(",").map((v) => v.trim()).filter((v) => /^\d+$/.test(v)).map(Number);
  }
  const rows = [];
  for (const rm of src.matchAll(/<row>([^]*?)<\/row>/g)) {
    const cells = [];
    for (const cm of rm[1].matchAll(/<cell([^>]*)>([^]*?)<\/cell>/g)) {
      const a = cm[1];
      const num = (k, d) => {
        const g = new RegExp(`\\b${k}="(\\d+)"`).exec(a);
        return g ? +g[1] : d;
      };
      cells.push({
        t: unesc(cm[2]), col: num("col", cells.length),
        cs: num("colspan", 1), rs: num("rowspan", 1),
        head: num("header", 0) === 1,
      });
    }
    if (cells.length) rows.push(cells);
  }
  return { cw, rows };
}

/** 칸 폭 —— 원본 폭이 있으면 그것을, 없으면 글 길이로 나눈다 */
function fitWidths(cw, ncol, rows, body = BODYW) {
  let w;
  if (cw && cw.length === ncol && cw.reduce((a, b) => a + b, 0) > 0) {
    w = cw.slice();
  } else {
    const avg = [];
    for (let i = 0; i < ncol; i++) {
      const xs = [];
      for (const r of rows) for (const c of r) if (c.col === i && c.cs === 1) xs.push(c.t.length);
      avg.push(xs.length ? Math.max(xs.reduce((a, b) => a + b, 0) / xs.length, 3) : 3);
    }
    const tot = avg.reduce((a, b) => a + b, 0) || 1;
    w = avg.map((a) => Math.max(1200, Math.round(a * body / tot)));
  }
  const s0 = w.reduce((a, b) => a + b, 0);
  if (s0 > body) w = w.map((v) => Math.max(900, Math.round(v * body / s0)));
  const s1 = w.reduce((a, b) => a + b, 0);
  w[w.length - 1] += body - s1;
  return w;
}

/** 표 개체 → 양식의 표를 본으로 삼은 <hp:p>. 못 만들면 null */
function objectTable(P, src) {
  if (typeof src !== "string" || src.indexOf("<table") < 0 || !P.tbl) return null;
  const { cw, rows } = parseTable(src);
  if (!rows.length) return null;
  let ncol = 1;
  for (const r of rows) for (const c of r) ncol = Math.max(ncol, c.col + c.cs);
  const w = fitWidths(cw, ncol, rows);
  const blk = P.tbl;
  const span = tableSpan(blk);
  if (!span) return null;
  const tbl = blk.slice(span[0], span[1]);
  const trs = topRows(tbl);
  const headProto = new RowProto(trs[0]);
  const dataProto = new RowProto(trs[1] || trs[0]);
  const made = [];
  rows.forEach((cells, ri) => {
    const pr = (ri === 0 || cells.some((c) => c.head)) ? headProto : dataProto;
    const spec = cells.map((c) => {
      const i = Math.min(c.col, ncol - 1);
      const wid = w.slice(i, i + c.cs).reduce((a, b) => a + b, 0) || w[i];
      const paras = String(c.t).split(NL);
      const body = (paras.length ? paras : [""])
        .map((x) => remake(pr.paraProto(i), [[null, x.trim()]])).join("");
      return { body, col: i, cs: c.cs, rs: c.rs, w: wid };
    });
    made.push(pr.makeSpec(ri, spec));
  });
  let tbl2 = tbl.replace(/(\bcolCnt=")\d+(")/, `$1${ncol}$2`);
  tbl2 = tbl2.replace(/(<hp:sz width=")\d+(")/,
    `$1${w.reduce((a, b) => a + b, 0)}$2`);
  return blk.slice(0, span[0]) + retable(tbl2, made.join(""), rows.length)
    + blk.slice(span[1]);
}

/* 한/글 수식 개체의 본 —— formdocs 의 EQ_PROTO 를 그대로 옮긴 것이다 */
let eqNo = 0;
function objectEquation(P, src) {
  if (typeof src !== "string" || src.indexOf("<equation") < 0) return null;
  let m = /<script>([^]*?)<\/script>/.exec(src);
  if (!m) m = /<readable>([^]*?)<\/readable>/.exec(src);
  if (!m) return null;
  const script = unesc(m[1].trim());
  eqNo += 1;
  const eq = '<hp:equation id="' + (1990000000 + eqNo) + '" zOrder="' + (100 + eqNo) + '"'
    + ' numberingType="EQUATION" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES"'
    + ' lock="0" dropcapstyle="None" version="Equation Version 60" baseLine="66"'
    + ' textColor="#000000" baseUnit="1000" lineMode="CHAR" font="HYhwpEQ">'
    + '<hp:sz width="' + Math.max(2000, script.length * 500) + '" widthRelTo="ABSOLUTE"'
    + ' height="2250" heightRelTo="ABSOLUTE" protect="0"/>'
    + '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0"'
    + ' holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP"'
    + ' horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
    + '<hp:outMargin left="56" right="56" top="0" bottom="0"/>'
    + '<hp:shapeComment>수식입니다.</hp:shapeComment>'
    + '<hp:script>' + esc(script) + '</hp:script></hp:equation>';
  return wrapInline(P.item, eq);
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

  /* 조문에 박힌 개체를 한꺼번에 받아 둔다 —— 하나씩 기다리면 조가 253개일 때
     하염없이 느리다. 못 받은 것은 그 자리에 한 줄로 밝힌다. */
  const want = new Set();
  for (const x of nodes) {
    if (x.isDeleted || x.status === "삭제") continue;
    for (const ln of bodyLines(x.body, true)) {
      if (typeof ln === "object") want.add(ln.obj);
    }
  }

  const objs = new Map();
  await Promise.all([...want].map(async (oid) => {
    objs.set(oid, await fetchObject(oid, opt.regId));
  }));

  let joCnt = 0, objCnt = 0, tblCnt = 0, eqCnt = 0, picCnt = 0;
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
    const lines = bodyLines(x.body, true);
    /* 조 제목 뒤에 첫 줄을 이어 붙인다 — 고시의 꼴이다. 다만 첫 줄이
       호(1.)나 항(①)이면 붙이지 아니한다 —— 붙이면 되받을 때 그 줄이
       제목의 꼬리로 읽혀 본문에서 사라진다. */
    const LIST0 = /^(?:[0-9]+\s*[.)]|[가-힣]\s*[.)]|[①-⑳]|[０-９])/;
    let first = "";
    if (lines.length && typeof lines[0] === "string" && !LIST0.test(lines[0])) {
      first = lines.shift();
    }
    const runs = [[null, lead]];
    if (first) runs.push([bodyChar, " " + first]);
    out.push(remake(P.art, runs));
    for (const s of lines) {
      if (typeof s === "object") {
        const src = objs.get(s.obj);
        const t = objectTable(P, src) || objectEquation(P, src)
          || objectPicture(P, f, src, s.obj);
        if (t) {
          if (typeof src !== "string") picCnt += 1;
          else if (src.indexOf("<table") >= 0) tblCnt += 1;
          else eqCnt += 1;
          out.push(t);
        } else {
          objCnt += 1;
          out.push(remake(P.item, [[null, `[개체 ${s.obj} 를 찾지 못했습니다]`]]));
        }
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
    표: tblCnt,
    수식: eqCnt,
    그림: picCnt,
    뺀개체: objCnt,
  };
}
