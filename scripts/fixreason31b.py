# -*- coding: utf-8 -*-
r"""제31조부터 제34조까지의 「관련 근거」와 「개정 내용」을 통합에 맞게 고친다.

fixreason31.py 가 「현행 규정」ㆍ「현행의 문제」ㆍ「개정 사유」를 고쳤으나,
남은 두 대목이 아직 신설로 적혀 있었다.

    ○ 관련 근거:  규정 체계 정비 — 현행 규정에 없던 사항을 새로 정함.
    ○ 개정 내용:  현행 규정에 없던 사항을 제31조로 새로 정한다 — …

네 조는 모두 현행 조문 둘을 합쳐 만든 것이다. 없던 사항을 새로 정한 것이
아니므로 그대로 두면 같은 조문 안에서 「현행 제20조와 제34조를 통합함」과
「현행 규정에 없던 사항」이 맞선다.

  python scripts\fixreason31b.py            보여만 준다
  python scripts\fixreason31b.py --write    고친다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
DRAFT = os.path.join(ROOT, "data", "draft2025.json")
MERGED = {31: (20, 34), 32: (21, 35), 33: (22, 36), 34: (23, 37)}
# 「새로 정한다 — …」 과 「새로 정함.」 두 꼴이 섞여 있다
RE_NEW = re.compile(r"^\*\s*현행 규정에 없던 사항을 제(\d+)조로 새로 "
                    r"(?:정한다|정함)(.*)$")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    hit = []
    for n in walk(doc["tree"]):
        if n.get("level") != "조" or n.get("no") not in MERGED:
            continue
        if n.get("origin") != "통합":
            continue
        a, b = MERGED[n["no"]]
        out, changed = [], []
        for ln in (n.get("reason") or "").split(NL):
            s = ln.strip()
            if s == "* 규정 체계 정비 — 현행 규정에 없던 사항을 새로 정함.":
                ln = ("* 규정 체계 정비 — 같은 절차를 정한 현행 제%d조와 "
                      "제%d조를 하나로 모음." % (a, b))
                changed.append(ln)
            else:
                m = RE_NEW.match(s)
                if m:
                    tail = m.group(2)
                    verb = "통합한다" if tail.strip() else "통합함"
                    ln = ("* 현행 제%d조와 제%d조를 제%s조로 %s%s"
                          % (a, b, m.group(1), verb, tail or "."))
                    changed.append(ln)
            out.append(ln)
        if changed:
            n["_new"] = NL.join(out)
            hit.append((n, changed))

    print("고칠 조 %d개" % len(hit))
    for n, changed in hit:
        print()
        print("── 제%d조 %s" % (n["no"], n.get("title")))
        for c in changed:
            print("     %s" % c)
    if not write:
        print()
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")
        return
    for n, _c in hit:
        n["reason"] = n.pop("_new")
    io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("고쳤습니다 — %d개 조" % len(hit))


if __name__ == "__main__":
    main()
