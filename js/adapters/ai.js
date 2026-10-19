/* ============================================================
   adapters/ai.js — Claude 연결 (Claude Code CLI)
   ------------------------------------------------------------
   · API 키를 쓰지 아니한다. 로컬 서버(serve.py)가 이 컴퓨터의 `claude`
     명령(Claude Code CLI)을 불러 묻고, 답만 화면에 돌려준다.
     쓰는 계정은 CLI 에 로그인한 계정이다 (claude auth login).
   · 그래서 실행.bat(serve.py)으로 띄웠을 때만 쓸 수 있다. 다른 정적 서버나
     웹에 올린 화면에서는 [연결 안 됨] 으로 보인다.
   · 규정 원문은 국가법령정보센터 공개 자료다. 다만 아직 공개하지 않은
     개정안 초안이 함께 실려 나가므로 화면에서 미리 알린다.
   ============================================================ */

const API = "api/claude";
const K_MODEL = "pm.ai.model";

// CLI 의 모델 별칭 —— 늘 그 갈래의 최신 모델을 가리킨다
export const MODELS = [
  { id: "sonnet", name: "Sonnet — 균형 (권장)" },
  { id: "opus", name: "Opus — 가장 꼼꼼함 (느림)" },
  { id: "haiku", name: "Haiku — 가장 빠름" },
];

let status = null;          // {ok, email, method, error} —— refresh() 가 채운다

/** CLI 연결 상태를 서버에 물어 새로 읽는다 */
export async function refresh() {
  try {
    const r = await fetch(API, { headers: { accept: "application/json" } });
    if (!r.ok) throw new Error(String(r.status));
    status = await r.json();
  } catch {
    status = { ok: false, error: "AI 도우미는 실행.bat(serve.py)으로 띄운 화면에서만 쓸 수 있습니다." };
  }
  return status;
}

/** 쓸 수 있는가 —— 아직 읽지 아니했으면 false */
export function ready() { return !!(status && status.ok); }
/** 아직 상태를 읽지 아니했는가 */
export function unknown() { return status === null; }
/** 연결 표시 글 */
export function statusHint() {
  if (!status) return "확인 중…";
  if (status.ok) return `Claude Code CLI${status.email ? " · " + status.email : ""}`;
  return status.error || "연결 안 됨";
}

export function getModel() {
  const m = localStorage.getItem(K_MODEL);
  return MODELS.some((x) => x.id === m) ? m : MODELS[0].id;
}
export function setModel(v) { localStorage.setItem(K_MODEL, v || MODELS[0].id); }

/**
 * @param {string} system 역할 지시
 * @param {string} user 물어볼 내용
 * @param {{maxTokens?:number, signal?:AbortSignal, model?:string}} opts
 *        maxTokens 는 CLI 가 받지 아니하므로 쓰지 아니한다.
 * @returns {Promise<string>} 답변 글
 */
export async function ask(system, user, { signal, model } = {}) {
  let r;
  try {
    r = await fetch(API, {
      method: "POST",
      signal,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ system, user, model: model || getModel() }),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("로컬 서버에 닿지 못했습니다. 실행.bat 으로 띄웠는지 확인해 주세요.");
  }
  let j = {};
  try { j = await r.json(); } catch { /* 아래에서 알림 */ }
  if (!r.ok) {
    if (r.status === 404 || r.status === 501) {
      throw new Error("이 화면은 AI 를 부를 수 없는 서버로 떠 있습니다. 실행.bat 으로 띄워 주세요.");
    }
    if (/로그인/.test(j.error || "")) status = { ok: false, error: j.error };
    throw new Error(j.error || `Claude 오류 ${r.status}`);
  }
  return String(j.text || "").trim();
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

/** 연결 확인 — 짧게 한 번 불러 본다 */
export async function verify(model) {
  const t = await ask("한 낱말로만 답하시오.", "확인", { model });
  await refresh();
  return t.slice(0, 40);
}
