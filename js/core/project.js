/* ============================================================
   core/project.js — 프로젝트 상태 · 버전 · 명령(트랜잭션) · 되돌리기
   ------------------------------------------------------------
   · 프로젝트는 여러 개의 '버전'을 가진다.
       - 'base' 버전 = 현행 원문 (읽기 전용, 삭제 불가)
       - 그 밖의 버전 = 개정안 v1, v2, … (분기 가능)
   · this.tree 는 항상 '현재 버전'의 트리 배열과 같은 객체를 가리킨다.
   · 모든 구조 변경은 run() 트랜잭션을 통해서만 일어난다.
   ============================================================ */
import * as M from "./model.js?v=20260906d";
import { revLabel, nextRevLabel, revValue, verPrefixOf } from "./targets.js?v=20260906d";
import { regFingerprint } from "./xrefs.js?v=20260906d";
import { numbersOf, planFrom, planStayed, remapCitations, articleIdsIn,
         planTermFixes, TERM_RULES } from "./xrefs.js?v=20260906d";

const MAX_HISTORY = 100;
const BASE_ID = "base";

let _vseq = 0;
let _aseq = 0;
const newVersionId = () => `v${Date.now().toString(36)}${(_vseq++).toString(36)}`;

export class Project {
  constructor() {
    this.name = "개정안";
    this.baseName = "";
    this.baseMeta = null;
    this.versions = [];          // [{id,label,title,parentId,createdAt,author,note,readonly,tree,events}]
    this.currentId = null;
    this.refDocs = [];           // 파일에서 불러와 색인한 참조 규정 (프로젝트에 함께 저장)
    this.assets = {};            // 바뀐 별표·별지 서식 파일 { id: {name,mime,size,data,at,by} }
    this.ui = { ref1: null, ref2: null };   // 참조 창별 {docId, mode}
    this.author = "";            // 이력에 기록할 작성자 이름
    this.remote = null;          // 서버(저장소) 연결 정보 {path, sha, name}
    this.tree = [];
    this.selectedId = null;
    this.dirty = false;
    this.targetIds = [];         // 담고 있는 개정 대상 (등록부의 id)
    this.activeTargetId = null;  // 지금 손대고 있는 규정 — 참조 창이 이걸 따라온다
    /* 규정마다 제 판을 가리킨다 — 작업규정은 vA-1.01 을 보면서 무인비행장치는
       vC-1.00 을 볼 수 있다. 판 하나가 세 규정을 함께 담고 있으므로, 트리는
       규정마다 제 판에서 그 규정 가지만 꺼내 모아 세운다. */
    this.currentByTarget = {};   // 대상 id -> 판 id
    this._undoByV = new Map();   // versionId -> {undo:[], redo:[]}
    this._log = [];
    this._listeners = new Set();
  }

  /* ---------- 구독 ---------- */
  onChange(fn) { this._listeners.add(fn); return () => this._listeners.delete(fn); }
  emit(msg = "") { for (const fn of this._listeners) fn(this, msg); }

  /* ---------- 버전 접근 ---------- */
  get current() { return this.versions.find((v) => v.id === this.currentId) || null; }
  get base() { return this.versions.find((v) => v.id === BASE_ID) || null; }
  version(id) { return this.versions.find((v) => v.id === id) || null; }
  /**
   * 지금 고칠 수 없는 상태인가.
   * 기준(현행) 판 전체가 잠겨 있거나, 손대는 규정 하나가 잠겨 있으면 잠긴 것으로 본다 —
   * 작업규정·성과심사 초안은 잠겨 있고 무인비행장치 초안은 열려 있으므로,
   * 잠금을 판이 아니라 규정마다 따진다.
   */
  get isReadonly() {
    if (this.current && this.current.readonly) return true;
    const reg = this.activeReg;
    return !!(reg && reg.readonly);
  }

  /** 편집 가능한 버전 목록 (기준 제외) */
  get editableVersions() { return this.versions.filter((v) => !v.readonly); }

  versionStats(id) {
    const v = this.version(id);
    return v ? M.stats(v.tree) : null;
  }

  /** 자식 버전 목록 */
  childrenOf(id) { return this.versions.filter((v) => v.parentId === id); }

  _stacks(id = this.currentId) {
    if (!this._undoByV.has(id)) this._undoByV.set(id, { undo: [], redo: [] });
    return this._undoByV.get(id);
  }

  _setTree(t) {
    this.tree = t;
    const v = this.current;
    if (v) v.tree = t;
  }

  /* ---------- 적재 ---------- */
  /**
   * @param {object} doc   기준이 될 현행 규정
   * @param {object} draft 연구보고서 기반 초안 (없으면 null)
   * @param {object} opts  { word, startNote } — 편집기에 따라 '개정안' 또는 '개정안',
   *                        초안이 없을 때 v1 에 달아 둘 메모
   */
  loadFromRegulation(doc, draft = null, opts = {}) {
    const word = opts.word || "개정안";
    this.baseName = doc.name;
    this.name = `${word} (기준: ${doc.name})`;
    this.baseMeta = {
      name: doc.name, org: doc.org, kind: doc.kind, no: doc.no,
      effective: doc.effective, source: doc.source,
    };

    const tree = JSON.parse(JSON.stringify(doc.tree));
    // 첫 화면에서 펼쳐 둘 단 — 규정의 최상위 단(작업규정은 '편', 성과심사 규정은 '장')
    const top = tree[0]?.level || "편";
    // 별표·별지도 개정 대상이므로 개정안 트리에 함께 싣는다
    if (Array.isArray(doc.annexTree) && doc.annexTree.length) {
      tree.push(...JSON.parse(JSON.stringify(doc.annexTree)));
    }
    M.walk(tree, (n) => {
      n.status = n.status || "유지";
      n.reason = n.reason || "";
      n.sourceRef = n.sourceRef || null;
      n.history = n.history || [];
      n.collapsed = n.level !== top;
      if (n.annexRef) {
        if (!n.legacyNo) n.legacyNo = `${n.annexRef.gubun} ${n.annexRef.no}`;
        // 본문에 들어 있던 내려받기 주소는 지운다 — 여기는 '서식 변경 내용'을 적는 칸이다
        if (/^\s*(HWP|PDF)\s+https?:/i.test(n.body || "")) n.body = "";
      }
      if (n.level === "조" && !n.annexRef && !n.legacyNo) n.legacyNo = `제${n.no}조`;
    });
    M.renumber(tree);

    // v1 을 무엇으로 시작할지 — 연구보고서 기반 개정안 초안이 있으면 그것으로
    let work = tree;
    let label = "v1", title = `${word} 초안`, note = opts.startNote || "";
    if (draft && Array.isArray(draft.tree) && draft.tree.length) {
      work = JSON.parse(JSON.stringify(draft.tree));
      label = draft.label || "v1";
      title = draft.title || `${word} 초안`;
      note = draft.note || "";
      M.walk(work, (n) => {
        n.status = n.status || "유지";
        n.reason = n.reason || "";
        n.sourceRef = n.sourceRef || null;
        n.history = n.history || [];
        n.children = n.children || [];
        n.collapsed = n.level !== (work[0]?.level || top);
        if (n.annexRef && !n.legacyNo) n.legacyNo = `${n.annexRef.gubun} ${n.annexRef.no}`;
      });
      M.renumber(work);
    }

    const now = new Date().toISOString();
    this.versions = [
      {
        id: BASE_ID, label: "기준", title: `현행 ${doc.name}`, parentId: null,
        createdAt: now, author: "", note: "국가법령정보센터 원문", readonly: true,
        tree: JSON.parse(JSON.stringify(tree)), events: [],
      },
      {
        id: newVersionId(), label, title, parentId: BASE_ID,
        createdAt: now, author: "", note,
        // 연구보고서 기반 초안은 그대로 두고, 고치면 상위 버전으로 갈라 나간다
        readonly: !!(draft && draft.readonly !== false),
        tree: work, events: [],
      },
    ];

    // 초안이 여러 벌인 규정 — 연구가 해를 달리하여 나온 경우다 (draft.next)
    // 앞 버전을 부모로 삼아 v2, v3 … 로 잇는다.
    for (const more of (draft && Array.isArray(draft.next) ? draft.next : [])) {
      if (!Array.isArray(more.tree) || !more.tree.length) continue;
      const t = JSON.parse(JSON.stringify(more.tree));
      M.walk(t, (n) => {
        n.status = n.status || "유지";
        n.reason = n.reason || "";
        n.sourceRef = n.sourceRef || null;
        n.history = n.history || [];
        n.children = n.children || [];
        n.collapsed = n.level !== (t[0]?.level || top);
        if (n.annexRef && !n.legacyNo) n.legacyNo = `${n.annexRef.gubun} ${n.annexRef.no}`;
      });
      M.renumber(t);
      this.versions.push({
        id: newVersionId(),
        label: more.label || `v${this.versions.length}`,
        title: more.title || `${word} 초안`,
        parentId: this.versions[this.versions.length - 1].id,
        createdAt: now, author: "", note: more.note || "",
        readonly: !!more.readonly, tree: t, events: [],
      });
    }

    const last = this.versions[this.versions.length - 1];
    this.currentId = last.id;
    this.tree = last.tree;
    this.selectedId = this.tree.length ? this.tree[0].id : null;
    this._undoByV = new Map();
    this._log = [];
    this.assets = {};
    this.dirty = false;
    this.emit("규정을 불러왔습니다.");
  }

  /* ---------- 개정 대상 여럿을 한 트리로 ---------- */
  /**
   * 편집기를 한 벌로 합치면서 들어온 적재 방법.
   * 트리 최상위에 규정이 나란히 서고, 그 아래로 편·장·절·관·조가 이어진다.
   *
   * @param {Array} entries [{ target, doc, draft }]  target=등록부 한 줄,
   *                        doc=현행 규정, draft=연구보고서 기반 초안(없으면 null)
   *
   * ■ 버전을 어떻게 세는가
   *
   *   규정마다 초안이 몇 벌인지 다르다 — 작업규정·성과심사는 v1 한 벌,
   *   무인비행장치는 v1(2024)·v2(2025) 두 벌이다. 판을 나란히 세워
   *   기준 · v1 · v2 로 잇고, 그 판이 없는 규정은 제 마지막 판을 그대로 쓴다.
   *   어느 규정이 그 판에서 나아갔는지는 버전 메모에 적어 둔다.
   *
   * ■ 읽기 전용은 규정마다 다르다
   *
   *   작업규정·성과심사 초안은 읽기 전용이고(고치려면 분기), 무인비행장치
   *   초안은 곧바로 고친다. 합치면서 이 차이를 잃지 않도록 읽기 전용을
   *   버전이 아니라 규정 노드에 붙인다.
   */
  loadFromTargets(entries, opts = {}) {
    const now = new Date().toISOString();
    const list = (entries || []).filter((e) => e && e.target && e.doc);
    if (!list.length) throw new Error("개정 대상이 하나도 없습니다.");

    // 규정마다 판을 늘어놓는다 — [기준, v1, v2, …]
    const lanes = list.map((e) => {
      /* 판 이름은 규정마다 머리글자를 달리하고 1.00 에서 0.01 씩 올린다
         (등록부의 ver — 작업규정 A · 성과심사 B · 무인비행장치 C).
         초안 파일에 적힌 v1·v2 는 그 규칙으로 갈음한다. */
      const pre = e.target.ver || "X";
      let ri = 0;
      const revs = [{
        label: "기준", title: `현행 ${e.doc.name}`, note: "국가법령정보센터 원문",
        readonly: true, tree: baseTreeOf(e.doc),
      }];
      if (e.draft && Array.isArray(e.draft.tree) && e.draft.tree.length) {
        revs.push({
          label: revLabel(pre, ri++), title: e.draft.title || `${e.target.word} 초안`,
          note: e.draft.note || "", readonly: e.draft.readonly !== false,
          tree: draftTreeOf(e.draft.tree, e.target),
          supplement: e.draft.supplement || null,
        });
        for (const more of (Array.isArray(e.draft.next) ? e.draft.next : [])) {
          if (!Array.isArray(more.tree) || !more.tree.length) continue;
          revs.push({
            label: revLabel(pre, ri++), title: more.title || `${e.target.word} 초안`,
            note: more.note || "", readonly: !!more.readonly,
            tree: draftTreeOf(more.tree, e.target),
            supplement: more.supplement || null,
          });
        }
      }
      return { entry: e, revs };
    });

    const maxRev = Math.max(...lanes.map((l) => l.revs.length));
    this.versions = [];
    for (let r = 0; r < maxRev; r += 1) {
      const moved = [];                       // 이 판에서 나아간 규정
      const tree = lanes.map((lane, i) => {
        const at = Math.min(r, lane.revs.length - 1);
        if (at === r && r > 0) moved.push(`${lane.entry.target.short} ${lane.revs[at].label}`);
        return makeRegNode(lane.entry.target, lane.revs[at], i === 0);
      });
      M.renumber(tree);
      const note = r === 0
        ? "국가법령정보센터 원문"
        : (moved.length ? moved.join(" · ") : "앞 판 그대로");
      this.versions.push({
        id: r === 0 ? BASE_ID : newVersionId(),
        label: r === 0 ? "기준" : `v${r}`,
        title: r === 0 ? "현행 규정 세 종" : `개정안 초안 ${r > 1 ? `(${r}판)` : ""}`.trim(),
        parentId: r === 0 ? null : this.versions[r - 1].id,
        createdAt: now, author: "", note,
        // 판 전체를 잠그지 않는다 — 잠금은 규정 노드가 저마다 지닌다
        readonly: r === 0,
        tree, events: [],
      });
    }

    this.baseName = list.map((e) => e.target.base).join(" · ");
    this.name = opts.name || "규정 개정안 (세 종)";
    this.baseMeta = {
      name: this.name,
      targets: list.map((e) => ({
        id: e.target.id, name: e.doc.name, org: e.doc.org, kind: e.doc.kind,
        no: e.doc.no, effective: e.doc.effective, source: e.doc.source,
      })),
    };
    this.targetIds = list.map((e) => e.target.id);

    /* 규정마다 제 마지막 판을 가리킨다 — 무인비행장치는 vC-1.01 이 있고
       작업규정은 vA-1.00 뿐이면 각자 그것을 본다. */
    this.currentByTarget = {};
    for (const e of list) {
      let pick = this.versions[0];
      for (const v of this.versions) {
        const reg = this.regIn(v, e.target.id);
        if (reg && !v.readonly) pick = v;
      }
      this.currentByTarget[e.target.id] = pick.id;
    }
    const last = this.versions[this.versions.length - 1];
    this.currentId = this.currentByTarget[list[0].target.id] || last.id;
    this.tree = last.tree;
    this.activeTargetId = list[0].target.id;
    this.composeTree();
    this.selectedId = null;
    this._undoByV = new Map();
    this._log = [];
    this.assets = {};
    this.dirty = false;
    this.emit("개정 대상 규정을 불러왔습니다.");
  }

  /* ---------- 용어 맞추기 ---------- */

  /**
   * 규정 사이에서 갈린 말을 정한 말로 맞춘다.
   *
   * 고친 조문마다 무엇을 왜 바꿨는지 근거와 함께 남긴다 — 현행 고시 체계를
   * 따른 까닭과, 국가공간정보 표준용어집이 쓰는 말·인용표준번호를 함께 적어
   * 어느 쪽을 왜 골랐는지 나중에도 알 수 있게 한다. 그 사유는 그대로
   * 개정사유서와 신구대조표 비고란으로 간다.
   *
   * @param {object} opts { only: ["레이저측량", …] 적용할 규칙, dryRun }
   * @returns {{count:number, nodes:number, byRule:object, plan:Array}}
   */
  unifyTerms(opts = {}) {
    const rules = (opts.only && opts.only.length)
      ? TERM_RULES.filter((r) => opts.only.includes(r.canon))
      : TERM_RULES;
    const tally = (list) => {
      const byRule = {};
      for (const f of list) for (const s of f.samples) byRule[s.canon] = (byRule[s.canon] || 0) + 1;
      return {
        count: list.reduce((a, f) => a + f.hits, 0),
        nodes: new Set(list.map((f) => f.node.id)).size,
        byRule, plan: list,
      };
    };
    const summary = tally(planTermFixes(this.tree, rules));
    if (opts.dryRun || !summary.count) return summary;

    /* 읽기 전용 판이면 _guard() 가 새 판을 만들고, 그때 트리가 통째로 복제된다.
       앞서 세운 계획은 옛 트리의 노드를 가리키므로 그대로 쓰면 고침이 옛 판에
       들어간다 — 기준(현행) 판을 건드리는 셈이 된다. 판을 먼저 가르고 나서
       지금 트리로 계획을 다시 세운다. (move() 의 crossing 도 같은 까닭으로 다시 잡는다) */
    if (!this._guard()) return { ...summary, count: 0 };
    const fresh = tally(planTermFixes(this.tree, rules));
    if (!fresh.count) return fresh;
    const plan = fresh.plan;

    const ok = this.run(`용어 맞춤 (${fresh.count}곳)`, () => {
      for (const f of plan) {
        f.node[f.field] = f.after;
        M.bumpStatus(f.node, "수정");
        // 무엇을 무엇으로 바꿨는지 — 같은 말끼리 묶어 적는다
        const pairs = new Map();
        for (const s of f.samples) pairs.set(`${s.from} → ${s.to}`, (pairs.get(`${s.from} → ${s.to}`) || 0) + 1);
        const what = [...pairs].map(([k, v]) => v > 1 ? `${k} (${v}곳)` : k).join(", ");
        const basis = rules
          .filter((r) => f.samples.some((s) => s.canon === r.canon))
          .map((r) => `「${r.label || r.canon}」 근거: ${r.basis}`
            + (r.std ? ` · 국가공간정보 표준용어집 '${r.std.ko}' (${r.std.no})` : " · 표준용어집에 항목 없음"))
          .join(" / ");
        this.note(f.node, "용어", `${f.field === "title" ? "제목" : "본문"} 용어를 맞췄습니다 — ${what}. ${basis}`);
        const line = `용어 통일: ${what} (${basis})`;
        f.node.reason = f.node.reason ? `${f.node.reason}
${line}` : line;
      }
      return true;
    });
    return ok ? fresh : { ...fresh, count: 0, nodes: 0, blocked: true };
  }

  /**
   * 개정안 이름 바꾸기 — 규정 하나의, 판 하나에서.
   *
   * 판 이름(v1·v2·v4…)은 세 규정을 아우른 것이라 규정 하나만 놓고 보면 뜻이
   * 없다. 작업규정으로는 두 번째 판인데 판 이름이 v4 인 일이 생긴다.
   * 그래서 규정마다 제 개정안 이름을 따로 지닌다(revLabel) — 그것을 고친다.
   */
  renameRev(targetId, versionId, label, title) {
    const v = this.version(versionId);
    if (!v) return false;
    const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === targetId);
    if (!reg) return false;
    const was = `${reg.revLabel || ""} · ${reg.revTitle || ""}`.trim();
    if (label !== null && label !== undefined) reg.revLabel = String(label).trim() || reg.revLabel;
    if (title !== null && title !== undefined) reg.revTitle = String(title).trim();
    this.dirty = true;
    this._log.push({ at: new Date().toISOString(), v: v.label,
      label: `개정안 이름: ${was} → ${reg.revLabel} · ${reg.revTitle || ""}`.trim() });
    this.emit(`개정안 이름을 바꿨습니다 — ${reg.revLabel}${reg.revTitle ? ` · ${reg.revTitle}` : ""}`);
    return true;
  }

  /**
   * 옛 판 이름을 규칙대로 갈음한다 — v1 · v2 · 이어받음 → vA-1.00 · vA-1.01 …
   *
   * 판 이름을 규정마다 매기기 전에 담아 둔 프로젝트가 있다. 열 때 한 번
   * 갈아 준다. 판 차례대로 매기되 기준(현행)은 건드리지 않는다.
   */
  _normalizeRevLabels() {
    /* 머리글자는 등록부에서 가져온다 — 예전에 담아 둔 규정 노드에는 ver 가
       없어 X 로 앉는다. 여기서 채워 넣어 분기할 때에도 쓰이게 한다. */
    for (const v of this.versions) {
      for (const reg of (v.tree || []).filter(M.isRegNode)) {
        if (!reg.ver) reg.ver = verPrefixOf(reg.targetId);
      }
    }
    /* 번호는 그 규정의 내용이 실제로 달라질 때만 올라간다.
       판은 세 규정을 한꺼번에 담으므로, 작업규정만 놓고 보면 여러 판이 글자
       하나 다르지 않다. 판마다 번호를 올리면 작업규정 개정안이 두 벌뿐인데
       vA-1.03 까지 가 버린다. 같은 내용이면 같은 이름을 쓴다.

       판을 차례대로 훑으며 셈하므로 몇 번을 열어도 같은 이름이 나온다. */
    const seenByTarget = new Map();               // 대상 id -> Map(지문 -> 이름)
    for (const v of this.versions) {
      if (v.readonly) continue;
      for (const reg of (v.tree || []).filter(M.isRegNode)) {
        if (reg.revLabel === "기준") continue;
        let seen = seenByTarget.get(reg.targetId);
        if (!seen) { seen = new Map(); seenByTarget.set(reg.targetId, seen); }
        const fp = regFingerprint(reg);
        const had = seen.get(fp);
        if (had) { reg.revLabel = had; continue; }   // 앞서 나온 것과 같은 내용
        reg.revLabel = revLabel(reg.ver, seen.size);
        seen.set(fp, reg.revLabel);
      }
    }
  }

  /**
   * 변경 이력을 비운다 — 시험 삼아 돌려 본 자취를 걷어 낼 때.
   *
   * 판마다의 이벤트 원장(events), 조문마다의 이력(history), 그리고 작업
   * 기록(_log)을 함께 지운다. 되돌릴 수 없다 — 부르는 쪽이 먼저 묻는다.
   *
   * @param {string} targetId 이 규정만 비운다. 없으면 모두.
   * @returns {{events:number, nodes:number, log:number}} 지운 수
   */
  clearHistory(targetId = null) {
    let events = 0, nodes = 0;
    for (const v of this.versions) {
      if (Array.isArray(v.events) && v.events.length) {
        if (targetId) {
          const reg = this.regIn(v, targetId);
          const ids = new Set();
          if (reg) { ids.add(reg.id); M.walk(reg.children || [], (n) => ids.add(n.id)); }
          const keep = v.events.filter((e) => !ids.has(e.nodeId));
          events += v.events.length - keep.length;
          v.events = keep;
        } else {
          events += v.events.length;
          v.events = [];
        }
      }
      const roots = targetId
        ? [this.regIn(v, targetId)].filter(Boolean)
        : (v.tree || []);
      for (const r of roots) {
        const wipe = (n) => { if (n.history && n.history.length) { nodes += 1; n.history = []; } };
        wipe(r);
        M.walk(r.children || [], wipe);
      }
    }
    const log = this._log.length;
    if (!targetId) this._log = [];
    this.dirty = true;
    this.emit("변경 이력을 비웠습니다.");
    return { events, nodes, log: targetId ? 0 : log };
  }

  /* ---------- 규정마다 제 판 ---------- */

  /** 그 규정이 지금 보고 있는 판 */
  versionOf(targetId) {
    return this.version(this.currentByTarget[targetId]) || this.current;
  }

  /** 판 하나에서 그 규정 가지를 꺼낸다 */
  regIn(version, targetId) {
    return ((version && version.tree) || []).find(
      (n) => M.isRegNode(n) && n.targetId === targetId) || null;
  }

  /**
   * 트리를 다시 모아 세운다.
   *
   * 규정 노드는 제 판의 트리에 든 그 객체를 그대로 쓴다 — 복제하지 않는다.
   * 그래야 여기서 고친 것이 그 판에 그대로 남는다.
   */
  composeTree() {
    const out = [];
    for (const id of this.targetIds) {
      const reg = this.regIn(this.versionOf(id), id);
      if (reg) out.push(reg);
    }
    if (out.length) this.tree = out;
    return this.tree;
  }

  /** 그 규정만 다른 판으로 옮긴다 — 나머지 규정은 그대로 둔다 */
  switchTargetVersion(targetId, versionId) {
    const v = this.version(versionId);
    if (!v || !this.regIn(v, targetId)) return false;
    if (this.currentByTarget[targetId] === versionId) return false;
    this.currentByTarget[targetId] = versionId;
    if (targetId === this.activeTargetId) this.currentId = versionId;
    this.composeTree();
    const reg = this.regIn(v, targetId);
    this.selectedId = null;
    this.emit(`${M.shortLabel(reg)} ${reg.revLabel || v.label} 개정안을 엽니다`);
    return true;
  }

  /** 손대는 규정을 바꾸면 판 가리킴도 그 규정의 것으로 */
  _syncCurrentToActive() {
    const vid = this.currentByTarget[this.activeTargetId];
    if (vid && this.version(vid)) this.currentId = vid;
  }

  /* ---------- 규정 경계 ---------- */

  /** 트리 최상위의 규정 노드들 */
  get regNodes() { return (this.tree || []).filter(M.isRegNode); }

  /** 대상 id 로 규정 노드 하나 */
  regNode(targetId) {
    return this.regNodes.find((n) => n.targetId === targetId) || null;
  }

  /** 지금 손대고 있는 규정 */
  get activeReg() {
    return this.regNode(this.activeTargetId) || this.regNodes[0] || null;
  }

  /**
   * 손대는 규정을 바꾼다. 고른 조문이 있으면 그 조문의 규정을 따른다 —
   * 참조 창이 이 값을 보고 따라온다.
   */
  setActiveTarget(targetId) {
    if (!targetId || targetId === this.activeTargetId) return false;
    if (!this.regNode(targetId)) return false;
    this.activeTargetId = targetId;
    this._syncCurrentToActive();
    this.emit("");
    return true;
  }

  /* ---------- 불러온 참조 규정 ---------- */
  addRefDoc(doc) {
    const i = this.refDocs.findIndex((d) => d.id === doc.id);
    if (i >= 0) this.refDocs[i] = doc; else this.refDocs.push(doc);
    this.dirty = true;
    this._log.push({ at: new Date().toISOString(), label: `참조 규정 추가: ${doc.name}` });
    return doc;
  }
  removeRefDoc(id) {
    const d = this.refDocs.find((x) => x.id === id);
    if (!d) return false;
    this.refDocs = this.refDocs.filter((x) => x.id !== id);
    for (const k of Object.keys(this.ui)) {
      if (this.ui[k] && this.ui[k].docId === id) this.ui[k] = null;
    }
    this.dirty = true;
    this.emit(`참조 규정을 제거했습니다: ${d.name}`);
    return true;
  }
  refDoc(id) { return this.refDocs.find((d) => d.id === id) || null; }
  setPaneState(key, docId, mode) {
    const prev = this.ui[key];
    if (prev && prev.docId === docId && prev.mode === mode) return;
    this.ui[key] = { docId, mode };
    if (prev) this.dirty = true;      // 최초 지정은 변경으로 보지 않는다
  }

  /* ---------- 저장 형식 ---------- */
  toJSON() {
    return {
      format: "pmproj", version: 4,
      name: this.name, baseName: this.baseName, baseMeta: this.baseMeta,
      savedAt: new Date().toISOString(),
      currentId: this.currentId,
      targetIds: this.targetIds || [],
      /* 이 작업본을 세울 때 쓴 자료 파일의 지문. 다음에 이어받을 때
         파일의 지문과 견주어, 스크립트가 자료를 고쳤는지 가린다.
         (core/srcfp.js) */
      srcFp: this.srcFp || {},
      activeTargetId: this.activeTargetId || null,
      currentByTarget: this.currentByTarget || {},
      author: this.author || "",
      refDocs: this.refDocs,
      assets: this.assets,
      ui: this.ui,
      versions: this.versions.map((v) => ({
        id: v.id, label: v.label, title: v.title, parentId: v.parentId,
        createdAt: v.createdAt, author: v.author || "", note: v.note || "",
        readonly: !!v.readonly, tree: v.tree, events: v.events || [],
      })),
      log: this._log.slice(-500),
    };
  }

  fromJSON(o) {
    if (!o || o.format !== "pmproj") throw new Error("프로젝트 파일 형식이 아닙니다.");
    this.name = o.name || "개정안";
    this.baseName = o.baseName || "";
    this.baseMeta = o.baseMeta || null;
    this._log = o.log || [];
    this.refDocs = Array.isArray(o.refDocs) ? o.refDocs : [];
    this.assets = (o.assets && typeof o.assets === "object") ? o.assets : {};
    this.ui = Object.assign({ ref1: null, ref2: null }, o.ui || {});
    if (o.author && !this.author) this.author = o.author;
    this.targetIds = Array.isArray(o.targetIds) ? o.targetIds : [];
    this.srcFp = (o.srcFp && typeof o.srcFp === "object") ? { ...o.srcFp } : {};
    this.activeTargetId = o.activeTargetId || null;
    this.currentByTarget = (o.currentByTarget && typeof o.currentByTarget === "object")
      ? { ...o.currentByTarget } : {};

    if (Array.isArray(o.versions) && o.versions.length) {
      this.versions = o.versions;
      // 보고 있던 판을 그대로 다시 연다. 읽기 전용이라고 버리지 아니한다 —
      // 이 편집기는 처음 켤 때에도 읽기 전용인 개정안 초안을 보여 주므로,
      // 버리면 이어서 열 때 엉뚱하게 현행 규정으로 돌아간다.
      this.currentId = o.currentId && this.version(o.currentId)
        ? o.currentId
        : (this.editableVersions[0] || this.versions[0]).id;
    } else {
      // v1 형식(baseTree/tree) 이전 파일 변환
      const now = o.savedAt || new Date().toISOString();
      const work = o.tree || [];
      this.versions = [];
      if (o.baseTree && o.baseTree.length) {
        this.versions.push({
          id: BASE_ID, label: "기준", title: `현행 ${o.baseName || ""}`.trim(), parentId: null,
          createdAt: now, author: "", note: "", readonly: true, tree: o.baseTree,
          events: [],
        });
      }
      const vid = newVersionId();
      this.versions.push({
        id: vid, label: "v1", title: "개정안", parentId: this.versions.length ? BASE_ID : null,
        createdAt: now, author: "", note: "", readonly: false, tree: work,
        events: [],
      });
      this.currentId = vid;
    }

    for (const v of this.versions) {
      if (!Array.isArray(v.events)) v.events = this._eventsFromTree(v.tree, v.label);
      M.walk(v.tree, (n) => {
        if (n.collapsed === undefined) n.collapsed = false;
        if (!n.history) n.history = [];
      });
    }
    this.tree = this.current.tree;
    this.selectedId = null;
    this._normalizeRevLabels();
    // 담고 있는 대상을 트리에서 다시 읽어 둔다 (예전 파일에는 targetIds 가 없다)
    const regs = this.regNodes;
    if (regs.length) {
      this.targetIds = regs.map((n) => n.targetId).filter(Boolean);
      if (!this.activeTargetId || !this.regNode(this.activeTargetId)) {
        this.activeTargetId = this.targetIds[0] || null;
      }
      /* 규정마다 제 판을 가리킨다. 예전 파일에는 가리킴이 없으므로,
         그 규정을 담은 마지막 고칠 수 있는 판으로 세운다. */
      for (const id of this.targetIds) {
        const has = this.version(this.currentByTarget[id]);
        if (has && this.regIn(has, id)) continue;
        let pick = this.current;
        for (const v of this.versions) {
          if (!v.readonly && this.regIn(v, id)) pick = v;
        }
        this.currentByTarget[id] = pick.id;
      }
      this._syncCurrentToActive();
      this.composeTree();
    }
    this._undoByV = new Map();
    this.dirty = false;
    this.emit("프로젝트를 열었습니다.");
  }

  /* ---------- 버전 명령 ---------- */

  /** 현재(또는 지정) 버전을 복제해 새 버전을 만들고 그 버전으로 전환 */
  createVersion({ fromId = null, label = null, title = "", switchTo = true } = {}) {
    const src = this.version(fromId || this.currentId);
    if (!src) return null;
    const used = new Set(this.versions.map((v) => v.label));
    let n = this.editableVersions.length + 1;
    let auto = label;
    if (!auto) { while (used.has(`v${n}`)) n += 1; auto = `v${n}`; }

    const v = {
      id: newVersionId(), label: auto, title: title || `${src.label} 에서 분기`,
      parentId: src.id, createdAt: new Date().toISOString(), author: "", note: "",
      readonly: false, tree: JSON.parse(JSON.stringify(src.tree)),
      events: JSON.parse(JSON.stringify(src.events || [])),
    };
    /* 갈라 나온 판은 고치라고 만드는 것이다. 규정마다 지니고 있던 잠금까지
       그대로 복제하면 분기해도 여전히 손댈 수 없다 — 기준(현행)에서 갈라
       나온 판이 특히 그렇다 (규정 셋이 모두 잠겨 있다). 여기서 푼다. */
    M.walk(v.tree, (n) => { if (M.isRegNode(n)) n.readonly = false; });

    /* 손대는 규정의 개정안 이름을 한 판 올린다.
       판 이름(v1·v2·v4…)은 세 규정을 아우른 것이라 규정 하나만 놓고 보면
       뜻이 없다. 작업규정에서 갈라 나왔으면 작업규정으로는 두 번째 판이므로
       그 규정의 개정안 이름을 v2 로 적는다 — 그래야 고르개에서 갈린다. */
    const act = this.activeTargetId;
    if (act) {
      const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === act);
      if (reg) {
        const used = [];
        for (const ov of this.versions) {
          const r = (ov.tree || []).find((n) => M.isRegNode(n) && n.targetId === act);
          if (r && r.revLabel) used.push(r.revLabel);
        }
        reg.revLabel = nextRevLabel(reg.ver || "X", used);
      }
    }
    this.versions.push(v);
    /* 갈라 나온 판은 손대는 규정만 그리로 옮긴다 — 나머지 규정은 보던 판을
       그대로 본다. 규정마다 제 판을 가리키므로 서로 끌려다니지 않는다. */
    this.dirty = true;
    this._log.push({ at: v.createdAt, label: `버전 생성: ${v.label} (${src.label} 에서 분기)` });
    /* 갈라 나온 판은 손대는 규정만 그리로 옮긴다 — 나머지 규정은 보던 판을
       그대로 본다. 규정마다 제 판을 가리키므로 서로 끌려다니지 않는다. */
    if (switchTo) {
      if (this.targetIds && this.targetIds.length && this.activeTargetId) {
        this.currentByTarget[this.activeTargetId] = v.id;
        this.currentId = v.id;
        this.composeTree();
        this.selectedId = null;
        const reg = this.regNode(this.activeTargetId);
        this.emit(`${M.shortLabel(reg)} ${reg ? reg.revLabel : v.label} 을(를) 만들었습니다.`);
      } else {
        this.switchVersion(v.id, `버전 ${v.label} 을(를) 만들었습니다.`);
      }
    }
    else this.emit(`버전 ${v.label} 을(를) 만들었습니다.`);
    return v;
  }

  /** 판 전체 전환 — 세 규정을 모두 이 판으로 옮긴다 (메뉴바 판 고르개) */
  switchVersion(id, msg = null) {
    const v = this.version(id);
    if (!v || id === this.currentId) return false;
    this.currentId = id;
    if (this.targetIds && this.targetIds.length) {
      for (const t of this.targetIds) {
        if (this.regIn(v, t)) this.currentByTarget[t] = id;
      }
      this.composeTree();
      this.selectedId = null;
      this.emit(msg || `버전 전환: ${v.label}${v.readonly ? " (읽기 전용)" : ""}`);
      return true;
    }
    this.tree = v.tree;
    this.selectedId = v.tree.length ? v.tree[0].id : null;
    this.emit(msg || `버전 전환: ${v.label}${v.readonly ? " (읽기 전용)" : ""}`);
    return true;
  }

  updateVersion(id, patch) {
    const v = this.version(id);
    if (!v) return false;
    Object.assign(v, patch);
    this.dirty = true;
    this.emit("버전 정보를 수정했습니다.");
    return true;
  }

  deleteVersion(id) {
    const v = this.version(id);
    if (!v) return false;
    if (v.readonly) { this.emit("⚠ 기준 버전은 삭제할 수 없습니다."); return false; }
    if (this.editableVersions.length <= 1) { this.emit("⚠ 마지막 남은 개정안 버전입니다."); return false; }
    // 자식 버전은 삭제 대상의 부모로 재연결
    for (const c of this.childrenOf(id)) c.parentId = v.parentId;
    this.versions = this.versions.filter((x) => x.id !== id);
    this._undoByV.delete(id);
    this._log.push({ at: new Date().toISOString(), label: `버전 삭제: ${v.label}` });
    this.dirty = true;
    if (this.currentId === id) {
      const next = this.editableVersions[0];
      this.currentId = next.id;
      this.tree = next.tree;
      this.selectedId = next.tree.length ? next.tree[0].id : null;
    }
    this.emit(`버전 ${v.label} 을(를) 삭제했습니다.`);
    return true;
  }

  /* ---------- 조문 이력 ---------- */
  /**
   * 조문 하나에 변경 이력을 남기고 상태를 자동으로 올린다.
   * @param {object} node
   * @param {string} kind  이동 | 수정 | 신설 | 삭제 | 순서 | 참조삽입 | 통합
   * @param {string} detail 사람이 읽는 설명
   * @param {string} bump  상태를 올릴 유형 ('이동' | '수정' | null)
   */
  note(node, kind, detail, bump = null) {
    if (!node) return;
    if (bump) M.bumpStatus(node, bump);
    const entry = { kind, detail, by: this.author || "", v: this.current?.label || "" };
    M.addHistory(node, entry);
    this._recordEvent(node, Object.assign({}, entry, { at: node.history[node.history.length - 1].at }));
  }

  /** 하위 노드까지 같은 이력을 남긴다 (편·장 이동 시) */
  noteSubtree(node, kind, detail, bump = null) {
    this.note(node, kind, detail, bump);
    M.walk(node.children, (n) => {
      if (bump) M.bumpStatus(n, bump);
      const entry = { kind, detail, by: this.author || "", v: this.current?.label || "", cascade: true };
      M.addHistory(n, entry);
      this._recordEvent(n, Object.assign({}, entry, { at: n.history[n.history.length - 1].at }));
    });
  }

  /** 트리에서 노드가 삭제되어도 남는 버전별 불변 이벤트 원장 */
  _recordEvent(node, entry) {
    const v = this.current;
    if (!v || !node) return;
    if (!Array.isArray(v.events)) v.events = [];
    const path = M.pathOf(v.tree, node.id).map(M.shortLabel).join(" › ") || M.shortLabel(node);
    v.events.push(Object.assign({}, entry, {
      nodeId: node.id, label: M.shortLabel(node), title: node.title || "", path,
    }));
    if (v.events.length > 10000) v.events.splice(0, v.events.length - 10000);
  }

  _recordAudit(entry, kind, detail) {
    const v = this.current;
    if (!v) return;
    if (!Array.isArray(v.events)) v.events = [];
    v.events.push(Object.assign({}, entry, {
      at: new Date().toISOString(), kind, detail,
      by: this.author || entry.by || "", v: v.label,
      audit: true, cascade: false,
    }));
  }

  /** 구형 프로젝트의 노드 내 history를 이벤트 원장으로 변환 */
  _eventsFromTree(tree, versionLabel = "") {
    const out = [];
    (function rec(list, trail) {
      for (const n of list || []) {
        const t = trail.concat(M.shortLabel(n));
        for (const h of (n.history || [])) {
          out.push(Object.assign({}, h, {
            v: h.v || versionLabel, nodeId: n.id, label: M.shortLabel(n),
            title: n.title || "", path: t.join(" › "),
          }));
        }
        rec(n.children, t);
      }
    })(tree, []);
    out.sort((a, b) => String(a.at).localeCompare(String(b.at)));
    return out;
  }

  /**
   * 현재 버전의 모든 조문 이력을 시간 역순으로 모은다.
   * @returns [{at, kind, detail, by, v, nodeId, label, path}]
   */
  allHistory({ versionId = null, limit = 500 } = {}) {
    const v = this.version(versionId || this.currentId);
    if (!v) return [];
    const out = Array.isArray(v.events) ? v.events.slice() : this._eventsFromTree(v.tree, v.label);
    out.sort((a, b) => String(b.at).localeCompare(String(a.at)));
    return out.slice(0, limit);
  }

  /* ---------- 트랜잭션 ---------- */
  _snapshot() {
    return { tree: JSON.parse(JSON.stringify(this.tree)), selectedId: this.selectedId };
  }
  /**
   * 되돌리기 — 트리 배열을 통째로 갈아 끼우지 않고 규정 가지를 자리에서 되돌린다.
   *
   * 트리가 여러 판에서 모아 세운 것이므로, 배열을 갈아 끼우면 어느 판의 것이
   * 어느 것인지 잃는다. 규정 노드는 그 판의 트리에 든 객체 그대로여야 한다.
   */
  _restore(s) {
    const live = this.tree || [];
    for (const snap of s.tree || []) {
      const cur = live.find((n) => n.id === snap.id);
      if (!cur) continue;
      for (const k of Object.keys(cur)) if (!(k in snap)) delete cur[k];
      Object.assign(cur, snap);
    }
    this.selectedId = s.selectedId;
  }

  run(label, fn) {
    if (this.isReadonly) { this.emit("⚠ 기준(현행) 버전은 편집할 수 없습니다. 새 버전을 만드세요."); return false; }
    const before = this._snapshot();
    const eventStart = (this.current?.events || []).length;
    const res = fn(this.tree);
    if (res === false) { this._restore(before); return false; }
    M.renumber(this.tree);
    const st = this._stacks();
    const eventRefs = (this.current?.events || []).slice(eventStart).map((e) => Object.assign({}, e));
    st.undo.push({ label, before, eventRefs });
    if (st.undo.length > MAX_HISTORY) st.undo.shift();
    st.redo.length = 0;
    this._log.push({ at: new Date().toISOString(), v: this.current?.label, label });
    this.dirty = true;
    this.emit(label);
    return true;
  }

  undo() {
    const st = this._stacks();
    if (!st.undo.length) return false;
    const e = st.undo.pop();
    st.redo.push({ label: e.label, before: this._snapshot(), eventRefs: e.eventRefs || [] });
    this._restore(e.before);
    for (const h of (e.eventRefs || []).filter((x) => !x.cascade)) {
      this._recordAudit(h, "되돌림", `취소: ${e.label}`);
    }
    this.dirty = true;
    this.emit(`되돌림: ${e.label}`);
    return true;
  }
  redo() {
    const st = this._stacks();
    if (!st.redo.length) return false;
    const e = st.redo.pop();
    st.undo.push({ label: e.label, before: this._snapshot(), eventRefs: e.eventRefs || [] });
    this._restore(e.before);
    for (const h of (e.eventRefs || []).filter((x) => !x.cascade)) {
      this._recordAudit(h, "다시실행", `다시 실행: ${e.label}`);
    }
    this.dirty = true;
    this.emit(`다시 실행: ${e.label}`);
    return true;
  }
  get canUndo() { return this._stacks().undo.length > 0; }
  get canRedo() { return this._stacks().redo.length > 0; }

  /* ---------- 선택 ---------- */
  select(id) {
    if (this.selectedId === id) return;
    this.selectedId = id;
    // 고른 조문이 속한 규정으로 손대는 규정을 옮긴다 — 참조 창이 이걸 따라온다
    const reg = this.regionOf(id);
    if (reg && reg.targetId && reg.targetId !== this.activeTargetId) {
      this.activeTargetId = reg.targetId;
      this._syncCurrentToActive();
    }
    this.emit("");
  }
  get selected() { return this.selectedId ? M.findNode(this.tree, this.selectedId) : null; }

  /* ================= 편집 명령 ================= */

  /** 편집 가능 여부 확인 (읽기 전용 버전 차단) */
  /**
   * 편집을 막는 문지기.
   * 읽기 전용 버전에서 고치려 하면 그 버전을 밑그림 삼아 새 버전을 만들고 이어서 고치게 한다.
   *   · 기준(현행) → v2, v3 …
   *   · v1 개정안 초안(2025) → v2 …
   * 원본은 그대로 남으므로 언제든 되돌아가 견줄 수 있다.
   */
  _guard() {
    if (!this.isReadonly) return true;
    const src = this.current;
    const v = this.createVersion({
      fromId: src.id,
      title: `${src.label} ${src.title || ""} 에서 이어 고침`.replace(/\s+/g, " ").trim(),
      switchTo: true,
    });
    if (!v) {
      this.emit("⚠ 읽기 전용 버전입니다. [⑂분기] 로 새 버전을 만든 뒤 고치세요.");
      return false;
    }
    this.emit(`읽기 전용 버전이라 ${v.label} 을(를) 만들어 이어서 고칩니다.`);
    return true;
  }

  /**
   * 노드를 옮긴다.
   *
   * 규정을 넘는 이동은 '이관' 으로 따로 다룬다 — 규정 안의 이동은 번호만
   * 바뀌지만, 규정을 넘으면 근거 법령이 바뀐다. 그래서 사유를 받고,
   * 보낸 규정과 받은 규정 양쪽 이력에 남기고, 상태를 '이관' 으로 적는다.
   *
   * @param {object} opts { reason, onNeedReason }
   *        onNeedReason(info) 를 주면 사유가 없을 때 불러 받아 온다.
   *        (core 는 화면을 모르므로 묻는 일은 부르는 쪽이 한다)
   */
  move(dragId, targetId, pos, opts = {}) {
    let crossing = null;                 // 규정을 넘는 이동이면 {from, to}
    // 먼저 옮길 수 있는지 본다 — 안 되면 버전을 새로 만들지 않는다
    {
      const d = M.findNode(this.tree, dragId);
      const t = M.findNode(this.tree, targetId);
      if (!d || !t || dragId === targetId) return false;
      if (M.isRegNode(d)) { this.emit("⚠ 규정 자체는 옮길 수 없습니다."); return false; }
      if (M.isDescendant(d, targetId)) { this.emit("⚠ 자기 하위로는 옮길 수 없습니다."); return false; }
      if (this._inAnnex(dragId) !== this._inAnnex(targetId)) {
        this.emit("⚠ 별표·별지는 별표 묶음 안에서만 옮길 수 있습니다.");
        return false;
      }
      const from = this.regionOf(dragId);
      const to = M.isRegNode(t) && pos === "into" ? t : this.regionOf(targetId);
      if (from && to && from.id !== to.id) {
        // 받는 규정의 계층 규칙을 먼저 본다 — 편이 없는 규정으로 편을 옮길 수 없다
        const parentLv = (M.isRegNode(t) && pos === "into") ? M.REG_LEVEL
          : (pos === "into" ? t.level : (M.findParent(this.tree, targetId) || to).level);
        const parentNode = (M.isRegNode(t) && pos === "into") ? t
          : (pos === "into" ? t : (M.findParent(this.tree, targetId) || to));
        if (!M.canContain(parentLv, d.level, parentNode)) {
          this.emit(`⚠ 「${to.title}」 에는 ${d.level} 을(를) 둘 수 없습니다 `
                    + `— 이 규정은 ${to.top} 부터 시작합니다.`);
          return false;
        }
        crossing = { from, to };
      }
    }

    // 이관이면 사유를 받는다 — 근거 법령이 바뀌는 일이라 그냥 넘기지 않는다
    let reason = opts.reason || "";
    if (crossing && !reason) {
      if (typeof opts.onNeedReason === "function") {
        reason = opts.onNeedReason({
          node: M.findNode(this.tree, dragId),
          fromName: crossing.from.title, toName: crossing.to.title,
        }) || "";
      }
      if (!reason.trim()) {
        this.emit("이관 사유를 적지 않아 옮기지 않았습니다.");
        return false;
      }
    }

    if (!this._guard()) return false;
    const drag = M.findNode(this.tree, dragId);
    const target = M.findNode(this.tree, targetId);
    if (!drag || !target) return false;
    // 버전이 갈라졌을 수 있으므로 규정 노드를 다시 잡는다
    if (crossing) {
      crossing = {
        from: this.regNode(crossing.from.targetId) || crossing.from,
        to: this.regNode(crossing.to.targetId) || crossing.to,
      };
    }

    const beforePath = M.pathOf(this.tree, dragId).map(M.shortLabel).join(" › ");
    const oldParent = M.findParent(this.tree, dragId);
    /* 옮기기 전 번호를 적어 둔다 — 옮기고 나면 인용을 고쳐 쓸 때 짝지을 것이 없다.
       보낸 규정과 받은 규정 양쪽을 적는다. 조문이 빠져나가거나 끼어들면
       그 뒤의 조 번호가 줄줄이 밀리고, 번호로 적힌 인용이 함께 어긋난다. */
    const goneIds = crossing ? articleIdsIn(drag) : null;
    const numsFrom = crossing ? numbersOf(crossing.from) : null;
    const numsTo = crossing ? numbersOf(crossing.to) : null;
    const label = crossing ? `이관: ${M.shortLabel(drag)}` : `이동: ${M.shortLabel(drag)}`;
    const ok = this.run(label, (tree) => {
      const node = M.detach(tree, dragId);
      if (!node) return false;
      if (!M.insertAt(tree, node, targetId, pos)) return false;
      this.selectedId = node.id;
      const newParent = M.findParent(tree, node.id);
      const moved = (oldParent ? oldParent.id : null) !== (newParent ? newParent.id : null);
      M.renumber(tree);
      const afterPath = M.pathOf(tree, node.id).map(M.shortLabel).join(" › ");

      if (crossing) {
        const fromName = crossing.from.title, toName = crossing.to.title;
        const detail = `「${fromName}」 ${beforePath} → 「${toName}」 ${afterPath}`;
        // 옮긴 조문과 하위에 이관을 적는다
        this.noteSubtree(node, "이관", detail, "이관");
        node.transferredFrom = {
          targetId: crossing.from.targetId, regName: fromName,
          path: beforePath, label: M.shortLabel(node), at: new Date().toISOString(),
        };
        if (!node.reason) node.reason = reason;
        else node.reason = `${node.reason}
${reason}`;
        // 보낸 규정 쪽에도 남긴다 — 한쪽 이력만 보면 조문이 사라진 것처럼 보인다
        this.note(crossing.from, "이관(보냄)", `${detail}
사유: ${reason}`);
        this.note(crossing.to, "이관(받음)", `${detail}
사유: ${reason}`);

        /* 인용 표기를 고쳐 쓴다 — 두 가지가 한꺼번에 어긋난다.
             · 규정을 넘어간 조   제76조 → 「무인비행장치…」제5조
             · 남았는데 번호만 밀린 조   제229조 → 제215조
           보낸 규정은 조문이 빠져 뒤가 당겨지고, 받은 규정은 끼어들어 밀린다. */
        const fromPlan = planFrom(numsFrom, tree, toName, goneIds);
        const toPlan = planFrom(numsTo, tree, null, null);
        // 옮겨 간 조가 '두고 온' 조를 부르던 인용에도 보낸 규정 이름을 붙인다
        const stayPlan = planStayed(numsFrom, tree, goneIds, fromName);
        const fixed = [
          ...remapCitations(crossing.from, fromPlan),
          ...remapCitations(crossing.to, toPlan),
          ...remapCitations(node, stayPlan),
        ];
        for (const f of fixed) {
          M.bumpStatus(f.node, "수정");
          this.note(f.node, "인용 갱신",
            `이관에 따라 인용 표기를 고쳤습니다 (${f.hits}곳 · ${f.kinds.join("·")}).`);
        }
        this.lastTransfer = {
          nodeId: node.id, from: fromName, to: toName, reason,
          moved: goneIds.size, rewritten: fixed.length,
          rewrittenIn: fixed.map((f) => M.shortLabel(f.node)),
        };
      } else if (moved) {
        this.noteSubtree(node, "이동", `${beforePath} → ${afterPath}`, "이동");
      } else {
        this.note(node, "순서", `${beforePath} → ${afterPath}`);
      }
      return true;
    });

    if (ok && crossing) {
      const n = M.findNode(this.tree, dragId);
      const x = this.lastTransfer;
      this.emit(`「${crossing.from.title}」 → 「${crossing.to.title}」 이관 — ${M.shortLabel(n)}`
        + (x && x.rewritten
            ? ` · 인용 표기 ${x.rewritten}곳 자동 갱신 (${x.rewrittenIn.slice(0, 3).join(", ")}${x.rewrittenIn.length > 3 ? " 외" : ""})`
            : ""));
    }
    return ok;
  }

  /** 이 노드가 속한 규정 노드를 다른 이름으로 (이관 판정용) */
  regionOf(nodeId) {
    if (!nodeId) return null;
    for (const reg of this.regNodes) {
      if (reg.id === nodeId) return reg;
      if (M.findNode(reg.children, nodeId)) return reg;
    }
    return null;
  }

  /** 그 항목이 별표·별지 묶음 안에 있는가 */
  _inAnnex(id) {
    const path = M.pathOf(this.tree, id);
    return path.some((n) => n.isAnnex || n.annexRef);
  }

  addNode(level, where) {
    if (!this._guard()) return false;
    const sel = this.selected;

    // 별표 묶음 안에서 신설하면 조문이 아니라 별표·별지를 만든다
    if (sel && this._inAnnex(sel.id)) {
      const gubun = sel.annexRef?.gubun
        || M.pathOf(this.tree, sel.id).find((n) => n.isAnnex)?.annexGubun
        || "별표";
      const anx = M.makeNode("조", "");
      anx.annexRef = { gubun, no: "?", hwp: "", pdf: "" };
      anx.legacyNo = "";
      return this.run(`신설: ${gubun}`, (tree) => {
        const anchor = sel.annexRef ? sel.id : sel.id;
        const pos = sel.annexRef && where !== "child" ? "after" : "into";
        if (!M.insertAt(tree, anx, anchor, pos)) return false;
        this.selectedId = anx.id;
        M.renumber(tree);
        this.note(anx, "신설", `${M.shortLabel(anx)} 신설`);
        return true;
      });
    }

    const node = M.makeNode(level, "");
    return this.run(`신설: ${level}`, (tree) => {
      if (!sel) {
        if (!M.canContain(null, level)) return false;
        tree.push(node);
      } else if (where === "child") {
        if (!M.insertAt(tree, node, sel.id, "into")) return false;
      } else {
        if (!M.insertAt(tree, node, sel.id, "after")) return false;
      }
      this.selectedId = node.id;
      M.renumber(tree);
      this.note(node, "신설", `${level} 신설 (${M.shortLabel(node)})`);
      return true;
    });
  }

  promote() {
    const s0 = this.selected;
    if (!s0) return false;
    if (!M.findParent(this.tree, s0.id)) {
      this.emit("⚠ 최상위 항목은 더 승격할 수 없습니다.");
      return false;
    }
    if (!this._guard()) return false;
    const sel = this.selected;
    if (!sel) return false;
    const parent = M.findParent(this.tree, sel.id);
    if (!parent) return false;
    const gp = M.findParent(this.tree, parent.id);
    const newLevel = M.LEVELS[Math.max(0, M.levelIndex(sel.level) - 1)];
    if (!M.canContain(gp ? gp.level : null, newLevel)) { this.emit("⚠ 계층 규칙에 어긋납니다."); return false; }
    const beforeLabel = M.shortLabel(sel);
    return this.run(`승격: ${beforeLabel}`, (tree) => {
      const node = M.detach(tree, sel.id);
      node.level = newLevel;
      if (!M.insertAt(tree, node, parent.id, "after")) return false;
      M.renumber(tree);
      this.noteSubtree(node, "이동", `승격 ${beforeLabel} → ${M.shortLabel(node)}`, "이동");
      return true;
    });
  }

  demote() {
    const s0 = this.selected;
    if (!s0) return false;
    {
      const l0 = M.siblingsOf(this.tree, s0.id);
      if (l0.findIndex((n) => n.id === s0.id) <= 0) {
        this.emit("⚠ 위 형제가 있어야 강등할 수 있습니다.");
        return false;
      }
    }
    if (!this._guard()) return false;
    const sel = this.selected;
    if (!sel) return false;
    const list = M.siblingsOf(this.tree, sel.id);
    const i = list.findIndex((n) => n.id === sel.id);
    if (i <= 0) return false;
    const prev = list[i - 1];
    const newLevel = M.LEVELS[Math.min(M.LEVELS.length - 1, M.levelIndex(sel.level) + 1)];
    if (!M.canContain(prev.level, newLevel)) { this.emit("⚠ 계층 규칙에 어긋납니다."); return false; }
    const beforeLabel2 = M.shortLabel(sel);
    return this.run(`강등: ${beforeLabel2}`, (tree) => {
      const node = M.detach(tree, sel.id);
      node.level = newLevel;
      prev.collapsed = false;
      if (!M.insertAt(tree, node, prev.id, "into")) return false;
      M.renumber(tree);
      this.noteSubtree(node, "이동", `강등 ${beforeLabel2} → ${M.shortLabel(node)} (${M.shortLabel(prev)} 하위)`, "이동");
      return true;
    });
  }

  moveVertical(dir) {
    const cur = this.selected;
    if (!cur) return false;
    {
      const l0 = M.siblingsOf(this.tree, cur.id);
      const i0 = l0.findIndex((n) => n.id === cur.id);
      if (i0 + dir < 0 || i0 + dir >= l0.length) return false;
    }
    if (!this._guard()) return false;
    const sel = this.selected;
    if (!sel) return false;
    const list = M.siblingsOf(this.tree, sel.id);
    const i = list.findIndex((n) => n.id === sel.id);
    const j = i + dir;
    if (j < 0 || j >= list.length) return false;
    const beforeLabel3 = M.shortLabel(sel);
    return this.run(`순서 이동: ${beforeLabel3}`, (tree) => {
      const [n] = list.splice(i, 1);
      list.splice(j, 0, n);
      M.renumber(tree);
      this.note(n, "순서", `${beforeLabel3} → ${M.shortLabel(n)} (${dir < 0 ? "위로" : "아래로"})`);
      return true;
    });
  }

  remove() {
    if (!this._guard()) return false;
    const sel = this.selected;
    if (!sel) return false;
    const label = M.shortLabel(sel);
    const cnt = M.flatten([sel]).length - 1;
    return this.run(`삭제: ${label}${cnt ? ` (하위 ${cnt})` : ""}`, (tree) => {
      const beforePath = M.pathOf(tree, sel.id).map(M.shortLabel).join(" › ");
      this.noteSubtree(sel, "삭제", `${beforePath}${cnt ? ` 및 하위 ${cnt}개 항목` : ""} 삭제`);
      const list = M.siblingsOf(tree, sel.id);
      const i = list.findIndex((n) => n.id === sel.id);
      const next = list[i + 1] || list[i - 1] || M.findParent(tree, sel.id);
      M.detach(tree, sel.id);
      this.selectedId = next ? next.id : (tree[0] ? tree[0].id : null);
      return true;
    });
  }

  /* ============================================================
     별표·별지 서식 파일
     ------------------------------------------------------------
     파일은 버전마다 복사되면 프로젝트가 무거워지므로 assets 에 한 번만 담고,
     노드는 그 열쇠(newFileId)만 들고 있는다.
     ============================================================ */
  addAsset(a) {
    const id = `f${Date.now().toString(36)}${(_aseq++).toString(36)}`;
    this.assets[id] = { id, name: a.name, mime: a.mime || "", size: a.size || 0, data: a.data, at: new Date().toISOString(), by: this.author || "" };
    return id;
  }
  asset(id) { return (id && this.assets[id]) || null; }

  /** 어느 버전에서도 쓰지 않는 파일을 지운다 */
  gcAssets() {
    const used = new Set();
    for (const v of this.versions) {
      M.walk(v.tree, (n) => { if (n.annexRef?.newFileId) used.add(n.annexRef.newFileId); });
    }
    let n = 0;
    for (const k of Object.keys(this.assets)) if (!used.has(k)) { delete this.assets[k]; n += 1; }
    return n;
  }

  /** 바뀐 서식 파일을 별표·별지에 붙인다 (null 이면 뗀다) */
  setAnnexFile(id, a) {
    if (!this._guard()) return false;
    const n = M.findNode(this.tree, id);
    if (!n || !n.annexRef) return false;
    const label = M.shortLabel(n);

    if (!a) {
      const old = this.asset(n.annexRef.newFileId);
      if (!old) return false;
      return this.run(`서식 파일 제거: ${label}`, () => {
        const t = M.findNode(this.tree, id);
        t.annexRef.newFileId = null;
        t.annexRef.newFileName = "";
        this.note(t, "서식교체", `첨부한 서식 파일을 뗐습니다 (${old.name})`, "수정");
        this.gcAssets();
        return true;
      });
    }

    const fid = this.addAsset(a);
    return this.run(`서식 파일 올리기: ${label}`, () => {
      const t = M.findNode(this.tree, id);
      const prev = this.asset(t.annexRef.newFileId);
      t.annexRef.newFileId = fid;
      t.annexRef.newFileName = a.name;
      this.note(t, "서식교체",
        prev ? `바뀐 서식 파일 교체: ${prev.name} → ${a.name}` : `바뀐 서식 파일 올림: ${a.name}`,
        "수정");
      this.gcAssets();
      return true;
    });
  }

  updateFields(id, patch) {
    const n0 = M.findNode(this.tree, id);
    if (!n0) return false;
    if (!Object.keys(patch).some((k) => n0[k] !== patch[k])) return false;
    if (!this._guard()) return false;
    const n = M.findNode(this.tree, id);
    if (!n) return false;
    const before = { title: n.title, body: n.body, reason: n.reason, status: n.status };
    return this.run(`내용 수정: ${M.shortLabel(n)}`, () => {
      const t = M.findNode(this.tree, id);
      Object.assign(t, patch);
      const what = [];
      if (patch.title !== undefined && patch.title !== before.title) what.push("제목");
      if (patch.body !== undefined && patch.body !== before.body) what.push("본문");
      if (patch.reason !== undefined && patch.reason !== before.reason) what.push("변경 사유");
      if (patch.status !== undefined && patch.status !== before.status) {
        this.note(t, "상태변경", `${before.status} → ${patch.status}`);
      } else if (what.length) {
        this.note(t, "수정", `${what.join("·")} 수정`, "수정");
      }
      return true;
    });
  }

  insertReference(sourceNode, sourceDocName, targetId, pos) {
    if (!this._guard()) return false;
    const copy = M.cloneTree(sourceNode, { asReference: true });
    M.walk([copy], (n) => {
      n.sourceRef = { doc: sourceDocName, label: M.labelOf(sourceNode) };
      n.legacyNo = "";
    });
    return this.run(`참조 삽입: ${sourceDocName} ${M.shortLabel(sourceNode)}`, (tree) => {
      if (!targetId) { if (!M.canContain(null, copy.level)) return false; tree.push(copy); }
      else if (!M.insertAt(tree, copy, targetId, pos)) return false;
      this.selectedId = copy.id;
      M.renumber(tree);
      this.noteSubtree(copy, "참조삽입", `${sourceDocName} ${M.shortLabel(sourceNode)} 에서 인용`);
      return true;
    });
  }

  toggleCollapse(id) {
    const n = M.findNode(this.tree, id);
    if (!n || !n.children.length) return;
    n.collapsed = !n.collapsed;
    this.emit("");
  }
}

export { BASE_ID };

/* ============================================================
   규정 노드 만들기 — 합치기 1단계에서 새로 생긴 자리
   ------------------------------------------------------------
   조문 id 는 규정마다 따로 매겨져 있어 세 규정을 한 트리에 담으면
   부딪친다 (a3 · a7 · a22 … 가 세 규정 모두에 있다). 담을 때
   규정 id 를 앞에 붙여 갈라 준다 — work:a3 · uav:a3.
   ============================================================ */

/** 규정 id 를 앞에 붙여 조문 id 가 규정을 넘어 부딪치지 않게 한다 */
function nsTree(tree, targetId) {
  M.walk(tree, (n) => {
    if (n.id && !String(n.id).startsWith(targetId + ":")) n.id = `${targetId}:${n.id}`;
  });
  return tree;
}

/** 현행 규정 → 개정 대상 트리 (별표·별지도 개정 대상이므로 함께 싣는다) */
function baseTreeOf(doc) {
  const tree = JSON.parse(JSON.stringify(doc.tree));
  const top = tree[0]?.level || "편";
  if (Array.isArray(doc.annexTree) && doc.annexTree.length) {
    tree.push(...JSON.parse(JSON.stringify(doc.annexTree)));
  }
  M.walk(tree, (n) => {
    n.status = n.status || "유지";
    n.reason = n.reason || "";
    n.sourceRef = n.sourceRef || null;
    n.history = n.history || [];
    n.children = n.children || [];
    n.collapsed = n.level !== top;
    if (n.annexRef) {
      if (!n.legacyNo) n.legacyNo = `${n.annexRef.gubun} ${n.annexRef.no}`;
      if (/^\s*(HWP|PDF)\s+https?:/i.test(n.body || "")) n.body = "";
    }
    if (n.level === "조" && !n.annexRef && !n.legacyNo) n.legacyNo = `제${n.no}조`;
  });
  return tree;
}

/** 초안 트리 다듬기 */
function draftTreeOf(src, target) {
  const tree = JSON.parse(JSON.stringify(src));
  const top = tree[0]?.level || target.top || "편";
  M.walk(tree, (n) => {
    n.status = n.status || "유지";
    n.reason = n.reason || "";
    n.sourceRef = n.sourceRef || null;
    n.history = n.history || [];
    n.children = n.children || [];
    n.collapsed = n.level !== top;
    if (n.annexRef && !n.legacyNo) n.legacyNo = `${n.annexRef.gubun} ${n.annexRef.no}`;
  });
  return tree;
}

/**
 * 규정 한 줄 — 트리 최상위에 서는 노드.
 * 읽기 전용은 여기에 붙는다 (버전이 아니라 규정마다 다르다).
 */
function makeRegNode(target, rev, open) {
  return {
    id: `reg:${target.id}`,
    level: M.REG_LEVEL,
    targetId: target.id,
    top: target.top,
    word: target.word,
    ver: target.ver || "X",        // 판 이름 머리글자 — vA-1.00 의 A

    title: target.base,
    short: target.short,
    body: "",
    no: 0, branch: 0,
    status: "유지",
    legacyNo: "",
    reason: "",
    sourceRef: null,
    history: [],
    readonly: !!rev.readonly,
    revLabel: rev.label,
    revTitle: rev.title,
    revNote: rev.note || "",
    /* 부칙은 규정 트리에 담지 아니한다 — 현행 규정 색인이 부칙을 걷어내므로
       트리에 넣으면 조 번호가 어그러진다. 개정안 자료의 supplement 를 규정
       노드가 지니고 있다가 보고서를 지을 때 내어 준다. */
    supplement: rev.supplement || null,
    collapsed: !open,
    children: nsTree(rev.tree, target.id),
  };
}
