/* ============================================================
   scripts/checklinks.mjs — 연계 조문 링크를 전체 규정에서 훑는다

   본문의 인용을 세 가지로 나누어 잇는다.
     「규정 이름」        → 그 규정
     법·영·규칙 제○조     → 그 법령
     제○조               → 같은 규정의 그 조

   여기서는 89종 전부에 대해 링크가 몇 개 걸렸는지, 잘못 걸린 것
   (다른 법령의 조를 제 규정의 조로 이은 것)이 없는지 센다.

   링크가 걸리지 아니한 '제○조' 는 그 까닭을 갈래로 나누어 센다.
   앞의 법령 이름이 미치는 자리라서 일부러 걸지 않은 것과, 걸렸어야
   하는데 빠진 것을 가리기 위함이다.

   실행:  node scripts/checklinks.mjs           갈래별 건수
          node scripts/checklinks.mjs -v        갈래마다 보기까지
          node scripts/checklinks.mjs 누락      그 갈래만 모두 뽑기
   ============================================================ */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { linkCitations, linkLawRefs, linkSelfRefs } from "../js/core/objects.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(path.dirname(HERE), "data");
const lib = JSON.parse(fs.readFileSync(path.join(DATA, "library.json"), "utf-8"));

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// 규정 이름 → id (앱의 resolveCite 와 같은 구실)
const byName = new Map();
for (const r of lib.regulations) byName.set(r.name.replace(/\s+/g, ""), r.id);
const resolveCite = (name) => byName.get(String(name).replace(/\s+/g, "")) || null;
// 앱의 buildLawAlias 와 같은 짜임 — 약칭이 가리키는 법령을 갈라 준다
const LAW = "공간정보의 구축 및 관리 등에 관한 법률";
const ALIAS = {
  "법": "reg02", "법률": "reg02", "같은 법": "reg02", "같은법": "reg02",
  "영": "reg03", "시행령": "reg03", "같은 법 시행령": "reg03", "같은법 시행령": "reg03",
  "규칙": "reg04", "시행규칙": "reg04", "같은 법 시행규칙": "reg04", "같은법 시행규칙": "reg04",
};
const NAME = { reg02: LAW, reg03: `${LAW} 시행령`, reg04: `${LAW} 시행규칙` };
for (const k of Object.keys(ALIAS)) {          // 띄어쓰기 없는 인용(같은법시행령)도 받는다
  const bare = k.replace(/\s+/g, "");
  if (!ALIAS[bare]) ALIAS[bare] = ALIAS[k];
}
const resolveLaw = (w) => (ALIAS[w] ? { id: ALIAS[w], name: NAME[ALIAS[w]] } : null);

const RE_JO = /(?<![가-힣A-Za-z])제\s*(\d+)\s*조/g;
let tot = { docs: 0, arts: 0, self: 0, law: 0, cite: 0, citejo: 0, wrong: 0, miss: 0 };
const wrongs = [];

/* ── 링크가 걸리지 아니한 '제○조' 의 갈래 ──────────────────────
   앞자리에 무엇이 있었는지로 나눈다. 링크는 지우지 않고 표로 바꾸어
   (⟦C⟧ 규정 이름 · ⟦L⟧ 법령 조문 · ⟦S⟧ 이 규정의 조) 앞뒤를 살핀다. */
const KINDS = {
  "규정딸림": "「규정 이름」 에 딸린 조 — 조 번호는 앞의 규정 링크가 안고 간다",
  "법령딸림": "앞의 법령 인용에 딸린 조 (법 제18조 및 제105조) — 걸지 않는다",
  "시행령령": "시행령·시행규칙 제○조 — 그 법령의 조인데 약칭 목록에 없어 링크가 안 걸린다",
  "법령이름": "낫표 없이 쓴 법령 이름 뒤 (도로법 제2조) — 그 법의 조이므로 걸지 않는다",
  "약칭실패": "법·영·규칙 제○조 인데 약칭을 풀지 못하였다",
  "별표딸림": "별표·별지·서식 번호 뒤 — 조가 아니다",
  "누락": "앞에 다른 법령이 없다 — 이 규정의 조로 걸렸어야 한다",
};
const miss = {};                      // 갈래 → [보기]
for (const k of Object.keys(KINDS)) miss[k] = [];

const CONN = "[\\s및과와,·’”\\)\\]]";              // 조와 조를 잇는 말·군더더기
// 법령 이름 뒤에 조가 줄줄이 이어지는 자리 — 「도로법」 제2조 및 제5조, 제7조
const CHAIN = `(?:${CONN}*제\\s*\\d+\\s*조(?:의\\s*\\d+)?(?:\\s*제\\s*\\d+\\s*[항호])*)*${CONN}*$`;
const AT = {
  "규정딸림": new RegExp(`(?:⟦C⟧|[」』])${CHAIN}`),
  "법령딸림": new RegExp(`⟦L⟧${CHAIN}`),
  "시행령령": new RegExp(`(?:시행령|시행규칙)${CHAIN}`),
  "약칭실패": new RegExp(`(?<![가-힣A-Za-z])(?:법률|법|영|규칙)${CHAIN}`),
  "법령이름": new RegExp(`[가-힣]{2,20}(?:법률|법|규칙|규정|기준|령)${CHAIN}`),
  "별표딸림": /(?:별표|별지|서식)\s*\d*\s*$/,
};

/** 앞자리 글을 보고 갈래를 매긴다 — 어느 것에도 걸리지 않으면 '누락' */
function kindOf(before) {
  for (const [k, re] of Object.entries(AT)) if (re.test(before)) return k;
  return "누락";
}

/** 이 자리는 다른 법령이 미치는 자리인가 (이 규정의 조로 이으면 안 되는가) */
const inOtherLaw = (before) =>
  AT["규정딸림"].test(before) || AT["법령딸림"].test(before)
  || AT["시행령령"].test(before) || AT["약칭실패"].test(before);

for (const r of lib.regulations) {
  if (!r.file) continue;
  let doc;
  try { doc = JSON.parse(fs.readFileSync(path.join(DATA, r.file), "utf-8")); }
  catch { continue; }
  tot.docs += 1;

  const arts = [];
  (function rec(ns) {
    for (const n of ns || []) {
      if (n.level === "조" && !n.annexRef) arts.push(n);
      rec(n.children);
    }
  })(doc.tree);
  const have = new Set(arts.map((a) => Number(a.no)));
  const hasJo = (n) => have.has(Number(n));

  for (const a of arts) {
    const body = String(a.body || "");
    if (!body) continue;
    tot.arts += 1;
    let h = linkCitations(esc(body), resolveCite);
    h = linkLawRefs(h, resolveLaw);
    h = linkSelfRefs(h, hasJo);

    tot.self += (h.match(/class="cite self"/g) || []).length;
    tot.law += (h.match(/class="cite law"/g) || []).length;
    tot.cite += (h.match(/class="cite"/g) || []).length;
    tot.citejo += (h.match(/class="cite" href="#" data-reg="[^"]*" data-jo="\d/g) || []).length;

    // 잘못 이은 것 — 「…」 이나 법령 이름이 미치는 자리의 조를 제 규정의 조로 이었는가
    // 바로 뒤뿐 아니라 이음말로 이어진 뒤쪽 조까지 본다 (「도로법」 제2조 및 제5조)
    const marked = h.replace(/<a class="cite( law)?"[^>]*>[^]*?<\/a>/g,
      (_m, k) => (k === " law" ? "⟦L⟧" : "⟦C⟧"));
    for (const m of marked.matchAll(/([^<]{0,60})<a class="cite self"[^>]*>(제\s*\d+\s*조)/g)) {
      const before = m[1];
      if (inOtherLaw(before)) {
        tot.wrong += 1;
        if (wrongs.length < 12) wrongs.push(`${r.id} 제${a.no}조 … ${before.slice(-24)}${m[2]}`);
      }
    }
    // 링크가 되지 아니한 '제○조' — 링크는 표로 바꾸어 앞자리를 살필 수 있게 한다
    const plain = h.replace(/<a class="cite( law| self)?"[^>]*>[^]*?<\/a>/g,
      (_m, k) => (k === " law" ? "⟦L⟧" : k === " self" ? "⟦S⟧" : "⟦C⟧"));
    for (const m of plain.matchAll(RE_JO)) {
      if (!hasJo(m[1])) continue;
      tot.miss += 1;
      const i = m.index;
      const kind = kindOf(plain.slice(Math.max(0, i - 60), i));
      miss[kind].push(`${r.id} 제${a.no}조 … ${plain.slice(Math.max(0, i - 30), i + 10)}`);
    }
  }
}

console.log(`규정 ${tot.docs}종 · 조문 ${tot.arts}개`);
console.log(`  링크 — 규정 이름 ${tot.cite}(그 가운데 조까지 짚는 것 ${tot.citejo})`
  + ` · 법령 조문 ${tot.law} · 같은 규정 조문 ${tot.self}`);
console.log(`  잘못 이은 것 ${tot.wrong}건 · 링크가 안 걸린 '제○조' ${tot.miss}건`);
if (wrongs.length) { console.log("\n[잘못 이은 보기]"); wrongs.forEach((x) => console.log("  " + x)); }

const arg = process.argv[2] || "";
const only = KINDS[arg] ? arg : null;
const verbose = only || arg === "-v";

console.log("\n[링크가 안 걸린 까닭]");
for (const [k, why] of Object.entries(KINDS)) {
  const n = miss[k].length;
  const mark = k === "누락" ? "!" : " ";
  console.log(`  ${mark} ${k} ${String(n).padStart(4)}건  ${why}`);
}
for (const [k, list] of Object.entries(miss)) {
  if (!list.length) continue;
  if (only ? k !== only : !(verbose || k === "누락")) continue;
  console.log(`\n[${k} 보기]`);
  (only ? list : list.slice(0, 12)).forEach((x) => console.log("  " + x));
  if (!only && list.length > 12) console.log(`  … 그밖에 ${list.length - 12}건`);
}
