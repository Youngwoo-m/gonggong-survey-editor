/* ============================================================
   core/diff.js — 개정 전후 비교 (대비표 생성 엔진)
   ------------------------------------------------------------
   두 트리를 받아 조문 단위 대응 관계를 계산한다.
   대응은 노드 id 로 판정한다.
     · base 에만 있음  → 삭제
     · work 에만 있음  → 신설
     · 둘 다 있음      → 부모 체인 변화(이동) / 제목·본문 변화(수정) 판정
   ============================================================ */
import * as M from "./model.js?v=20260823a";
import { stripImgTags } from "./objects.js?v=20260823a";
import { wordDiff, afterRuns, beforeRuns, hasChange } from "./textdiff.js?v=20260823a";

export const KIND_LIST = ["신설", "삭제", "이동", "이동·수정", "수정", "통합", "유지"];

/** 별표·별지는 '서식 변경 내용' 아래에 올린 파일 이름까지 붙여 견준다 */
function bodyOf(n) {
  /* 표·수식은 본문에 <img id="…"> 표식으로 박혀 있다. 그대로 견주면 어절
     비교가 표식 가운데를 잘라, 비교표에 markup 조각이 그대로 드러난다.
     견주기 전에 자리표시로 바꾼다 — 표가 몇째 것인지는 남는다. */
  const b = stripImgTags(n.body || "", (i) => `[표 ${i}]`);
  if (n.annexRef && n.annexRef.newFileName) {
    return (b ? `${b}\n` : "") + `[바뀐 서식 파일] ${n.annexRef.newFileName}`;
  }
  return b;
}

function index(tree) {
  const map = new Map();
  let order = 0;
  (function rec(list, parentIds, trail) {
    for (const n of list) {
      const label = M.shortLabel(n);
      const t = trail.concat(label);
      map.set(n.id, {
        id: n.id, node: n, level: n.level,
        parentIds: parentIds.join(">"),
        order: order++,
        label, path: t.join(" › "),
        title: n.title || "", body: bodyOf(n), annex: !!n.annexRef,
      });
      rec(n.children, parentIds.concat(n.id), t);
    }
  })(tree || [], [], []);
  return map;
}

function makeRow(b, w) {
  let kind, tRuns = null, bRuns = null;

  if (!b) kind = "신설";
  else if (!w) kind = "삭제";
  else {
    tRuns = wordDiff(b.title, w.title);
    bRuns = wordDiff(b.body, w.body);
    const moved = b.parentIds !== w.parentIds;
    const edited = hasChange(tRuns) || hasChange(bRuns);
    kind = moved && edited ? "이동·수정" : moved ? "이동" : edited ? "수정" : "유지";
    if (w.node.status === "통합") kind = "통합";
  }

  const owner = w || b;
  const src = owner.node.sourceRef;
  return {
    id: owner.id,
    kind,
    level: owner.level,
    annex: !!owner.annex,
    before: b ? { label: b.label, title: b.title, body: b.body, path: b.path } : null,
    after: w ? { label: w.label, title: w.title, body: w.body, path: w.path } : null,
    // 개정문을 지으려면 '무엇을 무엇으로' 인지 짝지어야 하므로 날 도막도 남긴다
    titleDiff: tRuns, bodyDiff: bRuns,
    beforeTitleRuns: tRuns ? beforeRuns(tRuns) : null,
    afterTitleRuns: tRuns ? afterRuns(tRuns) : null,
    beforeBodyRuns: bRuns ? beforeRuns(bRuns) : null,
    afterBodyRuns: bRuns ? afterRuns(bRuns) : null,
    reason: owner.node.reason || "",
    status: owner.node.status || "",
    source: src ? `${src.doc} ${src.label}` : "",
    numberChanged: !!(b && w && b.label !== w.label),
  };
}

/**
 * @param {Array} baseTree 기준(현행)
 * @param {Array} workTree 대상(개정안)
 * @param {object} opts { onlyChanged:boolean, joOnly:boolean }
 */
export function buildComparison(baseTree, workTree, opts = {}) {
  const B = index(baseTree);
  const W = index(workTree);

  // 1) 개정안 순서대로 기본 행 생성
  const workOrdered = [...W.values()].sort((x, y) => x.order - y.order);
  const rows = workOrdered.map((w) => makeRow(B.get(w.id) || null, w));

  // 2) 삭제된 항목을 원래 위치(직전에 살아남은 항목 뒤)에 끼워 넣는다
  const baseOrdered = [...B.values()].sort((x, y) => x.order - y.order);
  const pending = new Map();            // anchorId(null=맨앞) -> [row,...]
  let anchor = null;
  for (const b of baseOrdered) {
    if (W.has(b.id)) { anchor = b.id; continue; }
    if (!pending.has(anchor)) pending.set(anchor, []);
    pending.get(anchor).push(makeRow(b, null));
  }

  let merged = [];
  if (pending.has(null)) merged.push(...pending.get(null));
  for (const r of rows) {
    merged.push(r);
    if (pending.has(r.id)) merged.push(...pending.get(r.id));
  }

  // 3) 요약 (필터 전 전체 기준)
  const summary = {
    총: merged.length,
    조: merged.filter((r) => r.level === "조" && !r.annex).length,
    별표: merged.filter((r) => r.annex).length,
  };
  for (const k of KIND_LIST) summary[k] = merged.filter((r) => r.kind === k).length;
  summary.변경 = merged.length - summary.유지;

  // 4) 필터
  let out = merged;
  if (opts.joOnly) out = out.filter((r) => r.level === "조" || r.annex);
  if (opts.onlyChanged) out = out.filter((r) => r.kind !== "유지");
  // 내용 변경 없이 위치(편제)만 바뀐 항목 숨기기 — '이동·수정'은 남는다
  if (opts.excludePureMove) out = out.filter((r) => r.kind !== "이동");
  out = out.map((r, i) => Object.assign({}, r, { seq: i + 1 }));

  return { rows: out, summary, all: merged };
}

/** 런 배열 → 순수 텍스트 */
export function runsToText(runs, fallback) {
  if (!runs) return fallback || "";
  return runs.map((r) => r.s).join("");
}
