/* ============================================================
   ui/share.js — 공유 화면 (저장소 연결 · 프로젝트 목록 · 저장 이력)
   ============================================================ */
import * as GH from "../adapters/github.js?v=20260824d";
import { esc, fmtDT } from "./html.js?v=20260824d";

/** 파일 저장에 이어 저장소에도 올릴지 */
export const AUTOPUSH = {
  get on() { return localStorage.getItem("pm.gh.autopush") !== "0"; },
  set on(v) { localStorage.setItem("pm.gh.autopush", v ? "1" : "0"); },
};

export class ShareView {
  /**
   * @param {object} project
   * @param {object} cb { onOpen(data, meta), getPayload(), onToast(msg, ms) }
   */
  constructor(project, cb = {}) {
    this.project = project;
    this.cb = cb;
    this.el = null;
    this.tab = "list";           // list | history | setup
    this.items = [];
    this.commits = [];
    this.busy = false;
  }

  async open(tab = null) {
    if (this.el) this.close();
    if (tab) this.tab = tab;
    if (!GH.hasToken() || !GH.getConfig().owner) this.tab = "setup";
    this.el = document.createElement("div");
    this.el.className = "overlay";
    document.body.appendChild(this.el);
    this._esc = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._esc, true);
    this.el.addEventListener("click", (e) => { if (e.target === this.el) this.close(); });
    this.render();
    if (this.tab === "list") await this.refreshList();
  }

  close() {
    if (this._esc) document.removeEventListener("keydown", this._esc, true);
    this.el?.remove();
    this.el = null;
  }

  toast(m, ms) { this.cb.onToast?.(m, ms); }

  /* ---------- 데이터 ---------- */
  async refreshList() {
    if (!GH.hasToken()) return;
    this.setBusy("목록을 읽는 중…");
    try {
      this.items = await GH.listProjects();
      const meta = await GH.lastCommits(this.items.map((i) => i.path));
      this.items.forEach((i) => Object.assign(i, meta[i.path] || {}));
    } catch (e) {
      this.toast("목록을 읽지 못했습니다.\n" + e.message, 6000);
      this.items = [];
    } finally { this.setBusy(false); this.render(); }
  }

  async refreshHistory() {
    const path = this.project.remote?.path;
    if (!path) { this.commits = []; return; }
    this.setBusy("저장 이력을 읽는 중…");
    try { this.commits = await GH.history(path, 40); }
    catch (e) { this.toast("이력을 읽지 못했습니다.\n" + e.message, 5000); this.commits = []; }
    finally { this.setBusy(false); this.render(); }
  }

  setBusy(msg) {
    this.busy = !!msg;
    const b = this.el?.querySelector("#shBusy");
    if (b) { b.textContent = msg || ""; b.classList.toggle("hidden", !msg); }
  }

  /* ---------- 렌더 ---------- */
  render() {
    const cfg = GH.getConfig();
    const connected = GH.hasToken() && cfg.owner && cfg.repo;
    const cur = this.project.remote;

    this.el.innerHTML = `
<div class="cmp share">
  <div class="cmp-head">
    <div>
      <div class="cmp-title">공유 저장소</div>
      <div class="cmp-sub">
        ${connected
          ? `<b>${esc(cfg.owner)}/${esc(cfg.repo)}</b> · ${esc(cfg.branch)} · <code>${esc(cfg.dir || "/")}</code>
             &nbsp;|&nbsp; 저장할 때마다 커밋이 남아 버전이 관리됩니다.`
          : "저장소를 연결하면 프로젝트를 함께 쓰고, 저장할 때마다 버전이 남습니다."}
      </div>
    </div>
    <button class="x" data-x="close" title="닫기 (Esc)">✕</button>
  </div>

  <div class="cmp-bar2 share-tabs">
    <button data-tab="list" class="${this.tab === "list" ? "on" : ""}">프로젝트 목록</button>
    <button data-tab="history" class="${this.tab === "history" ? "on" : ""}">저장 이력</button>
    <button data-tab="setup" class="${this.tab === "setup" ? "on" : ""}">연결 설정</button>
    <span id="shBusy" class="hint hidden"></span>
    <div class="spacer"></div>
    ${cur ? `<span class="hint">현재 연결: <b>${esc(cur.name)}</b></span>` : `<span class="hint">서버에 저장된 프로젝트가 아닙니다</span>`}
    ${connected && this.tab === "list" ? `<button data-x="reload">새로 고침</button>
      <button class="primary" data-x="saveNew">현재 작업을 서버에 저장</button>` : ""}
  </div>

  <div class="cmp-body share-body">${
    this.tab === "setup" ? this.viewSetup(cfg)
    : this.tab === "history" ? this.viewHistory()
    : this.viewList(connected)}</div>
</div>`;

    this.el.querySelector('[data-x="close"]').onclick = () => this.close();
    this.el.querySelectorAll("[data-tab]").forEach((b) => {
      b.onclick = async () => {
        this.tab = b.dataset.tab;
        this.render();
        if (this.tab === "list") await this.refreshList();
        if (this.tab === "history") await this.refreshHistory();
      };
    });
    this.el.querySelector('[data-x="reload"]')?.addEventListener("click", () => this.refreshList());
    this.el.querySelector('[data-x="saveNew"]')?.addEventListener("click", () => this.saveAsNew());
    this.bindSetup();
    this.bindRows();
  }

  /* ----- 목록 ----- */
  viewList(connected) {
    if (!connected) return `<div class="sh-none">연결 설정 탭에서 저장소와 토큰을 먼저 지정하세요.</div>`;
    if (!this.items.length) {
      return `<div class="sh-none">저장된 프로젝트가 없습니다.<br>
        위의 <b>[현재 작업을 서버에 저장]</b> 으로 첫 프로젝트를 올려보세요.</div>`;
    }
    const cur = this.project.remote;
    return `<table class="sh-table">
      <thead><tr>
        <th>프로젝트</th><th style="width:150px">마지막 저장</th>
        <th style="width:110px">저장한 사람</th><th style="width:78px">크기</th><th style="width:200px">작업</th>
      </tr></thead>
      <tbody>${this.items.map((i) => `
        <tr class="${cur && cur.path === i.path ? "cur" : ""}">
          <td><b>${esc(i.name)}</b>${cur && cur.path === i.path ? ' <span class="tag k-mov">열림</span>' : ""}
              ${i.message ? `<br><span class="mut">${esc(i.message)}</span>` : ""}</td>
          <td class="mut">${i.at ? fmtDT(i.at) : "—"}</td>
          <td class="mut">${esc(i.by || "—")}</td>
          <td class="c mut">${(i.size / 1024).toFixed(0)} KB</td>
          <td class="nowrap">
            <button data-act="open" data-path="${esc(i.path)}">열기</button>
            <button data-act="save" data-path="${esc(i.path)}" data-sha="${esc(i.sha)}" data-name="${esc(i.name)}">덮어쓰기</button>
            <button data-act="del" data-path="${esc(i.path)}" data-sha="${esc(i.sha)}" class="danger">삭제</button>
          </td>
        </tr>`).join("")}</tbody>
    </table>`;
  }

  /* ----- 이력 ----- */
  viewHistory() {
    const cur = this.project.remote;
    if (!cur) return `<div class="sh-none">서버에 저장된 프로젝트를 연 상태에서만 이력을 볼 수 있습니다.</div>`;
    if (!this.commits.length) return `<div class="sh-none">저장 이력이 없습니다.</div>`;
    return `<div class="sh-hist-head"><b>${esc(cur.name)}</b> · 저장할 때마다 커밋 한 개가 쌓입니다. 과거 시점을 열어 확인하거나 되살릴 수 있습니다.</div>
    <table class="sh-table">
      <thead><tr>
        <th style="width:150px">저장 시각</th><th style="width:110px">저장한 사람</th>
        <th>메시지</th><th style="width:78px">커밋</th><th style="width:170px">작업</th>
      </tr></thead>
      <tbody>${this.commits.map((c, i) => `
        <tr>
          <td class="mut">${fmtDT(c.at)}${i === 0 ? ' <span class="tag k-new">최신</span>' : ""}</td>
          <td class="mut">${esc(c.by)}</td>
          <td>${esc(c.message)}</td>
          <td class="c mut"><code>${esc(c.short)}</code></td>
          <td class="nowrap">
            <button data-act="openAt" data-sha="${esc(c.sha)}">이 시점 열기</button>
            <a class="btnlink" href="${esc(c.url)}" target="_blank" rel="noopener">GitHub</a>
          </td>
        </tr>`).join("")}</tbody>
    </table>`;
  }

  /* ----- 설정 ----- */
  viewSetup(cfg) {
    const connected = GH.hasToken();
    return `<div class="sh-setup">
      <div class="sh-guide">
        <b>준비물</b> — GitHub 계정과, 프로젝트를 담을 <b>비공개 저장소</b> 하나.
        앱이 올라간 공개 저장소와는 <b>다른 저장소</b>를 쓰십시오. 작업물이 공개되지 않습니다.
        <ol>
          <li>GitHub 에서 비공개 저장소를 만듭니다 (예: <code>gonggong-projects</code>).</li>
          <li><a href="https://github.com/settings/personal-access-tokens" target="_blank" rel="noopener">Settings → Developer settings → Personal access tokens → Fine-grained</a> 에서 토큰을 만듭니다.
              <br>Repository access = 그 저장소만, Permissions → <b>Contents: Read and write</b>.</li>
          <li>아래에 저장소와 토큰을 넣고 [연결 확인] 을 누릅니다.</li>
        </ol>
        <div class="sh-warn">토큰은 <b>이 브라우저에만</b> 저장되며 GitHub 외에는 전송되지 않습니다.
          공용 PC 에서는 사용 후 [연결 해제] 를 누르세요.</div>
      </div>

      <div class="row2">
        <div class="fld"><label>GitHub 계정/조직 (owner)</label><input class="s-owner" value="${esc(cfg.owner)}" placeholder="Youngwoo-m"></div>
        <div class="fld"><label>저장소 이름 (repo)</label><input class="s-repo" value="${esc(cfg.repo)}" placeholder="gonggong-projects"></div>
      </div>
      <div class="row2">
        <div class="fld"><label>브랜치</label><input class="s-branch" value="${esc(cfg.branch)}" placeholder="main"></div>
        <div class="fld"><label>저장 폴더</label><input class="s-dir" value="${esc(cfg.dir)}" placeholder="projects"></div>
      </div>
      <div class="fld"><label>내 이름 (변경 이력에 기록됩니다)</label>
        <input class="s-author" value="${esc(GH.getAuthor())}" placeholder="홍길동"></div>
      <div class="fld">
        <label class="sh-check">
          <input type="checkbox" class="s-autopush"${AUTOPUSH.on ? " checked" : ""}>
          <span>파일로 저장할 때 <b>공유 저장소에도 함께 올리기</b></span>
        </label>
        <div class="mut" style="margin-top:3px">
          이미 저장소에 올려 둔 프로젝트에만 적용됩니다.
          처음 올리는 것은 이 창의 [새로 저장] 에서 이름을 정해 주세요.
        </div>
      </div>
      <div class="fld"><label>액세스 토큰 ${connected ? `<span class="mut">— 저장됨 (${esc(GH.tokenHint())})</span>` : ""}</label>
        <input class="s-token" type="password" autocomplete="off" placeholder="${connected ? "바꿀 때만 새로 입력" : "github_pat_… 또는 ghp_…"}"></div>

      <div class="detail-actions">
        ${connected ? `<button data-x="disconnect" class="danger">연결 해제</button>` : ""}
        <button class="primary" data-x="verify">연결 확인 후 저장</button>
      </div>
      <div id="shResult" class="sh-result hidden"></div>
    </div>`;
  }

  bindSetup() {
    const q = (c) => this.el.querySelector("." + c);
    this.el.querySelector('[data-x="verify"]')?.addEventListener("click", async () => {
      GH.setConfig({
        owner: q("s-owner").value.trim(), repo: q("s-repo").value.trim(),
        branch: q("s-branch").value.trim() || "main", dir: q("s-dir").value.trim(),
      });
      GH.setAuthor(q("s-author").value.trim());
      AUTOPUSH.on = !!q("s-autopush")?.checked;
      this.project.author = GH.getAuthor();
      const t = q("s-token").value;
      if (t) GH.setToken(t);
      q("s-token").value = "";
      const box = this.el.querySelector("#shResult");
      box.classList.remove("hidden");
      box.className = "sh-result";
      box.textContent = "확인 중…";
      try {
        const v = await GH.verify();
        box.classList.add("ok");
        box.innerHTML = `연결되었습니다. <b>${esc(v.login)}</b> 님으로 <b>${esc(v.repo)}</b>
          (${v.private ? "비공개" : "<span style='color:var(--accent)'>공개 — 작업물이 노출됩니다</span>"})
          · 쓰기 권한 ${v.canWrite ? "있음" : "<b style='color:var(--accent)'>없음</b>"}`;
        this.toast("저장소에 연결되었습니다.");
        setTimeout(async () => { this.tab = "list"; this.render(); await this.refreshList(); }, 900);
      } catch (e) {
        box.classList.add("err");
        box.textContent = e.message;
      }
    });
    this.el.querySelector('[data-x="disconnect"]')?.addEventListener("click", () => {
      if (!confirm("이 브라우저에 저장된 토큰을 지웁니다. 계속할까요?")) return;
      GH.clearToken();
      this.toast("연결을 해제했습니다.");
      this.render();
    });
  }

  /* ---------- 동작 ---------- */
  bindRows() {
    this.el.querySelectorAll("[data-act]").forEach((b) => {
      b.onclick = () => this.act(b.dataset.act, b.dataset);
    });
  }

  async act(act, d) {
    try {
      if (act === "open") {
        this.setBusy("여는 중…");
        const r = await GH.readProject(d.path);
        this.cb.onOpen?.(r.data, { path: r.path, sha: r.sha, name: d.path.split("/").pop().replace(/\.pmproj$/i, "") });
        this.close();
        this.toast(`서버에서 열었습니다 — ${d.path.split("/").pop()}`);
      } else if (act === "openAt") {
        const cur = this.project.remote;
        this.setBusy("과거 시점을 여는 중…");
        const r = await GH.readAt(cur.path, d.sha);
        this.cb.onOpen?.(r.data, { path: cur.path, sha: null, name: cur.name, atCommit: d.sha.slice(0, 7) });
        this.close();
        this.toast(`${d.sha.slice(0, 7)} 시점을 열었습니다.\n그대로 저장하면 이 내용으로 되살아납니다.`, 6000);
      } else if (act === "save") {
        await this.saveTo(d.path, d.sha, d.name);
      } else if (act === "del") {
        const name = d.path.split("/").pop();
        if (!confirm(`서버에서 ${name} 을(를) 삭제합니다.\n이력(커밋)은 남지만 목록에서는 사라집니다. 계속할까요?`)) return;
        this.setBusy("삭제 중…");
        await GH.deleteProject(d.path, d.sha);
        this.toast(`삭제했습니다 — ${name}`);
        await this.refreshList();
      }
    } catch (e) {
      this.toast((e.code === "conflict" ? "" : "실패: ") + e.message, 7000);
    } finally { this.setBusy(false); }
  }

  async saveAsNew() {
    const suggest = (this.project.remote?.name)
      || (this.project.baseName ? `${this.project.baseName} 개정안` : "개정안");
    const name = prompt("서버에 저장할 프로젝트 이름을 입력하세요.", suggest);
    if (name === null) return;
    const clean = name.trim().replace(/[\\/:*?"<>|]/g, "_");
    if (!clean) return;
    const path = GH.pathOf(clean + ".pmproj");
    const dup = this.items.find((i) => i.path === path);
    if (dup && !confirm(`같은 이름의 프로젝트가 있습니다.\n덮어쓸까요?`)) return;
    await this.saveTo(path, dup ? dup.sha : null, clean);
  }

  /**
   * @param {{message?:string, quiet?:boolean}} opts
   *        message 를 주면 묻지 않는다 (파일 저장에 이어 자동으로 올릴 때)
   */
  async saveTo(path, sha, name, opts = {}) {
    const msg = opts.message !== undefined
      ? opts.message
      : prompt("저장 메시지 (무엇을 바꿨는지 한 줄)", "작업 내용 저장");
    if (msg === null) return;
    this.setBusy("서버에 저장하는 중…");
    try {
      const payload = this.cb.getPayload();
      const author = GH.getAuthor();
      const r = await GH.writeProject(path, payload, {
        sha,
        message: `${msg}${author ? ` (${author})` : ""}`,
      });
      this.cb.onSaved?.({ path, sha: r.sha, name });
      this.toast(`서버에 저장했습니다 — ${name}\n커밋 ${r.commit.slice(0, 7)}`, 4500);
      await this.refreshList();
    } finally { this.setBusy(false); }
  }
}

