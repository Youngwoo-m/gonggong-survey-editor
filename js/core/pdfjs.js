/* ============================================================
   core/pdfjs.js — 저장소에 넣어 둔 pdf.js 를 불러 온다
   ------------------------------------------------------------
   ■ 왜 따로 두는가

     별표 미리보기에서 「PDF 를 열지 못했습니다」 가 떴다. PDF 가 상한 것이
     아니라 pdf.js 모듈 자체를 못 불러온 것이었다.

       Failed to fetch dynamically imported module: …/vendor/pdfjs/pdf.min.mjs

     까닭은 서버가 .mjs 를 text/plain 으로 내주었기 때문이다. 브라우저는
     자바스크립트 MIME 이 아니면 ES 모듈을 실행하지 않는다.

       serve.py        text/javascript   ← 제대로 내준다
       미리보기 서버    text/plain        ← 거부당한다

     서버를 고르는 것은 우리 몫이 아니고, 웹에 올렸을 때 어느 서버를 만날지도
     알 수 없다. 그래서 서버에 기대지 아니한다 — 모듈 부르기가 막히면 파일을
     글로 받아 Blob 으로 만들어 부른다. MIME 을 우리가 정하는 셈이다.

   ■ 두 군데서 쓴다

     ui/pdfview.js    별표 미리보기 (쪽마다 그린다)
     core/importer.js PDF 를 열어 글자를 뽑을 때
   ============================================================ */

const BASE = new URL("../../vendor/pdfjs/", import.meta.url);
const JS = /javascript|ecmascript/i;

let _mod = null;

/** 파일을 글로 받아 자바스크립트 Blob 주소로 만든다 */
async function blobUrl(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} — ${r.status}`);
  const t = await r.text();
  return URL.createObjectURL(new Blob([t], { type: "text/javascript" }));
}

/** 서버가 자바스크립트로 내주는가 */
async function servedAsJs(url) {
  try {
    const r = await fetch(url, { method: "HEAD" });
    return r.ok && JS.test(r.headers.get("content-type") || "");
  } catch {
    return false;
  }
}

/**
 * pdf.js 를 불러 온다 (한 번만 불러 두고 되쓴다).
 * @returns {Promise<object>} pdf.js 모듈
 */
export async function loadPdfjs() {
  if (_mod) return _mod;

  const main = new URL("pdf.min.mjs?v=20260907k", BASE).href;
  let mod;
  try {
    mod = await import(/* @vite-ignore */ main);
  } catch (e) {
    mod = await import(/* @vite-ignore */ await blobUrl(main));
  }

  // 일꾼(worker)도 같은 문제를 겪는다. 서버가 제대로 내주면 그대로 쓰고,
  // 아니면 Blob 으로 바꾸어 준다.
  const w = new URL("pdf.worker.min.mjs", BASE).href;
  mod.GlobalWorkerOptions.workerSrc =
    (await servedAsJs(w)) ? w : await blobUrl(w);

  _mod = mod;
  return mod;
}
