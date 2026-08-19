/* ============================================================
   core/eqmath.js — 한글 수식 스크립트를 MathML 로 바꾼다
   ------------------------------------------------------------
   국가법령정보센터 본문은 수식을 그림으로 넣어 두었고, 원본 HWPX 에는
   한글 수식 편집기의 스크립트가 들어 있다. 그 스크립트를 브라우저가
   그대로 그릴 수 있는 MathML 로 옮긴다. 딸린 라이브러리는 없다.

   다루는 것
     LEFT [ … RIGHT ]   LEFT | … RIGHT |    괄호·절댓값 (세로로 늘어난다)
     eqalign{ a # b # c }                    줄을 쌓는다 (행렬·열벡터)
     {a} over {b}                            분수
     sqrt{a}                                 근호
     _{…}  ^{…}                              아래·위 첨자
     TRIANGLE · SIGMA · lambda …             기호
     ``` (백틱)                              자간 — 원문의 칸 맞춤을 살린다

   백틱을 지우지 않고 너비로 옮기는 까닭:
   한글 수식에는 행렬의 열을 나누는 표시가 없다. 글쓴이가 백틱을 여러 개
   넣어 눈으로 칸을 맞추어 두었으므로, 그 개수를 너비로 옮기면 원문과
   같은 자리에 선다.
   ============================================================ */

/* 한글 수식 낱말 → 유니코드
   글자(Δ·λ·φ …)는 변수이므로 <mi> 로, 셈말(×·≤·∑ …)은 <mo> 로 찍는다.
   섞으면 'Δ N' 처럼 사이가 벌어져 원문과 달라진다. */
const SYM = {
  TIMES: ["×", "o"], CDOT: ["·", "o"], DIV: ["÷", "o"], PM: ["±", "o"], MP: ["∓", "o"],
  LEQ: ["≤", "o"], GEQ: ["≥", "o"], NEQ: ["≠", "o"], APPROX: ["≒", "o"],
  SIM: ["∼", "o"], PROP: ["∝", "o"], BULLET: ["•", "o"], DEG: ["°", "o"],
  SUM: ["∑", "o"], PROD: ["∏", "o"], INT: ["∫", "o"],
  INF: ["∞", "i"], PARTIAL: ["∂", "i"], TRIANGLE: ["Δ", "i"],
};

/* 그리스 문자 — 낱말을 모두 대문자로 썼으면 대문자로 찍는다
   (SIGMA → Σ · sigma → σ). 모두 변수이므로 <mi> 로 찍는다. */
const GREEK = {
  ALPHA: ["α", "Α"], BETA: ["β", "Β"], GAMMA: ["γ", "Γ"], DELTA: ["δ", "Δ"],
  EPSILON: ["ε", "Ε"], ZETA: ["ζ", "Ζ"], ETA: ["η", "Η"], THETA: ["θ", "Θ"],
  IOTA: ["ι", "Ι"], KAPPA: ["κ", "Κ"], LAMBDA: ["λ", "Λ"], MU: ["μ", "Μ"],
  NU: ["ν", "Ν"], XI: ["ξ", "Ξ"], PI: ["π", "Π"], RHO: ["ρ", "Ρ"],
  SIGMA: ["σ", "Σ"], TAU: ["τ", "Τ"], UPSILON: ["υ", "Υ"], PHI: ["φ", "Φ"],
  CHI: ["χ", "Χ"], PSI: ["ψ", "Ψ"], OMEGA: ["ω", "Ω"],
};
/* 늘 곧게 세우는 함수 이름 */
const FUNC = new Set(["sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp",
                      "max", "min", "lim", "cm", "mm", "km", "m"]);
const OPS = "+-=<>,;:/±×÷≤≥≠≒∼∝•";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- 낱말 나누기 ---------- */
function lex(src) {
  const s = String(src || "").replace(/\r/g, "");
  const out = [];
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (c === "`" || c === "~") {                    // 자간
      let n = 0;
      while (i < s.length && (s[i] === "`" || s[i] === "~")) { n++; i++; }
      out.push({ t: "sp", n });
      continue;
    }
    if (/\s/.test(c)) { i++; continue; }
    if (c === "{" || c === "}") { out.push({ t: c }); i++; continue; }
    if (c === "#") { out.push({ t: "#" }); i++; continue; }
    if (c === "_" || c === "^") { out.push({ t: c }); i++; continue; }
    if (/[0-9]/.test(c)) {
      let j = i;
      while (j < s.length && /[0-9.]/.test(s[j])) j++;
      out.push({ t: "num", v: s.slice(i, j) });
      i = j;
      continue;
    }
    if (/[A-Za-z]/.test(c)) {
      let j = i;
      while (j < s.length && /[A-Za-z]/.test(s[j])) j++;
      const w = s.slice(i, j);
      i = j;
      const up = w.toUpperCase();
      if (up === "LEFT" || up === "RIGHT") out.push({ t: up });
      else if (up === "EQALIGN" || up === "MATRIX" || up === "PILE") out.push({ t: "stack" });
      else if (up === "OVER") out.push({ t: "over" });
      else if (up === "SQRT") out.push({ t: "sqrt" });
      else if (GREEK[up]) out.push({ t: "sym", k: "i",
                                     v: GREEK[up][w === up ? 1 : 0] });
      else if (SYM[up]) out.push({ t: "sym", v: SYM[up][0], k: SYM[up][1] });
      else out.push({ t: "id", v: w });
      continue;
    }
    if (OPS.includes(c)) { out.push({ t: "op", v: c }); i++; continue; }
    if ("()[]|".includes(c)) { out.push({ t: "fence", v: c }); i++; continue; }
    out.push({ t: "id", v: c });                      // ϕ 처럼 그대로 쓰는 글자
    i++;
  }
  return out;
}

/* ---------- 낱말 → MathML ---------- */
const mi = (v) => (FUNC.has(v) || v.length > 1)
  ? `<mi mathvariant="normal">${esc(v)}</mi>` : `<mi>${esc(v)}</mi>`;
const space = (n) => (n >= 2 ? `<mspace width="${Math.min(n * 0.28, 8).toFixed(2)}em"/>` : "");

class P {
  constructor(toks) { this.k = toks; this.i = 0; }
  peek() { return this.k[this.i]; }
  next() { return this.k[this.i++]; }

  /** 끝나는 자리를 만날 때까지 읽는다 */
  seq(stop) {
    const out = [];
    for (;;) {
      const t = this.peek();
      if (!t) break;
      if (stop && stop(t)) break;
      const node = this.atom();
      if (node === null) continue;
      out.push(this.scripts(node));
      this.infix(out);
    }
    return out;
  }

  /** over 는 앞뒤를 받아 분수로 만든다 */
  infix(out) {
    const t = this.peek();
    if (!t || t.t !== "over") return;
    this.next();
    while (this.peek() && this.peek().t === "sp") this.next();
    const num = out.pop() || "<mrow/>";
    const den = this.scripts(this.atom() ?? "<mrow/>");
    out.push(`<mfrac>${wrap(num)}${wrap(den)}</mfrac>`);
  }

  /** 아래·위 첨자를 붙인다 */
  scripts(node) {
    let sub = null, sup = null;
    for (;;) {
      const t = this.peek();
      if (!t || (t.t !== "_" && t.t !== "^")) break;
      this.next();
      const v = this.atom();
      if (v === null || v === "") continue;           // _{} 처럼 빈 것은 버린다
      if (t.t === "_") sub = v; else sup = v;
    }
    if (sub && sup) return `<msubsup>${wrap(node)}${wrap(sub)}${wrap(sup)}</msubsup>`;
    if (sub) return `<msub>${wrap(node)}${wrap(sub)}</msub>`;
    if (sup) return `<msup>${wrap(node)}${wrap(sup)}</msup>`;
    return node;
  }

  atom() {
    const t = this.next();
    if (!t) return null;
    switch (t.t) {
      case "sp": return space(t.n) || null;
      case "num": return `<mn>${esc(t.v)}</mn>`;
      case "id": return mi(t.v);
      case "sym": return t.k === "i" ? `<mi>${esc(t.v)}</mi>` : `<mo>${esc(t.v)}</mo>`;
      case "op": return `<mo>${esc(t.v)}</mo>`;
      case "fence": return `<mo>${esc(t.v)}</mo>`;
      case "{": {
        const inner = this.seq((x) => x.t === "}");
        this.next();                                   // }
        return `<mrow>${inner.join("")}</mrow>`;
      }
      case "stack": return this.stack();
      case "sqrt": {
        const v = this.atom();
        return `<msqrt>${wrap(v ?? "<mrow/>")}</msqrt>`;
      }
      case "LEFT": return this.fenced();
      case "RIGHT": { this.next(); return null; }      // 짝 없는 RIGHT 는 버린다
      default: return null;
    }
  }

  /** eqalign{ a # b # c } — 줄을 쌓는다 */
  stack() {
    while (this.peek() && this.peek().t === "sp") this.next();
    if (!this.peek() || this.peek().t !== "{") return "<mrow/>";
    this.next();
    const rows = [[]];
    for (;;) {
      const t = this.peek();
      if (!t || t.t === "}") break;
      if (t.t === "#") { this.next(); rows.push([]); continue; }
      const node = this.atom();
      if (node === null) continue;
      const cur = rows[rows.length - 1];
      cur.push(this.scripts(node));
      this.infix(cur);
    }
    this.next();                                       // }
    const body = rows
      .filter((r) => r.join("").trim() !== "")
      .map((r) => `<mtr><mtd><mrow>${r.join("")}</mrow></mtd></mtr>`)
      .join("");
    return `<mtable columnalign="center">${body}</mtable>`;
  }

  /** LEFT [ … RIGHT ] — 괄호가 안쪽 높이만큼 늘어난다 */
  fenced() {
    while (this.peek() && this.peek().t === "sp") this.next();
    const o = this.peek();
    const open = o && (o.t === "fence" || o.t === "op") ? this.next().v : "";
    const inner = this.seq((x) => x.t === "RIGHT");
    let close = "";
    if (this.peek() && this.peek().t === "RIGHT") {
      this.next();
      while (this.peek() && this.peek().t === "sp") this.next();
      const c = this.peek();
      if (c && (c.t === "fence" || c.t === "op")) close = this.next().v;
    }
    // MathML 의 stretchy 는 mtable 둘레에서 늘어나지 않는 엔진이 있다.
    // 줄 수를 세어 괄호 글자를 그만큼 키운다.
    const body = inner.join("");
    const rows = (body.match(/<mtr>/g) || []).length;
    const fence = (ch) => {
      if (!ch || ch === ".") return "";
      const s = rows > 1 ? ` style="font-size:${(rows * 1.24).toFixed(2)}em"` : "";
      return `<mo stretchy="false"${s}>${esc(ch)}</mo>`;
    };
    return `<mrow>${fence(open)}${body}${fence(close)}</mrow>`;
  }
}

function wrap(x) {
  const s = String(x || "");
  return /^<m(row|table|frac|sqrt|sub|sup|subsup|i|n|o)\b/.test(s) ? s : `<mrow>${s}</mrow>`;
}

/**
 * 한글 수식 스크립트 → MathML
 * @param {string} script
 * @returns {string} <math> … </math> · 바꾸지 못하면 빈 글
 */
export function toMathML(script) {
  const src = String(script || "").trim();
  if (!src) return "";
  try {
    const p = new P(lex(src));
    // 맨 바깥의 # 는 줄바꿈이다 — 그림 하나에 여러 줄이 들어 있던 것을
    // 한 수식으로 모을 때 이 표로 잇는다 (scripts/genobjects.py)
    const rows = [[]];
    for (;;) {
      const t = p.peek();
      if (!t) break;
      if (t.t === "#") { p.next(); rows.push([]); continue; }
      const node = p.atom();
      if (node === null) continue;
      const cur = rows[rows.length - 1];
      cur.push(p.scripts(node));
      p.infix(cur);
    }
    const lines = rows.map((r) => r.join("")).filter((s) => s.trim());
    if (!lines.length) return "";
    const body = lines.length === 1 ? `<mrow>${lines[0]}</mrow>`
      : `<mtable columnalign="left">`
        + lines.map((s) => `<mtr><mtd><mrow>${s}</mrow></mtd></mtr>`).join("")
        + `</mtable>`;
    return `<math display="block" xmlns="http://www.w3.org/1998/Math/MathML">`
      + body + `</math>`;
  } catch {
    return "";                                         // 못 바꾸면 글로 보여 준다
  }
}
