/* ============================================================
   core/objects.js — 본문 속 '그림으로 된' 표·수식
   ------------------------------------------------------------
   국가법령정보센터 본문은 표와 수식을 이미지로 넣어 두었다 (<img id="…">).
   scripts/genobjects.py 가 원본 HWPX 에서 그것을 XML 로 바꿔 놓았고,
   여기서는 그 XML 을 읽어 화면에 진짜 표로 그린다.
   ============================================================ */

import { toMathML } from "./eqmath.js?v=20260822u";

const RE_IMG = /<img\s+id="([\w.-]+)"\s*>(?:<\/img>)?/gi;
// 본문이 인용하는 다른 규정 — 「…」 / 『…』
// 뒤에 딸린 '제○조' 까지 함께 잡아 그 조로 바로 갈 수 있게 한다.
const RE_CITE = /([「『])([^」』\r\n]{2,80})([」』])(\s*제\s*(\d+)\s*조(?:의\s*\d+)?)?/g;

/**
 * 본문의 「…」 인용을 링크로 바꾼다.
 * 「도로법」 제2조 처럼 조가 딸려 있으면 그 조 번호까지 실어 보낸다.
 * @param {string} html 이미 escape 된 글
 * @param {(name:string)=>string|null} resolve 규정명 → 규정 id (없으면 null)
 */
export function linkCitations(html, resolve) {
  if (!resolve) return html;
  return String(html).replace(RE_CITE, (m, open, name, close, joTxt, joNo) => {
    const id = resolve(name);
    if (!id) return m;
    const tail = joTxt || "";                  // '제2조' 는 글 그대로 둔다
    const tip = joNo ? `${name} 제${joNo}조 — 참조규정 창에서 엽니다`
                     : "참조규정 창에서 엽니다";
    return `${open}<a class="cite" href="#" data-reg="${esc(id)}" data-jo="${esc(joNo || "")}"`
      + ` title="${esc(tip)}">${name}</a>${close}${tail}`;
  });
}

/**
 * 약칭으로 하는 법령 인용 — "법 제7조", "같은 법 시행령 제8조", "영 제7조제2항"
 * 앞에 한글·영문이 붙으면 잡지 않는다 ("방법 제7조" 같은 오인식을 막는다).
 */
const RE_LAW = /(?<![가-힣A-Za-z])(같은\s*법\s*시행규칙|같은법\s*시행규칙|같은\s*법\s*시행령|같은법\s*시행령|시행규칙|시행령|같은\s*법|같은법|법률|법|영|규칙)\s*(제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?)/g;

/**
 * 약칭 법령 인용을 링크로 바꾼다.
 * @param {string} html 이미 escape 된 글
 * @param {(word:string)=>{id:string,name:string}|null} resolveLaw 약칭 → 규정
 */
export function linkLawRefs(html, resolveLaw) {
  if (!resolveLaw) return html;
  return String(html).replace(RE_LAW, (m, word, jo) => {
    const hit = resolveLaw(word.replace(/\s+/g, " ").trim());
    if (!hit) return m;
    const no = (jo.match(/제\s*(\d+)\s*조/) || [])[1] || "";
    return `<a class="cite law" href="#" data-reg="${esc(hit.id)}" data-jo="${esc(no)}"`
      + ` title="${esc(hit.name)} ${esc(jo)} — 참조규정 창에서 엽니다">${word} ${jo}</a>`;
  });
}

/**
 * 같은 규정 안의 조문 인용 — "제12조", "제12조의2", "제12조제3항"
 * 앞에 약칭 법령 이름이 붙은 것(법 제7조)은 linkLawRefs 가 이미 링크로 바꾸었으므로
 * 이미 <a> 안에 든 글은 건드리지 아니한다.
 */
const RE_JO = /(?<!<[^>]{0,80})(?<![가-힣A-Za-z])(제\s*(\d+)\s*조(?:의\s*\d+)?)((?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?)/g;

/* 앞의 법령 이름이 어디까지 미치는가 —
   「도로법」 제2조 및 제5조, 제7조 처럼 이음말로 이어진 조는 모두 그 법의 조이다.
   이음말과 조문 나열을 규칙 안에 넣어, 나열이 아무리 길어도 놓치지 않는다. */
const CONN = "[\\s및과와,·’”\\)\\]]";
/* 범위로 이은 것도 그 법의 조다 — 「도로법」제2조부터 제5조까지.
   이음말 글자(CONN)만으로는 '부터·까지·내지' 를 넘지 못해, 그 제5조를 이 규정의
   제5조로 이어 링크를 걸고 검증에서도 없는 조라고 짚고 있었다. */
const RANGE = "(?:부터|까지|내지)";
const CONN2 = `(?:${CONN}|${RANGE})`;
const CHAIN = `(?:${CONN2}*제\\s*\\d+\\s*조(?:의\\s*\\d+)?(?:\\s*제\\s*\\d+\\s*[항호])*)*${CONN2}*$`;
/* 법령 이름 뒤에 약칭을 괄호로 다는 자리 — 「…법률」(이하 "법"이라 한다) 제2조제3호.
   이 괄호를 넘기지 못해 그 제2조를 이 규정의 제2조로 잇고 있었다. 괄호 안에는
   따옴표와 한글이 들어 이음말 규칙(CONN)으로는 넘을 수 없다. */
const ASIDE = `(?:\\s*[\\(（][^()（）]{0,40}[\\)）])?`;
const AFTER_LINK = new RegExp(`^${ASIDE}${CHAIN}`);             // 바로 앞 도막이 법령 링크였다
const AFTER_CITE = new RegExp(`[」』]${ASIDE}${CHAIN}`);         // 「규정 이름」 뒤
const AFTER_WORD = new RegExp(                                 // 법·영·규칙·시행령 뒤
  `(?<![가-힣A-Za-z])(?:시행규칙|시행령|법률|법|영|규칙)${CHAIN}`);
/* 「…작업규정」에 따르며, 그 규정 제20조제1항 단서에 따라 —
   '그 규정' 은 방금 든 그 규정을 가리키므로 이 규정의 조가 아니다.
   이음말만으로는 '에 따르며,' 를 넘지 못해 개정안 제113조가 잘못 이어졌다. */
const AFTER_THAT = new RegExp(`(?:그|같은|해당|당해|위)\\s*(?:규정|고시|규칙|지침|기준)${CHAIN}`);
/* 출처 표시 — <현행 제168조 「정의」>. 여기 적힌 번호는 현행 규정의 조이지
   이 안의 조가 아니다. 글로 새겨진 뒤라 &lt;현행 … 으로 남아 있다. */
const IN_PROV = /&lt;현행(?:(?!&gt;)[^])*$/;

/**
 * 이 자리의 "제N조" 가 이 규정의 조를 가리키는가.
 *
 * 링크를 그리는 데에도, 규정을 넘어 옮긴 뒤 인용 표기를 고쳐 쓰는 데에도,
 * 규정 사이 인용이 성한지 보는 데에도 같은 판정이 필요하다. 한 곳에 둔다 —
 * 여기가 갈라지면 화면에 보이는 링크와 검증 결과가 서로 어긋난다.
 *
 * @param {string} before  그 "제N조" 앞에 있는 글 (도막 첫머리부터)
 * @param {boolean} afterLaw 바로 앞 도막이 약칭 법령 링크였는가
 */
export function isSelfCite(before, afterLaw = false) {
  if (afterLaw && AFTER_LINK.test(before)) return false;   // 「법 제18조」 및 제105조
  if (AFTER_CITE.test(before)) return false;               // 「도로법」 제2조 및 제5조
  if (AFTER_WORD.test(before)) return false;               // 시행령 제34조 및 제35조
  if (AFTER_THAT.test(before)) return false;               // 그 규정 제20조
  if (IN_PROV.test(before)) return false;                  // <현행 제168조 「정의」>
  return true;
}

/** 조문 인용을 찾는 규칙 — 글 위에서 그대로 쓰라고 내준다 */
export const RE_JO_G = () => new RegExp(RE_JO.source, "g");

/**
 * 같은 규정 안의 조문 인용을 링크로 바꾼다.
 * @param {string} html 이미 escape 된 글
 * @param {(no:number)=>boolean} hasJo 그 조가 이 규정에 있는지
 */
export function linkSelfRefs(html, hasJo) {
  if (!hasJo) return html;
  // 이미 링크가 된 데(「…」 인용·약칭 법령)는 건드리지 아니한다
  let lawBefore = false;                 // 바로 앞 도막이 약칭 법령 링크였는가
  return String(html).split(new RegExp('(<a[^]*?<\/a>)')).map((seg) => {
    if (seg.startsWith("<a")) {
      lawBefore = /class="cite/.test(seg);      // 법령이든 규정 이름이든
      return seg;
    }
    const afterLaw = lawBefore;
    lawBefore = false;
    return seg.replace(RE_JO, (m, jo, no, tail, off, whole) => {
      if (!hasJo(+no)) return m;
      // 앞의 법령 인용이 미치는 자리인가 — 그렇다면 이 규정의 조가 아니다
      const before = whole.slice(0, off);       // 도막 첫머리부터 본다 (나열이 길어도 놓치지 않게)
      if (!isSelfCite(before, afterLaw)) return m;
      return `<a class="cite self" href="#" data-jo="${esc(no)}"`
        + ` title="이 규정의 ${esc(jo)} 로 갑니다">${jo}</a>${tail}`;
    });
  }).join("");
}

/** 본문에 박혀 있는 이미지 표식들의 id */
export function imgIdsIn(text) {
  const out = [];
  RE_IMG.lastIndex = 0;
  let m;
  while ((m = RE_IMG.exec(String(text || "")))) out.push(m[1]);
  return out;
}

/** 이미지 표식을 사람이 읽을 수 있는 자리표시로 바꾼다 (검증·비교표용) */
export function stripImgTags(text, label = (i, id) => `[표·수식 ${i}]`) {
  let i = 0;
  return String(text || "").replace(RE_IMG, (_m, id) => label(++i, id));
}

export class ObjectStore {
  constructor() {
    this.index = {};        // regId -> { imgId: meta }   본문 속 표·수식
    this.annex = {};        // regId -> { "별표1": meta }  별표·별지 원본 표
    this.cache = new Map();
  }

  setIndex(regId, idx) { this.index[regId] = idx || {}; }
  meta(regId, imgId) { return (this.index[regId] || {})[imgId] || null; }
  has(regId, imgId) { return !!this.meta(regId, imgId); }

  setAnnexIndex(regId, idx) { this.annex[regId] = idx || {}; }
  /** node.legacyNo("별표 1") 또는 "별표1" 로 찾는다 */
  annexMeta(regId, key) {
    return (this.annex[regId] || {})[String(key || "").replace(/\s+/g, "")] || null;
  }
  annexUrl(regId, key) {
    const m = this.annexMeta(regId, key);
    return m ? `data/objects/${encodeURIComponent(regId)}/annex/${encodeURIComponent(m.file)}` : "";
  }
  async getAnnex(regId, key) {
    const url = this.annexUrl(regId, key);
    if (!url) return null;
    if (this.cache.has(url)) return this.cache.get(url);
    // 데이터가 바뀌면 곧바로 따라오도록 늘 새로 확인한다 (loadJSON 과 같은 규칙)
    const p = fetch(url, { cache: "no-cache" })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.text(); })
      .then((t) => parseXml(t))
      .catch(() => null);
    this.cache.set(url, p);
    return p;
  }

  /** XML 을 읽어 구조로 바꾼다 (한 번만 내려받고 담아 둔다) */
  async get(regId, imgId) {
    const key = `${regId}/${imgId}`;
    if (this.cache.has(key)) return this.cache.get(key);
    const p = fetch(this.url(regId, imgId), { cache: "no-cache" })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.text(); })
      .then((t) => parseXml(t))
      .catch(() => null);
    this.cache.set(key, p);
    return p;
  }

  url(regId, imgId) {
    return `data/objects/${encodeURIComponent(regId)}/${encodeURIComponent(imgId)}.xml`;
  }
}

/** XML 문자열 → {kind, …} */
export function parseXml(text) {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) return null;
  const root = doc.documentElement;

  if (root.tagName === "equation") {
    return {
      kind: "equation",
      id: root.getAttribute("id") || "",
      article: root.getAttribute("article") || "",
      script: root.querySelector("script")?.textContent || "",
      readable: root.querySelector("readable")?.textContent || "",
      latex: root.querySelector("latex")?.textContent || "",
    };
  }

  if (root.tagName === "annex") {
    const items = [];
    for (const el of root.children) {
      if (el.tagName === "text") items.push({ kind: "text", text: el.textContent || "" });
      else if (el.tagName === "table") items.push(readTable(el));
      // 표가 아니라 그림으로 된 별표 (배치도 등) — 원본에서 꺼내 둔 그림을 그대로 보인다
      else if (el.tagName === "image") {
        items.push({
          kind: "image",
          src: el.getAttribute("src") || "",
          w: +el.getAttribute("w") || 0,
          h: +el.getAttribute("h") || 0,
          row: +el.getAttribute("row") || 0,
          alt: el.getAttribute("alt") || "",
        });
      }
    }
    return {
      kind: "annex",
      id: root.getAttribute("id") || "",
      gubun: root.getAttribute("gubun") || "별표",
      no: root.getAttribute("no") || "",
      title: root.getAttribute("title") || "",
      source: root.getAttribute("source") || "",
      items,
    };
  }

  return readTable(root);
}

function readTable(root) {
  const rows = [...root.querySelectorAll("row")].map((r) =>
    [...r.querySelectorAll("cell")].map((c) => ({
      col: +c.getAttribute("col") || 0,
      row: +c.getAttribute("row") || 0,
      colspan: +c.getAttribute("colspan") || 1,
      rowspan: +c.getAttribute("rowspan") || 1,
      header: c.getAttribute("header") === "1",
      text: c.textContent || "",
    })));

  return {
    kind: "table",
    id: root.getAttribute("id") || "",
    article: root.getAttribute("article") || "",
    rows,
    rowCnt: +root.getAttribute("rows") || rows.length,
    colCnt: +root.getAttribute("cols") || 0,
    source: root.getAttribute("source") || "",
  };
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** m_3, 10^-6 처럼 남은 위·아래 첨자를 진짜 첨자로 */
function supSub(s) {
  return esc(s)
    .replace(/\^\{?(-?[0-9A-Za-z.+]+)\}?/g, "<sup>$1</sup>")
    .replace(/_\{?(-?[0-9A-Za-z.+가-힣]+)\}?/g, "<sub>$1</sub>");
}

/** 구조 → 화면에 그릴 HTML */
export function toHtml(obj) {
  if (!obj) return `<div class="obj-fail">이 표·수식은 아직 XML 로 바꾸지 못했습니다.</div>`;

  if (obj.kind === "annex") {
    // 같은 row 를 받은 그림은 한 줄에 나란히 둔다 — 넓이는 원본 가로 비로 나눈다
    const out = [];
    let row = null, buf = [];
    const flush = () => {
      if (!buf.length) return;
      out.push(`<div class="annex-imgrow">${buf.join("")}</div>`);
      buf = [];
    };
    const fig = (it) => `<figure class="annex-img" style="flex:${it.w || 1} 1 0">
      <img loading="lazy" src="${esc(it.src)}" alt="${esc(it.alt)}"${
        it.w ? ` width="${it.w}" height="${it.h}"` : ""}></figure>`;
    for (const it of obj.items) {
      if (it.kind === "image") {
        if (row !== null && it.row !== row) flush();
        row = it.row;
        buf.push(fig(it));
        continue;
      }
      flush(); row = null;
      out.push(it.kind === "text" ? `<div class="bd-text">${esc(it.text)}</div>` : toHtml(it));
    }
    flush();
    return out.join("");
  }

  if (obj.kind === "equation") {
    // 원문처럼 그린다. 못 바꾸면 글로 적은 것을 그대로 보인다.
    const math = toMathML(obj.script);
    const head = math
      ? `<div class="eq-math">${math}</div>`
      : `<div class="eq-line">${supSub(obj.readable || obj.script)}</div>`;
    return `<div class="obj-eq">
      ${head}
      <details class="eq-src"><summary>수식 원본</summary>
        ${math ? `<div class="eq-latex"><span>글</span><code>${esc(obj.readable)}</code></div>` : ""}
        <div class="eq-latex"><span>LaTeX</span><code>${esc(obj.latex)}</code></div>
        <div class="eq-latex"><span>한글</span><code>${esc(obj.script)}</code></div>
      </details>
    </div>`;
  }

  // 첫 줄이 머리행인지 — header 표시가 없으면 첫 줄을 머리로 본다
  const useFirstAsHead = !obj.rows.some((r) => r.some((c) => c.header));
  const cellTag = (c, ri) => (c.header || (useFirstAsHead && ri === 0)) ? "th" : "td";

  const body = obj.rows.map((cells, ri) => `<tr>${cells.map((c) => {
    const t = cellTag(c, ri);
    const sp = (c.colspan > 1 ? ` colspan="${c.colspan}"` : "")
             + (c.rowspan > 1 ? ` rowspan="${c.rowspan}"` : "");
    return `<${t}${sp}>${esc(c.text).replace(/\n/g, "<br>")}</${t}>`;
  }).join("")}</tr>`).join("");

  return `<div class="obj-tbl-wrap"><table class="obj-tbl">${body}</table></div>`;
}

/**
 * 본문을 원래 순서 그대로 그린다 — <img id> 자리에 진짜 표·수식을 끼워 넣는다.
 * @returns {Promise<DocumentFragment>}
 */
export async function renderBody(text, regId, store,
                                { onXml = null, resolveCite = null, resolveLaw = null,
                                  onCite = null, hasJo = null, onJo = null } = {}) {
  const frag = document.createDocumentFragment();
  const src = String(text || "");
  RE_IMG.lastIndex = 0;

  let last = 0, m, seq = 0;
  const pushText = (s) => {
    if (!s.trim()) return;
    const d = document.createElement("div");
    d.className = "bd-text";
    const plain = s.replace(/^\n+|\n+$/g, "");
    if (resolveCite || resolveLaw || hasJo) {
      // 「…」 인용을 눌러 참조규정 창에서 열 수 있게 한다
      let h = linkCitations(esc(plain), resolveCite);
      h = linkLawRefs(h, resolveLaw);
      h = linkSelfRefs(h, hasJo);          // 같은 규정 안의 제○조 인용
      d.innerHTML = h;
      d.querySelectorAll("a.cite").forEach((a) => {
        a.onclick = (e) => {
          e.preventDefault();
          if (a.classList.contains("self")) onJo?.(+a.dataset.jo);
          else onCite?.(a.dataset.reg, a.textContent, a.dataset.jo || "");
        };
      });
    } else {
      d.textContent = plain;
    }
    frag.appendChild(d);
  };

  while ((m = RE_IMG.exec(src))) {
    pushText(src.slice(last, m.index));
    last = m.index + m[0].length;
    seq += 1;

    const id = m[1];
    const meta = store && store.meta(regId, id);
    const box = document.createElement("div");
    box.className = "bd-obj";
    // 표도 수식도 아닌 도해는 원본 그림을 그대로 보여 준다
    if (meta && meta.kind === "image") {
      const src = `data/objects/${encodeURIComponent(regId)}/${encodeURIComponent(meta.file || id + ".gif")}`;
      box.innerHTML = `<div class="obj-body obj-pic"><img src="${src}" alt="${esc(meta.article || "")} 그림" loading="lazy"></div>
        <div class="obj-foot"><span class="obj-seq">${seq}</span>
          <span class="mut">원문 그림 · 이미지 id ${id}</span>
          <div class="spacer"></div>
          <a class="btnlink" href="${src}" target="_blank" rel="noopener">원본 보기</a></div>`;
      frag.appendChild(box);
      continue;
    }
    box.innerHTML = meta
      ? `<div class="obj-body"><span class="mut">읽는 중…</span></div>
         <div class="obj-foot"><span class="obj-seq">${seq}</span>
           <span class="mut">${meta.kind === "table" ? `표 ${meta.rows}행 × ${meta.cols}열` : "수식"}
           · 원문 이미지 id ${id}</span>
           <div class="spacer"></div>
           ${meta.kind === "table" ? `<button class="mini2 obj-zoom-btn" type="button">크게 보기</button>` : ""}
           <a class="btnlink" href="${store.url(regId, id)}" download="${id}.xml">XML</a></div>`
      : `<div class="obj-fail">원문에 그림으로 들어 있는 표·수식입니다.
           아직 XML 로 바꾸지 못했습니다. (이미지 id ${id})</div>`;
    frag.appendChild(box);

    if (meta) {
      store.get(regId, id).then((o) => {
        const slot = box.querySelector(".obj-body");
        slot.innerHTML = toHtml(o);
        fitTable(slot);
        const zb = box.querySelector(".obj-zoom-btn");
        if (zb) zb.onclick = () => openTableOverlay(toHtml(o), `${o.article || ""} 표`.trim());
        onXml?.(box, o);
      });
    }
  }
  pushText(src.slice(last));
  return frag;
}

/**
 * 표가 창보다 넓으면 폭에 맞춘다.
 *   1) 줄바꿈을 풀어 (shrunk) 칸이 접히게 하고
 *   2) 그래도 넘치면 글자를 줄인다 (8.5px 까지)
 *   3) 그래도 넘치면 가로 스크롤 + [크게 보기] 로 넘긴다
 */
export function fitTable(scope) {
  const wraps = [...scope.querySelectorAll(".obj-tbl-wrap")];
  if (!wraps.length) return;

  requestAnimationFrame(() => {
    for (const wrap of wraps) {
      const t = wrap.querySelector("table.obj-tbl");
      if (!t) continue;
      t.style.fontSize = "";
      wrap.classList.remove("shrunk");

      const avail = wrap.clientWidth;
      if (!avail || t.scrollWidth <= avail) continue;

      wrap.classList.add("shrunk");             // 줄바꿈 허용 · 여백 축소
      const base = parseFloat(getComputedStyle(t).fontSize) || 11;
      let size = base;
      for (let pass = 0; pass < 3 && t.scrollWidth > avail && size > MIN_FONT; pass++) {
        size = Math.max(MIN_FONT, Math.floor(size * (avail / t.scrollWidth) * 10) / 10);
        t.style.fontSize = `${size}px`;
      }
      wrap.dataset.overflow = t.scrollWidth > avail + 2 ? "1" : "";
    }
  });
}

const MIN_FONT = 8.5;

/* ============================================================
   별표 개정 표시 — 바뀌는 문구를 붉게 드러낸다
   ------------------------------------------------------------
   별표 원문은 HWP 에서 뽑은 표라 같은 말이 칸마다 다르게 띄어져 있다
   (예: '공공측량작업규정\n제2편 제2장' · '공공측량\n작업규정\n제4편제7장').
   그래서 찾을 말은 글자 사이의 공백·줄바꿈을 무시하고 맞춘다.

   edits: [{find, to}]      바뀌는 문구  — 옛 문구에 취소선, 새 문구를 붉게
          [{find, add}]     덧붙는 문구  — 옛 문구는 그대로, 새 문구만 붉게
          [{find, del:true}] 빠지는 문구 — 취소선만
   ============================================================ */
const looseRe = (s) => new RegExp(
  [...String(s).replace(/\s+/g, "")]
    .map((ch) => ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("\\s*"), "g");

/**
 * @param {Element} root  표가 그려진 자리
 * @param {Array}   edits 바꿀 문구 목록
 * @returns {Array} 각 문구가 몇 곳에 걸렸는지 (hits)
 */
export function markAnnexEdits(root, edits) {
  const list = (edits || [])
    .filter((e) => e && e.find)
    .map((e) => ({ ...e, rx: looseRe(e.find), hits: 0 }))
    // 긴 말을 먼저 잡아야 짧은 말이 그 안을 다시 물지 않는다
    .sort((a, b) => String(b.find).replace(/\s+/g, "").length
                  - String(a.find).replace(/\s+/g, "").length);
  if (!list.length) return [];

  const tmp = document.createElement("div");
  for (const cell of root.querySelectorAll("td, th, .bd-text")) {
    tmp.innerHTML = cell.innerHTML.replace(/<br\s*\/?>/gi, "\n");
    const plain = tmp.textContent;
    if (!plain.trim()) continue;

    const marks = [];
    for (const e of list) {
      e.rx.lastIndex = 0;
      let m;
      while ((m = e.rx.exec(plain))) {
        if (!m[0]) { e.rx.lastIndex += 1; continue; }
        const s = m.index, t = m.index + m[0].length;
        if (!marks.some((k) => s < k.end && k.start < t)) marks.push({ start: s, end: t, text: m[0], e });
      }
    }
    if (!marks.length) continue;

    marks.sort((a, b) => a.start - b.start);
    let html = "", at = 0;
    for (const k of marks) {
      html += esc(plain.slice(at, k.start));
      if (k.e.add) {
        html += `${esc(k.text)}<ins class="anx-ins">${esc(k.e.add)}</ins>`;
      } else if (k.e.to) {
        html += `<del class="anx-del">${esc(k.text)}</del>`
              + `<ins class="anx-ins">${esc(k.e.to)}</ins>`;
      } else {
        html += `<del class="anx-del">${esc(k.text)}</del>`;
      }
      k.e.hits += 1;
      at = k.end;
    }
    html += esc(plain.slice(at));
    cell.innerHTML = html.replace(/\n/g, "<br>");
  }
  return list.map((e) => ({
    find: e.find, to: e.to || "", add: e.add || "", del: !!e.del,
    why: e.why || "", hits: e.hits,
  }));
}

/** 좁은 창에서 표를 크게 펼쳐 보는 덮개 화면 */
export function openTableOverlay(html, caption = "") {
  const el = document.createElement("div");
  el.className = "overlay obj-zoom";
  el.innerHTML = `<div class="zoom-box">
      <div class="zoom-head"><b>${caption ? esc(caption) : "표 크게 보기"}</b>
        <div class="spacer"></div>
        <button class="x" title="닫기 (Esc)">✕</button></div>
      <div class="zoom-body">${html}</div>
    </div>`;
  const close = () => { el.remove(); document.removeEventListener("keydown", onKey, true); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  el.querySelector(".x").onclick = close;
  el.addEventListener("click", (e) => { if (e.target === el) close(); });
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(el);
}
