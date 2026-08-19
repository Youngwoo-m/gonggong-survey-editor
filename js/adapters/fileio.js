/* ============================================================
   adapters/fileio.js — 파일 입출력 어댑터 (브라우저 구현)
   ------------------------------------------------------------
   데스크톱(Electron) 전환 시 이 파일만 fs 기반 구현으로 교체한다.
   상위 코드는 openProject / saveProject / loadJSON 만 사용한다.

   저장 경로
     1) 파일에 직접 덮어쓰기 (File System Access API)
     2) 실패하면 내려받기로 폴백  ← 어떤 환경에서도 성과물은 남는다
   ============================================================ */

const hasFSA = typeof window !== "undefined"
  && "showSaveFilePicker" in window
  && "showOpenFilePicker" in window;

let _handle = null;              // 저장 대상 파일 핸들
let _handleWritable = false;     // 그 핸들에 쓰기 권한이 확인되었는지
let _fsaBlocked = false;         // 이 환경에서 파일 덮어쓰기가 막혀 있는지 (한 번 확인하면 기억)

export const capabilities = {
  nativeFilePicker: hasFSA,
  canOverwriteInPlace: hasFSA,
};

const TYPES = [{
  description: "구조개편 프로젝트",
  accept: { "application/json": [".pmproj", ".json"] },
}];

const safeName = (s) => String(s || "개정안").replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);

/** 다른 창 안에 끼워진(iframe) 상태인지 — 이 경우 파일 덮어쓰기가 막힌다 */
export function inFrame() {
  try { return window.self !== window.top; } catch { return true; }
}

/** 핸들에 읽기·쓰기 권한이 있는지 확인하고, 없으면 요청한다 */
async function ensureWritable(handle) {
  if (!handle) return false;
  const opts = { mode: "readwrite" };
  try {
    if (typeof handle.queryPermission === "function") {
      if ((await handle.queryPermission(opts)) === "granted") return true;
    }
    if (typeof handle.requestPermission === "function") {
      if ((await handle.requestPermission(opts)) === "granted") return true;
      return false;
    }
    // 권한 API 가 없는 구현 — 실제 쓰기 시도로 판단
    return true;
  } catch {
    return false;
  }
}

function downloadFallback(text, name) {
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  return name;
}

/** 사용자가 대화상자를 닫은 경우인지 */
const isAbort = (e) => !!e && (e.name === "AbortError" || /aborted|취소/i.test(e.message || ""));

/**
 * @returns {{name:string, inPlace:boolean, warning?:string}}
 * @throws  AbortError — 사용자가 대화상자를 취소한 경우
 */
export async function saveProject(data, { forceDialog = false } = {}) {
  const text = JSON.stringify(data, null, 1);
  const fallbackName = safeName(data && data.name) + ".pmproj";

  // 지원하지 않거나, 이미 막혀 있다고 확인된 환경 → 곧바로 내려받기 (대화상자를 두 번 띄우지 않는다)
  if (!hasFSA || _fsaBlocked) {
    return {
      name: downloadFallback(text, fallbackName), inPlace: false,
      quiet: _fsaBlocked,
      warning: _fsaBlocked ? null
        : "이 브라우저는 파일 덮어쓰기를 지원하지 않아 내려받기로 저장했습니다. (Chrome 또는 Edge 권장)",
    };
  }

  let reason = "";
  try {
    if (forceDialog || !_handle) {
      _handle = await window.showSaveFilePicker({ suggestedName: fallbackName, types: TYPES });
      // 저장 대화상자로 고른 핸들은 이미 쓰기 권한이 있다 — 다시 묻지 않는다
      _handleWritable = true;
    }

    if (!_handleWritable) {
      const ok = await ensureWritable(_handle);
      if (!ok) { reason = "파일 쓰기 권한이 허용되지 않았습니다."; throw new Error(reason); }
      _handleWritable = true;
    }

    const w = await _handle.createWritable();
    await w.write(new Blob([text], { type: "application/json" }));
    await w.close();
    return { name: _handle.name, inPlace: true };

  } catch (err) {
    if (isAbort(err)) throw err;                      // 사용자가 직접 취소 — 조용히 종료

    // 덮어쓰기 실패 → 내려받기로 저장하고, 이 환경에서는 더 이상 시도하지 않는다
    _handle = null;
    _handleWritable = false;
    _fsaBlocked = true;
    const detail = reason || (err && err.message) || "알 수 없는 오류";
    let hint;
    if (inFrame()) {
      hint = "이 화면은 다른 창 안에 끼워진(iframe) 상태라 파일 덮어쓰기가 막힙니다. " +
             "실행.bat 으로 연 브라우저 탭에서 직접 사용하세요.";
    } else if (/permission|allowed|granted|권한/i.test(detail)) {
      hint = "파일 쓰기 권한을 허용하지 않았거나, 브라우저가 쓰기를 막는 위치(시스템 폴더 등)입니다. " +
             "[다른 이름으로]로 문서·바탕화면 등 일반 폴더를 지정해 보세요.";
    } else {
      hint = "[다른 이름으로]로 저장 위치를 다시 지정해 보세요.";
    }
    return {
      name: downloadFallback(text, fallbackName),
      inPlace: false,
      warning: `${hint}\n앞으로 이 창에서는 저장을 누르면 바로 내려받습니다.\n(원인: ${detail})`,
    };
  }
}

export async function openProject() {
  if (hasFSA) {
    const [h] = await window.showOpenFilePicker({ types: TYPES, multiple: false });
    const f = await h.getFile();
    const data = JSON.parse(await f.text());
    // 열기로 얻은 핸들은 읽기 전용일 수 있다 — 저장 시점에 권한을 확인한다
    _handle = h;
    _handleWritable = false;
    return { name: h.name, data };
  }
  return new Promise((resolve, reject) => {
    const input = document.getElementById("filePicker");
    input.value = "";
    input.onchange = async () => {
      const f = input.files && input.files[0];
      if (!f) return reject(new Error("취소"));
      try { resolve({ name: f.name, data: JSON.parse(await f.text()) }); }
      catch (e) { reject(e); }
    };
    input.click();
  });
}

export function resetTarget() { _handle = null; _handleWritable = false; }
export function currentTargetName() { return _handle ? _handle.name : null; }

/** 데이터 파일(JSON) 읽기 */
export async function loadJSON(path) {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${path} 를 읽지 못했습니다 (${r.status})`);
  return r.json();
}
