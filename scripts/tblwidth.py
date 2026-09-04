# -*- coding: utf-8 -*-
r"""원본 한/글 파일에서 표의 실제 칸 폭을 가져와 개체 XML 에 적어 둔다.

■ 왜

  본문에 박힌 표를 다시 그릴 때, 여태는 양식에 있던 표 하나를 본으로 삼아
  그 칸 폭을 그대로 썼다. 그런데 그 본은 4열이다. 열이 더 많은 표를 그리면
  마지막 폭을 되풀이해 붙이는 바람에 표가 본문폭을 넘었다.

      본문폭 45,356        표54(12열) 칸 합계 153,547   ← 세 곱절 넘게 넘침

  개체 XML 의 id 는 원본 한/글 파일의 <hp:tbl id> 를 그대로 물려받았다.
  그러니 원본에서 그 표를 찾아 실제 칸 폭을 가져올 수 있다.

■ 무엇을 적는가

  <table id="…" tw="총폭" cw="칸폭,칸폭,…"> 두 가지를 더한다.
  formdocs 가 그것을 보고 표를 그린다. 없으면 글 길이로 나눈다.

  python scripts\tblwidth.py            무엇이 달라지는지 보여만 준다
  python scripts\tblwidth.py --write    개체 XML 에 적는다
"""
import io
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = os.path.dirname(os.path.dirname(ROOT))
DATA = os.path.join(ROOT, "data")

# 원본 한/글 파일을 찾을 자리. 개체의 source 이름과 굳이 맞추지 아니하고,
# 있는 대로 모두 훑어 id 로 찾는다 — 같은 규정이 여러 벌 있기 때문이다.
SOURCES = [
    os.path.join(BASE, "Form", "09.현행원본", "공공측량 작업규정(2025).hwpx"),
    os.path.join(BASE, "99.참고자료", "관련규정",
                 "공공측량 작업규정.2025.04.23_수식수정.오류표시.hwpx"),
    os.path.join(BASE, "App", "관련규정", "공공측량작업규정",
                 "공공측량 작업규정.2025.04.23_수식수정.오류표시.hwpx"),
    os.path.join(BASE, "Form", "09.현행원본", "무인비행장치 측량 작업규정(2020 고시).hwpx"),
]


RE_T = re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", re.S)


def fp(rows, cells):
    """표를 알아보는 지문 — 칸 글을 이어 붙인 것.

    개체 XML 의 id 는 색인기가 새로 매긴 번호라 원본의 <hp:tbl id> 와 맞지
    않는다(하나도 겹치지 아니하였다). 그래서 번호가 아니라 내용으로 짝을
    찾는다. 공백을 모두 걷어 내어 색인 과정의 사소한 차이를 넘긴다."""
    s = re.sub(r"\s+", "", "".join(cells))
    return "%dx|%s" % (rows, s[:120])


def index_source(path):
    """원본 한/글 파일 → {지문: (총폭, [칸 폭…])}

    칸 폭은 병합되지 아니한 칸(colSpan=1)에서만 거둔다. 병합된 칸의 폭은
    여러 열을 아우른 것이라 한 열의 폭이 아니다."""
    out = {}
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return out
    for n in z.namelist():
        if not re.match(r"Contents/section\d+\.xml$", n):
            continue
        x = z.read(n).decode("utf-8", "replace")
        for m in re.finditer(r"<hp:tbl\s[^>]*>", x):
            e = x.find("</hp:tbl>", m.end())
            tbl = x[m.start():e]
            nrow = re.search(r'rowCnt="(\d+)"', m.group(0))
            texts = [re.sub(r"\s+", "", "".join(t.group(1) for t in RE_T.finditer(tc.group(0))))
                     for tc in re.finditer(r"<hp:tc\b.*?</hp:tc>", tbl, re.S)]
            tid = fp(int(nrow.group(1)) if nrow else 0, texts)
            sz = re.search(r'<hp:sz width="(\d+)"', tbl)
            cols = {}
            for tc in re.finditer(r"<hp:tc\b.*?</hp:tc>", tbl, re.S):
                s = tc.group(0)
                a = re.search(r'<hp:cellAddr colAddr="(\d+)"', s)
                sp = re.search(r'<hp:cellSpan colSpan="(\d+)"', s)
                w = re.search(r'<hp:cellSz width="(\d+)"', s)
                if not (a and w):
                    continue
                if sp and int(sp.group(1)) != 1:
                    continue
                cols.setdefault(int(a.group(1)), int(w.group(1)))
            if cols:
                order = [cols[k] for k in sorted(cols)]
                out[tid] = (int(sz.group(1)) if sz else sum(order), order)
    return out


def main():
    write = "--write" in sys.argv
    book = {}
    for p in SOURCES:
        if not os.path.exists(p):
            continue
        got = index_source(p)
        for k, v in got.items():
            book.setdefault(k, v)
        print("원본에서 표 %4d개를 읽었습니다 — %s"
              % (len(got), os.path.relpath(p, BASE)))
    print("서로 다른 표 %d개\n" % len(book))

    hit = miss = 0
    for p in sorted(__import__("glob").glob(os.path.join(DATA, "objects", "*", "*.xml"))):
        s = io.open(p, encoding="utf-8").read()
        m = re.search(r"<table\s[^>]*>", s)
        if not m:
            continue
        rows = re.findall(r"<row>(.*?)</row>", s, re.S)
        cells = [c for r in rows
                 for c in re.findall(r"<cell[^>]*>(.*?)</cell>", r, re.S)]
        key = fp(len(rows), cells)
        if key not in book:
            miss += 1
            continue
        tw, cw = book[key]
        hit += 1
        tag = m.group(0)
        tag = re.sub(r'\s+tw="[^"]*"', "", tag)
        tag = re.sub(r'\s+cw="[^"]*"', "", tag)
        tag = tag[:-1] + ' tw="%d" cw="%s">' % (tw, ",".join(str(v) for v in cw))
        if write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                s[:m.start()] + tag + s[m.end():])
        if hit <= 6:
            print("  %-28s %d열 · 총폭 %d · %s"
                  % (os.path.basename(p), len(cw), tw,
                     ",".join(str(v) for v in cw)))

    print("\n원본 폭을 찾은 표 %d개 · 못 찾은 표 %d개" % (hit, miss))
    if not write:
        print("보여만 준 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
