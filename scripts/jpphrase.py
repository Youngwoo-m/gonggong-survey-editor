# -*- coding: utf-8 -*-
r"""일본 준칙 번역의 굳은 표현을 우리 규정 꼴로 일괄 정비한다.

문장을 다시 쓰지 아니한다. **되풀이되는 꼴만** 바꾼다. 조문별 재번역은
사람이 읽으며 할 일이고, 이 도구는 그 짐을 더는 것이다.

■ 무엇을 바꾸는가 —— 근거는 우리 작업규정(reg01)이다

  ㉠ 次のとおりとする
        차와 같이 로 한다      → 다음과 같이 한다
     「次」 를 「차」 로 둔 채 두었고, 「とする」 를 「로 한다」 로 덧붙였다.
     우리 규정은 「다음과 같이」 14곳, 「다음 표와 같이」 6곳으로 적는다.

  ㉡ 次の各号
        다음의 각 호 (174곳)   → 다음 각 호
     우리 규정은 「다음 각 호」 53곳, 「다음의 각 호」 1곳이다.

  ㉢ ことができる
        구하는 것이 할 수 있다  → 구할 수 있다
        실시할 것이 할 수 있다  → 실시할 수 있다
     「~하는 것이」 와 「~할 것이」 를 앞에 두고 「할 수 있다」 를 이었다.

  ㉣ 겹친 「하는」
        구하는 하는 것으로 한다 → 구하는 것으로 한다

  ㉤ 「には」
        영구표지에 는, 필요에… → 영구표지에는 필요에…
     「に」 와 「は」 를 따로 옮겨 「에 는」 이 되었다.

  ㉥ 「~다」 뒤에 이름씨가 붙은 것
        실시한다경우 → 실시하는 경우 ㆍ 할 수 없다경우 → 할 수 없는 경우
        확인할 수 있다것 → 확인할 수 있는 것

  ㉦ 뜻이 깨진 낱말
        노하는 → 힘쓰는 ㆍ 피노하여야 → 피하여야 ㆍ 그림것에 따라 → 도모함으로써
     努める를 「노」, 避ける를 「피노」, 図る를 「그림」 으로 옮긴 자리이다.

■ 손대지 아니하는 것

  ㆍ 「~로 있는」(44곳) —— 「측량성과로 있는」 은 「측량성과인」 이 맞으나
    「수정가능으로 있는」 은 「수정할 수 있는」 이라 한 규칙으로 묶이지 아니한다.
  ㆍ 「그림」(521곳) —— 「平均図」를 「평균그림」 으로 옮긴 것이다. 우리 규정은
    「관측도」 5곳ㆍ「선점도」 14곳처럼 「도」 로 적으나, 「출력그림」ㆍ「단면그림」
    처럼 일본 고유 서식 이름도 섞여 있어 통째로 바꿀 수 없다.
  둘 다 조문별 재번역에서 사람이 볼 일이다.

  python scripts\jpphrase.py            무엇을 고칠지 보여만 준다
  python scripts\jpphrase.py --write    고친다
"""
import io
import json
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
SRC = os.path.join(ROOT, "data", "loc11.json")

# 차례가 중요하다. 「차와 같이」 를 먼저 고쳐야 「와 같이 로 한다」 가 맞물린다.
RULES = [
    ("차와 같이", "다음과 같이"),
    ("와 같이 로 한다", "와 같이 한다"),
    ("다음의 각 호", "다음 각 호"),
    ("하는 것이 할 수 있다", "할 수 있다"),
    ("할 것이 할 수 있다", "할 수 있다"),
    ("하는 하는", "하는"),
    # 「に」 와 「は」 를 따로 옮겨 「에 는」 이 되었다. 붙이기만 하고
    # 문장부호는 건드리지 아니한다 —— 콤마를 지우면 글이 달라진다.
    ("에 는,", "에는,"),
    ("에 는 ", "에는 "),
    ("한다경우", "하는 경우"),
    ("없다경우", "없는 경우"),
    ("있다경우", "있는 경우"),
    ("한다것", "하는 것"),
    ("없다것", "없는 것"),
    ("있다것", "있는 것"),
    ("한다때", "하는 때"),
    ("노하는", "힘쓰는"),
    ("피노하여야", "피하여야"),
    ("그림것에 따라", "도모함으로써"),

    # ── 図 → 도  (2026-09-04 사람이 「평균도ㆍ관측도 갈래만」 으로 정함)
    #
    # 기계번역이 図 를 「그림」 으로 옮겼다. 원문에 「絵」 는 한 자도 없고
    # 「図」 만 1,032곳이므로, 번역의 「그림」 520곳은 모두 図 이다.
    # 우리 규정도 도형 6곳ㆍ도화 1곳ㆍ기본도 7곳ㆍ관측도 5곳ㆍ선점도 14곳
    # ㆍ단면도 21곳ㆍ주제도 3곳으로 「도」 를 쓴다.
    #
    # 基図 는 「기도」 가 되면 뜻이 통하지 아니하므로 먼저 「기본도」 로 바꾼다
    # (사람이 정함). 우리 규정도 「기본도」 7곳을 쓴다.
    ("기그림", "기본도"),
    ("그림", "도"),
]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    doc = json.load(io.open(SRC, encoding="utf-8"))
    tot = collections.Counter()
    samples = []
    hit = 0
    for n in walk(doc.get("tree") or []):
        t = (n.get("transBody") or "")
        if not t.strip():
            continue
        new = t
        for a, b in RULES:
            k = new.count(a)
            if k:
                new = new.replace(a, b)
                tot["%s → %s" % (a, b)] += k
        if new == t:
            continue
        hit += 1
        if len(samples) < 4:
            samples.append((n.get("no"), n.get("title"), t, new))
        if write:
            n["transBody"] = new

    print("고친 마디 %d개" % hit)
    print()
    print("%-30s %6s" % ("바꾼 꼴", "곳"))
    for k, v in tot.most_common():
        print("%-30s %6d" % (k, v))
    print()
    for no, ti, was, now in samples:
        print("── 제%s %s" % (no, ti))
        for x, y in zip([l for l in was.split(NL) if l.strip()],
                        [l for l in now.split(NL) if l.strip()]):
            if x != y:
                print("   전 %s" % x[:80])
                print("   후 %s" % y[:80])
        print()
    if write:
        io.open(SRC, "w", encoding="utf-8", newline=NL).write(
            json.dumps(doc, ensure_ascii=False))
        print("적었습니다 — data/loc11.json")
    else:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")


if __name__ == "__main__":
    main()
