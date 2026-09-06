/* ============================================================
   core/diff.js — 개정 전후 비교 (대비표 생성 엔진)
   ------------------------------------------------------------
   두 트리를 받아 조문 단위 대응 관계를 계산한다.
   대응은 노드 id 로 판정한다.
     · base 에만 있음  → 삭제
     · work 에만 있음  → 신설
     · 둘 다 있음      → 부모 체인 변화(이동) / 제목·본문 변화(수정) 판정
   ============================================================ */
import * as M from "./model.js?v=20260907a";
import { stripImgTags } from "./objects.js?v=20260907a";
import { wordDiff, afterRuns, beforeRuns, hasChange } from "./textdiff.js?v=20260907a";

/* 「통합·신설」 은 makeRow 가 매기는 kind 가 아니라 요약에서만 쓰는 이름이다.
   현행 여럿을 합쳐 새로 둔 조문(origin="통합")을 신설에서 갈라 세려는 것이다. */
export const KIND_LIST = ["신설", "통합·신설", "삭제", "이동", "이동·수정", "수정", "통합", "유지"];

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

/* ────────────────────────────────── 삭제 자리표시
 *
 * 현행에서 없앤 조를 개정안 트리에 자리표시로 남겨 둔다.
 *
 *     id "del-jo-193" · legacyNo "제193조" · isDeleted true
 *     제목에 「제193조 정의」처럼 현행 이름을 통째로 담는다
 *     모두 「삭제 (43건)」 이라는 편 아래에 모아 둔다
 *
 * 견주기는 마디 id 로 짝을 짓는데, 그 id 는 현행 트리에 없다. 그대로 두면
 * **없앤 조가 새로 만든 조로 뒤집혀** 대비표에 <제193조 정의 신설> 로 나온다.
 * 게다가 현행 제193조는 짝을 잃어 삭제 줄로도 한 번 더 나오므로, 한 조가
 * 두 줄을 차지한다.
 *
 * 그래서 자리표시는 견줄 목록에서 빼고, 거기 적어 둔 개정 사유만 그 조의
 * 삭제 줄로 넘긴다.
 */

/** '제193조' · '제7조의2' → 짝을 지을 열쇠 */
function legacyKey(s) {
  const m = /제\s*(\d+)\s*조(?:\s*의\s*(\d+))?/.exec(String(s || ""));
  return m ? `${m[1]}${m[2] ? `-${m[2]}` : ""}` : "";
}

/** 마디 자신의 열쇠 — 현행 조를 자리표시와 맞대 보려는 것 */
function selfKey(n) {
  if (!n || n.level !== "조" || !n.no) return "";
  return `${n.no}${n.branch ? `-${n.branch}` : ""}`;
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
        /* 표식을 걷어 낸 글(body)과 함께 날 글도 실어 보낸다.
           비교표 칸에 진짜 표를 끼워 넣으려면 <img id="…"> 의 id 가 있어야
           하는데, 견주기 전에 자리표시로 바꾸면서 id 가 사라진다. */
        raw: n.body || "",
      });
      rec(n.children, parentIds.concat(n.id), t);
    }
  })(tree || [], [], []);
  return map;
}

/** note 는 삭제 자리표시 마디 — 그 조를 왜 없앴는지 적혀 있다 */
/** splitFrom 은 이 조를 나누어 낸 현행 조의 이름표 — <현행 제29조에서 나눔> */
function makeRow(b, w, note = null, splitFrom = "") {
  let kind, tRuns = null, bRuns = null;

  if (!b) kind = splitFrom ? (w.node.status || "이동·수정") : "신설";
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
    before: b ? { label: b.label, title: b.title, body: b.body, path: b.path,
                  raw: b.raw } : null,
    after: w ? { label: w.label, title: w.title, body: w.body, path: w.path,
                 raw: w.raw } : null,
    // 개정문을 지으려면 '무엇을 무엇으로' 인지 짝지어야 하므로 날 도막도 남긴다
    titleDiff: tRuns, bodyDiff: bRuns,
    beforeTitleRuns: tRuns ? beforeRuns(tRuns) : null,
    afterTitleRuns: tRuns ? afterRuns(tRuns) : null,
    beforeBodyRuns: bRuns ? beforeRuns(bRuns) : null,
    afterBodyRuns: bRuns ? afterRuns(bRuns) : null,
    reason: (note && note.reason) || owner.node.reason || "",
    status: (note && note.status) || owner.node.status || "",
    // 유래 — 현행 조문 여럿을 합쳐 새로 둔 것이면 "통합"
    origin: owner.node.origin || "",
    source: src ? `${src.doc} ${src.label}` : "",
    numberChanged: !!(b && w && b.label !== w.label),
    splitFrom,
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

  /* ── 한 조를 여러 조로 나눈 것
   *
   * 개정안 마디의 id 가 「현행 id-sN」 이면 그 현행 조에서 나누어 낸 것이다.
   *
   *     현행 제29조  (a33)  → 개정안 제42~46조  (a33-s1 … a33-s5)
   *     현행 제188조 (a210) → 개정안 제197~201조 (a210-s1 … a210-s5)
   *
   * 그대로 두면 현행 조는 짝을 잃어 **삭제**로, 나눈 조들은 짝이 없어
   * **신설**로 잡힌다. 없앤 적도 새로 만든 적도 없는데 한 조가 여섯 줄로
   * 부풀고, 대비표를 읽는 이는 없앤 조문으로 읽는다.
   *
   * 첫 조각을 현행 조의 짝으로 삼고, 나머지는 '나눈 것' 으로 표시한다.
   */
  const splitOf = new Map();          // 개정안 id -> {base, nth}
  const splitHead = new Map();        // 현행 id  -> 첫 조각의 id
  for (const w of W.values()) {
    const m = /^(.+)-s(\d+)$/.exec(String(w.id || ""));
    if (!m) continue;
    const base = B.get(m[1]);
    if (!base || W.has(m[1])) continue;      // 밑동이 개정안에 그대로 있으면 나눈 것이 아니다
    const nth = +m[2];
    splitOf.set(w.id, { base, nth });
    const cur = splitHead.get(base.id);
    if (!cur || nth < splitOf.get(cur).nth) splitHead.set(base.id, w.id);
  }

  /* 삭제 자리표시는 견줄 것이 아니라 '없앴다는 표시' 다. 목록에서 빼고
     적어 둔 사유만 챙겨 둔다 (위 주석 참고). */
  const trash = new Map();
  for (const [id, w] of [...W]) {
    if (!w.node || !w.node.isDeleted) continue;
    const key = legacyKey(w.node.legacyNo);
    if (key) trash.set(key, w.node);
    W.delete(id);
  }

  // 1) 개정안 순서대로 기본 행 생성
  const workOrdered = [...W.values()].sort((x, y) => x.order - y.order);
  const rows = workOrdered.map((w) => {
    const sp = splitOf.get(w.id);
    if (!sp) return makeRow(B.get(w.id) || null, w);
    // 첫 조각이 현행 조의 짝이다. 나머지는 어디에서 나왔는지만 적는다.
    return splitHead.get(sp.base.id) === w.id
      ? makeRow(sp.base, w)
      : makeRow(null, w, null, sp.base.label);
  });

  // 2) 삭제된 항목을 원래 위치(직전에 살아남은 항목 뒤)에 끼워 넣는다
  const baseOrdered = [...B.values()].sort((x, y) => x.order - y.order);
  const pending = new Map();            // anchorId(null=맨앞) -> [row,...]
  let anchor = null;
  for (const b of baseOrdered) {
    // 나누어 간 조는 없앤 것이 아니다 — 첫 조각이 그 자리를 잇는다
    if (splitHead.has(b.id)) { anchor = splitHead.get(b.id); continue; }
    if (W.has(b.id)) { anchor = b.id; continue; }
    if (!pending.has(anchor)) pending.set(anchor, []);
    // 그 조를 왜 없앴는지 자리표시에 적어 두었으면 함께 싣는다
    pending.get(anchor).push(makeRow(b, null, trash.get(selfKey(b.node))));
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
  /* 신설 가운데 현행 여럿을 합쳐 둔 것을 갈라 센다 — 두 수를 더하면 신설 전체다 */
  const mergedNew = merged.filter((r) => r.kind === "신설" && r.origin === "통합").length;
  summary["통합·신설"] = mergedNew;
  summary["신설"] -= mergedNew;
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

/**
 * 비교표에 적을 갈래 이름표 —— 유래를 얹는다.
 * 신설 가운데 현행 조문 여럿을 합쳐 둔 것은 「통합·신설」 로 적는다.
 * 세는 자리(kind)는 그대로 「신설」 이다 (model.js 의 statusLabel 과 같은 뜻).
 * @param {{kind:string, origin?:string}} row
 */
export function kindLabel(row) {
  if (!row) return "";
  return row.kind === "신설" && row.origin === "통합" ? "통합·신설" : row.kind;
}

/** 런 배열 → 순수 텍스트 */
export function runsToText(runs, fallback) {
  if (!runs) return fallback || "";
  return runs.map((r) => r.s).join("");
}
