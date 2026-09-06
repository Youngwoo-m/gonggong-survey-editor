/* ============================================================
   core/structure.js — 텍스트 줄 목록 → 편·장·절·관·조 트리 (색인화)
   한국어(제N편/제N조) · 일본어(第N編/第N条) 표기를 함께 인식한다.
   ============================================================ */
import * as M from "./model.js?v=20260906p";

/* ---------- 패턴 ---------- */
const NN = "[0-9０-９一二三四五六七八九十百]+";
const P = {
  편: [new RegExp(`^제\\s*(${NN})\\s*편\\s*(.*)$`), new RegExp(`^第\\s*(${NN})\\s*編\\s*(.*)$`)],
  장: [new RegExp(`^제\\s*(${NN})\\s*장\\s*(.*)$`), new RegExp(`^第\\s*(${NN})\\s*章\\s*(.*)$`)],
  절: [new RegExp(`^제\\s*(${NN})\\s*절\\s*(.*)$`), new RegExp(`^第\\s*(${NN})\\s*節\\s*(.*)$`)],
  관: [new RegExp(`^제\\s*(${NN})\\s*관\\s*(.*)$`), new RegExp(`^第\\s*(${NN})\\s*款\\s*(.*)$`)],
};
const N = "[0-9０-９一二三四五六七八九十百]+";
const JO_TITLED = [
  new RegExp(`^제\\s*(${N})\\s*조(?:의\\s*(${N}))?\\s*[（(]\\s*([^）)]*)\\s*[）)]\\s*([\\s\\S]*)$`),
  new RegExp(`^第\\s*(${N})\\s*条(?:の\\s*(${N}))?\\s*[（(]\\s*([^）)]*)\\s*[）)]\\s*([\\s\\S]*)$`),
];
const JO_PLAIN = [
  new RegExp(`^제\\s*(${N})\\s*조(?:의\\s*(${N}))?\\s+([\\s\\S]*)$`),
  new RegExp(`^第\\s*(${N})\\s*条(?:の\\s*(${N}))?\\s+([\\s\\S]*)$`),
];

const KANJI = { 一:1, 二:2, 三:3, 四:4, 五:5, 六:6, 七:7, 八:8, 九:9, 十:10 };
function num(s) {
  s = String(s).replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  // 十, 十二, 二十三 …
  let t = 0, cur = 0;
  for (const ch of s) {
    const k = KANJI[ch];
    if (k === undefined) continue;
    if (k === 10) { cur = (cur || 1) * 10; t += cur; cur = 0; }
    else cur += k;
  }
  return (t + cur) || 1;
}

const matchAny = (line, list) => { for (const re of list) { const m = line.match(re); if (m) return m; } return null; };

/* ---------- 잡음 제거 ---------- */
function cleanLines(lines) {
  const counts = new Map();
  for (const l of lines) {
    const k = l.trim();
    if (k.length > 0 && k.length < 60) counts.set(k, (counts.get(k) || 0) + 1);
  }
  const repeated = new Set([...counts].filter(([k, c]) => c >= 5 && k.length < 40).map(([k]) => k));

  return lines
    .map((l) => String(l || "").replace(/ /g, " ").replace(/\s+$/g, ""))
    .filter((l) => {
      const t = l.trim();
      if (!t) return false;
      if (/^-?\s*\d{1,4}\s*-?$/.test(t)) return false;               // 쪽번호
      if (/^(page|Page)\s*\d+/.test(t)) return false;
      if (repeated.has(t) && !/^제\s*\d|^第\s*\d/.test(t)) return false; // 머리말·꼬리말
      return true;
    });
}

const isHeading = (l) =>
  !!(matchAny(l, P.편) || matchAny(l, P.장) || matchAny(l, P.절) || matchAny(l, P.관));

/** 괄호만으로 된 조 제목 줄 — 일본 준칙은 제목을 조문 앞 줄에 따로 둔다 */
const PAREN_TITLE = /^[（(]\s*([^）)]{1,40})\s*[）)]$/;

/**
 * 「（목적及び適用範囲）」 + 「第１条 본문…」 형태를
 * 「第１条（목적及び適用範囲） 본문…」 한 줄로 합친다.
 */
function attachParenTitles(src) {
  const out = [];
  for (let i = 0; i < src.length; i++) {
    const cur = src[i].trim();
    const m = cur.match(PAREN_TITLE);
    const next = (src[i + 1] || "").trim();
    if (m && next) {
      const j = matchAny(next, JO_PLAIN);
      if (j && !matchAny(next, JO_TITLED)) {
        const head = next.slice(0, next.length - (j[3] || "").length).trim();
        out.push(`${head}（${m[1]}） ${j[3] || ""}`.trim());
        i += 1;
        continue;
      }
    }
    out.push(src[i]);
  }
  return out;
}

/** 조 표제 줄이면 본문 부분을 돌려준다 (목차 줄은 본문이 비어 있다) */
function joBody(l) {
  let m = matchAny(l, JO_TITLED);
  if (m) return (m[4] || "").trim();
  m = matchAny(l, JO_PLAIN);
  if (m) return (m[3] || "").trim();
  return null;
}

/**
 * 앞머리 목차 제거
 * 규정 문서는 대개 '제N조(제목)' 만 나열한 목차가 앞에 붙는다.
 * 본문의 조 표제는 같은 줄에 조문 내용이 이어지므로 그것으로 구분한다.
 */
function stripToc(src) {
  let firstBody = -1, tocCount = 0;
  for (let i = 0; i < src.length; i++) {
    const b = joBody(src[i].trim());
    if (b === null) continue;
    if (b.length > 8) { firstBody = i; break; }
    tocCount += 1;
  }
  if (firstBody < 0) return { lines: src, removed: 0 };

  // 본문 시작 지점 = 첫 조문 앞에 붙어 있는 표제 줄들의 시작
  let start = firstBody;
  while (start > 0) {
    const prev = src[start - 1].trim();
    if (isHeading(prev) || PAREN_TITLE.test(prev)) start -= 1;
    else break;
  }
  // 앞쪽에 표제만 잔뜩 있으면(목차) 걷어낸다
  let headBefore = 0;
  for (let i = 0; i < start; i++) {
    const l = src[i].trim();
    if (isHeading(l) || joBody(l) !== null) headBefore += 1;
  }
  if (headBefore < 10) return { lines: src, removed: 0 };
  return { lines: src.slice(start), removed: start };
}

/**
 * 부칙 이후를 본문 트리에서 분리한다.
 * 목차에도 '부칙' 항목이 있으므로, 문서 뒤쪽에 있는 것만 인정한다.
 */
function splitAddenda(src) {
  const RE = /^\s*(부\s*칙|附\s*則)\s*[<＜(（]?/;
  let joSeen = 0;
  for (let i = 0; i < src.length; i++) {
    const b = joBody(src[i].trim());
    if (b !== null && b.length > 8) joSeen += 1;
    if (RE.test(src[i]) && i >= src.length * 0.5 && joSeen >= 10) {
      return { lines: src.slice(0, i), addenda: src.slice(i) };
    }
  }
  return { lines: src, addenda: [] };
}

/** 조문 본문 안에서 항(①②…) 앞에 줄바꿈 */
function tidy(body) {
  let t = String(body || "").replace(/[ \t]+/g, " ").trim();
  t = t.replace(/(?!^)([①-⑳])/g, "\n$1");
  t = t.replace(/(?<=[.。」"])\s*(\d{1,2}\.\s)/g, "\n$1");
  return t.trim();
}

/* ============================================================
   목차(Contents) 기준 색인
   ------------------------------------------------------------
   조문 체계가 없는 문서(ASPRS · USGS · FGDC · 일본 手引き 등)는
   「1.」「1.2」「1.2.3」 같은 번호 매김 표제를 트리로 삼는다.
   깊이는 점(.)의 개수로 정하고, 표제 사이의 글은 본문으로 붙인다.
   ============================================================ */
const OUT_NUM = /^(\d+(?:\.\d+){0,5})\.?\s+(\S.*)$/;                    // 1.2.3 제목
const OUT_APP = /^(Appendix|Annex|附録|付録|부록|별첨)\s*([A-Z]|\d+)?\s*[.:-]?\s*(.*)$/i;
const OUT_CHAP = /^(Chapter|Section|Part)\s+([A-Z0-9][\w.-]*)\s*[.:-]?\s*(.*)$/i;
const LEADER = /[.·‥…·․…\s]{4,}\s*\d{1,4}\s*$/;          // 목차 점선 + 쪽번호
const TOC_TITLE = /^(table\s+of\s+contents|contents|목\s*차|차\s*례|index)$/i;

/** 목차 줄에서 점선·쪽번호를 떼어낸다 */
function stripLeader(s) {
  return s.replace(LEADER, "").replace(/\s+\d{1,4}$/, "").trim();
}

function outlineHead(line) {
  const s = stripLeader(line);
  if (!s || s.length > 160 || TOC_TITLE.test(s)) return null;
  let m = s.match(OUT_NUM);
  if (m) {
    const title = m[2].trim();
    const parts = m[1].split(".");
    // 표제가 아닌 것 걸러내기
    //   · "1 기준점측량 | 1급, 2급 | …"  → 표에서 온 줄
    //   · "700 miles across Wyoming,"    → 숫자로 시작하는 문장
    if (title.includes("|")) return null;
    if (+parts[0] > 40) return null;                       // 표제 번호가 이렇게 클 수 없다
    if (/^[a-z]/.test(title)) return null;                 // 소문자로 이어지면 문장
    if (/[,;]$/.test(title)) return null;
    if (title.length < 3 || /^[\d.,%()\s\-–—]+$/.test(title)) return null;
    const depth = parts.length;                            // 1 → 1, 1.2 → 2 …
    return { depth: Math.min(depth, 5), no: m[1], title, kind: "num" };
  }
  m = s.match(OUT_APP);
  if (m) return { depth: 1, no: (m[2] || "").trim(), title: (m[3] || m[1]).trim() || m[1], kind: "appendix" };
  m = s.match(OUT_CHAP);
  if (m) return { depth: /table|figure/i.test(m[1]) ? 3 : 1, no: m[2], title: (m[3] || "").trim(), kind: "chap" };
  return null;
}

/**
 * 앞머리 목차 블록 제거 — 표제만 줄줄이 나오다가
 * 처음으로 '표제 + 본문' 이 나오는 지점부터를 본문으로 본다.
 */
function stripOutlineToc(src) {
  let firstBody = -1, heads = 0;
  for (let i = 0; i < src.length; i++) {
    if (!outlineHead(src[i].trim())) continue;
    heads += 1;
    // 다음 줄이 표제가 아니면 본문이 붙은 것
    let j = i + 1;
    while (j < src.length && !src[j].trim()) j += 1;
    if (j < src.length && !outlineHead(src[j].trim())) { firstBody = i; break; }
  }
  if (firstBody < 0 || heads < 5) return src;
  // 목차에만 있고 본문에 없는 표제를 잃지 않도록, 실제로 중복될 때만 자른다
  const before = new Set();
  for (let i = 0; i < firstBody; i++) {
    const h = outlineHead(src[i].trim());
    if (h) before.add((h.no || "") + "|" + h.title);
  }
  let dup = 0;
  for (let i = firstBody; i < src.length; i++) {
    const h = outlineHead(src[i].trim());
    if (h && before.has((h.no || "") + "|" + h.title)) dup += 1;
  }
  return dup >= Math.max(3, before.size * 0.5) ? src.slice(firstBody) : src;
}

/**
 * 목차 기준 트리. 깊이 1~5 를 편·장·절·관·조에 대응시킨다.
 * @returns {{tree:Array, stats:object, headings:number}}
 */
export function buildOutline(lines) {
  const src = stripOutlineToc(cleanLines(lines));
  const root = { children: [] };
  const stack = [[-1, root]];
  let seq = 0;
  const mk = (depth, no, title, kind) => ({
    id: M.newId(depth >= 5 ? "a" : "h"),
    level: M.LEVELS[Math.min(depth, 5) - 1] || "조",
    no: 0, branch: 0,
    title: (title || no || "").trim(),
    body: "", status: "유지", legacyNo: no || "", reason: "", sourceRef: null,
    outlineNo: no || "", outlineKind: kind, history: [],
    origTitle: "", children: [], collapsed: depth > 1,
  });

  let last = null, headings = 0;
  for (const raw of src) {
    const line = raw.trim();
    const h = outlineHead(line);
    if (h && (h.title || h.no)) {
      seq += 1; headings += 1;
      const node = mk(h.depth, h.no, h.title, h.kind);
      while (stack.length && stack[stack.length - 1][0] >= h.depth) stack.pop();
      stack[stack.length - 1][1].children.push(node);
      stack.push([h.depth, node]);
      last = node;
      continue;
    }
    if (last) last.body = (last.body ? last.body + "\n" : "") + stripLeader(line);
  }

  const tree = root.children;
  M.renumber(tree);
  return { tree, stats: M.stats(tree), headings, outline: true };
}

/** 조문 체계인지 목차 체계인지 스스로 고른다 */
export function buildAuto(lines) {
  const a = buildStructure(lines);
  if (a.stats.조 >= 5) return Object.assign(a, { mode: "조문" });
  const b = buildOutline(lines);
  if (b.headings >= 5) return Object.assign(b, { mode: "목차", unmatched: 0, tocRemoved: 0, addenda: 0 });
  return Object.assign(a, { mode: "조문" });
}

/**
 * @param {string[]} lines
 * @param {object} opts { lang: 'ko'|'ja'|'en' }
 * @returns {{tree:Array, stats:object, unmatched:number}}
 */
export function buildStructure(lines, opts = {}) {
  // 목차를 먼저 걷어내야 목차 안의 '부칙' 항목에 속지 않는다
  const cleaned = attachParenTitles(cleanLines(lines));
  const t = stripToc(cleaned);
  const a = splitAddenda(t.lines);
  const src = a.lines;
  const root = { children: [] };
  const stack = [[-1, root]];
  const push = (node, lv) => {
    while (stack.length && stack[stack.length - 1][0] >= lv) stack.pop();
    stack[stack.length - 1][1].children.push(node);
    stack.push([lv, node]);
  };
  const mk = (level, no, branch, title, body) => ({
    id: M.newId(level === "조" ? "a" : "h"),
    level, no, branch, title: (title || "").trim(), body: body || "",
    status: "유지", legacyNo: level === "조" ? `제${no}조${branch ? `의${branch}` : ""}` : "",
    reason: "", sourceRef: null, origTitle: "", origBody: "", children: [], collapsed: level !== "편",
  });

  let unmatched = 0;
  let last = null;

  for (const raw of src) {
    const line = raw.trim();
    let m;

    if ((m = matchAny(line, P.편))) { last = mk("편", num(m[1]), 0, m[2]); push(last, 0); continue; }
    if ((m = matchAny(line, P.장))) { last = mk("장", num(m[1]), 0, m[2]); push(last, 1); continue; }
    if ((m = matchAny(line, P.절))) { last = mk("절", num(m[1]), 0, m[2]); push(last, 2); continue; }
    if ((m = matchAny(line, P.관))) { last = mk("관", num(m[1]), 0, m[2]); push(last, 3); continue; }

    // 부록·별첨은 최상위 항목으로 세운다
    if ((m = line.match(/^(부\s*록|附\s*録|付\s*録|별\s*첨)\s*([0-9０-９]+|[A-Z])?\s*[.:-]?\s*(.*)$/))) {
      const label = m[1].replace(/\s/g, "");
      last = mk("편", 0, 0, `${label}${m[2] ? " " + m[2] : ""}${m[3] ? " " + m[3].trim() : ""}`);
      last.isAppendix = true;
      push(last, 0);
      continue;
    }

    if ((m = matchAny(line, JO_TITLED))) {
      last = mk("조", num(m[1]), m[2] ? num(m[2]) : 0, m[3], tidy(m[4]));
      push(last, 4); continue;
    }
    if ((m = matchAny(line, JO_PLAIN))) {
      const rest = (m[3] || "").trim();
      const cut = rest.search(/[ 　]/) > 0 && rest.length > 18 ? rest.indexOf(" ") : -1;
      last = mk("조", num(m[1]), m[2] ? num(m[2]) : 0,
                cut > 0 ? rest.slice(0, cut) : rest.slice(0, 30), tidy(cut > 0 ? rest.slice(cut) : ""));
      push(last, 4); continue;
    }

    // 조문에 이어지는 문단
    if (last && last.level === "조") last.body = (last.body ? last.body + "\n" : "") + line;
    else if (last) last.body = (last.body ? last.body + "\n" : "") + line;
    else unmatched += 1;
  }

  const tree = root.children;
  M.renumber(tree);
  return {
    tree,
    stats: M.stats(tree),
    unmatched,
    tocRemoved: t.removed,        // 목차로 판단해 걷어낸 줄 수
    addenda: a.addenda.length,    // 부칙 줄 수 (본문 트리에서 제외)
  };
}
