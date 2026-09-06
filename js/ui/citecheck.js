/* ============================================================
   ui/citecheck.js — 피인용조문 검색 화면
   ------------------------------------------------------------
   이 규정이 부르는 남의 조문이 아직 성한지 훑어 보인다.
   판정은 core/citecheck.js 가 하고, 여기는 보이고 짚어 주기만 한다.
   ============================================================ */
import { GRADES } from "../core/citecheck.js?v=20260907p";
import { esc } from "./html.js?v=20260907p";

const CLS = { [GRADES.OK]: "g-ok", [GRADES.MUST]: "g-must", [GRADES.CHECK]: "g-check" };

export class CiteCheckView {
  constructor(opts = {}) {
    this.onJump = opts.onJump || null;      // 우리 조문으로 가기
    this.onOpenRef = opts.onOpenRef || null; // 그 규정을 참조 창에 띄우기
    this.el = null;
    this.rows = [];
    this.only = "";                          // "" 전체 · 등급 하나
  }

  open(rows, info = {}) {
    this.rows = rows || [];
    this.info = info;
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
    this.el.querySelector("#ccBody").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-node]");
      if (tr && this.onJump) { this.onJump(tr.dataset.node); this.close(); return; }
      const a = e.target.closest("[data-reg]");
      if (a && this.onOpenRef) { this.onOpenRef(a.dataset.reg); }
    });
    this._paint();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  _counts() {
    const c = { 총: this.rows.length };
    for (const g of Object.values(GRADES)) c[g] = this.rows.filter((r) => r.grade === g).length;
    return c;
  }

  _shell() {
    const c = this._counts();
    const chip = (g) => `<button class="chip ${CLS[g]}" data-flt="${g}">${g} <b>${c[g]}</b></button>`;
    return `
<div class="cmp cc">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">피인용조문 검색</div>
      <div class="cmp-sub">${esc(this.info.regName || "")} 이(가) 부르는 남의 조문이 성한지 봅니다</div>
      <div class="cmp-sub">라이브러리 ${this.info.indexed || 0}종의 조문을 잣대로 삼았습니다 —
        색인이 없는 규정은 '확인필요' 로 남깁니다.</div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>
  <div class="cmp-bar">
    <div class="chips">
      <button class="chip total on" data-flt="">전체 <b>${c.총}</b></button>
      ${chip(GRADES.MUST)}${chip(GRADES.CHECK)}${chip(GRADES.OK)}
    </div>
    <span class="hint">줄을 누르면 그 조문으로 갑니다</span>
  </div>
  <div class="cmp-body"><table id="ccBody" class="cc-tbl"></table></div>
</div>`;
  }

  _paint() {
    const rows = this.only ? this.rows.filter((r) => r.grade === this.only) : this.rows;
    const head = `<thead><tr>
      <th style="width:96px">판정</th>
      <th style="width:92px">우리 조문</th>
      <th style="width:30%">인용</th>
      <th>살펴볼 것</th>
    </tr></thead>`;
    if (!rows.length) {
      this.el.querySelector("#ccBody").innerHTML =
        head + `<tbody><tr><td colspan="4" class="none">해당하는 인용이 없습니다.</td></tr></tbody>`;
      return;
    }
    const body = rows.map((r) => `
      <tr data-node="${esc(r.node.id)}" class="${CLS[r.grade]}">
        <td class="c"><span class="tag ${CLS[r.grade]}">${esc(r.grade)}</span></td>
        <td class="c">${esc(r.label)}</td>
        <td><span class="cc-raw">${esc(r.raw)}</span>${
          r.reg ? `<div class="cc-reg" data-reg="${esc(r.reg.id)}">${esc(r.reg.name)}</div>` : ""}</td>
        <td class="note">${esc(r.why || "")}</td>
      </tr>`).join("");
    this.el.querySelector("#ccBody").innerHTML = head + `<tbody>${body}</tbody>`;
  }
}

