/* ============================================================
   core/srcfp.js — 개정안 자료 파일의 지문

   왜 필요한가
     편집기는 브라우저에 담아 둔 작업본을 자료 파일보다 먼저 이어받는다
     (main.js 의 「지난번에 담아 둔 것이 있으면 이어서 작업한다」).
     그런데 이 편집기의 자료는 사람이 화면에서만 고치는 것이 아니다.
     scripts\ 의 연장들이 data\draft*.json 을 직접 고친다 —— 「지도등」
     일괄 정비, 조문 신설, 부칙 달기가 모두 그러하다.

     그러면 화면이 옛 작업본을 되살려, 스크립트로 고친 것이 보이지 아니한다.
     더 나쁜 것은 그 상태에서 무엇을 고쳐 내보내면 스크립트로 한 일이
     사라진 채 덮인다는 점이다.

     그래서 자료를 파일에서 읽을 때 그 지문을 함께 적어 두고, 다음에
     작업본을 이어받을 때 파일의 지문과 견준다. 다르면 사람에게 알린다.

   무엇을 보는가
     조문 나무의 뼈대만 본다 —— 마디의 갈래ㆍ번호ㆍ가지ㆍ상태ㆍ제목과
     본문ㆍ사유의 길이. 글자를 통째로 넣지 아니하는 까닭은 빠르기 때문이며,
     길이만으로도 스크립트가 손댄 것은 거의 다 드러난다.

     부칙과 next(다음 판)도 함께 본다.

   왜 sha 가 아닌가
     브라우저의 crypto.subtle 은 비동기이고 http 가 아닌 자리에서는 막힌다.
     여기서는 남을 속일 일이 없고 우연히 같아지지만 않으면 되므로,
     FNV-1a 32비트로 넉넉하다.
   ============================================================ */

/** FNV-1a 32비트 — 문자열 하나를 여덟 자리 십육진수로 */
function fnv1a(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

function walk(nodes, out) {
  for (const n of (nodes || [])) {
    out.push([
      n.level || "", n.no ?? "", n.branch ?? "", n.status || "",
      n.title || "", (n.body || "").length, (n.reason || "").length,
      n.origin || "",
    ].join(""));
    walk(n.children, out);
  }
}

function revFp(rev) {
  const out = [];
  walk(rev && rev.tree, out);
  out.push("부칙" + ((rev && rev.supplement) || "").length);
  return out;
}

/**
 * 개정안 자료 파일 하나의 지문.
 * @param {object|null} draft  data/draft*.json 을 읽은 것
 * @returns {string} 여덟 자리 십육진수. 자료가 없으면 "00000000".
 */
export function fingerprint(draft) {
  if (!draft || !Array.isArray(draft.tree)) return "00000000";
  const out = revFp(draft);
  for (const more of (Array.isArray(draft.next) ? draft.next : [])) {
    out.push("판");
    out.push(...revFp(more));
  }
  return fnv1a(out.join("\n"));
}

/**
 * 두 지문 꾸러미를 견주어 어긋난 대상 id 를 돌려준다.
 * 한쪽에만 있는 것은 견주지 아니한다 —— 등록부가 늘거나 줄었을 뿐,
 * 자료가 바뀐 것이 아닐 수 있다.
 */
export function drifted(mine, file) {
  const out = [];
  for (const id of Object.keys(file || {})) {
    if (!mine || !mine[id]) continue;
    if (mine[id] !== file[id]) out.push(id);
  }
  return out;
}
