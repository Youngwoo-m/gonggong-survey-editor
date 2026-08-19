/* ============================================================
   core/xrefs.js — 규정 사이 인용
   ------------------------------------------------------------
   편집기가 세 벌이던 동안, 규정 사이 인용이 성한지는 편집기 밖에서
   scripts/checkcites.py 를 따로 돌려야만 알 수 있었고 그 결과는 화면으로
   돌아오지 않았다. 세 규정이 한 트리에 모였으니 그 일을 안으로 들인다.

   여기가 하는 일 셋

     1. 규정을 넘어 조문을 옮기면(이관) 그 조를 인용하던 글을 고쳐 쓴다.
        제76조  →  「무인비행장치 측량 작업규정」제5조

     2. 규정 밖을 가리키는 인용이 성한지 본다.
        「무인비행장치 측량 작업규정」제20조 가 그 규정에 실제로 있는가.

     3. 세 규정이 같은 것을 다른 말로 부르는지 본다.

   ■ 인용을 알아보는 규칙은 objects.js 것을 그대로 쓴다

     화면에 그리는 링크와 여기의 판정이 갈라지면, 사람 눈에는 링크가 걸려
     있는데 검증은 못 찾는 일이 생긴다. isSelfCite 하나를 함께 쓴다.

   DOM 을 모른다.
   ============================================================ */
import * as M from "./model.js?v=20260823e";
import { isSelfCite, RE_JO_G } from "./objects.js?v=20260823e";

/** 「규정 이름」 뒤에 붙은 조 — 규정 밖을 가리키는 인용 */
const RE_CROSS = /[「『]([^」』]{2,60})[」』]\s*(?:[（(][^()（）]{0,40}[)）])?\s*제\s*(\d+)\s*조(?:의\s*(\d+))?/g;

/* ---------- 규정 안의 조문 찾기 ---------- */

/** 규정 노드 안의 조문을 번호로 찾는 표 — { "12": node, "12의2": node } */
export function articleIndex(regNode) {
  const by = new Map();
  M.walk(regNode.children || [], (n) => {
    if (n.level !== "조" || n.annexRef) return;
    by.set(String(n.no) + (n.branch ? `의${n.branch}` : ""), n);
  });
  return by;
}

/** 규정 이름(또는 줄임말)으로 규정 노드를 찾는다 */
export function regByName(tree, name) {
  const want = String(name || "").replace(/\s+/g, "");
  if (!want) return null;
  for (const reg of (tree || []).filter(M.isRegNode)) {
    const full = String(reg.title || "").replace(/\s+/g, "");
    const shrt = String(reg.short || "").replace(/\s+/g, "");
    if (full === want || shrt === want) return reg;
    // 「공공측량 작업규정」처럼 이름이 온전히 든 경우까지
    if (full && (full.includes(want) || want.includes(full))) return reg;
  }
  return null;
}

/* ---------- 1. 옮긴 뒤 인용 표기 고쳐 쓰기 ---------- */

/**
 * 조문을 옮기면 남은 조문의 번호가 줄줄이 밀린다. 본문에 번호로 적힌 인용은
 * 그대로 두면 조용히 엉뚱한 조를 가리킨다 — 이것이 이관에서 가장 잘 깨지는
 * 자리다. 옮기기 전후의 번호를 짝지어 본문을 함께 고쳐 쓴다.
 *
 * 두 가지를 한 번에 훑는다 (두 번 훑으면 고친 것을 또 고친다).
 *   · 규정을 넘어간 조   제76조 → 「무인비행장치 측량 작업규정」제5조
 *   · 그대로 남았는데 번호만 밀린 조   제229조 → 제215조
 *
 * @param {object} reg   고쳐 쓸 규정 노드
 * @param {Map<string,{to:string, regName?:string}>} plan 옛 번호 → 새 자리
 * @returns {Array<{node, hits, kinds}>}
 */
export function remapCitations(reg, plan) {
  if (!plan || !plan.size) return [];
  const changed = [];
  const roots = M.isRegNode(reg) || !reg.level ? (reg.children || []) : [reg];
  M.walk(roots, (n) => {
    if (!n.body || n.level !== "조" || n.annexRef) return;
    let hits = 0; const kinds = new Set();
    const src = String(n.body);
    const after = src.replace(RE_JO_G(), (m, jo, no, tail, off) => {
      const to = plan.get(String(no));
      if (!to) return m;
      if (!isSelfCite(src.slice(0, off), false)) return m;   // 남의 법령 조는 그대로
      hits += 1;
      if (to.regName) { kinds.add("규정 밖"); return `「${to.regName}」제${to.to}조${tail || ""}`; }
      kinds.add("번호"); return `제${to.to}조${tail || ""}`;
    });
    if (hits) { n.body = tidyRuns(after); changed.push({ node: n, hits, kinds: [...kinds] }); }
  });
  return changed;
}

/**
 * 잇달아 붙은 같은 규정 이름을 지운다.
 *
 * 고쳐 쓰면 "제121조부터 제123조까지" 가
 * "「공공측량 작업규정」제107조부터 「공공측량 작업규정」제109조까지" 가 된다.
 * 뜻은 맞으나 규정 글로는 읽히지 않는다. 이어지는 자리에서는 앞에서 한 번
 * 든 이름이 뒤까지 미치므로 뒤엣것을 지운다 — 규정 원문이 쓰는 꼴이다.
 *
 *   「공공측량 작업규정」제107조부터 제109조까지
 */
export function tidyRuns(text) {
  /* 인용을 죽 훑으며 '지금 어느 규정 이야기인가' 를 들고 간다.
     짝만 보는 규칙으로는 「A」제12조, 「A」제15조, 「A」제18조 에서 셋째를 놓친다 —
     둘째의 이름을 지우고 나면 셋째 앞에 이름이 없어 짝이 서지 않기 때문이다. */
  const TOKEN = /([「『][^」』]{2,60}[」』])?(제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*[항호])*)/g;
  const JOIN_ONLY = /^(?:부터|까지|내지|및|와|과|[,·]|\s)*$/;
  const src = String(text || "");
  let out = "", at = 0, lastName = null, lastEnd = -1, m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(src))) {
    const [whole, name, jo] = m;
    const between = lastEnd >= 0 ? src.slice(lastEnd, m.index) : null;
    const runs = between !== null && JOIN_ONLY.test(between);
    if (name && runs && name === lastName) {
      out += src.slice(at, m.index) + jo;      // 앞에서 든 이름이 여기까지 미친다
      at = m.index + whole.length;
    } else if (name) {
      lastName = name;
    } else if (!runs) {
      lastName = null;                          // 인용이 끊겼다
    }
    lastEnd = m.index + whole.length;
  }
  return out + src.slice(at);
}

/**
 * 규정 안 모든 조문의 지금 번호를 적어 둔다 (id → 번호).
 * 옮기고 번호를 다시 매긴 뒤 짝지으려면 옮기기 전 번호가 있어야 한다.
 */
export function numbersOf(reg) {
  const out = new Map();
  M.walk(reg.children || [], (n) => {
    if (n.level === "조" && !n.annexRef) out.set(n.id, String(n.no) + (n.branch ? `의${n.branch}` : ""));
  });
  return out;
}

/**
 * 옮기기 전 번호와 지금 트리를 견주어 고쳐 쓸 거리를 만든다.
 *
 * @param {Map} before      옮기기 전 id → 번호 (numbersOf)
 * @param {Array} tree      옮긴 뒤 트리
 * @param {string} goneName 규정을 넘어간 조들이 간 규정 이름 (없으면 번호만 갱신)
 * @param {Set} goneIds     규정을 넘어간 조들의 id
 */
/**
 * 옮겨 간 조문이 '두고 온' 조를 부르던 인용 — 거울에 비친 쪽.
 *
 * 작업규정에서 무인비행장치 규정으로 옮긴 조가 본문에서 제121조를 부르고
 * 있었다면, 그 제121조는 작업규정에 남아 있다. 옮긴 자리에서는 남의 규정
 * 조이므로 규정 이름을 붙여야 한다.
 *
 * @param {Map} before   보낸 규정의 옮기기 전 id → 번호
 * @param {Array} tree   옮긴 뒤 트리
 * @param {Set} goneIds  옮겨 간 조들의 id
 * @param {string} fromName 보낸 규정 이름
 */
export function planStayed(before, tree, goneIds, fromName) {
  const plan = new Map();
  for (const [id, oldNo] of before) {
    if (goneIds && goneIds.has(id)) continue;          // 함께 옮겨 간 조는 아니다
    const n = M.findNode(tree, id);
    if (!n) continue;
    const newNo = String(n.no) + (n.branch ? `의${n.branch}` : "");
    plan.set(oldNo, { to: newNo, regName: fromName });
  }
  return plan;
}

export function planFrom(before, tree, goneName, goneIds) {
  const plan = new Map();
  for (const [id, oldNo] of before) {
    const n = M.findNode(tree, id);
    if (!n) continue;                                  // 지워진 조 — 알 수 없다
    const newNo = String(n.no) + (n.branch ? `의${n.branch}` : "");
    if (goneIds && goneIds.has(id)) {
      if (goneName) plan.set(oldNo, { to: newNo, regName: goneName });
    } else if (newNo !== oldNo) {
      plan.set(oldNo, { to: newNo });
    }
  }
  return plan;
}

/** 옮겨 갈 조들의 id 를 모은다 */
export function articleIdsIn(node) {
  const ids = new Set();
  const take = (n) => { if (n.level === "조" && !n.annexRef) ids.add(n.id); };
  take(node); M.walk(node.children || [], take);
  return ids;
}

/* ---------- 2. 규정 밖 인용이 성한가 ---------- */

/**
 * 트리 전체에서 「규정 이름」제N조 꼴의 인용을 모아, 그 조가 실제로 있는지 본다.
 * 우리가 담고 있는 세 규정을 가리키는 것만 본다 — 바깥 법령은 알 길이 없다.
 *
 * @returns {Array} [{ level, fromReg, node, path, regName, no, reason }]
 */
export function checkCrossRefs(tree) {
  const regs = (tree || []).filter(M.isRegNode);
  if (regs.length < 2) return [];
  const idx = new Map();                       // 규정 노드 -> 조문 번호 표
  for (const r of regs) idx.set(r, articleIndex(r));

  const out = [];
  for (const reg of regs) {
    M.walk(reg.children || [], (n) => {
      if (!n.body || n.level !== "조" || n.annexRef) return;
      const text = String(n.body);
      RE_CROSS.lastIndex = 0;
      let m;
      while ((m = RE_CROSS.exec(text))) {
        const [, name, no, branch] = m;
        const to = regByName(tree, name);
        if (!to) continue;                     // 우리가 담지 않은 규정 — 알 수 없다
        if (to === reg) continue;              // 제 이름을 부른 것
        const key = String(no) + (branch ? `의${branch}` : "");
        if (idx.get(to).has(key)) continue;    // 성하다
        out.push({
          fromReg: reg, node: n, regName: to.title, short: M.shortLabel(to),
          no: key, cite: m[0].trim(),
        });
      }
    });
  }
  return out;
}

/* ---------- 3. 세 규정이 같은 것을 다른 말로 부르는가 ---------- */

/**
 * 「…」 · 『…』 안은 규정·지침·매뉴얼의 이름이다 — 고유명사이므로 용어를 맞출 대상이 아니다.
 *
 * 「지상라이다 측량 작업 및 성과에 관한 지침」 은 실제로 그 이름으로 있는 지침이다.
 * 여기의 '라이다' 를 용어 불일치로 짚으면 고칠 수 없는 것을 고치라고 하는 셈이 된다.
 * 자리는 남기고 글자만 지운다 — 앞뒤 낱말 경계가 어긋나지 않게.
 */
function stripNames(text) {
  return String(text || "").replace(/[「『][^」』]{0,80}[」』]/g, (m) => " ".repeat(m.length));
}

/**
 * 손대면 안 되는 자리를 가린다 — 이름과 출처 표시.
 *
 *   「…」 규정·지침·매뉴얼의 이름 (고유명사)
 *   <…>  출처 표시 · 표·수식 표식
 *        <신설 기준점측량 개설 「공공기준점측량의 선점」> 은 현행 규정이 무엇을
 *        어떻게 적고 있는지를 옮겨 둔 것이다. 여기 글자를 고치면 원문을
 *        잘못 인용하는 것이 된다 — 현행은 현행대로 두어야 한다.
 */
function maskProtected(text) {
  const masked = String(text || "").replace(/<[^<>]{0,200}>/g, (m) => {
    /* <현행 제168조 「정의」> 는 현행 규정을 그대로 옮긴 것이라 통째로 가린다.
       표·수식 표식(<img id=…>)도 글이 아니므로 가린다.
       <신설 기준점 측량 개설 「…」> 의 앞부분은 개정안의 편·장 이름이라
       함께 고쳐야 한다 — 그 안의 「…」 만 아래 stripNames 가 가린다. */
    return /^<\s*(?:현행|img)/i.test(m) ? " ".repeat(m.length) : m;
  });
  return stripNames(masked);
}

/**
 * 낱말 하나를 찾는 규칙.
 *
 * 우리말은 조사·어미가 이름씨에 그대로 붙는다 — '레이저측량으로', '라이다를'.
 * 뒤쪽에 한글이 오지 못하게 막으면 정작 쓰인 자리를 죄다 놓친다.
 * 앞쪽만 막아 낱말 가운데에서 걸리는 것을 피하고, 뒤는 열어 둔다.
 * 로마자 낱말(Lidar)은 앞뒤를 다 막는다 — 붙여 쓰는 일이 없다.
 */
function termRe(term) {
  const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return /^[A-Za-z]/.test(term)
    ? new RegExp(`(?<![A-Za-z])${esc}(?![A-Za-z])`, "g")
    : new RegExp(`(?<![가-힣A-Za-z])${esc}`, "g");
}

/**
 * 함께 맞춰야 하는 말 — 무엇으로 맞추고, 그 근거가 무엇인가.
 *
 * ■ 무엇을 기준으로 삼는가 — 현행 고시 체계를 앞세우고 표준용어를 병기한다
 *
 *   국가공간정보 표준용어집(KS X ISO 번역 기반)과 현행 측량 관계 고시가
 *   서로 다른 말을 쓰는 자리가 있다. 개정안 본문은 제가 인용하는 고시의
 *   이름과 어긋나면 안 되므로 — 「항공레이저측량 작업규정」을 인용하면서
 *   본문에서는 '라이다' 라고 부를 수는 없다 — 고시 체계를 따르고,
 *   표준용어는 근거로 함께 적어 어느 쪽인지 알 수 있게 한다.
 *
 *   basis  이 말을 쓰는 근거 (현행 고시·규정 이름)
 *   std    국가공간정보 표준용어집이 쓰는 말과 인용표준번호
 *          (data/표준용어집.json · scripts/fetch_terms.py 로 받는다)
 *
 * ■ 라이다와 레이저측량은 같은 말이 아니다
 *
 *   표준용어집의 '라이다(light detection and ranging)' 는 센서·기술이고,
 *   '레이저측량' 은 그것으로 하는 측량 방법이다. 본문도 이미 갈라 쓴다 —
 *   "고정형 지상라이다를 이용한 지상레이저측량". 그래서 장비를 가리키는
 *   라이다는 짚지 않고, 측량 방법 자리에 라이다가 쓰인 것만 짚는다.
 */
export const TERM_RULES = [
  {
    canon: "레이저측량",
    variants: ["라이더"],
    /* 이 자리에 쓰인 라이다만 '방법' 으로 본다 — 장비를 가리키는 라이다는 그대로 둔다 */
    methodOnly: /라이다\s*측량|라이다에\s*의한\s*(?:[가-힣]{0,6}\s*)?(?:작업)?방법/g,
    basis: "「항공레이저측량 작업규정」 등 현행 고시 명칭",
    std: { ko: "라이다, 광탐지 및 레인지 측정", no: "KS X ISO TS 19130-2" },
    note: "장비·센서는 '라이다', 측량 방법은 '레이저측량' 으로 갈라 씁니다.",
  },
  {
    canon: "수치표고모형",
    variants: ["수치표고모델"],
    basis: "「수치표고모형의 구축 및 관리 등에 관한 규정」",
    std: { ko: "수치표고모델", no: "KS X ISO TS 19101-2" },
  },
  {
    canon: "점군자료",
    variants: ["점군데이터", "포인트클라우드", "포인트 클라우드"],
    basis: "현행 고시 표기",
    std: { ko: "점군, 포인트 클라우드", no: "KS X ISO TS 19130-2" },
  },
  {
    canon: "정사영상",
    variants: ["정사사진", "정사이미지"],
    basis: "「정사영상 제작 작업 및 성과에 관한 규정」",
    std: { ko: "정사영상", no: "KS X ISO TS 19101-2" },     // 표준용어집과 일치
  },
  {
    canon: "기준점 측량",
    variants: ["기준점측량"],
    label: "이름씨 뒤의 '측량' 띄어쓰기",
    /* 앞말이 구체적인 이름씨인 것만 띄운다 — 기준점 · 삼각점 · 수준점 ·
       조절점 · 지하시설물. 앞가지가 붙은 것도 함께 걸린다
       (공공삼각점측량 · 간접수준점측량 · 지상기준점측량).

       레이저측량 · 공공측량 · 지형측량 · 응용측량 · 항공사진측량처럼 굳어진
       갈래 이름은 건드리지 않는다. 넓게 잡으면 방금 맞춘 레이저측량까지
       쪼개진다 — 본문에 75곳이 있다.

       이미 띄어 쓴 것은 '측량' 이 바로 붙어 있지 않으므로 걸리지 않는다. */
    pattern: /([가-힣]{0,6}(?:삼각점|수준점|기준점|조절점|지하시설물))측량/g,
    rewrite: (m) => `${m[1]} 측량`,
    basis: "이름씨 뒤의 '측량' 을 띄어 쓴다 — 표준용어집도 '지상 기준점' 으로 띄운다",
    std: { ko: "지상 기준점", no: "KS X ISO 19130-1" },
    note: "굳어진 갈래 이름(레이저측량 · 공공측량 · 지형측량 등)은 그대로 둡니다.",
  },
  {
    canon: "무인비행장치",
    variants: ["무인항공기", "드론"],
    basis: "「무인비행장치 측량 작업규정」",
    std: null,                                              // 표준용어집에 항목 없음
  },
];

/** 예전 이름 — 규칙에서 맞춘 말과 변형만 뽑아 쓰던 곳이 있다 */
export const TERM_SETS = TERM_RULES.map((r) => [r.canon, ...r.variants]);

/**
 * 세 규정이 같은 뜻을 다른 말로 부르는 자리를 모은다.
 * 한 규정 안에서만 쓰이는 말은 짚지 않는다 — 규정 사이에서 갈릴 때만 본다.
 *
 * @returns {Array} [{ canon, basis, std, note, used: [{term, regs, count}] }]
 */
export function checkTerms(tree) {
  const regs = (tree || []).filter(M.isRegNode);
  if (regs.length < 2) return [];

  // 규정마다 글을 한 덩이로 모은다 (「…」 안의 고유명사는 뺀다)
  const textOf = new Map();
  for (const reg of regs) {
    let text = "";
    M.walk(reg.children || [], (n) => {
      if (n.level !== "조") return;
      text += " " + stripNames((n.title || "") + " " + (n.body || ""));
    });
    textOf.set(M.shortLabel(reg), text);
  }

  const out = [];
  for (const rule of TERM_RULES) {
    const seen = new Map();                    // 말 -> Map(규정 -> 몇 곳)
    const count = (text, term) => {
      // 라이다처럼 자리에 따라 뜻이 달라지는 말은 그 자리에서만 센다
      if (rule.methodOnly && /라이다|LiDAR|Lidar|lidar/i.test(term)) {
        rule.methodOnly.lastIndex = 0;
        return (text.match(rule.methodOnly) || []).length;
      }
      return (text.match(termRe(term)) || []).length;
    };
    const terms = [rule.canon, ...rule.variants,
                   ...(rule.methodOnly ? ["라이다"] : [])];
    for (const [regName, text] of textOf) {
      for (const term of terms) {
        const c = count(text, term);
        if (!c) continue;
        if (!seen.has(term)) seen.set(term, new Map());
        seen.get(term).set(regName, c);
      }
    }
    if (seen.size < 2) continue;
    const used = [...seen].map(([term, byReg]) => ({
      term, regs: [...byReg.keys()], count: [...byReg.values()].reduce((a, b) => a + b, 0),
    }));
    if (new Set(used.flatMap((u) => u.regs)).size < 2) continue;
    out.push({ canon: rule.canon, basis: rule.basis, std: rule.std, note: rule.note, used });
  }
  return out;
}

/* ---------- 3-2. 용어를 실제로 맞추기 ---------- */

/**
 * 용어를 맞출 자리를 찾는다 (고치지는 않는다).
 *
 * 「…」 안은 규정·지침 이름이라 건드리지 않는다. 「지상라이다 측량 작업 및
 * 성과에 관한 지침」 은 실제로 그 이름인 지침이라 고치면 없는 지침이 된다.
 * 자리를 세어 두고 원문에서 그 자리만 바꾼다.
 *
 * @param {Array} tree   프로젝트 트리 (최상위가 규정)
 * @param {Array} rules  TERM_RULES 가운데 적용할 것
 * @returns {Array} [{ reg, node, field, before, after, hits, rule, samples }]
 */
export function planTermFixes(tree, rules) {
  const out = [];
  for (const reg of (tree || []).filter(M.isRegNode)) {
    M.walk(reg.children || [], (n) => {
      if (n.annexRef) return;                       // 별표 서식은 따로 다룬다
      for (const field of ["title", "body"]) {
        const raw = String(n[field] || "");
        if (!raw) continue;
        let after = raw, hits = 0;
        const samples = [];
        for (const rule of rules) {
          const res = applyRule(after, rule);
          if (!res.hits) continue;
          hits += res.hits; after = res.text;
          samples.push(...res.samples.map((x) => ({ ...x, canon: rule.canon })));
        }
        if (hits) out.push({ reg, node: n, field, before: raw, after, hits, samples });
      }
    });
  }
  return out;
}

/** 규칙 하나를 글 한 덩이에 적용한다 — 「…」 안은 건너뛴다 */
function applyRule(text, rule) {
  const src = String(text);
  const masked = maskProtected(src);                // 이름·출처 표시는 공백으로 가려 둔다
  const spans = [];

  const push = (start, end, from, to) => spans.push({ start, end, from, to });

  if (rule.methodOnly) {
    // 라이다처럼 자리에 따라 뜻이 달라지는 말 — 그 자리 안의 낱말만 바꾼다
    rule.methodOnly.lastIndex = 0;
    let m;
    while ((m = rule.methodOnly.exec(masked))) {
      const i = m[0].search(/라이다|LiDAR|Lidar|LIDAR|lidar/);
      if (i < 0) continue;
      const word = m[0].slice(i).match(/라이다|LiDAR|Lidar|LIDAR|lidar/)[0];
      push(m.index + i, m.index + i + word.length, word, rule.canon);
    }
  } else if (rule.pattern) {
    // 낱말을 통째로 갈아 끼우는 것이 아니라 꼴만 바꾸는 규칙 (합성어 띄어쓰기)
    rule.pattern.lastIndex = 0;
    let m;
    while ((m = rule.pattern.exec(masked))) {
      const to = rule.rewrite(m);
      if (!to || to === m[0]) continue;
      push(m.index, m.index + m[0].length, m[0], to);
    }
  } else {
    for (const v of rule.variants) {
      const re = termRe(v);
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(masked))) push(m.index, m.index + v.length, v, rule.canon);
    }
  }
  if (!spans.length) return { text: src, hits: 0, samples: [] };

  spans.sort((a, b) => a.start - b.start);
  let out = "", at = 0;
  const samples = [];
  for (const sp of spans) {
    if (sp.start < at) continue;                    // 겹치면 앞엣것을 살린다
    out += src.slice(at, sp.start) + sp.to;
    samples.push({ from: sp.from, to: sp.to,
      around: src.slice(Math.max(0, sp.start - 20), sp.end + 20).replace(/\n/g, " ") });
    at = sp.end;
  }
  return { text: out + src.slice(at), hits: spans.length, samples };
}

/* ---------- 4. 별표 번호가 부딪치는가 ---------- */

/**
 * 규정을 넘어 옮긴 조문이 부르는 별표 번호가, 받은 규정에서 이미 쓰이고 있는가.
 * 이관한 조문만 본다 — 규정마다 별표 번호를 따로 매기는 것은 본디 그러하다.
 */
export function checkAnnexClash(tree) {
  const regs = (tree || []).filter(M.isRegNode);
  const out = [];
  for (const reg of regs) {
    // 이 규정이 지닌 별표 번호
    const own = new Set();
    M.walk(reg.children || [], (n) => {
      if (n.annexRef) own.add(`${n.annexRef.gubun} ${n.annexRef.no}`);
    });
    M.walk(reg.children || [], (n) => {
      if (!n.transferredFrom || n.level !== "조") return;
      const cites = new Set();
      const t = (n.body || "") + " " + (n.citesAnnex || []).join(" ");
      for (const m of t.matchAll(/(별표|별지)\s*제?\s*(\d+)\s*호?/g)) {
        cites.add(`${m[1]} ${m[2]}`);
      }
      for (const c of cites) {
        if (own.has(c)) continue;              // 그 번호가 이 규정에 있다 — 성하다
        out.push({ reg, node: n, cite: c, from: n.transferredFrom.regName });
      }
    });
  }
  return out;
}

/* ---------- 규정 가지 지문 ---------- */

/**
 * 규정 하나의 내용 지문.
 *
 * 판(버전)은 세 규정을 한꺼번에 담으므로, 어느 한 규정만 놓고 보면 여러 판이
 * 똑같은 내용일 수 있다 — 작업규정은 v1·v2·이어받음 세 판에서 글자 하나
 * 다르지 않다. 개정안을 고르는 자리에 같은 것을 셋 늘어놓으면, 무엇이
 * 다른지 알 수 없어 고를 수가 없다. 내용으로 같고 다름을 가린다.
 */
export function regFingerprint(reg) {
  if (!reg) return "";
  const s = JSON.stringify(reg.children || []);
  let h = 5381;
  for (let i = 0; i < s.length; i += 1) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return `${s.length}:${h.toString(36)}`;
}
