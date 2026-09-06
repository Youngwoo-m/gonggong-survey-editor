/* ============================================================
   core/validate.js — 정합성 검증 엔진
   ------------------------------------------------------------
   구조를 바꾸면 규정은 쉽게 깨진다. 내보내기 전에 먼저 확인한다.
     오류 : 그대로 두면 규정이 성립하지 않는 것
     경고 : 사람이 판단해야 하는 것
     정보 : 알아두면 좋은 것
   ============================================================ */
import * as M from "./model.js?v=20260907u";
import { CITE_CHAIN } from "./objects.js?v=20260907u";
import { checkCrossRefs, checkTerms, checkAnnexClash } from "./xrefs.js?v=20260907u";
import { QUALITY_ELEMENTS, elementsOf } from "./quality.js?v=20260907u";

export const LEVELS_OF = { 오류: 0, 경고: 1, 정보: 2 };

/* 같은 것을 가리키는 다른 표기 — 문서 안에서 섞여 쓰이면 알린다.
   뜻이 서로 다른 말은 여기에 넣지 아니한다. 섞여 쓰이는 것이 옳기 때문이다.
     수치지도 ≠ 수치지형도   서로 다른 성과다
     GPS ≠ GNSS             GPS 는 GNSS 를 이루는 하나다
                            (제2조는 'GPS·GLONASS·Galileo 등의 총칭' 으로 열거하고,
                             제54조는 'GPS 위성 5개 이상을 포함하는 GNSS 위성 신호' 라 한다) */
const TERM_SETS = [
  { name: "수치표고모델 / 수치표고모형", terms: ["수치표고모델", "수치표고모형"] },
  { name: "무인비행장치 / 무인항공기 / 드론 / UAV", terms: ["무인비행장치", "무인항공기", "드론", "UAV"] },
  { name: "정사영상 / 정사사진", terms: ["정사영상", "정사사진"] },
  { name: "점군 / 포인트클라우드", terms: ["점군", "포인트클라우드", "포인트 클라우드"] },
  { name: "성과심사 / 성과검사", terms: ["성과심사", "성과검사"] },
  { name: "기준점 / 표준점", terms: ["공공기준점", "공공표준점"] },
  { name: "네트워크 RTK 표기", terms: ["네트워크 RTK", "네트워크RTK", "Network RTK"] },
];

const RE_JO_CITE = /제\s*(\d+)\s*조(?:의\s*(\d+))?/g;
const RE_BYL_CITE = /별표\s*제?\s*(\d+)/g;

/* 출처 표시 — 정의 조문에 붙는 <현행 제150조 「정의」> 는 인용이 아니다 */
const RE_PROV = /<[^<>]*>/g;

/* 약칭 괄호 — 「…법률」(이하 "법"이라 한다) 제105조 처럼 법령 이름과 조 사이에 끼어
   인용이 남의 법령을 가리킨다는 표시를 끊어 놓는다. 자리만 남기고 지운다. */
const RE_ALIAS = /\((?:이하|약칭)[^()]*\)/g;

/* 앞의 법령·규정 이름이 미치는 자리인가 — 그 조는 이 규정의 조가 아니다.
   본문 링크를 거는 규칙(core/objects.js)과 같은 잣대를 쓴다. */
/* 규칙을 베끼지 아니하고 본문 링크와 같은 것을 가져다 쓴다. 두 벌을 두었더니
   한쪽만 고칠 때마다 화면의 링크와 검증 결과가 어긋났다 —
   가운뎃점(ㆍ)과 별표 사슬이 그렇게 갈라졌다. */
const CHAIN = CITE_CHAIN;
const OTHER_LAW = [
  new RegExp(`[」』]${CHAIN}`),                                   // 「도로법」 제2조 및 제5조
  new RegExp(`(?<![가-힣A-Za-z])(?:시행규칙|시행령|법률|법|영|규칙)${CHAIN}`),
  new RegExp(`(?:그|같은|이)\\s*(?:규정|지침|준칙|고시|기준)${CHAIN}`),  // 그 규정 제20조제1항
  new RegExp(`[가-힣]{2,20}(?:법률|법|규칙|규정|지침|준칙|기준|령)${CHAIN}`),
];

const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();

/**
 * @param {object} project
 * @param {object} opts { versionId, longBodyChars }
 * @returns {{items:Array, summary:object}}
 */
/**
 * 검증은 규정 한 종을 놓고 도는 규칙들이다 — 조번호 중복·끊김, 별표 인용 따위.
 * 편집기를 합치면서 트리에 규정이 셋 들어왔으므로, 규정(3종)을 한 덩이로 돌리면
 * 규정(3종) 모두에 있는 제1조가 '조번호 중복' 으로 잡힌다.
 * 그래서 규정마다 따로 돌리고 결과를 합친다 — 규칙 자체는 손대지 않는다.
 *
 * 규정 사이를 가로지르는 검증(끊어진 인용·용어 불일치·별표 번호 충돌)은
 * 2단계에서 여기에 더한다.
 */
export function validate(project, opts = {}) {
  const v = project.version(opts.versionId || project.currentId);
  if (!v) return { items: [], summary: { 오류: 0, 경고: 0, 정보: 0, 총: 0 } };

  const baseV = project.base;
  const regs = (v.tree || []).filter(M.isRegNode);
  if (regs.length) {
    // 기준 판에서 같은 규정을 찾아 짝지어 준다 — 기준 대비 검증은 규정끼리 견줘야 한다
    const baseRegs = new Map(
      ((baseV && baseV.tree) || []).filter(M.isRegNode).map((n) => [n.targetId || n.id, n]));
    const items = [];
    for (const reg of regs) {
      const baseReg = baseRegs.get(reg.targetId || reg.id);
      const one = validateTree(reg.children, opts, {
        baseTree: (baseV && baseV.id !== v.id && baseReg) ? baseReg.children : null,
        top: reg.top || M.ROOT_LEVEL,
        regName: reg.title || M.shortLabel(reg),
      });
      const head = M.shortLabel(reg);
      for (const it of one) {
        it.path = it.path ? `${head} › ${it.path}` : head;
        items.push(it);
      }
    }
    items.push(...crossChecks(v.tree));
    items.sort((a, b) => LEVELS_OF[a.level] - LEVELS_OF[b.level]);
    return { items, summary: summarize(items) };
  }
  const items = validateTree(v.tree, opts, {
    baseTree: (baseV && baseV.id !== v.id) ? baseV.tree : null,
  });
  return { items, summary: summarize(items) };
}

function summarize(items) {
  const summary = { 오류: 0, 경고: 0, 정보: 0, 총: items.length };
  for (const it of items) summary[it.level] = (summary[it.level] || 0) + 1;
  return summary;
}

/** 규정 한 종을 검증한다 */
function validateTree(tree, opts = {}, ctx = {}) {
  const LONG = opts.longBodyChars || 1800;
  const baseTree = ctx.baseTree || null;   // 견줄 기준 트리 (같은 규정의 현행). 없으면 건너뛴다
  /* 최상위에 올 수 있는 단은 규정마다 다르다 — 작업규정만 '편' 이 있다.
     M.ROOT_LEVEL 은 화면에서 고른 규정을 따라 바뀌는 값이라, 그것을 보면
     어느 규정을 마지막에 눌렀는지에 따라 검증 결과가 달라진다. 규정이
     제 것을 들고 오게 한다. */
  const topLevel = ctx.top || M.ROOT_LEVEL;
  const regName = ctx.regName || "이 규정";

  const items = [];
  const add = (level, code, title, detail, node, path) =>
    items.push({ level, code, title, detail, nodeId: node ? node.id : null, path: path || "" });

  /* ---- 색인 만들기 ---- */
  const flat = [];
  (function rec(list, parent, trail) {
    for (const n of list) {
      if (n.isDeleted) continue;        // 없앤 것을 모아 둔 묶음은 검증하지 않는다
      const t = trail.concat(M.displayLabel(n));
      flat.push({ node: n, parent, path: t.join(" › ") });
      rec(n.children, n, t);
    }
  })(tree, null, []);

  const joByNo = new Map();          // "12|0" -> [node]
  const annexNos = new Set();        // 별표 번호
  let bodyAll = "";
  for (const f of flat) {
    const n = f.node;
    if (n.annexRef) {
      // 제목이 '(…안)' 으로 끝나면 채택 전의 안이므로, 가리키는 곳이 없어도 옳다
      if (!/\([^)]*안\)\s*$/.test(n.title || "")) annexNos.add(String(n.annexRef.no));
      // 별표가 다른 별표를 가리키는 것도 인용이다 —
      // 조문이 「성과 유형별 성과패키지의 구성」 을 위임하고 그 별표가 개별 서식을 가리킨다
      bodyAll += " " + (n.body || "") + " " + (n.citesAnnex || []).join(" ");
      continue;
    }
    if (n.level === "조") {
      const k = `${n.no}|${n.branch || 0}`;
      if (!joByNo.has(k)) joByNo.set(k, []);
      joByNo.get(k).push(f);
    }
    // 조문이 품은 표가 가리키는 별표도 인용이다 (gendraft2025.py 가 적어 둔다)
    bodyAll += " " + (n.title || "") + " " + (n.body || "")
             + " " + (n.citesAnnex || []).join(" ");
  }

  /* ---- 1. 중복 조번호 (오류) ---- */
  for (const [k, arr] of joByNo) {
    if (arr.length > 1) {
      const [no, br] = k.split("|");
      add("오류", "dup-no", `조번호 중복 — 제${no}조${br !== "0" ? `의${br}` : ""}`,
        `같은 번호가 ${arr.length}곳에 있습니다: ${arr.map((x) => x.path).join(" / ")}`,
        arr[0].node, arr[0].path);
    }
  }

  /* ---- 2. 조번호 누락 (오류) ---- */
  const nos = [...joByNo.keys()].filter((k) => k.endsWith("|0")).map((k) => +k.split("|")[0]).sort((a, b) => a - b);
  const gaps = [];
  for (let i = 1; i < nos.length; i++) {
    if (nos[i] - nos[i - 1] > 1) gaps.push(`제${nos[i - 1]}조 → 제${nos[i]}조`);
  }
  if (gaps.length) {
    add("오류", "gap-no", `조번호가 끊겼습니다 (${gaps.length}곳)`,
      `번호가 이어지지 않습니다: ${gaps.slice(0, 8).join(", ")}${gaps.length > 8 ? " …" : ""}`, null, "");
  }

  /* ---- 3. 계층 위반 (오류) ---- */
  for (const f of flat) {
    const n = f.node;
    if (n.annexRef || n.isAnnex || n.isAppendix || n.outlineNo) continue;
    const pi = f.parent ? M.levelIndex(f.parent.level) : -1;
    const ci = M.levelIndex(n.level);
    if (ci < 0) continue;
    if (f.parent && ci <= pi) {
      add("오류", "hierarchy", `계층 위반 — ${M.displayLabel(n)}`,
        `${f.parent.level} 아래에 ${n.level} 이 들어갈 수 없습니다. (편▸장▸절▸관▸조 순서)`, n, f.path);
    }
    if (!f.parent && ci > M.levelIndex(topLevel)) {
      add("오류", "hierarchy-root", `최상위 계층 위반 — ${M.displayLabel(n)}`,
        `「${regName}」 의 최상위에는 '${topLevel}' 까지만 올 수 있습니다. 현재 '${n.level}'.`, n, f.path);
    }
  }

  /* ---- 4. 끊어진 인용 (오류) ----
     본문의 「제N조」 인용은 그 버전의 조 번호를 가리킨다. 번호를 다시 매길 때
     본문의 인용도 함께 옮기므로(scripts/gendraft2025.py), 지금 번호로 확인한다.
     현행 번호로만 남아 어긋난 것은 아래 5에서 따로 짚는다. */
  const liveNow = new Set();                  // 지금 버전에 있는 조 번호
  for (const f of flat) {
    if (f.node.level === "조" && !f.node.annexRef) liveNow.add(M.shortLabel(f.node));
  }
  const baseVer = baseTree ? { tree: baseTree } : null;
  const liveLegacy = new Set();               // 현재 버전에 살아 있는 현행 조번호
  const legacyToNow = new Map();              // 현행 번호 → 지금 번호
  for (const f of flat) {
    const n = f.node;
    if (n.level === "조" && n.legacyNo) {
      liveLegacy.add(n.legacyNo.replace(/\s/g, ""));
      legacyToNow.set(n.legacyNo.replace(/\s/g, ""), M.shortLabel(n));
    }
  }
  const baseLegacy = new Set();
  if (baseVer) {
    M.walk(baseVer.tree, (n) => {
      if (n.level === "조" && n.legacyNo) baseLegacy.add(n.legacyNo.replace(/\s/g, ""));
    });
  }

  for (const f of flat) {
    const n = f.node;
    if (n.annexRef) continue;
    // 출처 표시(<현행 제150조 「정의」>)는 인용이 아니므로 자리만 남기고 지운다
    const text = String(n.body || "")
      .replace(RE_PROV, (s) => " ".repeat(s.length))
      .replace(RE_ALIAS, (s) => " ".repeat(s.length));
    const gone = new Set(), moved = new Set();
    let m;
    RE_JO_CITE.lastIndex = 0;
    while ((m = RE_JO_CITE.exec(text))) {
      const key = `제${+m[1]}조${m[2] ? `의${+m[2]}` : ""}`;
      // 다른 법령·규정의 조를 가리키는 자리는 건드리지 않는다
      const before = text.slice(0, m.index);
      if (OTHER_LAW.some((re) => re.test(before))) continue;
      if (liveNow.has(key)) continue;                   // 지금 있는 조를 가리킨다
      // 지금은 없는 번호다 — 현행 번호로 남아 있는 것인지, 아예 사라진 것인지 가른다
      if (baseLegacy.has(key) && liveLegacy.has(key)) moved.add(`${key}→${legacyToNow.get(key)}`);
      else gone.add(key);
    }
    if (gone.size) {
      add("오류", "broken-ref", `없는 조문을 인용합니다 — ${M.displayLabel(n)}`,
        `본문이 ${[...gone].join(", ")} 를 인용하지만 개정안에 그 조문이 없습니다.`, n, f.path);
    }
    if (moved.size) {
      add("경고", "ref-renumber", `인용이 현행 번호로 남아 있습니다 — ${M.displayLabel(n)}`,
        `새 번호로 고쳐야 합니다: ${[...moved].slice(0, 6).join(", ")}${moved.size > 6 ? " …" : ""}`, n, f.path);
    }
  }

  /* ---- 5. 고아 별표 (경고) ---- */
  if (annexNos.size) {
    const cited = new Set();
    let m;
    RE_BYL_CITE.lastIndex = 0;
    while ((m = RE_BYL_CITE.exec(bodyAll))) cited.add(m[1]);
    const orphan = [...annexNos].filter((no) => !cited.has(String(no).replace(/의.*/, "")));
    if (orphan.length) {
      add("경고", "orphan-annex", `인용되지 않는 별표 ${orphan.length}건`,
        `어느 조문에서도 인용하지 않습니다: 별표 ${orphan.slice(0, 12).join(", ")}${orphan.length > 12 ? " …" : ""}`, null, "");
    }
  }

  /* ---- 6. 빈 본문 · 제목 없음 (경고) ---- */
  for (const f of flat) {
    const n = f.node;
    if (n.annexRef || n.isAnnex || n.isAppendix) continue;
    if (n.level === "조") {
      if (!norm(n.body)) {
        add("경고", "empty-body", `본문이 비었습니다 — ${M.displayLabel(n)}`,
          n.title ? `제목만 있고 조문 내용이 없습니다.` : `제목과 본문이 모두 비어 있습니다.`, n, f.path);
      }
      if (!norm(n.title)) {
        add("경고", "no-title", `제목이 없습니다 — ${M.displayLabel(n)}`, `조문 제목을 넣어 주세요.`, n, f.path);
      }
    } else if (!norm(n.title)) {
      add("경고", "no-title", `제목이 없습니다 — ${M.displayLabel(n)}`, `${n.level} 제목을 넣어 주세요.`, n, f.path);
    }
    if (n.level !== "조" && !n.children.length) {
      add("경고", "empty-branch", `하위 항목이 없습니다 — ${M.displayLabel(n)} ${n.title || ""}`,
        `${n.level} 아래에 아무 항목도 없습니다.`, n, f.path);
    }
  }

  /* ---- 7. 용어 불일치 (경고) ----
     「…」 안은 남의 규정 이름이므로 우리 용어로 세지 아니한다.
     (제113조가 「수치표고모형의 구축 및 관리 등에 관한 규정」 을 가리킨다고 해서
      '수치표고모형' 을 쓴 것은 아니다) */
  const noName = (s) => String(s || "").replace(/[「『][^」』\r\n]{0,80}[」』]/g, " ");
  const bodyTerm = noName(bodyAll);
  for (const set of TERM_SETS) {
    const used = set.terms.filter((t) => bodyTerm.includes(t));
    if (used.length > 1) {
      const where = [];
      for (const f of flat) {
        const t = noName(`${f.node.title || ""} ${f.node.body || ""}`);
        const hit = used.filter((u) => t.includes(u));
        if (hit.length) where.push(`${M.displayLabel(f.node)}(${hit.join("·")})`);
        if (where.length >= 6) break;
      }
      add("경고", "term", `용어가 섞여 쓰입니다 — ${set.name}`,
        `${used.join(" / ")} 가 함께 나옵니다. 예: ${where.join(", ")}${where.length >= 6 ? " …" : ""}`, null, "");
    }
  }

  /* ---- 8. 기준 대비 사라진 조문 (정보) ---- */
  if (baseTree) {
    const cur = new Set(flat.map((f) => f.node.id));
    const lost = [];
    M.walk(baseTree, (n) => { if (n.level === "조" && !cur.has(n.id)) lost.push(M.shortLabel(n)); });
    if (lost.length) {
      add("정보", "removed", `현행에서 사라진 조문 ${lost.length}건`,
        `${lost.slice(0, 12).join(", ")}${lost.length > 12 ? " …" : ""} — 삭제·통합 사유를 변경 사유에 남기면 비교표에 반영됩니다.`, null, "");
    }
  }

  /* ---- 9. 장문 조문 (정보) ---- */
  for (const f of flat) {
    const n = f.node;
    if (n.level !== "조" || n.annexRef) continue;
    const len = (n.body || "").length;
    if (len > LONG) {
      add("정보", "long", `조문이 깁니다 — ${M.displayLabel(n)} (${len.toLocaleString()}자)`,
        `분할을 검토해 보세요. 권장 ${LONG.toLocaleString()}자 이하.`, n, f.path);
    }
  }

  /* ---- 10. 같은 부모 안 제목 중복 (정보) ---- */
  const byParent = new Map();
  for (const f of flat) {
    const key = (f.parent ? f.parent.id : "@root") + "|" + norm(f.node.title);
    if (!norm(f.node.title)) continue;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(f);
  }
  for (const [, arr] of byParent) {
    if (arr.length > 1) {
      add("정보", "dup-title", `제목이 같습니다 — “${arr[0].node.title}” ${arr.length}건`,
        arr.map((x) => M.displayLabel(x.node)).join(", "), arr[0].node, arr[0].path);
    }
  }

  items.sort((a, b) => LEVELS_OF[a.level] - LEVELS_OF[b.level]);
  return items;                       // 합치는 일은 부르는 쪽(validate)이 한다
}


/* ============================================================
   규정 사이 검증 — 규정(3종)이 한 트리에 모여야만 돌 수 있는 것들
   ------------------------------------------------------------
   편집기가 세 벌이던 동안에는 scripts/checkcites.py 를 밖에서 따로 돌려야
   했고 그 결과는 화면으로 돌아오지 않았다. 합치기 2단계에서 안으로 들인다.
   ============================================================ */
function crossChecks(tree) {
  const items = [];
  const add = (level, code, title, detail, node, path) =>
    items.push({ level, code, title, detail, nodeId: node ? node.id : null, path: path || "" });

  /* ---- 끊어진 인용 (규정 사이) — 오류 ---- */
  for (const b of checkCrossRefs(tree)) {
    add("오류", "cross-broken",
      `규정 밖 인용이 끊어졌습니다 — ${b.short} 제${b.no}조`,
      `${M.shortLabel(b.node)} 이(가) “${b.cite}” 을(를) 부르는데 「${b.regName}」 에 그 조가 없습니다. `
      + `옮겨졌거나 지워진 조입니다.`,
      b.node, `${M.shortLabel(b.fromReg)} › ${M.shortLabel(b.node)}`);
  }

  /* ---- 용어 불일치 (규정 사이) — 경고 ----
     무엇으로 맞출지와 그 근거를 함께 적는다. 현행 고시 체계를 앞세우고
     국가공간정보 표준용어집(KS X ISO)의 말을 병기한다 — 둘이 다른 자리가
     있어(라이다/레이저측량, 모델/모형) 어느 쪽을 왜 골랐는지 보여야 한다. */
  for (const t of checkTerms(tree)) {
    const other = t.used.filter((u) => u.term !== t.canon);
    if (!other.length) continue;
    const parts = [
      other.map((u) => `“${u.term}” ${u.count}곳 (${u.regs.join(" · ")})`).join(", "),
      `→ 「${t.canon}」 으로 맞춥니다.`,
      t.basis ? `근거: ${t.basis}.` : "",
      t.std ? `국가공간정보 표준용어집은 '${t.std.ko}' (${t.std.no}).` : "표준용어집에는 항목이 없습니다.",
      t.note || "",
    ].filter(Boolean);
    add("경고", "cross-term", `규정마다 다른 말로 부릅니다 — ${t.canon}`,
      parts.join(" "), null, "규정 사이");
  }

  /* ---- 별표 허용기준이 다루지 않는 품질요소 (정보) ----
     KS X 19157-1:2025 의 품질모델로 견준다. 말로 가리는 어림이므로
     '빠짐' 이 아니라 '눈에 띄지 않음' 으로 적는다 — 사람이 보아야 한다. */
  for (const reg of (tree || []).filter(M.isRegNode)) {
    const short = M.shortLabel(reg);
    const tally = Object.fromEntries(QUALITY_ELEMENTS.map((e) => [e.id, 0]));
    let n = 0;
    M.walk(reg.children || [], (node) => {
      if (!node.annexRef) return;
      const body = `${node.title || ""} ${node.body || ""} ${(node.citesAnnex || []).join(" ")}`;
      if (!/정확도|공차|허용|오차|품질/.test(body)) return;
      n += 1;
      for (const id of elementsOf(body)) tally[id] += 1;
    });
    if (!n) continue;
    const thin = QUALITY_ELEMENTS.filter((e) => tally[e.id] === 0);
    if (!thin.length) continue;
    add("정보", "q19157",
      `${short} — 별표 기준이 다루지 않는 품질요소 ${thin.length}가지`,
      `기준을 담은 별표 ${n}건 가운데 `
      + thin.map((e) => `${e.name}(${e.hint})`).join(", ")
      + ` 을(를) 다루는 것이 눈에 띄지 않습니다. KS X 19157-1:2025 품질모델 기준이며, `
      + `말로 가린 어림이므로 실제로 없는지는 살펴보아야 합니다.`,
      null, `${short} › 별표`);
  }

  /* ---- 별표 번호 충돌 — 경고 ---- */
  for (const c of checkAnnexClash(tree)) {
    add("경고", "cross-annex",
      `이관한 조문이 부르는 ${c.cite} 이(가) 이 규정에 없습니다`,
      `${M.shortLabel(c.node)} 은(는) 「${c.from}」 에서 이관되었고 ${c.cite} 을(를) 부릅니다. `
      + `「${M.shortLabel(c.reg)}」 에는 그 번호가 없습니다 — 별표를 함께 옮기거나 번호를 고치십시오.`,
      c.node, `${M.shortLabel(c.reg)} › ${M.shortLabel(c.node)}`);
  }

  return items;
}
