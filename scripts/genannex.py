# -*- coding: utf-8 -*-
"""
별표·서식 PDF → 미리보기 이미지(WebP) 생성

국가법령정보센터는 CORS 를 허용하지 않아 브라우저에서 PDF 를 직접 읽을 수 없다.
그래서 여기서 미리 이미지로 만들어 함께 배포한다.

사용:  python scripts/genannex.py [카테고리 …]
       (기본: core review — 핵심 규정과 성과심사 관련만)
       python scripts/genannex.py all      → 전부
출력:  data/annex/<regId>/<gubun><no>_<page>.webp
       data/annex/index.json
"""
import io, json, os, re, sys, time, urllib.request

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "annex")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}

WIDTH = 1000          # 렌더 가로 픽셀
QUALITY = 72          # WebP 품질
MAX_PAGES = 4         # 별표 한 건당 최대 쪽수


def fetch(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2)


def render(pdf_bytes):
    """PDF 바이트 → [webp 바이트, …]"""
    out = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= MAX_PAGES:
                break
            zoom = WIDTH / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out.append(pix.pil_tobytes(format="WEBP", quality=QUALITY, method=4))
    return out


def slug(s):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", str(s)).strip("_")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    cats = None if (args and args[0] == "all") else (args or ["core", "review"])

    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    regs = [r for r in lib["regulations"] if r.get("hasFullText")]
    if cats:
        regs = [r for r in regs if r["category"] in cats]

    os.makedirs(OUT, exist_ok=True)
    index, total_img, total_bytes = {}, 0, 0

    for r in regs:
        doc = json.load(io.open(os.path.join(DATA, r["file"]), encoding="utf-8"))
        annex = doc.get("annex") or []
        if not annex:
            continue
        d = os.path.join(OUT, r["id"])
        os.makedirs(d, exist_ok=True)
        entry = {}
        print(f"\n[{r['name']}] 별표 {len(annex)}건")
        for a in annex:
            src = a.get("pdf") or a.get("hwp")
            if not src:
                continue
            key = f"{a['gubun']}{a['no']}"
            try:
                blob = fetch(src)
                if blob[:4] != b"%PDF":
                    print(f"   [PDF아님] {key}")
                    continue
                pages = render(blob)
                names = []
                for pi, img in enumerate(pages, start=1):
                    fn = f"{slug(key)}_{pi}.webp"
                    with open(os.path.join(d, fn), "wb") as f:
                        f.write(img)
                    names.append(fn)
                    total_img += 1
                    total_bytes += len(img)
                entry[key] = names
                print(f"   OK  {key:<10} {len(pages)}쪽  {sum(len(x) for x in pages)/1024:6.0f} KB  {a['title'][:28]}")
            except Exception as e:
                print(f"   [오류] {key}: {e}")
        if entry:
            index[r["id"]] = entry

    with io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n완료 — 규정 {len(index)}종 / 이미지 {total_img}장 / {total_bytes/1024/1024:.1f} MB")
    print(f"출력: {OUT}")
