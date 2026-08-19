/* ============================================================
   core/zipreader.js — 최소 ZIP 판독기
   ------------------------------------------------------------
   HWPX(한글 XML 문서) 같은 ZIP 컨테이너를 외부 라이브러리 없이 읽는다.
   압축 해제는 브라우저 내장 DecompressionStream('deflate-raw') 사용.
   ============================================================ */

const dv = (buf) => new DataView(buf);

function findEOCD(buf) {
  const v = dv(buf);
  const max = Math.min(buf.byteLength, 65557 + 22);
  for (let i = buf.byteLength - 22; i >= buf.byteLength - max && i >= 0; i--) {
    if (v.getUint32(i, true) === 0x06054b50) return i;
  }
  return -1;
}

async function inflateRaw(bytes) {
  if (typeof DecompressionStream !== "function") {
    throw new Error("이 브라우저는 압축 해제를 지원하지 않습니다 (Chrome·Edge 권장).");
  }
  const ds = new DecompressionStream("deflate-raw");
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/**
 * @param {ArrayBuffer} buf
 * @returns {Promise<Map<string, Uint8Array>>} 파일명 → 내용
 */
export async function readZip(buf) {
  const eocd = findEOCD(buf);
  if (eocd < 0) throw new Error("ZIP 형식이 아닙니다.");
  const v = dv(buf);
  const count = v.getUint16(eocd + 10, true);
  let p = v.getUint32(eocd + 16, true);

  const entries = [];
  for (let i = 0; i < count; i++) {
    if (v.getUint32(p, true) !== 0x02014b50) break;
    const method = v.getUint16(p + 10, true);
    const csize = v.getUint32(p + 20, true);
    const nameLen = v.getUint16(p + 28, true);
    const extraLen = v.getUint16(p + 30, true);
    const cmtLen = v.getUint16(p + 32, true);
    const offset = v.getUint32(p + 42, true);
    const name = new TextDecoder("utf-8").decode(new Uint8Array(buf, p + 46, nameLen));
    entries.push({ name, method, csize, offset });
    p += 46 + nameLen + extraLen + cmtLen;
  }

  const out = new Map();
  for (const e of entries) {
    if (e.name.endsWith("/")) continue;
    const lh = e.offset;
    if (v.getUint32(lh, true) !== 0x04034b50) continue;
    const nLen = v.getUint16(lh + 26, true);
    const xLen = v.getUint16(lh + 28, true);
    const start = lh + 30 + nLen + xLen;
    const raw = new Uint8Array(buf, start, e.csize);
    try {
      out.set(e.name, e.method === 0 ? raw : await inflateRaw(raw));
    } catch {
      /* 개별 엔트리 실패는 건너뛴다 */
    }
  }
  return out;
}
