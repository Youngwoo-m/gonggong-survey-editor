/* ============================================================
   ui/validate.js — 정합성 검증 결과 화면
   ============================================================ */
import { validate } from "../core/validate.js?v=20260820h";
import { esc } from "./html.js?v=20260820h";

const CLS = { "오류": "k-del", "경고": "k-edit", "정보": "k-keep" };

export class ValidateView {
  constructor(project, { onJump } = {}) {
    this.project = project;
    this.onJump = onJump;
    this.el = null;
    this.filter = "";
    this.result = null;
  }

  /** 화면 없이 결과만 (상태바·게이트용) */
  run(versionId = null) {
    this.result = validate(this.project, { versionId });
    return this.result;
  }

  open() {
    if (this.el) this.close();
    this.el = document.createElement("div");
    this.el.className = "overlay";
    document.body.appendChild(this.el);
    this._esc = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._esc, true);
    this.el.addEventListener("click", (e) => { if (e.target === this.el) this.close(); });
    this.render();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  render() {
    const p = this.project;
    const { items, summary } = this.run();
    const rows = this.filter ? items.filter((i) => i.level === this.filter) : items;

    this.el.innerHTML = `
<div class="cmp vld">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">정합성 검증</div>
      <div class="cmp-sub">
        <b>${esc(p.current?.label || "")}</b> ${esc(p.current?.title || "")}
        &nbsp;|&nbsp; 구조를 바꾸면 규정은 쉽게 깨집니다. 내보내기 전에 확인하세요.
      </div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar">
    <div class="chips">
      <span class="chip ${this.filter === "" ? "on" : ""}" data-f="">전체 <b>${summary.총}</b></span>
      <span class="chip k-del ${this.filter === "오류" ? "on" : ""}" data-f="오류">오류 <b>${summary.오류}</b></span>
      <span class="chip k-edit ${this.filter === "경고" ? "on" : ""}" data-f="경고">경고 <b>${summary.경고}</b></span>
      <span class="chip ${this.filter === "정보" ? "on" : ""}" data-f="정보">정보 <b>${summary.정보}</b></span>
      ${summary.오류 === 0
        ? `<span class="vld-ok">오류 없음 — 내보낼 수 있습니다</span>`
        : `<span class="vld-bad">오류 ${summary.오류}건 — 먼저 고쳐 주세요</span>`}
    </div>
  </div>

  <div class="cmp-bar2">
    <span class="hint">줄을 누르면 해당 조문으로 이동합니다</span>
    <div class="spacer"></div>
    <button data-x="rerun">다시 검사</button>
    <button data-x="csv">CSV 내보내기</button>
  </div>

  <div class="cmp-body">${
    rows.length ? `<table class="vld-table">
      <thead><tr>
        <th style="width:62px">구분</th><th style="width:34%">항목</th>
        <th>내용</th><th style="width:190px">위치</th>
      </tr></thead>
      <tbody>${rows.map((r, i) => `
        <tr data-i="${i}" class="${r.nodeId ? "jump" : ""}">
          <td class="c"><span class="tag ${CLS[r.level]}">${r.level}</span></td>
          <td><b>${esc(r.title)}</b><br><span class="mut">${esc(r.code)}</span></td>
          <td>${esc(r.detail)}</td>
          <td class="mut">${esc(r.path || "—")}</td>
        </tr>`).join("")}</tbody>
    </table>`
    : `<div class="vld-none">${summary.총 === 0
        ? "확인된 문제가 없습니다."
        : "해당 구분에 항목이 없습니다."}</div>`}
  </div>
</div>`;

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.querySelector('[data-x="rerun"]').onclick = () => this.render();
    this.el.querySelector('[data-x="csv"]').onclick = () => this.exportCsv(items);
    this.el.querySelectorAll("[data-f]").forEach((c) => {
      c.onclick = () => { this.filter = c.dataset.f; this.render(); };
    });
    this.el.querySelectorAll("tr.jump").forEach((tr) => {
      tr.onclick = () => {
        const r = rows[+tr.dataset.i];
        if (!r.nodeId) return;
        this.close();
        this.onJump?.(r.nodeId);
      };
    });
  }

  exportCsv(items) {
    const q = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const csv = "﻿" + [
      ["구분", "코드", "항목", "내용", "위치"].map(q).join(","),
      ...items.map((r) => [r.level, r.code, r.title, r.detail, r.path].map(q).join(",")),
    ].join("\r\n");
    const d = new Date();
    const name = `정합성검증_${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}.csv`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
}

