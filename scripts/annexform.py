# -*- coding: utf-8 -*-
r"""서식 파일을 별표ㆍ별지 자리에 앉힌다 — 조문 글로 짓던 것을 갈음한다.

■ 왜

  신설 별표를 조문 본문 글에서 지어 왔다. 그러니 표여야 할 서식이 글줄로만
  나왔다. 무인비행장치는 별표수정(안) 양식을 잘라 쓰는 것으로 고쳤고
  (annexsplit.py), 작업규정은 App\관련규정\서식\ 에 서식 파일이 따로 있다.

      서식 17개  ↔  트리의 지어 낸 별표ㆍ별지 17건   (제목으로 하나도 빠짐없이 맞음)

■ 번호가 다르다

  서식 파일의 번호는 만들 때의 것이라 지금 트리와 다르다.

      별표44_안전관리비 계상 요율      →  트리 별표 51
      별표45_성과 유형별 성과패키지     →  트리 별표 17

  그래서 번호가 아니라 **제목으로 짝을 짓고**, 문서 안의 [별표 NN] 을 트리
  번호로 고쳐 넣는다.

  python scripts\annexform.py            무엇이 앉는지 보여만 준다
  python scripts\annexform.py --write    파일을 만들고 자료를 고친다
"""
import io
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BASE = os.path.dirname(os.path.dirname(ROOT))
DATA = os.path.join(ROOT, "data")

import formfill as FF                                   # noqa: E402
import forms_hwp as HWP                                 # noqa: E402

SRC = os.path.join(BASE, "App", "관련규정", "서식")
OUT = os.path.join(DATA, "annex", "form", "work")
PREV = os.path.join(DATA, "annex", "formwork")
DRAFT = os.path.join(DATA, "draft2025.json")

RE_FILE = re.compile(r"^(별표|별지)(\d+)_(.+)\.hwpx$")
RE_HEAD = re.compile(r"^\[(별표|별지)\s*(\d+)\]\s*$")


def norm(s):
    """제목을 견줄 꼴로 — 사이 기호와 공백을 걷어 낸다"""
    return re.sub(r"[\s·ㆍ/()]", "", str(s or ""))


def forms():
    """서식 파일 → {견줄 제목: (구분, 번호, 제목, 길)}"""
    out = {}
    for p in sorted(__import__("glob").glob(os.path.join(SRC, "*.hwpx"))):
        m = RE_FILE.match(os.path.basename(p))
        if m:
            out[norm(m.group(3))] = (m.group(1), m.group(2), m.group(3), p)
    return out


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def renumber(src, dst, gubun, no):
    """서식 하나를 옮겨 앉히며 문서 안의 번호를 트리 번호로 고친다"""
    f = FF.Form(src)
    hit = 0
    for _s, _e, _pp, _cp, t, blk, nested in f.paras():
        if nested:
            continue
        m = RE_HEAD.match(t.strip())
        if m:
            # 머리글 문단의 글만 갈아 끼운다 — 쪽 설정을 잃지 아니한다
            f.xml = f.xml.replace(blk, FF.retext(blk, "[%s %s]" % (gubun, no)), 1)
            hit += 1
            break
    f.save(dst)
    return hit


def main():
    write = "--write" in sys.argv
    book = forms()
    draft = json.load(io.open(DRAFT, encoding="utf-8"))

    plan, miss = [], []
    seen = set()
    for rev in [draft] + list(draft.get("next") or []):
        for x in walk(rev.get("tree") or []):
            a = x.get("annexRef")
            if not a or not a.get("gen"):
                continue
            g, no = a.get("gubun") or "별표", str(a.get("no"))
            if (g, no) in seen:
                continue
            seen.add((g, no))
            f = book.get(norm(x.get("title")))
            (plan if f else miss).append((g, no, x.get("title") or "", f))

    print("서식 %d개 · 지어 낸 별표ㆍ별지 %d건 · 짝지은 것 %d건"
          % (len(book), len(plan) + len(miss), len(plan)))
    for g, no, ti, f in plan:
        print("  %-4s %-3s %-40s ← %s" % (g, no, ti[:40], os.path.basename(f[3])))
    for g, no, ti, _f in miss:
        print("  [없음] %-4s %-3s %s" % (g, no, ti[:40]))
    if not write:
        print("\n보여만 준 것입니다. 앉히려면 --write 를 붙이십시오.")
        return

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    made = []
    for g, no, _ti, f in plan:
        dst = os.path.join(OUT, "%s%s.hwpx" % (g, no))
        if renumber(f[3], dst, g, no) == 0:
            print("  [주의] %s %s — 문서 안에서 [%s NN] 머리글을 못 찾았습니다"
                  % (g, no, g))
        made.append((g, no, dst))

    if HWP.available():
        hwp = HWP.Hwp()
        for _g, _no, dst in made:
            hwp.convert(dst, {"HWP": dst[:-1], "PDF": dst[:-4] + "pdf"},
                        fmt="HWPX")
        hwp.close()
        for _g, _no, dst in made:
            pdf = dst[:-4] + "pdf"
            if os.path.exists(pdf):
                base = os.path.splitext(os.path.basename(dst))[0]
                try:
                    HWP.pdf_to_webp(pdf, os.path.join(PREV, base + "_1.webp"),
                                    zoom=2.0)
                except Exception as ex:
                    print("  [그림 실패] %s — %s" % (base, ex))
        print("\n한/글로 .hwp · .pdf 와 미리보기 그림을 만들었습니다.")
    else:
        print("\n[주의] 한/글을 부를 수 없어 .hwpx 만 만들었습니다.")

    rel = os.path.relpath(OUT, ROOT).replace("\\", "/")
    n = 0
    for rev in [draft] + list(draft.get("next") or []):
        for x in walk(rev.get("tree") or []):
            a = x.get("annexRef")
            if not a or not a.get("gen"):
                continue
            g, no = a.get("gubun") or "별표", str(a.get("no"))
            p = "%s/%s%s" % (rel, g, no)
            if os.path.exists(os.path.join(ROOT, p + ".hwpx")):
                a["hwp"] = p + ".hwp"
                a["pdf"] = p + ".pdf"
                a["hwpx"] = p + ".hwpx"
                a["previewDir"] = "formwork"
                a["src"] = "관련규정 서식 파일"
                a.pop("gen", None)
                n += 1
    io.open(DRAFT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(draft, ensure_ascii=False))
    print("개정안 자료의 별표ㆍ별지 %d건이 서식 파일을 가리킵니다." % n)


if __name__ == "__main__":
    main()
