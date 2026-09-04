# -*- coding: utf-8 -*-
r"""PDF 안의 그림만 줄여 파일을 가볍게 한다. 글자와 벡터는 손대지 아니한다.

■ 왜 그림만 건드리는가

  ASPRS 표준 문서는 228쪽 19.8MB 인데, 그 가운데 13.9MB 가 그림 56개이다.
  글자는 611,218자로 벡터이므로 크기에 거의 보태지 아니한다. 그림만 줄이면
  읽는 데 아무 지장 없이 파일이 작아진다.

  가장 큰 것 하나가 8.9MB —— 첫 쪽 표지가 2663x3413 로 들어 있다. 종이에
  놓인 크기로 따지면 300dpi 를 넘는다. 화면으로 보고 인쇄해 보는 문서에는
  지나치다.

■ 어떻게 줄이는가

  ㆍ 쪽에 놓인 실제 크기를 재어 dpi 를 구한다. 목표 dpi 를 넘는 것만 줄인다.
    **키우지는 아니한다** —— 이미 성긴 그림을 늘리면 크기만 늘고 흐려진다.
  ㆍ JPEG 로 다시 뜬다. 다만 줄인 것이 원래보다 크면 원래 것을 둔다.
  ㆍ 투명(알파)이 있는 그림은 건드리지 아니한다. JPEG 는 투명을 담지 못해
    검은 바탕이 생긴다.

■ 무엇을 확인하는가

  쪽수와 글자 수가 그대로인지 본다. 하나라도 어긋나면 갈아 끼우지 아니한다.

  python scripts\pdfslim.py <파일>                보여만 준다
  python scripts\pdfslim.py <파일> --write        갈아 끼운다
  옵션 : --dpi 150 (기본) · --quality 80 (기본)
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")


def arg(name, default):
    if name in sys.argv:
        return type(default)(sys.argv[sys.argv.index(name) + 1])
    return default


def main():
    import fitz
    from PIL import Image

    src = next((a for a in sys.argv[1:] if not a.startswith("--")
                and os.path.exists(a)), None)
    if not src:
        sys.exit("줄일 PDF 를 대어 주십시오.")
    write = "--write" in sys.argv
    DPI = arg("--dpi", 150)
    Q = arg("--quality", 80)

    doc = fitz.open(src)
    n_pages, before = len(doc), os.path.getsize(src)
    text0 = "".join(doc[i].get_text() for i in range(n_pages))

    # 그림이 쪽에 놓인 크기 —— 같은 그림이 여러 쪽에 있으면 가장 큰 자리를 본다
    placed = {}
    for i in range(n_pages):
        for x in doc[i].get_images(full=True):
            xref = x[0]
            for r in doc[i].get_image_rects(xref):
                w = max(r.width, 1)
                placed[xref] = max(placed.get(xref, 0), w)

    rows, saved = [], 0
    for xref, wpt in sorted(placed.items()):
        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        raw, w, h = info["image"], info["width"], info["height"]
        try:
            im = Image.open(io.BytesIO(raw))
        except Exception:
            continue
        if im.mode in ("RGBA", "LA", "P") and "transparency" in im.info:
            rows.append((xref, len(raw), len(raw), "투명이 있어 그대로 둠"))
            continue
        dpi = w / (wpt / 72.0) if wpt else 0
        scale = min(1.0, DPI / dpi) if dpi > DPI else 1.0
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        im2 = im.convert("RGB")
        if scale < 1.0:
            im2 = im2.resize((nw, nh), Image.LANCZOS)
        buf = io.BytesIO()
        im2.save(buf, "JPEG", quality=Q, optimize=True, progressive=True)
        new = buf.getvalue()
        if len(new) >= len(raw):
            rows.append((xref, len(raw), len(raw), "줄여도 크므로 그대로 둠"))
            continue
        rows.append((xref, len(raw), len(new),
                     "%dx%d → %dx%d (%.0fdpi)" % (w, h, nw, nh, dpi)))
        saved += len(raw) - len(new)
        if write:
            doc.update_stream(xref, new, new=False) if False else None
            for i in range(n_pages):
                if xref in [y[0] for y in doc[i].get_images(full=True)]:
                    doc[i].replace_image(xref, stream=new)
                    break

    print("%s" % os.path.basename(src))
    print("   쪽 %d · 지금 %.1f MB · 그림 %d개" % (n_pages, before / 1048576, len(rows)))
    print("   목표 %ddpi · 품질 %d" % (DPI, Q))
    print()
    rows.sort(key=lambda z: -(z[1] - z[2]))
    print("%8s %10s %10s  %s" % ("xref", "지금", "줄인 뒤", "무엇을"))
    for xref, a, b, why in rows[:12]:
        print("%8d %10d %10d  %s" % (xref, a, b, why))
    print()
    print("   줄어들 양 %.1f MB → 대략 %.1f MB"
          % (saved / 1048576, (before - saved) / 1048576))

    if not write:
        print()
        print("보여만 준 것임. 갈아 끼우려면 --write 를 붙일 것.")
        return

    tmp = src + ".slim"
    doc.save(tmp, garbage=4, deflate=True, clean=True)
    doc.close()
    chk = fitz.open(tmp)
    ok_pages = len(chk) == n_pages
    text1 = "".join(chk[i].get_text() for i in range(len(chk)))
    ok_text = (text1 == text0)
    after = os.path.getsize(tmp)
    chk.close()
    print()
    print("   쪽수 그대로 : %s · 글자 그대로 : %s (%d자)"
          % ("예" if ok_pages else "★ 아니오",
             "예" if ok_text else "★ 아니오 (%d자)" % len(text1), len(text0)))
    if not (ok_pages and ok_text):
        print("   어긋나므로 갈아 끼우지 아니합니다 — %s" % tmp)
        return
    os.replace(tmp, src)
    print("   갈아 끼웠습니다 — %.1f MB → %.1f MB (%d%% 줄임)"
          % (before / 1048576, after / 1048576,
             round(100 * (before - after) / before)))


if __name__ == "__main__":
    main()
