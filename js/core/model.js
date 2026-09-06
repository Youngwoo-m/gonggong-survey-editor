/* ============================================================
   core/model.js — 순수 트리 모델
   DOM·파일 I/O 의존 없음. 데스크톱(Electron) 전환 시 그대로 재사용.
   ============================================================ */

/* 편집기를 한 벌로 합치면서 '규정' 이 편 위에 한 단 더 생겼다.
   트리 최상위 세 줄이 개정 대상 규정(3종)이고, 그 아래로 편·장·절·관·조가 이어진다. */
export const REG_LEVEL = "규정";
export const LEVELS = [REG_LEVEL, "편", "장", "절", "관", "조"];
export const levelIndex = (lv) => LEVELS.indexOf(lv);

/* 규정 안에서 최상위로 올 수 있는 단 — 규정마다 다르다.
   작업규정은 '편' 으로 시작하지만, 성과심사·무인비행장치 규정은 '장' 으로 시작한다.
   규정 노드가 제 top 을 지니므로(core/targets.js), 여기서는 그것을 읽어 쓴다.
   규정 노드가 없는 트리(참조 창에 띄운 낱 규정)를 위해 기본값을 남겨 둔다. */
export let ROOT_LEVEL = "편";
export function setRootLevel(lv) { if (LEVELS.includes(lv)) ROOT_LEVEL = lv; }

/** 규정 노드인가 — 트리 최상위 세 줄 */
export function isRegNode(n) { return !!(n && n.level === REG_LEVEL); }

let _seq = 0;
export function newId(prefix = "n") {
  _seq += 1;
  return `${prefix}${Date.now().toString(36)}${_seq.toString(36)}`;
}

export function makeNode(level, title = "", body = "") {
  return {
    id: newId(level === "조" ? "a" : "h"),
    level, no: 0, branch: 0,
    title, body,
    status: "신설",
    legacyNo: "",
    reason: "",
    sourceRef: null,
    history: [],
    children: [],
    collapsed: false,
  };
}

/* ---------- 탐색 ---------- */
export function walk(nodes, fn, parent = null, depth = 0) {
  for (const n of nodes) {
    if (fn(n, parent, depth) === false) return false;
    if (walk(n.children, fn, n, depth + 1) === false) return false;
  }
  return true;
}

export function findNode(nodes, id) {
  let found = null;
  walk(nodes, (n) => { if (n.id === id) { found = n; return false; } });
  return found;
}

export function findParent(nodes, id) {
  let res = null;
  walk(nodes, (n, p) => { if (n.id === id) { res = p; return false; } });
  return res;
}

/** 부모의 children 배열을 반환 (루트면 nodes 자체) */
export function siblingsOf(nodes, id) {
  const p = findParent(nodes, id);
  return p ? p.children : nodes;
}

export function pathOf(nodes, id) {
  const path = [];
  (function rec(list, trail) {
    for (const n of list) {
      const t = trail.concat(n);
      if (n.id === id) { path.push(...t); return true; }
      if (rec(n.children, t)) return true;
    }
    return false;
  })(nodes, []);
  return path;
}

export function isDescendant(node, targetId) {
  let hit = false;
  walk(node.children, (n) => { if (n.id === targetId) { hit = true; return false; } });
  return hit;
}

export function countBy(nodes, level) {
  let c = 0;
  walk(nodes, (n) => { if (n.level === level) c += 1; });
  return c;
}

export function flatten(nodes) {
  const out = [];
  walk(nodes, (n, p, d) => { out.push({ node: n, parent: p, depth: d }); });
  return out;
}

/* ---------- 계층 규칙 ---------- */
/** child 를 parent(또는 루트) 아래 둘 수 있는가 */
export function canContain(parentLevel, childLevel, parentNode = null) {
  const ci = levelIndex(childLevel);
  if (ci < 0) return false;
  // 루트에 올 수 있는 것은 규정뿐이다 — 조문은 반드시 어느 규정에 속한다
  if (parentLevel === null) return childLevel === REG_LEVEL;
  // 규정 아래에서는 그 규정의 최상위 단부터 (작업규정만 '편' 이 있다)
  if (parentLevel === REG_LEVEL) {
    const top = (parentNode && parentNode.top) || ROOT_LEVEL;
    return ci >= levelIndex(top) && ci <= levelIndex("조");
  }
  const pi = levelIndex(parentLevel);
  if (pi < 0) return false;
  return ci > pi;                                     // 편>장>절>관>조 순서만
}

/* ---------- 이동/삽입 ---------- */
export function detach(nodes, id) {
  const list = siblingsOf(nodes, id);
  const i = list.findIndex((n) => n.id === id);
  if (i < 0) return null;
  return list.splice(i, 1)[0];
}

/** targetId 기준 pos('before'|'after'|'into') 위치에 node 삽입. 성공 시 true */
export function insertAt(nodes, node, targetId, pos) {
  if (targetId === null) {                            // 루트 끝
    if (!canContain(null, node.level)) return false;
    nodes.push(node); return true;
  }
  const target = findNode(nodes, targetId);
  if (!target) return false;

  if (pos === "into") {
    if (!canContain(target.level, node.level, target)) return false;
    target.children.push(node);
    target.collapsed = false;
    return true;
  }
  const parent = findParent(nodes, targetId);
  if (!canContain(parent ? parent.level : null, node.level, parent)) return false;
  const list = parent ? parent.children : nodes;
  const i = list.findIndex((n) => n.id === targetId);
  list.splice(pos === "before" ? i : i + 1, 0, node);
  return true;
}

/* ---------- 번호 자동 재계산 ---------- */
/**
 * 규칙
 *  - 편/장/절/관 : 같은 부모 안에서 1부터
 *  - 조          : 규정 하나 안에서 통번호 1부터 (현행 작업규정 방식)
 *
 * 편집기를 합치면서 트리에 규정이 셋 들어왔다. 조 번호는 규정마다 따로
 * 매겨야 한다 — 규정(3종)을 통틀어 1..330 으로 매기면 어느 규정도 제 번호를
 * 갖지 못한다. 규정 노드를 만나면 통번호를 0 으로 되돌린다.
 */
export function renumber(nodes) {
  let joNo = 0;
  (function rec(list, inAnnex) {
    const counters = { 편: 0, 장: 0, 절: 0, 관: 0 };
    const anx = {};                                   // 별표·별지 각각 1부터
    for (const n of list) {
      const annexBranch = inAnnex || !!n.isAnnex;
      if (n.level === REG_LEVEL) {
        joNo = 0;                                     // 규정이 바뀌면 조 번호를 다시 1부터
        rec(n.children, false);
        continue;
      }
      if (n.annexRef) {
        // 별표·별지는 구분별로 다시 매긴다 (별표 1,2,3 / 별지 1,2)
        const g = n.annexRef.gubun || "별표";
        anx[g] = (anx[g] || 0) + 1;
        n.annexRef.no = String(anx[g]);
      } else if (annexBranch) {
        // 별표 묶음 머리(별표 (43건))는 번호를 매기지 않는다
      } else if (n.level === "조") {
        joNo += 1; n.no = joNo; n.branch = 0;
      } else {
        counters[n.level] = (counters[n.level] || 0) + 1; n.no = counters[n.level];
      }
      rec(n.children, annexBranch);
      // 묶음 머리의 건수 표시를 맞춰 준다
      if (n.isAnnex) {
        const g = (n.children.find((c) => c.annexRef)?.annexRef.gubun) || n.annexGubun || "별표";
        n.annexGubun = g;
        n.title = `${g} (${n.children.length}건)`;
      }
    }
  })(nodes, false);
  return nodes;
}

/** 별표·별지·부록처럼 조번호를 쓰지 않는 항목인가 */
export function isAnnexNode(n) {
  return !!(n && (n.annexRef || n.isAnnex || n.isAppendix));
}

export function labelOf(n) {
  if (!n) return "";
  if (isRegNode(n)) return n.title || "";          // 규정은 번호가 아니라 이름으로 부른다
  if (isAnnexNode(n)) {
    const s = shortLabel(n);
    return n.annexRef ? `${s}(${n.title || "제목없음"})` : s;
  }
  const num = `제${n.no}${n.level}` + (n.branch ? `의${n.branch}` : "");
  return n.level === "조" ? `${num}(${n.title || "제목없음"})` : `${num} ${n.title || ""}`.trim();
}

export function shortLabel(n) {
  if (!n) return "";
  if (isRegNode(n)) return n.short || n.title || "";
  if (n.annexRef) return `${n.annexRef.gubun} ${n.annexRef.no}`;
  if (n.isAnnex || n.isAppendix) return n.title || "";
  return `제${n.no}${n.level}` + (n.branch ? `의${n.branch}` : "");
}

/** 화면·경로 표시용 라벨 — 별표·부록·목차 항목은 자체 번호를 쓴다 */
export function displayLabel(n) {
  if (!n) return "";
  if (isRegNode(n)) return n.short || n.title || "";
  if (n.annexRef) return `${n.annexRef.gubun} ${n.annexRef.no}`;
  if (n.isAnnex || n.isAppendix) return n.title || "";
  if (n.outlineNo) return n.outlineNo;
  return shortLabel(n);
}

/* ---------- 복제 ---------- */
export function cloneTree(node, { asReference = false } = {}) {
  const copy = JSON.parse(JSON.stringify(node));
  (function rec(n) {
    n.id = newId(n.level === "조" ? "a" : "h");
    if (asReference) {
      n.status = "신설";
      n.reason = n.reason || "참조 규정에서 인용";
    }
    n.children.forEach(rec);
  })(copy);
  return copy;
}

/* ---------- 검색 ---------- */
export function search(nodes, q) {
  const s = (q || "").trim();
  if (!s) return [];
  const low = s.toLowerCase();
  const hits = [];
  walk(nodes, (n) => {
    const hay = [labelOf(n), n.title, n.body, n.transTitle, n.transBody, n.legacyNo]
      .filter(Boolean).join(" ").toLowerCase();
    if (hay.includes(low)) hits.push(n.id);
  });
  return hits;
}

/* ---------- 상태 · 이력 ---------- */
export const STATUSES = ["유지", "수정", "신설", "이동", "이동·수정", "통합", "삭제"];

/**
 * 화면에 적을 상태 이름표 —— 유래(origin)를 얹어 짓는다.
 *
 * 흩어져 있던 현행 조문 여럿을 합쳐 새로 둔 조문은 상태를 「신설」 그대로 두고
 * 마디에 `origin: "통합"` 만 지닌다. 상태 낱말을 늘리면 신설을 세는 자리와
 * 개정문을 짓는 자리 스무 곳 남짓이 이 조문을 신설이 아니라고 보게 되므로,
 * 세는 것은 상태로 하고 보이는 이름만 「통합·신설」 로 적는다.
 *
 * 트리ㆍ비교표ㆍ조문 상세가 모두 이 함수를 쓴다.
 * @param {{status?:string, origin?:string}} node
 * @returns {string} 이름표. 상태가 없으면 빈 글.
 */
export function statusLabel(node) {
  const st = (node && node.status) || "";
  if (!st) return "";
  return node.origin === "통합" ? `통합·${st}` : st;
}

/**
 * 편집 동작에 따라 조문 상태를 자동으로 올린다.
 *  · 신설된 조문은 무엇을 해도 '신설' 로 남는다
 *  · 이동 + 수정 이 겹치면 '이동·수정'
 */
export function bumpStatus(node, kind) {
  const s = node.status || "유지";
  if (s === "신설" || s === "통합" || s === "삭제") return s;

  // 이관 — 규정을 넘어 옮긴 것. 규정 안의 이동과 달리 근거 법령이 바뀌므로
  // 다른 무엇에도 덮이지 않는다 (개정 전후 비교표에서도 따로 적어야 한다).
  if (kind === "이관") { node.status = "이관"; return node.status; }
  if (s === "이관") return s;

  if (kind === "이동") {
    node.status = (s === "수정" || s === "이동·수정") ? "이동·수정" : "이동";
  } else if (kind === "수정") {
    node.status = (s === "이동" || s === "이동·수정") ? "이동·수정" : "수정";
  }
  return node.status;
}

/** 조문 단위 변경 이력 한 줄 추가 */
export function addHistory(node, entry) {
  if (!node.history) node.history = [];
  node.history.push(Object.assign({ at: new Date().toISOString() }, entry));
  if (node.history.length > 200) node.history.shift();
  return node.history;
}

/* ---------- 통계 ---------- */
export function stats(nodes) {
  const st = { 편: 0, 장: 0, 절: 0, 관: 0, 조: 0, 별표: 0, 별지: 0, 변경: 0 };
  (function rec(list, inAnnex) {
    for (const n of list) {
      if (n.isDeleted) continue;                // 없앤 것을 모아 둔 묶음은 세지 않는다
      const annexBranch = inAnnex || !!n.isAnnex;
      if (n.annexRef) {
        const g = n.annexRef.gubun || "별표";
        st[g] = (st[g] || 0) + 1;
      } else if (!annexBranch && st[n.level] !== undefined) {
        st[n.level] += 1;                       // 별표 묶음 머리는 편으로 세지 않는다
      }
      if (n.status && n.status !== "유지") st.변경 += 1;
      rec(n.children || [], annexBranch);
    }
  })(nodes || [], false);
  return st;
}
