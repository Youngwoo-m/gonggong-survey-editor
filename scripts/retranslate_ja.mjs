/* ============================================================
   scripts/retranslate_ja.mjs — 일본 규정의 한글 대역을 다시 만든다
   ------------------------------------------------------------
   낱말 사전(translate.js)에 가타카나 낱말표와 한자 음독표
   (jafallback.js)를 더한 뒤, loc11·loc12 의 대역을 새로 만든다.
   원문(origTitle·origBody)은 손대지 않는다.

   실행:  node scripts/retranslate_ja.mjs
   ============================================================ */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { translateVia } from "../js/core/translate.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(path.dirname(HERE), "data");
const JA = /[぀-ヿ一-鿿]/g;

function left(s) {
  return ((s || "").match(JA) || []).length;
}

for (const rid of ["loc11", "loc12"]) {
  const p = path.join(DATA, `${rid}.json`);
  const doc = JSON.parse(fs.readFileSync(p, "utf-8"));
  let n = 0, before = 0, after = 0, orig = 0;

  const walk = (ns) => {
    for (const x of ns) {
      const ot = x.origTitle ?? x.title;
      const ob = x.origBody ?? x.body;
      if (ot || ob) {
        before += left(x.transTitle) + left(x.transBody);
        x.origTitle = ot;
        x.origBody = ob;
        x.transTitle = translateVia(ot, "ja");
        x.transBody = translateVia(ob, "ja");
        after += left(x.transTitle) + left(x.transBody);
        orig += left(ot) + left(ob);
        n += 1;
      }
      walk(x.children || []);
    }
  };
  walk(doc.tree || []);

  const cov = orig ? Math.max(0, 1 - after / orig) : 1;
  doc.translated = { lang: "ja", coverage: cov, dict: doc.translated?.dict ?? 0 };
  fs.writeFileSync(p, JSON.stringify(doc), "utf-8");

  // 목록의 대역률도 함께 고친다
  const lp = path.join(DATA, "library.json");
  const lib = JSON.parse(fs.readFileSync(lp, "utf-8"));
  for (const r of lib.regulations) {
    if (r.id === rid) r.translated = { ...(r.translated || {}), lang: "ja", coverage: cov };
  }
  fs.writeFileSync(lp, JSON.stringify(lib), "utf-8");

  const pct = (v) => (v * 100).toFixed(1) + "%";
  console.log(`${rid} — 마디 ${n} · 남은 일본어 ${before} → ${after} 자 · 대역률 ${pct(cov)}`);
}
