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

/* ---------- 개정안 판 이름 ----------
   규정마다 머리글자를 달리하고 1.00 에서 0.01 씩 올린다.

     작업규정        vA-1.00 · vA-1.01 · vA-1.02 …
     성과심사 규정    vB-1.00 · vB-1.01 …
     무인비행장치 규정 vC-1.00 · vC-1.01 …

   백분의 일 자리까지 쓰므로 셈은 정수(1/100 단위)로 한다 — 소수로 더하면
   1.00 + 0.01 이 1.0099999… 로 앉는 일이 생긴다. */

const HUNDREDTH = 100;

/** n 번째 판 이름 (n = 0 이면 첫 판 작업-1.00) */
/* 예전 이름의 머리글자 —— 「vA-1.00」 을 아직 읽을 수 있어야 한다.
   2026-09-06 에 사람이 vA→작업 ㆍ vB→심사 ㆍ vC→드론 으로 바꾸었다. */
const OLD_PREFIX = { "작업": "A", "심사": "B", "드론": "C" };

export function revLabel(prefix, n) {
  const cents = HUNDREDTH + Math.max(0, n | 0);
  return `${prefix}-${(cents / HUNDREDTH).toFixed(2)}`;
}

/** 이 이름이 그 규정의 판 이름인가 — 맞으면 1/100 단위 값, 아니면 null */
export function revValue(prefix, label) {
  const txt = String(label || "").trim();
  const heads = [prefix];
  if (OLD_PREFIX[prefix]) heads.push("v" + OLD_PREFIX[prefix]);   // 옛 이름도 읽는다
  for (const h of heads) {
    const m = new RegExp(`^${h}-(\\d+)\\.(\\d{2})$`).exec(txt);
    if (m) return (+m[1]) * HUNDREDTH + (+m[2]);
  }
  return null;
}

/** 이미 쓰인 이름들 다음 판 */
export function nextRevLabel(prefix, used) {
  let max = HUNDREDTH - 1;                      // 아무것도 없으면 첫 판이 1.00
  for (const u of used || []) {
    const v = revValue(prefix, u);
    if (v !== null && v > max) max = v;
  }
  const cents = max + 1;
  return `${prefix}-${(cents / HUNDREDTH).toFixed(2)}`;
}

/** 대상 id 로 머리글자 (등록부에 없으면 이름 첫 글자) */
export function verPrefixOf(targetId) {
  const t = targetById(targetId);
  return (t && t.ver) || "X";
}
