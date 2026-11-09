# -*- coding: utf-8 -*-
r"""개정안 별표 28 ㆍ 별표 31 의 「GNSS높이측량」을 「GNSS 수준측량」으로 (2026-11-09).

■ 왜

  제2편 제4장의 이름을 「GNSS 수준측량」으로 정비하면서 본문은 고쳤으나,
  현행에서 이어받은 서식 두 개(현행 별표 10 관측기록부, 별표 13 성과표)는
  현행 원본 파일을 그대로 가리켜 옛 이름이 남았다(보류 지적 2편B-3).

  현행 원본(data/annex/원본/work/…)을 고치면 현행 규정의 별표까지 바뀌므로
  손대지 아니한다. 개정안 자리(data/annex/gen/work/별표28.hwpx ㆍ 별표31.hwpx)에
  사본을 두고 글자만 바꾼 뒤 개정안 마디가 그것을 가리키게 한다.
  PDF 는 한/글로 다시 뽑는다(hwprender). 미리보기는 annexfix.py 가 짓는다.

  이미 되어 있으면 아무것도 하지 아니한다.

  python scripts\annexgnss.py            보여만 준다
  python scripts\annexgnss.py --write    파일을 짓고 자료에 적는다
"""
import io
import json
import os
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
GEN = os.path.join(ROOT, "data", "annex", "gen", "work")
SKILL = r"C:\Users\ds2ey\.claude\skills\hwpx"
NL = chr(10)
OLD, NEW = "GNSS높이측량", "GNSS 수준측량"
NODES = {"reg01-anx-별표-10": "별표28", "reg01-anx-별표-13": "별표31"}


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def copy_replace(src, dst):
    """HWPX 의 글자만 바꾼 사본 —— 항목 차례와 압축 방식은 그대로"""
    tmp = dst + ".tmp"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            b = zin.read(it.filename)
            if it.filename.endswith((".xml", ".txt")):
                b = b.decode("utf-8").replace(OLD, NEW).encode("utf-8")
            zout.writestr(it, b)
    os.replace(tmp, dst)
    subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "fix_namespaces.py"), dst],
                   check=True, capture_output=True)


def main():
    write = "--write" in sys.argv
    d = json.load(io.open(SRC, encoding="utf-8"))
    by = {n["id"]: n for n in walk(d["tree"])}
    todo = []
    for nid, name in NODES.items():
        n = by[nid]
        a = n["annexRef"]
        rel = "data/annex/gen/work/%s.hwpx" % name
        if a.get("hwpx") == rel and OLD not in (n.get("title") or ""):
            continue
        todo.append((n, name, rel))
    if not todo:
        print("바꿀 것: 없음 (이미 적용됨)")
        return
    for n, name, rel in todo:
        print("바꿀 것: %s %s —— %s" % (n["id"], n.get("title"), rel))
    if not write:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")
        return
    from hwprender import render                     # 한/글이 있어야 하므로 쓸 때만 부른다
    os.makedirs(GEN, exist_ok=True)
    for n, name, rel in todo:
        a = n["annexRef"]
        src = os.path.join(ROOT, a["hwpx"])
        dst = os.path.join(ROOT, rel)
        copy_replace(src, dst)
        _pages, failed = render([dst], os.path.dirname(dst), quiet=True)
        if failed:
            print("!! PDF 를 뽑지 못함 —— %s" % failed)
            sys.exit(1)
        a["hwpx"] = rel
        a["pdf"] = rel[:-5] + ".pdf"
        a.pop("hwp", None)                           # 옛 원본 .hwp 는 옛 이름을 지니므로 걸지 아니함
        a["previewDir"] = "genwork"
        n["title"] = (n.get("title") or "").replace(OLD, NEW)
        if n.get("status") == "이동":
            n["status"] = "이동·수정"
        r = n.get("reason") or ""
        line = "* 서식 이름과 서식 안의 「GNSS높이측량」을 「GNSS 수준측량」으로 고침 —— 제2편 제4장 제목과 이름을 맞춤 (2026-11-09)."
        if line not in r:
            n["reason"] = (r.rstrip() + NL + line) if r else "[변경 사유]" + NL + NL + "○ 개정 내용:" + NL + NL + line
        print("지었습니다 —— %s" % rel)
    io.open(SRC, "w", encoding="utf-8", newline=NL).write(json.dumps(d, ensure_ascii=False))
    print("적었습니다 —— data/draft2025.json")


if __name__ == "__main__":
    main()
