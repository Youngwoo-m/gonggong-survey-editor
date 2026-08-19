/* ============================================================
   core/citecheck.js — 피인용조문 검색
   ------------------------------------------------------------
   법제처 법령안편집기의 '피인용조문 검색' 이다.
   (App/관련규정/법제처_법령안편집기 · 법령안편집기_피인용조문검색.mp4)

     ▷ 이 규정이 인용하는 타법과 조문이 아직 성한지 본다.
     ▷ 인용하는 조가 옮겨졌으면 현행화가 필요한지에 따라
       '검토필수' 또는 '확인필요' 로 적는다.

   ■ '인용조문' 과 '피인용조문' 은 방향이 반대다

     인용조문 검색   내 조가 옮겨졌을 때 나를 부르던 남을 찾는다
                     (부칙 '다른 규정의 개정' — core/supplement.js)
     피인용조문 검색  내가 부르는 남이 아직 성한지 본다  ← 여기

   ■ 무엇을 잣대로 삼는가

     라이브러리에 규정 92종의 조문 트리가 색인되어 있다. 「도로법」제2조를
     부르고 있으면 그 규정의 트리를 열어 제2조가 실제로 있는지 본다.
     색인되지 않은 규정(파일만 있는 것)은 알 길이 없으므로 '확인필요' 로
     남긴다 — 모르는 것을 성하다고 하지 않는다.

   DOM 을 모른다. 규정 트리를 읽어 오는 일은 부르는 쪽이 한다.
   ============================================================ */
import * as M from "./model.js?v=20260822v";

/** 「법령 이름」제N조제M항제K호 — 이름은 「」 안, 뒤에 붙는 항·호까지 문다 */
const RE_CITE = /[「『]([^」』]{2,60})[」』]\s*(?:[（(][^()（）]{0,40}[)）])?\s*제\s*(\d+)\s*조(?:의\s*(\d+))?((?:\s*제\s*\d+\s*[항호])*)/g;

/** 이름만 부르는 자리 (조 번호 없이) — 규정이 있기는 한지만 본다 */
const RE_NAME = /[「『]([^」』]{2,60})[」』]/g;

/**
 * 규정 하나가 부르는 남의 조문을 모은다.
 * @param {object} regNode 규정 노드
 * @returns {Array<{node, label, name, no, branch, tail, raw}>}
 */
export function scanCitations(regNode) {
  const out = [];
  M.walk((regNode && regNode.children) || [], (n) => {
    if (n.level !== "조" || !n.body) return;
    const text = String(n.body);
    RE_CITE.lastIndex = 0;
    let m;
    while ((m = RE_CITE.exec(text))) {
      out.push({
        node: n, label: M.shortLabel(n),
        name: m[1].trim(), no: +m[2], branch: m[3] ? +m[3] : 0,
        tail: (m[4] || "").replace(/\s+/g, ""), raw: m[0].trim(),
      });
    }
  });
  return out;
}

/** 이름만 부르는 자리 (조 번호가 없는 인용) */
export function scanNameOnly(regNode) {
  const out = new Map();
  M.walk((regNode && regNode.children) || [], (n) => {
    if (n.level !== "조" || !n.body) return;
    RE_NAME.lastIndex = 0;
    let m;
    while ((m = RE_NAME.exec(n.body))) {
      const name = m[1].trim();
      if (!/(법|령|규칙|규정|고시|지침|준칙|기준|매뉴얼|요령|예규|훈령)$/.test(name)) continue;
      if (!out.has(name)) out.set(name, []);
      out.get(name).push({ node: n, label: M.shortLabel(n) });
    }
  });
  return out;
}

/* ---------- 이름으로 규정 찾기 ---------- */

const squeeze = (s) => String(s || "").replace(/\s+/g, "");

/**
 * 인용에 적힌 이름으로 라이브러리의 규정을 찾는다.
 * 띄어쓰기는 무시하고, 온전히 같은 것을 먼저, 없으면 담고 있는 것을 본다.
 */
export function resolveName(name, regulations) {
  const want = squeeze(name);
  if (!want) return null;
  let loose = null;
  for (const r of regulations || []) {
    const got = squeeze(r.name);
    if (got === want) return r;
    if (!loose && (got.includes(want) || want.includes(got))) loose = r;
  }
  return loose;
}

/* ---------- 판정 ---------- */

/* 법제처 편집기와 같이 둘로 가른다 — 고쳐야 할 것과 사람이 봐야 할 것 */
export const GRADES = {
  OK: "성함",
  MUST: "검토필수",   // 색인된 규정인데 그 조가 없다 — 옮겨졌거나 지워졌다
  CHECK: "확인필요",  // 색인이 없거나 라이브러리 밖이라 알 수 없다
};

/**
 * 인용 하나를 판정한다.
 *
 * @param {object} cite   scanCitations 의 한 줄
 * @param {object} meta   library.json 의 규정 (없으면 null)
 * @param {object} doc    그 규정의 조문 트리 (색인이 없으면 null)
 * @param {Set}    selfNames 이 프로젝트가 담고 있는 규정 이름들 (제 자신은 건너뛴다)
 */
export function gradeCitation(cite, meta, doc) {
  if (!meta) {
    // 우리가 담고 있지 않은 법령 — 모르는 것을 성하다고 하지 않는다
    return { grade: GRADES.CHECK,
      why: "라이브러리에 없는 규정입니다 — 이름이 맞는지, 그 조가 있는지 손으로 살피십시오." };
  }
  if (!doc) {
    return { grade: GRADES.CHECK, reg: meta,
      why: `「${meta.name}」 은(는) 본문이 색인되지 않아 조문이 성한지 알 수 없습니다.` };
  }
  const key = `${cite.no}|${cite.branch}`;
  const found = articleIndex(doc).get(key);
  if (found) {
    return { grade: GRADES.OK, reg: meta, target: found,
      why: `${found.title || ""}`.trim() };
  }
  const want = `제${cite.no}조${cite.branch ? `의${cite.branch}` : ""}`;
  // 번호는 같은데 가지(의N)만 다른 조가 있으면 그것부터 짚는다
  const sameNo = [...articleIndex(doc)].filter(([k]) => +k.split("|")[0] === cite.no)
    .map(([, n]) => M.shortLabel(n));
  if (sameNo.length) {
    return { grade: GRADES.MUST, reg: meta,
      why: `「${meta.name}」 에 ${want} 은(는) 없고 ${sameNo.join(" · ")} 이(가) 있습니다 `
        + `— 가지 번호를 살피십시오.` };
  }
  const near = nearestArticle(doc, cite.no);
  return { grade: GRADES.MUST, reg: meta,
    why: `「${meta.name}」 에 ${want} 이(가) 없습니다`
      + (near ? ` — 가장 가까운 조는 ${near} 입니다.` : " — 옮겨졌거나 지워진 조입니다.") };
}

/** 규정 트리의 조문 색인 */
const _idx = new WeakMap();
function articleIndex(doc) {
  if (_idx.has(doc)) return _idx.get(doc);
  const map = new Map();
  M.walk(doc.tree || [], (n) => {
    if (n.level !== "조" || n.annexRef) return;
    map.set(`${n.no}|${n.branch || 0}`, n);
  });
  _idx.set(doc, map);
  return map;
}

/** 그 번호에 가장 가까운 조 — 얼마나 어긋났는지 가늠하게 한다 */
function nearestArticle(doc, no) {
  let best = null, gap = Infinity;
  for (const [k, n] of articleIndex(doc)) {
    const num = +k.split("|")[0];
    const d = Math.abs(num - no);
    if (d < gap) { gap = d; best = n; }
  }
  return best ? M.shortLabel(best) : "";
}

/**
 * 인용 목록 전체를 판정한다.
 * @param {Array} cites
 * @param {Array} regulations library.json 의 규정 목록
 * @param {Map}   docs        규정 id → 조문 트리 (부르는 쪽이 미리 읽어 둔다)
 */
export function gradeAll(cites, regulations, docs) {
  return cites.map((c) => {
    const meta = resolveName(c.name, regulations);
    const doc = meta ? (docs.get(meta.id) || null) : null;
    return Object.assign({}, c, gradeCitation(c, meta, doc));
  });
}

/** 판정할 때 미리 읽어 두어야 할 규정 id 들 */
export function neededDocs(cites, regulations) {
  const ids = new Set();
  for (const c of cites) {
    const meta = resolveName(c.name, regulations);
    if (meta && meta.hasFullText) ids.add(meta.id);
  }
  return [...ids];
}
