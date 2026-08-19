/* ============================================================
   core/targets.js — 개정 대상 등록부
   ------------------------------------------------------------
   편집기를 세 벌에서 한 벌로 합치면서, 프로파일(코드)이 하던 일을
   등록부(데이터)가 대신한다.  data/targets.json 을 읽어 둔다.

   ■ 이 파일이 지키는 것 — 규정 경계

     어느 조문이 어느 규정 것인지 묻는 자리를 여기 한 곳으로 모은다.
     트리 최상위에 규정 세 줄이 서면서 '이 노드는 어느 규정인가' 를
     묻는 곳이 늘어난다. 그 물음의 답은 오직 여기에서만 낸다 —
     여기가 흩어지면 합친 보람이 없다. (UI 설계(안) v3 · 규칙 ③)

   ■ DOM 을 모른다

     core/ 의 규칙 그대로. 화면은 이 파일이 내주는 값만 쓴다.
   ============================================================ */

/** @type {{targets: Array}|null} */
let REG = null;

/** 규정 노드의 id 는 늘 이 꼴이다 — 트리 어디에서나 알아볼 수 있게 */
export const REG_PREFIX = "reg:";
export const regNodeId = (targetId) => REG_PREFIX + targetId;

/** 규정 노드인가 (트리 최상위 세 줄) */
export function isRegNode(n) {
  return !!(n && n.level === "규정");
}

/** 규정 노드의 id 에서 대상 id 를 뽑는다 */
export function targetIdOf(node) {
  if (!isRegNode(node)) return null;
  return node.targetId || (String(node.id).startsWith(REG_PREFIX)
    ? String(node.id).slice(REG_PREFIX.length) : null);
}

/* ---------- 적재 ---------- */

/**
 * 등록부를 읽어 둔다. 앱이 켜질 때 한 번 부른다.
 * @param {(path:string)=>Promise<object>} loadJSON  파일 읽는 함수 (adapters/fileio)
 */
export async function loadTargets(loadJSON) {
  const raw = await loadJSON("data/targets.json");
  const list = (raw && Array.isArray(raw.targets)) ? raw.targets : [];
  if (!list.length) throw new Error("개정 대상 등록부가 비어 있습니다: data/targets.json");
  REG = {
    targets: list.map((t) => Object.freeze({
      ...t,
      short: t.short || t.base,
      word: t.word || "개정안",
      top: t.top || "편",
      regId: regNodeId(t.id),
      /** 참조 창 묶음 차례 — [[key, label], …] */
      catOrder: (t.refOrder || []).map(([k, l]) => [k, l]),
      /** 이 대상에서만 앞으로 당기는 규정들 (없으면 빈 집합) */
      aerialSet: new Set(t.aerial || []),
    })),
  };
  Object.freeze(REG.targets);
  return REG.targets;
}

/** 등록된 개정 대상 전부 */
export function allTargets() {
  if (!REG) throw new Error("등록부를 아직 읽지 않았습니다 — loadTargets() 를 먼저 부르십시오.");
  return REG.targets;
}

/** id 로 하나 */
export function targetById(id) {
  return allTargets().find((t) => t.id === id) || null;
}

/** 규정 이름으로 하나 (예전 pmproj 의 baseName 을 옮겨 담을 때 쓴다) */
export function targetByBaseName(name) {
  if (!name) return null;
  return allTargets().find((t) => t.base === name) || null;
}

/** 첫 대상 — 화면을 열 때 고를 자리 */
export function firstTarget() { return allTargets()[0]; }

/* ---------- 규정 경계 ---------- */

/**
 * 트리에서 이 노드가 속한 규정을 찾는다.
 * @param {Array} tree   프로젝트 트리 (최상위가 규정 노드)
 * @param {string} nodeId
 * @returns {{regNode:object, target:object}|null}
 */
export function regionOf(tree, nodeId) {
  for (const reg of tree || []) {
    if (!isRegNode(reg)) continue;
    if (reg.id === nodeId || contains(reg.children, nodeId)) {
      return { regNode: reg, target: targetById(targetIdOf(reg)) };
    }
  }
  return null;
}

function contains(list, id) {
  for (const n of list || []) {
    if (n.id === id) return true;
    if (contains(n.children, id)) return true;
  }
  return false;
}

/**
 * 두 노드가 같은 규정에 속하는가 — 규정을 넘는 이동(이관)인지 가리는 데 쓴다.
 * 2단계에서 이관을 붙일 때 이 함수가 그 문이 된다.
 */
export function sameRegion(tree, aId, bId) {
  const a = regionOf(tree, aId), b = regionOf(tree, bId);
  return !!(a && b && a.regNode.id === b.regNode.id);
}

/** 이 규정 안에서 최상위로 올 수 있는 단 (작업규정만 '편' 이 있다) */
export function topLevelOf(target) {
  return (target && target.top) || "편";
}
