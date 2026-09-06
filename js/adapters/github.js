/* ============================================================
   adapters/github.js — GitHub 저장소를 프로젝트 보관소로 사용
   ------------------------------------------------------------
   · 프로젝트(.pmproj)를 저장소에 커밋으로 저장한다 → 버전관리는 git 이 해준다
   · 여러 사람이 같은 저장소를 보면 목록·이력이 공유된다
   · 토큰은 이 브라우저(localStorage)에만 있고, GitHub 말고는 아무 데도 보내지 않는다
   ============================================================ */

const API = "https://api.github.com";
const K_TOKEN = "pm.gh.token";
const K_CFG = "pm.gh.cfg";
const K_AUTHOR = "pm.author";

/* ---------- 설정 ---------- */
/* 기본 공유 저장소 —— 이 편집기가 개정안 작업본(.pmproj)을 두는 자리.
   아무 설정도 하지 아니한 사람도 목록을 보고 남의 작업본을 열 수 있게
   기본값으로 둔다. 공개 저장소이므로 읽기는 토큰이 없어도 된다.
   저장(쓰기)에는 토큰이 있어야 한다. */
export const DEFAULT_CFG = {
  owner: "Youngwoo-m", repo: "gonggong-survey-editor",
  branch: "main", dir: "projects",
};

export function getConfig() {
  try {
    const c = JSON.parse(localStorage.getItem(K_CFG) || "{}");
    return { ...DEFAULT_CFG, ...c };
  } catch { return { ...DEFAULT_CFG }; }
}
export function setConfig(cfg) {
  localStorage.setItem(K_CFG, JSON.stringify({ ...getConfig(), ...cfg }));
}
export function getAuthor() { return localStorage.getItem(K_AUTHOR) || ""; }
export function setAuthor(v) { localStorage.setItem(K_AUTHOR, v || ""); }

/* ---------- 토큰 ---------- */
export function hasToken() { return !!localStorage.getItem(K_TOKEN); }
export function setToken(t) {
  if (t) localStorage.setItem(K_TOKEN, t.trim());
  else localStorage.removeItem(K_TOKEN);
}
export function clearToken() { localStorage.removeItem(K_TOKEN); }
/** 화면에 보여줄 용도 — 앞뒤 일부만 */
export function tokenHint() {
  const t = localStorage.getItem(K_TOKEN) || "";
  return t ? `${t.slice(0, 7)}…${t.slice(-4)}` : "";
}

/* ---------- 공통 ---------- */
const COMMON = {
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
};

/** 쓰기에 쓰는 머리 —— 토큰이 있어야 한다 */
function authHeaders(extra = {}) {
  const t = localStorage.getItem(K_TOKEN);
  if (!t) throw new Error("연결되지 않았습니다. [공유] 에서 저장소와 토큰을 설정하세요.");
  return { Authorization: `Bearer ${t}`, ...COMMON, ...extra };
}

/** 읽기에 쓰는 머리 —— 토큰이 있으면 쓰고, 없으면 그냥 읽는다.
    공개 저장소는 인증 없이 읽을 수 있다(다만 시간당 60번으로 묶인다). */
function readHeaders(extra = {}) {
  const t = localStorage.getItem(K_TOKEN);
  return t ? { Authorization: `Bearer ${t}`, ...COMMON, ...extra }
           : { ...COMMON, ...extra };
}

async function api(path, opts = {}) {
  const write = !!opts.method && opts.method !== "GET";
  const head = write ? authHeaders(opts.headers) : readHeaders(opts.headers);
  const r = await fetch(API + path, { ...opts, headers: head });
  if (r.status === 401) throw new Error("토큰이 유효하지 않습니다. 다시 연결해 주세요.");
  if (r.status === 403) {
    const rem = r.headers.get("x-ratelimit-remaining");
    const noTok = !localStorage.getItem(K_TOKEN);
    throw new Error(rem === "0"
      ? (noTok ? "GitHub 호출 한도를 넘었습니다. [공유 저장소] 에서 토큰을 넣으면 한도가 크게 늘어납니다."
               : "GitHub API 호출 한도를 넘었습니다. 잠시 후 다시 시도하세요.")
      : "권한이 없습니다. 토큰에 Contents 읽기·쓰기 권한이 있는지 확인하세요.");
  }
  if (r.status === 404) { const e = new Error("찾을 수 없습니다."); e.code = 404; throw e; }
  if (r.status === 409 || r.status === 422) {
    const e = new Error("다른 사람이 먼저 저장했습니다. 목록을 새로 고친 뒤 다시 저장하세요.");
    e.code = "conflict"; throw e;
  }
  if (!r.ok) throw new Error(`GitHub 오류 ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? null : r.json();
}

/* ---------- base64 (UTF-8 안전) ---------- */
function toBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  const CH = 0x8000;
  for (let i = 0; i < bytes.length; i += CH) bin += String.fromCharCode(...bytes.subarray(i, i + CH));
  return btoa(bin);
}
function fromBase64(b64) {
  const bin = atob(String(b64).replace(/\s/g, ""));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

const enc = (s) => encodeURIComponent(s).replace(/%2F/g, "/");
const base = () => { const c = getConfig(); return `/repos/${c.owner}/${c.repo}`; };
const dirOf = () => (getConfig().dir || "").replace(/^\/+|\/+$/g, "");
export const pathOf = (name) => (dirOf() ? `${dirOf()}/${name}` : name);

/* ---------- 연결 확인 ---------- */
export async function verify() {
  const c = getConfig();
  if (!c.owner || !c.repo) throw new Error("저장소(owner/repo)를 입력하세요.");
  const user = await api("/user");
  const repo = await api(base());
  return {
    login: user.login, name: user.name || user.login,
    repo: repo.full_name, private: repo.private,
    canWrite: !!(repo.permissions && (repo.permissions.push || repo.permissions.admin)),
    branch: c.branch || repo.default_branch,
  };
}

/* ---------- 프로젝트 목록 ---------- */
export async function listProjects() {
  const c = getConfig();
  const d = dirOf();
  let items;
  try {
    items = await api(`${base()}/contents/${enc(d)}?ref=${enc(c.branch)}`);
  } catch (e) {
    if (e.code === 404) return [];          // 폴더가 아직 없음
    throw e;
  }
  if (!Array.isArray(items)) return [];
  return items
    .filter((x) => x.type === "file" && /\.pmproj$/i.test(x.name))
    .map((x) => ({ name: x.name.replace(/\.pmproj$/i, ""), file: x.name, path: x.path, sha: x.sha, size: x.size }))
    .sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

/** 각 프로젝트의 최근 커밋 정보 (목록에 표시용) */
export async function lastCommits(paths) {
  const c = getConfig();
  const out = {};
  await Promise.all(paths.map(async (p) => {
    try {
      const cm = await api(`${base()}/commits?path=${enc(p)}&sha=${enc(c.branch)}&per_page=1`);
      if (cm && cm[0]) {
        out[p] = {
          at: cm[0].commit.author.date,
          by: cm[0].commit.author.name,
          message: cm[0].commit.message.split("\n")[0],
        };
      }
    } catch { /* 개별 실패는 무시 */ }
  }));
  return out;
}

/* ---------- 읽기 ---------- */
export async function readProject(path, ref = null) {
  const c = getConfig();
  const q = `?ref=${enc(ref || c.branch)}`;
  const meta = await api(`${base()}/contents/${enc(path)}${q}`);
  let text;
  if (meta.content) text = fromBase64(meta.content);
  else {
    // 1MB 초과 파일은 blob API 로
    const blob = await api(`${base()}/git/blobs/${meta.sha}`);
    text = fromBase64(blob.content);
  }
  return { data: JSON.parse(text), sha: meta.sha, size: meta.size, path };
}

/* ---------- 쓰기 (= 커밋) ---------- */
export async function writeProject(path, obj, { sha = null, message = null } = {}) {
  const c = getConfig();
  const body = {
    message: message || `프로젝트 저장: ${path.split("/").pop()}`,
    content: toBase64(JSON.stringify(obj, null, 1)),
    branch: c.branch,
  };
  if (sha) body.sha = sha;
  const author = getAuthor();
  if (author) body.committer = undefined;      // 커밋 작성자는 토큰 소유자로 둔다
  const r = await api(`${base()}/contents/${enc(path)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { sha: r.content.sha, commit: r.commit.sha, url: r.content.html_url };
}

export async function deleteProject(path, sha) {
  const c = getConfig();
  await api(`${base()}/contents/${enc(path)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: `프로젝트 삭제: ${path.split("/").pop()}`, sha, branch: c.branch }),
  });
  return true;
}

/* ---------- 저장 이력 (커밋) ---------- */
export async function history(path, limit = 30) {
  const c = getConfig();
  const cm = await api(`${base()}/commits?path=${enc(path)}&sha=${enc(c.branch)}&per_page=${limit}`);
  return (cm || []).map((x) => ({
    sha: x.sha,
    short: x.sha.slice(0, 7),
    at: x.commit.author.date,
    by: x.commit.author.name,
    login: x.author ? x.author.login : "",
    message: x.commit.message.split("\n")[0],
    url: x.html_url,
  }));
}

/** 특정 커밋 시점의 프로젝트 내용 */
export async function readAt(path, commitSha) {
  return readProject(path, commitSha);
}

/* ============================================================
   참조 규정 공유 — 파일에서 색인한 규정을 저장소에 올려 함께 쓴다
   저장 위치: <dir>/refs/<이름>.json
   ============================================================ */
const refDir = () => {
  const d = dirOf();
  return d ? `${d}/refs` : "refs";
};
export const refPathOf = (name) => `${refDir()}/${name}.json`;

export async function listRefs() {
  const c = getConfig();
  try {
    const items = await api(`${base()}/contents/${enc(refDir())}?ref=${enc(c.branch)}`);
    if (!Array.isArray(items)) return [];
    return items
      .filter((x) => x.type === "file" && /\.json$/i.test(x.name))
      .map((x) => ({ name: x.name.replace(/\.json$/i, ""), path: x.path, sha: x.sha, size: x.size }))
      .sort((a, b) => a.name.localeCompare(b.name, "ko"));
  } catch (e) {
    if (e.code === 404) return [];
    throw e;
  }
}

export async function readRef(path) {
  const r = await readProject(path);
  return r.data;
}

/** 색인한 참조 규정을 저장소에 올린다 (같은 이름이면 갱신) */
export async function writeRef(doc, { sha = null } = {}) {
  const safe = String(doc.name || "규정").replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
  const path = refPathOf(safe);
  let useSha = sha;
  if (!useSha) {
    try {
      const meta = await api(`${base()}/contents/${enc(path)}?ref=${enc(getConfig().branch)}`);
      useSha = meta.sha;
    } catch (e) { if (e.code !== 404) throw e; }
  }
  const author = getAuthor();
  const r = await writeProjectRaw(path, doc, {
    sha: useSha,
    message: `참조 규정 공유: ${safe}${author ? ` (${author})` : ""}`,
  });
  return { path, name: safe, sha: r.sha };
}

export async function deleteRef(path, sha) { return deleteProject(path, sha); }

/** writeProject 와 같지만 메시지를 그대로 쓴다 */
async function writeProjectRaw(path, obj, opts) { return writeProject(path, obj, opts); }

export function repoUrl() {
  const c = getConfig();
  return c.owner && c.repo ? `https://github.com/${c.owner}/${c.repo}` : "";
}
