/* ============================================================
   ui/detail.js — 조문 상세 패널
   ============================================================ */
import * as M from "../core/model.js?v=20260906a";
import { wordDiff, beforeRuns, afterRuns, hasChange } from "../core/textdiff.js?v=20260906a";
import { imgIdsIn, renderBody, fitTable, toHtml, openTableOverlay, markAnnexEdits }
  from "../core/objects.js?v=20260906a";

/** 만들고 있는 안을 부르는 말 — 작업규정은 개정안, 성과심사 규정은 개정안 */
/* 만들어 내는 안을 부르는 말 — 규정마다 다르다 (작업규정은 '개정안', 나머지는 '개정안').
   편집기를 합치면서 화면 하나가 세 규정을 오가므로, 손대는 규정이 바뀔 때 갈아 끼운다. */
let WORD = "개정안";
export function setWord(w) { if (w) WORD = w; }

const STATUSES = M.STATUSES;
/** 본문 속 표·수식 자리표시 — 밑줄 비교에서는 글자로 드러내지 아니한다 */
const RE_IMG_TAG = /<img\s+id="[\w.-]+"\s*>(?:<\/img>)?/gi;
export const MAX_MB = 8;          // 서식 파일 한 건 최대 크기

/** 표·수식 표식을 뺀 글 — 밑줄 비교에서는 글자로 드러내지 아니한다 */
const noImg = (s) => String(s || "").replace(RE_IMG_TAG, "");

function fmtSize(n) {
  if (!n) return "";
  return n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const KIND_CLASS = {
  "신설": "k-new", "삭제": "k-del", "이동": "k-mov", "순서": "k-mov",
  "수정": "k-edit", "통합": "k-mrg", "참조삽입": "k-ref", "상태변경": "k-keep",
  "되돌림": "k-undo", "다시실행": "k-redo",
};

/** 조문 단위 변경 이력 타임라인 */
function historyBlock(node) {
  const wrap = document.createElement("div");
  wrap.className = "fld hist";
  const list = (node.history || []).slice().reverse();
  wrap.innerHTML = `<label>변경 이력 <span class="cnt">${list.length}</span></label>`;

  if (!list.length) {
    const e = document.createElement("div");
    e.className = "hist-empty";
    e.textContent = "아직 변경 이력이 없습니다.";
    wrap.appendChild(e);
    return wrap;
  }

  const ul = document.createElement("div");
  ul.className = "hist-list";
  ul.innerHTML = list.map((h) => `
    <div class="hist-row${h.cascade ? " cascade" : ""}">
      <span class="dot ${KIND_CLASS[h.kind] || ""}"></span>
      <div class="hist-main">
        <div class="hist-top">
          <span class="tag ${KIND_CLASS[h.kind] || ""}">${esc(h.kind)}</span>
          <span class="hist-at">${fmtDT(h.at)}</span>
          ${h.v ? `<span class="hist-v">${esc(h.v)}</span>` : ""}
          ${h.by ? `<span class="hist-by">${esc(h.by)}</span>` : ""}
        </div>
        <div class="hist-detail">${esc(h.detail || "")}${h.cascade ? " <i>(상위 항목과 함께)</i>" : ""}</div>
      </div>
    </div>`).join("");
  wrap.appendChild(ul);
  return wrap;
}

/** 대역이 있으면 번역문을, 없으면 원문을 쓴다 */
function textOf(node, field) {
  if (!node) return "";
  const t = field === "title" ? (node.transTitle || node.title) : (node.transBody || node.body);
  return String(t || "");
}
function runsHtml(runs) {
  return runs.map((r) => (r.mark ? `<u class="mk">${esc(r.s)}</u>` : esc(r.s))).join("");
}

import { linkReason, wireReasonLinks } from "../core/reasonlink.js?v=20260906a";
import { esc, fmtDT } from "./html.js?v=20260906a";
import { renderPdf } from "./pdfview.js?v=20260906a";

/** 사유 글이 스스로 머리글을 달고 있는가 — 그러면 딱지를 겹쳐 붙이지 아니한다 */
const RE_REASON_HEAD = /^\s*\[변경 사유\]/;

export class DetailPanel {
  constructor(bodyEl, pathEl, { onApply, onAnnexFile, getAsset, resolveCite, onCite, annexIndex = null } = {}) {
    this.body = bodyEl;
    this.path = pathEl;
    this.onApply = onApply;
    this.onAnnexFile = onAnnexFile;    // (nodeId, File|null)
    this.getAsset = getAsset;          // (assetId) => {name,mime,size,data,at,by}
    this.resolveCite = resolveCite;    // (규정명) => 규정 id | null
    this.resolveLaw = null;            // (약칭) => {id, name} | null
    this.onCite = onCite;              // (규정 id, 규정명) => 참조규정 창에서 열기
    this.annexIndex = annexIndex;      // { regId: { "별표1": ["별표1_1.webp", …] } }
    this.current = null;
  }

  setAnnexIndex(idx) { this.annexIndex = idx; }
  /** 본문 속 표·수식 저장소 (core/objects.js 의 ObjectStore) */
  setObjectStore(store) { this.objects = store; }
  /** 개정안 트리의 별표 미리보기가 볼 기준 규정 id */
  setBaseRegId(id) { this.baseRegId = id; }
  /** 신설 별표의 서식이 놓인 자리 — 번호가 같은 현행 별표를 끌어오지 아니한다 */
  setDraftRegId(id) { this.draftRegId = id; }

  /** 본문을 원문 순서대로 — <img id> 자리에 진짜 표·수식을 끼워 그린다 */
  _bodyView(node, regId, label = "본문") {
    regId = regId || this.baseRegId;      // 개정안(읽기 전용)은 기준 규정의 표를 쓴다
    const wrap = document.createElement("div");
    wrap.className = "fld";
    const n = imgIdsIn(node.body).length;
    wrap.innerHTML = `<label>${esc(label)}${n ? ` <span class="cnt">표·수식 ${n}</span>` : ""}</label>
      <div class="body-rich"></div>`;
    const host = wrap.querySelector(".body-rich");
    if (!node.body) {
      host.innerHTML = `<div class="bd-text mut">(하위 조문 참조)</div>`;
      return wrap;
    }
    renderBody(node.body, regId, this.objects, this._citeOpts(regId)).then((frag) => {
      host.replaceChildren(frag);
      fitTable(host);
    });
    return wrap;
  }

  /** 약칭 법령 인용(법 제7조 …)을 풀 함수 */
  setLawResolver(fn) { this.resolveLaw = fn; }

  /** 표준 인용(ISO 19157-1:2023 …)을 풀 함수 */
  setStdResolver(fn) { this.resolveStd = fn; }

  /** 같은 규정 안의 제○조 인용을 오갈 함수 — {has(docId,no), go(docId,no)} */
  setJoNav(nav) { this.joNav = nav; }

  _citeOpts(docId = null) {
    return {
      resolveCite: this.resolveCite,
      resolveLaw: this.resolveLaw,
      resolveStd: this.resolveStd,
      onCite: (id, name, jo, clause) => this.onCite?.(id, name, jo, clause),
      hasJo: docId && this.joNav ? (no) => this.joNav.has(docId, no) : null,
      onJo: (no) => this.joNav?.go(docId, no),
      /* 본문 속 별표·별지도 눌러 갈 수 있게 한다. 지금까지는 변경 사유에서만
         되어, 정작 규정 본문에서 별표를 부를 때에는 찾아 헤매야 했다.
         개정안 트리에서 찾으므로 docId 는 넘기지 않는다(null). */
      hasAnx: this.joNav?.hasAnx ? (g, no) => this.joNav.hasAnx(null, g, no) : null,
      onAnx: (g, no) => this.joNav?.goAnx?.(null, g, no),
      /* <현행 제N조에서 옮김> — 개정안 제2조에 거두어 모은 약칭이 본디
         어느 조문에 있었는지. 눌러 현행규정 창에서 그 조문을 편다. */
      onMoved: (jo) => this.onMoved?.(jo),
    };
  }

  /** <현행 제N조에서 옮김> 을 눌렀을 때 부를 함수 */
  setMovedNav(fn) { this.onMoved = fn; }

  /**
   * 조문이 현행과 달라진 곳 — 바뀐 말을 푸르게 짚어 보인다.
   *
   * 본문을 그대로 보면 어디가 바뀐 것인지 알 수 없어, 개정 전후를 견주려면
   * 두 창을 나란히 놓아야 했다. 바뀐 조문에는 현행 본문을 함께 담아 두므로
   * (gendraft2025.py 의 wasBody) 한 창에서 바로 짚어 보인다.
   * 별표는 붉게, 조문은 푸르게 — 무엇이 바뀐 것인지 한눈에 갈린다.
   */
  _bodyDiff(node) {
    const was = node.wasBody || "";
    const now = node.body || "";
    if (!was || was === now) return null;
    const runs = wordDiff(noImg(was), noImg(now));
    if (!hasChange(runs)) return null;
    const box = document.createElement("div");
    box.className = "fld body-diff";
    box.innerHTML = `<label>현행과 달라진 곳
        <span class="cnt">바뀐 말에 표시했습니다</span></label>
      <div class="body-view">
        <div class="bd-row"><span class="bd-tag">현행</span><div class="bd-txt">${
          runsHtml(beforeRuns(runs))}</div></div>
        <div class="bd-row"><span class="bd-tag new">${WORD}</span><div class="bd-txt">${
          runsHtml(afterRuns(runs))}</div></div>
      </div>`;
    return box;
  }

  /**
   * 한글 대역 — 옛 옮김본에서 손본 곳이 있으면 바뀐 말을 푸르게 짚어 보인다.
   *
   * 준칙 UAV 레이저 측량 장은 2025년판을 담되 우리말은 2023년 옮김본에서
   * 가져왔다. 판이 바뀌며 글이 달라진 조는 문구를 손볼 수밖에 없었는데,
   * 손본 글만 보이면 무엇을 건드린 것인지 알 수 없다. 옛 문구를 함께 담아
   * 두었으므로(transWasBody) 조문의 개정 표시와 같은 방식으로 짚어 보인다.
   */
  /**
   * 한글 대역. 원문에 표·수식이 있으면 **번역에도 그대로 끼워 그린다.**
   *
   * 여태는 글자만 내보내어 `<img id="loc11t0007">` 가 글로 드러났다.
   * 원문 쪽(_bodyView)과 똑같이 renderBody 로 개체를 풀어 준다.
   */
  _transView(node, regId) {
    regId = regId || this.baseRegId;
    const b = document.createElement("div");
    const was = node.transWasBody || "";
    const now = node.transBody || "";
    const n = imgIdsIn(now).length;
    const runs = was && was !== now ? wordDiff(noImg(was), noImg(now)) : null;
    const draw = (host) => {
      // ko: true —— 표도 우리말로 옮긴 것을 그린다 (없으면 원문 표)
      renderBody(now, regId, this.objects,
                 { ...this._citeOpts(regId), ko: true }).then((frag) => {
        host.replaceChildren(frag);
        fitTable(host);
      });
    };
    if (!runs || !hasChange(runs)) {
      b.className = "fld";
      b.innerHTML = `<label>본문 (한글 대역)${
        n ? ` <span class="cnt">표·수식 ${n}</span>` : ""}</label>`
        + `<div class="body-rich ko"></div>`;
      draw(b.querySelector(".body-rich"));
      return b;
    }
    b.className = "fld body-diff";
    b.innerHTML = `<label>본문 (한글 대역)
        <span class="cnt">옛 옮김본에서 손본 말에 표시했습니다</span></label>
      <div class="body-view ko">
        <div class="bd-row"><span class="bd-tag">옮김본</span><div class="bd-txt">${
          runsHtml(beforeRuns(runs))}</div></div>
        <div class="bd-row"><span class="bd-tag new">손봄</span><div class="bd-txt">${
          runsHtml(afterRuns(runs))}</div></div>
      </div>${n ? `<div class="body-rich ko"></div>` : ""}`;
    // 견줌 표시는 글자만 다루므로 개체가 빠진다. 표는 아래에 따로 그린다.
    if (n) draw(b.querySelector(".body-rich"));
    return b;
  }

  /**
   * 별표·별지가 현행과 달라진 곳 — 바뀐 말을 붉게 짚어 보인다.
   *
   * 별표는 서식 파일이 따로 있어 본문 비교가 되지 아니한다. 그래서 무엇이
   * 달라졌는지 알기 어려웠다. 적어도 이름이 바뀐 것은 짚어 보인다.
   */
  _annexDiff(node) {
    const was = node.wasTitle || "";
    const now = node.title || "";
    if (!was || was === now) return null;
    const runs = wordDiff(was, now);
    if (!hasChange(runs)) return null;
    const box = document.createElement("div");
    box.className = "fld anx-diff";
    box.innerHTML = `<label>현행과 달라진 곳</label>
      <div class="body-view">
        <div class="anx-row"><span class="anx-tag">현행</span>${
          runsHtml(beforeRuns(runs))}</div>
        <div class="anx-row"><span class="anx-tag new">${WORD}</span>${
          runsHtml(afterRuns(runs))}</div>
      </div>`;
    return box;
  }

  /** 사유 글을 링크가 박힌 HTML 로 — 어느 창에서나 같은 규칙을 쓴다
   *
   *  사유에 적힌 번호는 개정안의 번호다(현행 번호는 앞에 '현행' 이 붙어 있고,
   *  그런 자리는 linkReason 이 잇지 아니한다). 그러므로 규정 id 를 넘기지 아니하여
   *  참조 창이 아닌 개정안 트리에서 찾게 한다.
   */
  _reasonHtml(text) {
    const docId = null;
    return linkReason(text, {
      hasJo: (no) => !this.joNav || this.joNav.has(docId, no),
      hasAnx: (g, no) => !this.joNav?.hasAnx || this.joNav.hasAnx(docId, g, no),
      // ISO 19157-1:2023 처럼 맨몸으로 적힌 표준 — 인용이 본문보다 사유에 훨씬 많다
      resolveStd: this.resolveStd,
    });
  }

  /** 그 글 안의 링크에 누름 동작을 붙인다 — 개정안 트리로 옮겨 준다 */
  _wireReason(host) {
    const docId = null;
    wireReasonLinks(host, {
      onCite: (id, name, jo, clause) => this.onCite?.(id, name, jo, clause),
      onJo: (no) => this.joNav?.go(docId, no),
      onAnx: (g, no) => this.joNav?.goAnx?.(docId, g, no),
    });
  }

  /**
   * 변경 사유 — 평소엔 조문·별표를 링크로 이어 보여 주고, 누르면 글자를 고친다.
   * 본문과 같은 틀로 만들어 쓰는 법이 다르지 아니하게 한다.
   */
  _reasonEditor(node) {
    const wrap = document.createElement("div");
    wrap.className = "fld reason-edit";
    wrap.innerHTML = `<label>변경 사유
        <button class="mini2 rs-toggle" type="button">고치기</button></label>
      <div class="reason-view body-view"></div>`;
    const host = wrap.querySelector(".reason-view");
    const btn = wrap.querySelector(".rs-toggle");

    let text = node.reason || "";
    const draw = () => {
      host.innerHTML = this._reasonHtml(text) || '<span class="mut">(사유 없음)</span>';
      this._wireReason(host);
    };
    draw();

    btn.onclick = () => {
      const editing = wrap.classList.toggle("editing");
      btn.textContent = editing ? "미리보기" : "고치기";
      if (editing) {
        const ta = document.createElement("textarea");
        ta.className = "f-reason";
        ta.rows = 12;
        ta.value = text;
        ta.oninput = () => { text = ta.value; };
        host.replaceChildren(ta);
        ta.focus();
      } else {
        draw();
      }
    };
    wrap.getReason = () => text;
    return wrap;
  }

  /** 개정안 본문 — 평소엔 표까지 그려 보여 주고, 누르면 글자를 고친다 */
  _bodyEditor(node) {
    const wrap = document.createElement("div");
    wrap.className = "fld body-edit";
    const n = imgIdsIn(node.body).length;
    wrap.innerHTML = `<label>본문${n ? ` <span class="cnt">표·수식 ${n}</span>` : ""}
        <button class="mini2 bd-toggle" type="button">고치기</button></label>
      <div class="body-rich"></div>`;
    const host = wrap.querySelector(".body-rich");
    const btn = wrap.querySelector(".bd-toggle");

    // 트리를 직접 건드리지 않는다 — [적용] 을 눌러야 반영된다
    let text = node.body || "";
    const draw = () => {
      renderBody(text, this.baseRegId, this.objects, this._citeOpts(this.baseRegId)).then((frag) => {
        host.replaceChildren(frag);
        fitTable(host);
      });
    };
    draw();

    btn.onclick = () => {
      const editing = wrap.classList.toggle("editing");
      btn.textContent = editing ? "미리보기" : "고치기";
      if (editing) {
        const ta = document.createElement("textarea");
        ta.className = "f-body";
        ta.rows = 15;
        ta.value = text;
        ta.spellcheck = false;
        host.replaceChildren(ta);
        ta.focus();
      } else {
        const ta = host.querySelector("textarea");
        if (ta) text = ta.value;
        draw();
      }
    };
    wrap.getBody = () => host.querySelector("textarea")?.value ?? text;
    return wrap;
  }

  /** 바뀐 서식 파일 올리기 블록 */
  _annexUpload(node) {
    const wrap = document.createElement("div");
    wrap.className = "fld annex-up";
    const a = this.getAsset?.(node.annexRef?.newFileId);

    wrap.innerHTML = `<label>바뀐 서식 파일</label>
      ${a ? `<div class="up-card">
          <div class="up-main">
            <b>${esc(a.name)}</b>
            <div class="up-meta">${fmtSize(a.size)}${a.by ? ` · ${esc(a.by)}` : ""} · ${fmtDT(a.at)}</div>
          </div>
          <a class="btnlink" download="${esc(a.name)}" href="${esc(a.data)}">내려받기</a>
          <button class="mini2" data-up="del" title="첨부 떼기">✕</button>
        </div>
        ${/^image\//.test(a.mime) ? `<div class="annex-preview up-img"><figure>
            <img src="${esc(a.data)}" alt="${esc(a.name)}"></figure></div>` : ""}`
        : `<div class="up-empty">아직 올린 파일이 없습니다.</div>`}
      <div class="up-actions">
        <button class="mini2" data-up="pick">${a ? "다른 파일로 바꾸기" : "＋ 파일 올리기"}</button>
        <span class="mut">HWP · HWPX · PDF · 이미지 — 한 건에 ${MAX_MB}MB 까지</span>
      </div>
      <input type="file" class="up-input hidden"
             accept=".hwp,.hwpx,.pdf,.png,.jpg,.jpeg,.webp,.gif,.xlsx,.docx">`;

    const input = wrap.querySelector(".up-input");
    wrap.querySelector('[data-up="pick"]').onclick = () => { input.value = ""; input.click(); };
    input.onchange = () => {
      const f = input.files && input.files[0];
      if (f) this.onAnnexFile?.(node.id, f);
    };
    const del = wrap.querySelector('[data-up="del"]');
    if (del) del.onclick = () => {
      if (confirm(`「${a.name}」 첨부를 뗍니다. 계속할까요?`)) this.onAnnexFile?.(node.id, null);
    };
    return wrap;
  }

  /** 별표·별지 원본 표 — HWP 에서 뽑아 둔 XML 을 진짜 표로 그린다 */
  _annexTables(node, regId) {
    regId = regId || this.baseRegId;
    const key = node.legacyNo || `${node.annexRef.gubun}${node.annexRef.no}`;
    // 신설 별표는 개정안 전용 자리에서만 찾는다 —
    // 번호로만 찾으면 같은 번호의 현행 별표를 끌어온다
    if (node.status === "신설") {
      if (!this.draftRegId) return null;
      regId = this.draftRegId;
    }
    const meta = this.objects && this.objects.annexMeta(regId, key);
    if (!meta) return null;

    // 이번 개정으로 새로 두는 별표ㆍ별지는 붉게 둘러 신설임을 드러낸다
    const isNew = node.status === "신설";
    const wrap = document.createElement("div");
    wrap.className = isNew ? "fld anx-new" : "fld";
    wrap.innerHTML = `<label>서식 표 ${
        isNew ? `<span class="anx-badge">신설</span> ` : ""}<span class="cnt">${meta.tables}개</span>
        <a class="btnlink lbl-right" href="${esc(this.objects.annexUrl(regId, key))}"
           download="${esc(meta.file)}">XML</a></label>${
      isNew ? `<div class="anx-new-note">이번 개정으로 새로 두는 ${
        esc(node.annexRef.gubun)}입니다 — 현행 규정에는 없습니다.</div>` : ""}
      <div class="annex-tbl"><span class="mut">읽는 중…</span></div>`;

    const host = wrap.querySelector(".annex-tbl");
    this.objects.getAnnex(regId, key).then((o) => {
      if (!o) { host.innerHTML = `<div class="obj-fail">표를 읽지 못했습니다.</div>`; return; }
      host.innerHTML = toHtml(o);
      // 개정안의 별표라면 바뀌는 문구를 붉게 드러낸다
      const edits = Array.isArray(node.annexEdits) ? node.annexEdits : null;
      if (edits && edits.length) {
        const applied = markAnnexEdits(host, edits);
        wrap.insertBefore(this._annexEditLegend(applied), host);
      }
      // 새로 두는 비고 — 표마다 되풀이 적지 아니하고 한 자리에 모은 것.
      // 심사기준표는 머리에, 서식(명세서)은 원래 비고가 있던 아래에 붙인다
      if (Array.isArray(node.annexNotes) && node.annexNotes.length) {
        const foot = node.annexNotesAt === "foot";
        const box = this._annexNotes(node.annexNotes, foot);
        if (foot) host.appendChild(box);
        else host.insertBefore(box, host.firstChild);
      }
      fitTable(host);
      const zoom = document.createElement("button");
      zoom.className = "mini2";
      zoom.type = "button";
      zoom.textContent = "크게 보기";
      // 표시를 마친 화면 그대로 크게 본다
      zoom.onclick = () => openTableOverlay(
        host.innerHTML.replace(/<button[^>]*>.*?<\/button>/gi, ""),
        `${key} ${o.title || ""}`.trim());
      host.appendChild(zoom);
    });
    return wrap;
  }

  /**
   * 개정으로 새로 더하는 심사표 — 현행 서식에는 없던 표다.
   * 문구 교체로는 담을 수 없어 표를 통째로 새로 짓는다 (별표 3 의 레이저측량 심사표).
   */
  _annexExtra(node) {
    const key = node.annexAdd;
    if (!key || !this.draftRegId || !this.objects) return null;
    const meta = this.objects.annexMeta(this.draftRegId, key);
    if (!meta) return null;

    const wrap = document.createElement("div");
    wrap.className = "fld anx-extra";
    wrap.innerHTML = `<label>새로 더하는 심사표 <span class="cnt">${meta.tables}개</span>
        <a class="btnlink lbl-right" href="${esc(this.objects.annexUrl(this.draftRegId, key))}"
           download="${esc(meta.file)}">XML</a></label>
      <div class="annex-tbl"><span class="mut">읽는 중…</span></div>`;

    const host = wrap.querySelector(".annex-tbl");
    this.objects.getAnnex(this.draftRegId, key).then((o) => {
      if (!o) { host.innerHTML = `<div class="obj-fail">표를 읽지 못했습니다.</div>`; return; }
      host.innerHTML = toHtml(o);
      fitTable(host);
      const zoom = document.createElement("button");
      zoom.className = "mini2";
      zoom.type = "button";
      zoom.textContent = "크게 보기";
      zoom.onclick = () => openTableOverlay(toHtml(o), `${node.legacyNo || ""} 새로 더하는 심사표`.trim());
      host.appendChild(zoom);
    });
    return wrap;
  }

  /** 새로 두는 비고 — 표 앞(머리) 또는 뒤(서식 아래)에 붉게 붙인다 */
  _annexNotes(notes, foot = false) {
    const el = document.createElement("div");
    el.className = `anx-note${foot ? " foot" : ""}`;
    el.innerHTML = `<div class="anx-note-head">비고 <span class="mut">— ${
        foot ? "서식 아래에" : "별표 머리에"} 새로 둡니다</span></div>
      <ol>${notes.map((n) => `<li><ins class="anx-ins">${esc(n)}</ins></li>`).join("")}</ol>`;
    return el;
  }

  /** 별표에서 무엇을 붉게 바꾸었는지 — 표 위에 붙이는 안내 */
  _annexEditLegend(applied) {
    const el = document.createElement("div");
    el.className = "anx-legend";
    const total = applied.reduce((s, e) => s + e.hits, 0);
    const rows = applied.map((e) => {
      const what = e.add ? `<ins class="anx-ins">${esc(e.add)}</ins> 를 덧붙인다`
        : e.to ? `<del class="anx-del">${esc(e.find)}</del> → <ins class="anx-ins">${esc(e.to)}</ins>`
        : `<del class="anx-del">${esc(e.find)}</del> 를 뺀다`;
      const where = e.hits ? `${e.hits}곳` : `<span class="mut">표에서 찾지 못함</span>`;
      return `<li>${what} <span class="n">${where}</span>${
        e.why ? `<div class="why">${esc(e.why)}</div>` : ""}</li>`;
    }).join("");
    el.innerHTML = `<div class="anx-legend-head">
        <b>이번 개정으로 바뀌는 문구</b>
        <span class="mut">붉은 글씨 — 아래 표에 ${total}곳 표시했습니다</span>
      </div><ul>${rows}</ul>`;
    return el;
  }

  /** 곁에 둔 파일인가 — 밖(law.go.kr)의 것과 갈라 본다 */
  static _isLocal(p) { return !!p && !/^https?:/i.test(p); }

  /** 길에 한글이 섞여 있으므로 마디마다 따로 감싼다 (‘/’ 는 살려 둔다) */
  static _fileUrl(p) {
    return String(p || "").split("/").map(encodeURIComponent).join("/");
  }

  /** 별표·별지의 내려받기 단추 — 곁의 것은 정말 내려받게 한다 */
  _annexLinks(node) {
    const a = node.annexRef || {};
    const one = (p, label) => {
      if (!p) return "";
      const url = DetailPanel._fileUrl(p);
      const name = decodeURIComponent(String(p).split("/").pop());
      return DetailPanel._isLocal(p)
        ? `<a class="btnlink" href="${esc(url)}" download="${esc(name)}">${label} 내려받기</a>`
        : `<a class="btnlink" href="${esc(p)}" target="_blank" rel="noopener">${label} 내려받기</a>`;
    };
    /* 원본을 모두 .hwpx 로 바꾸었다. .hwp 를 이고 있는 옛 자료도 있을 수
       있으므로 둘 다 보되, 같은 문서를 두 번 내주지는 아니한다. */
    const links = [one(a.hwpx, "HWPX"), one(a.hwpx ? "" : a.hwp, "HWP"),
                   one(a.pdf, "PDF")].filter(Boolean).join(" ");
    const note = a.gen
      ? `<span class="mut">본문 글로 지은 서식입니다 — 조판은 한글에서 다듬으십시오.</span>`
      : a.src ? `<span class="mut">${esc(a.src)}</span>` : "";
    return `<div class="annex-links">${
      links || "<span class='mut'>제공되는 파일이 없습니다.</span>"}${note ? " " + note : ""}</div>`;
  }

  /** 별표 미리보기 — PDF 가 곁에 있으면 통째로, 없으면 그림으로 */
  _annexPreview(node, docId) {
    docId = docId || this.baseRegId;
    const bin = this.annexIndex || {};
    const mine = this.draftRegId || "draft2025";
    // 판마다 별표 번호가 겹치므로, 노드가 제 미리보기 자리를 들고 있으면 그것을 쓴다
    const own = node.annexRef && node.annexRef.previewDir;
    const self = `${node.annexRef.gubun}${node.annexRef.no}`.replace(/\s+/g, "");
    /* 열쇠를 무엇으로 삼는가
     *
     *   제 미리보기 자리가 있으면  → **제 번호**로 찾는다.
     *     그 자리의 그림은 그 마디의 번호로 지어 두었다(별표15_1.webp).
     *   그렇지 않으면            → 현행 번호(legacyNo)로 찾는다.
     *     자리를 옮긴 별표는 현행 규정의 자리에 현행 번호로 담겨 있다.
     *
     * 신설 별표에 legacyNo 가 붙어 있는 일이 있다 — 앞선 초안에서 쓰던
     * 번호다(별표 15 ← 별표 46). 그것을 열쇠로 삼으면 옛 번호가 찍힌
     * 그림을 보여 주므로, 제 자리가 있을 때에는 제 번호를 앞세운다. */
    const legacy = (node.legacyNo || self).replace(/\s+/g, "");
    const key = (own && bin[own] && bin[own][self]) ? self : legacy;
    const where = (own && bin[own] && bin[own][key]) ? own
      : ((node.status === "신설" && bin[mine] && bin[mine][key]) ? mine : docId);
    const files = bin[where] && bin[where][key];
    const wrap = document.createElement("div");
    wrap.className = "fld";

    const pdf = node.annexRef && node.annexRef.pdf;
    const shots = (files || []).map((f, i) => `
        <figure>
          <img loading="lazy" src="data/${encodeURIComponent("annex")}/${
            encodeURIComponent(where)}/${encodeURIComponent(f)}"
               alt="${esc(node.title)} ${i + 1}쪽">
          ${files.length > 1 ? `<figcaption>${i + 1} / ${files.length}</figcaption>` : ""}
        </figure>`).join("");

    // 그림이 PDF 와 다른 것을 담고 있을 때가 있다 — 이를테면 무인비행장치
    // 별표 8 의 둘째 쪽은 연구보고서의 신구대조표다. 그래서 접어 두되 남긴다.
    const shotsLabel = node.status === "신설" ? "연구보고서에 실린 쪽" : "원본 쪽 그림";
    const shotsOpen = false;

    if (DetailPanel._isLocal(pdf)) {
      // PDF 를 통째로 붙인다 — 한 쪽만 보이던 그림과 달리 끝까지 넘겨 볼 수 있다
      const url = DetailPanel._fileUrl(pdf);
      const pages = Number(node.annexRef.pages) || 0;
      wrap.innerHTML = `<label>미리보기 ${
          pages ? `<span class="cnt">${pages}쪽</span>` : ""}
          <a class="btnlink lbl-right" href="${esc(url)}" target="_blank"
             rel="noopener">새 창에서 크게 보기</a></label>
        <div class="annex-pdf" data-pdf="${esc(url)}"></div>
        ${shots ? `<details class="annex-shots"${shotsOpen ? " open" : ""}><summary>${
          esc(shotsLabel)} ${files.length}장 보기</summary><div class="annex-preview">${
          shots}</div></details>` : ""}`;
      wrap.querySelectorAll("img").forEach((img) => {
        img.onclick = () => window.open(img.src, "_blank", "noopener");
        img.onerror = () => { img.closest("figure").remove(); };
      });
      // 브라우저의 PDF 뷰어에 맡기지 아니하고 pdf.js 로 손수 그린다 —
      // 뷰어가 없거나 막힌 자리에서는 <iframe>·<object> 가 까만 칸만 남긴다
      renderPdf(wrap.querySelector(".annex-pdf"), url).then((n) => {
        const cnt = wrap.querySelector("label .cnt");
        if (n && cnt) cnt.textContent = `${n}쪽`;
      });
      return wrap;
    }

    if (!shots) {
      wrap.innerHTML = `<label>미리보기</label>
        <div class="annex-noimg">미리보기가 준비되지 않은 별표입니다.
        위의 내려받기 단추로 원본을 확인하세요.</div>`;
      return wrap;
    }
    wrap.innerHTML = `<label>미리보기 <span class="cnt">${files.length}쪽</span></label>
      <div class="annex-preview">${shots}</div>`;
    wrap.querySelectorAll("img").forEach((img) => {
      img.onclick = () => window.open(img.src, "_blank", "noopener");
      img.onerror = () => { img.closest("figure").remove(); };
    });
    return wrap;
  }

  /** 밖에서 [적용] 을 누를 수 있게 — 편집 폼이 떠 있을 때만 참 */
  canApply() { return typeof this._apply === "function"; }
  applyNow() {
    if (!this._apply) return false;
    this._apply();
    return true;
  }

  clear() {
    this._apply = null;
    this.current = null;
    this.path.textContent = "—";
    this.body.innerHTML = `<div class="empty">오른쪽 개정안 트리에서 항목을 선택하세요.</div>`;
  }

  /** 읽기 전용(참조 규정) 표시 */
  showReadonly(node, docName, trail, docId = null) {
    this._apply = null;
    this.current = null;
    this.path.textContent = trail || docName;
    const el = document.createElement("div");
    el.innerHTML = `<div class="readonly-note">참조 규정 · 읽기 전용 &nbsp;—&nbsp; <b>${esc(docName)}</b></div>`;

    el.appendChild(field("구분", M.displayLabel(node), true));
    el.appendChild(field("제목", node.title || "", true));
    if (node.transTitle && node.transTitle !== node.title) {
      const t = document.createElement("div");
      t.className = "fld";
      t.innerHTML = `<label>제목 (한글 대역)</label><div class="body-view ko">${esc(node.transTitle)}</div>`;
      el.appendChild(t);
    }

    if (node.annexRef) {
      const a = document.createElement("div");
      a.className = "fld";
      a.innerHTML = `<label>별표·서식 파일</label>${this._annexLinks(node)}`;
      el.appendChild(a);
      // 읽기 전용으로 볼 때에도 달라진 말을 짚어 보인다
      const ad = this._annexDiff(node);
      if (ad) el.appendChild(ad);
    }

    // 원본 서식이 있는 별표는 '현행 서식 표' 를, 신설 별표는 개정안 전용 자리에
    // 서식이 있을 때에만 붙인다 (_annexTables 가 가려낸다)
    if (node.annexRef && (node.annexRef.hwpx || node.annexRef.hwp || node.annexRef.pdf
        || node.status === "신설")) {
      const at = this._annexTables(node, docId);
      if (at) el.appendChild(at);
      const ax = this._annexExtra(node);
      if (ax) el.appendChild(ax);
    }
    // 미리보기는 신설 별표에도 붙인다 — 개정안 전용 자리에 그림이 있다
    if (node.annexRef && (node.annexRef.hwpx || node.annexRef.hwp || node.annexRef.pdf
        || this.annexIndex?.[node.annexRef.previewDir]
        || this.annexIndex?.[this.draftRegId || "draft2025"]?.[
             (node.legacyNo || `${node.annexRef.gubun}${node.annexRef.no}`).replace(/\s+/g, "")])) {
      el.appendChild(this._annexPreview(node, docId));
    }

    // 본문은 조문에, 그리고 글이 있는 별표·별지 모두에 보인다.
    // 여태는 원본 파일이 걸리면 글이 사라졌는데, 서식 파일과 규정 문언은
    // 서로 갈음하는 것이 아니라 나란히 보아야 하는 것이다.
    if (!node.annexRef || node.body) {
      el.appendChild(this._bodyView(node, docId, node.annexRef ? "내용" : "본문"));
    }

    {
      const bd = this._bodyDiff(node);
      if (bd) el.appendChild(bd);
    }

    if (node.transBody) {
      el.appendChild(this._transView(node, docId));
    }

    const note = document.createElement("div");
    note.className = "ref-origin";
    // 사유 글이 스스로 '[변경 사유]' 로 시작하면 딱지를 다시 붙이지 아니한다.
    // 사유 안의 조문·별표는 링크로 이어 준다 (읽기 전용이어도 오갈 수 있어야 한다)
    note.innerHTML = node.reason
      ? (RE_REASON_HEAD.test(node.reason)
          ? `<b>${this._reasonHtml(node.reason)}</b>`
          : `변경 사유 <b>${this._reasonHtml(node.reason)}</b>`)
      : `읽기 전용 항목입니다. 편집하려면 편집 가능한 버전으로 전환하거나, 참조 규정이라면 오른쪽 개정안 트리로 <b>끌어다 놓으세요</b>.`;
    el.appendChild(note);
    this._wireReason(note);

    if ((node.history || []).length) el.appendChild(historyBlock(node));

    this.body.replaceChildren(el);
  }

  /**
   * 현행규정 ↔ 참조규정 조문 나란히 비교
   * @param {object} a {node, docName, trail, docId}
   * @param {object} b 같은 형태
   */
  /**
   * 여러 창에서 고른 조문을 위아래로 나눠 보여 준다.
   * @param {Array<{key,badge,node,docName,trail,docId,editable}>} items
   *        key: "ref1" | "ref2" | "edit"
   */
  showPanels(items) {
    this._apply = null;
    if (!items.length) return this.clear();

    // 한 곳만 골랐으면 원래대로 온전히 보여 준다
    if (items.length === 1) {
      const it = items[0];
      return it.editable
        ? this.show(it.node, it.trail)
        : this.showReadonly(it.node, it.docName, it.trail, it.docId);
    }

    this.current = null;
    this.path.textContent = items.map((x) => `${x.badge} ${M.displayLabel(x.node)}`).join("  ↔  ");

    // 둘일 때만 낱말 단위로 다른 곳에 밑줄을 친다
    let tRuns = null, bRuns = null, same = false;
    if (items.length === 2) {
      // 표·수식 표식은 견주기 전에 지운다. 낱말로 쪼개진 뒤에 지우면
      // <img id="…"> 가 두 도막에 걸쳐 남아 글자 그대로 드러난다.
      tRuns = wordDiff(textOf(items[0].node, "title"), textOf(items[1].node, "title"));
      bRuns = wordDiff(noImg(textOf(items[0].node, "body")),
                       noImg(textOf(items[1].node, "body")));
      same = !hasChange(tRuns) && !hasChange(bRuns);
    }

    const wrap = document.createElement("div");
    wrap.className = "dt-stack";
    wrap.innerHTML = items.length === 2
      ? `<div class="rc-note ${same ? "same" : "diff"}">${same
          ? "두 조문의 제목과 본문이 같습니다."
          : "다른 부분에 <u class='mk'>밑줄</u>을 표시했습니다. 위쪽 밑줄은 위 조문에만, 아래쪽 밑줄은 아래 조문에만 있는 표현입니다."}</div>`
      : `<div class="rc-note">고른 ${items.length}곳을 위아래로 나눠 보여 줍니다. 같은 항목을 다시 누르면 그 선택이 풀립니다.</div>`;

    items.forEach((it, i) => {
      const box = document.createElement("section");
      box.className = `dt-panel ${it.key}`;
      const titleHtml = tRuns
        ? runsHtml(i === 0 ? beforeRuns(tRuns) : afterRuns(tRuns))
        : esc(textOf(it.node, "title"));

      box.innerHTML = `
        <header class="dt-head">
          <span class="dt-badge ${it.key}">${esc(it.badge)}</span>
          <b>${esc(it.docName)}</b>
          <span class="dt-label">${esc(M.displayLabel(it.node))}</span>
          <div class="spacer"></div>
          ${it.node.status && it.node.status !== "유지"
            ? `<span class="tag k-edit">${esc(M.statusLabel(it.node))}</span>` : ""}
        </header>
        <div class="dt-path">${esc(it.trail || "")}</div>
        <div class="dt-title">${titleHtml || "<span class='mut'>(제목 없음)</span>"}</div>
        <div class="dt-body"></div>
        ${it.node.reason
          ? `<div class="dt-reason">${RE_REASON_HEAD.test(it.node.reason)
              ? "" : "<b>변경 사유</b> "}${this._reasonHtml(it.node.reason)}</div>`
          : ""}`;

      const rs = box.querySelector(".dt-reason");
      if (rs) this._wireReason(rs);

      const host = box.querySelector(".dt-body");
      if (bRuns) {
        // 밑줄을 살리려면 글로만 그린다. 표·수식 표식은 이미 지웠고,
        // 진짜 표는 아래에 따로 붙인다.
        host.className = "dt-body pre";
        const runs = i === 0 ? beforeRuns(bRuns) : afterRuns(bRuns);
        host.innerHTML = runsHtml(runs).trim()
          || "<span class='mut'>(내용 없음)</span>";
        const ids = imgIdsIn(it.node.body);
        if (ids.length) {
          const extra = document.createElement("div");
          extra.className = "dt-objs";
          renderBody(it.node.body.replace(/[^]*?(?=<img)/, ""),
                     it.docId || this.baseRegId, this.objects,
                     this._citeOpts(it.docId || this.baseRegId))
            .then((frag) => { extra.replaceChildren(frag); fitTable(extra); });
          box.appendChild(extra);
        }
      } else {
        renderBody(it.node.body, it.docId || this.baseRegId, this.objects,
                   this._citeOpts(it.docId || this.baseRegId))
          .then((frag) => { host.replaceChildren(frag); fitTable(host); });
      }

      if (it.node.annexRef && (it.node.annexRef.hwpx || it.node.annexRef.hwp
                               || it.node.annexRef.pdf)) {
        const t = this._annexTables(it.node, it.docId);
        if (t) box.appendChild(t);
      }
      wrap.appendChild(box);
    });

    const foot = document.createElement("div");
    foot.className = "rc-foot";
    foot.textContent = "현행규정·참조규정과 개정안에서 고른 항목이 여기에 함께 나옵니다. "
      + "한 곳만 남기면 그 조문을 온전히 보고 고칠 수 있습니다.";
    wrap.appendChild(foot);

    this.body.replaceChildren(wrap);
    fitTable(this.body);
  }

  /** 편집 가능(개정안) 표시 */
  show(node, trail) {
    this._apply = null;
    this.current = node.id;
    this.path.textContent = trail || M.shortLabel(node);

    const el = document.createElement("div");

    const rowTop = document.createElement("div");
    rowTop.className = "row2";
    rowTop.appendChild(field("번호 (자동)", M.shortLabel(node), true));
    rowTop.appendChild(selectField("상태", STATUSES, node.status || "유지", "f-status"));
    el.appendChild(rowTop);

    const isAnnex = !!node.annexRef;

    el.appendChild(field("제목", node.title || "", false, "f-title",
      isAnnex ? "예) 기준점현황조사서"
              : node.level === "조" ? "예) 성과의 품질기준" : "예) 총칙"));

    if (isAnnex) {
      // 별표·별지 — 본문 대신 원본 파일과 미리보기를 보여 준다
      const a = document.createElement("div");
      a.className = "fld";
      a.innerHTML = `<label>별표·서식 파일</label>${this._annexLinks(node)}`;
      el.appendChild(a);
      const ad = this._annexDiff(node);
      if (ad) el.appendChild(ad);
      el.appendChild(textareaField("서식 변경 내용", node.body || "", "f-body", 6,
        "바뀐 항목·칸·단위 등을 적어 두면 개정 전후 비교표에 그대로 실립니다."));
      const at = this._annexTables(node, this.baseRegId);
      if (at) el.appendChild(at);
      const ax = this._annexExtra(node);
      if (ax) el.appendChild(ax);
      el.appendChild(this._annexUpload(node));
      el.appendChild(this._annexPreview(node, this.baseRegId));
    } else if (node.level === "조") {
      el.appendChild(this._bodyEditor(node));
      const bd = this._bodyDiff(node);
      if (bd) el.appendChild(bd);
    } else if (node.isAnnex) {
      const info = document.createElement("div");
      info.className = "fld";
      info.innerHTML = `<label>구성</label><div class="body-view">${
        node.children.length}건 — 아래 항목을 골라 고치거나, 이 묶음을 고른 채 [＋ 하위 신설] 로 새 ${
        esc(node.annexGubun || "별표")}를 만듭니다.</div>`;
      el.appendChild(info);
    } else {
      const info = document.createElement("div");
      info.className = "fld";
      info.innerHTML = `<label>구성</label><div class="body-view">${
        M.LEVELS.filter((l) => M.countBy(node.children, l))
          .map((l) => `${l} ${M.countBy(node.children, l)}`).join(" · ") || "하위 항목 없음"
      }</div>`;
      el.appendChild(info);
      // 편·장에도 설명이 있으면 표까지 그려 준다 (개편 근거 표 등)
      if (node.body) el.appendChild(this._bodyView(node, this.baseRegId, "설명"));
    }

    el.appendChild(this._reasonEditor(node));

    const acts = document.createElement("div");
    acts.className = "detail-actions";
    acts.innerHTML = `<button data-act="revert">되돌리기</button><button class="primary" data-act="apply">적용</button>`;
    el.appendChild(acts);

    const meta = document.createElement("div");
    meta.className = "ref-origin";
    const bits = [];
    if (node.legacyNo) bits.push(`현행 ${node.annexRef ? "번호" : "조번호"} <b>${esc(node.legacyNo)}</b>`);
    if (node.sourceRef) bits.push(`출처 <b>${esc(node.sourceRef.doc)}</b> ${esc(node.sourceRef.label)}`);
    bits.push(`내부 ID <b>${esc(node.id)}</b>`);
    meta.innerHTML = bits.join("<br>");
    el.appendChild(meta);

    el.appendChild(historyBlock(node));

    this.body.replaceChildren(el);

    const get = (c) => el.querySelector("." + c);
    const apply = () => {
      this.onApply?.(node.id, {
        title: get("f-title").value.trim(),
        body: el.querySelector(".body-edit")?.getBody?.()
           ?? (get("f-body") ? get("f-body").value : node.body),
        reason: (el.querySelector(".reason-edit")?.getReason?.()
                 ?? get("f-reason")?.value ?? node.reason ?? "").trim(),
        status: get("f-status").value,
      });
    };
    this._apply = apply;                 // 툴바의 [적용] 도 같은 일을 한다
    this.onFormReady?.();
    acts.querySelector('[data-act="apply"]').addEventListener("click", apply);
    acts.querySelector('[data-act="revert"]').addEventListener("click", () => this.show(node, trail));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); apply(); }
    });
  }
}

/* ---------- 헬퍼 ---------- */
function field(label, value, readonly, cls = "", ph = "") {
  const d = document.createElement("div");
  d.className = "fld";
  d.innerHTML = `<label>${esc(label)}</label>
    <input class="${cls}" value="${esc(value)}" placeholder="${esc(ph)}" ${readonly ? "readonly" : ""}>`;
  return d;
}
function textareaField(label, value, cls, rows, hint = "") {
  const d = document.createElement("div");
  d.className = "fld";
  d.innerHTML = `<label>${esc(label)}</label>
    <textarea class="${cls}" rows="${rows}">${esc(value)}</textarea>
    ${hint ? `<div style="font-size:10.5px;color:var(--muted);margin-top:3px">${esc(hint)}</div>` : ""}`;
  return d;
}
function selectField(label, options, value, cls) {
  const d = document.createElement("div");
  d.className = "fld";
  d.innerHTML = `<label>${esc(label)}</label><select class="${cls}">${
    options.map((o) => `<option${o === value ? " selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
  return d;
}
