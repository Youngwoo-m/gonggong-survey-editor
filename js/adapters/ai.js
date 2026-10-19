/* ============================================================
   adapters/ai.js — Claude 연결 (Claude Code CLI ㆍ API 키 ㆍ 자동)
   ------------------------------------------------------------
   연결 방식 셋 —— [연결 설정] 에서 고른다.

     cli   이 컴퓨터의 `claude` 명령(Claude Code CLI)으로 부른다. 로컬 서버
           (serve.py)가 대신 불러 주므로 실행.bat 으로 띄운 화면에서만 된다.
           구독 사용량을 쓰고, 호출마다 돈이 나가지 아니한다. (기본)
     api   Anthropic API 키로 브라우저에서 바로 부른다. 웹에 올린 화면에서도
           되고, 쓴 만큼 돈이 나간다. 키는 이 브라우저(localStorage)에만 있다.
     auto  평소에는 CLI, 두 경우에만 API 키로 간다.
             ㆍ 보낼 글이 기준 글자 수(BIG_CHARS_DEFAULT)를 넘을 때 —— 큰 글은
               CLI 가 1시간 캐시 쓰기 값을 붙여 API 보다 비싸고, 구독 한도를
               한꺼번에 많이 쓰기 때문이다.
             ㆍ CLI 가 막혔을 때(로그인 만료 ㆍ claude 없음 ㆍ 서버 아님).
           API 키가 없으면 auto 는 cli 와 같다.

   · API 키는 api.anthropic.com 말고는 아무 데도 보내지 않는다.
   · 규정 원문은 국가법령정보센터 공개 자료다. 다만 아직 공개하지 않은
     개정안 초안이 함께 실려 나가므로 화면에서 미리 알린다.
   ============================================================ */

const CLI_URL = "api/claude";
const API_URL = "https://api.anthropic.com/v1/messages";
const K_KEY = "pm.ai.key";
const K_MODEL = "pm.ai.model";
const K_MODE = "pm.ai.mode";
const K_EFFORT = "pm.ai.effort";
const K_BIG = "pm.ai.big";

export const BIG_CHARS_DEFAULT = 12000;       // 앱이 한 번에 보내는 가장 큰 글은 약 24,000자

// id 는 CLI 별칭이다. API 로 갈 때는 apiId 를 쓴다.
export const MODELS = [
  { id: "sonnet", apiId: "claude-sonnet-5-5", name: "Sonnet — 균형 (권장)" },
  { id: "opus", apiId: "claude-opus-5-5", name: "Opus — 가장 꼼꼼함 (느리고 비쌈)" },
  { id: "haiku", apiId: "claude-haiku-5-5", name: "Haiku — 가장 빠르고 쌈" },
];

export const MODES = [
  { id: "cli", name: "Claude Code CLI — 구독 사용 (기본)" },
  { id: "auto", name: "자동 — 평소 CLI, 큰 글만 API 키" },
  { id: "api", name: "API 키 — 쓴 만큼 요금" },
];

export const EFFORTS = [
  { id: "low", name: "낮음 — 빠르고 쌈 (기본)" },
  { id: "medium", name: "보통" },
  { id: "high", name: "높음 — 느리고 비쌈" },
];

/* ---------- 설정 ---------- */
const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { v == null || v === "" ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* 저장소가 막힌 곳 */ } };

export function hasKey() { return !!read(K_KEY); }
export function setKey(v) { write(K_KEY, (v || "").trim()); }
export function keyHint() {
  const k = read(K_KEY) || "";
  return k ? `${k.slice(0, 12)}…${k.slice(-4)}` : "";
}
export function getModel() {
  const m = read(K_MODEL);
  return MODELS.some((x) => x.id === m) ? m : MODELS[0].id;
}
export function setModel(v) { write(K_MODEL, v || MODELS[0].id); }
export function getMode() {
  const m = read(K_MODE);
  return MODES.some((x) => x.id === m) ? m : "cli";
}
export function setMode(v) { write(K_MODE, v); }
export function getEffort() {
  const e = read(K_EFFORT);
  return EFFORTS.some((x) => x.id === e) ? e : "low";
}
export function setEffort(v) { write(K_EFFORT, v); }
export function getBigChars() {
  const n = parseInt(read(K_BIG), 10);
  return n >= 1000 && n <= 200000 ? n : BIG_CHARS_DEFAULT;
}
export function setBigChars(v) {
  const n = parseInt(v, 10);
  write(K_BIG, n >= 1000 && n <= 200000 && n !== BIG_CHARS_DEFAULT ? String(n) : "");
}

/* ---------- CLI 상태 ---------- */
let status = null;          // {ok, email, method, error} —— refresh() 가 채운다

/** CLI 연결 상태를 서버에 물어 새로 읽는다 */
export async function refresh() {
  try {
    const r = await fetch(CLI_URL, { headers: { accept: "application/json" } });
    if (!r.ok) throw new Error(String(r.status));
    status = await r.json();
  } catch {
    status = { ok: false, error: "CLI 는 실행.bat(serve.py)으로 띄운 화면에서만 쓸 수 있습니다." };
  }
  return status;
}
export function cliReady() { return !!(status && status.ok); }
/** 아직 CLI 상태를 읽지 아니했는가 */
export function unknown() { return status === null; }

/** 지금 설정으로 쓸 수 있는가 */
export function ready() {
  const m = getMode();
  if (m === "api") return hasKey();
  if (m === "auto") return cliReady() || hasKey();
  return cliReady();
}

/** 연결 표시 글 */
export function statusHint() {
  const cli = !status ? "확인 중…" : status.ok
    ? `Claude Code CLI${status.email ? " · " + status.email : ""}`
    : (status.error || "CLI 연결 안 됨");
  const api = hasKey() ? `API 키 ${keyHint()}` : "API 키 없음";
  const m = getMode();
  if (m === "api") return api;
  if (m === "auto") return `자동 — ${cli} / ${api}`;
  return cli;
}

/* ---------- 길 고르기 ---------- */
/**
 * 이번 호출을 어느 길로 보낼지 —— 화면이 미리 보여 줄 수도 있다.
 * @returns {"cli"|"api"}
 */
export function pickRoute(system, user) {
  const m = getMode();
  if (m === "api") return "api";
  if (m === "cli") return "cli";
  if (!hasKey()) return "cli";                                   // auto 인데 키가 없으면 cli
  const size = String(system || "").length + String(user || "").length;
  if (size >= getBigChars()) return "api";
  if (status && !status.ok) return "api";                        // CLI 가 막혔을 때
  return "cli";
}

let last = null;
/** 가장 최근 호출의 길 —— {route, model, chars, fallback} */
export function lastCall() { return last; }

/**
 * @param {string} system 역할 지시
 * @param {string} user 물어볼 내용
 * @param {{maxTokens?:number, signal?:AbortSignal, model?:string, route?:"cli"|"api"}} opts
 *        maxTokens 는 API 길에서만 쓴다 (CLI 는 받지 아니한다).
 * @returns {Promise<string>} 답변 글
 */
export async function ask(system, user, { maxTokens = 4000, signal, model, route } = {}) {
  const m = model || getModel();
  let way = route || pickRoute(system, user);
  const chars = String(system || "").length + String(user || "").length;
  let fallback = false;

  if (way === "cli") {
    try {
      const text = await askCli(system, user, { signal, model: m });
      last = { route: "cli", model: m, chars, fallback };
      return text;
    } catch (e) {
      // 자동일 때만, 막힌 CLI 대신 API 키로 한 번 더 간다. 사람이 끊은 것은 아니다.
      if (e.name === "AbortError" || getMode() !== "auto" || !hasKey() || route) throw e;
      way = "api";
      fallback = true;
    }
  }
  const text = await askApi(system, user, { maxTokens, signal, model: m });
  last = { route: "api", model: m, chars, fallback };
  return text;
}

async function askCli(system, user, { signal, model }) {
  let r;
  try {
    r = await fetch(CLI_URL, {
      method: "POST",
      signal,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ system, user, model, effort: getEffort() }),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    status = { ok: false, error: "로컬 서버에 닿지 못했습니다. 실행.bat 으로 띄웠는지 확인해 주세요." };
    throw new Error(status.error);
  }
  let j = {};
  try { j = await r.json(); } catch { /* 아래에서 알림 */ }
  if (!r.ok) {
    if (r.status === 404 || r.status === 501) {
      status = { ok: false, error: "이 화면은 CLI 를 부를 수 없는 서버로 떠 있습니다. 실행.bat 으로 띄워 주세요." };
      throw new Error(status.error);
    }
    if (/로그인|찾지 못/.test(j.error || "")) status = { ok: false, error: j.error };
    throw new Error(j.error || `Claude 오류 ${r.status}`);
  }
  return String(j.text || "").trim();
}

async function askApi(system, user, { maxTokens, signal, model }) {
  const key = read(K_KEY);
  if (!key) throw new Error("API 키가 없습니다. [연결 설정] 에서 넣어 주세요.");
  const apiId = (MODELS.find((x) => x.id === model) || MODELS[0]).apiId;

  let r;
  try {
    r = await fetch(API_URL, {
      method: "POST",
      signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: apiId,
        max_tokens: maxTokens,
        system,
        messages: [{ role: "user", content: user }],
      }),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Claude 에 닿지 못했습니다. 인터넷 연결이나 방화벽을 확인해 주세요.");
  }

  if (r.status === 401) throw new Error("API 키가 올바르지 않습니다. 다시 넣어 주세요.");
  if (r.status === 429) throw new Error("요청이 몰렸습니다. 잠시 뒤 다시 시도해 주세요.");
  if (r.status === 400) {
    const t = await r.text();
    throw new Error(`요청이 거부되었습니다: ${t.slice(0, 200)}`);
  }
  if (!r.ok) throw new Error(`Claude 오류 ${r.status}: ${(await r.text()).slice(0, 200)}`);

  const j = await r.json();
  return (j.content || []).filter((c) => c.type === "text").map((c) => c.text).join("").trim();
}

/** 답변에서 JSON 만 끄집어낸다 (```json 울타리·앞뒤 설명 제거) */
export function pickJson(text) {
  const t = String(text || "").trim();
  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fence ? fence[1] : t;
  const i = body.search(/[[{]/);
  if (i < 0) throw new Error("답변에서 결과를 읽지 못했습니다.");
  const open = body[i];
  const close = open === "[" ? "]" : "}";
  let depth = 0, inStr = false, esc = false;
  for (let k = i; k < body.length; k++) {
    const c = body[k];
    if (inStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') inStr = true;
    else if (c === open) depth += 1;
    else if (c === close) {
      depth -= 1;
      if (depth === 0) return JSON.parse(body.slice(i, k + 1));
    }
  }
  throw new Error("답변의 JSON 이 끝나지 않았습니다.");
}

/**
 * 연결 확인 —— 짧게 한 번 불러 본다. 길을 정해 주면 그 길만 본다.
 * 자동일 때 설정 창이 CLI 와 API 를 따로 확인하려는 것이다.
 */
export async function verify(model, route) {
  if (route === "cli") await refresh();
  const t = await ask("한 낱말로만 답하시오.", "확인", { maxTokens: 16, model, route: route || undefined });
  if (route !== "api") await refresh();
  return t.slice(0, 40);
}
