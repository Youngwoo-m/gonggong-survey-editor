/* ============================================================
   adapters/ai.js — Claude API 연결
   ------------------------------------------------------------
   · 서버 없이 브라우저에서 바로 부른다 (Anthropic 이 허용하는 방식)
   · API 키는 이 브라우저(localStorage)에만 있고 api.anthropic.com 말고는
     아무 데도 보내지 않는다. 저장소 토큰과 같은 취급이다.
   · 규정 원문은 국가법령정보센터 공개 자료다. 다만 아직 공개하지 않은
     개정안 초안이 함께 실려 나가므로 화면에서 미리 알린다.
   ============================================================ */

const API = "https://api.anthropic.com/v1/messages";
const K_KEY = "pm.ai.key";
const K_MODEL = "pm.ai.model";

export const MODELS = [
  { id: "claude-sonnet-5", name: "Sonnet 5 — 균형 (권장)" },
  { id: "claude-opus-5", name: "Opus 5 — 가장 꼼꼼함 (느리고 비쌈)" },
  { id: "claude-haiku-4-5-20251001", name: "Haiku 4.5 — 가장 빠름" },
];

export function hasKey() { return !!localStorage.getItem(K_KEY); }
export function setKey(v) {
  if (v) localStorage.setItem(K_KEY, v.trim());
  else localStorage.removeItem(K_KEY);
}
export function keyHint() {
  const k = localStorage.getItem(K_KEY) || "";
  return k ? `${k.slice(0, 12)}…${k.slice(-4)}` : "";
}
export function getModel() { return localStorage.getItem(K_MODEL) || MODELS[0].id; }
export function setModel(v) { localStorage.setItem(K_MODEL, v || MODELS[0].id); }

/**
 * @param {string} system 역할 지시
 * @param {string} user 물어볼 내용
 * @param {{maxTokens?:number, signal?:AbortSignal, model?:string}} opts
 * @returns {Promise<string>} 답변 글
 */
export async function ask(system, user, { maxTokens = 4000, signal, model } = {}) {
  const key = localStorage.getItem(K_KEY);
  if (!key) throw new Error("API 키가 없습니다. [✦AI] → [연결 설정] 에서 넣어 주세요.");

  let r;
  try {
    r = await fetch(API, {
      method: "POST",
      signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: model || getModel(),
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

/** 연결 확인 — 짧게 한 번 불러 본다 */
export async function verify(model) {
  const t = await ask("한 낱말로만 답하시오.", "확인", { maxTokens: 16, model });
  return t.slice(0, 40);
}
