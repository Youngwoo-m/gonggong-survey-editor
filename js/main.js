/* ============================================================
   main.js — 앱 조립 (1단계 프로토타입)
   ============================================================ */
import * as M from "./core/model.js?v=20260823e";
import { Project } from "./core/project.js?v=20260823e";
import * as FS from "./adapters/fileio.js?v=20260823e";
import * as AUTO from "./adapters/autosave.js?v=20260823e";
import { TreeView } from "./ui/tree.js?v=20260823e";
import { DetailPanel, MAX_MB, setWord } from "./ui/detail.js?v=20260823e";
import { CompareView } from "./ui/compare.js?v=20260823e";
import { VersionsView } from "./ui/versions.js?v=20260823e";
import { HistoryView } from "./ui/history.js?v=20260823e";
import { ShareView, AUTOPUSH } from "./ui/share.js?v=20260823e";
import { ValidateView } from "./ui/validate.js?v=20260823e";
import { RefPicker } from "./ui/refpicker.js?v=20260823e";
import { AIView } from "./ui/ai.js?v=20260823e";
import { CiteCheckView } from "./ui/citecheck.js?v=20260823e";
import { TermsView } from "./ui/terms.js?v=20260823e";
import { scanCitations, neededDocs, gradeAll } from "./core/citecheck.js?v=20260823e";
import * as GH from "./adapters/github.js?v=20260823e";
import { extractLines } from "./core/importer.js?v=20260823e";
import { buildAuto } from "./core/structure.js?v=20260823e";
import { translateTree, DICT_SIZE } from "./core/translate.js?v=20260823e";
import { ObjectStore, fitTable } from "./core/objects.js?v=20260823e";
import { loadTargets, allTargets, targetById, firstTarget } from "./core/targets.js?v=20260823e";
import { regFingerprint, TERM_RULES } from "./core/xrefs.js?v=20260823e";
import { setRegulation as setAIRegulation } from "./core/aitasks.js?v=20260823e";

const $ = (s) => document.querySelector(s);
const NL = "\n";
/* 편집기를 한 벌로 합치면서 '이 화면이 어느 편집기인가' 라는 물음이 없어졌다.
   대신 '지금 어느 규정에 손대고 있는가' 를 묻는다 — 트리에서 고른 조문이 정한다.
   참조 창 두 개와 AI 도우미가 이 값을 따라온다. */
let APP = null;                      // 지금 손대는 개정 대상 (등록부 한 줄)
const activeTarget = () => APP;
const project = new Project();
const objects = new ObjectStore();
const pickers = {};        // idx -> RefPicker
const compare = new CompareView(project);
const versions = new VersionsView(project, {
  onCompare: (fromId, toId) => compare.open(fromId, toId, scopedTargetId()),
});
const share = new ShareView(project, {
  getPayload: () => project.toJSON(),
  onToast: (m, ms) => toast(m, ms),
  onOpen: (data, meta) => {
    project.fromJSON(data);
    project.remote = meta;
    project.author = GH.getAuthor();
    syncRefLibrary();
    restorePaneStates();
    project.dirty = !!meta.atCommit;
    project.emit(meta.atCommit ? `과거 시점 ${meta.atCommit} 을 열었습니다.` : "서버에서 열었습니다.");
  },
  onSaved: (meta) => {
    project.remote = meta;
    project.dirty = false;
    project.emit("서버에 저장했습니다.");
  },
});
const validator = new ValidateView(project, { onJump: (id) => jumpToNode(id) });
const ai = new AIView(project, {
  getRef: () => { const p = paneOf("ref2"); return p && p.doc ? { name: p.doc.name, tree: p.tree } : null; },
  onToast: (m, ms) => toast(m, ms),
  onJump: (id) => jumpToNode(id),
  host: $("#aiDock"),          // 별도 창이 아니라 개정안 창 아래에 붙인다
});
const citecheck = new CiteCheckView({
  onJump: (id) => jumpToNode(id),
  onOpenRef: (regId) => { $("#refSelect2").value = regId; setRefDoc("ref2", regId); },
});
/* 용어 통일 결과 창 — 무엇이 어디서 어떻게 바뀌는지 보이고 나서 묻는다.
   맞추는 일은 project.unifyTerms() 가 한다. */
const termsView = new TermsView({
  onJump: (id) => jumpToNode(id),
  onApply: (canons) => {
    const r = project.unifyTerms({ only: canons });
    toast(r.count
      ? `용어를 맞췄습니다 — ${r.count}곳 · 조문 ${r.nodes}개
`
        + "조문마다 변경 사유에 근거를 남겼습니다."
      : "읽기 전용 판이라 맞추지 못했습니다 — 새 개정안을 만든 뒤 다시 하십시오.", 6000);
    return r;
  },
});
const history = new HistoryView(project, {
  onJump: (nodeId, versionId) => {
    if (versionId && versionId !== project.currentId) project.switchVersion(versionId);
    jumpToNode(nodeId);
  },
});

function jumpToNode(nodeId) {
  if (!M.findNode(project.tree, nodeId)) {
    toast("이 항목은 현재 버전에서 삭제되어 원래 위치로 이동할 수 없습니다.", 4000);
    return false;
  }
  expandAncestors(project.tree, nodeId);
  project.select(nodeId);
  setEditTree(nodeId);
  editTree.scrollToId?.(nodeId);
  return true;
}

let library = null;          // library.json
const refCache = new Map();

/** 참조 규정 패널 2개 — 각각 독립된 규정을 띄운다 */
const refPanes = [
  { key: "ref1", idx: 1, doc: null, tree: null, selectedId: null, hits: [], hitAt: -1, mode: "orig" },
  { key: "ref2", idx: 2, doc: null, tree: null, selectedId: null, hits: [], hitAt: -1, mode: "orig" },
];
const paneOf = (key) => refPanes.find((p) => p.key === key);
let importedSeq = 0;                        // 파일로 불러온 규정 id 부여용

/* ---------- 초기화 ---------- */
init().catch((e) => { console.error(e); toast("초기화 실패: " + e.message, 5000); });

async function init() {
  AUTO.setScope("all");             // 세 규정을 한 벌로 담는다 (합치기 1단계)
  library = await FS.loadJSON("data/library.json");
  await loadTargets(FS.loadJSON);   // 개정 대상 등록부 — data/targets.json
  APP = firstTarget();

  const full = library.regulations.filter((r) => r.hasFullText);
  for (const i of [1, 2]) pickers[i] = new RefPicker($(`#refSelect${i}`));
  $("#refCount").textContent = `${full.length}종 색인 / 총 ${library.regulations.length}종`;

  // 개정 대상 — 등록부에 오른 규정을 모두 불러 한 트리에 담는다
  const entries = [];
  for (const t of allTargets()) {
    const meta = full.find((r) => r.name === t.base);
    if (!meta) { console.warn("등록부의 규정을 라이브러리에서 찾지 못했습니다:", t.base); continue; }
    const doc = await loadReg(meta.id);
    let draft = null;
    if (t.draft) {
      try { draft = await FS.loadJSON(t.draft); } catch { /* 초안이 없으면 현행에서 시작 */ }
    }
    entries.push({ target: t, doc, draft, regId: meta.id });
    baseRegIdOf[t.id] = meta.id;
  }
  if (!entries.length) throw new Error("개정 대상 규정을 하나도 불러오지 못했습니다.");
  M.setRootLevel(APP.top);
  project.loadFromTargets(entries);

  const base = { id: baseRegIdOf[APP.id] };
  baseRegId = base.id;
  const baseDoc = await loadReg(base.id);

  $("#refSelect1").innerHTML = buildRefOptions(1);
  $("#refSelect2").innerHTML = buildRefOptions(2);

  buildTrees();

  // 참조 패널 기본값 — ① 개정 대상 현행 규정, ② 목록 첫 묶음의 첫 규정
  $("#refSelect1").value = base.id;
  await setRefDoc("ref1", base.id);
  const second = $("#refSelect2").querySelector("option:not([disabled])");
  if (second) {
    $("#refSelect2").value = second.value;
    await setRefDoc("ref2", second.value);
  }

  project.author = GH.getAuthor();
  detail.setBaseRegId(base.id);
  // 신설 별표의 서식은 개정안 전용 자리에 둔다 (data/objects/<초안 id>/annex)
  for (const e of entries) {
    if (e.draft && e.draft.id) {
      draftRegIdOf[e.target.id] = e.draft.id;
      await loadObjectIndex(e.draft.id);
    }
    await loadObjectIndex(e.regId);      // 규정마다 본문 속 표·수식 목록
  }
  if (draftRegIdOf[APP.id]) detail.setDraftRegId(draftRegIdOf[APP.id]);
  detail.setObjectStore(objects);
  detail.setLawResolver((w) => resolveLawWord(w));
  detail.setJoNav({ has: hasArticle, go: gotoArticle,
                    hasAnx: hasAnnex, goAnx: gotoAnnex });
  try { detail.setAnnexIndex(await FS.loadJSON("data/annex/index.json")); } catch { /* 미리보기 없음 */ }
  loadSharedRefs();
  wire();

  // 창·칸 폭이 바뀌면 본문 속 표를 다시 맞춘다
  let refit = null;
  const doRefit = () => {
    clearTimeout(refit);
    refit = setTimeout(() => fitTable($("#detailBody")), 120);
  };
  window.addEventListener("resize", doRefit);
  new ResizeObserver(doRefit).observe($("#detailBody"));
  // 지난번에 담아 둔 것이 있으면 이어서 작업한다.
  // 처음부터 다시 하려면 [현행으로 초기화] 를 누른다.
  let resumed = null, moved = null;
  try {
    let got = await AUTO.load();
    // 편집기 세 벌이 저마다 담아 두던 것을 한 벌로 옮겨 담는다 (합치기 1단계).
    // 합치고 처음 켤 때 한 번만 도는 일이다 — 빠뜨리면 그동안 고친 것이
    // 화면에서 사라진 것처럼 보인다.
    if (!got) {
      const old = await AUTO.loadSplit(allTargets().map((t) => t.id));
      if (old && old.length) {
        mergeSplitProjects(old);
        moved = old.map((o) => o.id);
        resumed = old[0].at;
      }
    } else if (got.data && got.data.format === "pmproj") {
      project.fromJSON(got.data);
      syncRefLibrary();
      await restorePaneStates();
      resumed = got.at;
    }
  } catch (e) { console.warn("담아 둔 것을 이어받지 못했습니다:", e); }

  /* 앱을 열 때에는 공공측량 작업규정부터 보인다.
     이어받은 프로젝트에 지난번 손대던 규정이 적혀 있어도, 처음 화면은
     늘 첫 규정으로 연다 — 이 편집기의 본디 일감이 작업규정 개정이다. */
  const first = firstTarget();
  if (first && project.regNode(first.id)) {
    project.activeTargetId = first.id;
    editScope = null;
  }

  project.onChange(onProjectChange);
  onProjectChange(project, "");
  if (moved) {
    toast(`편집기 세 벌이 따로 담아 두었던 작업을 한 벌로 옮겨 담았습니다 — `
          + `${moved.map((id) => targetById(id)?.short || id).join(" · ")}
`
          + `세 규정이 이제 한 트리에 있습니다.`, 7000);
  } else if (resumed) {
    const at = new Date(resumed);
    toast(`지난 작업을 이어서 엽니다 — ${isNaN(at) ? "" : at.toLocaleString("ko-KR")}
`
          + `처음부터 다시 하려면 [현행으로 초기화] 를 누르세요.`, 5200);
  } else {
    const st = M.stats(project.tree);
    toast(`개정 대상 ${project.regNodes.length}종 · 조문 ${st.조}개를 불러왔습니다.`, 3200);
  }
}

/* ============================================================
   옮겨 담기 — 편집기 세 벌이 따로 담아 두었던 작업을 한 벌로
   ------------------------------------------------------------
   합치고 처음 켤 때 한 번만 돈다. 세 벌 각각에서 '보고 있던 판' 을 꺼내
   지금 트리의 해당 규정 자리에 끼워 넣는다. 판(버전) 계보까지 합치지는
   않는다 — 세 벌의 계보를 하나로 엮으면 어느 판이 어느 판인지 알 수 없게
   되므로, 이어받은 작업을 새 판 하나로 세우고 원본은 남겨 둔다.
   ============================================================ */
function mergeSplitProjects(saved) {
  // 이어받은 작업을 담을 새 판을 세운다 (지금 마지막 판에서 갈라 나온다)
  const v = project.createVersion({
    label: "이어받음",
    title: "편집기 세 벌에서 옮겨 담은 작업",
    switchTo: true,
  });
  if (!v) return false;

  const took = [];
  for (const one of saved) {
    const t = targetById(one.id);
    const reg = project.regNode(one.id);
    if (!t || !reg) continue;
    // 그 편집기가 보고 있던 판의 트리
    const vs = Array.isArray(one.data.versions) ? one.data.versions : [];
    const cur = vs.find((x) => x.id === one.data.currentId) || vs[vs.length - 1];
    if (!cur || !Array.isArray(cur.tree) || !cur.tree.length) continue;

    const tree = JSON.parse(JSON.stringify(cur.tree));
    // 그때의 조문 id 에는 규정 이름표가 없다 — 붙여 준다 (work:a3)
    M.walk(tree, (n) => {
      if (n.id && !String(n.id).startsWith(one.id + ":")) n.id = `${one.id}:${n.id}`;
      n.children = n.children || [];
      n.history = n.history || [];
      if (n.collapsed === undefined) n.collapsed = n.level !== t.top;
    });
    reg.children = tree;
    reg.readonly = false;              // 이어받은 작업은 곧바로 고칠 수 있다
    reg.revLabel = cur.label || "이어받음";
    reg.revTitle = cur.title || "";
    reg.revNote = `편집기 세 벌 시절 ${one.id} 에서 옮겨 담음`;
    took.push(t.short);

    // 참조 규정·서식도 함께 옮긴다 (있으면)
    for (const d of (one.data.refDocs || [])) project.addRefDoc(d);
    Object.assign(project.assets, one.data.assets || {});
  }

  M.renumber(project.tree);
  v.note = took.length ? `옮겨 담은 규정: ${took.join(" · ")}` : "옮겨 온 것 없음";
  project.dirty = true;
  syncRefLibrary();
  return true;
}

/**
 * ③ 개정안 구조 창을 그 규정으로 옮긴다 — ① 창에서 규정을 골랐을 때.
 *
 * 세 규정이 이미 한 트리에 있으므로 새로 불러올 것은 없다. 그 규정 줄을
 * 펴서 눈앞에 놓고, 손대는 규정을 그리로 옮긴다. 개정안이 읽기 전용이면
 * (작업규정·성과심사 초안이 그렇다) 그대로 읽기 전용으로 열린다 —
 * 고치려면 [⑂분기] 로 새 판을 만든다.
 */
/* ③ 창이 무엇을 보이는가
     null   ① 에서 고른 규정을 따라간다 (기본)
     "*"    세 규정을 모두 편다 — [⊞전체]. 규정을 넘는 이관을 하려면 필요하다
     id     그 규정에 붙박아 둔다 */
let editScope = null;

/** 지금 ③ 창이 보이는 규정 */
function scopedTargetId() {
  if (editScope === "*") return null;
  return editScope || project.activeTargetId;
}

/** 지금 ③ 창에 보일 가지 — 고른 규정의 편·장부터 곧바로 선다 */
function editRoots() {
  const id = scopedTargetId();
  if (!id) return project.tree;
  const reg = project.regNode(id);
  return reg ? reg.children : project.tree;
}

/** ③ 창을 다시 그린다 (트리를 갈아 끼우는 자리는 여기 하나뿐) */
function setEditTree(selId) {
  editTree.setData(editRoots(), selId);
  paintEditHead();
}

/** 창 머리에 어느 규정을 보고 있는지 적는다 */
function paintEditHead() {
  const id = scopedTargetId();
  const t = id ? targetById(id) : null;
  const el = document.querySelector(".pane-edit .pane-title");
  if (el) el.textContent = t ? `${t.short} ${t.word} 구조 · 드래그 편집`
                             : "개정안 구조 · 드래그 편집 (세 규정)";
  const btn = $("#btnScopeAll");
  if (btn) btn.classList.toggle("hidden", editScope === "*");
  paintRevPicker(id);
  paintDocName(id);
}

/* 메뉴바에는 지금 고치고 있는 규정 하나만 적는다.
   세 규정 이름을 죄다 늘어놓으면 두 줄로 넘치고, 정작 무엇을 고치는 중인지가
   보이지 않는다. 셋을 다 담고 있다는 것은 ① 창과 [⊞전체] 가 보여 준다. */
function paintDocName(targetId) {
  const el = $("#docName");
  if (!el) return;
  const t = targetId ? targetById(targetId) : null;
  const reg = targetId ? project.regNode(targetId) : null;
  const names = project.regNodes.map((r) => "· " + r.title).join(NL);
  el.textContent = t
    ? `${t.base}${reg && reg.revLabel && !reg.readonly ? ` · ${reg.revLabel}` : ""}`
    : `개정 대상 ${project.regNodes.length}종`;
  el.title = t
    ? `개정 대상 ${project.regNodes.length}종 가운데 지금 고치는 규정입니다${NL}${names}`
    : names;
}

/* ============================================================
   규정마다 개정안이 여러 벌일 때 — 그 창에서 고른다
   ------------------------------------------------------------
   연구가 해를 달리하여 나온 규정이 있다. 무인비행장치 측량 작업규정은
   v1(2024년 연구성과) · v2(2025년 연구결과 · 다중센서) 두 벌이다.
   판(버전) 고르개는 세 규정을 한꺼번에 갈아 끼우므로, 지금 보고 있는
   규정의 개정안만 고를 수 있게 여기 따로 둔다.

   판마다 규정이 어느 개정안을 담고 있는지는 규정 노드가 revLabel 로
   지니고 있다 (합치기 1단계). 그것을 모아 목록으로 세우고, 고르면 그
   개정안을 담은 판으로 옮겨 간다 — 트리를 건드리지 않으므로 되돌릴 것도
   없다.
   ============================================================ */
function revsOfTarget(targetId) {
  /* 내용이 같은 판은 하나로 접는다 — 판은 세 규정을 한꺼번에 담으므로
     한 규정만 놓고 보면 여러 판이 글자 하나 다르지 않을 수 있다.
     (작업규정은 v1·v2·이어받음 세 판에서 같다) */
  const by = new Map();
  for (const v of project.versions) {
    if (v.readonly) continue;          // 기준(현행) 은 개정안이 아니다 — 판 고르개에 있다
    const reg = (v.tree || []).find((n) => M.isRegNode(n) && n.targetId === targetId);
    if (!reg) continue;
    by.set(regFingerprint(reg), { label: reg.revLabel || v.label,
      title: reg.revTitle || v.title || "", versionId: v.id, versionLabel: v.label });
  }
  return [...by.values()];
}

function paintRevPicker(targetId) {
  const row = $("#editRevRow"), sel = $("#editRevSelect"), note = $("#editRevNote");
  if (!row || !sel) return;
  const revs = targetId ? revsOfTarget(targetId) : [];
  // 개정안이 한 벌뿐이면 고를 것이 없다
  if (revs.length < 2) {
    row.classList.add("hidden");
    sel.innerHTML = ""; sel.dataset.sig = "";   // 옛 목록을 남기지 않는다
    return;
  }
  row.classList.remove("hidden");
  const sig = revs.map((r) => r.versionId + "|" + r.label).join("~") + "@" + targetId;
  if (sel.dataset.sig !== sig) {
    sel.dataset.sig = sig;
    /* 같은 이름을 단 판이 둘 이상이면 판 이름을 덧붙여 갈라 준다.
       작업규정은 초안이 한 벌인데, 거기에 용어 통일을 적용한 판이 따로
       있으면 둘 다 'v1 · 개정안 초안(2025)' 이라 무엇이 다른지 알 수 없다. */
    const dup = {};
    for (const r of revs) dup[r.label] = (dup[r.label] || 0) + 1;
    sel.innerHTML = revs.map((r) => {
      const tail = (dup[r.label] > 1 && r.versionLabel !== r.label) ? ` [${esc(r.versionLabel)}]` : "";
      return `<option value="${r.versionId}">${esc(r.label)}`
        + `${r.title ? ` · ${esc(r.title)}` : ""}${tail}</option>`;
    }).join("");
  }
  const now = revs.find((r) => r.versionId === project.currentId);
  sel.value = now ? now.versionId : (revs.find((r) => {
    const reg = project.regNode(targetId);
    return reg && r.label === reg.revLabel;
  }) || revs[revs.length - 1]).versionId;
  const cur = revs.find((r) => r.versionId === sel.value);
  if (note) note.textContent = cur && cur.versionLabel !== cur.label ? `판 ${cur.versionLabel}` : "";
}

/**
 * ③ 창을 그 규정의 개정안으로 바꾼다 — ① 창에서 규정을 골랐을 때.
 * 규정 줄은 보이지 않고 그 규정의 편·장부터 선다.
 */
function showTargetInEditTree(targetId) {
  const reg = project.regNode(targetId);
  if (!reg) return false;
  editScope = targetId;                 // 고른 규정에 붙박는다
  reg.collapsed = false;
  project.activeTargetId = targetId;
  const first = (reg.children || [])[0];
  project.select(first ? first.id : null);
  setEditTree(first ? first.id : null);
  const ro = reg.readonly || project.isReadonly;
  toast(`${M.shortLabel(reg)} ${reg.word || "개정안"}을 엽니다`
        + `${ro ? " — 읽기 전용 (고치려면 [⑂분기])" : ""}`, 2600);
  return true;
}

/** 세 규정을 모두 편다 — 규정을 넘는 이관을 하려면 둘이 함께 보여야 한다 */
function showAllTargets() {
  editScope = "*";
  for (const r of project.regNodes) r.collapsed = false;
  setEditTree(project.selectedId);
  toast("세 규정을 모두 폈습니다 — 규정을 넘어 조문을 끌어 옮길 수 있습니다.", 3000);
}

/**
 * 규정을 넘는 이동(이관) 사유를 묻는다.
 *
 * 규정 안의 이동은 번호만 바뀌지만 규정을 넘으면 근거 법령이 바뀐다.
 * 여기서 적은 사유가 그대로 개정사유서와 개정 전후 비교표의 비고란으로 간다.
 */
function askTransferReason(info) {
  const what = M.shortLabel(info.node) + (info.node.title ? ` (${info.node.title})` : "");
  const kids = M.countBy(info.node.children || [], "조");
  return prompt(
    `규정을 넘는 이동입니다 — 이관

`
    + `  ${what}
`
    + `  「${info.fromName}」
`
    + `    → 「${info.toName}」
`
    + (kids ? `  하위 ${kids}개 조문이 함께 옮겨 갑니다.
` : "")
    + `
근거 법령이 바뀌는 일이므로 사유를 남깁니다.
`
    + `여기 적은 사유가 개정사유서와 신구대조표 비고란으로 갑니다.`,
    "");
}

/* ============================================================
   손대는 규정이 바뀌면 — 참조 창 두 개와 AI 도우미가 따라온다
   ------------------------------------------------------------
   편집기 세 벌일 때에는 화면을 갈아타야 했던 일이다. 이제 트리에서
   조문 하나를 고르면 그 조문의 규정으로 저절로 옮겨 간다.
   ============================================================ */
let _followingTarget = null;

async function followActiveTarget() {
  const id = project.activeTargetId;
  if (!id || id === _followingTarget) return;
  const t = targetById(id);
  if (!t) return;
  _followingTarget = id;
  APP = t;

  M.setRootLevel(t.top);
  setWord(t.word);
  setAIRegulation({ name: t.base, work: t.aiWork });

  const regId = baseRegIdOf[id];
  if (regId) {
    baseRegId = regId;
    detail.setBaseRegId(regId);
    await loadObjectIndex(regId);
  }
  detail.setDraftRegId(draftRegIdOf[id] || "");

  // ② 창 묶음 차례가 규정을 따라 다시 선다 (지금 프로파일이 하던 일)
  const keep2 = $("#refSelect2").value;
  $("#refSelect1").innerHTML = buildRefOptions(1);
  $("#refSelect2").innerHTML = buildRefOptions(2);
  pickers[1]?.refresh?.();
  pickers[2]?.refresh?.();
  if (keep2 && $("#refSelect2").querySelector(`option[value="${keep2}"]`)) {
    $("#refSelect2").value = keep2;
  }

  // ① '현행규정' 창은 손대는 규정의 현행본으로 (③ → ① 방향)
  if (regId && paneOf("ref1")?.doc?.id !== regId) {
    $("#refSelect1").value = regId;
    await setRefDoc("ref1", regId);
  } else if (regId) {
    $("#refSelect1").value = regId;
  }
  paintEditHead();      // 창 머리 글자는 paintEditHead 한 곳에서만 적는다
}

/** 본문 속 표·수식 XML 목록 — 없으면 조용히 넘어간다 */
async function loadObjectIndex(regId) {
  if (objects.index[regId]) return;
  try {
    objects.setIndex(regId, await FS.loadJSON(`data/objects/${regId}/index.json`));
  } catch { objects.setIndex(regId, {}); }
  try {
    objects.setAnnexIndex(regId, await FS.loadJSON(`data/objects/${regId}/annex-index.json`));
  } catch { objects.setAnnexIndex(regId, {}); }
}

async function loadReg(id) {
  if (refCache.has(id)) return refCache.get(id);
  const meta = library.regulations.find((r) => r.id === id);
  if (!meta || !meta.file) throw new Error("규정을 찾을 수 없습니다: " + id);
  const doc = await FS.loadJSON("data/" + meta.file);
  refCache.set(id, doc);
  return doc;
}

/** 참조 패널은 각자 접힘 상태를 따로 가져야 하므로 트리를 복제해 쓴다 */
function cloneForPane(doc) {
  const tree = JSON.parse(JSON.stringify(doc.tree));
  const top = tree[0]?.level || "편";        // 규정의 최상위 단만 펼쳐 둔다
  M.walk(tree, (n) => { n.collapsed = n.level !== top; });
  // 별표·서식 가지를 본문 뒤에 붙인다 (참조용, 통계에는 넣지 않는다)
  if (Array.isArray(doc.annexTree) && doc.annexTree.length) {
    const anx = JSON.parse(JSON.stringify(doc.annexTree));
    M.walk(anx, (n) => { n.collapsed = n.level === "편"; });
    tree.push(...anx);
  }
  return tree;
}

/* ---------- 트리 뷰 ---------- */
let editTree, detail;
let baseRegId = "";               // 지금 손대는 규정의 현행 규정 id
const baseRegIdOf = {};           // 대상 id -> 현행 규정 id  (work -> reg01)
const draftRegIdOf = {};          // 대상 id -> 초안 id       (work -> draft2025)
const refTrees = {};   // key -> TreeView

function buildTrees() {
  editTree = new TreeView($("#editTree"), {
    editable: true,
    onSelect: (id) => project.select(project.selectedId === id ? null : id),
    // 두 번 누르면 현행규정 창에서 그 조문의 현행 조문을 함께 골라 준다
    onDblSelect: (id) => {
      const node = M.findNode(project.tree, id);
      if (node && (node.level !== "조" || !node.legacyNo)) { project.toggleCollapse(id); return; }
      if (project.selectedId !== id) project.select(id);
      syncRefToDraft(id);
    },
    onToggle: (id) => project.toggleCollapse(id),
    onMove: (dragId, targetId, pos) => project.move(dragId, targetId, pos, {
      // 규정을 넘는 이동이면 사유를 묻는다 — core 는 화면을 모르므로 여기서 묻는다
      onNeedReason: (info) => askTransferReason(info),
    }),
    onExternalDrop: (payload, targetId, pos) => {
      const pane = paneOf(payload.source);
      if (!pane || !pane.tree) return;
      const node = M.findNode(pane.tree, payload.id);
      if (!node) return;
      project.insertReference(node, pane.doc.name, targetId, pos);
    },
  });

  for (const pane of refPanes) {
    const idx = pane.key === "ref1" ? 1 : 2;
    refTrees[pane.key] = new TreeView($(`#refTree${idx}`), {
      editable: false,
      dragSource: true,
      sourceName: pane.key,
      onSelect: (id) => {
        // 같은 항목을 다시 누르면 선택 해제 (비교 짝 풀기)
        if (pane.selectedId === id) {
          pane.selectedId = null;
          refTrees[pane.key].setSelected(null);
          refreshRefDetail(pane);
          return;
        }
        pane.selectedId = id;
        refTrees[pane.key].setSelected(id);
        refreshRefDetail(pane);
      },
      onToggle: (id) => {
        const n = M.findNode(pane.tree, id);
        if (n) { n.collapsed = !n.collapsed; refTrees[pane.key].setData(pane.tree, pane.selectedId); }
      },
    });
  }

  detail = new DetailPanel($("#detailBody"), $("#detailPath"), {
    onApply: (id, patch) => {
      if (project.updateFields(id, patch)) toast("적용했습니다.");
      else toast("변경된 내용이 없습니다.");
    },
    getAsset: (fid) => project.asset(fid),
    onAnnexFile: (id, file) => uploadAnnexFile(id, file),
    resolveCite: (name) => resolveRegName(name),
    onCite: (id, name, jo) => openInRef2(id, name, jo),
  });
}

async function setRefDoc(key, id) {
  const pane = paneOf(key);
  if (String(id).startsWith("shared:")) {
    const path = String(id).slice(7);
    if (!refCache.has(id)) {
      busy("공유 규정을 내려받는 중…");
      try {
        const doc = await GH.readRef(path);
        doc.id = id;
        doc.sharedFrom = path;
        refCache.set(id, doc);
        if (!library.regulations.some((r) => r.id === id)) {
          library.regulations.push({
            id, name: doc.name, org: doc.org, kind: doc.kind, no: doc.no,
            effective: doc.effective, lang: doc.lang, category: "shared",
            source: "", stats: doc.stats, file: null, hasFullText: true, shared: true,
          });
        }
      } finally { busy(false); }
    }
  }
  pane.doc = await loadReg(id);
  await loadObjectIndex(id);
  pane.tree = cloneForPane(pane.doc);
  pane.selectedId = null;
  refTrees[key]?.setData(pane.tree, null);
  refTrees[key]?.setHighlight([]);
  const s = pane.doc.stats || {};
  const idx = pane.idx;
  const d = pane.doc;
  const head = d.imported
    ? `가져온 파일 · ${d.imported.kind.toUpperCase()}${d.indexMode ? ` · ${d.indexMode} 기준 색인` : ""} · ${d.imported.fileName}`
    : metaLine(d);
  $(`#refMeta${idx}`).innerHTML =
    `${head}<br>${["편", "장", "절", "조"].filter((k) => s[k]).map((k) => `${k} ${s[k]}`).join(" · ")}` +
    (d.annex?.length ? ` · <b>별표·서식 ${d.annex.length}</b>` : "") +
    (d.translated ? ` · <span style="color:var(--green)">한글 대역 (치환률 ${Math.round(d.translated.coverage * 100)}%)</span>` : "")
    // 조문을 공개 API 가 아니라 고시 원문 파일에서 읽은 규정임을 밝힌다
    + (d.textSource ? `<br><span class="mut" title="${esc(d.textSource)}">본문 출처 — 법제처 고시 원문 파일</span>` : "");

  // 번역이 있는 문서에서만 표시 모드 전환을 보여준다
  const modes = $(`#refModes${idx}`);
  modes.classList.toggle("hidden", !d.translated);
  if (!d.translated) pane.mode = "orig";
  refTrees[key].opts.displayMode = pane.mode;
  modes.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.mode === pane.mode));
  refTrees[key]?.setData(pane.tree, null);
  pane.hits = []; pane.hitAt = -1;
  project.setPaneState(key, id, pane.mode);
  pickers[pane.idx]?.syncLabel();
  updateRemoveButtons();
  if (typeof refreshRefDetail === "function") refreshRefDetail(null);
}

/* ============================================================
   본문의 「…」 인용 → 참조규정 창에서 열기
   ============================================================ */
const normName = (s) => String(s || "").replace(/[\s·ㆍ・,()]/g, "");

/** 본문이 인용한 이름이 우리가 가진 규정인가 */
function resolveRegName(name) {
  const n = normName(name);
  if (n.length < 4) return null;
  // 이름이 바뀐 규정 — 옛 이름으로 한 인용도 잇는다 (scripts/gencites.py 가 만든다)
  for (const [old, id] of Object.entries(library.nameAlias || {})) {
    if (normName(old) === n) return id;
  }
  const pool = library.regulations.filter((r) => r.hasFullText);
  let hit = pool.find((r) => normName(r.name) === n);
  if (!hit) hit = pool.find((r) => { const k = normName(r.name); return k.includes(n) || n.includes(k); });
  if (!hit || hit.category === "core") return null;      // 자기 자신은 링크하지 않는다
  return hit.id;
}

/* ---------- 파일 저장에 이어 공유 저장소에도 올리기 ---------- */
/**
 * 파일로 저장한 뒤 같은 내용을 공유 저장소에 올린다.
 * 이미 저장소에 올려 둔 프로젝트일 때만 한다 —
 * 처음 올리는 것은 [공유 저장소] 에서 이름을 정해야 하므로 여기서 하지 않는다.
 */
async function pushToShare() {
  const rm = project.remote;
  if (!rm || !rm.path) return;
  if (!GH.hasToken() || !GH.getConfig().owner) return;
  if (!AUTOPUSH.on) return;

  busy("공유 저장소에 올리는 중…");
  try {
    const who = GH.getAuthor();
    const r = await share.saveTo(rm.path, rm.sha, rm.name, {
      message: `파일 저장에 이어 올림${who ? ` (${who})` : ""}`,
      quiet: true,
    });
    if (r) toast(`공유 저장소에도 올렸습니다 — ${rm.name}\n커밋 ${r.commit.slice(0, 7)}`, 4500);
  } catch (e) {
    if (e.code === "conflict") {
      toast("다른 사람이 먼저 저장했습니다.\n[공유 저장소] 에서 목록을 새로 고친 뒤 다시 올려 주세요.", 7000);
    } else {
      toast(`공유 저장소에 올리지 못했습니다: ${e.message}\n파일 저장은 끝났습니다.`, 7000);
    }
  } finally { busy(false); }
}

/** 툴바의 [적용] — 조문 상세의 편집 폼 내용을 개정안에 반영한다 */
function applyDetail() {
  if (project.isReadonly) {
    toast("읽기 전용 버전입니다. [✎편집] 으로 새 버전을 만든 뒤 고치세요.", 4000);
    return;
  }
  if (!detail.applyNow()) toast("고칠 조문을 먼저 고르세요.", 3000);
}

/** [적용] 단추를 켜고 끈다 */
function syncApplyButton() {
  const b = $("#btnApply");
  if (!b) return;
  const on = !project.isReadonly && detail.canApply();
  b.disabled = !on;
  b.title = project.isReadonly
    ? "읽기 전용 버전입니다. [✎편집] 으로 새 버전을 만든 뒤 고칠 수 있습니다."
    : on
      ? "조문 상세에서 고친 제목·본문·상태·변경 사유를 개정안에 반영합니다."
      : "개정안 트리에서 조문을 하나만 고르면 여기서 바로 반영할 수 있습니다.";
}

/**
 * [✎ 편집 시작] — 읽기 전용 버전을 밑그림 삼아 새 버전을 만들고 이어서 고친다.
 * 기준(현행)과 v1 개정안 초안(2025)은 그대로 남는다.
 */
function startEditing() {
  if (!project.isReadonly) {
    toast(`이미 고칠 수 있는 버전입니다 — ${project.current?.label || ""}`, 3000);
    return;
  }
  const src = project.current;
  const v = project.createVersion({
    fromId: src.id,
    title: `${src.label} ${src.title || ""} 에서 이어 고침`.replace(/\s+/g, " ").trim(),
    switchTo: true,
  });
  if (v) {
    toast(`${v.label} 을(를) 만들어 편집을 시작합니다.
${src.label} 은(는) 그대로 남아 있어 언제든 견줄 수 있습니다.`, 5000);
  }
}

/* ---------- 약칭 법령 인용 (법 제7조, 같은 법 시행령 제8조 …) ---------- */
let lawAlias = null;          // { "법": "공간정보의 구축 및 관리 등에 관한 법률", … }

/**
 * 규정 스스로 정한 약칭을 본문에서 찾아낸다.
 *   「공간정보의 구축 및 관리 등에 관한 법률」(이하 "법"이라 한다)
 * 그리고 '같은 법 시행령·시행규칙'은 그 법 이름에 붙여 만든다.
 */
function buildLawAlias() {
  const map = {};
  const RE = /[「『]([^」』\r\n]{4,60})[」』]\s*\(\s*이하\s*["“']([^"”']{1,12})["”']\s*(?:이)?\s*라\s*한다/g;
  let text = "";
  M.walk(project.base?.tree || project.tree, (n) => {
    if (n.body && text.length < 40000) text += `\n${n.body}`;
  });
  let m;
  while ((m = RE.exec(text))) {
    const full = m[1].trim();
    const alias = m[2].trim();
    if (!map[alias]) map[alias] = full;
  }
  const base = map["법"];
  if (base) {
    map["같은 법"] = base;
    map["같은법"] = base;
    map["같은 법 시행령"] = `${base} 시행령`;
    map["같은법 시행령"] = `${base} 시행령`;
    map["시행령"] = `${base} 시행령`;
    map["영"] = `${base} 시행령`;
    map["같은 법 시행규칙"] = `${base} 시행규칙`;
    map["같은법 시행규칙"] = `${base} 시행규칙`;
    map["시행규칙"] = `${base} 시행규칙`;
    map["규칙"] = `${base} 시행규칙`;
  }
  // 띄어쓰기를 하지 아니한 인용(같은법시행령)도 같은 자리로 보낸다
  for (const k of Object.keys(map)) {
    const bare = k.replace(/\s+/g, "");
    if (!map[bare]) map[bare] = map[k];
  }
  return map;
}

/** 약칭 → {id, name} */
function resolveLawWord(word) {
  if (!lawAlias) lawAlias = buildLawAlias();
  const full = lawAlias[word];
  if (!full) return null;
  const id = resolveRegName(full);
  return id ? { id, name: full } : null;
}

/** 참조규정 창에 그 규정을 띄운다 (조번호가 있으면 그 조문으로 이동) */
async function openInRef2(id, name, joNo = "") {
  const pane = paneOf("ref2");
  const sel = $("#refSelect2");
  if (!sel) return;
  if (!pickers[2]?.has(id)) { toast(`「${name}」 은(는) ② 창 목록에 없습니다.`, 4000); return; }

  if (!pane.doc || pane.doc.id !== id) {
    sel.value = id;
    pickers[2]?.syncLabel();
    await setRefDoc("ref2", id);
  }
  const reg = library.regulations.find((r) => r.id === id);
  const where = jumpRefTo(pane, joNo);
  toast(`참조규정 창에 열었습니다 — ${reg ? reg.name : name}${where ? ` ${where}` : ""}`, 3500);
}

/** 참조 창에서 제N조로 이동 */
function jumpRefTo(pane, joNo) {
  const no = parseInt(joNo, 10);
  if (!no || !pane.tree) return "";
  let hit = null;
  M.walk(pane.tree, (n) => {
    if (hit || n.annexRef) return;
    if (n.level === "조" && (n.no === no || n.legacyNo === `제${no}조`)) hit = n;
  });
  if (!hit) return "";
  expandAncestors(pane.tree, hit.id);
  pane.selectedId = hit.id;
  const view = refTrees[pane.key];
  view.setData(pane.tree, hit.id);
  view.scrollToId?.(hit.id);
  refreshRefDetail(pane);
  return `제${no}조`;
}

/** 개정안에서 고른 조문의 '현행 조문' 을 현행규정 창에서 함께 골라 준다 */
function syncRefToDraft(draftId) {
  const pane = paneOf("ref1");
  if (!pane || !pane.tree || !pane.doc) return;
  // 현행규정 창이 바탕 규정(핵심규정)일 때에만 짝지어 준다
  if (baseRegId && pane.doc.id !== baseRegId) return;

  const node = M.findNode(project.tree, draftId);
  if (!node) return;
  const key = String(node.legacyNo || "").replace(/\s+/g, "");
  if (!key) {                                   // 신설 조문은 현행에 짝이 없다
    toast("신설 조문이라 현행 규정에 짝이 되는 조문이 없습니다.", 2600);
    return;
  }

  let hit = null;
  M.walk(pane.tree, (n) => {
    if (hit) return;
    if (String(n.legacyNo || "").replace(/\s+/g, "") === key) hit = n;
  });
  if (!hit) {
    toast(`현행규정에서 ${key} 를 찾지 못했습니다.`, 2600);
    return;
  }
  if (pane.selectedId === hit.id) return;

  expandAncestors(pane.tree, hit.id);
  pane.selectedId = hit.id;
  const view = refTrees[pane.key];
  view.setData(pane.tree, hit.id);
  view.scrollToId?.(hit.id);
  refreshRefDetail();
}

/** 바뀐 별표·별지 서식 파일을 프로젝트에 담는다 */
async function uploadAnnexFile(id, file) {
  if (!file) {                                  // 첨부 떼기
    if (project.setAnnexFile(id, null)) toast("첨부를 뗐습니다.");
    return;
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    toast(`파일이 너무 큽니다 (${(file.size / 1024 / 1024).toFixed(1)}MB).
한 건에 ${MAX_MB}MB 까지 올릴 수 있습니다. 압축하거나 PDF 로 줄여 주세요.`, 6000);
    return;
  }
  busy(`${file.name} 읽는 중…`);
  try {
    const data = await new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(fr.result);
      fr.onerror = () => rej(new Error("파일을 읽지 못했습니다."));
      fr.readAsDataURL(file);                   // 프로젝트에 함께 저장되도록 data: 로 담는다
    });
    const ok = project.setAnnexFile(id, {
      name: file.name,
      mime: file.type || guessMime(file.name),
      size: file.size,
      data,
    });
    if (ok) toast(`올렸습니다 — ${file.name}
프로젝트를 저장하면 파일도 함께 저장되고, 공유 저장소에도 같이 올라갑니다.`, 5000);
  } catch (e) {
    toast("올리지 못했습니다: " + e.message, 5000);
  } finally { busy(false); }
}

const MIME = {
  hwp: "application/x-hwp", hwpx: "application/hwp+zip", pdf: "application/pdf",
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", gif: "image/gif",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};
const guessMime = (n) => MIME[String(n).split(".").pop().toLowerCase()] || "application/octet-stream";

/** 참조 창 선택 상태에 따라 조문 상세를 갱신 — 둘 다 골랐으면 비교 화면 */
function refreshRefDetail() {
  const items = [];

  for (const p of refPanes) {
    if (!p.selectedId || !p.tree || !p.doc) continue;
    const node = M.findNode(p.tree, p.selectedId);
    if (!node) continue;
    items.push({
      key: p.key,
      badge: p.key === "ref1" ? "현행규정" : "참조규정",
      node, docName: p.doc.name, docId: p.doc.id,
      trail: M.pathOf(p.tree, p.selectedId).map(M.displayLabel).join(" › "),
      editable: false,
    });
  }

  const sel = project.selected;
  if (sel) {
    items.push({
      key: "edit",
      badge: "개정안",
      node: sel,
      docName: `${project.current?.label || ""} ${project.current?.title || ""}`.trim(),
      docId: detail.baseRegId,
      trail: M.pathOf(project.tree, sel.id).map(M.displayLabel).join(" › "),
      editable: !project.isReadonly,
    });
  }

  detail.showPanels(items);
  syncApplyButton();
}

/** 본문의 '제○조' 인용 — 그 규정의 트리에서 그 조를 찾는다 */
function findArticle(docId, no) {
  const wanted = Number(no);
  if (!wanted) return null;
  const dig = (ns) => {
    for (const n of ns) {
      if (n.level === "조" && !n.annexRef && Number(n.no) === wanted) return n;
      const got = dig(n.children || []);
      if (got) return got;
    }
    return null;
  };
  const pane = refPanes.find((p) => p.doc && p.doc.id === docId);
  if (pane) return pane.tree ? dig(pane.tree) : null;
  return dig(project.tree);          // 개정안
}

const hasArticle = (docId, no) => !!findArticle(docId, no);

/** 별표·별지 한 건을 찾는다 — 변경 사유의 '별표 41' 을 이을 때 쓴다 */
function findAnnex(docId, gubun, no) {
  const wanted = String(no);
  const dig = (ns) => {
    for (const n of ns) {
      const a = n.annexRef;
      if (a && (a.gubun || "별표") === gubun && String(a.no) === wanted) return n;
      const got = dig(n.children || []);
      if (got) return got;
    }
    return null;
  };
  const pane = refPanes.find((p) => p.doc && p.doc.id === docId);
  if (pane) return pane.tree ? dig(pane.tree) : null;
  return dig(project.tree);
}

const hasAnnex = (docId, gubun, no) => !!findAnnex(docId, gubun, no);

/** 그 별표·별지를 골라 트리에서 보여 준다 */
function gotoAnnex(docId, gubun, no) {
  const node = findAnnex(docId, gubun, no);
  if (!node) { toast(`${gubun} ${no}을(를) 찾지 못했습니다.`, 2400); return; }
  const pane = refPanes.find((p) => p.doc && p.doc.id === docId);
  const open = (tree) =>
    M.pathOf(tree, node.id).forEach((a) => { if (a.id !== node.id) a.collapsed = false; });
  if (pane) {
    open(pane.tree);
    pane.selectedId = node.id;
    refTrees[pane.key].setData(pane.tree, node.id);
    refTrees[pane.key].scrollToId(node.id);
  } else {
    open(project.tree);
    project.select(node.id);
    setEditTree(node.id);
    editTree.scrollToId(node.id);
  }
  refreshRefDetail();
  toast(`${gubun} ${no}(으)로 옮겼습니다 — ${node.title || ""}`, 2200);
}

/** 그 조문을 골라 트리에서 보여 준다 */
function gotoArticle(docId, no) {
  const node = findArticle(docId, no);
  if (!node) { toast(`제${no}조를 찾지 못했습니다.`, 2400); return; }
  const pane = refPanes.find((p) => p.doc && p.doc.id === docId);
  const open = (tree) =>
    M.pathOf(tree, node.id).forEach((a) => { if (a.id !== node.id) a.collapsed = false; });
  if (pane) {
    open(pane.tree);
    pane.selectedId = node.id;
    refTrees[pane.key].setData(pane.tree, node.id);
    refTrees[pane.key].scrollToId(node.id);
  } else {
    open(project.tree);
    project.select(node.id);
    setEditTree(node.id);
    editTree.scrollToId(node.id);
  }
  refreshRefDetail();
  toast(`제${no}조로 옮겼습니다 — ${node.title || ""}`, 2200);
}

/** 참조 창에서 고른 조문을 푼다 — 비교 짝을 풀 때 쓴다 */
function clearPaneSel(key) {
  const pane = paneOf(key);
  if (!pane) return;
  pane.selectedId = null;
  refTrees[key]?.setSelected(null);
  refreshRefDetail();
}

/** 개정안에서 고른 조문을 푼다 */
function clearDraftSel() {
  project.select(null);
  editTree.setSelected(null);
  refreshRefDetail();
}

/** 어디서 골랐든 조문 상세를 다시 그린다 */
const refreshDetail = () => refreshRefDetail();

/* ---------- 상태 반영 ---------- */
let autosaveAt = "";               // 마지막으로 담은 시각 (화면에 보인다)

/** 고칠 때마다 부르되 잦은 호출은 묶는다 */
const autosaveNow = AUTO.debounced(() => {
  autosaveAt = new Date().toTimeString().slice(0, 5);
  const el = document.getElementById("stSaved");
  if (el && !project.remote) el.textContent = `자동 저장됨 · ${autosaveAt}`;
  return project.toJSON();
});


function onProjectChange(p, msg) {
  // 고른 조문이 다른 규정이면 참조 창과 부르는 말이 그리로 따라간다
  followActiveTarget().catch((e) => console.warn("규정 따라가기:", e));
  editTree.opts.editable = !p.isReadonly;
  setEditTree(p.selectedId);
  editTree.scrollToSelected();

  // 버전 선택기
  const vs = $("#versionSelect");
  const want = p.versions.map((v) => `${v.id}|${v.label}|${v.title || ""}`).join("~");
  if (vs.dataset.sig !== want) {
    vs.dataset.sig = want;
    vs.innerHTML = p.versions.map((v) =>
      `<option value="${v.id}">${v.label}${v.readonly ? " (읽기 전용)" : ""}${v.title ? ` · ${v.title}` : ""}</option>`).join("");
  }
  vs.value = p.currentId;
  $(".pane-edit .pane-head").classList.toggle("ro", p.isReadonly);
  $("#editHint").textContent = "노드를 끌어 위치를 바꾸면 조 번호가 자동으로 다시 매겨집니다.";
  updateFilterCounts();
  // [✎ 편집 시작] 은 읽기 전용일 때만 — 설명은 툴팁으로
  const be = $("#btnStartEdit");
  be.classList.toggle("hidden", !p.isReadonly);
  be.title = p.isReadonly
    ? [`${p.current?.label || ""} ${p.current?.title || ""} 은(는) 읽기 전용입니다.`.trim(),
       "[✎편집] 을 누르면 이 버전을 밑그림 삼아 새 버전을 만들고 이어서 고칩니다.",
       "원본은 그대로 남아 언제든 견줄 수 있습니다. (Ctrl+E)"].join("\n")
    : "";

  const st = M.stats(p.tree);
  const anx = [st.별표 ? `별표 ${st.별표}` : "", st.별지 ? `별지 ${st.별지}` : ""].filter(Boolean).join(" · ");
  $("#editStats").textContent =
    `${p.current ? p.current.label + " · " : ""}편 ${st.편} · 장 ${st.장}${st.절 ? ` · 절 ${st.절}` : ""} · 조 ${st.조}` +
    `${anx ? ` · ${anx}` : ""} · 변경 ${st.변경}`;
  $("#stCount").textContent = `편 ${st.편} / 장 ${st.장} / 조 ${st.조}${anx ? ` / ${anx}` : ""} · 변경 ${st.변경}`;
  scheduleValidate();
  $("#dirty").classList.toggle("hidden", !p.dirty);
  // 편집 내용은 이 브라우저에 자동으로 담긴다 (adapters/autosave.js).
  // 예전에는 고친 것이 없으면 한 번도 저장한 적이 없어도 '저장됨' 이라 적어
  // 오해를 불렀다. 이제는 마지막으로 담은 시각을 적는다.
  autosaveNow();
  $("#stSaved").textContent = p.remote
    ? `${p.dirty ? "◍ 서버와 다름" : "✓ 서버 저장됨"} · ${p.remote.name}${p.remote.atCommit ? ` (${p.remote.atCommit} 시점)` : ""}`
    : (autosaveAt ? `자동 저장됨 · ${autosaveAt}` : "이 브라우저에 자동으로 담습니다");

  const sel = p.selected;
  if (sel) {
    const trail = M.pathOf(p.tree, sel.id).map(M.shortLabel).join(" › ");
    $("#stSel").textContent = `선택: ${trail}` +
      (sel.children.length ? ` · 하위 ${M.flatten([sel]).length - 1}` : "");
  } else {
    $("#stSel").textContent = "선택 없음";
  }
  // 현행규정·참조규정과 개정안의 선택을 모아 한 번에 그린다
  refreshRefDetail();

  $('[data-cmd="undo"]').disabled = !p.canUndo;
  $('[data-cmd="redo"]').disabled = !p.canRedo;

  if (msg) {
    $("#stMsg").textContent = msg;
    clearTimeout(onProjectChange._t);
    onProjectChange._t = setTimeout(() => ($("#stMsg").textContent = ""), 3200);
  }
}

/* ---------- 정합성 검증 요약 (상태바) ---------- */
let _vTimer = null;
function scheduleValidate() {
  clearTimeout(_vTimer);
  _vTimer = setTimeout(() => {
    try {
      const { summary } = validator.run();
      const el = $("#stValid");
      el.className = "stv " + (summary.오류 ? "err" : summary.경고 ? "warn" : "ok");
      el.textContent = summary.오류 ? `검증: 오류 ${summary.오류} · 경고 ${summary.경고}`
        : summary.경고 ? `검증: 경고 ${summary.경고} · 정보 ${summary.정보}`
        : `검증: 이상 없음`;
      el.title = "F5 — 정합성 검증 자세히 보기";
      el.onclick = () => doCommand("validate");
    } catch { /* 검증 실패는 조용히 무시 */ }
  }, 400);
}

/* ---------- 이벤트 결선 ---------- */
function wire() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cmd]");
    if (b && !b.disabled) doCommand(b.dataset.cmd);
  });

  // 메뉴바 판 고르개는 세 규정을 한꺼번에 옮긴다 (규정 하나만 옮기려면 ③ 창의 개정안 고르개)
  $("#versionSelect").addEventListener("change", (e) => project.switchVersion(e.target.value));
  // 그 규정의 개정안 고르개 — 그 개정안을 담은 판으로 옮겨 간다
  $("#editRevSelect").addEventListener("change", (e) => {
    const v = project.version(e.target.value);
    if (!v) return;
    // 그 규정만 옮긴다 — 나머지 규정은 보던 판을 그대로 본다
    project.switchTargetVersion(scopedTargetId(), v.id);
    const t = targetById(scopedTargetId());
    const reg = project.regNode(scopedTargetId());
    toast(`${t ? t.short + " " : ""}${reg?.revLabel || v.label} 개정안을 엽니다`
          + `${reg?.revTitle ? ` — ${reg.revTitle}` : ""}`, 3200);
  });

  // 개정안 창 하단 — 수정·신설만 골라 보기
  for (const b of document.querySelectorAll(".edit-foot .flt")) {
    b.addEventListener("click", () => {
      const key = b.dataset.flt || "";
      applyEditFilter(key === editFilter ? "" : key);   // 다시 누르면 풀린다
    });
  }

  for (const pane of refPanes) {
    const idx = pane.idx;
    $(`#refSelect${idx}`).addEventListener("change", async (e) => {
      await setRefDoc(pane.key, e.target.value);
      $(`#refSearch${idx}`).value = "";
      $(`#refHit${idx}`).textContent = "";
      // ① 창에서 개정 대상 규정을 고르면 ③ 창이 그 규정의 개정안으로 옮겨 간다
      if (idx === 1) {
        const tid = e.target.selectedOptions[0]?.dataset.target;
        if (tid) showTargetInEditTree(tid);
      }
    });
    $(`#refSearch${idx}`).addEventListener("input", () => runRefSearch(pane));
    $(`#refSearch${idx}`).addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      stepRefHit(pane, e.shiftKey ? -1 : 1);
    });
    $(`#refModes${idx}`).addEventListener("click", (e) => {
      const b = e.target.closest("[data-mode]");
      if (!b) return;
      pane.mode = b.dataset.mode;
      $(`#refModes${idx}`).querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      refTrees[pane.key].opts.displayMode = pane.mode;
      refTrees[pane.key].setData(pane.tree, pane.selectedId);
      refTrees[pane.key].setHighlight(pane.hits);
      project.setPaneState(pane.key, pane.doc?.id, pane.mode);
    });
  }

  $("#centerSearch").addEventListener("input", () => runCenterSearch());
  $("#centerSearch").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    stepCenterHit(e.shiftKey ? -1 : 1);
  });

  document.addEventListener("keydown", onKey);
  setupSplitters();
  setupRefSplitter();
  setRef2Visible(true);

  // 나갈 때 묻지 아니한다 — 자동으로 담기므로 잃을 것이 없다.
  // 다만 담는 중이면 마무리한다.
  window.addEventListener("pagehide", () => { AUTO.save(project.toJSON()); });
}

function onKey(e) {
  const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  const mod = e.ctrlKey || e.metaKey;

  if (mod && e.shiftKey && e.key.toLowerCase() === "v") { e.preventDefault(); doCommand("branch"); return; }
  if (e.key === "F5") { e.preventDefault(); doCommand("validate"); return; }
  if (mod && e.key.toLowerCase() === "i") { e.preventDefault(); doCommand("ai"); return; }
  if (mod && e.key.toLowerCase() === "e") { e.preventDefault(); doCommand("startEdit"); return; }
  if (mod && e.key.toLowerCase() === "h") { e.preventDefault(); doCommand("history"); return; }
  if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); doCommand("compare"); return; }
  if (mod && e.key.toLowerCase() === "f") { e.preventDefault(); $("#centerSearch").focus(); return; }
  // 편집 내용은 자동으로 담기므로 Ctrl+S 는 파일로 꺼내는 일을 맡는다
  if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); doCommand("export"); return; }
  if (mod && e.key.toLowerCase() === "g") { e.preventDefault(); doCommand("share"); return; }

  if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); doCommand("undo"); return; }
  if (mod && (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))) {
    e.preventDefault(); doCommand("redo"); return;
  }
  if (mod && e.key.toLowerCase() === "n") {
    e.preventDefault(); doCommand(e.shiftKey ? "addChild" : "addSibling"); return;
  }
  if (inField) return;

  if (e.key === "Tab") { e.preventDefault(); doCommand(e.shiftKey ? "promote" : "demote"); return; }
  if (e.altKey && e.key === "ArrowUp") { e.preventDefault(); doCommand("moveUp"); return; }
  if (e.altKey && e.key === "ArrowDown") { e.preventDefault(); doCommand("moveDown"); return; }
  if (e.key === "Delete") { e.preventDefault(); doCommand("del"); return; }
  if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); moveCursor(e.key === "ArrowDown" ? 1 : -1); return; }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const sel = project.selected;
    if (sel && sel.children.length) {
      const want = e.key === "ArrowLeft";
      if (sel.collapsed !== want) { e.preventDefault(); project.toggleCollapse(sel.id); }
    }
  }
}

function moveCursor(dir) {
  const visible = [];
  (function rec(list) {
    for (const n of list) { visible.push(n.id); if (n.children.length && !n.collapsed) rec(n.children); }
  })(project.tree);
  const i = visible.indexOf(project.selectedId);
  const j = Math.max(0, Math.min(visible.length - 1, (i < 0 ? 0 : i + dir)));
  project.select(visible[j]);
}

async function doCommand(cmd) {
  switch (cmd) {
    case "addSibling": {
      const sel = project.selected;
      const lv = sel ? sel.level : "편";
      project.addNode(lv, "sibling");
      break;
    }
    case "addChild": {
      const sel = project.selected;
      if (!sel) { project.addNode("편", "sibling"); break; }
      const idx = M.levelIndex(sel.level);
      if (idx >= M.LEVELS.length - 1) { toast("조 아래에는 하위 항목을 둘 수 없습니다."); break; }
      project.addNode(M.LEVELS[idx + 1], "child");
      break;
    }
    case "promote": project.promote(); break;
    case "demote": project.demote(); break;
    case "moveUp": project.moveVertical(-1); break;
    case "moveDown": project.moveVertical(1); break;
    case "del": {
      const sel = project.selected;
      if (!sel) break;
      const cnt = M.flatten([sel]).length - 1;
      if (cnt > 0 && !confirm(`${M.shortLabel(sel)} 와 하위 ${cnt}개 항목을 삭제합니다. 계속할까요?`)) break;
      project.remove();
      break;
    }
    case "undo": project.undo(); break;
    case "redo": project.redo(); break;

    case "compare": {
      if (project.versions.length < 2) { toast("비교할 버전이 하나뿐입니다. 새 버전을 만드세요.", 4000); break; }
      // 지금 보고 있는 규정의 개정안을 그 규정의 현행과 견준다
      compare.open(null, null, scopedTargetId());
      break;
    }
    case "versions": versions.open(); break;
    case "history": history.open(); break;
    case "ai": ai.open(); break;
    case "startEdit": startEditing(); break;
    case "apply": applyDetail(); break;
    case "validate": validator.open(); break;
    case "share": await share.open(); await loadSharedRefs(); updateRemoveButtons(); break;
    case "addRef2": setRef2Visible(true); break;
    case "closeRef2": setRef2Visible(false); break;
    case "openFile1": await importFileIntoPane(paneOf("ref1")); break;
    case "openFile2": await importFileIntoPane(paneOf("ref2")); break;
    case "shareRef1": await shareImported(paneOf("ref1")); break;
    case "shareRef2": await shareImported(paneOf("ref2")); break;
    case "clearSel1": clearPaneSel("ref1"); break;
    case "clearSel2": clearPaneSel("ref2"); break;
    case "clearSelEdit": clearDraftSel(); break;
    case "delRef1": removeImported(paneOf("ref1")); break;
    case "delRef2": removeImported(paneOf("ref2")); break;
    case "prev1": stepRefHit(paneOf("ref1"), -1); break;
    case "next1": stepRefHit(paneOf("ref1"), 1); break;
    case "prev2": stepRefHit(paneOf("ref2"), -1); break;
    case "next2": stepRefHit(paneOf("ref2"), 1); break;
    case "branch": {
      const src = project.current;
      const title = prompt("새 버전 설명을 입력하세요.", `${src ? src.label : ""} 에서 분기`);
      if (title === null) break;
      const v = project.createVersion({ title: title.trim() });
      if (v) toast(`${v.label} 을(를) 만들었습니다. 이제 ${v.label} 을(를) 편집합니다.`, 3000);
      break;
    }

    // 편집 내용은 자동으로 담기므로 '저장' 단추는 두지 아니한다.
    // 이 브라우저 밖으로 꺼낼 때에만 파일을 만든다 — 남에게 넘기거나 갈무리할 때.
    /* 보고서 한 벌 — 개정(안)·별표및별지모음·개정사유서·신구대조표를 zip 으로.
     *
     * HWPX 는 브라우저에서 만들 수 없다. 손으로 조립한 꾸러미는 한/글이
     * '손상된 파일' 로 보므로(forms_hwp.py 주석) 한/글에게 저장을 맡겨야 하고,
     * 그것은 이 컴퓨터의 python scripts/genreport.py 가 한다. 여기서는 그렇게
     * 만들어 둔 꾸러미를 내려받는다 — 언제 만든 것인지 함께 알린다. */
    case "report": {
      try {
        const meta = await (await fetch("data/report/index.json?t=" + Date.now())).json();
        const a = document.createElement("a");
        a.href = "data/report/개정보고서.zip?t=" + Date.now();
        a.download = meta.file || "개정보고서.zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
        const at = new Date(meta.at);
        const stale = (Date.now() - at.getTime()) / 86400000;
        toast(`보고서를 내려받습니다 — ${meta.file}
${(meta.items || []).join(" · ")} · ${(meta.bytes / 1024 / 1024).toFixed(1)} MB
만든 때 ${at.toLocaleString("ko-KR")}`
          + (stale > 1 ? `
이 뒤로 개정안을 고쳤다면 python scripts/genreport.py 로 다시 만드십시오.` : ""),
          stale > 1 ? 9000 : 6000);
      } catch {
        toast(`아직 만들어 둔 보고서가 없습니다.
python scripts/genreport.py 를 돌리면 만들어집니다.`, 7000);
      }
      break;
    }

    case "export": {
      try {
        const payload = project.toJSON();
        const mb = JSON.stringify(payload).length / 1024 / 1024;
        const r = await FS.saveProject(payload, { forceDialog: true });
        const extra = `버전 ${project.versions.length}개`
          + (project.refDocs.length ? ` · 참조 규정 ${project.refDocs.length}건` : "")
          + ` · ${mb.toFixed(1)} MB`;
        toast(`내보냈습니다 — ${r.name}
${extra}` + (r.warning ? `
${r.warning}` : ""),
              r.warning ? 9000 : 4000);
        await pushToShare();
      } catch (err) {
        if (err && err.name !== "AbortError") toast("내보내기 실패: " + err.message, 5000);
      }
      break;
    }

    case "scopeAll": showAllTargets(); break;

    /* 개정안 이름 바꾸기 — 판 이름은 세 규정을 아우른 것이라 규정 하나만
       놓고 보면 뜻이 없다. 작업규정으로는 둘째 판인데 판 이름이 v4 인 일이
       생긴다. 규정마다 지닌 제 이름을 고친다. */
    case "renameRev": {
      const tid = scopedTargetId();
      const reg = tid ? project.regNode(tid) : null;
      if (!reg) { toast("규정을 먼저 고르십시오.", 3000); break; }
      const vid = $("#editRevSelect")?.value || project.currentId;
      const cur = project.version(vid);
      const r = cur ? (cur.tree || []).find((n) => M.isRegNode(n) && n.targetId === tid) : null;
      if (!r) break;
      const label = prompt(
        `개정안 이름을 적으십시오 — ${targetById(tid)?.short || ""}` + NL
        + `(판 이름 '${cur.label}' 은 세 규정을 아우른 것이라 그대로 둡니다)`,
        r.revLabel || "");
      if (label === null) break;
      const title = prompt("설명을 적으십시오 (비워 두어도 됩니다).", r.revTitle || "");
      if (title === null) break;
      project.renameRev(tid, vid, label, title);
      $("#editRevSelect").dataset.sig = "";     // 목록을 다시 세운다
      paintEditHead();
      break;
    }

    /* 피인용조문 검색 — 이 규정이 부르는 남의 조문이 아직 성한지 본다.
       라이브러리에 색인된 규정의 조문 트리를 잣대로 삼는다. 색인이 없는
       규정은 '확인필요' 로 남긴다 — 모르는 것을 성하다고 하지 않는다. */
    case "cites": {
      const reg = project.regNode(scopedTargetId()) || project.regNodes[0];
      if (!reg) break;
      const cites = scanCitations(reg);
      if (!cites.length) { toast("이 규정에는 조 번호까지 적은 인용이 없습니다.", 3500); break; }
      busy(`인용 ${cites.length}건을 견주는 중…`);
      const ids = neededDocs(cites, library.regulations);
      const docs = new Map();
      for (const id of ids) {
        try { docs.set(id, await loadReg(id)); } catch { /* 못 읽으면 확인필요로 남는다 */ }
      }
      busy(false);
      citecheck.open(gradeAll(cites, library.regulations, docs),
        { regName: reg.title, indexed: docs.size });
      break;
    }
    /* 규정 사이에서 갈린 말을 맞춘다 — 무엇을 왜 바꾸는지 먼저 보이고 묻는다.
       고친 조문마다 근거(현행 고시 명칭 + 국가공간정보 표준용어집 인용표준번호)를
       남기므로, 그것이 그대로 개정사유서와 신구대조표 비고란으로 간다. */
    case "terms": {
      const dry = project.unifyTerms({ dryRun: true });
      if (!dry.count) {
        toast("규정 사이에서 갈린 말이 없습니다 — 이미 다 맞춰져 있습니다.", 4000);
        break;
      }
      termsView.open(dry, TERM_RULES);
      break;
    }

    case "reset": {
      if (!confirm("지금까지 고친 내용이 모두 사라지고 현행 규정에서 다시 시작합니다. "
                   + "이 브라우저에 담아 둔 것도 함께 지웁니다. 계속할까요?")) break;
      await AUTO.clear();
      FS.resetTarget();
      const entries = [];
      for (const t of allTargets()) {
        const regId = baseRegIdOf[t.id];
        if (!regId) continue;
        let draft = null;
        if (t.draft) { try { draft = await FS.loadJSON(t.draft); } catch { /* 없으면 현행에서 */ } }
        entries.push({ target: t, doc: await loadReg(regId), draft, regId });
      }
      project.loadFromTargets(entries);
      _followingTarget = null;
      await followActiveTarget();
      toast("현행 규정으로 초기화했습니다.");
      break;
    }
  }
}

/* ============================================================
   검색 → 해당 조문으로 이동 + 조문 상세 표시
   ============================================================ */
let centerHits = [], centerAt = -1;

function runCenterSearch() {
  const q = $("#centerSearch").value;
  if (!q.trim()) {
    centerHits = []; centerAt = -1;
    editTree.setHighlight([]);
    $("#searchCount").textContent = "";
    return;
  }
  centerHits = M.search(project.tree, q);
  centerAt = -1;
  expandTo(project.tree, centerHits);
  setEditTree(project.selectedId);
  editTree.setHighlight(centerHits);
  $("#searchCount").textContent = centerHits.length ? `0/${centerHits.length}` : "없음";
  if (centerHits.length) stepCenterHit(1);
}

function stepCenterHit(dir) {
  if (!centerHits.length) return;
  centerAt = (centerAt + dir + centerHits.length) % centerHits.length;
  const id = centerHits[centerAt];
  expandAncestors(project.tree, id);
  project.select(id);                       // 상세 패널은 onProjectChange 가 갱신
  setEditTree(id);
  editTree.setHighlight(centerHits);
  $("#searchCount").textContent = `${centerAt + 1}/${centerHits.length}`;
  editTree.scrollToId?.(id);
}

function runRefSearch(pane) {
  const q = $(`#refSearch${pane.idx}`).value;
  const view = refTrees[pane.key];
  if (!q.trim()) {
    pane.hits = []; pane.hitAt = -1;
    view.setHighlight([]);
    $(`#refHit${pane.idx}`).textContent = "";
    return;
  }
  pane.hits = M.search(pane.tree, q);
  pane.hitAt = -1;
  expandTo(pane.tree, pane.hits);
  view.setData(pane.tree, pane.selectedId);
  view.setHighlight(pane.hits);
  $(`#refHit${pane.idx}`).textContent = pane.hits.length ? `0/${pane.hits.length}` : "없음";
  if (pane.hits.length) stepRefHit(pane, 1);
}

function stepRefHit(pane, dir) {
  if (!pane.hits.length) return;
  pane.hitAt = (pane.hitAt + dir + pane.hits.length) % pane.hits.length;
  const id = pane.hits[pane.hitAt];
  expandAncestors(pane.tree, id);
  pane.selectedId = id;
  const view = refTrees[pane.key];
  view.setData(pane.tree, id);
  view.setHighlight(pane.hits);
  $(`#refHit${pane.idx}`).textContent = `${pane.hitAt + 1}/${pane.hits.length}`;

  refreshRefDetail(pane);
  view.scrollToId?.(id);
}

/** 대상 노드의 조상들을 모두 펼친다 */
function expandAncestors(tree, id) {
  const path = M.pathOf(tree, id);
  for (let i = 0; i < path.length - 1; i++) path[i].collapsed = false;
}

/* ============================================================
   파일 열기 → 색인화 → (외국어면) 한글 대역 생성
   ============================================================ */
function pickRefFile() {
  return new Promise((resolve) => {
    const input = $("#refFilePicker");
    input.value = "";
    input.onchange = () => resolve(input.files && input.files[0] ? input.files[0] : null);
    input.click();
  });
}

function guessLang(lines) {
  const s = lines.slice(0, 500).join(" ");
  const ja = (s.match(/[぀-ヿ]/g) || []).length;          // 히라가나·가타카나
  const ko = (s.match(/[가-힣]/g) || []).length;
  const en = (s.match(/[A-Za-z]/g) || []).length;
  if (ko > ja && ko > en / 3) return "ko";
  if (ja > 20) return "ja";
  if (en > 200) return "en";
  return "ko";
}

async function importFileIntoPane(pane) {
  const file = await pickRefFile();
  if (!file) return;
  busy(`${file.name} 읽는 중…`);
  try {
    const { lines, kind, native } = await extractLines(file, (m) => busy(m));

    let doc;
    if (native) {
      doc = Object.assign({}, native, { id: `imp${++importedSeq}`, name: native.name || file.name });
    } else {
      busy("구조 분석 중…");
      const r = buildAuto(lines);
      const { tree, stats, mode } = r;
      if (!stats.조 && !stats.편 && !stats.장) {
        throw new Error("구조를 찾지 못했습니다.\n조문 형식(제N조 / 第N条) 또는 번호 매김 목차(1.2.3)가 있는 문서인지 확인해 주세요.");
      }
      const lang = guessLang(lines);
      doc = {
        id: `imp${++importedSeq}`,
        name: file.name.replace(/\.[^.]+$/, ""),
        org: "가져온 파일", kind: kind.toUpperCase(), no: "-", effective: "",
        lang, stats, tree, annex: [], source: "",
        indexMode: mode,
        imported: { fileName: file.name, kind, lines: lines.length, unmatched: r.unmatched || 0 },
      };

      if (lang === "ja" || lang === "en") {
        busy("한글 대역 생성 중…");
        const r = translateTree(tree, lang);
        doc.translated = { lang, coverage: r.coverage, dict: DICT_SIZE[lang] };
      }
    }

    // 프로젝트에 보관 → .pmproj 에 함께 저장된다
    project.addRefDoc(doc);
    syncRefLibrary();
    $(`#refSelect${pane.idx}`).value = doc.id;
    await setRefDoc(pane.key, doc.id);
    project.emit(`참조 규정 추가: ${doc.name}`);

    const t = doc.translated;
    toast(
      `${doc.name} — ${doc.indexMode === "목차" ? "목차 기준으로 " : ""}` +
      `${doc.stats.편 ? `1단 ${doc.stats.편} · ` : ""}2단 ${doc.stats.장} · 항목 ${doc.stats.조} 로 색인했습니다.` +
      (t ? `\n한글 대역 생성 완료 (용어 ${t.dict}개 적용, 치환률 약 ${Math.round(t.coverage * 100)}%). '표시' 에서 번역·대역으로 볼 수 있습니다.` : ""),
      t ? 8000 : 4500);
  } catch (err) {
    console.error(err);
    toast("파일을 열지 못했습니다.\n" + (err.message || err), 8000);
  } finally {
    busy(false);
  }
}

function removeImported(pane) {
  const d = pane.doc && project.refDoc(pane.doc.id);
  if (!d) return;
  if (!confirm(`불러온 참조 규정 「${d.name}」 을(를) 프로젝트에서 제거합니다.\n계속할까요?`)) return;
  project.removeRefDoc(d.id);
  library.regulations = library.regulations.filter((r) => r.id !== d.id);
  refCache.delete(d.id);
  syncRefLibrary();
  const first = library.regulations.find((r) => r.hasFullText && !r.imported);
  if (first) { $(`#refSelect${pane.idx}`).value = first.id; setRefDoc(pane.key, first.id); }
  toast(`제거했습니다 — ${d.name}`);
}

/* ============================================================
   참조 규정 드롭다운
     ① 창 — 핵심 규정(개정 대상)만
     ② 창 — 나머지를 다섯 묶음으로
          1 규정 내 별도규정 → 2 상위법령 → 3 하위규정
          → 4 국외 관련규정 → 5 기타 관련규정
   ------------------------------------------------------------
   '규정 내 별도규정' 은 공공측량 작업규정 조문이 「…」 로 인용하는 규정이다.
   scripts/gencites.py 가 library.json 의 citedIn 에 인용 조문을 적어 둔다.
   ============================================================ */
/* 묶음 차례는 손대는 규정마다 다르다 — 고정값이 아니라 그때그때 읽는다 */
const catOrder = () => (APP && APP.catOrder) || [];

/** KDS·KCS 계열은 상위 고시와 하위 기준을 한 묶음으로 본다 */
const isKdsKcs = (r) => r.category === "kds" || /(?:KDS|KCS)\s*12\s/.test(String(r.name || "") + " ");

/**
 * 규정 하나가 어느 묶음에 들어가는지
 * 성과심사·지하시설물은 폴더대로 따로 묶는다 — 인용 여부보다 먼저 본다.
 * (인용된 조문은 항목 옆에 그대로 표시되므로 정보가 사라지지 않는다)
 * 프로파일이 regroup 을 두면 그 결과를 한 번 더 손본다
 * (무인비행장치 편집기는 영상·점군 성과 규정을 앞 묶음으로 당긴다).
 */
function groupOf(r) {
  const g = baseGroupOf(r);
  // 무인비행장치 규정은 영상·점군 성과 규정을 앞 묶음으로 당긴다 (등록부의 aerial)
  if (APP && APP.aerialSet && APP.aerialSet.has(r.id)) return "aerial";
  return g;
}

function baseGroupOf(r) {
  if (r.category === "core") return "core";
  if (r.category === "review") return "review";
  if (r.category === "under") return "under";
  if (r.category === "safety") return "safety";
  if (isKdsKcs(r)) return "kds";
  if (r.citedIn && r.citedIn.length) return "cited";
  if (r.category === "law") return "law";
  if (r.category === "sub") return "sub";
  if (r.category === "intl") return "intl";
  return "etc";
}

/** 인용 조문 요약 — "제61조 외 4곳" */
function citedHint(r) {
  const c = r.citedIn || [];
  if (!c.length) return "";
  return c.length === 1 ? `  · ${c[0]}` : `  · ${c[0]} 외 ${c.length - 1}곳`;
}

function optionOf(r, cat) {
  // 조문이 없는 기준서(KDS·KCS·국외 사양서)는 편·장 수로 크기를 보인다
  const st = r.stats || {};
  const size = st.조 ? `  · ${st.조}조`
    : (st.편 || st.장) ? `  · 편 ${st.편 || 0} · 장 ${st.장 || 0}` : "";
  const tail = r.hasFullText ? `${size}${citedHint(r)}` : "  (파일만 보유 · 미색인)";
  return `<option value="${r.id}"${r.hasFullText ? "" : " disabled"}>${esc(r.name)}${tail}</option>`;
}

/**
 * @param {1|2} idx 어느 창의 목록인가
 */
/** 이 규정이 ① 창(개정 대상)에 드는가 — 손대는 대상이 정한다 */
function isCoreReg(r, group) {
  if (!APP) return false;
  return APP.coreGroup ? group === APP.coreGroup : r.name === APP.base;
}

function buildRefOptions(idx) {
  const pool = library.regulations.filter((r) => !r.imported && !r.shared);

  if (idx === 1) {
    /* ① 창에는 개정 대상 세 규정을 모두 띄운다.
       예전에는 이 편집기가 고치는 규정 하나만 있었다. 편집기를 합친 뒤로는
       세 규정을 오가므로, 여기서 규정을 고르면 ③ 창이 그 규정의 개정안으로
       따라간다 (③ 에서 고르면 ① 이 따라오는 것과 짝을 이룬다). */
    const byId = new Map(pool.map((r) => [r.id, r]));
    const opts = [];
    for (const t of allTargets()) {
      const r = byId.get(baseRegIdOf[t.id]);
      if (!r) continue;
      const on = t.id === (APP && APP.id) ? " selected" : "";
      opts.push(`<option value="${r.id}" data-target="${t.id}"${on}>`
        + `${esc(t.short)} — ${esc(r.name)}${r.stats?.조 ? `  · ${r.stats.조}조` : ""}</option>`);
    }
    if (!opts.length) {                       // 등록부를 아직 못 읽었을 때
      const core = pool.filter((r) => isCoreReg(r, groupOf(r)));
      return `<optgroup label="${APP.coreLabel} (${core.length})">`
        + core.map((r) => optionOf(r, "core")).join("") + `</optgroup>`;
    }
    return `<optgroup label="개정 대상 (${opts.length}종)">${opts.join("")}</optgroup>`;
  }

  const groups = new Map(catOrder().map(([k]) => [k, []]));
  for (const r of pool) {
    const g = groupOf(r);
    if (isCoreReg(r, g)) continue;                         // ② 창에는 넣지 않는다
    groups.get(g)?.push(r);
  }
  // 인용이 있는 묶음은 많이 인용된 것부터
  for (const k of ["cited", "review", "under"]) {
    groups.get(k)?.sort((a, b) =>
      ((b.citedIn || []).length - (a.citedIn || []).length)
      || a.name.localeCompare(b.name, "ko"));
  }

  let html = "";
  for (const [cat, label] of catOrder()) {
    const list = groups.get(cat);
    if (!list.length) continue;
    html += `<optgroup label="${label} (${list.length})">`
      + list.map((r) => optionOf(r, cat)).join("") + `</optgroup>`;
  }
  return html;
}

/* ---------- 개정안 창 — 상태로 골라 보기 ---------- */
/** 단추 이름 → 그 상태인가 (이동·수정 은 '수정' 에 든다) */
const FILTERS = {
  "수정": (n) => String(n.status || "").includes("수정"),
  "신설": (n) => String(n.status || "").includes("신설"),
  // 용어를 바로잡은 것만 — 공청회에서 다툴 것과 다투지 아니할 것을 가른다.
  // gendraft2025.py 가 연구 검토의 '용어 오류·불일치' 지적이 걸린 조문에 표시해 둔다
  "용어": (n) => n.changeKind === "용어",
};
let editFilter = "";                 // "" 이면 전부 보인다

/** 걸리는 것을 조문과 별표·별지로 나누어 센다 */
function countStatus(fn) {
  let jo = 0, anx = 0;
  M.walk(project.tree, (x) => {
    if (x.level !== "조" || !fn(x)) return;
    if (x.annexRef || x.isAnnex) anx += 1; else jo += 1;
  });
  return { jo, anx, all: jo + anx };
}

function updateFilterCounts() {
  for (const b of document.querySelectorAll(".edit-foot .flt[data-flt]")) {
    const key = b.dataset.flt;
    if (!key) continue;
    b.querySelector(".n").textContent = ` ${countStatus(FILTERS[key]).jo}`;
  }
}

function applyEditFilter(key) {
  editFilter = FILTERS[key] ? key : "";
  editTree.setFilter(editFilter ? FILTERS[editFilter] : null);
  for (const b of document.querySelectorAll(".edit-foot .flt")) {
    b.classList.toggle("on", (b.dataset.flt || "") === editFilter);
    b.classList.toggle("off", (b.dataset.flt || "") !== editFilter);
  }
  if (!editFilter) {
    $("#editHint").textContent = "노드를 끌어 위치를 바꾸면 조 번호가 자동으로 다시 매겨집니다.";
    return;
  }
  const c = countStatus(FILTERS[editFilter]);
  const lbl = editFilter === "용어" ? "용어를 바로잡은" : `${editFilter}`;
  $("#editHint").textContent =
    `${lbl} 조문 ${c.jo}개${c.anx ? ` · 별표·별지 ${c.anx}건` : ""} 만 보입니다. [전체] 로 되돌립니다.`;
}

/** 프로젝트에 보관된 참조 규정을 두 창의 드롭다운·캐시에 반영 */
function syncRefLibrary() {
  for (const d of project.refDocs) {
    refCache.set(d.id, d);
    if (!library.regulations.some((r) => r.id === d.id)) {
      library.regulations.push({
        id: d.id, name: d.name, org: d.org, kind: d.kind, no: d.no,
        effective: d.effective, lang: d.lang, category: "imported",
        source: "", stats: d.stats, file: null, hasFullText: true, imported: true,
      });
    }
  }
  for (const p of refPanes) {
    const sel = $(`#refSelect${p.idx}`);
    const keep = sel.value;
    let g = sel.querySelector('optgroup[data-imported]');
    if (project.refDocs.length === 0) { g?.remove(); continue; }
    if (!g) {
      g = document.createElement("optgroup");
      g.dataset.imported = "1";
      sel.insertBefore(g, sel.firstChild);
    }
    g.label = `가져온 파일 (${project.refDocs.length})`;
    g.innerHTML = project.refDocs.map((d) =>
      `<option value="${d.id}">${esc(d.name)}${d.stats?.조 ? `  · ${d.stats.조}조` : ""}${d.translated ? "  (한글 대역)" : ""}</option>`).join("");
    if ([...sel.options].some((o) => o.value === keep)) sel.value = keep;
  }
  updateRemoveButtons();
  for (const i of [1, 2]) pickers[i]?.refresh();
}

function updateRemoveButtons() {
  for (const p of refPanes) {
    const imported = !!(p.doc && project.refDoc(p.doc.id));
    $(`#refDel${p.idx}`).classList.toggle("hidden", !imported);
    $(`#refShare${p.idx}`).classList.toggle("hidden", !(imported && GH.hasToken() && GH.getConfig().owner));
  }
}

/** 불러온 참조 규정을 공유 저장소에 올린다 */
async function shareImported(pane) {
  const d = pane.doc && project.refDoc(pane.doc.id);
  if (!d) return;
  if (!GH.hasToken() || !GH.getConfig().owner) {
    toast("먼저 [공유 저장소] 에서 저장소를 연결하세요.", 4500);
    return;
  }
  if (!confirm(`「${d.name}」 을(를) 공유 저장소에 올립니다.
같은 이름이 있으면 갱신됩니다. 계속할까요?`)) return;
  busy("공유 저장소에 올리는 중…");
  try {
    const r = await GH.writeRef(d);
    d.shared = { path: r.path, at: new Date().toISOString() };
    await loadSharedRefs();
    toast(`공유했습니다 — ${r.name}
다른 사람은 참조 규정 목록의 [공유 규정] 에서 바로 열 수 있습니다.`, 6000);
  } catch (e) {
    toast("공유 실패: " + e.message, 6000);
  } finally { busy(false); }
}

/** 저장소에 올라와 있는 참조 규정을 목록에 반영 */
let sharedRefs = [];
async function loadSharedRefs() {
  if (!GH.hasToken() || !GH.getConfig().owner) return;
  try { sharedRefs = await GH.listRefs(); } catch { sharedRefs = []; }
  for (const p of refPanes) {
    const sel = $(`#refSelect${p.idx}`);
    const keep = sel.value;
    let g = sel.querySelector("optgroup[data-shared]");
    if (!sharedRefs.length) { g?.remove(); continue; }
    if (!g) {
      g = document.createElement("optgroup");
      g.dataset.shared = "1";
      sel.insertBefore(g, sel.firstChild);
    }
    g.label = `공유 규정 (${sharedRefs.length})`;
    g.innerHTML = sharedRefs.map((r) =>
      `<option value="shared:${esc(r.path)}">${esc(r.name)}</option>`).join("");
    if ([...sel.options].some((o) => o.value === keep)) sel.value = keep;
  }
  for (const i of [1, 2]) pickers[i]?.refresh();
}

/** 저장된 참조 창 상태(문서·표시모드) 복원 */
async function restorePaneStates() {
  for (const pane of refPanes) {
    const st = project.ui[pane.key];
    if (!st || !st.docId) continue;
    const sel = $(`#refSelect${pane.idx}`);
    if (![...sel.options].some((o) => o.value === st.docId)) continue;
    sel.value = st.docId;
    pane.mode = st.mode || "orig";
    await setRefDoc(pane.key, st.docId);
  }
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- 보조 ---------- */
function busy(msg) {
  const el = $("#busy");
  if (msg === false) { el.classList.add("hidden"); return; }
  $("#busyMsg").textContent = msg;
  el.classList.remove("hidden");
}

function expandTo(tree, ids) {
  const set = new Set(ids);
  (function rec(list) {
    let any = false;
    for (const n of list) {
      const inner = rec(n.children);
      const self = set.has(n.id);
      if (inner) n.collapsed = false;
      if (inner || self) any = true;
    }
    return any;
  })(tree);
}

function setRef2Visible(show) {
  $("#refBlock2").classList.toggle("hidden", !show);
  $("#refSplit").classList.toggle("hidden", !show);
  $("#btnAddRef2").classList.toggle("hidden", show);
  if (show) refTrees.ref2?.render();
}

/** 참조 창 사이 가로 분할선 */
function setupRefSplitter() {
  const sp = $("#refSplit");
  sp.addEventListener("mousedown", (e) => {
    e.preventDefault();
    sp.classList.add("dragging");
    const b2 = $("#refBlock2");
    const startY = e.clientY;
    const startH = b2.getBoundingClientRect().height;
    const total = $(".pane-ref").getBoundingClientRect().height;
    const onMove = (ev) => {
      const h = Math.max(90, Math.min(total - 150, startH - (ev.clientY - startY)));
      b2.style.height = h + "px";
    };
    const onUp = () => {
      sp.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

function setupSplitters() {
  document.querySelectorAll(".splitter").forEach((sp) => {
    sp.addEventListener("mousedown", (e) => {
      e.preventDefault();
      sp.classList.add("dragging");
      // 늘어나는 칸(조문 상세) 말고 고정 칸의 폭을 바꾼다
      const left = sp.previousElementSibling;
      const right = sp.nextElementSibling;
      const growL = parseFloat(getComputedStyle(left).flexGrow) || 0;
      const target = growL > 0 ? right : left;
      const sign = target === left ? 1 : -1;
      const startX = e.clientX;
      const startW = target.getBoundingClientRect().width;
      const onMove = (ev) => {
        const w = Math.max(200, Math.min(900, startW + sign * (ev.clientX - startX)));
        target.style.width = w + "px";
        target.style.flex = "none";
        target.style.maxWidth = "none";
      };
      const onUp = () => {
        sp.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

function fmtDate(d) {
  if (!d) return "";
  if (d.length === 8) return `${d.slice(0, 4)}. ${+d.slice(4, 6)}. ${+d.slice(6, 8)}.`;
  if (d.length === 6) return `${d.slice(0, 4)}. ${+d.slice(4, 6)}.`;
  return d;
}

/**
 * 규정 창의 머리글 — 매뉴얼·기준서처럼 고시번호나 시행일이 없는 문서도 있다.
 * 없는 것은 '제-호' 로 채우지 아니하고 뺀다.
 */
function metaLine(d) {
  const no = d.no && d.no !== "-" ? String(d.no) : "";
  const dt = fmtDate(d.effective);
  return `${d.org} ${d.kind}`
    + (no ? ` 제${no}호` : "")
    + (dt ? ` · ${no ? "시행 " : ""}${dt}` : "");
}

let toastTimer;
function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), ms);
}
