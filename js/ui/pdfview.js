/* ============================================================
   ui/pdfview.js — PDF 를 쪽마다 그려 보인다
   ------------------------------------------------------------
   <iframe> 이나 <object> 로 붙이면 브라우저의 PDF 뷰어에 맡기게 되는데,
   그것이 없거나 막혀 있는 자리에서는 까만 칸만 남는다. 실제로 그러하였다.

   저장소에 pdf.js 가 이미 들어 있으므로(본문 글자를 뽑을 때 쓴다) 그것으로
   직접 그린다 — 뷰어가 있든 없든 똑같이 보이고, 밖으로 나가지도 아니한다.

   쪽이 많은 별표가 있으므로 화면에 들어올 때에 그린다(IntersectionObserver).
   ============================================================ */

/* pdf.js 를 부르는 일은 core/pdfjs.js 에 모아 두었다 — 서버가 .mjs 를
   text/plain 으로 내주면 모듈이 막히는데, 그것을 넘기는 수가 들어 있다. */
import { loadPdfjs } from "../core/pdfjs.js?v=20260906q";

/**
 * PDF 를 쪽마다 그려 넣는다.
 * @param {HTMLElement} box  그릴 자리 (비우고 채운다)
 * @param {string} url       PDF 주소 (마디마다 감싼 것)
 * @param {object} [opt]     {scale} — 1 이면 폭 100%
 * @returns {Promise<number>} 그린 쪽 수 (실패하면 0)
 */
export async function renderPdf(box, url, opt = {}) {
  box.innerHTML = `<div class="pv-wait">PDF 를 여는 중…</div>`;
  let doc;
  try {
    const pdf = await loadPdfjs();
    doc = await pdf.getDocument({ url, isEvalSupported: false }).promise;
  } catch (e) {
    box.innerHTML = `<div class="pv-fail">PDF 를 열지 못했습니다 —
      위의 <b>PDF 내려받기</b> 로 받아 보십시오.</div>`;
    return 0;
  }

  box.innerHTML = "";
  const n = doc.numPages;
  const io = ("IntersectionObserver" in window)
    ? new IntersectionObserver((es) => {
        for (const e of es) {
          if (!e.isIntersecting) continue;
          io.unobserve(e.target);
          draw(e.target);
        }
      }, { root: box, rootMargin: "400px" })
    : null;

  for (let i = 1; i <= n; i++) {
    const fig = document.createElement("figure");
    fig.className = "pv-page";
    fig.dataset.page = String(i);
    fig.innerHTML = `<div class="pv-skel">${i} / ${n}</div>`;
    box.appendChild(fig);
    if (io) io.observe(fig); else await draw(fig);
  }

  async function draw(fig) {
    const no = Number(fig.dataset.page);
    try {
      const page = await doc.getPage(no);
      // 화면 너비에 맞추고, 화면이 촘촘하면 그만큼 크게 그린다
      const w = Math.max(320, fig.clientWidth || box.clientWidth || 720);
      const v1 = page.getViewport({ scale: 1 });
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const scale = (w / v1.width) * dpr * (opt.scale || 1);
      const vp = page.getViewport({ scale });
      const cv = document.createElement("canvas");
      cv.width = Math.floor(vp.width);
      cv.height = Math.floor(vp.height);
      cv.style.width = "100%";
      await page.render({ canvasContext: cv.getContext("2d"), viewport: vp }).promise;
      fig.innerHTML = "";
      fig.appendChild(cv);
      if (n > 1) {
        const cap = document.createElement("figcaption");
        cap.textContent = `${no} / ${n}`;
        fig.appendChild(cap);
      }
    } catch {
      fig.innerHTML = `<div class="pv-fail">${no}쪽을 그리지 못했습니다.</div>`;
    }
  }

  return n;
}
