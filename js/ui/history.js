/* ============================================================
   ui/history.js — 버전 전체 변경 이력 화면
   ============================================================ */

import { esc, fmtDT } from "./html.js?v=20260906j";
const KIND_CLASS = {
  "신설": "k-new", "삭제": "k-del", "이동": "k-mov", "순서": "k-mov",
  "수정": "k-edit", "통합": "k-mrg", "참조삽입": "k-ref", "상태변경": "k-keep",
  "되돌림": "k-undo", "다시실행": "k-redo",
};
const KINDS = ["신설", "이동", "순서", "수정", "참조삽입", "상태변경", "통합", "삭제", "되돌림", "다시실행"];

export class HistoryView {
  constructor(project, { onJump } = {}) {
    this.project = project;
    this.onJump = onJump;
    this.el = null;
    this.filter = { kind: "", q: "", hideCascade: true, versionId: null };
  }

  open() {
    if (this.el) this.close();
    this.el = document.createElement("div");
    this.el.className = "overlay";
    document.body.appendChild(this.el);
    this._esc = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._esc, true);
    this.el.addEventListener("click", (e) => { if (e.target === this.el) this.close(); });
    this.filter.versionId = this.project.currentId;
    this.render();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  render() {
    const p = this.project;
    const all = p.allHistory({ versionId: this.filter.versionId, limit: 2000 });
    const rows = all.filter((h) => {
      if (this.filter.hideCascade && h.cascade) return false;
      if (this.filter.kind && h.kind !== this.filter.kind) return false;
      if (this.filter.q) {
        const q = this.filter.q.toLowerCase();
        const hay = `${h.label} ${h.title} ${h.detail} ${h.by} ${h.path}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const counts = {};
    for (const h of all) if (!(this.filter.hideCascade && h.cascade)) counts[h.kind] = (counts[h.kind] || 0) + 1;

    this.el.innerHTML = `
<div class="cmp hist-view">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">변경 이력</div>
      <div class="cmp-sub">조문에 무엇을 언제 누가 했는지 시간 역순으로 봅니다. 줄을 누르면 해당 조문으로 이동합니다.</div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar">
    <div class="chips">
      <span class="chip total">전체 <b>${rows.length}</b></span>
      ${KINDS.filter((k) => counts[k]).map((k) =>
        `<span class="chip ${KIND_CLASS[k]} ${this.filter.kind === k ? "on" : ""}" data-kind="${k}">${k} <b>${counts[k]}</b></span>`).join("")}
      ${this.filter.kind ? `<span class="chip" data-kind="">필터 해제 ✕</span>` : ""}
    </div>
  </div>

  <div class="cmp-bar2">
    <label>버전
      <select id="hvVer">${p.versions.map((v) =>
        `<option value="${v.id}"${v.id === this.filter.versionId ? " selected" : ""}>${v.label}${v.title ? ` · ${v.title}` : ""}</option>`).join("")}</select>
    </label>
    <label><input type="checkbox" id="hvCascade" ${this.filter.hideCascade ? "checked" : ""}> 상위 항목과 함께 옮겨진 하위 조문 숨기기</label>
    <input id="hvQ" class="search" type="search" placeholder="조문·내용·작성자 검색" value="${esc(this.filter.q)}">
    <div class="spacer"></div>
    <button data-x="csv">CSV 내보내기</button>
    <button data-x="wipe" class="danger" title="시험 삼아 돌려 본 자취를 걷어 냅니다 — 되돌릴 수 없습니다">이력 비우기</button>
  </div>

  <div class="cmp-body">
    ${rows.length ? `<table id="hvTable">
      <thead><tr>
        <th style="width:132px">시각</th>
        <th style="width:82px">유형</th>
        <th style="width:150px">조문</th>
        <th>내용</th>
        <th style="width:110px">위치</th>
        <th style="width:88px">작성자</th>
      </tr></thead>
      <tbody>${rows.map((h) => `
        <tr data-node="${esc(h.nodeId)}">
          <td class="c mut">${fmtDT(h.at)}</td>
          <td class="c"><span class="tag ${KIND_CLASS[h.kind] || ""}">${esc(h.kind)}</span></td>
          <td><b>${esc(h.label)}</b>${h.title ? `<br><span class="mut">${esc(h.title)}</span>` : ""}</td>
          <td>${esc(h.detail || "")}${h.cascade ? ' <i class="mut">(상위와 함께)</i>' : ""}</td>
          <td class="mut">${esc(h.path)}</td>
          <td class="c mut">${esc(h.by || "—")}</td>
        </tr>`).join("")}</tbody>
    </table>` : `<div class="hv-none">해당하는 이력이 없습니다.</div>`}
  </div>
</div>`;

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.querySelector('[data-x="csv"]').onclick = () => this.exportCsv(rows);
    this.el.querySelector('[data-x="wipe"]').onclick = () => this.wipe();
    this.el.querySelector("#hvVer").onchange = (e) => { this.filter.versionId = e.target.value; this.render(); };
    this.el.querySelector("#hvCascade").onchange = (e) => { this.filter.hideCascade = e.target.checked; this.render(); };
    const q = this.el.querySelector("#hvQ");
    q.oninput = () => {
      this.filter.q = q.value;
      const pos = q.selectionStart;
      this.render();
      const n = this.el.querySelector("#hvQ");
      n.focus(); n.setSelectionRange(pos, pos);
    };
    this.el.querySelectorAll("[data-kind]").forEach((c) => {
      c.onclick = () => { this.filter.kind = c.dataset.kind; this.render(); };
    });
    this.el.querySelectorAll("#hvTable tbody tr").forEach((tr) => {
      tr.onclick = () => {
        const id = tr.dataset.node;
        this.close();
        this.onJump?.(id, this.filter.versionId);
      };
    });
  }

  /**
   * 변경 이력 비우기 — 시험 삼아 돌려 본 자취를 걷어 낸다.
   * 되돌릴 수 없으므로 먼저 묻고, 무엇이 지워지는지 세어 보인다.
   */
  wipe() {
    const p = this.project;
    const nEv = p.versions.reduce((a, v) => a + ((v.events || []).length), 0);
    const ask = [
      "변경 이력을 비웁니다.", "",
      `  판마다의 이력  ${nEv}건`,
      `  작업 기록      ${(p._log || []).length}건`,
      "  조문마다 달린 이력도 함께 지웁니다.", "",
      "되돌릴 수 없습니다. 조문 본문과 개정안은 그대로 남습니다.",
    ].join("\n");
    if (!confirm(ask)) return;
    const r = p.clearHistory();
    this.close();
    this.open();
    alert(`이력을 비웠습니다 — 이력 ${r.events}건 · 조문 ${r.nodes}개 · 작업 기록 ${r.log}건`);
  }

  exportCsv(rows) {
    const head = ["시각", "유형", "조문", "제목", "내용", "위치", "작성자", "버전"];
    const esc2 = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const body = rows.map((h) =>
      [fmtDT(h.at), h.kind, h.label, h.title, h.detail, h.path, h.by, h.v].map(esc2).join(","));
    const csv = "﻿" + [head.map(esc2).join(","), ...body].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const d = new Date();
    a.href = url;
    a.download = `변경이력_${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
}

