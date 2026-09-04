# -*- coding: utf-8 -*-
r"""일본 준칙 번역의 기계번역 자국을 우리 작업규정 꼴로 다듬는다.

이 도구는 **층 표시와 굳은 낱말만** 손댄다. 문장을 다시 쓰지 아니한다.
조문별 재번역은 사람이 읽으며 할 일이다.

■ 층 표시 —— 근거는 우리 작업규정이다

  reg01 제24조(공공삼각점측량 관측)가 항ㆍ호ㆍ목을 다 지니고 있어 본으로
  삼을 수 있다. 세어 보면 우리 규정은 호를 `1.` 로 490줄, 항을 `①②③` 로
  436줄, 목을 `가.` 로 116줄 적는다. `1)` 과 `(1)` 은 한 줄도 없다.

      층    일본 준칙        기계번역        우리 작업규정
      항    ２ ３ ４         2 3 4          ② ③ ④
      호    一 二 三         일 이 삼        1. 2. 3.
      목    イ ロ ハ ニ      이 로 하 니     가. 나. 다. 라.

  기계번역이 층 표시를 **낱말로 옮겨 뒷말에 붙여 놓았다** —— 「일제품사양서는」.
  줄바꿈을 되살려 두었으므로(fixtransbr.py) 이제 줄머리에서 가려낼 수 있다.

  **첫 항에 ① 을 붙이지 아니한다.** 원문 첫 줄에는 표시가 없다. 주신 규칙 4
  「원문 포맷 100% 유지」 를 따라, 없는 것을 만들어 넣지 아니한다.

■ 굳은 낱말 —— 이것도 우리 작업규정에 있는 말이다

      次表      차표      → 다음 표      (reg01 제24조 「다음 표와 같이 한다」)
      読定      독정      → 읽음        (reg01 제24조 「1시준 1읽음」)

  둘 다 우리 규정이 실제로 쓰는 말이므로 지어낸 것이 아니다.

■ 지키는 것

  ㆍ 줄 수를 늘리거나 줄이지 아니한다.
  ㆍ 층 표시 말고는 한 글자도 건드리지 아니한다.
  ㆍ 원문 줄과 번역 줄의 수가 맞는 마디에서만 손댄다. 맞지 아니하면
    어느 줄이 어느 층인지 알 수 없으므로 건너뛴다.

  python scripts\jpstyle.py            무엇을 고칠지 보여만 준다
  python scripts\jpstyle.py --write    고친다
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

RE_IMG = re.compile(r'<img\s[^>]*>(?:</img>)?')
HANJA = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
         "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
KANA = {"イ": 1, "ロ": 2, "ハ": 3, "ニ": 4, "ホ": 5,
        "ヘ": 6, "ト": 7, "チ": 8, "リ": 9, "ヌ": 10}
KANA_KO = {"イ": "이", "ロ": "로", "ハ": "하", "ニ": "니", "ホ": "호",
           "ヘ": "헤", "ト": "토", "チ": "치", "リ": "리", "ヌ": "누"}
HANJA_KO = {"一": "일", "二": "이", "三": "삼", "四": "사", "五": "오",
            "六": "육", "七": "칠", "八": "팔", "九": "구", "十": "십"}
GANADA = "가나다라마바사아자차카타파하"
WON = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
FULL = {chr(0xFF10 + i): str(i) for i in range(10)}

# 사람이 정한 용어 대조표 (2026-09-04).
# 아홉은 기계번역이 이미 그 말을 쓰고 있어 손댈 것이 없고, 여기 넷만 다르다.
#   次表    차표        → 다음 표    (reg01 제24조 「다음 표와 같이 한다」)
#   読定    독정        → 읽음      (reg01 제24조 「1시준 1읽음」)
#   地図情報レベル 지도정보레벨 → 지도정보 수준
# 「레벨」 을 통째로 바꾸면 「입체모델레벨」 따위까지 걸리므로 낱말 전체로 바꾼다.
WORDS = [
    # 사람이 준 용어 대조표를 그대로 따른다 (2026-09-04, 두 번째 표).
    ("차표", "다음 표"),          # 次表  —— reg01 제24조 「다음 표와 같이 한다」
    ("지도정보레벨", "지도정보 수준"),  # 地図情報レベル
    ("전자기준점", "위성기준점"),      # 電子基準点 —— 우리 규정도 「위성기준점」 5곳
    ("정확도관리표", "정확도 관리표"),  # 精度管理表 —— 우리 규정도 띄어 씀 21곳
    ("수치사진", "디지털 사진"),      # 数値写真 —— 우리 규정에 둘 다 없어 권고를 따름
    ("독정", "읽음"),               # 読定
    # ── 권고와 우리 규정이 갈린 셋 —— 사람이 「우리 규정에 맞춘다」 로 정함
    #    読定        권고 판독        → 우리 reg01 제24조 「1시준 1읽음」 8곳
    #    製品仕様書   권고 제품 사양서  → 우리 개정안 17곳ㆍ성과심사 21곳이 붙여 씀
    #    品質評価     권고 품질 평가    → 우리 개정안 5곳이 붙여 씀
    #    참조규정과 우리 규정이 같은 것을 달리 부르면 맞대어 볼 수 없다.
]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def lines(s):
    return [x for x in str(s or "").split(NL) if RE_IMG.sub("", x).strip()]


def layer(line):
    """원문 줄머리 → (층, 차례, 번역에서 지울 글자). 없으면 None"""
    s = str(line or "").lstrip()
    if not s:
        return None
    if s[0] in HANJA and (len(s) == 1 or s[1] in " 　"):
        return "호", HANJA[s[0]], HANJA_KO[s[0]]
    if s[0] in KANA and (len(s) == 1 or s[1] in " 　"):
        return "목", KANA[s[0]], KANA_KO[s[0]]
    m = re.match(r"^([０-９]{1,2}|[0-9]{1,2})[\s　]", s)
    if m:
        k = int("".join(FULL.get(c, c) for c in m.group(1)))
        return "항", k, "".join(FULL.get(c, c) for c in m.group(1))
    return None


def restyle(kline, kind, no, drop):
    """번역 줄의 층 표시를 우리 꼴로 바꾼다. 못 바꾸면 None"""
    s = kline.lstrip()
    if not s.startswith(drop):
        return None                       # 예상한 글자가 없으면 손대지 아니한다
    rest = s[len(drop):].lstrip()
    if not rest:
        return None
    if kind == "항":
        head = WON[no - 1] if 1 <= no <= len(WON) else "%d " % no
        return head + " " + rest if head in WON else head + rest
    if kind == "호":
        return "%d. %s" % (no, rest)
    return "%s. %s" % (GANADA[no - 1] if no <= len(GANADA) else str(no), rest)


def main():
    write = "--write" in sys.argv
    doc = json.load(io.open(SRC, encoding="utf-8"))
    tot = collections.Counter()
    samples = []
    for n in walk(doc.get("tree") or []):
        b = (n.get("body") or "").strip()
        t = (n.get("transBody") or "").strip()
        if not b or not t:
            continue
        lb = [x for x in str(b).split(NL) if x.strip()]
        lt = [x for x in str(t).split(NL) if x.strip()]
        if len(lb) != len(lt):
            # 층 표시는 줄이 맞아야 가릴 수 있으나, 굳은 낱말은 줄과 상관없다.
            # 줄이 어긋난 마디에도 낱말은 고쳐야 한다.
            new = t
            for a_, c_ in WORDS:
                k = new.count(a_)
                if k:
                    new = new.replace(a_, c_)
                    tot["낱말 %s→%s" % (a_, c_)] += k
            if new != t:
                tot["고친 마디"] += 1
                if write:
                    n["transBody"] = new
            tot["줄 수가 달라 층 표시는 건너뜀"] += 1
            continue
        out, touched = [], 0
        for x, y in zip(lb, lt):
            lay = layer(x)
            if not lay:
                out.append(y)
                continue
            kind, no, drop = lay
            got = restyle(y, kind, no, drop)
            if got is None:
                out.append(y)
                tot["표시를 못 바꿈"] += 1
                continue
            out.append(got)
            touched += 1
            tot["%s 표시" % kind] += 1
        new = NL.join(out)
        for a, c in WORDS:
            k = new.count(a)
            if k:
                new = new.replace(a, c)
                tot["낱말 %s→%s" % (a, c)] += k
                touched += 1
        if new != t:
            tot["고친 마디"] += 1
            if len(samples) < 3:
                samples.append((n.get("no"), n.get("title"), lb, lt, out))
            if write:
                n["transBody"] = new

    print("%-22s %6s" % ("갈래", "수"))
    for k, v in tot.most_common():
        print("%-22s %6d" % (k, v))
    print()
    for no, ti, lb, lt, out in samples:
        print("── 제%s %s" % (no, ti))
        for x, y, z in zip(lb, lt, out):
            mark = "  " if y == z else "→ "
            print("   %s%-34s | %s" % (mark, x[:34], z[:56]))
        print()
    if write:
        io.open(SRC, "w", encoding="utf-8", newline=NL).write(
            json.dumps(doc, ensure_ascii=False))
        print("적었습니다 — data/loc11.json")
    else:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")


if __name__ == "__main__":
    main()
