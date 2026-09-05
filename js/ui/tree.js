/* ============================================================
   ui/tree.js — 트리 렌더링 + 드래그 앤 드롭
   ============================================================ */
import * as M from "../core/model.js?v=20260904n";

/* 상태 이름 → CSS 클래스에 쓸 이름. 가운데점은 클래스에 못 쓴다. */
const statusKey = (s) => String(s || "").replace(/[^가-힣A-Za-z0-9]/g, "");

const STATUS_HINT = {
  "신설": "현행에 없던 조문을 새로 둔 것입니다.",
  "수정": "자리는 그대로 두고 문언을 고친 것입니다.",
  "이동": "문언은 그대로 두고 자리만 옮긴 것입니다.",
  "이동·수정": "자리를 옮기고 문언도 고친 것입니다.",
  "삭제": "현행 조문을 없앤 것입니다.",
  "통합": "여러 조문을 하나로 합친 것입니다.",
  "통합·신설": "흩어져 있던 현행 조문 여럿을 합쳐 새 조문으로 둔 것입니다.",
};

const INDENT = 15;

/** 같은 마디를 이 사이 안에 다시 누르면 두 번 누른 것으로 본다 (밀리초) */
const DBL_MS = 420;

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
      /* 클래스 이름에는 가운데점을 넣지 아니한다. '이동·수정' 이 그대로
         클래스가 되면 CSS 가 그것을 집지 못해 배지가 흰 글자만 남아
         보이지 않았다 — statusKey 가 기호를 걷어 낸다. */
      /* 여러 조문을 합쳐 새로 둔 것은 「통합·신설」 로 적는다. 상태는
         「신설」 그대로 두고 유래(origin)만 따로 지녀, 신설을 세는 자리와
         개정문을 짓는 자리가 그대로 돌게 한다 (model.js 의 statusLabel). */
      const label = M.statusLabel(n);
      b.className = `badge b-${statusKey(label)}`;
      b.textContent = label;
      b.title = STATUS_HINT[label] || STATUS_HINT[n.status] || label;
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

    /* 두 번 누름을 여기에서 센다 —— 브라우저의 dblclick 을 쓰지 아니한다.
       한 번 누를 때마다 트리를 다시 그리므로(setSelected → render) 두 번째
       누름이 첫 번째와 다른 요소에 떨어져, 브라우저가 dblclick 을 내지
       아니한다. 같은 마디를 짧은 사이에 두 번 누른 것으로 갈음한다. */
    el.addEventListener("click", (e) => {
      const row = this._rowOf(e.target);
      if (!row) return;
      if (e.target.dataset.role === "twisty") { this.opts.onToggle?.(row.dataset.id); return; }
      const id = row.dataset.id;
      const now = Date.now();
      const twice = this._lastId === id && now - this._lastAt < DBL_MS;
      this._lastId = id;
      this._lastAt = twice ? 0 : now;      // 세 번째 누름이 또 두 번이 되지 아니하게
      this.selectedId = id;
      if (twice) {
        // 두 번 누름을 따로 받는 곳이 있으면 그쪽에 넘기고, 없으면 펴고 접는다
        if (this.opts.onDblSelect) this.opts.onDblSelect(id);
        else this.opts.onToggle?.(id);
        return;
      }
      this.opts.onSelect?.(id);
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
