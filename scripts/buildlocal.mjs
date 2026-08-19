/* ============================================================
   buildlocal.mjs — 글줄 → 조문 트리 JSON

   앱이 '파일 열기' 로 색인할 때 쓰는 바로 그 모듈(core/structure.js,
   core/translate.js)을 그대로 불러 쓴다. 화면에서 연 결과와 어긋나지 않는다.

   사용:  node scripts/buildlocal.mjs <lines.json> <meta.json> <out.json>
     lines.json : ["글줄", …]
     meta.json  : {id,name,org,kind,no,effective,lang,category,source,path}
   ============================================================ */
import { readFileSync, writeFileSync } from "node:fs";
import { buildAuto } from "../js/core/structure.js?v=20260814l";
import { translateTree, DICT_SIZE } from "../js/core/translate.js?v=20260814l";

const [linesPath, metaPath, outPath] = process.argv.slice(2);
if (!linesPath || !metaPath || !outPath) {
  console.error("사용: node scripts/buildlocal.mjs <lines.json> <meta.json> <out.json>");
  process.exit(1);
}

const lines = JSON.parse(readFileSync(linesPath, "utf-8"));
const meta = JSON.parse(readFileSync(metaPath, "utf-8"));

const r = buildAuto(lines);
const { tree, stats, mode } = r;

if (!stats.조 && !stats.편 && !stats.장) {
  console.error("구조를 찾지 못했습니다 (조문·목차 형식 아님)");
  process.exit(2);
}

const doc = {
  id: meta.id,
  name: meta.name,
  org: meta.org || "",
  kind: meta.kind || "",
  no: meta.no || "-",
  promulgated: meta.promulgated || "",
  effective: meta.effective || "",
  lang: meta.lang || "ko",
  category: meta.category || "etc",
  source: meta.source || "",
  stats,
  annex: [],
  annexTree: [],
  indexMode: mode,
  localFile: meta.path || "",
  tree,
};

if (meta.lang === "ja" || meta.lang === "en") {
  const t = translateTree(tree, meta.lang);
  doc.translated = { lang: meta.lang, coverage: t.coverage, dict: DICT_SIZE[meta.lang] };
}

writeFileSync(outPath, JSON.stringify(doc), "utf-8");

const t = doc.translated;
console.log(JSON.stringify({
  mode, stats,
  translated: t ? Math.round(t.coverage * 100) : null,
  unmatched: r.unmatched || 0,
}));
