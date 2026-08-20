/* ============================================================
   core/importer.js — 파일 → 텍스트 줄 목록
   ------------------------------------------------------------
   지원 : .txt .md  /  .hwp(HWPML XML)  /  .hwpx  /  .pdf  /  .json(자체 형식)
   미지원: 구형 이진 HWP(OLE2) — 안내 후 변환 요청
   ============================================================ */
import { readZip } from "./zipreader.js?v=20260820n";

const dec = (b, enc = "utf-8") => new TextDecoder(enc).decode(b);

function looksXml(bytes) {
  const head = dec(bytes.slice(0, 200)).trimStart();
  return head.startsWith("<?xml") || head.startsWith("<HWPML") || head.startsWith("<");
}
function isOle(bytes) {
  const sig = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
  return sig.every((v, i) => bytes[i] === v);
}
function isZip(bytes) {
  return bytes[0] === 0x50 && bytes[1] === 0x4B;
}

/* ---------- HWPML (.hwp, 국가법령정보센터 내려받기 형식) ---------- */
function fromHwpml(text) {
  const doc = new DOMParser().parseFromString(text, "text/xml");
  if (doc.querySelector("parsererror")) throw new Error("HWPML 구조를 읽지 못했습니다.");
  const paras = doc.getElementsByTagName("P");
  const lines = [];
  for (const p of paras) {
    let s = "";
    for (const c of p.getElementsByTagName("CHAR")) s += c.textContent;
    lines.push(s.replace(/ /g, " ").trim());
  }
  return lines;
}

/* ---------- HWPX ---------- */
const HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph";
async function fromHwpx(buf) {
  const files = await readZip(buf);
  const sections = [...files.keys()]
    .filter((n) => /Contents\/section\d+\.xml$/i.test(n))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  if (!sections.length) throw new Error("HWPX 안에서 본문(section)을 찾지 못했습니다.");

  const lines = [];
  for (const name of sections) {
    const xml = dec(files.get(name));
    const doc = new DOMParser().parseFromString(xml, "text/xml");
    let paras = doc.getElementsByTagNameNS(HP_NS, "p");
    if (!paras.length) paras = doc.getElementsByTagName("hp:p");
    if (!paras.length) paras = doc.getElementsByTagName("p");
    for (const p of paras) {
      let ts = p.getElementsByTagNameNS(HP_NS, "t");
      if (!ts.length) ts = p.getElementsByTagName("hp:t");
      if (!ts.length) ts = p.getElementsByTagName("t");
      let s = "";
      for (const t of ts) s += t.textContent;
      lines.push(s.replace(/ /g, " ").trim());
    }
  }
  return lines;
}

/* ---------- PDF (내장 pdf.js) ---------- */
let _pdfjs = null;
async function pdfjs() {
  if (_pdfjs) return _pdfjs;
  const mod = await import("../../vendor/pdfjs/pdf.min.mjs?v=20260820n");
  mod.GlobalWorkerOptions.workerSrc = new URL("../../vendor/pdfjs/pdf.worker.min.mjs", import.meta.url).href;
  _pdfjs = mod;
  return mod;
}

async function fromPdf(buf, onProgress) {
  const pdf = await pdfjs();
  const doc = await pdf.getDocument({ data: buf, isEvalSupported: false }).promise;
  const lines = [];
  for (let i = 1; i <= doc.numPages; i++) {
    onProgress?.(i, doc.numPages);
    const page = await doc.getPage(i);
    const tc = await page.getTextContent();
    // Y 좌표로 줄 묶기
    const rows = new Map();
    for (const it of tc.items) {
      if (!it.str) continue;
      const y = Math.round(it.transform[5]);
      const key = Math.round(y / 3) * 3;
      if (!rows.has(key)) rows.set(key, []);
      rows.get(key).push({ x: it.transform[4], s: it.str });
    }
    [...rows.entries()]
      .sort((a, b) => b[0] - a[0])
      .forEach(([, parts]) => {
        parts.sort((a, b) => a.x - b.x);
        lines.push(parts.map((p) => p.s).join("").replace(/ /g, " ").trim());
      });
    lines.push("");
    page.cleanup();
  }
  await doc.destroy();
  return lines;
}

/* ---------- 진입점 ---------- */
/**
 * @param {File} file
 * @param {(msg:string)=>void} onProgress
 * @returns {Promise<{lines:string[], kind:string, native?:object}>}
 */
export async function extractLines(file, onProgress) {
  const name = (file.name || "").toLowerCase();
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);

  if (name.endsWith(".json")) {
    const obj = JSON.parse(dec(bytes));
    if (obj && Array.isArray(obj.tree)) return { lines: [], kind: "json", native: obj };
    throw new Error("조문 트리(tree)가 들어 있는 JSON이 아닙니다.");
  }

  if (name.endsWith(".txt") || name.endsWith(".md")) {
    let text = dec(bytes);
    if (/�/.test(text.slice(0, 400))) text = dec(bytes, "euc-kr");   // 한글 인코딩 폴백
    return { lines: text.split(/\r?\n/), kind: "txt" };
  }

  if (name.endsWith(".pdf") || (bytes[0] === 0x25 && bytes[1] === 0x50)) {
    onProgress?.("PDF 텍스트 추출 준비…");
    const lines = await fromPdf(buf, (p, t) => onProgress?.(`PDF 텍스트 추출 ${p} / ${t}쪽`));
    return { lines, kind: "pdf" };
  }

  if (name.endsWith(".hwpx") || (isZip(bytes) && !name.endsWith(".zip"))) {
    onProgress?.("HWPX 압축 해제…");
    return { lines: await fromHwpx(buf), kind: "hwpx" };
  }

  if (name.endsWith(".hwp")) {
    if (isOle(bytes)) {
      throw new Error(
        "구형 이진 HWP 파일입니다. 한/글에서 '다른 이름으로 저장 → HWPX' 로 바꾼 뒤 다시 열어 주세요. " +
        "(국가법령정보센터에서 내려받은 HWP 는 XML 형식이라 바로 열립니다.)");
    }
    if (looksXml(bytes)) return { lines: fromHwpml(dec(bytes)), kind: "hwpml" };
    throw new Error("HWP 형식을 알아보지 못했습니다.");
  }

  if (isZip(bytes)) { onProgress?.("압축 해제…"); return { lines: await fromHwpx(buf), kind: "hwpx" }; }
  if (looksXml(bytes)) return { lines: fromHwpml(dec(bytes)), kind: "hwpml" };

  throw new Error("지원하지 않는 형식입니다. (TXT · HWP(XML) · HWPX · PDF · JSON)");
}
