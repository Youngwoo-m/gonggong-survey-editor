/* ============================================================
   ui/ask.js — 화면 안에서 묻는 창 (prompt ㆍ confirm 을 갈음한다)
   ------------------------------------------------------------
   브라우저는 한 화면에서 대화상자를 되풀이 띄우면 「이 페이지가 더 이상
   대화상자를 표시하지 않도록」 을 내걸고, 그 뒤로 prompt() 는 묻지도 않고
   null 을, confirm() 은 늘 거짓을 돌려준다. 그러면 단추를 눌러도 아무 일이
   없는 것처럼 보인다 —— 버전 [⑂새버전] 과 [삭제] 가 그러하였다.
   ============================================================ */
import { esc } from "./html.js?v=20260907w";
/* 화면 안에서 묻는 작은 칸.

   prompt() 은 브라우저가 막을 수 있다 —— 한 화면에서 대화상자를 되풀이해
   띄우면 「이 페이지가 더 이상 대화상자를 표시하지 않도록」 이 뜨고, 그 뒤로
   prompt() 은 묻지도 않고 null 을 돌려준다. 그러면 단추를 눌러도 아무 일이
   없는 것처럼 보인다. 그래서 화면 안에 칸을 띄운다.

   @param {string} title 무엇을 하는 자리인가
   @param {Array<{key,label,value,hint}>} fields 물을 칸들
   @returns {Promise<object|null>} 취소하면 null */
/* 화면 안에서 묻는 확인창 —— confirm() 을 갈음한다.
   confirm() 도 prompt() 와 같이 브라우저가 막을 수 있고, 막히면 늘
   「취소」를 돌려주므로 단추가 죽은 것처럼 보인다.
   @param {string} title 무엇을 하는가
   @param {Array<string>} lines 알려 줄 줄들
   @param {string} okText 확인 단추에 적을 말
   @returns {Promise<boolean>} */
export function askYesNo(title, lines, okText = "계속") {
  return new Promise((done) => {
    const back = document.createElement("div");
    back.className = "overlay ask-back";
    back.innerHTML = `
      <div class="cmp sm ask">
        <div class="cmp-head"><div class="cmp-title">${esc(title)}</div>
          <button class="x" data-x="no" title="닫기 (Esc)">✕</button></div>
        <div class="ask-body ask-say">${lines.map((t) =>
          `<p>${esc(t)}</p>`).join("")}</div>
        <div class="detail-actions">
          <button data-x="no">취소</button>
          <button class="primary" data-x="yes">${esc(okText)}</button></div>
      </div>`;
    document.body.appendChild(back);
    back.querySelector('[data-x="yes"]').focus();
    const close = (v) => {
      document.removeEventListener("keydown", onKey, true);
      back.remove(); done(v);
    };
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); close(false); }
      if (e.key === "Enter") { e.preventDefault(); close(true); }
    };
    document.addEventListener("keydown", onKey, true);
    back.addEventListener("click", (e) => {
      if (e.target === back) return close(false);
      const x = e.target.closest("[data-x]");
      if (x) close(x.dataset.x === "yes");
    });
  });
}
export function askBox(title, fields) {
  return new Promise((done) => {
    const back = document.createElement("div");
    back.className = "overlay ask-back";
    back.innerHTML = `
      <div class="cmp sm ask">
        <div class="cmp-head"><div class="cmp-title">${esc(title)}</div>
          <button class="x" data-x="cancel" title="닫기 (Esc)">✕</button></div>
        <div class="ask-body">${fields.map((f) => `
          <div class="fld"><label>${esc(f.label)}</label>
            <input data-k="${esc(f.key)}" value="${esc(f.value || "")}"
                   placeholder="${esc(f.hint || "")}"></div>`).join("")}</div>
        <div class="detail-actions">
          <button data-x="cancel">취소</button>
          <button class="primary" data-x="ok">확인</button></div>
      </div>`;
    document.body.appendChild(back);
    const first = back.querySelector("input");
    if (first) { first.focus(); first.select(); }
    const close = (val) => {
      document.removeEventListener("keydown", onKey, true);
      back.remove();
      done(val);
    };
    const take = () => {
      const out = {};
      back.querySelectorAll("input[data-k]").forEach((i) => { out[i.dataset.k] = i.value.trim(); });
      close(out);
    };
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); close(null); }
      if (e.key === "Enter") { e.preventDefault(); take(); }
    };
    document.addEventListener("keydown", onKey, true);
    back.addEventListener("click", (e) => {
      if (e.target === back) close(null);
      const x = e.target.closest("[data-x]");
      if (!x) return;
      if (x.dataset.x === "ok") take(); else close(null);
    });
  });
}
