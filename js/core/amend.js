/* ============================================================
   core/amend.js — 개정문(개정 지시문) 짓기
   ------------------------------------------------------------
   법제처 법령안편집기가 하는 일의 알맹이가 이것이다.
   (App/관련규정/법제처_법령안편집기 · 교재 II장 '법령안 일부개정')

   신구조문 대비표가 '무엇이 어떻게 달라졌는가' 를 보이는 표라면,
   개정문은 '무엇을 어떻게 고치라' 고 적는 글이다. 고시로 낼 때 실제로
   실리는 것은 개정문이고, 대비표는 붙임으로 따라간다.

     「공공측량 작업규정」 일부를 다음과 같이 개정한다.

     제5조제1항 중 "수치표고모델"을 "수치표고모형"으로 한다.
     제7조를 다음과 같이 한다.
       제7조(성과의 품질기준) ① …
     제12조를 삭제한다.
     제20조를 제18조로 한다.

   ■ 짓는 규칙 (교재 II. 1~11)

     자구변경    제N조제M항 중 "옛말"을 "새말"로 한다.
                 한 조에 여럿이면 ", "옛말"을 "새말"로 하고," 로 잇는다
     제목 개정    제N조의 제목 중 "옛말"을 "새말"로 한다.
     전문개정    바뀐 분량이 많으면 제N조를 다음과 같이 한다. + 전문
     신설        제N조를 다음과 같이 신설한다. + 전문
     삭제        제N조를 삭제한다.
     이동        제N조를 제M조로 한다.

   ■ 어디를 고치는지 짚기

     우리 모델은 조 하나의 본문을 통글로 지니므로, 바뀐 자리가 몇 항인지
     글 앞쪽의 ①②③ 를 세어 알아낸다. 호(1. 2. 3.)도 같은 식으로 본다.
     항·호를 못 짚으면 조만 적는다 — 틀리게 짚느니 덜 짚는다.

   DOM 을 모른다.
   ============================================================ */

const HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";

/** 전문개정으로 볼 만큼 많이 바뀌었는가 — 바뀐 글자가 절반을 넘으면 */
const FULL_REWRITE_RATIO = 0.6;

/* ---------- 자리 짚기 ---------- */

/**
 * 글 안 어느 자리가 몇 항 몇 호인지.
 * @returns {{hang:number, ho:number}} 못 짚으면 0
 */
export function whereIn(text, offset) {
  const head = String(text || "").slice(0, offset);
  let hang = 0;
  for (const ch of head) {
    const i = HANG.indexOf(ch);
    if (i >= 0) hang = i + 1;
  }
  // 호는 마지막 항 뒤에서만 센다 — 항이 바뀌면 호도 1부터 다시다
  const lastHang = Math.max(...[...HANG].map((c) => head.lastIndexOf(c)));
  const tail = head.slice(lastHang >= 0 ? lastHang : 0);
  let ho = 0;
  for (const m of tail.matchAll(/(?:^|\n)\s*(\d{1,2})\.\s/g)) ho = +m[1];
  return { hang, ho };
}

/** 제5조제1항제2호 꼴로 적는다 */
export function addrOf(label, at) {
  let s = label || "";
  if (at && at.hang) s += `제${at.hang}항`;
  if (at && at.ho) s += `제${at.ho}호`;
  return s;
}

/* ---------- 자구변경 짝짓기 ---------- */

/**
 * 어절 도막에서 '옛말 → 새말' 짝을 뽑는다.
 * 붙어 있는 -/+ 를 한 짝으로 본다. 한쪽만 있는 것은 넣거나 뺀 것이다.
 *
 * @param {Array} runs core/textdiff.js 의 wordDiff 결과 [{t,s}]
 * @param {string} before 옛 글 (자리 짚기에 쓴다)
 * @returns {Array<{from, to, at}>}
 */
export function pairChanges(runs, before) {
  if (!runs) return [];
  const out = [];
  let off = 0;                       // 옛 글에서의 자리
  for (let i = 0; i < runs.length; i += 1) {
    const r = runs[i];
    if (r.t === "=") { off += r.s.length; continue; }
    let from = "", to = "";
    const at = whereIn(before, off);
    // 붙어 있는 -/+ 를 모아 한 짝으로
    while (i < runs.length && runs[i].t !== "=") {
      if (runs[i].t === "-") { from += runs[i].s; off += runs[i].s.length; }
      else to += runs[i].s;
      i += 1;
    }
    i -= 1;
    from = from.trim(); to = to.trim();
    if (!from && !to) continue;
    out.push({ from, to, at });
  }
  return out;
}

/**
 * 새 글 가운데 새로 쓴 대목이 얼마나 되는가 (0~1).
 *
 * 뺀 말과 넣은 말을 함께 세면 낱말 하나만 갈아 끼워도 절반이 넘는다 —
 * "수치표고모델로"(7) 를 빼고 "수치표고모형으로"(8) 를 넣으면 15가 되어,
 * 남은 9자보다 커진다. 새 글을 잣대로 삼아 새로 쓴 대목만 센다.
 */
export function changeRatio(runs) {
  if (!runs || !runs.length) return 0;
  let kept = 0, added = 0;
  for (const r of runs) {
    const n = r.s.replace(/\s+/g, "").length;
    if (r.t === "=") kept += n;
    else if (r.t === "+") added += n;
  }
  return (kept + added) ? added / (kept + added) : 0;
}

/** 고친 자리가 몇 군데인가 — 흩어져 여럿이면 전문개정이 읽기 낫다 */
function changeGroups(runs) {
  if (!runs) return 0;
  let n = 0, inRun = false;
  for (const r of runs) {
    if (r.t === "=") { inRun = false; continue; }
    if (!inRun) { n += 1; inRun = true; }
  }
  return n;
}

/**
 * 전문개정으로 적을 것인가.
 * 새로 쓴 대목이 태반이거나, 고친 자리가 너무 흩어져 자구변경으로 적으면
 * 오히려 읽기 어려울 때 전문개정으로 적는다.
 */
function isFullRewrite(runs) {
  return changeRatio(runs) >= FULL_REWRITE_RATIO || changeGroups(runs) >= 6;
}

/* ---------- 개정문 짓기 ---------- */

/**
 * 비교 결과에서 개정문을 짓는다.
 *
 * @param {Array} rows core/diff.js 의 buildComparison 결과 rows
 * @param {object} opts { regName, whole } whole=true 면 전부개정 머리말
 * @returns {{head:string, items:Array<{label, text, body, kind}>, text:string}}
 */
export function buildAmendment(rows, opts = {}) {
  const regName = opts.regName || "이 규정";
  const head = opts.whole
    ? `「${regName}」 전부를 다음과 같이 개정한다.`
    : `「${regName}」 일부를 다음과 같이 개정한다.`;

  const items = [];
  for (const r of rows || []) {
    const b = r.before, a = r.after;
    if (r.kind === "유지") continue;

    if (r.kind === "신설") {
      items.push({ kind: "신설", label: a ? a.label : "",
        text: `${a ? a.label : ""}를 다음과 같이 신설한다.`,
        body: fullText(a), order: a ? a.label : "" });
      continue;
    }
    if (r.kind === "삭제") {
      items.push({ kind: "삭제", label: b ? b.label : "",
        text: `${b ? b.label : ""}를 삭제한다.`, order: b ? b.label : "" });
      continue;
    }
    if (r.kind === "이동") {
      // 자리만 옮긴 것 — 번호가 바뀌었을 때만 적는다
      if (b && a && b.label !== a.label) {
        items.push({ kind: "이동", label: b.label,
          text: `${b.label}를 ${a.label}로 한다.`, order: b.label });
      }
      continue;
    }

    // 수정 · 이동·수정 · 통합
    const whole = isFullRewrite(r.bodyDiff);
    const numberMoved = b && a && b.label !== a.label;
    if (numberMoved) {
      items.push({ kind: "이동", label: b.label,
        text: `${b.label}를 ${a.label}로 한다.`, order: b.label });
    }
    const label = a ? a.label : (b ? b.label : "");

    if (whole) {
      items.push({ kind: "전문개정", label,
        text: `${label}를 다음과 같이 한다.`, body: fullText(a), order: label });
      continue;
    }

    // 제목 고침
    const tPairs = pairChanges(r.titleDiff, b ? b.title : "");
    if (tPairs.length) {
      items.push({ kind: "제목", label,
        text: `${label}의 제목 중 ${joinPairs(tPairs)}.`, order: label });
    }
    // 본문 자구 고침 — 항·호별로 묶는다
    const bPairs = pairChanges(r.bodyDiff, b ? b.body : "");
    for (const [addr, group] of groupByAddr(bPairs, label)) {
      items.push({ kind: "자구", label,
        text: `${addr} 중 ${joinPairs(group)}.`, order: label });
    }
  }
  return { head, items, text: [head, "", ...items.map(itemText)].join("\n") };
}

/** 항·호가 같은 것끼리 묶는다 — 한 문장으로 잇기 위해 */
function groupByAddr(pairs, label) {
  const map = new Map();
  for (const p of pairs) {
    const addr = addrOf(label, p.at);
    if (!map.has(addr)) map.set(addr, []);
    map.get(addr).push(p);
  }
  return [...map];
}

/* ---------- 조사 ----------
   법령문은 조사를 가려 쓴다. "을/를" 은 받침 유무로, "으로/로" 는 받침이
   있되 'ㄹ' 이 아닐 때만 '으로' 를 쓴다. 따옴표 안 마지막 글자로 가린다. */

/** 마지막 글자에 받침이 있는가 — 없으면 null, 있으면 종성 번호 */
function jong(word) {
  const ch = String(word || "").trim().slice(-1);
  const c = ch.charCodeAt(0);
  if (!(c >= 0xac00 && c <= 0xd7a3)) return null;   // 한글이 아니면 알 수 없다
  return (c - 0xac00) % 28;                          // 0 이면 받침 없음
}
const eul = (w) => { const j = jong(w); return j === null ? "을(를)" : (j ? "을" : "를"); };
const ro = (w) => {
  const j = jong(w);
  if (j === null) return "(으)로";
  return (j === 0 || j === 8) ? "로" : "으로";       // 8 = ㄹ
};

/** "가"를 "나"로 하고, "다"를 "라"로 한다 */
function joinPairs(pairs) {
  const parts = pairs.map((p) => {
    if (p.from && p.to) return { s: `“${p.from}”${eul(p.from)} “${p.to}”${ro(p.to)}`, verb: "하" };
    if (!p.from) return { s: `“${p.to}”${eul(p.to)}`, verb: "넣" };
    return { s: `“${p.from}”${eul(p.from)}`, verb: "빼" };
  });
  // 마지막만 '한다', 앞엣것은 '하고' 로 잇는다
  const END = { "하": "한다", "넣": "넣는다", "빼": "뺀다" };
  return parts.map((x, i) =>
    `${x.s} ${i === parts.length - 1 ? END[x.verb] : x.verb + "고"}`).join(", ");
}

function fullText(side) {
  if (!side) return "";
  const head = `${side.label}${side.title ? `(${side.title})` : ""}`;
  return side.body ? `${head} ${side.body}` : head;
}

function itemText(it) {
  return it.body ? `${it.text}\n  ${it.body.replace(/\n/g, "\n  ")}` : it.text;
}
