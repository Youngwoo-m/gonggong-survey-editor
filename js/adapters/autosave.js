/* ============================================================
   adapters/autosave.js — 편집 내용을 이 브라우저에 자동으로 담아 둔다

   웹에서 도는 편집기이므로 '저장' 을 사람이 눌러야 남는 것은 어색하다.
   고칠 때마다 조용히 담고, 다음에 열면 이어서 작업한다.

   왜 IndexedDB 인가
     프로젝트 한 벌이 참조 규정까지 안으면 몇 MB 가 된다. localStorage 는
     5MB 안팎에서 막히므로 담다가 터진다. IndexedDB 는 그런 제약이 없다.

   담기는 곳은 이 브라우저뿐이다. 남에게 넘기거나 오래 갈무리하려면
   [내보내기] 로 .pmproj 파일을 만들거나 공유 저장소에 올린다.
   ============================================================ */

const DB = "pmproj";
const STORE = "auto";

/* 담아 두는 자리는 편집기마다 따로 둔다.
   작업규정ㆍ성과심사ㆍ무인비행장치가 한 브라우저에서 같은 자리를 쓰면
   마지막에 고친 것이 다른 편집기에서 되살아난다. */
const LEGACY = "project";
let KEY = LEGACY;

/** 편집기별 자리 — main.js 가 프로파일 id 로 정해 준다 */
export function setScope(id) {
  KEY = id ? `project:${id}` : LEGACY;
}

/**
 * 편집기 세 벌이 저마다 담아 두었던 것을 모아 온다 — 합치기 1단계의 옮겨 담기.
 *
 * 편집기가 셋일 때에는 project:work · project:review · project:uav 로 자리를
 * 나눠 담았다. 한 벌로 합치면서 그 셋을 한 자리(project:all)로 옮겨야 한다.
 * 원본은 지우지 않는다 — 옮겨 담기가 잘못되어도 되돌릴 수 있게 남겨 둔다.
 *
 * @param {string[]} ids 등록부의 대상 id 들
 * @returns {Promise<Array<{id, at, data}>>} 담긴 것이 있던 대상만
 */
export async function loadSplit(ids) {
  const out = [];
  for (const id of ids || []) {
    try {
      const got = await run("readonly", (s) => s.get(`project:${id}`));
      if (got && got.data && got.data.format === "pmproj") {
        out.push({ id, at: got.at, data: got.data });
      }
    } catch { /* 없으면 넘어간다 */ }
  }
  return out;
}

/** 자리를 나누기 전에 담아 둔 것 (편집기 구분이 없다) */
export async function loadLegacy() {
  try {
    return (await run("readonly", (s) => s.get(LEGACY))) || null;
  } catch {
    return null;
  }
}

export async function clearLegacy() {
  try {
    await run("readwrite", (s) => s.delete(LEGACY));
    return true;
  } catch {
    return false;
  }
}

let _db = null;

function open() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => {
      if (!r.result.objectStoreNames.contains(STORE)) r.result.createObjectStore(STORE);
    };
    r.onsuccess = () => { _db = r.result; resolve(_db); };
    r.onerror = () => reject(r.error);
  });
}

function run(mode, fn) {
  return open().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }));
}

/** 담아 둔 것이 있는가 — {data, at, name} 또는 null */
export async function load() {
  try {
    return (await run("readonly", (s) => s.get(KEY))) || null;
  } catch {
    return null;                      // 브라우저가 막아 두었으면 조용히 넘어간다
  }
}

/** 지금 상태를 담는다 */
export async function save(data) {
  try {
    await run("readwrite", (s) => s.put(
      { data, at: new Date().toISOString(), name: data && data.name }, KEY));
    return true;
  } catch {
    return false;
  }
}

export async function clear() {
  try {
    await run("readwrite", (s) => s.delete(KEY));
    return true;
  } catch {
    return false;
  }
}

/**
 * 고칠 때마다 부르되 잦은 호출은 묶는다.
 * @param {() => object} payload  담을 것을 그때 만들어 주는 함수
 * @param {number} wait  마지막 고침 뒤 기다리는 밀리초
 */
export function debounced(payload, wait = 1200) {
  let t = null, busy = false, again = false;
  const go = async () => {
    if (busy) { again = true; return; }
    busy = true;
    try { await save(payload()); } finally {
      busy = false;
      if (again) { again = false; go(); }
    }
  };
  return () => { clearTimeout(t); t = setTimeout(go, wait); };
}
