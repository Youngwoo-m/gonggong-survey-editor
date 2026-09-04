# -*- coding: utf-8 -*-
r"""<약칭에서 옮김> 에 어디에서 옮겼는지를 적어 넣는다.

■ 왜

  개정안 제2조(정의)에는 현행 조문 곳곳에 흩어져 있던 약칭을 거두어 모았다.
  그 자리마다 <약칭에서 옮김> 이라고만 적혀 있어, 어느 조문에서 온 것인지
  알 수 없었다.

      25. "시행자"란 공공측량시행자를 줄여 이르는 말이다. <약칭에서 옮김>

  현행 규정에서 그 약칭을 정한 조문을 찾아 함께 적는다. 그러면 화면에서
  눌러 현행 조문으로 갈 수 있다(objects.js 의 linkMoved).

      25. "시행자"란 … <현행 제5조에서 옮김>

■ 약칭을 정하는 꼴이 여러 가지다

      (이하 "시행자"라 한다)        (이하 "편심점"이라 한다.)
      (이하 "관측위치 확인자료"라고 한다)

  마침표가 붙기도 하고 '라고' 가 되기도 한다. 셋을 모두 문다.

  python scripts\movedfrom.py            무엇이 적히는지 보여만 준다
  python scripts\movedfrom.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

MARK = "<약칭에서 옮김>"
# 약칭을 정하는 자리 — '이하 "…"(이)라(고) 한다' 에 마침표가 붙기도 한다
RE_ALIAS = re.compile(
    r'\(\s*이하\s*[“"]([^”"]+)[”"]\s*(?:이)?라(?:고)?\s*한다\.?\s*\)')
# 정의 줄에서 정하는 말 — 25. "시행자"란 …
RE_TERM = re.compile(r'[“"]([^”"]+)[”"]')


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def alias_book(path):
    """현행 규정 → ({약칭: (조 번호, 조 제목)}, 현행 글 전체)

    글 전체도 함께 돌려준다. 약칭으로는 못 찾았을 때 그 말이 현행에 아예
    없는지(신설인지) 가리려는 것이다."""
    d = json.load(io.open(path, encoding="utf-8"))
    out, all_text = {}, []
    for x in walk(d.get("tree") or []):
        if x.get("level") != "조":
            continue
        b = x.get("body") or ""
        all_text.append(b)
        for m in RE_ALIAS.finditer(b):
            out.setdefault(m.group(1), (x.get("no"), x.get("title") or ""))
    return out, "\n".join(all_text)


# (개정안 파일, 그 규정의 현행 파일)
PAIRS = [("draft2025.json", "reg01.json"),
         ("draft_simsa.json", "reg29.json"),
         ("draft_uav.json", "reg12.json")]


def main():
    write = "--write" in sys.argv
    hit = miss = newmark = 0
    for dj, rj in PAIRS:
        dp = os.path.join(DATA, dj)
        rp = os.path.join(DATA, rj)
        if not (os.path.exists(dp) and os.path.exists(rp)):
            continue
        book, curtext = alias_book(rp)
        draft = json.load(io.open(dp, encoding="utf-8"))
        shown = False
        for rev in [draft] + list(draft.get("next") or []):
            for x in walk(rev.get("tree") or []):
                b = x.get("body") or ""
                if MARK not in b:
                    continue
                out = []
                for ln in b.split("\n"):
                    if MARK not in ln:
                        out.append(ln)
                        continue
                    m = RE_TERM.search(ln)
                    term = m.group(1) if m else ""
                    got = book.get(term)
                    if got:
                        hit += 1
                        no, ti = got
                        ln = ln.replace(MARK, "<현행 제%s조에서 옮김>" % no)
                        if not shown:
                            print("  %-18s ← 현행 제%s조(%s)" % (term, no, ti[:24]))
                    elif term and term not in curtext:
                        # 그 말이 현행에 아예 없다 — 옮겨 온 것이 아니라
                        # 새로 둔 정의다. 표시 자체가 잘못이므로 바로잡는다.
                        newmark += 1
                        ln = ln.replace(MARK, "<신설>")
                        print("  %-18s ← 현행에 없음, 신설로 바로잡음" % term)
                    else:
                        miss += 1
                        print("  %-18s ← 약칭 꼴이 아님 (그대로 둠)" % term)
                    out.append(ln)
                x["body"] = "\n".join(out)
        if write:
            io.open(dp, "w", encoding="utf-8", newline="\n").write(
                json.dumps(draft, ensure_ascii=False))
    print("\n출처를 적은 것 %d · 신설로 바로잡은 것 %d · 그대로 둔 것 %d"
          % (hit, newmark, miss))
    if not write:
        print("보여만 준 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
