/* ============================================================
   ui/terms.js — 용어 통일 결과 창
   ------------------------------------------------------------
   법제처 법령안편집기의 '용어검사' 에 해당한다.

   여태까지는 브라우저의 confirm() 하나로 물었다. 줄글로 몰아 적으니
   무엇이 어디서 어떻게 바뀌는지 보이지 않고, 브라우저가 대화상자를
   막아 둔 자리에서는 눌러도 아무 일이 없는 것처럼 보였다.
   그래서 인용 검사와 같은 결과 창으로 바꾼다.

     ▷ 규칙마다 몇 곳인지 칩으로 보이고, 눌러 걸러 본다
     ▷ 조문마다 무엇이 무엇으로 바뀌는지 낱낱이 보인다
     ▷ 줄을 누르면 그 조문으로 간다
     ▷ 규칙을 골라 그것만 맞출 수 있다 (체크를 끄면 뺀다)

   판정과 고침은 core/xrefs.js · core/project.js 가 한다.
   여기는 보이고 고르게 하는 일만 한다.
   ============================================================ */

import { esc } from "./html.js?v=20260907u";

export class TermsView {
  constructor(opts = {}) {
    this.onJump = opts.onJump || null;
    this.onApply = opts.onApply || null;   // (canons:string[]) => {count, nodes}
    this.el = null;
    this.only = "";                        // "" 전체 · 규칙 이름 하나
    this.picked = new Set();               // 맞출 규칙
  }

  /**
   * @param {object} dry   project.unifyTerms({dryRun:true}) 의 결과
   * @param {Array}  rules TERM_RULES (근거·표준용어집 정보를 여기서 읽는다)
   */
  open(dry, rules) {
    this.dry = dry || { count: 0, nodes: 0, byRule: {}, plan: [] };
    this.rules = rules || [];
    this.picked = new Set(Object.keys(this.dry.byRule));
    if (this.el) this.close();

    this.el = document.createElement("div");
    this.el.className = "overlay";
    this.el.innerHTML = this._shell();
    document.body.appendChild(this.el);

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.addEventListener("click", (e) => { if (e.target === this.el) this.close(); });
    this._esc = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._esc, true);

    this.el.querySelectorAll("[data-flt]").forEach((b) => {
      b.onclick = () => {
        this.only = b.dataset.flt;
        this.el.querySelectorAll("[data-flt]").forEach((x) => x.classList.toggle("on", x === b));
        this._paint();
      };
    });
    this.el.querySelectorAll("[data-pick]").forEach((c) => {
      c.onchange = () => {
        if (c.checked) this.picked.add(c.dataset.pick); else this.picked.delete(c.dataset.pick);
        this._paint();
        this._syncGo();
      };
    });
    this.el.querySelector("#tmBody").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-node]");
      if (tr && this.onJump) { this.onJump(tr.dataset.node); this.close(); }
    });
    this.el.querySelector('[data-x="go"]').onclick = () => {
      if (!this.picked.size || !this.onApply) return;
      const r = this.onApply([...this.picked]);
      this.close();
      return r;
    };
    this._paint();
    this._syncGo();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  /** 맞출 곳을 센다 — 고른 규칙만 세되, 걸러 보기는 셈에 넣지 않는다.
      거르기는 눈으로 보려는 것일 뿐, 맞추는 것은 고른 규칙 모두이다. */
  _pickedCount() {
    let hits = 0;
    const nodes = new Set();
    for (const f of this.dry.plan || []) {
      const n = (f.samples || []).filter((s) => this.picked.has(s.canon)).length;
      if (n) { hits += n; nodes.add(f.node.id); }
    }
    return { hits, nodes: nodes.size };
  }

  /** 지금 보일 고침들 — 규칙 고르기와 칩 거르기를 함께 건다 */
  _rows() {
    const out = [];
    for (const f of this.dry.plan || []) {
      const samples = (f.samples || []).filter((s) =>
        this.picked.has(s.canon) && (!this.only || s.canon === this.only));
      if (samples.length) out.push({ ...f, samples, hits: samples.length });
    }
    return out;
  }

  _ruleOf(canon) {
    return this.rules.find((r) => r.canon === canon) || null;
  }

  _shell() {
    const by = this.dry.byRule || {};
    const chips = Object.entries(by).map(([canon, n]) => {
      const r = this._ruleOf(canon);
      /* <label> 로 감싸면 걸러 보려고 글자를 눌렀을 때 체크까지 꺼진다 —
         고르기(체크)와 거르기(글자)는 하는 일이 다르므로 갈라 둔다 */
      return `<span class="chip tm-pick" title="${esc(r?.note || "")}">
        <input type="checkbox" data-pick="${esc(canon)}" checked
               title="이 말을 맞출지 고릅니다" />
        <span data-flt="${esc(canon)}" title="이 말만 걸러 봅니다">${
          esc(r?.label || canon)} <b>${n}</b>곳</span>
      </span>`;
    }).join("");
    return `
<div class="cmp tm">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">용어 통일</div>
      <div class="cmp-sub">규정 사이에서 갈린 말을 정한 말로 맞춥니다 —
        <b>${this.dry.count}</b>곳 · 조문 <b>${this.dry.nodes}</b>개</div>
      <div class="cmp-sub">고친 조문마다 <b>변경 사유</b>에 근거를 남깁니다 —
        현행 고시 명칭과 국가공간정보 표준용어집 인용표준번호(KS X ISO).
        그 사유가 그대로 개정사유서와 신구대조표 비고란으로 갑니다.</div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>
  <div class="cmp-bar">
    <div class="chips">
      <button class="chip total on" data-flt="">전체 <b>${this.dry.count}</b></button>
      ${chips}
    </div>
    <span class="hint">체크를 끄면 그 말은 그대로 둡니다 · 줄을 누르면 그 조문으로 갑니다</span>
  </div>
  <div class="cmp-body"><table id="tmBody" class="tm-tbl"></table></div>
  <div class="cmp-bar2">
    <span class="hint" id="tmGoNote"></span>
    <button class="primary" data-x="go" style="margin-left:auto">맞추기</button>
    <button data-x="close">닫기</button>
  </div>
</div>`;
  }

  _syncGo() {
    const { hits, nodes } = this._pickedCount();
    const go = this.el.querySelector('[data-x="go"]');
    go.disabled = !hits;
    go.textContent = hits ? `${hits}곳 맞추기` : "맞출 것 없음";
    this.el.querySelector("#tmGoNote").textContent = hits
      ? `조문 ${nodes}개를 고칩니다 — 되돌리려면 Ctrl+Z.`
      : "규칙을 하나 이상 고르십시오.";
    this.el.querySelectorAll('[data-x="close"]').forEach((b) => { b.onclick = () => this.close(); });
  }

  _paint() {
    const rows = this._rows();
    const head = `<thead><tr>
      <th style="width:132px">규정</th>
      <th style="width:120px">조문</th>
      <th style="width:64px">자리</th>
      <th>바꾸는 말</th>
      <th style="width:38%">근거</th>
    </tr></thead>`;
    const body = this.el.querySelector("#tmBody");
    if (!rows.length) {
      body.innerHTML = head
        + `<tbody><tr><td colspan="5" class="none">맞출 말이 없습니다.</td></tr></tbody>`;
      return;
    }
    const html = rows.map((f) => {
      // 같은 말끼리 묶어 적는다 — 한 조문에서 같은 말이 여러 번 나오는 일이 잦다
      const pairs = new Map();
      for (const s of f.samples) {
        const k = `${s.from} → ${s.to}`;
        pairs.set(k, (pairs.get(k) || 0) + 1);
      }
      const what = [...pairs].map(([k, n]) => {
        const [from, to] = k.split(" → ");
        return `<span class="tm-w"><s>${esc(from)}</s> → <b>${esc(to)}</b>`
          + (n > 1 ? ` <i>${n}곳</i>` : "") + `</span>`;
      }).join("");
      const canons = [...new Set(f.samples.map((s) => s.canon))];
      const basis = canons.map((c) => {
        const r = this._ruleOf(c);
        if (!r) return esc(c);
        return `<div class="tm-b">「${esc(r.label || r.canon)}」 ${esc(r.basis)}`
          + (r.std ? ` · 표준용어집 ‘${esc(r.std.ko)}’ (${esc(r.std.no)})`
                   : " · 표준용어집에 항목 없음")
          + (r.note ? `<div class="tm-n">${esc(r.note)}</div>` : "")
          + `</div>`;
      }).join("");
      return `<tr data-node="${esc(f.node.id)}">
        <td class="c">${esc(f.reg.title || "")}</td>
        <td>${esc(shortOf(f.node))}</td>
        <td class="c">${f.field === "title" ? "제목" : "본문"}</td>
        <td>${what}</td>
        <td class="note">${basis}</td>
      </tr>`;
    }).join("");
    body.innerHTML = head + `<tbody>${html}</tbody>`;
  }
}

/* 트리의 짧은 이름 — model.js 를 끌어오지 않으려고 여기서 짓는다 */
function shortOf(n) {
  if (!n) return "";
  const no = n.no ? `제${n.no}${n.level || "조"}${n.branch ? `의${n.branch}` : ""}` : "";
  return `${no}${n.title ? `(${n.title})` : ""}`.trim() || (n.title || n.id || "");
}

