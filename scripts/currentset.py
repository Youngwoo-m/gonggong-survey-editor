# -*- coding: utf-8 -*-
r"""현행 규정과 그 별표ㆍ별지를 규정별 폴더에 모아 둔다.

  App\개정안\<규정>\0.1.현행규정(별표및별지포함)\
      <규정 이름>.hwpx            현행 고시 본문
      별표및별지\[별표 1] ….hwpx    별표ㆍ별지 원본과 PDF

개정안을 만들 때마다 현행과 견주어야 하는데, 현행 원본이 여기저기 흩어져
있어 찾아 헤매게 된다. 한자리에 모아 둔다.

  python scripts\currentset.py            무엇을 담을지 보여만 준다
  python scripts\currentset.py --write    실제로 담는다
"""
import io
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)          # App\prototype
APP = os.path.dirname(PROTO)           # App
BASE = os.path.dirname(APP)            # 2026.공공측량.품관원
OUT = os.path.join(APP, "개정안")
SUB = "0.1.현행규정(별표및별지포함)"

# (규정 폴더 이름, 현행 본문, 별표ㆍ별지가 든 폴더)
REGS = [
    ("작업규정",
     os.path.join(BASE, "Form", "09.현행원본", "공공측량 작업규정(2025).hwpx"),
     os.path.join(PROTO, "data", "annex", "원본", "work")),
    ("성과심사 규정",
     os.path.join(APP, "관련규정", "성과심사관련규정",
                  "측량성과 심사수탁기관의 심사업무 및 지정절차 등에 관한 규정"
                  "(국토지리정보원고시)(제2025-2091호)(20250423).hwpx"),
     os.path.join(PROTO, "data", "annex", "원본", "review")),
    ("무인비행장치 규정",
     os.path.join(BASE, "Form", "09.현행원본",
                  "무인비행장치 측량 작업규정(2020 고시).hwpx"),
     os.path.join(PROTO, "data", "annex", "reg12", "원본")),
]


def titles_of(regid):
    """별표 번호 → 제목.

    파일 이름이 '별표1.hwpx' 처럼 번호뿐인 자리(reg12)에 이름을 붙이려는 것이다.
    규정 자료(reg12.json)에는 별표 마디가 없으므로 서식 표 색인에서 가져온다."""
    out = {}
    p = os.path.join(PROTO, "data", "objects", regid, "annex-index.json")
    if not os.path.exists(p):
        return out
    try:
        idx = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return out
    for k, v in idx.items():
        if v.get("title"):
            out[k] = v["title"]
    return out


TITLE = {"무인비행장치 규정": "reg12"}


def safe(s):
    """파일 이름에 쓸 수 없는 글자를 걷어 낸다.

    별표 제목에 빗금이 들어 있다 — 「검사표(수치표면자료/수치표면모형 …)」.
    그대로 쓰면 없는 폴더에 담으려 하다 멎는다."""
    import re as _re
    return _re.sub(r'[\/:*?"<>|]', "_", str(s or "")).strip()


def main():
    write = "--write" in sys.argv
    for name, body, anxdir in REGS:
        dst = os.path.join(OUT, name, SUB)
        print("━━ %s" % name)
        if not os.path.exists(body):
            print("   ! 현행 본문을 찾지 못했습니다 — %s" % body)
            body = None
        else:
            print("   본문 : %s" % os.path.basename(body))
        files = []
        if os.path.isdir(anxdir):
            files = sorted(f for f in os.listdir(anxdir)
                           if f.lower().endswith((".hwpx", ".pdf")))
        n_hwpx = sum(1 for f in files if f.lower().endswith(".hwpx"))
        print("   별표ㆍ별지 : %d건 (hwpx %d · pdf %d)"
              % (n_hwpx, n_hwpx, len(files) - n_hwpx))
        if not write:
            continue
        os.makedirs(os.path.join(dst, "별표및별지"), exist_ok=True)
        if body:
            shutil.copyfile(body, os.path.join(dst, os.path.basename(body)))
        titles = titles_of(TITLE.get(name, "")) if name in TITLE else {}
        for f in files:
            stem, ext = os.path.splitext(f)
            out_name = f
            # 이름이 '별표1' 처럼 번호뿐이면 제목을 붙여 알아보기 쉽게 한다
            t = titles.get(stem.replace(" ", ""))
            if t:
                gub = "별지" if stem.startswith("별지") else "별표"
                num = stem.replace(gub, "").strip()
                out_name = safe("[%s %s] %s" % (gub, num, t)) + ext
            shutil.copyfile(os.path.join(anxdir, f),
                            os.path.join(dst, "별표및별지", out_name))
        print("   → %s" % dst)
    if not write:
        print()
        print("시험만 한 것입니다. 담으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
