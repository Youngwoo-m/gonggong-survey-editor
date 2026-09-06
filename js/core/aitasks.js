/* ============================================================
   core/aitasks.js — AI 에게 시킬 일 (지시문 + 답변 해석)
   ------------------------------------------------------------
   화면과 떨어져 있다. 여기서 만든 '제안'은 그대로 트리에 적용되지 않고,
   사람이 화면에서 하나씩 골라 [적용] 을 눌러야 반영된다.
   ============================================================ */
import * as M from "./model.js?v=20260906b";

const BLANK = "\n\n";      // 빈 줄 하나

/* 어느 규정을 고치는 일인가 — 편집기 프로파일이 켜질 때 정해 준다 */
let REG = { name: "공공측량 작업규정", work: "전부개정" };
export function setRegulation({ name, work } = {}) {
  if (name) REG.name = name;
  if (work) REG.work = work;
  SYSTEM = buildSystem();
}
const regName = () => REG.name;

function buildSystem() {
  return `당신은 대한민국 법령 입안 실무에 밝은 측량 분야 전문가입니다.
「${REG.name}」(국토지리정보원 고시) ${REG.work} 작업을 돕습니다.

지킬 것
- 법제처 「법령 입안-심사 기준」의 문장 규칙을 따릅니다.
  - 한 조는 하나의 사항만 담습니다.
  - "~하여야 한다"(의무) / "~할 수 있다"(재량) / "~한다"(사실 규정)를 구분합니다.
  - 인용은 「법령명」 제N조 제N항 제N호 형식으로 씁니다.
- 조문 본문은 위와 같이 '~한다' 체로 씁니다.
- 그러나 개정 사유, 검토 의견, 지적 사항처럼 보고서에 실리는 글은 개조식으로
  쓰고, 문장 끝을 '~음 / ~임 / ~함 / ~필요함' 으로 맺습니다.
  (보기: "용어가 갈려 혼선이 있음", "정의 규정을 신설할 필요함")
- 가운데점(가운뎃점)과 화살표 기호는 쓰지 않습니다. 낱말을 늘어놓을 때에는
  쉼표를, 바뀌는 관계를 적을 때에는 "A 를 B 로" 처럼 풀어서 씁니다.
- 측량 용어는 현행 규정과 상위 법령(공간정보의 구축 및 관리 등에 관한 법률)의 용례를 따릅니다.
- 근거 없이 새 의무를 만들지 않습니다. 확실하지 않으면 그렇다고 밝힙니다.
- 답은 요청받은 JSON 형식으로만 내고, 다른 설명은 붙이지 않습니다.`;
}

let SYSTEM = buildSystem();

/** 사람이 덧붙인 지시를 지시문 끝에 단다 */
export function withExtra(built, extra) {
  const t = String(extra || "").trim();
  if (!t) return built;
  return {
    system: built.system,
    user: `${built.user}

[작업자가 덧붙인 지시 — 위 규칙과 어긋나지 않는 선에서 반드시 따르십시오]
${t}`,
  };
}

/** 트리를 지시문에 넣기 좋게 줄인다 */
export function outline(nodes, { depth = 3, body = 0 } = {}) {
  const out = [];
  (function rec(list, d, trail) {
    for (const n of list) {
      if (n.isAnnex || n.annexRef) continue;              // 별표는 따로 다룬다
      const label = M.shortLabel(n);
      const line = `${"  ".repeat(d)}${label} ${n.title || ""}`.trimEnd();
      out.push(body && n.body ? `${line}\n${"  ".repeat(d + 1)}${n.body.slice(0, body)}` : line);
      if (d + 1 < depth) rec(n.children || [], d + 1, trail);
    }
  })(nodes, 0, []);
  return out.join("\n");
}

/* ============================================================
   1) 조문 다듬기
   ============================================================ */
export const polish = {
  key: "polish",
  name: "조문 다듬기",
  hint: "고른 조문의 제목·본문을 법령 문장 규칙에 맞게 다듬습니다.",
  needsNode: true,
  build(ctx) {
    const n = ctx.node;
    return {
      system: SYSTEM,
      user: `다음 조문을 다듬어 주십시오.

[현재 조문]
${M.shortLabel(n)} ${n.title || "(제목 없음)"}
${n.body || "(본문 없음)"}

[같은 장의 다른 조문 — 문체를 맞추기 위한 참고]
${ctx.siblings || "(없음)"}

아래 JSON 으로만 답하십시오.
{
  "title": "다듬은 제목",
  "body": "다듬은 본문 (항은 ①②③, 호는 1. 2. 3. 으로 표기)",
  "changes": ["무엇을 왜 고쳤는지 한 줄씩", "..."],
  "reason": "개정 사유 한 줄 (개조식, ~음/~임/~함 으로 맺음)",
  "risks": ["고칠 때 함께 살펴야 할 점", "..."]
}`,
    };
  },
  parse(j) {
    return {
      kind: "patch",
      patch: { title: j.title || "", body: j.body || "", reason: j.reason || "" },
      notes: [...(j.changes || []).map((x) => ["고친 곳", x]),
              ...(j.risks || []).map((x) => ["살필 점", x])],
    };
  },
};

/* ============================================================
   2) 구조 개편 제안
   ============================================================ */
export const restructure = {
  key: "restructure",
  name: "구조 개편 제안",
  hint: "고른 편·장의 하위 구조를 참조 규정과 대조해 재배치를 제안합니다.",
  needsNode: true,
  build(ctx) {
    return {
      system: SYSTEM,
      user: `아래는 개편 중인 「${regName()}」의 한 부분입니다.

[개정안 — ${M.shortLabel(ctx.node)} ${ctx.node.title || ""}]
${ctx.subtree}

${ctx.refName ? `[참고 — ${ctx.refName} 의 같은 분야 편제]\n${ctx.refOutline}\n` : ""}
이 부분의 편제를 더 낫게 바꿀 방법을 제안해 주십시오.
지금 있는 조문만 옮기거나 묶고, 새 조문은 꼭 필요한 것만 제안하십시오.

아래 JSON 으로만 답하십시오.
{
  "summary": "제안의 요지 두세 문장",
  "moves": [
    {"label": "제12조", "to": "제3장 성과관리 아래", "why": "왜 옮기는지"}
  ],
  "merges": [
    {"labels": ["제12조", "제13조"], "into": "합친 뒤 제목", "why": "왜 합치는지"}
  ],
  "news": [
    {"where": "제2장 끝", "title": "새 조문 제목", "why": "왜 필요한지"}
  ],
  "keep": ["건드리지 않는 편이 나은 조문과 이유", "..."]
}`,
    };
  },
  parse(j) {
    const notes = [];
    for (const m of j.moves || []) notes.push(["이동", `${m.label} → ${m.to} · ${m.why || ""}`]);
    for (const m of j.merges || []) notes.push(["통합", `${(m.labels || []).join(" + ")} → ${m.into || ""} · ${m.why || ""}`]);
    for (const m of j.news || []) notes.push(["신설", `${m.where || ""} · ${m.title || ""} · ${m.why || ""}`]);
    for (const k of j.keep || []) notes.push(["유지", k]);
    return { kind: "advice", summary: j.summary || "", notes };
  },
};

/* ============================================================
   3) 중복·상충 검토
   ============================================================ */
export const conflicts = {
  key: "conflicts",
  name: "중복·상충 검토",
  hint: "규정 전체에서 겹치거나 어긋나는 조문을 찾습니다.",
  needsNode: false,
  build(ctx) {
    return {
      system: SYSTEM,
      user: `아래는 개편 중인 「${regName()}」의 전체 편제와 조문 제목입니다.

${ctx.outline}

내용이 겹치거나 서로 어긋나 보이는 조문 짝을 찾아 주십시오.
제목만으로는 알 수 없는 것은 넣지 마십시오. 없으면 빈 배열로 답하십시오.

아래 JSON 으로만 답하십시오.
{
  "items": [
    {"level": "중복" 또는 "상충" 또는 "확인필요",
     "labels": ["제12조", "제45조"],
     "detail": "무엇이 겹치거나 어긋나는지",
     "suggest": "어떻게 정리하면 좋은지"}
  ]
}`,
    };
  },
  parse(j) {
    return {
      kind: "advice",
      summary: (j.items || []).length ? `${j.items.length}건을 짚었습니다.` : "겹치거나 어긋나는 곳을 찾지 못했습니다.",
      notes: (j.items || []).map((x) => [x.level || "확인필요",
        `${(x.labels || []).join(" ↔ ")} — ${x.detail || ""}${x.suggest ? ` · 정리안: ${x.suggest}` : ""}`]),
      jumps: (j.items || []).map((x) => (x.labels || [])[0]).filter(Boolean),
    };
  },
};

/* ============================================================
   4) 개정 사유 초안
   ============================================================ */
export const reasons = {
  key: "reasons",
  name: "개정 사유 초안",
  hint: "바뀐 조문들의 개정 사유 문장을 한꺼번에 만듭니다.",
  needsNode: false,
  build(ctx) {
    return {
      system: SYSTEM,
      user: `아래는 「${regName()}」 개정안에서 이미 바뀐 조문들입니다.
각 조문의 개정 사유를 개조식 한 줄로 만들어 주십시오.

  - 문장 끝은 '~음 / ~임 / ~함 / ~필요함' 으로 맺습니다.
  - 가운데점과 화살표 기호는 쓰지 않습니다.
  - 무엇이 문제였고 무엇을 고쳤는지가 한 줄에 드러나게 씁니다.

${ctx.changed}

아래 JSON 으로만 답하십시오.
{
  "items": [{"id": "노드 id 그대로", "reason": "개정 사유 한 줄 (개조식)"}]
}`,
    };
  },
  parse(j) {
    return {
      kind: "reasons",
      items: (j.items || []).filter((x) => x.id && x.reason),
      notes: (j.items || []).map((x) => ["사유", `${x.id} — ${x.reason}`]),
    };
  },
};

/* ============================================================
   5) 참조 규정과 비교하기
   ============================================================ */
export const compareRef = {
  key: "compareRef",
  name: "참조 규정과 비교하기",
  hint: "② 창에 띄운 규정과 비교하여 빠진 것·다른 것을 짚습니다.",
  needsNode: false,
  needsRef: true,
  build(ctx) {
    return {
      system: SYSTEM,
      user: `[개정안 — ${regName()}]
${ctx.outline}

[참조 규정 — ${ctx.refName}]
${ctx.refOutline}

참조 규정에는 있는데 개정안에 없는 것, 다루는 깊이가 크게 다른 것을 짚어 주십시오.
우리 규정 체계에 맞지 않는 것은 무리해서 넣자고 하지 마십시오.

아래 JSON 으로만 답하십시오.
{
  "summary": "견준 결과 요지 두세 문장",
  "missing": [{"what": "빠진 사항", "refAt": "참조 규정에서의 위치", "why": "왜 필요한지", "where": "개정안 어디에 넣으면 좋은지"}],
  "different": [{"what": "다르게 다루는 사항", "ours": "우리 규정", "theirs": "참조 규정", "comment": "의견"}],
  "notApplicable": ["가져오지 않는 편이 나은 것과 이유"]
}`,
    };
  },
  parse(j) {
    const notes = [];
    for (const m of j.missing || []) notes.push(["빠짐", `${m.what} (${m.refAt || ""}) · ${m.why || ""}${m.where ? ` → ${m.where}` : ""}`]);
    for (const m of j.different || []) notes.push(["다름", `${m.what} — 우리: ${m.ours || ""} / 참조: ${m.theirs || ""} · ${m.comment || ""}`]);
    for (const m of j.notApplicable || []) notes.push(["제외", m]);
    return { kind: "advice", summary: j.summary || "", notes };
  },
};

/* ============================================================
   6) 직접 묻기 — 사람이 쓴 질문을 그대로 보낸다
   ============================================================ */
export const freeAsk = {
  key: "free",
  name: "직접 묻기",
  hint: "묻고 싶은 것을 직접 쓰고, 함께 보낼 자료를 고릅니다.",
  free: true,
  build(ctx) {
    const parts = [];
    if (ctx.pickNode && ctx.nodeText) parts.push(`[고른 항목]
${ctx.nodeText}`);
    if (ctx.pickSubtree && ctx.subtree) parts.push(`[고른 항목의 하위 구조]
${ctx.subtree}`);
    if (ctx.pickOutline && ctx.outline) parts.push(`[개정안 전체 편제]
${ctx.outline}`);
    if (ctx.pickRef && ctx.refOutline) parts.push(`[참조 규정 — ${ctx.refName}]
${ctx.refOutline}`);

    const head = parts.length ? `${parts.join(BLANK)}${BLANK}---${BLANK}` : "";
    return {
      system: `${SYSTEM}

이번에는 JSON 이 아니라 사람이 읽을 글로 답하십시오.
- 짧은 문단과 목록으로 정리하고, 표는 쓰지 마십시오.
- 규정 조문을 제안할 때는 조 번호와 제목을 분명히 적으십시오.
- 모르는 것은 모른다고 하십시오.`,
      user: `${head}[물음]\n${ctx.question}`,
    };
  },
  parse(text) {
    return { kind: "text", text: String(text || "").trim() };
  },
};

export const TASKS = [polish, restructure, compareRef, conflicts, reasons, freeAsk];
export const SYSTEM_PROMPT = SYSTEM;
