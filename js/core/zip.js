/* ============================================================
   core/zip.js — 최소 ZIP 작성기 (무압축 STORE)
   외부 라이브러리 없이 .xlsx / .hwpx 컨테이너를 만들기 위한 것.
   ============================================================ */

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

const enc = new TextEncoder();

class Writer {
  constructor() { this.parts = []; this.len = 0; }
  bytes(b) { this.parts.push(b); this.len += b.length; }
  u16(v) { this.bytes(new Uint8Array([v & 0xFF, (v >>> 8) & 0xFF])); }
  u32(v) { this.bytes(new Uint8Array([v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF])); }
  blob(type) { return new Blob(this.parts, { type }); }
}

function dosTime(d) {
  return ((d.getHours() << 11) | (d.getMinutes() << 5) | (Math.floor(d.getSeconds() / 2))) & 0xFFFF;
}
function dosDate(d) {
  return (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF;
}

/**
 * @param {Array<{name:string, data:string|Uint8Array}>} files
 * @param {string} mime
 * @returns {Blob}
 */
export function createZip(files, mime = "application/zip") {
  const now = new Date();
  const time = dosTime(now), date = dosDate(now);
  const w = new Writer();
  const central = [];

  for (const f of files) {
    const nameBytes = enc.encode(f.name);
    const data = typeof f.data === "string" ? enc.encode(f.data) : f.data;
    const crc = crc32(data);
    const offset = w.len;

    w.u32(0x04034b50);          // local file header
    w.u16(20); w.u16(0x0800);   // version, flag(UTF-8)
    w.u16(0);                   // method = store
    w.u16(time); w.u16(date);
    w.u32(crc); w.u32(data.length); w.u32(data.length);
    w.u16(nameBytes.length); w.u16(0);
    w.bytes(nameBytes);
    w.bytes(data);

    central.push({ nameBytes, crc, size: data.length, offset });
  }

  const cdStart = w.len;
  for (const c of central) {
    w.u32(0x02014b50);
    w.u16(20); w.u16(20); w.u16(0x0800);
    w.u16(0);
    w.u16(time); w.u16(date);
    w.u32(c.crc); w.u32(c.size); w.u32(c.size);
    w.u16(c.nameBytes.length); w.u16(0); w.u16(0);
    w.u16(0); w.u16(0); w.u32(0);
    w.u32(c.offset);
    w.bytes(c.nameBytes);
  }
  const cdSize = w.len - cdStart;

  w.u32(0x06054b50);
  w.u16(0); w.u16(0);
  w.u16(central.length); w.u16(central.length);
  w.u32(cdSize); w.u32(cdStart);
  w.u16(0);

  return w.blob(mime);
}
