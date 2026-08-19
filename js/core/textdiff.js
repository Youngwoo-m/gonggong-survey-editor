/* ============================================================
   core/textdiff.js — 어절 단위 비교 (개정 대비표의 밑줄 표시용)
   반환: [{ t: "=" | "-" | "+", s: "문자열" }, ...]
   ============================================================ */

const MAX_TOKENS = 1200;   // 초장문 조문에서 DP 폭주 방지

function tokenize(s) {
  return (s || "").match(/\S+\s*|\s+/g) || [];
}

export function wordDiff(a, b) {
  const A = tokenize(a), B = tokenize(b);
  if (A.length > MAX_TOKENS || B.length > MAX_TOKENS) {
    // 너무 길면 통째로 교체된 것으로 처리
    const out = [];
    if (a) out.push({ t: "-", s: a });
    if (b) out.push({ t: "+", s: b });
    return out;
  }

  // 공통 앞/뒤 잘라내기
  let head = 0;
  while (head < A.length && head < B.length && A[head] === B[head]) head++;
  let tail = 0;
  while (tail < A.length - head && tail < B.length - head &&
         A[A.length - 1 - tail] === B[B.length - 1 - tail]) tail++;

  const a2 = A.slice(head, A.length - tail);
  const b2 = B.slice(head, B.length - tail);

  // LCS
  const n = a2.length, m = b2.length;
  const dp = new Uint32Array((n + 1) * (m + 1));
  const at = (i, j) => dp[i * (m + 1) + j];
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i * (m + 1) + j] = a2[i] === b2[j]
        ? at(i + 1, j + 1) + 1
        : Math.max(at(i + 1, j), at(i, j + 1));
    }
  }

  const mid = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a2[i] === b2[j]) { mid.push({ t: "=", s: a2[i] }); i++; j++; }
    else if (at(i + 1, j) >= at(i, j + 1)) { mid.push({ t: "-", s: a2[i] }); i++; }
    else { mid.push({ t: "+", s: b2[j] }); j++; }
  }
  while (i < n) mid.push({ t: "-", s: a2[i++] });
  while (j < m) mid.push({ t: "+", s: b2[j++] });

  const runs = [];
  if (head) runs.push({ t: "=", s: A.slice(0, head).join("") });
  runs.push(...mid);
  if (tail) runs.push({ t: "=", s: A.slice(A.length - tail).join("") });

  // 인접 동일 태그 병합
  const merged = [];
  for (const r of runs) {
    if (!r.s) continue;
    const last = merged[merged.length - 1];
    if (last && last.t === r.t) last.s += r.s;
    else merged.push({ t: r.t, s: r.s });
  }
  return merged;
}

/** 개정안 칸에 넣을 런 (삭제분 제외, 추가분만 강조) */
export function afterRuns(runs) {
  return runs.filter((r) => r.t !== "-").map((r) => ({ mark: r.t === "+", s: r.s }));
}
/** 현행 칸에 넣을 런 (추가분 제외, 삭제분만 강조) */
export function beforeRuns(runs) {
  return runs.filter((r) => r.t !== "+").map((r) => ({ mark: r.t === "-", s: r.s }));
}

export function hasChange(runs) {
  return runs.some((r) => r.t !== "=");
}
