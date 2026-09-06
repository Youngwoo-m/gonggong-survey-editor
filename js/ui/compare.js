/* ============================================================
   ui/compare.js — 개정 전후 비교표 화면
   ============================================================ */
import { buildComparison, KIND_LIST, kindLabel } from "../core/diff.js?v=20260906r";
import { writeXlsx } from "../core/xlsx.js?v=20260906r";
import * as M from "../core/model.js?v=20260906r";
import { regFingerprint } from "../core/xrefs.js?v=20260906r";
import { buildAmendment } from "../core/amend.js?v=20260906r";
import { buildSupplement, EFFECT_KINDS, topTitles } from "../core/supplement.js?v=20260906r";
import { stripImgTags, imgIdsIn, toHtml, fitTable }
  from "../core/objects.js?v=20260906r";
import { esc, fmtDate } from "./html.js?v=20260906r";

const KIND_CLASS = {
  "신설": "k-new", "삭제": "k-del", "이동": "k-mov", "이관": "k-xfer",
  "이동·수정": "k-mov", "수정": "k-edit", "통합": "k-mrg", "유지": "k-keep",
  // 통합·신설 —— 현행 조문 여럿을 합쳐 새로 둔 것. 새 조문이므로 신설의 빛깔을 쓴다.
  "통합·신설": "k-new",
};

export class CompareView {
  constructor(project) {
    this.project = project;
    this.el = null;
    this.opts = { onlyChanged: true, joOnly: false, excludePureMove: false };
    this.form = "official";   // "official" 신구조문 대비표 · "detail" 상세 비교표 · "amend" 개정문
    this.whole = false;       // 전부개정으로 적을 것인가
    // 부칙 — 시행일과 '다른 규정의 개정'
    this.sup = { on: true, kind: "promulgate", months: 6, date: "", others: true };
    this.result = null;
    this.fromId = null;
    this.toId = null;
    this.targetId = null;      // 어느 개정 대상 규정을 견주는가 (null 이면 세 규정 모두)
  }

  /* ---------- 개정 대상 규정 ---------- */

  /** 판 하나에서 이 규정의 가지만 꺼낸다 — 규정을 고르지 않았으면 판 전체 */
  _treeOf(v) {
    if (!v) return [];
    if (!this.targetId) return v.tree || [];
    const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === this.targetId);
    return reg ? (reg.children || []) : [];
  }

  /** 이 규정이 그 판에서 어느 개정안인가 — 판 이름이 아니라 규정의 개정안 이름으로 */
  _revOf(v) {
    if (!v) return null;
    if (!this.targetId) return { label: v.label, title: v.title || "", ver: v.label };
    const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === this.targetId);
    if (!reg) return null;                      // 그 판에 이 규정이 없다
    return { label: reg.revLabel || v.label, title: reg.revTitle || v.title || "", ver: v.label };
  }

  /** 개정안 이름 — 같은 이름을 담은 판이 여럿이면 판 이름을 덧붙인다 */
  _revText(v) {
    const r = this._revOf(v);
    if (!r) return "—";
    const dup = this._versions().filter((x) => this._revOf(x).label === r.label).length > 1;
    return `${r.label}${r.title ? ` · ${r.title}` : ""}`
      + (dup && r.ver !== r.label ? ` [${r.ver}]` : "");
  }

  /**
   * 이 규정을 담고 있는 판들 — 내용이 같은 판은 하나로 접는다.
   * 판은 세 규정을 한꺼번에 담으므로, 한 규정만 놓고 보면 여러 판이 똑같다.
   * 마지막 것을 남긴다 — 뒤엣것이 그 개정안의 최종 모습이다.
   */
  _versions() {
    const seen = new Map();
    for (const v of this.project.versions) {
      if (!this._revOf(v)) continue;
      const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === this.targetId);
      const key = this.targetId ? regFingerprint(reg) : v.id;
      seen.set(key, v);                            // 같은 내용이면 뒤엣것이 남는다
    }
    return [...seen.values()];
  }

  /** 비교 대상 버전 결정 (없으면 기준 ↔ 현재) */
  _resolve() {
    const p = this.project;
    const list = this._versions();
    const has = (id) => list.some((v) => v.id === id);
    if (!has(this.fromId)) this.fromId = (list.find((v) => v.readonly) || list[0])?.id || null;
    if (!has(this.toId)) {
      this.toId = has(p.currentId) ? p.currentId : (list[list.length - 1])?.id || null;
    }
    return { from: p.version(this.fromId), to: p.version(this.toId) };
  }

  open(fromId = null, toId = null, targetId = undefined) {
    if (targetId !== undefined) this.targetId = targetId;
    if (fromId) this.fromId = fromId;
    if (toId) this.toId = toId;
    if (this.el) this.close();
    this.el = document.createElement("div");
    this.el.className = "overlay";
    this.el.innerHTML = this._shell();
    document.body.appendChild(this.el);

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.addEventListener("click", (e) => { if (e.target === this.el) this.close(); });
    this._esc = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._esc, true);

    this.el.querySelector("#cmpForm").value = this.form;
    this.el.querySelector("#cmpForm").onchange = (e) => { this.form = e.target.value; this.refresh(); };
    this.el.querySelector("#cmpOnlyChanged").onchange = (e) => {
      this.opts.onlyChanged = e.target.checked; this.refresh();
    };
    this.el.querySelector("#cmpJoOnly").onchange = (e) => {
      this.opts.joOnly = e.target.checked; this.refresh();
    };
    this.el.querySelector("#cmpNoPureMove").onchange = (e) => {
      this.opts.excludePureMove = e.target.checked; this.refresh();
    };
    this.el.querySelector("#cmpWhole").onchange = (e) => { this.whole = e.target.checked; this.refresh(); };
    const sup = this.el.querySelector("#cmpSupBar");
    sup.querySelector("#supOn").onchange = (e) => { this.sup.on = e.target.checked; this.refresh(); };
    sup.querySelector("#supOthers").onchange = (e) => { this.sup.others = e.target.checked; this.refresh(); };
    sup.querySelector("#supKind").onchange = (e) => {
      this.sup.kind = e.target.value;
      sup.querySelector("#supMonthsWrap").classList.toggle("hidden", this.sup.kind !== "after");
      sup.querySelector("#supDateWrap").classList.toggle("hidden", this.sup.kind !== "date");
      this.refresh();
    };
    sup.querySelector("#supMonths").onchange = (e) => { this.sup.months = +e.target.value || 6; this.refresh(); };
    sup.querySelector("#supDate").onchange = (e) => { this.sup.date = e.target.value; this.refresh(); };
    this.el.querySelector('[data-x="copy"]').onclick = () => this.copyAmend();
    this.el.querySelector('[data-x="xlsx"]').onclick = () => this.exportXlsx();
    this.el.querySelector('[data-x="hwpx"]').onclick = (e) => this.exportHwpx(e.target);
    this.el.querySelector('[data-x="html"]').onclick = () => this.exportHtml();
    this.el.querySelector('[data-x="print"]').onclick = () => window.print();

    this.el.querySelector("#cmpTarget").onchange = (e) => {
      this.targetId = e.target.value || null;
      // 규정마다 담고 있는 판이 다르므로 앞뒤를 다시 고르고 목록을 다시 세운다
      this.fromId = this.toId = null;
      const { from, to } = this._resolve();
      this.el.querySelector("#cmpFrom").innerHTML = this._versionOptions(from?.id);
      this.el.querySelector("#cmpTo").innerHTML = this._versionOptions(to?.id);
      this.refresh();
    };
    this.el.querySelector("#cmpFrom").onchange = (e) => { this.fromId = e.target.value; this.refresh(); };
    this.el.querySelector("#cmpTo").onchange = (e) => { this.toId = e.target.value; this.refresh(); };
    this.el.querySelector('[data-x="swap"]').onclick = () => {
      const a = this.fromId; this.fromId = this.toId; this.toId = a;
      this.el.querySelector("#cmpFrom").value = this.fromId;
      this.el.querySelector("#cmpTo").value = this.toId;
      this.refresh();
    };

    this.refresh();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  refresh() {
    const { from, to } = this._resolve();
    this.result = buildComparison(this._treeOf(from), this._treeOf(to), this.opts);
    const { rows, summary } = this.result;

    const label = (v) => this._revText(v);
    this.el.querySelector("#cmpPair").innerHTML =
      `<b>개정 전</b> ${esc(label(from))} &nbsp;→&nbsp; <b>개정 후</b> ${esc(label(to))}`;
    this.el.querySelector("#cmpBase").innerHTML = esc(this._baseText());

    const chips = ["신설", "통합·신설", "삭제", "이관", "이동", "이동·수정", "수정", "통합", "유지"]
      .filter((k) => summary[k])
      .map((k) => `<span class="chip ${KIND_CLASS[k]}">${k} <b>${summary[k]}</b></span>`).join("");
    this.el.querySelector("#cmpSummary").innerHTML =
      `<span class="chip total">전체 <b>${summary.총}</b></span>` +
      `<span class="chip total">조 <b>${summary.조}</b></span>` +
      (summary.별표 ? `<span class="chip total">별표·별지 <b>${summary.별표}</b></span>` : "") +
      `<span class="chip total">변경 <b>${summary.변경}</b></span>` + chips;

    this.el.querySelector("#cmpCount").textContent = `${rows.length}행 표시`;
    const tbl = this.el.querySelector("#cmpTable");
    const amd = this.el.querySelector("#cmpAmend");
    const isAmend = this.form === "amend";
    tbl.classList.toggle("hidden", isAmend);
    amd.classList.toggle("hidden", !isAmend);
    this.el.querySelector("#cmpWholeWrap").classList.toggle("hidden", !isAmend);
    this.el.querySelector("#btnCmpCopy").classList.toggle("hidden", !isAmend);
    this.el.querySelector("#btnCmpXlsx").classList.toggle("hidden", isAmend);
    // 한/글 내보내기는 신구조문 대비표에서만 — 양식이 그 꼴이다
    this.el.querySelector("#btnCmpHwpx")
      .classList.toggle("hidden", this.form !== "official");
    this.el.querySelector("#cmpSupBar").classList.toggle("hidden", !isAmend);
    if (isAmend) {
      this.amend = buildAmendment(rows, { regName: this._regTitle(), whole: this.whole });
      const { from, to } = this._resolve();
      this.supText = this.sup.on ? buildSupplement({
        regName: this._regTitle(), tree: this.project.tree, targetId: this.targetId, rows,
        effective: { kind: this.sup.kind, months: this.sup.months, date: this.sup.date },
        withOthers: this.sup.others,
        oldTops: topTitles(this._treeOf(from)), newTops: topTitles(this._treeOf(to)),
      }) : null;
      amd.innerHTML = this._amendHtml(this.amend)
        + (this.supText ? this._supHtml(this.supText) : "");
      this.el.querySelector("#cmpCount").textContent =
        `${this.amend.items.length}개 지시문` + (this.supText ? ` · 부칙 ${this.supText.articles.length}개 조` : "");
      const w = this.el.querySelector("#supWarn");
      if (w) w.textContent = this.supText && this.supText.warnings.length
        ? `손으로 살필 것 ${this.supText.warnings.length}건` : "";
    } else {
      tbl.innerHTML = this.form === "official" ? this._officialTable(rows) : this._table(rows);
      tbl.className = this.form === "official" ? "official" : "";
      // 칸 안의 [표 N] 자리에 진짜 표를 끼워 넣는다 (뒤늦게 채운다)
      if (this.form === "official") {
        this._fillObjects(tbl, this._officialRows(rows));
      }
    }
  }

  /* ============================================================
     칸 안에 표 넣기
     ------------------------------------------------------------
     조문 본문에는 표가 <img id="…"> 표식으로 박혀 있다. 대비표를 글로만
     그리면 그 자리가 [표 1] 이라는 자리표시로만 남아, 무엇이 어떻게
     바뀌었는지 볼 수 없었다.

     자리표시의 번호는 그 칸의 본문에서 몇 번째 표인가를 가리킨다. 본문에서
     표 id 를 차례대로 뽑아 두면 [표 3] 이 어느 id 인지 알 수 있다.

     표 XML 은 data/objects/<규정>/<id>.xml 에 있다. 내려받아 그린 뒤
     자리표시 자리에 바꾸어 넣는다. 한 번 내려받은 것은 저장소가 담아 둔다.
     ============================================================ */

  /** 비교표에 표 저장소를 물린다 — main.js 에서 부른다 */
  setObjectStore(store, regIdOf = null) {
    this.objects = store;
    this.regIdOf = regIdOf || {};
  }

  /** 이 줄의 표가 어느 규정 것인가 */
  _objRegId(imgId) {
    return (this.targetId && this.regIdOf?.[this.targetId])
      || this.objects?.regOf(imgId)
      || null;
  }

  async _fillObjects(scope, rows) {
    if (!this.objects) return;
    const trs = [...scope.querySelectorAll("tbody tr")];
    for (let i = 0; i < trs.length; i++) {
      const r = rows[i];
      if (!r) continue;
      await this._fillCell(trs[i].children[0], r.before);
      await this._fillCell(trs[i].children[1], r.after);
    }
    fitTable(scope);
  }

  /** 한 칸의 [표 N] 을 진짜 표로 */
  async _fillCell(td, side) {
    if (!td || !side) return;
    // 자리표시의 번호는 날 본문에서 몇째 표인가를 가리킨다
    const ids = imgIdsIn(side.raw || "");
    if (!ids.length) return;
    // 글 마디를 훑어 [표 N] 을 찾는다 — 자리표시는 글로 박혀 있다
    const walker = document.createTreeWalker(td, NodeFilter.SHOW_TEXT);
    const hits = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (/\[표\s*\d+\]/.test(n.nodeValue)) hits.push(n);
    }
    for (const node of hits) {
      const parts = node.nodeValue.split(/(\[표\s*\d+\])/);
      const frag = document.createDocumentFragment();
      for (const p of parts) {
        const m = p.match(/^\[표\s*(\d+)\]$/);
        if (!m) { if (p) frag.appendChild(document.createTextNode(p)); continue; }
        const id = ids[+m[1] - 1];
        const box = document.createElement("div");
        box.className = "cmp-obj";
        box.textContent = p;                       // 못 그리면 자리표시 그대로
        frag.appendChild(box);
        if (!id) continue;
        const regId = this._objRegId(id);
        if (!regId) continue;
        // 표도 수식도 아닌 도해는 XML 이 없다 — 원본 그림을 그대로 보인다
        const meta = this.objects.meta(regId, id);
        if (meta && meta.kind === "image") {
          const url = `data/objects/${encodeURIComponent(regId)}/`
            + encodeURIComponent(meta.file || `${id}.gif`);
          box.innerHTML = `<img class="cmp-pic" loading="lazy" src="${esc(url)}"`
            + ` alt="${esc(meta.article || "")} 그림">`;
          box.classList.add("ok");
          continue;
        }
        this.objects.get(regId, id).then((obj) => {
          if (obj) { box.innerHTML = toHtml(obj); box.classList.add("ok"); }
        }).catch(() => { /* 못 읽으면 자리표시로 둔다 */ });
      }
      node.parentNode.replaceChild(frag, node);
    }
  }

  /* ============================================================
     신구조문 대비표 — 공공기관이 쓰는 공식 양식
     ------------------------------------------------------------
     App/관련규정/신구 조문 대비표_샘플.pdf 를 따른다.

       · 두 칸뿐이다 — 「현행」과 「개정안」
       · 신설은 현행 칸에 <제7조의2 신설> 이라 적고, 개정안 칸에 전문을 쓴다
       · 삭제는 개정안 칸에 '삭제' 라 적는다
       · 고친 조문은 개정안 칸에서 현행과 같은 대목을 줄표로 대신하고
         바뀐 대목만 글로 적는다 — 이것이 이 양식의 알맹이다
       · 그대로인 것은 현행 칸에 (생략), 개정안 칸에 (현행과 같음)

     조문 사이의 어절 비교(core/textdiff.js)가 이미 있으므로 그대로 쓴다.
     ============================================================ */

  /**
   * 바뀌지 않은 대목을 줄표로 — 글자 수만큼 그어 자리를 가늠하게 한다.
   * core/textdiff.js 의 afterRuns 는 {mark, s} 를 돌려준다 (mark 가 바뀐 대목).
   */
  _dashify(runs, fallback) { return dashify(runs, fallback); }

  /** 한 줄을 현행·개정안 두 칸으로 — 공식 양식의 표기법대로 */
  _officialCells(r) { return officialCells(r); }

  /* ---------- 렌더 ---------- */
  /** 견주고 있는 규정의 이름·고시 정보 */
  _baseText() {
    const m = this.project.baseMeta || {};
    const t = (m.targets || []).find((x) => x.id === this.targetId);
    if (!t) return `개정 대상 ${(m.targets || []).length || this.project.regNodes.length}종 전체`;
    return `${t.name}`
      + (t.kind ? ` (${t.org} ${t.kind} 제${t.no}호, 시행 ${fmtDate(t.effective)})` : "");
  }

  /**
   * 판 고르개 항목 — 그 규정의 개정안 이름으로 적는다.
   *
   * 같은 개정안을 담은 판이 여럿일 수 있다. 무인비행장치 v2 는 원본 초안과
   * 편집기 세 벌에서 옮겨 담은 것 둘 다에 들어 있다. 이름만으로는 갈리지
   * 않으므로, 겹칠 때에만 판 이름을 덧붙인다.
   */
  _versionOptions(sel) {
    const list = this._versions();
    const seen = {};
    for (const v of list) { const k = this._revOf(v).label; seen[k] = (seen[k] || 0) + 1; }
    return list.map((v) => {
      const r = this._revOf(v);
      const dup = seen[r.label] > 1 && v.label !== r.label;
      return `<option value="${v.id}"${v.id === sel ? " selected" : ""}>`
        + `${esc(r.label)}${r.title ? ` — ${esc(r.title)}` : ""}`
        + `${dup ? ` [${esc(v.label)}]` : ""}</option>`;
    }).join("");
  }

  _shell() {
    const { from, to } = this._resolve();
    /* 판 목록을 그 규정의 개정안 이름으로 보인다 — 판 이름(v1·v2)은 세 규정을
       아우른 것이라, 어느 개정안을 견주는지가 드러나지 않는다. */
    const opts = (sel) => this._versionOptions(sel);
    const tOpts = [
      ...this.project.regNodes.map((n) =>
        `<option value="${esc(n.targetId)}"${n.targetId === this.targetId ? " selected" : ""}>`
        + `${esc(n.short || n.title)}</option>`),
      `<option value=""${this.targetId ? "" : " selected"}>개정 대상 전체 (세 규정)</option>`,
    ].join("");
    return `
<div class="cmp">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">개정 전후 비교표</div>
      <div class="cmp-sub" id="cmpPair"></div>
      <div class="cmp-sub" id="cmpBase"></div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar">
    <div class="vpick">
      <span>개정 대상</span><select id="cmpTarget" title="견줄 규정을 고릅니다">${tOpts}</select>
      <span class="sep"></span>
      <span>개정 전</span><select id="cmpFrom">${opts(from?.id)}</select>
      <button data-x="swap" title="앞뒤 바꾸기">⇄</button>
      <span>개정 후</span><select id="cmpTo">${opts(to?.id)}</select>
    </div>
    <div id="cmpSummary" class="chips"></div>
  </div>

  <div class="cmp-bar2">
    <label title="공공기관이 쓰는 신구조문 대비표 양식 — 현행·개정안 두 칸, 같은 대목은 줄표">
      양식 <select id="cmpForm">
        <option value="official">신구조문 대비표</option>
        <option value="detail">상세 비교표 (변경 사유 포함)</option>
        <option value="amend">개정문 (개정 지시문)</option>
      </select></label>
    <label><input type="checkbox" id="cmpOnlyChanged" checked> 변경된 항목만</label>
    <label><input type="checkbox" id="cmpJoOnly"> 조문만 (편·장 제외)</label>
    <label title="본문·제목 변경 없이 편제 위치만 바뀐 항목을 숨깁니다 ('이동·수정'은 남습니다)"><input type="checkbox" id="cmpNoPureMove"> 내용 변경 없는 이동 제외</label>
    <label id="cmpWholeWrap" class="hidden" title="머리말을 '전부를 다음과 같이 개정한다' 로 적습니다"><input type="checkbox" id="cmpWhole"> 전부개정</label>
    <span id="cmpCount" class="hint"></span>
    <div class="spacer"></div>
    <button data-x="copy" id="btnCmpCopy" class="hidden">개정문 복사</button>
    <button data-x="xlsx" id="btnCmpXlsx" class="primary">엑셀(.xlsx) 내보내기</button>
    <button data-x="hwpx" id="btnCmpHwpx">한/글(.hwpx) 내보내기</button>
    <button data-x="html">HTML 내보내기</button>
    <button data-x="print">인쇄</button>
  </div>

  <div class="cmp-bar3 hidden" id="cmpSupBar">
    <label><input type="checkbox" id="supOn" checked> <b>부칙</b></label>
    <span class="sep"></span>
    <label>시행일 <select id="supKind">${EFFECT_KINDS.map((k) =>
      `<option value="${k.id}">${esc(k.label)}</option>`).join("")}</select></label>
    <label id="supMonthsWrap" class="hidden">공포 후 <input type="number" id="supMonths" min="1" max="36" value="6" style="width:52px"> 개월</label>
    <label id="supDateWrap" class="hidden"><input type="date" id="supDate"></label>
    <span class="sep"></span>
    <label title="이 규정을 인용하는 다른 규정의 조문을 찾아 '다른 규정의 개정' 을 짓습니다">
      <input type="checkbox" id="supOthers" checked> 다른 규정의 개정</label>
    <span id="supWarn" class="hint"></span>
  </div>

  <div class="cmp-body"><table id="cmpTable"></table><div id="cmpAmend" class="amend hidden"></div></div>
</div>`;
  }

  /** 개정문에 적을 규정 이름 — 「…」 안에 들어갈 이름 */
  _regTitle() {
    const n = this.project.regNodes.find((x) => x.targetId === this.targetId);
    if (n) return n.title;
    const m = this.project.baseMeta || {};
    return (m.targets || []).map((t) => t.name).join("」·「") || this.project.baseName || "이 규정";
  }

  /**
   * 개정문 — 고시에 실제로 실리는 글.
   * 지시문 한 줄이 한 덩이이고, 전문을 붙이는 것(신설·전문개정)은 들여쓴다.
   */
  _amendHtml(am) {
    if (!am.items.length) {
      return `<div class="amend-head">${esc(am.head)}</div>`
        + `<div class="none">고칠 것이 없습니다. 개정 전후를 다시 골라 보세요.</div>`;
    }
    const KIND = { 자구: "자구", 제목: "제목", 전문개정: "전문개정",
                   신설: "신설", 삭제: "삭제", 이동: "이동" };
    const body = am.items.map((it) => `
      <div class="amend-item ${KIND_CLASS[it.kind] || ""}">
        <span class="amend-tag">${esc(KIND[it.kind] || it.kind)}</span>
        <div class="amend-text">${esc(it.text)}${
          it.body ? `<div class="amend-body">${esc(it.body)}</div>` : ""}</div>
      </div>`).join("");
    return `<div class="amend-head">${esc(am.head)}</div>${body}`;
  }

  /** 부칙 — 개정문 뒤에 이어 붙는다 */
  _supHtml(sup) {
    const arts = sup.articles.map((a) => `
      <div class="amend-item">
        <span class="amend-tag">부칙</span>
        <div class="amend-text"><b>제${a.no}조(${esc(a.title)})</b> ${esc(a.lines[0])}${
          a.lines.length > 1
            ? `<div class="amend-body">${a.lines.slice(1).map(esc).join("<br>")}</div>` : ""}</div>
      </div>`).join("");
    const warn = sup.warnings.length ? `
      <div class="amend-warn"><b>손으로 살펴야 할 것 ${sup.warnings.length}건</b>
        <ul>${sup.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : "";
    return `<div class="amend-sup"><div class="amend-head">부칙</div>${arts}${warn}</div>`;
  }

  /** 개정문을 글자 그대로 클립보드에 — 한/글에 그대로 붙여 넣는다 */
  async copyAmend() {
    const text = [this.amend ? this.amend.text : "",
                  this.supText ? "\n\n" + this.supText.text : ""].join("");
    try {
      await navigator.clipboard.writeText(text);
      this._flash("개정문을 복사했습니다 — 한/글에 그대로 붙여 넣으십시오.");
    } catch {
      // 클립보드를 막아 둔 브라우저에서는 골라 둔다
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); this._flash("개정문을 복사했습니다."); }
      catch { this._flash("복사하지 못했습니다 — 글을 직접 골라 복사하십시오."); }
      ta.remove();
    }
  }

  _flash(msg) {
    const el = this.el && this.el.querySelector("#cmpCount");
    if (!el) return;
    const old = el.textContent;
    el.textContent = msg;
    setTimeout(() => { if (el.textContent === msg) el.textContent = old; }, 2600);
  }

  /* 신구조문 대비표에 싣는 것은 **조문뿐**이다.
   *
   * 양식(Form\02.신구대조표)이 조문 대비표이고, 한/글 생성기
   * (scripts/formdocs.py 의 build_compare)도 조만 싣는다. 편ㆍ장 마디는
   * 본문 자리에 개편 작업 메모가 들어 있어(제1편 총칙에는 연구보고서 요약
   * 표 셋이 박혀 있다) 대비표에 넣으면 수정(안) 칸이 메모로 채워진다.
   * 별표ㆍ별지는 따로 목록을 낸다.
   */
  _officialRows(rows) {
    return (rows || []).filter((r) => r.level === "조" && !r.annex);
  }

  /** 신구조문 대비표 — 현 행 · 수정(안) · 개정 사유 세 칸
   *
   *  양식(Form\02.신구대조표)의 칸 폭 25510/26339/18981 에서 온 몫이다.
   *  한/글 생성기도 이 세 칸으로 짓는다. */
  _officialTable(allRows) {
    const rows = this._officialRows(allRows);
    const dropped = (allRows || []).length - rows.length;
    const head = `<thead><tr>
      <th style="width:36%">현 행</th>
      <th style="width:37%">수정(안)</th>
      <th style="width:27%">개정 사유</th>
    </tr></thead>`;
    if (!rows.length) {
      return head + `<tbody><tr><td colspan="3" class="none">표시할 항목이 없습니다. 필터를 해제해 보세요.</td></tbody>`;
    }
    const body = rows.map((r) => {
      const c = this._officialCells(r);
      return `<tr class="${KIND_CLASS[r.kind]}">
        <td>${cellsHtml(c.cur)}</td>
        <td>${cellsHtml(c.rev)}</td>
        <td class="why">${whyHtml(r)}</td>
      </tr>`;
    }).join("");
    const note = dropped
      ? `<tfoot><tr><td colspan="3" class="none">`
        + `편ㆍ장 마디와 별표ㆍ별지 ${dropped}개는 싣지 않았습니다 — `
        + `양식이 조문 대비표입니다. 별표ㆍ별지는 [상세 비교표] 에서 보십시오.`
        + `</td></tr></tfoot>`
      : "";
    return head + `<tbody>${body}</tbody>` + note;
  }

  _table(rows) {
    const pt = this._pairText();
    const head = `<thead><tr>
      <th style="width:46px">연번</th>
      <th style="width:78px">구분</th>
      <th style="width:32%">개정 전 — ${esc(pt.from)}</th>
      <th style="width:32%">개정 후 — ${esc(pt.to)}</th>
      <th style="width:22%">변경 사유 · 비고</th>
    </tr></thead>`;

    if (!rows.length) {
      return head + `<tbody><tr><td colspan="5" class="none">표시할 항목이 없습니다. 필터를 해제해 보세요.</td></tbody>`;
    }

    const body = rows.map((r) => {
      const b = r.before, a = r.after;
      const bTitle = r.beforeTitleRuns ? runsHtml(r.beforeTitleRuns) : esc(b ? b.title : "");
      const aTitle = r.afterTitleRuns ? runsHtml(r.afterTitleRuns) : esc(a ? a.title : "");
      const bBody = r.beforeBodyRuns ? runsHtml(r.beforeBodyRuns) : esc(b ? b.body : "");
      const aBody = r.afterBodyRuns ? runsHtml(r.afterBodyRuns) : esc(a ? a.body : "");

      const note = [];
      if (r.numberChanged) note.push(`조번호 <b>${esc(b.label)}</b> → <b>${esc(a.label)}</b>`);
      if (r.kind.includes("이동") && b && a) note.push(`위치 ${esc(b.path)} → ${esc(a.path)}`);
      if (r.source) note.push(`출처 ${esc(r.source)}`);
      if (r.reason) note.push(esc(r.reason));

      return `<tr class="${KIND_CLASS[r.kind]}">
        <td class="c">${r.seq}</td>
        <td class="c"><span class="tag ${KIND_CLASS[r.kind]}">${esc(kindLabel(r))}</span></td>
        <td class="${b ? "" : "empty"}">${b ? `<div class="lbl">${esc(b.label)}${b.title ? ` <span class="ttl">${bTitle}</span>` : ""}</div>${bBody ? `<div class="bd">${bBody}</div>` : ""}` : "— (해당 조문 없음)"}</td>
        <td class="${a ? "" : "empty"}">${a ? `<div class="lbl">${esc(a.label)}${a.title ? ` <span class="ttl">${aTitle}</span>` : ""}</div>${aBody ? `<div class="bd">${aBody}</div>` : ""}` : "— (삭제)"}</td>
        <td class="note">${note.join("<br>") || ""}</td>
      </tr>`;
    }).join("");

    return head + `<tbody>${body}</tbody>`;
  }

  /* ---------- 내보내기 ---------- */
  _pairText() {
    const { from, to } = this._resolve();
    return { from: this._revText(from), to: this._revText(to), base: this._baseText() };
  }

  /** 내보내는 파일 이름에 붙일 규정 이름 */
  _targetName() {
    const n = this.project.regNodes.find((x) => x.targetId === this.targetId);
    return n ? (n.short || n.title) : "개정 대상 전체";
  }

  _fileBase() {
    const d = new Date();
    const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
    const { from, to } = this._resolve();
    const safe = (s) => String(s || "").replace(/[\\/:*?"<>|\s]/g, "_");
    // 규정마다 따로 내므로 파일 이름에 규정을 적는다
    return `개정전후_비교표_${safe(this._targetName())}`
      + `_${safe(this._revOf(from)?.label)}-${safe(this._revOf(to)?.label)}_${ymd}`;
  }

  exportXlsx() {
    const { rows, summary } = this.result;
    const pt = this._pairText();
    const S = { HEAD: 1, CELL: 2, CEN: 3, TITLE: 4, SUB: 5, KIND: 6 };

    const sheetRows = [];
    sheetRows.push([{ v: this.form === "official" ? "신구조문 대비표" : "개정 전후 비교표", s: S.TITLE }]);
    sheetRows.push([{ v: `현행: ${pt.from}   ↔   개정안: ${pt.to}`, s: S.SUB }]);
    sheetRows.push([{ v: `대상 규정: ${pt.base}`, s: S.SUB }]);
    sheetRows.push([{
      v: `전체 ${summary.총} · 조 ${summary.조}${summary.별표 ? ` · 별표·별지 ${summary.별표}` : ""} · 변경 ${summary.변경}   ` +
         KIND_LIST.filter((k) => summary[k]).map((k) => `${k} ${summary[k]}`).join(" · ") +
         `   |  작성 ${new Date().toLocaleString("ko-KR")}`, s: S.SUB,
    }]);
    sheetRows.push([]);
    if (this.form === "official") {
      // 신구조문 대비표 — 양식대로 세 칸
      sheetRows.push(["현 행", "수정(안)", "개정 사유"].map((v) => ({ v, s: S.HEAD })));
      for (const r of rows) {
        const c = this._officialCells(r);
        sheetRows.push([
          { runs: cellRunsOfficial(c.cur), s: S.CELL },
          { runs: cellRunsOfficial(c.rev), s: S.CELL },
          { v: whyLines(r.reason, r.kind || r.status).map((s) => `- ${s}`).join("\n"),
            s: S.CELL },
        ]);
      }
      const blobO = writeXlsx({
        name: `신구조문 대비표 (${this._targetName()})`.slice(0, 31),
        cols: [{ w: 46 }, { w: 48 }, { w: 36 }],
        rows: sheetRows,
        freeze: 6,
      });
      download(blobO, this._fileBase() + ".xlsx");
      return;
    }
    sheetRows.push(["연번", "구분", `개정 전 — ${pt.from}`, `개정 후 — ${pt.to}`, "변경 사유 · 비고"]
      .map((v) => ({ v, s: S.HEAD })));

    for (const r of rows) {
      const b = r.before, a = r.after;
      const beforeRuns = cellRuns(b, r.beforeTitleRuns, r.beforeBodyRuns, "— (해당 조문 없음)");
      const afterRuns = cellRuns(a, r.afterTitleRuns, r.afterBodyRuns, "— (삭제)");
      const note = [];
      if (r.numberChanged) note.push(`조번호 ${b.label} → ${a.label}`);
      if (r.kind.includes("이동") && b && a) note.push(`위치 ${b.path} → ${a.path}`);
      if (r.source) note.push(`출처 ${r.source}`);
      if (r.reason) note.push(r.reason);
      sheetRows.push([
        { v: r.seq, s: S.CEN },
        { v: kindLabel(r), s: S.KIND },
        { runs: beforeRuns, s: S.CELL },
        { runs: afterRuns, s: S.CELL },
        { v: note.join("\n"), s: S.CELL },
      ]);
    }

    const blob = writeXlsx({
      name: `개정전후 비교표 (${this._targetName()})`.slice(0, 31),
      cols: [{ w: 6 }, { w: 10 }, { w: 58 }, { w: 58 }, { w: 34 }],
      rows: sheetRows,
      rowHeights: { 0: 24 },
      freeze: 6,
    });
    download(blob, this._fileBase() + ".xlsx");
  }

  /** 개정문 — 인쇄해서 그대로 올리는 꼴 (A4 세로) */
  _exportHtmlAmend(pt) {
    const am = this.amend || buildAmendment(this.result.rows,
      { regName: this._regTitle(), whole: this.whole });
    const css = `@page{size:A4 portrait;margin:25mm 22mm}
body{font-family:"맑은 고딕",sans-serif;font-size:11pt;line-height:2;margin:0;color:#000}
h1{font-size:14pt;margin:0 0 18px;font-weight:700}
p.it{margin:0 0 10px;text-indent:0}
pre.bd{font-family:inherit;font-size:10.5pt;margin:4px 0 12px 16px;white-space:pre-wrap;line-height:1.9}`;
    const items = am.items.map((it) =>
      `<p class="it">${esc(it.text)}</p>${it.body ? `<pre class="bd">${esc(it.body)}</pre>` : ""}`).join("");
    const sup = this.supText ? `<h1 style="margin-top:28px">부칙</h1>`
      + this.supText.articles.map((a) =>
        `<p class="it"><b>제${a.no}조(${esc(a.title)})</b> ${esc(a.lines[0])}</p>`
        + (a.lines.length > 1 ? `<pre class="bd">${a.lines.slice(1).map(esc).join("\n")}</pre>` : "")).join("")
      : "";
    const html = `<!doctype html><html lang="ko"><meta charset="utf-8">
<title>개정문 — ${esc(this._targetName())}</title><style>${css}</style>
<h1>${esc(am.head)}</h1>${items}${sup}</html>`;
    download(new Blob([html], { type: "text/html;charset=utf-8" }),
      this._fileBase().replace("개정전후_비교표", "개정문") + ".html");
  }

  /** 신구조문 대비표 — 인쇄해서 붙임으로 쓰는 꼴 (A4 세로, 두 칸) */
  _exportHtmlOfficial(rows, pt) {
    const css = `@page{size:A4 portrait;margin:20mm 18mm}
body{font-family:"맑은 고딕",sans-serif;font-size:10pt;margin:0;color:#000}
h1{font-size:15pt;text-align:center;margin:0 0 4px;letter-spacing:2px}
p.sub{text-align:center;color:#444;font-size:9pt;margin:0 0 12px;line-height:1.5}
table{border-collapse:collapse;width:100%;table-layout:fixed}
th,td{border:1px solid #000;padding:6px 7px;vertical-align:top;font-size:9.5pt;line-height:1.7;word-break:break-all}
th{text-align:center;font-weight:700;background:#f2f2f2}
u.mk{text-decoration:underline;color:#C00000}
.mk-new{font-weight:700}
.mk-omit{color:#444}
td.why{font-size:9pt;line-height:1.65;word-break:keep-all}
.rule{border:1px solid #bbb;background:#FAFAF7;padding:6px 10px;font-size:9pt;
      color:#444;margin:0 0 10px}`;
    const body = rows.map((r) => {
      const c = this._officialCells(r);
      return `<tr><td>${cellsHtml(c.cur)}</td><td>${cellsHtml(c.rev)}</td>`
        + `<td class="why">${whyHtml(r)}</td></tr>`;
    }).join("");
    const html = `<!doctype html><html lang="ko"><meta charset="utf-8">
<title>신구조문 대비표 — ${esc(this._targetName())}</title><style>${css}</style>
<h1>신구조문 대비표</h1>
<p class="sub">${esc(pt.base)}<br>현행: ${esc(pt.from)} &nbsp;↔&nbsp; 개정안: ${esc(pt.to)}</p>
<div class="rule"><b>표기 원칙</b> — 변경 없는 부분은 “_” 로 줄여 적고, 수정(안)의
 새 문구는 <u class="mk">붉은색 밑줄</u>로 표시하며, 개정 사유는 개조식으로 적습니다.</div>
<table><thead><tr><th style="width:36%">현 행</th><th style="width:37%">수정(안)</th>
<th style="width:27%">개정 사유</th></tr></thead>
<tbody>${body}</tbody></table></html>`;
    download(new Blob([html], { type: "text/html;charset=utf-8" }), this._fileBase() + ".html");
  }

  /* ============================================================
     한/글(.hwpx) 내보내기
     ------------------------------------------------------------
     HWPX 는 ZIP + XML 이라 브라우저에서도 지을 수 있다. 다만 손으로 조립한
     꾸러미는 한/글이 '손상된 파일' 로 본다. 그래서 **양식 파일을 열어 글만
     갈아 끼운다** — 파이썬 쪽(scripts/formfill.py)과 같은 방식이다.

     견주기는 화면이 이미 한 것(officialCells)을 그대로 넘긴다. 두 벌을
     두면 화면에서 본 대비표와 내려받은 문서가 서로 달라진다.
     ============================================================ */
  async exportHwpx(btn) {
    const old = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.textContent = "짓는 중…"; }
    try {
      const { buildCompareHwpx } = await import("../core/hwpxcompare.js?v=20260906r");
      // 대비표에 싣는 것은 조문뿐이다 — 양식이 조문 대비표다
      const rows = this._officialRows(this.result.rows);
      if (!rows.length) throw new Error("대비표에 실을 조문이 없습니다.");
      const got = await buildCompareHwpx(rows, {
        regname: this._targetName(),
        cells: (r) => this._officialCells(r),
        why: (r) => whyLines(r.reason, kindLabel(r) || r.status),
      });
      download(got.blob, got.name);
      if (btn) btn.textContent = `${got.rows}개 조 · 내려받음`;
      setTimeout(() => { if (btn) btn.textContent = old; }, 2500);
    } catch (err) {
      console.error(err);
      alert(`한/글 파일을 짓지 못했습니다.\n\n${err.message}`);
      if (btn) btn.textContent = old;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  exportHtml() {
    const { rows, summary } = this.result;
    const pt = this._pairText();
    if (this.form === "amend") return this._exportHtmlAmend(pt);
    if (this.form === "official")
      return this._exportHtmlOfficial(this._officialRows(rows), pt);
    const css = `body{font-family:"맑은 고딕",sans-serif;font-size:11pt;margin:24px;color:#1F2C35}
h1{font-size:17pt;margin:0 0 4px}p.sub{color:#7B8A92;font-size:9.5pt;margin:0 0 14px;line-height:1.6}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #C7D2D8;padding:6px 8px;vertical-align:top;font-size:9.5pt;line-height:1.6}
th{background:#1F2C35;color:#fff;font-size:9.5pt}
td.c{text-align:center;white-space:nowrap}
.lbl{font-weight:700;margin-bottom:3px}.ttl{font-weight:400}
.bd{white-space:pre-wrap;color:#33454F}
u.mk{text-decoration:underline;color:#C1502E;font-weight:700}
td.empty{color:#9AA8AF;text-align:center}
td.note{color:#44585F;font-size:9pt}
tr.k-new td{background:#F2F8F6}tr.k-del td{background:#FBF3F1}
.tag{font-size:8.5pt;padding:1px 6px;border-radius:9px;color:#fff;background:#7B8A92;white-space:nowrap}
.tag.k-new{background:#2E7D6B}.tag.k-del{background:#C1502E}.tag.k-mov{background:#B07A1E}
.tag.k-edit{background:#B07A1E}.tag.k-mrg{background:#7B8A92}.tag.k-keep{background:#B9C5CB}
@page{size:A4 landscape;margin:12mm}`;
    const html = `<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>개정 전후 비교표</title><style>${css}</style></head><body>
<h1>개정 전후 비교표</h1>
<p class="sub">개정 전: <b>${esc(pt.from)}</b> &nbsp;↔&nbsp; 개정 후: <b>${esc(pt.to)}</b><br>
기준 규정: ${esc(pt.base)}<br>
전체 ${summary.총} · 조 ${summary.조}${summary.별표 ? ` · 별표·별지 ${summary.별표}` : ""} · 변경 ${summary.변경} &nbsp;|&nbsp;
${KIND_LIST.filter((k) => summary[k]).map((k) => `${k} ${summary[k]}`).join(" · ")}
&nbsp;|&nbsp; 작성 ${new Date().toLocaleString("ko-KR")}</p>
<table>${this._table(rows)}</table></body></html>`;
    download(new Blob([html], { type: "text/html;charset=utf-8" }), this._fileBase() + ".html");
  }
}

/* ---------- 헬퍼 ---------- */
function cellRuns(side, titleRuns, bodyRuns, emptyText) {
  if (!side) return [{ mark: false, s: emptyText }];
  const runs = [{ mark: false, s: side.label + (side.title ? " " : "") }];
  if (side.title) {
    if (titleRuns) runs.push(...titleRuns.filter((r) => r.s));
    else runs.push({ mark: false, s: side.title });
  }
  if (side.body) {
    runs.push({ mark: false, s: "\n" });
    if (bodyRuns) runs.push(...bodyRuns.filter((r) => r.s));
    else runs.push({ mark: false, s: side.body });
  }
  return runs;
}

function runsHtml(runs) {
  return runs.map((r) => (r.mark ? `<u class="mk">${esc(r.s)}</u>` : esc(r.s))).join("");
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** 글자 수만큼 줄을 긋는다 — 공백은 세지 않는다 (신구조문 대비표 양식)
 *
 *  양식이 적어 둔 표기 원칙은 「변경 없는 부분은 "_" 로 생략」이다.
 *  한/글 생성기(scripts/formdocs.py 의 diff_runs)도 밑줄(_)을 쓴다.
 *  화면ㆍ웹 보고서ㆍ한/글 문서가 서로 달라 보이지 않도록 여기서도 맞춘다. */
function dashes(text) {
  const n = String(text || "").replace(/\s+/g, "").length;
  return n ? "_".repeat(Math.min(n, 400)) : "";
}
const NLC = "\n";

/** 바뀌지 아니한 대목은 줄표로, 새로 쓴 대목만 글로 */
export function dashify(runs, fallback) {
  if (!runs || !runs.length) return [{ t: "=", s: dashes(fallback || "") }];
  return runs.map((r) => r.mark ? { t: "+", s: r.s } : { t: "=", s: dashes(r.s) });
}

/**
 * 한 줄을 현행ㆍ개정안 두 칸으로 — 공식 양식의 표기법대로.
 *
 * 화면(CompareView)과 보고서(ui/report.js)가 함께 쓴다. 두 벌을 두면
 * 화면에서 본 대비표와 내려받은 대비표가 서로 달라진다.
 */
export function officialCells(r) {
  const b = r.before, a = r.after;
  /* 「제193조 정의(제193조 정의)」처럼 겹쳐 적히는 줄이 있다 — 조 번호를
     따로 두지 않고 제목에 통째로 담은 마디(삭제 자리표시 44개)가 그렇다.
     이름표가 이미 제목을 담고 있으면 괄호를 붙이지 아니한다. */
  const head = (x) => {
    if (!x) return "";
    const t = String(x.title || "").trim();
    const lb = String(x.label || "").trim();
    if (!t || lb === t || lb.endsWith(t)) return lb;
    return `${lb}(${t})`;
  };
  // 본문의 표·수식 표식은 글이 아니므로 자리만 남긴다
  const txt = (v) => stripImgTags(v || "", (i) => `[표 ${i}]`);
  const full = (x) => [{ t: "=", s: head(x) },
                       ...(x && x.body ? [{ t: "=", s: NLC + txt(x.body) }] : [])];
  /* 현행 칸 — 앞으로 바뀔 대목을 파랗게 짚는다.
     개정안 칸이 새로 쓴 대목을 붉게 짚는 것과 짝을 이룬다. */
  const curMarked = (x, runs) => {
    const parts = [{ t: "=", s: head(x) }];
    if (!x || !x.body) return parts;
    parts.push({ t: "=", s: NLC });
    if (!runs || !runs.length) { parts.push({ t: "=", s: txt(x.body) }); return parts; }
    parts.push(...runs.map((g) => ({ t: g.mark ? "-" : "=", s: g.s })));
    return parts;
  };

  if (!b && r.splitFrom) {
    /* 한 조를 여러 조로 나눈 것. 글은 현행에서 온 것이므로 신설이 아니다 —
       어느 조에서 나왔는지 적어 두어야 대비표를 읽을 수 있다. */
    return { cur: [{ t: "mark", s: `<현행 ${r.splitFrom}에서 나눔>` }], rev: full(a) };
  }
  if (r.kind === "신설") {
    // 표시는 번호만 적는다 — <제7조의2 신설>
    return { cur: [{ t: "mark", s: `<${a ? a.label : ""} 신설>` }], rev: full(a) };
  }
  if (r.kind === "삭제") {
    // 통째로 없애는 것이므로 본문 전부가 바뀔 대목이다
    return { cur: [{ t: "=", s: head(b) }, { t: "=", s: NLC },
                   { t: "-", s: b && b.body ? txt(b.body) : "" }],
             rev: [{ t: "mark", s: "삭제" }] };
  }
  if (r.kind === "유지" || r.kind === "이동") {
    // 이동은 자리만 옮긴 것 — 글은 그대로이므로 되풀이하지 않는다
    return { cur: [{ t: "=", s: head(b) }, { t: "omit", s: " (생략)" }],
             rev: [{ t: "=", s: head(a) }, { t: "omit", s: " (현행과 같음)" }] };
  }
  // 수정 · 이동·수정 · 통합 — 같은 대목은 줄표로, 바뀐 대목만 글로
  /* 항이 여럿인 조문은 바뀐 항만 적고 나머지는 접는다
       현행   제8조(보안성 검토 및 보안관리) ①∼③(생략)
       개정안 제8조(보안성 검토 및 보안관리) ①∼③(현행과 같음) */
  const folded = foldByHang(b && b.body, a && a.body, r.bodyDiff);
  if (folded) {
    return {
      cur: [{ t: "=", s: head(b) }, { t: "=", s: NLC }, ...folded.cur],
      rev: [{ t: "=", s: head(a) }, { t: "=", s: NLC }, ...folded.rev],
    };
  }
  const titleSame = !r.afterTitleRuns || !r.afterTitleRuns.some((x) => x.mark);
  const rev = titleSame
    ? [{ t: "=", s: head(a) }]
    : [{ t: "=", s: a ? a.label : "" }, ...dashify(r.afterTitleRuns, b && b.title)];
  if (a && (a.body || (b && b.body))) {
    rev.push({ t: "=", s: NLC });
    rev.push(...dashify(r.afterBodyRuns, b && b.body));
  }
  return { cur: curMarked(b, r.beforeBodyRuns), rev };
}

/* ------------------------------------------------- 셋째 칸에 넣을 개정 사유
 *
 * 한/글 생성기(scripts/genreport_hwpx.py 의 why_of)와 **같은 규칙**이라야
 * 한다. 규칙이 둘이면 화면에서 본 대비표와 [한글문서만들기.bat] 이 지은
 * 대비표의 셋째 칸이 서로 달라진다.
 *
 *   ○ 개정 내용: 을 먼저 쓰고, 없으면 ○ 개정 사유: 를 쓴다
 *   자리만 채워 둔 줄은 걷어 낸다 (42개 조가 모두 같은 한 줄을 이고 있다)
 *   겹치는 줄을 덜고 여섯 줄까지만 싣는다
 */
const SEC_WHY = "개정 사유";
const SEC_WHAT = "개정 내용";
const WHY_NOISE = /짚은 마디가 따로 없다|확인된 내용이 없다|해당 없음/;

/** 사유 글 → [[머리, [항목…]]…] */
function reasonSecs(reason) {
  const secs = [];
  let head = null;
  let items = [];
  for (const ln of String(reason || "").split("\n")) {
    const s = ln.trim();
    if (!s || s === "[변경 사유]") continue;
    if (s.startsWith("○")) {
      if (head !== null) secs.push([head, items]);
      head = s.replace(/^○+/, "").trim().replace(/:$/, "").trim();
      items = [];
    } else if (head === null) {
      secs.push(["", [s.replace(/^\*\s*/, "")]]);
    } else {
      items.push(s.replace(/^\*\s*/, ""));
    }
  }
  if (head !== null) secs.push([head, items]);
  return secs;
}

function pickSec(secs, ...names) {
  const out = [];
  for (const [head, items] of secs) {
    if (names.some((n) => head.includes(n))) out.push(...items);
  }
  return out;
}

/** 차례는 그대로 두고 겹치는 줄만 덜어 낸다 */
function uniqLines(xs) {
  const seen = new Set();
  const out = [];
  for (const x of xs) {
    const k = x.replace(/\s+/g, "");
    if (k && !seen.has(k)) { seen.add(k); out.push(x); }
  }
  return out;
}

/** 대비표 셋째 칸에 넣을 개조식 줄들 */
export function whyLines(reason, fallback) {
  const secs = reasonSecs(reason);
  const keep = (xs) => uniqLines(xs.filter((x) => !WHY_NOISE.test(x)));
  const what = keep(pickSec(secs, SEC_WHAT));
  const got = (what.length ? what : keep(pickSec(secs, SEC_WHY))).slice(0, 6);
  return got.length ? got : (fallback ? [String(fallback)] : []);
}

/** 셋째 칸을 HTML 로 — 개조식 한 줄에 하나씩 */
export function whyHtml(r) {
  const w = whyLines(r.reason, kindLabel(r) || r.status);
  return w.length
    ? w.map((s) => `- ${esc(s)}`).join("<br>")
    : `<span class="mk-omit">—</span>`;
}

/** 신구조문 대비표 한 칸 — 줄표·표시·본문을 갈라 그린다 */
export function cellsHtml(parts) {
  return (parts || []).map((r) => {
    if (r.t === "mark") return `<span class="mk-new">${esc(r.s)}</span>`;
    if (r.t === "omit") return `<span class="mk-omit">${esc(r.s)}</span>`;
    if (r.t === "+") return `<u class="mk">${esc(r.s)}</u>`;
    if (r.t === "-") return `<u class="mk-old">${esc(r.s)}</u>`;
    return `<span class="sm">${esc(r.s)}</span>`;
  }).join("").replace(/\n/g, "<br>");
}

/** 어절 도막에서 표·수식 표식을 자리표시로 바꾼다 */
function cleanRuns(runs, txt) {
  if (!runs) return runs;
  return runs.map((r) => ({ t: r.t, s: txt(r.s) }));
}

/** 엑셀 칸에 넣을 런 — 신구조문 대비표 양식 (바뀐 대목만 밑줄) */
function cellRunsOfficial(parts) {
  // xlsx.js 는 {mark, s} 를 받는다 — 바뀐 대목만 밑줄
  return (parts || []).map((r) => ({ mark: r.t === "+", s: r.s }));
}

/* ============================================================
   항 단위로 접기 — 신구조문 대비표 양식
   ------------------------------------------------------------
   ①②③ 로 나뉜 조문에서 바뀐 항만 적고, 잇달아 그대로인 항은 한 줄로
   접는다. 샘플이 그렇게 적는다 — 안 바뀐 것을 죄다 되풀이하면 표가
   길어져 정작 무엇이 바뀌었는지 보이지 않는다.

     현행    ①∼③(생략)        ④ 바뀐 항 전문 …
     개정안  ①∼③(현행과 같음)  ④ 바뀐 항 …(줄표)…

   항이 하나뿐이거나 ① 표시가 없는 조문은 접지 않는다 (null 을 돌려준다).
   ============================================================ */
const HANG_CH = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";

/** 본문을 항 단위로 자른다 — [{mark, text, start, end}] */
function splitHang(body) {
  const t = String(body || "");
  const at = [];
  for (let i = 0; i < t.length; i += 1) {
    if (HANG_CH.indexOf(t[i]) >= 0) at.push(i);
  }
  if (at.length < 2) return null;                 // 항이 둘은 되어야 접을 값이 있다
  const out = [];
  if (at[0] > 0) out.push({ mark: "", text: t.slice(0, at[0]), start: 0, end: at[0] });
  for (let k = 0; k < at.length; k += 1) {
    const s = at[k], e = k + 1 < at.length ? at[k + 1] : t.length;
    out.push({ mark: t[s], text: t.slice(s, e), start: s, end: e });
  }
  return out;
}

/** 어느 항이 바뀌었는가 — 옛 글 기준 자리로 가린다 */
function changedHang(segs, runs) {
  const hit = new Set();
  if (!runs) return hit;
  let off = 0;
  for (const r of runs) {
    if (r.t === "=") { off += r.s.length; continue; }
    if (r.t === "-") {
      const from = off, to = off + r.s.length;
      segs.forEach((g, i) => { if (g.end > from && g.start < to) hit.add(i); });
      off = to;
    } else {
      // 넣은 말은 옛 글에 자리가 없다 — 그 자리에 닿는 항을 짚는다
      segs.forEach((g, i) => { if (g.start <= off && off <= g.end) hit.add(i); });
    }
  }
  return hit;
}

/** 잇달아 그대로인 항을 ①∼③ 꼴로 */
function rangeLabel(segs, from, to) {
  const a = segs[from].mark, b = segs[to].mark;
  if (!a && !b) return "";
  if (from === to) return a || "";
  return `${a}∼${b}`;
}

function foldByHang(beforeBody, afterBody, runs) {
  const segs = splitHang(beforeBody);
  if (!segs) return null;
  const hit = changedHang(segs, runs);
  if (!hit.size || hit.size === segs.length) return null;   // 접을 것이 없다

  const cur = [], rev = [];
  let i = 0;
  while (i < segs.length) {
    if (hit.has(i)) {
      cur.push(...beforeRunsIn(runs, segs[i].start, segs[i].end), { t: "=", s: NLC });
      rev.push({ t: "=", s: segs[i].mark ? segs[i].mark + " " : "" },
               { t: "=", s: dashes(segs[i].text) + NLC });
      i += 1;
      continue;
    }
    let j = i;
    while (j + 1 < segs.length && !hit.has(j + 1)) j += 1;
    const lab = rangeLabel(segs, i, j);
    cur.push({ t: "=", s: lab }, { t: "omit", s: "(생략)" }, { t: "=", s: NLC });
    rev.push({ t: "=", s: lab }, { t: "omit", s: "(현행과 같음)" }, { t: "=", s: NLC });
    i = j + 1;
  }
  return { cur, rev };
}

/** 옛 글의 [start,end) 구간에 걸친 도막만 — 바뀔 대목은 '-' 로 표시 */
function beforeRunsIn(runs, start, end) {
  if (!runs) return [{ t: "=", s: "" }];
  const out = [];
  let off = 0;
  for (const r of runs) {
    if (r.t === "+") continue;                    // 넣은 말은 옛 글에 없다
    const a = off, b = off + r.s.length;
    off = b;
    if (b <= start || a >= end) continue;
    const piece = r.s.slice(Math.max(0, start - a), Math.min(r.s.length, end - a));
    if (piece) out.push({ t: r.t === "-" ? "-" : "=", s: piece });
  }
  return out.length ? out : [{ t: "=", s: "" }];
}
