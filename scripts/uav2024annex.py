# -*- coding: utf-8 -*-
r"""무인비행장치 2024년 연구성과 판(v1)의 별표 8ㆍ9ㆍ10 을 연구 원본으로 갈아 끼운다.

■ 왜

  v1(2024년 연구성과)의 별표 8ㆍ9ㆍ10 은 본문 글로 지은 것을 쓰고 있었다.
  연구에서 실제로 낸 한/글 파일이 따로 있으므로 그것으로 바꾼다.

      App\관련규정\무인비행장치 측량 작업규정개정관련\2024년.연구.한글파일
        별표8.무인비행장치용 대공표지의 형상.hwpx
        별표9.GNSS_PPK측위결과의 활용.hwpx
        별표10.품질관리기준.hwpx

  파일 이름에 눈에 보이지 않는 글자(U+200B)가 섞여 있어, 이름으로 찾지 아니하고
  '별표N' 만 뽑아 짝짓는다.

■ 하는 일

  1. hwpx 를 data/annex/원본/uav2024/별표N.hwpx 로 옮겨 담는다
  2. 한/글로 .hwp 와 .pdf 를 뽑는다
  3. 미리보기 그림을 data/annex/uav2024/ 에 그린다
  4. annexRef 를 그 파일로 바꾸고, 갈기 전의 길은 genSrc 에 남긴다

  python scripts\uav2024annex.py            보여만 준다
  python scripts\uav2024annex.py --write    자료에 적는다
"""
import io
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

DATA = os.path.join(ROOT, "data")
SRC = os.path.join(os.path.dirname(ROOT), "관련규정",
                   "무인비행장치 측량 작업규정개정관련", "2024년.연구.한글파일")
DST = os.path.join(DATA, "annex", "원본", "uav2024")
SHOT = os.path.join(DATA, "annex", "uav2024")

# 눈에 보이지 않는 글자를 걷어 낸다 — 파일 이름에 U+200B 가 섞여 있다
INVIS = re.compile("[​‌‍﻿]")


def find_sources():
    """{'8': 길, '9': …} — 이름에서 '별표N' 만 뽑아 짝짓는다"""
    got = {}
    if not os.path.isdir(SRC):
        return got
    for fn in os.listdir(SRC):
        if not fn.lower().endswith(".hwpx"):
            continue
        m = re.match(r"별표\s*(\d+)", INVIS.sub("", fn))
        if m:
            got[m.group(1)] = os.path.join(SRC, fn)
    return got


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    got = find_sources()
    print("연구 원본 %d개 : %s" % (len(got), ", ".join("별표 " + k for k in sorted(got, key=int))))
    if not got:
        print("원본을 찾지 못했습니다 — %s" % SRC)
        return

    path = os.path.join(DATA, "draft_uav.json")
    doc = json.load(io.open(path, encoding="utf-8"))
    rev = doc                                   # v1 은 첫 판이다
    todo, hits = [], []
    for x in walk(rev.get("tree") or []):
        a = x.get("annexRef")
        if not a or a.get("gubun") != "별표":
            continue
        no = str(a.get("no"))
        if no not in got:
            continue
        hits.append((no, x, a))

    print()
    print("v1 에서 갈아 끼울 것 %d개" % len(hits))
    for no, x, a in hits:
        print("   별표 %-3s %-34s  ← %s" % (no, str(x.get("title"))[:33],
                                           os.path.basename(INVIS.sub("", got[no]))[:44]))
    if not write:
        print()
        print("보여만 준 것입니다. 적으려면 --write 를 붙이십시오.")
        return

    os.makedirs(DST, exist_ok=True)
    for no, _x, _a in hits:
        dst = os.path.join(DST, "별표%s.hwpx" % no)
        shutil.copyfile(got[no], dst)
        todo.append(dst)

    print()
    print("■ 한/글로 hwp ㆍ pdf 뽑기")
    from hwprender import render
    pages, bad = render(todo, also_hwp=True)
    print("   된 것 %d · 안 된 것 %d" % (len(pages), len(bad)))
    for k, m in bad:
        print("      실패 %s %s" % (k, m))

    print()
    print("■ 미리보기 그리기")
    import fitz
    os.makedirs(SHOT, exist_ok=True)
    for no, _x, _a in hits:
        pdf = os.path.join(DST, "별표%s.pdf" % no)
        if not os.path.exists(pdf):
            continue
        with fitz.open(pdf) as d2:
            for i, page in enumerate(d2, 1):
                if i > 12:
                    break
                zoom = 1400 / max(page.rect.width, 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                io.open(os.path.join(SHOT, "별표%s_%d.webp" % (no, i)), "wb").write(
                    pix.pil_tobytes(format="WEBP", quality=82, method=4))
        print("   별표 %-3s %d쪽" % (no, len(fitz.open(pdf))))

    print()
    print("■ 걸기")
    for no, x, a in hits:
        rel = "data/annex/원본/uav2024/별표%s" % no
        if not os.path.exists(os.path.join(ROOT, rel + ".pdf")):
            print("   별표 %s — pdf 가 없어 걸지 못함" % no)
            continue
        # 갈기 전의 길(본문 글로 지은 것)은 남겨 둔다
        if a.get("gen") and not a.get("genSrc"):
            a["genSrc"] = {k: a.get(k) for k in ("hwp", "hwpx", "pdf") if a.get(k)}
        a["hwpx"] = rel + ".hwpx"
        a["hwp"] = rel + ".hwp"
        a["pdf"] = rel + ".pdf"
        a["previewDir"] = "uav2024"
        a["gen"] = False
        a["src"] = "2024년 연구성과 한글파일"
        # 다시 짓기(--force)가 덮어쓰지 못하게 못박는다 —
        # 이것은 우리가 지은 것이 아니라 연구에서 받은 원본이다
        a["keepSrc"] = True
        import fitz as f2
        a["pages"] = len(f2.open(os.path.join(ROOT, rel + ".pdf")))
        print("   별표 %-3s → %s (%d쪽)" % (no, rel, a["pages"]))
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("draft_uav.json 에 적었습니다.")


if __name__ == "__main__":
    main()
