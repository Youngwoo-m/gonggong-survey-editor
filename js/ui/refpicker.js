/* ============================================================
   ui/refpicker.js — 참조 규정 고르기 (트리 목록)
   ------------------------------------------------------------
   규정이 70종을 넘으면서 드롭다운으로는 찾기 어려워졌다.
   묶음을 접었다 폈다 하는 트리로 바꾸고 이름 검색을 붙인다.

   원래 <select> 는 그대로 두고(숨김) 그 내용을 읽어 그린다.
     · 고르면 select.value 를 바꾸고 change 를 쏜다 → 기존 코드가 그대로 돈다
     · 목록이 바뀌면(파일 열기·공유) refresh() 만 부르면 된다
   ============================================================ */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export class RefPicker {
  /**
   * @param {HTMLSelectElement} select 원래 드롭다운
   * @param {{onPick?:(id:string)=>void}} opts
   */
  constructor(select, { onPick } = {}) {
    this.sel = select;
    this.onPick = onPick;
    this.open = false;
    this.query = "";
    this.closed = new Set();          // 접어 둔 묶음 이름

    select.classList.add("hidden");

    this.root = document.createElement("div");
    this.root.className = "refpick";
    this.root.innerHTML = `
      <button type="button" class="rp-btn" title="참조 규정 고르기">
        <span class="rp-name">—</span><span class="rp-caret">▾</span>
      </button>
      <div class="rp-panel hidden">
        <input type="search" class="rp-q" placeholder="규정 이름으로 찾기" />
        <div class="rp-list"></div>
        <div class="rp-foot"><span class="rp-count"></span>
          <div class="spacer"></div>
          <button type="button" class="mini2 rp-all">모두 펼치기</button></div>
      </div>`;
    select.parentNode.insertBefore(this.root, select);
    // 창이 잘리지 않도록 판은 본문 맨 위에 띄운다
    this.panel = this.root.querySelector(".rp-panel");
    document.body.appendChild(this.panel);

    this.btn = this.root.querySelector(".rp-btn");
    this.list = this.panel.querySelector(".rp-list");
    this.q = this.panel.querySelector(".rp-q");

    this.btn.onclick = () => (this.open ? this.close() : this.show());
    this.q.oninput = () => { this.query = this.q.value.trim(); this.render(); };
    this.q.onkeydown = (e) => {
      if (e.key === "Escape") { e.stopPropagation(); this.close(); }
      if (e.key === "Enter") {
        const first = this.list.querySelector(".rp-item:not(.off)");
        if (first) first.click();
      }
    };
    this.panel.querySelector(".rp-all").onclick = () => {
      this.closed.clear();
      this.render();
    };
    this._away = (e) => {
      if (!this.root.contains(e.target) && !this.panel.contains(e.target)) this.close();
    };
    this._reposition = () => { if (this.open) this.place(); };
    this._esc = (e) => { if (e.key === "Escape") this.close(); };

    // 다른 곳에서 select.value 를 바꿔도 단추 이름이 따라오게
    select.addEventListener("change", () => this.syncLabel());
    this.refresh();
  }

  /** <select> 내용을 다시 읽는다 */
  refresh() {
    this.groups = [];
    for (const g of this.sel.querySelectorAll("optgroup")) {
      this.groups.push({
        label: g.label,
        items: [...g.querySelectorAll("option")].map((o) => ({
          id: o.value, text: o.textContent, disabled: o.disabled,
        })),
      });
    }
    const loose = [...this.sel.children].filter((c) => c.tagName === "OPTION");
    if (loose.length) {
      this.groups.push({
        label: "그 밖의 규정",
        items: loose.map((o) => ({ id: o.value, text: o.textContent, disabled: o.disabled })),
      });
    }
    this.syncLabel();
    if (this.open) this.render();
  }

  syncLabel() {
    const o = this.sel.selectedOptions && this.sel.selectedOptions[0];
    this.root.querySelector(".rp-name").textContent = o ? o.textContent.trim() : "—";
    this.btn.title = o ? o.textContent.trim() : "참조 규정 고르기";
  }

  /** 단추 바로 아래에 판을 놓는다 (화면 밖으로 나가지 않게) */
  place() {
    const r = this.btn.getBoundingClientRect();
    const w = Math.min(460, window.innerWidth * 0.86);
    this.panel.style.width = `${w}px`;
    this.panel.style.left = `${Math.max(6, Math.min(r.left, window.innerWidth - w - 6))}px`;
    const below = window.innerHeight - r.bottom - 10;
    if (below > 260) {
      this.panel.style.top = `${r.bottom + 3}px`;
      this.panel.style.bottom = "auto";
      this.panel.style.maxHeight = `${below}px`;
    } else {
      this.panel.style.top = "auto";
      this.panel.style.bottom = `${window.innerHeight - r.top + 3}px`;
      this.panel.style.maxHeight = `${r.top - 12}px`;
    }
  }

  show() {
    this.open = true;
    this.panel.classList.remove("hidden");
    this.place();
    this.root.classList.add("on");
    this.render();
    this.q.value = this.query;
    this.q.focus();
    this.q.select();
    setTimeout(() => {
      document.addEventListener("click", this._away, true);
      document.addEventListener("keydown", this._esc, true);
      window.addEventListener("resize", this._reposition);
      window.addEventListener("scroll", this._reposition, true);
    }, 0);
  }

  close() {
    this.open = false;
    this.panel.classList.add("hidden");
    this.root.classList.remove("on");
    document.removeEventListener("click", this._away, true);
    document.removeEventListener("keydown", this._esc, true);
    window.removeEventListener("resize", this._reposition);
    window.removeEventListener("scroll", this._reposition, true);
  }

  render() {
    const q = this.query.toLowerCase();
    const cur = this.sel.value;
    let shown = 0, total = 0;

    const html = this.groups.map((g) => {
      const hits = g.items.filter((it) => !q || it.text.toLowerCase().includes(q));
      total += g.items.length;
      shown += hits.length;
      if (!hits.length) return "";
      const folded = !q && this.closed.has(g.label);
      return `<div class="rp-grp${folded ? " folded" : ""}" data-g="${esc(g.label)}">
        <div class="rp-ghead"><span class="tw">${folded ? "▶" : "▼"}</span>
          <b>${esc(g.label)}</b></div>
        <div class="rp-items">${hits.map((it) => `
          <div class="rp-item${it.disabled ? " off" : ""}${it.id === cur ? " cur" : ""}"
               data-id="${esc(it.id)}" title="${esc(it.text)}">${mark(it.text, q)}</div>`).join("")}</div>
      </div>`;
    }).join("");

    this.list.innerHTML = html || `<div class="rp-none">찾는 규정이 없습니다.</div>`;
    this.panel.querySelector(".rp-count").textContent =
      q ? `${shown} / ${total}종` : `${total}종`;

    this.list.querySelectorAll(".rp-ghead").forEach((h) => {
      h.onclick = () => {
        const k = h.parentElement.dataset.g;
        if (this.closed.has(k)) this.closed.delete(k); else this.closed.add(k);
        this.render();
      };
    });
    this.list.querySelectorAll(".rp-item:not(.off)").forEach((el) => {
      el.onclick = () => {
        const id = el.dataset.id;
        this.close();
        if (id === this.sel.value) return;
        this.sel.value = id;
        this.syncLabel();
        this.onPick ? this.onPick(id) : this.sel.dispatchEvent(new Event("change"));
      };
    });

    const cel = this.list.querySelector(".rp-item.cur");
    if (cel) cel.scrollIntoView({ block: "nearest" });
  }

  /** 바깥에서 특정 규정을 고르게 한다 (본문 인용 링크 등) */
  pick(id) {
    if (!id || id === this.sel.value) return false;
    if (![...this.sel.options].some((o) => o.value === id && !o.disabled)) return false;
    this.sel.value = id;
    this.syncLabel();
    this.onPick ? this.onPick(id) : this.sel.dispatchEvent(new Event("change"));
    return true;
  }

  has(id) {
    return [...this.sel.options].some((o) => o.value === id && !o.disabled);
  }
}

function mark(text, q) {
  if (!q) return esc(text);
  const i = text.toLowerCase().indexOf(q);
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<b class='hit'>" + esc(text.slice(i, i + q.length)) + "</b>"
    + esc(text.slice(i + q.length));
}
