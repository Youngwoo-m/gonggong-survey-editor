/* ============================================================
   core/part.js — 조각(.pmpart) 짓기와 넣기
   ------------------------------------------------------------
   개정안의 한 덩이(편ㆍ장ㆍ절ㆍ관ㆍ조)를 따로 꺼내어 파일로 두고, 뒤에 그
   자리에 도로 넣는다. 여럿이 나누어 손볼 때 쓴다 —— 한 사람은 제2편,
   다른 사람은 제5편을 맡아 고치고 조각만 주고받는다.

   ■ 사람이 정한 잣대 (2026-09-06)

     ㆍ 번호는 조각에 적힌 것을 그대로 쓴다. 넣으면서 다시 매기지 아니한다.
     ㆍ 새로 덧붙이는 것이 아니라 **있던 마디를 갈아 끼운다**.
     ㆍ 별표ㆍ별지도 함께 담아 개정안을 갱신한다.

   ■ 짝을 찾는 차례

     ① 마디 id 가 같은 것
     ② 없으면 같은 갈래ㆍ번호(제23조의2 처럼 가지까지)
     ③ 별표ㆍ별지는 구분과 번호로 (별표 17)

     ①②③ 이 모두 빗나가면 넣지 아니하고 알린다. 어디에 넣을지 기계가
     어림하면 엉뚱한 자리를 덮는다.
   ============================================================ */

const FMT = "pmpart";

/** 마디 아래를 모두 (자신 포함) */
function* walk(n) {
  yield n;
  for (const c of n.children || []) yield* walk(c);
}

/** 그 마디가 부르는 별표ㆍ별지 번호 —— 본문에서 「별표 17」 을 훑는다 */
const RE_ANX = /(별표|별지)\s*(\d+)/g;

function annexKeysIn(node) {
  const out = new Set();
  for (const x of walk(node)) {
    const t = `${x.title || ""} ${x.body || ""}`;
    let m;
    RE_ANX.lastIndex = 0;
    while ((m = RE_ANX.exec(t))) out.add(`${m[1]}${m[2]}`);
  }
  return out;
}

const anxKey = (n) => (n.annexRef
  ? `${n.annexRef.gubun || "별표"}${n.annexRef.no}`
  : null);

/**
 * 조각을 짓는다.
 * @param {object} node 꺼낼 마디
 * @param {object} reg  그 마디가 속한 규정 마디
 * @param {{by?:string, versionLabel?:string}} meta
 * @returns {{json:object, name:string, 별표:number}}
 */
export function makePart(node, reg, meta = {}) {
  const keys = annexKeysIn(node);
  const annex = [];
  for (const x of walk(reg)) {
    const k = anxKey(x);
    if (k && keys.has(k)) annex.push(JSON.parse(JSON.stringify(x)));
  }
  const label = node.level === "조"
    ? `제${node.no}조${node.branch ? `의${node.branch}` : ""}`
    : `제${node.no}${node.level}`;
  return {
    json: {
      format: FMT, version: 1,
      savedAt: new Date().toISOString(),
      by: meta.by || "",
      from: {
        targetId: reg.targetId || "", regTitle: reg.title || "",
        revLabel: reg.revLabel || "", versionLabel: meta.versionLabel || "",
      },
      node: JSON.parse(JSON.stringify(node)),
      annex,
    },
    name: `${reg.title || "규정"} ${label} ${node.title || ""}`.trim()
      .replace(/[\\/:*?"<>|]/g, "_") + ".pmpart",
    별표: annex.length,
  };
}

/** 트리에서 짝이 되는 마디와 그 어버이를 찾는다 */
function findSpot(nodes, want, parent = null) {
  for (const n of nodes || []) {
    const same = n.id === want.id
      || (want.annexRef && anxKey(n) && anxKey(n) === anxKey(want))
      || (!want.annexRef && !n.annexRef && n.level === want.level
          && String(n.no) === String(want.no)
          && String(n.branch || "") === String(want.branch || ""));
    if (same) return { node: n, parent, list: nodes, at: nodes.indexOf(n) };
    const deep = findSpot(n.children, want, n);
    if (deep) return deep;
  }
  return null;
}

/**
 * 조각을 트리에 넣는다 —— 있던 마디를 갈아 끼운다.
 * @param {Array} tree 규정 마디의 children
 * @param {object} part 조각 json
 * @returns {{바꾼것:Array<string>, 못찾은것:Array<string>}}
 */
export function applyPart(tree, part) {
  const done = [], miss = [];
  const put = (want) => {
    const spot = findSpot(tree, want);
    const label = want.annexRef
      ? `${want.annexRef.gubun || "별표"} ${want.annexRef.no}`
      : (want.level === "조" ? `제${want.no}조` : `제${want.no}${want.level}`);
    if (!spot) { miss.push(`${label} ${want.title || ""}`.trim()); return; }
    /* 번호는 조각의 것을 그대로 쓴다. 자리(어느 편ㆍ장 아래인가)는 지금
       트리의 것을 지킨다 —— 조각은 그 마디의 알맹이를 담은 것이지 편제를
       담은 것이 아니다. */
    spot.list[spot.at] = JSON.parse(JSON.stringify(want));
    done.push(`${label} ${want.title || ""}`.trim());
  };
  put(part.node);
  for (const a of part.annex || []) put(a);
  return { 바꾼것: done, 못찾은것: miss };
}

/** 조각인가 */
export function isPart(o) {
  return !!o && o.format === FMT && !!o.node;
}
