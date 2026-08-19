/* ============================================================
   core/quality.js — 별표 정확도 기준을 19157 품질요소에 견주기
   ------------------------------------------------------------
   KS X 19157-1:2025 (= ISO 19157-1:2023 일치 부합화) 의 품질모델로
   작업규정 별표의 허용기준이 어느 품질요소를 다루고 어디가 비어 있는지 본다.
   (App/공간정보표준 · KS_X_19157-1_2025_…해설서_최신화_검토판)

   ■ 2013년판에서 달라진 것 — 해설서 부록 A

     시간 정확도            → 시간 품질   (정확도 + 일관성 + 타당성)
     주제 정확도            → 주제 품질   (분류 + 정량·비정량 속성)
     사용적합성(Usability)  → 품질모델에서 삭제, 적합품질수준으로 옮김
     메타품질               → 품질요소 체계에 들어옴 (신뢰도·대표성·동질성)

   ■ 무엇을 견주는가

     별표의 표 안 글에서 품질요소를 가리키는 말을 찾아, 그 별표가 어느
     요소를 다루는지 가린다. 말로 가리는 것이므로 어림이다 — 없다고 나온
     것이 정말 없는지는 사람이 보아야 한다. 그래서 '빠짐' 이 아니라
     '눈에 띄지 않음' 으로 적는다.

   DOM 을 모른다. 별표 표 글을 읽어 오는 일은 부르는 쪽이 한다.
   ============================================================ */

/** KS X 19157-1:2025 품질요소 — 해설서 8.1 · 부록 A */
export const QUALITY_ELEMENTS = [
  { id: "완전성", name: "완전성", sub: "누락 · 초과",
    hint: "있어야 할 것이 빠졌는가, 없어야 할 것이 들었는가",
    re: /누락|과잉|초과|미취득|결측|빠(?:짐|진)/ },
  { id: "논리일관성", name: "논리 일관성", sub: "개념 · 값영역 · 형식 · 위상",
    hint: "폐합·접합·중복·위상이 어긋나지 않는가",
    re: /위상|폐합|접합|중복|일관성|모순|교차|閉合/ },
  { id: "위치정확도", name: "위치 정확도", sub: "절대 · 상대 · 격자",
    hint: "자리가 얼마나 맞는가 (RMSE · CE95 · 허용오차)",
    re: /표준편차|RMSE|CE95|LE95|허용\s?오차|공차|평면|표고|수평|수직|잔차|폐합차|정확도/ },
  { id: "주제품질", name: "주제 품질", sub: "분류 · 정량 · 비정량 속성",
    hint: "지형지물을 옳게 가르고 속성을 옳게 적었는가",
    re: /분류|속성|코드|지형지물|판독|주기|注記/ },
  { id: "시간품질", name: "시간 품질", sub: "시간 정확도 · 일관성 · 타당성",
    hint: "언제 것인가, 시기가 서로 맞는가",
    re: /촬영\s?시기|촬영일|최신성|갱신|취득\s?시기|기준\s?시점/ },
  { id: "메타품질", name: "메타품질", sub: "신뢰도 · 대표성 · 동질성",
    hint: "이 결과를 얼마나 믿을 수 있는가 (표본·모집단·신뢰수준)",
    re: /신뢰도|대표성|동질성|표본|모집단|신뢰수준|층화/ },
];

/** 2013년판 표현이 남아 있으면 짚는다 — 해설서 9. 전환 체크리스트 */
export const LEGACY_TERMS = [
  { old: /시간\s?정확도/g, to: "시간 품질",
    why: "2023/2025판에서 시간 정확도는 '시간 품질' 로 넓어졌습니다 (정확도·일관성·타당성)." },
  { old: /주제\s?정확도/g, to: "주제 품질",
    why: "2023/2025판에서 주제 정확도는 '주제 품질' 로 넓어졌습니다 (분류·정량·비정량 속성)." },
  { old: /사용\s?적합성|유용성/g, to: "적합품질수준",
    why: "사용적합성은 품질모델에서 삭제되었습니다 — 제품사양의 적합품질수준과 사용자 요구로 적습니다." },
];

/**
 * 별표 하나가 다루는 품질요소를 가린다.
 * @param {string} text 별표 제목 + 표 안 글
 */
export function elementsOf(text) {
  const s = String(text || "");
  return QUALITY_ELEMENTS.filter((e) => e.re.test(s)).map((e) => e.id);
}

/**
 * 별표 묶음 전체를 견준다.
 *
 * @param {Array<{key,title,text}>} annexes 별표 (표 안 글까지 담아 넘긴다)
 * @returns {{rows, coverage, legacy, total}}
 */
export function checkAnnexes(annexes) {
  const rows = [];
  const coverage = Object.fromEntries(QUALITY_ELEMENTS.map((e) => [e.id, 0]));
  for (const a of annexes || []) {
    const body = `${a.title || ""} ${a.text || ""}`;
    // 허용기준을 담은 별표만 견준다 — 서식·조서는 대상이 아니다
    if (!/정확도|공차|허용|오차|품질|기준/.test(body)) continue;
    const has = elementsOf(body);
    for (const id of has) coverage[id] += 1;
    rows.push({ key: a.key, title: a.title || "", has,
      miss: QUALITY_ELEMENTS.map((e) => e.id).filter((id) => !has.includes(id)) });
  }
  // 옛 용어
  const all = (annexes || []).map((a) => `${a.title || ""} ${a.text || ""}`).join(" ");
  const legacy = [];
  for (const t of LEGACY_TERMS) {
    t.old.lastIndex = 0;
    const n = (all.match(t.old) || []).length;
    if (n) legacy.push({ term: String(t.old).replace(/[/\\g]/g, ""), n, to: t.to, why: t.why });
  }
  return { rows, coverage, legacy, total: rows.length };
}
