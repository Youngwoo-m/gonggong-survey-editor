/* ============================================================
   ui/versions.js — 버전 관리 화면 (목록 · 계보 · 생성/전환/삭제)
   ============================================================ */
import * as M from "../core/model.js?v=20260906f";
import { esc } from "./html.js?v=20260906f";

export class VersionsView {
  constructor(project, { onCompare } = {}) {
    this.project = project;
    this.onCompare = onCompare;
    this.el = null;
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
    this.el.innerHTML = `
<div class="cmp vers">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">버전 관리</div>
      <div class="cmp-sub">전부개정(안)을 여러 개 만들어 나란히 검토합니다. 기준(현행)은 읽기 전용입니다.</div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar2">
    <button class="primary" data-x="new">현재 버전에서 분기 (＋ 새 버전)</button>
    <span class="hint">현재: <b>${esc(p.current?.label || "-")}</b> ${esc(p.current?.title || "")}</span>
    <div class="spacer"></div>
    <button data-x="compare">이 두 버전 비교하기</button>
  </div>

  <div class="vers-body">
    ${this._tree()}
    ${this._table()}
  </div>
</div>`;

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.querySelector('[data-x="new"]').onclick = () => this._newVersion();
    this.el.querySelector('[data-x="compare"]').onclick = () => {
      const a = this.el.querySelector("#vCmpFrom").value;
      const b = this.el.querySelector("#vCmpTo").value;
      this.close();
      this.onCompare?.(a, b);
    };

    this.el.querySelectorAll("[data-act]").forEach((btn) => {
      btn.onclick = () => this._act(btn.dataset.act, btn.dataset.id);
    });
    this.el.querySelectorAll("[data-edit]").forEach((inp) => {
      inp.onchange = () => this.project.updateVersion(inp.dataset.id, { [inp.dataset.edit]: inp.value.trim() });
    });
  }

  /* ---------- 계보 ---------- */
  _tree() {
    const p = this.project;
    const roots = p.versions.filter((v) => !v.parentId || !p.version(v.parentId));
    const rec = (v, depth) => {
      const kids = p.childrenOf(v.id);
      const cur = v.id === p.currentId;
      const st = M.stats(v.tree);
      return `<div class="vnode${cur ? " cur" : ""}" style="margin-left:${depth * 26}px">
          <span class="vdot ${v.readonly ? "ro" : cur ? "on" : ""}"></span>
          <span class="vlab">${esc(v.label)}</span>
          <span class="vtit">${esc(v.title || "")}</span>
          <span class="vst">편 ${st.편} · 장 ${st.장} · 조 ${st.조}</span>
          ${cur ? `<span class="tag k-mov">현재</span>` : ""}
          ${v.readonly ? `<span class="tag k-keep">읽기 전용</span>` : ""}
        </div>` + kids.map((k) => rec(k, depth + 1)).join("");
    };
    return `<div class="vers-tree"><div class="vers-h">버전 계보</div>${roots.map((r) => rec(r, 0)).join("")}</div>`;
  }

  /* ---------- 목록 ---------- */
  _table() {
    const p = this.project;
    const opts = (sel) => p.versions
      .map((v) => `<option value="${v.id}"${v.id === sel ? " selected" : ""}>${esc(v.label)} — ${esc(v.title || "")}</option>`)
      .join("");

    const rows = p.versions.map((v) => {
      const st = M.stats(v.tree);
      const cur = v.id === p.currentId;
      return `<tr class="${cur ? "cur" : ""}">
        <td class="c"><b>${esc(v.label)}</b>${cur ? `<br><span class="tag k-mov">현재</span>` : ""}</td>
        <td><input data-edit="title" data-id="${v.id}" value="${esc(v.title || "")}" ${v.readonly ? "readonly" : ""}></td>
        <td class="c">${esc(p.version(v.parentId)?.label || "—")}</td>
        <td class="c">편 ${st.편}<br>장 ${st.장}</td>
        <td class="c">조 ${st.조}<br><span class="mut">변경 ${st.변경}</span></td>
        <td class="c mut">${fmtDT(v.createdAt)}</td>
        <td><input data-edit="note" data-id="${v.id}" value="${esc(v.note || "")}" placeholder="메모" ${v.readonly ? "readonly" : ""}></td>
        <td class="c nowrap">
          ${cur ? "" : `<button data-act="switch" data-id="${v.id}">전환</button>`}
          <button data-act="branch" data-id="${v.id}">분기</button>
          ${v.readonly ? "" : `<button data-act="del" data-id="${v.id}" class="danger">삭제</button>`}
        </td>
      </tr>`;
    }).join("");

    const base = p.base?.id || p.versions[0]?.id;
    return `<div class="vers-list">
      <table>
        <thead><tr>
          <th style="width:70px">버전</th><th>설명</th><th style="width:66px">분기원</th>
          <th style="width:60px">편·장</th><th style="width:74px">조·변경</th>
          <th style="width:104px">만든 시각</th><th style="width:22%">메모</th><th style="width:150px">작업</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="vers-cmp">
        <span>비교:</span>
        <select id="vCmpFrom">${opts(base)}</select>
        <span>↔</span>
        <select id="vCmpTo">${opts(p.currentId)}</select>
      </div>
    </div>`;
  }

  /* ---------- 동작 ---------- */
  _newVersion() {
    const title = prompt("새 버전 설명을 입력하세요.", `${this.project.current?.label || ""} 에서 분기`);
    if (title === null) return;
    this.project.createVersion({ title: title.trim() });
    this.render();
  }

  _act(act, id) {
    const p = this.project;
    const v = p.version(id);
    if (act === "switch") { p.switchVersion(id); this.render(); }
    else if (act === "branch") {
      const title = prompt("새 버전 설명을 입력하세요.", `${v.label} 에서 분기`);
      if (title === null) return;
      p.createVersion({ fromId: id, title: title.trim() });
      this.render();
    } else if (act === "del") {
      if (!confirm(`버전 ${v.label} (${v.title || ""}) 을(를) 삭제합니다.\n되돌릴 수 없습니다. 계속할까요?`)) return;
      p.deleteVersion(id);
      this.render();
    }
  }
}

function fmtDT(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const p2 = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${p2(d.getMonth() + 1)}.${p2(d.getDate())}<br>${p2(d.getHours())}:${p2(d.getMinutes())}`;
}
