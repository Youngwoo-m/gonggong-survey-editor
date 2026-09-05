# -*- coding: utf-8 -*-
r"""일본 준칙 **원문**에서 사라진 줄바꿈을 되살린다 (loc11).

■ 무엇이 어긋났는가

  번역의 줄바꿈은 fixtransbr.py 로 되살렸으나, 원문 쪽에도 같은 흠이 있다.
  PDF 에서 글을 뜰 때 폭에 맞추어 꺾인 줄을 잇다가, **항ㆍ호ㆍ목이 새로
  시작하는 자리까지 함께 이어 버린 자리**가 있다.

      원문(준칙 제37조)  … 観測終了後に行うものとする。ル ＲＴＫ法は、固定局及び…
      있어야 할 꼴       … 観測終了後に行うものとする。
                         ル ＲＴＫ法は、固定局及び…

  글은 다 있고 줄바꿈만 없다. 그대로 두면 대역으로 나란히 놓았을 때 번역이
  더 많은 마디를 지녀 짝이 밀린다.

■ 어떻게 되살리는가

  ㆍ 일본어 문장은 「。」 로 끝난다. 「。」 바로 뒤에 항ㆍ호ㆍ목 표시가 오면
    그 앞에서 줄을 끊는다.
  ㆍ 표시는 이로하 차례의 가타카나(イ ロ ハ …), 한자 수(一 二 三 …),
    전각 괄호 수（１）（２）, 전각 아라비아 수 ２ ３ 이다.
  ㆍ 표시 뒤에 빈칸이 오는 것만 끊는다. 「ル」 가 낱말 안에 든 자리
    (「ツール」 따위)를 끊지 아니하려는 것이다.
  ㆍ 한 줄로 이어진 것을 끊기만 한다. 글자는 더하지도 빼지도 아니한다.

  python scripts\jpbreak.py            무엇을 끊을지 보여만 준다
  python scripts\jpbreak.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "loc11.json")
NL = chr(10)
WRITE = "--write" in sys.argv

IROHA = "イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス"
KANJI = "一二三四五六七八九十"
# 「。」 뒤에 오는 항ㆍ호ㆍ목 표시
RE_BREAK = re.compile(
    r"(。)(?=(?:[%s]\s|[%s]\s|（[０-９一二三四五六七八九十ⅰⅱⅲⅳⅴ]+）|[１-９][０-９]?\s))"
    % (IROHA, KANJI))


def walk(ns):
    for n in ns:
        yield n
        for m in walk(n.get("children") or []):
            yield m


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    hits = []
    for n in walk(doc["tree"]):
        b = n.get("body")
        if not b:
            continue
        out = []
        for ln in b.split(NL):
            cut = RE_BREAK.sub(r"\1" + NL, ln)
            if cut != ln:
                for piece in cut.split(NL)[1:]:
                    hits.append((n.get("no"), n.get("title"), piece[:46]))
            out.append(cut)
        nb = NL.join(out)
        if nb != b and WRITE:
            n["body"] = nb

    print("■ 끊을 자리 %d곳" % len(hits))
    for no, title, piece in hits[:40]:
        print("   제%-4s %-22s → %s" % (no, (title or "")[:20], piece))
    if len(hits) > 40:
        print("   … 그 밖에 %d곳" % (len(hits) - 40))

    if not WRITE:
        print("\n자료에 적으려면 --write 를 붙이십시오.")
        return
    io.open(SRC, "w", encoding="utf-8", newline="").write(
        json.dumps(doc, ensure_ascii=False))
    print("\n담았습니다.")


if __name__ == "__main__":
    main()
