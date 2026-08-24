/* ============================================================
   core/reasonlink.js — 변경 사유 글 속의 조문·별표를 링크로 잇는다

   사유 글에는 두 갈래 번호가 섞여 있다.
     · 개정안 번호   "제31조(공공기준점측량의 공정별 작업구분 및 순서) 한 조로 통합"
     · 현행 번호     "○ 현행 규정: 제29조(…)" · "현행 제145조가 제166조가 된다"
   앞의 것만 이어야 한다. 현행 번호를 개정안 조문에 이으면 엉뚱한 데로 간다.

   그래서 두 가지를 가린다.
     1) '○ 현행 규정:' 도막은 통째로 잇지 아니한다 (그 도막의 번호는 모두 현행이다)
     2) '현행 제145조' 처럼 앞에 '현행' 이 붙은 것과, 「○○법」 제42조 처럼
        다른 법령을 가리키는 것은 건드리지 아니한다
   ============================================================ */

import { linkStdRefs } from "./objects.js?v=20260824f";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/** 다른 법령·규정을 가리키는 자리 — 「○○법」(이하 "법"이라 한다) 제42조제1항 */
const RE_LAWJO = new RegExp(
  "[「『][^」』]{2,60}[」』]\\s*(?:\\([^()]{0,40}\\)\\s*)?" +
  "(?:제\\s*\\d+\\s*조(?:의\\s*\\d+)?(?:\\s*제\\s*\\d+\\s*[항호])*[,·\\s및과와]*)+", "g");
/**
 * '현행 제145조' · '현행 별표 20' — 현행 규정의 번호다.
 * 이어 붙는 번호까지 한 덩이로 잡는다 — 현행 제43조·제59조·제74조 · 현행 제10·30·42조
 */
const RE_WAS = /현행\s*(?:제\s*\d+(?:\s*[·,]\s*\d+)*\s*조(?:의\s*\d+)?|별표\s*\d+|별지\s*(?:제\s*)?\d+\s*(?:호\s*서식)?)(?:\s*[·,]\s*(?:제\s*)?\d+\s*(?:조(?:의\s*\d+)?)?)*/g;
/** 같은 법·시행령 꼴 */
const RE_LAWWORD = /(?:같은\s*법(?:\s*시행령|\s*시행규칙)?|같은\s*규정|시행령|시행규칙|법률|법|영|규칙)\s*제\s*\d+\s*조(?:의\s*\d+)?/g;

const RE_JO = /제\s*(\d+)\s*조/g;
/** 별표 31 · 별지 제3호 서식 · 별지 3 */
const RE_ANX = /(별표|별지)\s*(?:제\s*)?(\d+)\s*(?:호\s*서식)?/g;

const HEAD = /^○\s*(.+?)\s*:/;
const SKIP_SECTION = "현행 규정";

/**
 * 사유 글 → 링크가 박힌 HTML
 * @param {string} text  변경 사유 원문
 * @param {{hasJo?:(no:number)=>boolean, hasAnx?:(gubun:string,no:number)=>boolean}} nav
 */
export function linkReason(text, nav = {}) {
  const hasJo = nav.hasJo || (() => true);
  const hasAnx = nav.hasAnx || (() => true);
  const resolveStd = nav.resolveStd || null;
  let section = "";

  return String(text ?? "").split("\n").map((line) => {
    const h = HEAD.exec(line.trim());
    if (h) section = h[1];
    if (section === SKIP_SECTION) return esc(line);

    // 건드리지 아니할 자리를 먼저 빼 둔다.
    // 자리를 지키는 표는 글에 나올 수 없는 널 문자로 감싼다 — 숫자만 쓰면
    // 본문의 진짜 숫자와 헷갈린다
    const keep = [];
    let s = esc(line);
    for (const re of [RE_LAWJO, RE_WAS, RE_LAWWORD]) {
      re.lastIndex = 0;
      s = s.replace(re, (m) => `\u0000${keep.push(m) - 1}\u0000`);
    }

    s = s.replace(RE_ANX, (m, g, n) => {
      const no = Number(n);
      if (!hasAnx(g, no)) return m;
      return `<a class="cite anx" href="#" data-anx="${g}" data-anx-no="${no}"`
        + ` title="${g} ${no}(으)로 갑니다">${m}</a>`;
    });
    s = s.replace(RE_JO, (m, n) => {
      const no = Number(n);
      if (!hasJo(no)) return m;
      return `<a class="cite self" href="#" data-jo="${no}"`
        + ` title="제${no}조로 갑니다">${m}</a>`;
    });

    // ISO 19157-1:2023 처럼 맨몸으로 적힌 표준 — 참조규정 창에서 연다.
    // 사유에 든 인용이 본문보다 훨씬 많아, 여기를 빼면 걸린 것이 거의 없다.
    if (resolveStd) s = linkStdRefs(s, resolveStd);

    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => keep[Number(i)]);
  }).join("\n");
}

/**
 * 링크에 누름 동작을 붙인다.
 * @param {HTMLElement} host
 * @param {{onJo?:(no:number)=>void, onAnx?:(gubun:string,no:number)=>void}} nav
 */
export function wireReasonLinks(host, nav = {}) {
  host.querySelectorAll("a.cite.std[data-reg]").forEach((a) => {
    a.onclick = (e) => {
      e.preventDefault();
      nav.onCite?.(a.dataset.reg, a.textContent, "", a.dataset.clause || "");
    };
  });
  host.querySelectorAll("a.cite[data-jo]").forEach((a) => {
    a.onclick = (e) => { e.preventDefault(); nav.onJo?.(Number(a.dataset.jo)); };
  });
  host.querySelectorAll("a.cite[data-anx]").forEach((a) => {
    a.onclick = (e) => {
      e.preventDefault();
      nav.onAnx?.(a.dataset.anx, Number(a.dataset.anxNo));
    };
  });
}
