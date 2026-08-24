/* ============================================================
   scripts/genreport_web.mjs — 화면의 [보고서] 와 똑같은 꾸러미를 파일로
   ------------------------------------------------------------
   화면에서 [보고서] 를 누르면 브라우저가 지어 내려받는다. 그런데 그것을
   어느 폴더에 넣어 달라고 하면 브라우저는 할 수 없는 일이다 — 내려받는
   자리를 고르는 것은 사람의 몫이기 때문이다.

   그래서 같은 코드를 Node 에서 돌린다. 조립도 화면과 같은 것을 쓴다
   (core/project.js 의 loadFromTargets, ui/report.js 의 buildReport).
   두 벌을 두지 아니하므로 화면에서 받은 것과 여기서 만든 것이 같다.

   사용:
     node scripts/genreport_web.mjs --reg uav --out "D:\\어느\\폴더"
     node scripts/genreport_web.mjs --reg uav --rev 1     (판을 골라)
     node scripts/genreport_web.mjs --list                (무엇이 있는지)

   --reg 를 주지 아니하면 등록부의 규정을 모두 담는다.
   ============================================================ */

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const DATA = path.join(ROOT, "data");

const imp = (rel) => import(pathToFileURL(path.join(ROOT, rel)).href);

const readJson = async (p) => JSON.parse(await fs.readFile(p, "utf8"));

function arg(name, dflt = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}
const has = (name) => process.argv.includes(name);

const main = async () => {
  const { Project } = await imp("js/core/project.js");
  const M = await imp("js/core/model.js");
  const { buildReport } = await imp("js/ui/report.js");

  const library = await readJson(path.join(DATA, "library.json"));
  const tj = await readJson(path.join(DATA, "targets.json"));
  const targets = tj.targets || tj;

  if (has("--list")) {
    for (const t of targets) console.log(`  ${t.id.padEnd(8)} ${t.short || t.base}`);
    return;
  }

  const want = arg("--reg");
  const use = want ? targets.filter((t) => t.id === want) : targets;
  if (!use.length) throw new Error(`등록부에 없는 규정입니다 — ${want}`);

  // 화면이 하는 것과 같은 차례로 담는다
  const entries = [];
  for (const t of use) {
    const meta = (library.regulations || []).find((r) => r.name === t.base);
    if (!meta) { console.warn(`라이브러리에서 못 찾음 — ${t.base}`); continue; }
    const doc = await readJson(path.join(DATA, meta.file));
    let draft = null;
    if (t.draft) {
      try { draft = await readJson(path.join(ROOT, t.draft)); } catch { /* 없으면 현행에서 */ }
    }
    entries.push({ target: t, doc, draft, regId: meta.id });
  }
  if (!entries.length) throw new Error("개정 대상 규정을 하나도 불러오지 못했습니다.");

  M.setRootLevel(use[0].top || "편");
  const project = new Project();
  project.loadFromTargets(entries);

  // 판 고르기 — 무인비행장치처럼 개정안이 여러 벌인 규정이 있다
  const revIdx = arg("--rev");
  if (revIdx !== null) {
    const list = project.versions.filter((v) => !v.readonly);
    const v = list[Number(revIdx) - 1];
    if (!v) throw new Error(`--rev ${revIdx} 은(는) 없습니다 — 1..${list.length}`);
    /* currentId 만 갈아서는 트리가 그대로다 — switchVersion 이 currentByTarget
       까지 맞추고 composeTree() 로 트리를 다시 세운다. 처음에 손으로 갈았다가
       판을 바꾸어도 같은 판이 나왔다. */
    project.switchVersion(v.id);
  }

  const cur = want ? project.versionOf(want) : project.current;
  /* 규정 하나만 담을 때에는 그 규정의 개정안 이름(vC-1.01 따위)을 파일 이름에
     넣는다. 판이 여러 벌인 규정이 있어(무인비행장치가 그렇다) 넣지 아니하면
     판만 다른 꾸러미가 같은 이름으로 나온다. */
  const regNode = want ? project.regNode(want) : null;
  const rev = regNode && regNode.revLabel ? regNode.revLabel : "";
  console.log(`담는 판 : ${rev || (cur ? cur.label : "—")}`
    + `${regNode && regNode.revTitle ? ` · ${regNode.revTitle}` : ""}`);

  // 판 이름은 buildReport 가 파일 이름에 넣는다 — 화면에서 받는 것과 같아진다
  const r = await buildReport(project, { targetId: want || null });

  const outDir = arg("--out", path.join(DATA, "report"));
  await fs.mkdir(outDir, { recursive: true });
  const dst = path.join(outDir, r.name);
  await fs.writeFile(dst, Buffer.from(await r.blob.arrayBuffer()));

  const mb = (r.blob.size / 1048576).toFixed(2);
  console.log(`\n만들었습니다 — ${dst}`);
  console.log(`  규정 ${r.regs}종 · ${mb} MB`);
  for (const it of r.items) console.log(`  · ${it}`);
};

main().catch((e) => { console.error("실패:", e.message); process.exit(1); });
