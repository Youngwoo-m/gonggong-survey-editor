/* ============================================================
   ui/ai.js — AI 도우미 화면
   ------------------------------------------------------------
   AI 가 낸 것은 언제나 '제안'이다. 화면에서 확인하고 [적용] 을 눌러야
   트리에 들어가며, 들어간 뒤에는 여느 편집과 똑같이 되돌릴 수 있다.
   ============================================================ */
import * as M from "../core/model.js?v=20260904n";
import * as AI from "../adapters/ai.js?v=20260904n";
import { TASKS, outline, withExtra } from "../core/aitasks.js?v=20260904n";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** 답변 글을 아주 가볍게 꾸민다 — **굵게**, - 목록, 빈 줄로 문단 */
function richText(t) {
  const NL = String.fromCharCode(10);
  return esc(String(t || ""))
    .replace(/\*\*([^*\r\n]+)\*\*/g, "<b>$1</b>")
    .replace(/^#{1,4}\s+(.*)$/gm, "<h5>$1</h5>")
    .replace(/^\s*[-•]\s+(.*)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>")
    .split(new RegExp(`${NL}{2,}`))
    .map((para) => (/^\s*<(ul|h5)/.test(para) ? para : `<p>${para}</p>`))
    .join("")
    .replace(new RegExp(NL, "g"), "<br>")
    .replace(/<p>\s*<\/p>/g, "");
}

/** API 키 발급 안내 — 연결 전 화면과 [연결 설정] 양쪽에서 쓴다 */
const KEYGUIDE = `
<ol class="ai-steps">
  <li><b>계정 만들기</b> —
    <a href="https://console.anthropic.com/" target="_blank" rel="noopener">console.anthropic.com</a>
    에서 가입합니다. 회사 메일로 가입하면 팀 단위로 쓰기 편합니다.</li>
  <li><b>결제 수단 등록</b> — 왼쪽 메뉴 <b>Billing</b> 에서 카드를 넣고 크레딧을 채웁니다.
    무료 크레딧이 없으면 키를 만들어도 호출이 막힙니다.
    <span class="mut">처음에는 5~10달러면 충분합니다. 조문 다듬기 한 번이 수십 원 수준입니다.</span></li>
  <li><b>키 만들기</b> — 왼쪽 메뉴 <b>API keys</b> → <b>Create Key</b> 를 누르고 이름을
    (예: 공공측량-개정) 적습니다.</li>
  <li><b>키 복사</b> — <code>sk-ant-…</code> 로 시작하는 문자열이 <b>이때 한 번만</b> 보입니다.
    창을 닫으면 다시 볼 수 없으니 그 자리에서 복사하세요.</li>
  <li><b>여기에 붙여넣기</b> — 오른쪽 위 <b>[연결 설정]</b> → <b>API 키</b> 칸에 붙여넣고
    <b>[연결 확인]</b> 으로 확인한 뒤 <b>[저장]</b> 을 누릅니다.</li>
</ol>
<p class="mut">키는 이 브라우저(localStorage)에만 저장되고 <code>api.anthropic.com</code> 말고는
아무 데도 가지 않습니다. 다른 PC에서 쓰려면 그 PC에서 한 번 더 넣어야 합니다.
키가 새어 나갔다고 판단되면 Console 의 <b>API keys</b> 에서 그 키를 지우고 새로 만드세요.</p>`;

const TAG_CLASS = {
  "고친 곳": "k-edit", "살필 점": "k-mov", "이동": "k-mov", "통합": "k-mrg",
  "신설": "k-new", "유지": "k-keep", "중복": "k-mrg", "상충": "k-del",
  "확인필요": "k-edit", "빠짐": "k-new", "다름": "k-edit", "제외": "k-keep",
  "사유": "k-ref",
};

export class AIView {
  /**
   * @param {import("../core/project.js").Project} project
   * @param {{getRef:()=>({name:string,tree:Array}|null), onToast:Function, onJump:Function}} opts
   */
  constructor(project, { getRef, onToast, onJump, onReport, host = null } = {}) {
    this.project = project;
    this.getRef = getRef;
    this.onToast = onToast || (() => {});
    this.onJump = onJump;
    this.onReport = onReport;        // [보고서 생성] 을 누르면 부른다
    this.host = host;                // 있으면 별도 창이 아니라 그 자리에 붙인다
    this.usedHost = false;           // 이번에 붙박이로 열었는지 (팝업과 가른다)
    this.el = null;
    this.taskKey = "polish";
    this.result = null;
    this.busy = false;
    this.abort = null;
    this.extra = "";                 // 모든 작업에 덧붙이는 지시
    this.question = "";              // '직접 묻기' 물음
    this.picks = { node: true, subtree: false, outline: false, ref: false };
  }

  /**
   * @param {string=} taskKey  열면서 고를 작업
   * @param {{popup?:boolean}=} opt  popup 이면 붙박이 자리가 있어도 팝업으로 띄운다
   */
  open(taskKey, opt) {
    if (taskKey) this.taskKey = taskKey;
    const popup = !!opt?.popup;
    if (this.el) {                      // 붙박이는 다시 누르면 접는다
      const same = popup === !this.usedHost;
      if (this.host && !taskKey && same) { this.close(); return; }
      this.close();
    }
    // 상단 [보고서] 처럼 팝업으로 부르는 자리가 있다. 그때는 붙박이 자리를
    // 쓰지 아니한다 — 화면 아래에 접혀 있으면 눌러도 안 보이기 때문이다.
    this.usedHost = !!this.host && !popup;
    if (this.usedHost) {
      this.el = this.host;
      this.host.classList.remove("hidden");
    } else {
      this.el = document.createElement("div");
      this.el.className = "overlay";
      document.body.appendChild(this.el);
      this.el.addEventListener("click", (e) => {
        if (e.target === this.el && !this.busy) this.close();
      });
    }
    this._esc = (e) => { if (e.key === "Escape" && !this.busy) this.close(); };
    document.addEventListener("keydown", this._esc, true);
    this.render();
  }

  /** 열려 있는지 */
  get isOpen() { return !!this.el; }

  close() {
    this.abort?.abort();
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    if (this.usedHost) {
      this.host.classList.add("hidden");
      this.host.replaceChildren();
    } else {
      this.el?.remove();
    }
    this.usedHost = false;
    this.el = null;
    this.result = null;
    this.busy = false;
  }

  get task() { return TASKS.find((t) => t.key === this.taskKey) || TASKS[0]; }

  /* ---------- 화면 ---------- */
  render() {
    const p = this.project;
    const sel = p.selected;
    const ref = this.getRef?.();
    const t = this.task;
    const connected = AI.hasKey();

    this.el.innerHTML = `
<div class="cmp ai${this.usedHost ? " dock" : ""}">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">✦ AI 도우미</div>
      <div class="cmp-sub">
        <b>${esc(p.current?.label || "")}</b> ${esc(p.current?.title || "")}
        &nbsp;|&nbsp; AI 가 내는 것은 <b>제안</b>입니다. 확인하고 [적용] 을 눌러야 반영되며, 되돌릴 수 있습니다.
      </div>
    </div>
    <button class="x" data-x="close" title="접기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar">
    <div class="chips ai-tasks">
      ${TASKS.map((x) => `<span class="chip ${x.key === this.taskKey ? "on" : ""}" data-t="${x.key}">${esc(x.name)}</span>`).join("")}
    </div>
  </div>

  <div class="cmp-bar2">
    <span class="hint">${esc(t.hint)}</span>
    <div class="spacer"></div>
    <span class="ai-conn ${connected ? "on" : ""}">${connected
      ? `연결됨 · ${esc(AI.keyHint())}` : "연결 안 됨"}</span>
    <button data-x="report" title="지금 편집 상태 그대로 보고서 한 벌을 지어 zip 으로 내려받습니다 — 개정(안)·신구대조표·개정사유서·별표및별지목록">보고서 생성</button>
    <button data-x="setup">연결 설정</button>
    <button class="primary" data-x="run"${connected ? "" : " disabled"}>${t.free ? "물어보기" : "제안 받기"}</button>
  </div>

  <div class="cmp-body ai-body">${this.bodyHtml(t, sel, ref)}</div>
</div>`;

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.querySelector('[data-x="setup"]').onclick = () => this.setup();
    // 보고서 짓기는 AI 와 상관이 없다. 다만 웹에 올렸을 때 여기가 가장 눈에
    // 띄는 자리라 함께 둔다 — 상단 [보고서] 도 이 창을 띄운다.
    const rb = this.el.querySelector('[data-x="report"]');
    if (rb) {
      rb.onclick = async () => {
        rb.disabled = true;
        const was = rb.textContent;
        rb.textContent = "작성 중…";
        try { await this.onReport?.(); } finally {
          rb.disabled = false;
          rb.textContent = was;
        }
      };
    }
    this.el.querySelector('[data-x="run"]').onclick = () => this.run();
    this.el.querySelectorAll("[data-t]").forEach((c) => {
      c.onclick = () => { this.keepInputs(); this.taskKey = c.dataset.t; this.result = null; this.render(); };
    });
    this.el.querySelectorAll("[data-apply]").forEach((b) => {
      b.onclick = () => this.apply(b.dataset.apply);
    });
    this.el.querySelectorAll("[data-jump]").forEach((b) => {
      b.onclick = () => { const id = b.dataset.jump; this.close(); this.onJump?.(id); };
    });

    const ta = this.el.querySelector(".ai-ask");
    if (ta) {
      ta.oninput = () => { this.question = ta.value; };
      ta.onkeydown = (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); this.run(); }
      };
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    }
    const ex = this.el.querySelector(".ai-extra");
    if (ex) ex.oninput = () => { this.extra = ex.value; };
    this.el.querySelectorAll("[data-pick]").forEach((c) => {
      c.onchange = () => { this.picks[c.dataset.pick] = c.checked; this.render(); };
    });
  }

  /** 다시 그리기 전에 입력칸 값을 챙긴다 */
  keepInputs() {
    const ta = this.el?.querySelector(".ai-ask");
    if (ta) this.question = ta.value;
    const ex = this.el?.querySelector(".ai-extra");
    if (ex) this.extra = ex.value;
  }

  bodyHtml(t, sel, ref) {
    if (this.busy) {
      return `<div class="ai-wait"><div class="ai-dots"><i></i><i></i><i></i></div>
        <div>Claude 에게 물어보는 중입니다…</div>
        <div class="mut">규정이 크면 20초쯤 걸립니다.</div></div>`;
    }
    if (!AI.hasKey()) {
      return `<div class="ai-intro">
        <p><b>쓰기 전에 API 키를 넣어야 합니다.</b> 아래 순서로 5분이면 됩니다.</p>
        ${KEYGUIDE}
        <p class="warn">보내는 내용에 <b>아직 공개하지 않은 개정안 초안</b>이 들어갑니다.
           기관 보안 지침에 어긋나지 않는지 먼저 확인해 주세요.</p>
      </div>`;
    }
    if (t.needsNode && !sel) {
      return `<div class="ai-intro"><p>오른쪽 개정안 트리에서 <b>대상 항목을 먼저 고르세요.</b></p>
        <p class="mut">${esc(t.name)} 은(는) 고른 조문·편·장을 기준으로 합니다.</p></div>`;
    }
    if (t.needsRef && !ref) {
      return `<div class="ai-intro"><p>참조 규정 <b>② 창에 견줄 규정을 먼저 띄우세요.</b></p></div>`;
    }
    if (t.free) return this.askHtml(sel, ref) + (this.result ? this.resultHtml(this.result) : "");

    if (!this.result) {
      return `<div class="ai-intro">
        <p><b>${esc(t.name)}</b> — ${esc(t.hint)}</p>
        ${t.needsNode ? `<p>대상 · <b>${esc(M.shortLabel(sel))} ${esc(sel.title || "")}</b></p>` : ""}
        ${t.needsRef ? `<p>참조 · <b>${esc(ref.name)}</b></p>` : ""}
        <p class="mut">[제안 받기] 를 누르면 위 내용을 Claude 에 보냅니다.</p>
      </div>${this.extraHtml()}`;
    }
    return this.resultHtml(this.result) + this.extraHtml();
  }

  /** 어느 작업에나 붙는 '이렇게 해 주세요' 칸 */
  extraHtml() {
    return `<div class="ai-extra-box">
      <label>덧붙일 지시 <span class="mut">(비워 두어도 됩니다)</span></label>
      <textarea class="ai-extra" rows="2"
        placeholder="예) 문장을 더 짧게. / 제3항은 그대로 두고 제1·2항만. / 이 조는 의무 규정으로."
        >${esc(this.extra)}</textarea>
    </div>`;
  }

  /** '직접 묻기' 입력 화면 */
  askHtml(sel, ref) {
    const P = this.picks;
    const box = (k, on, label, note) => `
      <label class="ai-pick${on ? "" : " off"}">
        <input type="checkbox" data-pick="${k}"${P[k] ? " checked" : ""}${on ? "" : " disabled"}>
        <span>${esc(label)}</span>${note ? `<i>${esc(note)}</i>` : ""}
      </label>`;

    return `<div class="ai-ask-box">
      <label>묻고 싶은 것</label>
      <textarea class="ai-ask" rows="4"
        placeholder="예) 이 조를 두 개로 나눈다면 어떻게 나누는 게 좋을까요?&#10;예) 일본 준칙의 정확도 규정과 우리 규정의 차이를 표가 아닌 글로 정리해 주세요.&#10;예) 이 장에서 상위 법령 위임 근거가 약한 조문을 짚어 주세요."
        >${esc(this.question)}</textarea>
      <div class="ai-picks">
        <span class="mut">함께 보낼 자료</span>
        ${box("node", !!sel, sel ? `고른 항목 — ${M.shortLabel(sel)} ${sel.title || ""}` : "고른 항목 (없음)", "제목·본문")}
        ${box("subtree", !!sel, "고른 항목의 하위 구조", "하위 4단")}
        ${box("outline", true, "개정안 전체 편제", "조문 제목만")}
        ${box("ref", !!ref, ref ? `참조 규정 — ${ref.name}` : "참조규정 (없음)", "편제")}
      </div>
      <div class="mut ai-tip">Ctrl+Enter 로 바로 보냅니다.</div>
    </div>`;
  }

  resultHtml(r) {
    const notes = (r.notes || []).map(([tag, text]) => `
      <div class="ai-note"><span class="tag ${TAG_CLASS[tag] || ""}">${esc(tag)}</span>
        <div>${esc(text)}</div></div>`).join("");

    if (r.kind === "patch") {
      const n = this.project.selected;
      const same = n && n.title === r.patch.title && n.body === r.patch.body;
      return `
        ${r.patch.reason ? `<div class="ai-summary">${esc(r.patch.reason)}</div>` : ""}
        <div class="ai-diff">
          <div class="ai-col"><h4>지금</h4>
            <div class="ai-t">${esc(n?.title || "")}</div>
            <div class="ai-b">${esc(n?.body || "")}</div></div>
          <div class="ai-col new"><h4>제안</h4>
            <div class="ai-t">${esc(r.patch.title)}</div>
            <div class="ai-b">${esc(r.patch.body)}</div></div>
        </div>
        ${notes}
        <div class="ai-actions">
          <button data-apply="patch" class="primary"${same ? " disabled" : ""}>이 제안 적용</button>
          <span class="mut">${same ? "지금과 같습니다." : "적용한 뒤에도 Ctrl+Z 로 되돌릴 수 있습니다."}</span>
        </div>`;
    }

    if (r.kind === "reasons") {
      return `<div class="ai-summary">${r.items.length}개 조문의 개정 사유를 만들었습니다.</div>
        ${notes}
        <div class="ai-actions">
          <button data-apply="reasons" class="primary"${r.items.length ? "" : " disabled"}>
            변경 사유 ${r.items.length}건 한꺼번에 적용</button>
          <span class="mut">이미 적어 둔 사유는 덮어쓰지 않습니다.</span>
        </div>`;
    }

    if (r.kind === "text") {
      return `<div class="ai-answer">${richText(r.text)}</div>`;
    }

    return `${r.summary ? `<div class="ai-summary">${esc(r.summary)}</div>` : ""}
      ${notes || `<div class="ai-intro"><p class="mut">짚을 것이 없다고 합니다.</p></div>`}
      <div class="ai-actions"><span class="mut">
        이 제안은 사람이 직접 옮겨 적용합니다 — 트리에서 끌어 옮기거나 조문 상세에서 고치세요.</span></div>`;
  }

  /* ---------- 실행 ---------- */
  async run() {
    const t = this.task;
    const p = this.project;
    const sel = p.selected;
    const ref = this.getRef?.();
    if (!t.free && t.needsNode && !sel) return;
    if (!t.free && t.needsRef && !ref) return;

    const ctx = { node: sel };
    if (t.key === "polish" && sel) {
      const parent = M.findParent(p.tree, sel.id);
      ctx.siblings = (parent?.children || [])
        .filter((x) => x.id !== sel.id && x.level === "조")
        .slice(0, 4)
        .map((x) => `${M.shortLabel(x)} ${x.title}\n${(x.body || "").slice(0, 220)}`)
        .join("\n\n");
    }
    if (t.key === "restructure" && sel) {
      ctx.subtree = outline([sel], { depth: 4, body: 120 });
      if (ref) { ctx.refName = ref.name; ctx.refOutline = outline(ref.tree, { depth: 3 }).slice(0, 6000); }
    }
    if (t.key === "conflicts") ctx.outline = outline(p.tree, { depth: 5 }).slice(0, 20000);
    if (t.key === "compareRef") {
      ctx.outline = outline(p.tree, { depth: 4 }).slice(0, 12000);
      ctx.refName = ref.name;
      ctx.refOutline = outline(ref.tree, { depth: 4 }).slice(0, 12000);
    }
    if (t.key === "reasons") {
      const rows = [];
      M.walk(p.tree, (n) => {
        if (!n.status || n.status === "유지" || n.reason) return;
        if (rows.length >= 40) return;
        rows.push(`- id:${n.id} | ${M.shortLabel(n)} ${n.title || ""} | 상태:${n.status}\n  ${(n.body || "").slice(0, 200)}`);
      });
      if (!rows.length) {
        this.result = { kind: "advice", summary: "사유를 적을 조문이 없습니다. 먼저 조문을 고치거나 옮겨 보세요.", notes: [] };
        this.render();
        return;
      }
      ctx.changed = rows.join("\n");
    }

    if (t.free) {
      this.keepInputs();
      const qs = (this.question || "").trim();
      if (!qs) { this.onToast("묻고 싶은 것을 먼저 적어 주세요."); return; }
      ctx.question = qs;
      ctx.pickNode = this.picks.node && !!sel;
      ctx.pickSubtree = this.picks.subtree && !!sel;
      ctx.pickOutline = this.picks.outline;
      ctx.pickRef = this.picks.ref && !!ref;
      if (ctx.pickNode) ctx.nodeText = `${M.shortLabel(sel)} ${sel.title || ""}
${sel.body || "(본문 없음)"}`;
      if (ctx.pickSubtree) ctx.subtree = outline([sel], { depth: 4, body: 160 }).slice(0, 12000);
      if (ctx.pickOutline) ctx.outline = outline(p.tree, { depth: 5 }).slice(0, 20000);
      if (ctx.pickRef) { ctx.refName = ref.name; ctx.refOutline = outline(ref.tree, { depth: 4 }).slice(0, 12000); }
    } else {
      this.keepInputs();
    }

    const built = t.build(ctx);
    const { system, user } = t.free ? built : withExtra(built, this.extra);
    this.busy = true;
    this.abort = new AbortController();
    this.render();
    try {
      const text = await AI.ask(system, user, { signal: this.abort.signal, maxTokens: 6000 });
      this.result = t.free ? t.parse(text) : t.parse(AI.pickJson(text));
    } catch (e) {
      if (e.name === "AbortError") return;
      this.result = { kind: "advice", summary: "", notes: [["확인필요", e.message]] };
    } finally {
      this.busy = false;
      this.abort = null;
      if (this.el) this.render();
    }
  }

  /* ---------- 적용 ---------- */
  apply(what) {
    const p = this.project;
    if (what === "patch") {
      const sel = p.selected;
      if (!sel || !this.result?.patch) return;
      const ok = p.updateFields(sel.id, {
        title: this.result.patch.title,
        body: this.result.patch.body,
        reason: sel.reason || this.result.patch.reason || "",
        status: sel.status,
      });
      this.onToast(ok ? "제안을 적용했습니다. (Ctrl+Z 로 되돌릴 수 있습니다)" : "바뀐 내용이 없습니다.");
      if (ok) this.close();
      return;
    }
    if (what === "reasons") {
      const items = this.result?.items || [];
      let n = 0;
      for (const it of items) {
        const node = M.findNode(p.tree, it.id);
        if (!node || node.reason) continue;
        if (p.updateFields(it.id, { reason: it.reason })) n += 1;
      }
      this.onToast(n ? `변경 사유 ${n}건을 적었습니다.` : "새로 적을 사유가 없었습니다.");
      if (n) this.close();
    }
  }
}

/* ---------- 연결 설정 ---------- */
AIView.prototype.setup = function setup() {
  const box = document.createElement("div");
  box.className = "overlay ai-setup";
  box.innerHTML = `
<div class="cmp sm">
  <div class="cmp-head">
    <div><div class="cmp-title">AI 연결 설정</div>
      <div class="cmp-sub">키는 이 브라우저에만 저장되고 api.anthropic.com 말고는 아무 데도 보내지 않습니다.</div></div>
    <button class="x" data-x="close">✕</button>
  </div>
  <div class="cmp-body">
    <div class="fld"><label>Anthropic API 키</label>
      <input class="f-key" type="password" placeholder="sk-ant-..." value="" autocomplete="off">
      <div class="mut" style="margin-top:4px">
        ${AI.hasKey() ? `지금 저장된 키 · <b>${esc(AI.keyHint())}</b>` : "아직 저장된 키가 없습니다."}
        &nbsp;— console.anthropic.com 에서 발급합니다.</div>
    </div>
    <div class="fld"><label>모델</label>
      <select class="f-model">${AI.MODELS.map((m) =>
        `<option value="${m.id}"${m.id === AI.getModel() ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</select>
    </div>
    <details class="ai-guide">
      <summary>API 키는 어디서 받나요?</summary>
      ${KEYGUIDE}
    </details>
    <div class="ai-warn">보내는 내용에 <b>아직 공개하지 않은 개정안 초안</b>이 들어갑니다.
      기관 보안 지침을 먼저 확인해 주세요. 규정 원문은 국가법령정보센터 공개 자료입니다.</div>
    <div class="detail-actions">
      <button data-x="clear">키 지우기</button>
      <button data-x="test">연결 확인</button>
      <button class="primary" data-x="save">저장</button>
    </div>
    <div class="ai-msg mut"></div>
  </div>
</div>`;
  document.body.appendChild(box);
  const close = () => box.remove();
  const msg = (t) => { box.querySelector(".ai-msg").textContent = t; };
  box.querySelector('[data-x="close"]').onclick = close;
  box.addEventListener("click", (e) => { if (e.target === box) close(); });
  box.querySelector('[data-x="save"]').onclick = () => {
    const k = box.querySelector(".f-key").value.trim();
    if (k) AI.setKey(k);
    AI.setModel(box.querySelector(".f-model").value);
    close();
    this.render();
  };
  box.querySelector('[data-x="clear"]').onclick = () => {
    AI.setKey(""); close(); this.render();
    this.onToast("저장된 API 키를 지웠습니다.");
  };
  const guide = box.querySelector(".ai-guide");
  box.querySelector('[data-x="test"]').onclick = async () => {
    const k = box.querySelector(".f-key").value.trim();
    if (k) AI.setKey(k);
    msg("확인하는 중…");
    try {
      await AI.verify(box.querySelector(".f-model").value);
      msg("연결되었습니다.");
    } catch (e) {
      msg(e.message);
      if (guide) guide.open = true;      // 막히면 발급 안내를 펼쳐 준다
    }
  };
};
