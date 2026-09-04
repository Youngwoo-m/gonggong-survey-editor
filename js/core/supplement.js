/* ============================================================
   core/supplement.js — 부칙 짓기
   ------------------------------------------------------------
   법제처 법령안편집기의 '부칙작성' 이 하는 일이다.
   (App/관련규정/법제처_법령안편집기 · 교재 III장 '부칙의 작성')

     ▷ 시행일   기본시행일·단서시행일을 고르면 부칙의 '시행일' 을 짓는다
     ▷ 타법개정 다른 법령에 든 문구를 찾아 법령마다 개정문을 짓고,
                이를 모아 '다른 법령의 개정' 을 짓는다

   ■ 다른 규정의 개정을 우리는 어떻게 짓는가

     이 편집기는 세 규정을 한 트리에 담고 있다. 그래서 작업규정의 조를
     옮기면 성과심사·무인비행장치 규정에서 그 조를 부르던 자리가 어긋나는
     것을 곧바로 알 수 있다 — 규정 사이 인용은 이미 찾아 두고 있다
     (core/xrefs.js). 그 자리를 부칙 문안으로 옮겨 적기만 하면 된다.

       부칙
       제1조(시행일) 이 규정은 공포한 날부터 시행한다.
       제2조(다른 규정의 개정) ① 「측량성과 심사수탁기관의 …」 일부를
         다음과 같이 개정한다.
         제14조 중 “「공공측량 작업규정」제76조”를 “「공공측량 작업규정」
         제80조”로 한다.

     바깥 법령(우리가 담고 있지 않은 것)은 알 길이 없으므로 짓지 않는다.
     대신 그 규정이 우리를 부르고 있다는 것은 library.json 의 citedIn 에
     적혀 있으므로, 손으로 살펴야 할 것으로 따로 알린다.

   DOM 을 모른다.
   ============================================================ */
import * as M from "./model.js?v=20260904j";
import { eul, ro, iga } from "./amend.js?v=20260904j";

/* ---------- 시행일 ---------- */

export const EFFECT_KINDS = [
  { id: "promulgate", label: "공포한 날부터 시행" },
  { id: "after", label: "공포 후 일정 기간이 지난 날부터 시행" },
  { id: "date", label: "정한 날부터 시행" },
];

/** 2026-03-01 → 2026년 3월 1일 */
function ymd(s) {
  const m = String(s || "").match(/(\d{4})\D*(\d{1,2})\D*(\d{1,2})/);
  return m ? `${m[1]}년 ${+m[2]}월 ${+m[3]}일` : "";
}

/**
 * 시행일 조문 한 줄.
 * @param {object} o { kind, months, date, proviso:{date, targets} }
 */
export function effectiveClause(o = {}) {
  const kind = o.kind || "promulgate";
  let main;
  if (kind === "after") {
    const n = +o.months || 6;
    main = `이 규정은 공포 후 ${n}개월이 경과한 날부터 시행한다.`;
  } else if (kind === "date") {
    main = `이 규정은 ${ymd(o.date) || "○○○○년 ○월 ○일"}부터 시행한다.`;
  } else {
    main = "이 규정은 공포한 날부터 시행한다.";
  }
  // 단서 — 일부 조문만 날을 달리할 때
  const pv = o.proviso;
  if (pv && (pv.targets || "").trim()) {
    const when = pv.kind === "after"
      ? `공포 후 ${+pv.months || 6}개월이 경과한 날`
      : (ymd(pv.date) || "○○○○년 ○월 ○일");
    main += ` 다만, ${pv.targets.trim()}의 개정규정은 ${when}부터 시행한다.`;
  }
  return main;
}

/* ---------- 다른 규정의 개정 ---------- */

/** 이 규정을 부르는 인용 — 「이름」제N조(의M) */
function citeRe(regName) {
  const esc = String(regName).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`[「『]\\s*${esc}\\s*[」』]\\s*제\\s*(\\d+)\\s*조(?:의\\s*(\\d+))?`, "g");
}

/**
 * 개정으로 번호가 바뀌거나 없어진 조를 표로 만든다.
 * @param {Array} rows core/diff.js 의 비교 결과
 * @returns {Map<string,{to:string|null}>} 옛 번호 → 새 번호 (null 이면 삭제)
 */
export function renumberMap(rows) {
  const map = new Map();
  for (const r of rows || []) {
    if (r.kind === "신설") continue;
    const b = r.before, a = r.after;
    if (!b) continue;
    if (!a) { map.set(b.label, { to: null }); continue; }
    if (b.label !== a.label) map.set(b.label, { to: a.label });
  }
  return map;
}

/**
 * 다른 규정에서 이 규정을 부르던 자리가 어긋났는지 보고, 개정문을 짓는다.
 *
 * @param {Array}  tree     프로젝트 트리 (최상위가 규정)
 * @param {string} targetId 지금 개정하는 규정의 대상 id
 * @param {string} regName  그 규정의 이름
 * @param {Map}    moved    renumberMap 결과
 * @returns {Array<{reg, name, items:Array<{node,label,from,to,gone}>}>}
 */
export function otherRegChanges(tree, targetId, regName, moved) {
  const out = [];
  if (!moved || !moved.size) return out;
  for (const reg of (tree || []).filter(M.isRegNode)) {
    if (reg.targetId === targetId) continue;          // 제 자신은 아니다
    const items = [];
    M.walk(reg.children || [], (n) => {
      if (n.level !== "조" || !n.body) return;
      const re = citeRe(regName);
      re.lastIndex = 0;
      let m;
      const seen = new Set();
      while ((m = re.exec(n.body))) {
        const label = `제${+m[1]}조${m[2] ? `의${+m[2]}` : ""}`;
        const hit = moved.get(label);
        if (!hit || seen.has(label)) continue;
        seen.add(label);
        // 원문을 글자 그대로 딴다 — 개정문은 본문에 있는 그대로를 따야 한다
        items.push({ node: n, label: M.shortLabel(n),
          from: m[0].trim(), to: hit.to, gone: hit.to === null });
      }
    });
    if (items.length) out.push({ reg, name: reg.title, items });
  }
  return out;
}

/**
 * 조 번호가 아니라 '편별 구분' 처럼 짜임새를 옮겨 적은 자리를 찾는다.
 *
 * 세 규정은 서로를 조 번호로 부르지 않는다 — 이름으로만 부른다. 그래서
 * 번호 갈이만 보면 고칠 것이 없어 보인다. 그러나 성과심사 규정 제14조는
 *
 *   「공공측량 작업규정」의 편별 구분에 따라 다음 각 호와 같이 나눈다.
 *   1. 기준점 측량 : 공공삼각점 측량, 공공수준점 측량 …
 *
 * 처럼 작업규정의 편 이름을 그대로 옮겨 적고 있다. 작업규정이 5편에서
 * 7편으로 바뀌면 이 줄은 어긋난다. 번호로는 잡히지 않으므로 따로 본다.
 *
 * @param {Array} oldTops 개정 전 편·장 제목
 * @param {Array} newTops 개정 후 편·장 제목
 */
export function structureEchoes(tree, targetId, regName, oldTops, newTops) {
  const gone = oldTops.filter((t) => t && !newTops.includes(t));
  if (!gone.length) return [];
  const out = [];
  const nameRe = citeRe0(regName);
  for (const reg of (tree || []).filter(M.isRegNode)) {
    if (reg.targetId === targetId) continue;
    M.walk(reg.children || [], (n) => {
      if (n.level !== "조" || !n.body) return;
      nameRe.lastIndex = 0;
      if (!nameRe.test(n.body)) return;
      const echoed = gone.filter((t) => n.body.includes(t));
      if (echoed.length) out.push({ reg, label: M.shortLabel(n), echoed });
    });
  }
  return out;
}

/** 「이름」 만 부르는 자리 (조 번호 없이) */
function citeRe0(regName) {
  const esc = String(regName).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`[「『]\\s*${esc}\\s*[」』]`, "g");
}

/** 트리에서 편·장 제목을 뽑는다 */
export function topTitles(nodes) {
  const out = [];
  for (const n of nodes || []) {
    if (n.level === "편" || n.level === "장") out.push(n.title || "");
    for (const c of n.children || []) if (c.level === "장") out.push(c.title || "");
  }
  return out.filter(Boolean);
}

/* ---------- 부칙 전체 ---------- */

/**
 * 부칙을 짓는다.
 *
 * @param {object} o {
 *   regName, tree, targetId, rows,
 *   effective: { kind, months, date, proviso },
 *   withOthers: boolean,      다른 규정의 개정을 넣을 것인가
 *   extern: Array<string>     바깥 법령 이름들 (손으로 살필 것)
 * }
 * @returns {{text, articles:Array<{no, title, lines}>, warnings:Array<string>}}
 */
export function buildSupplement(o = {}) {
  const articles = [];
  const warnings = [];

  articles.push({ no: 1, title: "시행일", lines: [effectiveClause(o.effective)] });

  if (o.withOthers) {
    const moved = renumberMap(o.rows);
    const groups = otherRegChanges(o.tree, o.targetId, o.regName, moved);
    if (groups.length) {
      const lines = [];
      groups.forEach((g, gi) => {
        const num = "①②③④⑤⑥⑦⑧⑨⑩"[gi] || `(${gi + 1})`;
        lines.push(`${num} 「${g.name}」 일부를 다음과 같이 개정한다.`);
        for (const it of g.items) {
          if (it.gone) {
            warnings.push(`「${g.name}」 ${it.label}${iga(it.label)} 부르는 ${it.from}${eul(it.from)} `
              + `이번 개정으로 없어집니다 — 무엇으로 갈음할지 손으로 정해야 합니다.`);
            lines.push(`  ${it.label} 중 “${it.from}”${eul(it.from)} `
              + `“○○○”${ro("○○○")} 한다.  ※ 삭제된 조문 — 갈음할 조를 적으십시오`);
            continue;
          }
          const to = `「${o.regName}」${it.to}`;
          lines.push(`  ${it.label} 중 “${it.from}”${eul(it.from)} “${to}”${ro(to)} 한다.`);
        }
      });
      articles.push({ no: articles.length + 1, title: "다른 규정의 개정", lines });
    }
    // 짜임새를 옮겨 적은 자리 — 번호로는 잡히지 않는다
    for (const e of structureEchoes(o.tree, o.targetId, o.regName,
                                    o.oldTops || [], o.newTops || [])) {
      warnings.push(`「${e.reg.title}」 ${e.label}${iga(e.label)} 「${o.regName}」 의 `
        + `짜임새를 옮겨 적고 있습니다 — 이번 개정으로 없어지는 `
        + `${e.echoed.map((x) => `‘${x}’`).join(" · ")}${eul(e.echoed[e.echoed.length - 1])} `
        + `담고 있으니 손으로 살피십시오.`);
    }
    for (const name of (o.extern || [])) {
      warnings.push(`「${name}」${iga(name)} 이 규정을 인용하고 있습니다 — `
        + `이 편집기에 담고 있지 않아 개정문을 짓지 못합니다. 손으로 살피십시오.`);
    }
  }

  const text = ["부칙", ""].concat(articles.flatMap((a) => [
    `제${a.no}조(${a.title}) ${a.lines[0]}`,
    ...a.lines.slice(1),
    "",
  ])).join("\n").trimEnd();

  return { text, articles, warnings };
}
