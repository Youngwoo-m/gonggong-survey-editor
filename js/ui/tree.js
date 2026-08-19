/* ============================================================
   ui/tree.js — 트리 렌더링 + 드래그 앤 드롭
   ============================================================ */
import * as M from "../core/model.js?v=20260823d";

const INDENT = 15;

export class TreeView {
  /**
   * @param {HTMLElement} el
   * @param {object} opts
   *   editable   : 드래그로 구조 변경 가능 여부
   *   dragSource : 다른 트리로 끌어낼 수 있는지
   *   onSelect(id), onToggle(id), onMove(dragId,targetId,pos), onExternalDrop(payload,targetId,pos)
   */
  constructor(el, opts = {}) {
    this.el = el;
    this.opts = Object.assign({ editable: false, dragSource: false }, opts);
    this.nodes = [];
    this.selectedId = null;
    this.highlight = new Set();
    this.filter = null;              // 노드로 거르기 (setFilter)
    this._drag = null;
    this._bind();
  }

  setData(nodes, selectedId) {
    this.nodes = nodes || [];
    this.selectedId = selectedId ?? this.selectedId;
    this.render();
  }
  setSelected(id) { this.selectedId = id; this.render(); }
  setHighlight(ids) { this.highlight = new Set(ids || []); this.render(); }

  /**
   * 상태로 걸러 본다 — 고른 상태의 조문과 그 위 편·장만 보인다.
   * @param {(status:string)=>boolean|null} fn 없으면 거르지 아니한다
   */
  setFilter(fn) { this.filter = fn || null; this.render(); }

  /** 이 가지 안에 걸린 조문이 있는가 */
  _hit(n) {
    if (this.filter(n)) return true;   // 상태 말고도 볼 것이 있다 (용어 수정 등)
    return (n.children || []).some((c) => this._hit(c));
  }

  render() {
    const scroll = this.el.scrollTop;
    const frag = document.createDocumentFragment();
    const build = (list, depth) => {
      for (const n of list) {
        if (this.filter) {
          if (!this._hit(n)) continue;
          frag.appendChild(this._row(n, depth));
          build(n.children || [], depth + 1);   // 거를 때에는 접힘을 무시하고 펼쳐 보인다
          continue;
        }
        frag.appendChild(this._row(n, depth));
        if (n.children.length && !n.collapsed) build(n.children, depth + 1);
      }
    };
    build(this.nodes, 0);
    this.el.replaceChildren(frag);
    this.el.scrollTop = scroll;
  }

  scrollToSelected() {
    const r = this.el.querySelector(".node.sel");
    if (r) r.scrollIntoView({ block: "nearest" });
  }

  /** 특정 노드를 화면 가운데로 */
  scrollToId(id, { center = true } = {}) {
    const r = this.el.querySelector(`.node[data-id="${CSS.escape(id)}"]`);
    if (!r) return false;
    r.scrollIntoView({ block: center ? "center" : "nearest" });
    r.classList.add("flash");
    setTimeout(() => r.classList.remove("flash"), 900);
    return true;
  }

  _row(n, depth) {
    const row = document.createElement("div");
    row.className = `node lv-${n.level}`;
    row.dataset.id = n.id;
    row.style.paddingLeft = `${8 + depth * INDENT}px`;
    row.style.setProperty("--ind", `${8 + depth * INDENT + 14}px`);
    if (n.id === this.selectedId) row.classList.add("sel");
    if (this.highlight.has(n.id)) row.classList.add("hit");

    const tw = document.createElement("span");
    tw.className = "tw" + (n.children.length ? "" : " leaf");
    tw.textContent = n.children.length ? (n.collapsed ? "▶" : "▼") : "·";
    tw.dataset.role = "twisty";
    row.appendChild(tw);

    const no = document.createElement("span");
    no.className = "no";
    // 별표·부록·목차 항목은 자체 번호 표기를 쓴다
    if (n.annexRef) { no.textContent = M.displayLabel(n); no.classList.add("anx"); }
    else if (n.isAnnex || n.isAppendix) { no.textContent = ""; no.classList.add("anx"); }
    else if (n.outlineNo) { no.textContent = n.outlineNo; no.classList.add("onum"); }
    else no.textContent = M.shortLabel(n);
    row.appendChild(no);
    if (n.isAnnex || n.annexRef || n.isAppendix) row.classList.add("anx-row");

    const mode = this.opts.displayMode || "orig";
    const plain = n.annexRef || n.isAnnex || n.isAppendix || n.outlineNo;
    const wrapTitle = (s) => (n.level === "조" && !plain ? `(${s || "제목없음"})` : (s || ""));
    const tt = document.createElement("span");
    tt.className = "tt";
    if (mode !== "orig" && n.transTitle) {
      if (mode === "trans") tt.textContent = wrapTitle(n.transTitle);
      else {
        tt.classList.add("bi");
        const a = document.createElement("span");
        a.className = "t-o"; a.textContent = wrapTitle(n.title);
        const b = document.createElement("span");
        b.className = "t-t"; b.textContent = wrapTitle(n.transTitle);
        tt.append(a, b);
        row.classList.add("bi-row");
      }
    } else {
      tt.textContent = wrapTitle(n.title);
    }
    row.appendChild(tt);

    if (n.status && n.status !== "유지") {
      const b = document.createElement("span");
      b.className = `badge b-${n.status}`;
      b.textContent = n.status;
      row.appendChild(b);
    }
    if (n.sourceRef) {
      const b = document.createElement("span");
      b.className = "badge b-참조";
      b.textContent = "참조";
      b.title = `${n.sourceRef.doc} ${n.sourceRef.label}`;
      row.appendChild(b);
    }

    if (this.opts.editable || this.opts.dragSource) row.draggable = true;
    if (this.opts.readonlyHint) row.title = this.opts.readonlyHint;
    return row;
  }

  _rowOf(t) { return t && t.closest ? t.closest(".node") : null; }

  _bind() {
    const el = this.el;

    el.addEventListener("click", (e) => {
      const row = this._rowOf(e.target);
      if (!row) return;
      if (e.target.dataset.role === "twisty") { this.opts.onToggle?.(row.dataset.id); return; }
      this.selectedId = row.dataset.id;
      this.opts.onSelect?.(row.dataset.id);
    });

    el.addEventListener("dblclick", (e) => {
      const row = this._rowOf(e.target);
      if (!row) return;
      // 두 번 누름을 따로 받는 곳이 있으면 그쪽에 넘기고, 없으면 펴고 접는다
      if (this.opts.onDblSelect) this.opts.onDblSelect(row.dataset.id);
      else this.opts.onToggle?.(row.dataset.id);
    });

    if (!(this.opts.editable || this.opts.dragSource)) return;

    el.addEventListener("dragstart", (e) => {
      const row = this._rowOf(e.target);
      if (!row) return;
      if (!this.opts.editable && !this.opts.dragSource) { e.preventDefault(); return; }
      this._drag = row.dataset.id;
      row.classList.add("dragging");
      e.dataTransfer.effectAllowed = "copyMove";
      const payload = JSON.stringify({
        kind: this.opts.dragSource ? "external" : "internal",
        source: this.opts.sourceName || "",
        id: row.dataset.id,
      });
      e.dataTransfer.setData("text/plain", payload);
      e.dataTransfer.setData("application/x-pmnode", payload);
    });

    el.addEventListener("dragend", () => {
      this._drag = null;
      el.querySelectorAll(".dragging").forEach((r) => r.classList.remove("dragging"));
      this._clearMarks();
    });

    if (!this.opts.editable) return;

    el.addEventListener("dragover", (e) => {
      const row = this._rowOf(e.target);
      this._clearMarks();
      if (!row || !this.opts.editable) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const pos = this._posFor(row, e.clientY);
      row.classList.add(pos === "into" ? "drop-into" : `drop-${pos}`);
    });

    el.addEventListener("dragleave", (e) => {
      if (!el.contains(e.relatedTarget)) this._clearMarks();
    });

    el.addEventListener("drop", (e) => {
      e.preventDefault();
      const row = this._rowOf(e.target);
      this._clearMarks();
      if (!row || !this.opts.editable) return;
      const pos = this._posFor(row, e.clientY);
      let payload = null;
      try { payload = JSON.parse(e.dataTransfer.getData("application/x-pmnode") || e.dataTransfer.getData("text/plain")); }
      catch { return; }
      if (!payload) return;
      if (payload.kind === "internal") this.opts.onMove?.(payload.id, row.dataset.id, pos);
      else this.opts.onExternalDrop?.(payload, row.dataset.id, pos);
    });
  }

  /** 행 안에서의 세로 위치로 before / into / after 판정 */
  _posFor(row, clientY) {
    const r = row.getBoundingClientRect();
    const rel = (clientY - r.top) / r.height;
    if (rel < 0.3) return "before";
    if (rel > 0.7) return "after";
    return "into";
  }

  _clearMarks() {
    this.el.querySelectorAll(".drop-before,.drop-after,.drop-into")
      .forEach((r) => r.classList.remove("drop-before", "drop-after", "drop-into"));
  }
}
