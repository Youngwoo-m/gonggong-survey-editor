# -*- coding: utf-8 -*-
r"""성과심사 개정안의 「지도 등」을 상위법 표기인 「지도등」으로 일괄 정비한다.

■ 왜 붙여 쓰는가

  국어 문법으로는 의존명사 '등(等)'을 띄어 쓰는 것이 원칙이다. 그러나
  「공간정보의 구축 및 관리 등에 관한 법률」 제15조제1항은

      "기본측량성과 및 기본측량기록을 사용하여 지도나 그 밖에 필요한
       간행물(이하 "지도등"이라 한다)"

  이라 하여 '지도등' 을 하나의 심사 대상을 특정하는 법률 전문 용어로 묶어
  두었다. 띄어 쓰면 '지도와 그 밖의 것' 이라는 일반 나열로 읽혀 규제 범위가
  흐려진다. 상위법이 붙여 쓰므로 하위 고시도 붙여 쓴다.

  「디지털기반 지도등 간행심사 제도개선 및 효율화 방안 연구」(2026. 01,
  공간정보품질관리원) 표 3-3 이 같은 정비를 제안하였다.

■ 무엇을 건드리고 무엇을 두는가

      title ㆍ body      고친다 — 개정안의 조문이다.
      wasBody           두어야 한다 — 신구대조표의 「현행」 칸이다.
      reason            무엇을 왜 고쳤는지 한 줄 적는다.
      현행 규정(reg29)  손대지 아니한다.

■ 상태

  글이 바뀌면 「유지」나 「이동」으로 둘 수 없다. 조와 별표에 한하여
  유지 → 수정, 이동 → 이동ㆍ수정 으로 올린다. 편ㆍ장의 제목은 조문이
  아니므로 상태를 건드리지 아니한다.

  python scripts\jidodeung.py            무엇을 고칠지 보여만 준다
  python scripts\jidodeung.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft_simsa.json")
NL = chr(10)

OLD = "지도 등"
NEW = "지도등"
WHY = "* 「지도 등」을 상위법의 표기인 「지도등」으로 고침."
WHY2 = ("* 「공간정보의 구축 및 관리 등에 관한 법률」 제15조제1항이 "
        "「지도등」을 하나의 심사 대상으로 묶어 정한 법률 용어이므로 그 표기를 따름.")
UP = {"유지": "수정", "이동": "이동·수정"}


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def add_why(node, lines):
    r = (node.get("reason") or "[변경 사유]").rstrip()
    add = NL.join(lines)
    head = "○ 개정 내용:"
    node["reason"] = (r + NL + add + NL) if head in r else \
        (r + NL * 2 + head + NL * 2 + add + NL)


def main():
    write = "--write" in sys.argv
    d = json.load(io.open(SRC, encoding="utf-8"))
    revs = [d] + list(d.get("next") or [])
    hits, bumped, kept = [], [], []

    for rev in revs:
        for x in walk(rev.get("tree") or []):
            n = 0
            for fld in ("title", "body"):
                s = x.get(fld) or ""
                c = s.count(OLD)
                if not c:
                    continue
                n += c
                if write:
                    x[fld] = s.replace(OLD, NEW)
            if not n:
                continue
            lv = x.get("level")
            st = x.get("status")
            hits.append((x, n, lv, st))
            # 조와 별표만 상태를 올린다 — 편ㆍ장 제목은 조문이 아니다
            isjo = lv == "조"
            if isjo and st in UP:
                bumped.append((x, st, UP[st]))
                if write:
                    x["status"] = UP[st]
            else:
                kept.append((x, st))
            if write:
                lines = [WHY]
                # 까닭은 용어를 정한 자리(제2조)에만 온전히 적는다.
                # 열여덟 마디에 같은 문장을 되풀이하면 사유 칸이 상투구가 된다.
                if str(x.get("no")) == "2" and lv == "조":
                    lines.append(WHY2)
                add_why(x, lines)

    print("고칠 자리 %d곳 · 마디 %d개" % (sum(h[1] for h in hits), len(hits)))
    print()
    print("%-4s %-24s %-5s %s" % ("조", "제목", "곳", "상태"))
    for x, n, lv, st in hits:
        up = UP.get(st) if lv == "조" and st in UP else None
        print("%-4s %-24s %-5d %s" % (
            str(x.get("no") or "별"), (x.get("title") or "")[:24], n,
            ("%s → %s" % (st, up)) if up else "%s (그대로)" % st))

    if not write:
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")
        return

    io.open(SRC, "w", encoding="utf-8", newline=NL).write(
        json.dumps(d, ensure_ascii=False))
    left = sum((x.get("title") or "").count(OLD) + (x.get("body") or "").count(OLD)
               for rev in revs for x in walk(rev.get("tree") or []))
    print()
    print("자료에 적었습니다 — 상태를 올린 조 %d개 · 남은 「지도 등」 %d곳"
          % (len(bumped), left))


if __name__ == "__main__":
    main()
