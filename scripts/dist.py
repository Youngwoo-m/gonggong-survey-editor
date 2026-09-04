# -*- coding: utf-8 -*-
r"""인터넷이 닿지 아니하는 PC 에 옮겨 쓸 배포 꾸러미를 짓는다.

  python scripts\dist.py            무엇을 담을지 보여만 준다
  python scripts\dist.py --write    zip 을 짓는다
  python scripts\dist.py --write --out D:\어디에\

■ 인터넷 없이 도는가

  편집기 화면(index.html ㆍ css ㆍ js)은 바깥을 부르지 아니한다. 글꼴도
  이미지도 모두 이 폴더 안에 있고, PDF 보기는 vendor\pdfjs 를 함께 담았다.

  다만 두 가지는 인터넷이 있어야 도는 **곁다리 기능**이다. 없으면 그 단추만
  듣지 아니할 뿐 편집기는 그대로 돈다.

      GitHub 로 올리고 내리기      js\adapters\github.js
      AI 도움말                    js\adapters\ai.js

■ 왜 서버가 있어야 하는가

  화면이 ES 모듈과 fetch 로 짜여 있어 `file://` 로 열면 브라우저가 막는다.
  그래서 `실행.bat` 이 파이썬 기본 서버(serve.py)를 띄우고 브라우저를 연다.
  받는 PC 에 **파이썬 3 이 있어야 한다** — 없으면 읽어보세요.txt 에 적어 둔
  다른 길을 쓴다.

■ 무엇을 빼는가

      scripts\           문서를 짓는 파이썬 연장 — 한/글이 있어야 돌고,
                         편집기를 쓰는 데에는 쓰이지 아니한다.
      data\report\       생성기가 낸 찌꺼기(8.8MB). 화면이 읽지 아니한다.
      __pycache__        파이썬이 남긴 것.
      할일.md ㆍ KS표준인용.md
                         안에서 보는 기록.
"""
import datetime
import io
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "공공측량_규정개정_편집기"

# 담을 것 — 폴더는 통째로, 파일은 그것만
TAKE_DIR = ["css", "js", "vendor", "data", "kit", "docs", "sample"]
TAKE_FILE = ["index.html", "serve.py", "실행.bat", "README.md"]

# 폴더 안에서 뺄 것 (경로 조각으로 본다)
DROP_PART = ["__pycache__", os.sep + "data" + os.sep + "report" + os.sep]
DROP_EXT = [".pyc", ".pyo"]


def wanted(rel):
    p = os.sep + rel.replace("/", os.sep)
    if any(d in p for d in DROP_PART):
        return False
    if os.path.splitext(rel)[1].lower() in DROP_EXT:
        return False
    return True


def gather():
    """담을 것을 모은다 → [(실제 길, 꾸러미 안 이름)]"""
    out = []
    for f in TAKE_FILE:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            out.append((p, f))
    for d in TAKE_DIR:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for cur, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                p = os.path.join(cur, f)
                rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                if wanted(rel):
                    out.append((p, rel))
    return out


READ_ME = r"""공공측량 규정 개정 편집기 — 인터넷 없이 쓰기

■ 여는 법

  1. 이 꾸러미를 아무 폴더에나 풉니다. 한글이 든 경로도 괜찮습니다.
     반드시 폴더째 푸십시오 — 파일 하나만 꺼내면 돌지 아니합니다.
  2. 「실행.bat」 을 두 번 누릅니다.
  3. 브라우저가 저절로 열립니다. 열리지 아니하면 주소창에 아래를 칩니다.

         http://localhost:8765

  4. 마칠 때는 검은 창을 닫습니다.

■ 파이썬이 있어야 합니다

  화면이 ES 모듈로 짜여 있어 파일을 곧바로 여는 방식(file://)으로는
  브라우저가 막습니다. 그래서 작은 서버를 하나 띄웁니다.

  파이썬 3 이 깔려 있지 아니하면 「실행.bat」 이 그렇게 알립니다.
  그때는 둘 가운데 하나를 하십시오.

      ㆍ 파이썬 3 을 깝니다 (python.org — 인터넷 되는 PC 에서 내려받아 옮깁니다).
        깔 때 「Add python.exe to PATH」 를 켜십시오.
      ㆍ 다른 정적 서버가 이미 있으면 이 폴더에서 그것을 띄우고
        그 주소로 들어갑니다.

  파이썬은 서버를 띄우는 데에만 씁니다. 편집기 자체는 브라우저 안에서 돕니다.

■ 폴더 짜임 — 어디에 무엇이 있는가

      실행.bat            이것을 누릅니다
      읽어보세요.txt        이 글
      index.html          편집기 화면
      serve.py            실행.bat 이 띄우는 작은 서버
      css\  js\           화면을 이루는 것 — 손대지 마십시오
      vendor\pdfjs\       PDF 를 보여 주는 것 (인터넷 없이 돌라고 함께 담음)
      data\               규정 자료 — 이 꾸러미의 알맹이입니다
        data\reg*.json      참조규정 103종의 본문
        data\draft*.json    개정안 세 벌
        data\annex\        별표ㆍ별지의 원본(hwpx ㆍ pdf)과 미리보기(webp)
        data\objects\      조문 본문에 딸린 표
      kit\                 화면에서 보고서를 내려받을 때 그 안에 함께 담기는 재료
      docs\  sample\       개정 메모와 보기 파일
      README.md           만든 사람을 위한 글 — 안 보셔도 됩니다

■ 인터넷 없이 되는 것

  ㆍ 규정 읽기, 조문 고치기, 신구대조표 보기
  ㆍ 별표ㆍ별지 미리보기와 내려받기 (hwpx ㆍ pdf)
  ㆍ 참조규정 103종 열어 보기
  ㆍ 보고서 내려받기 (html ㆍ xlsx ㆍ hwpx)
  ㆍ PDF 보기

■ 인터넷이 있어야 되는 것 — 없으면 그 단추만 듣지 아니합니다

  ㆍ GitHub 로 올리고 내리기
  ㆍ AI 도움말

■ 고친 것은 어디에 남는가

  브라우저 안(IndexedDB)에 남습니다. PC 를 옮기면 따라가지 아니합니다.
  다른 PC 로 옮기려면 화면에서 내려받기로 파일을 뽑아 옮기십시오.
  브라우저의 「인터넷 사용 기록 삭제」로 사이트 데이터를 지우면 함께 지워집니다.

  처음 상태로 되돌리려면 화면의 「현행으로 초기화」 를 누릅니다.

■ 한/글 문서를 짓는 일에 대하여

  화면에서 개정(안)ㆍ신구대조표ㆍ개정사유서를 hwpx 로 곧바로 내려받을 수 있고,
  이것은 인터넷도 한/글도 없이 됩니다.

  그와 별개로, 화면의 「보고서 생성」으로 내려받는 zip 안에는
  「한글문서만들기.bat」 이 함께 들어갑니다. 그것을 쓰려면 그 zip 을 풀어 놓은
  PC 에 한/글과 파이썬이 있어야 합니다. 이 꾸러미의 kit\ 폴더는
  그 zip 에 담길 재료일 뿐이므로 여기서 직접 누르지 마십시오.

■ 담긴 것

%(list)s

  지은 날 : %(day)s
"""


def main():
    write = "--write" in sys.argv
    out = (sys.argv[sys.argv.index("--out") + 1]
           if "--out" in sys.argv else os.path.dirname(ROOT))
    items = gather()
    total = sum(os.path.getsize(p) for p, _ in items)

    # 무엇이 얼마나 담기는지
    by = {}
    for p, rel in items:
        top = rel.split("/")[0] if "/" in rel else "(낱개 파일)"
        n, s = by.get(top, (0, 0))
        by[top] = (n + 1, s + os.path.getsize(p))
    lines = []
    for k in sorted(by, key=lambda z: -by[z][1]):
        n, s = by[k]
        lines.append("      %-14s %5d개  %7.1fMB" % (k, n, s / 1048576))
    print("담을 것 %d개 · %.1fMB" % (len(items), total / 1048576))
    print("\n".join(lines))

    day = datetime.date.today().isoformat()
    zpath = os.path.join(out, "%s_%s.zip" % (NAME, day))
    print()
    print("꾸러미 : %s" % zpath)
    if not write:
        print()
        print("시험만 한 것입니다. 지으려면 --write 를 붙이십시오.")
        return

    readme = READ_ME % {"list": "\n".join(lines), "day": day}
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(NAME + "/읽어보세요.txt",
                   readme.encode("utf-8-sig").decode("utf-8-sig")
                   .replace("\n", "\r\n"))
        for p, rel in items:
            z.write(p, NAME + "/" + rel)
    print("   지었습니다 — %.1fMB (푼 크기 %.1fMB)"
          % (os.path.getsize(zpath) / 1048576, total / 1048576))


if __name__ == "__main__":
    main()
