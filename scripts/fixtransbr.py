# -*- coding: utf-8 -*-
r"""국외 규정 번역에서 사라진 줄바꿈을 되살린다.

■ 무엇이 어긋났는가

  글은 다 있는데 줄바꿈이 없어졌다.

      원문 2줄   この準則は…目的とする。
                 ２ この準則は、公共測量に適用する。
      번역 1줄   이 준칙은…목적으로 한다. 2 이 준칙은, 공공측량에 적용한다.

  대역으로 나란히 놓으면 항이 밀려 짝이 어긋난다. 이제 화면에서 고른 갈래
  그대로 내려받을 수 있으므로(ui/printdoc.js), 그대로 문서에 실려 나간다.

■ 일본 규정의 층 표시

  일본 준칙은 항ㆍ호ㆍ목을 우리와 다르게 적는다. 옮긴 것이 기계번역이라
  그 표를 **낱말로 옮겨 뒷말에 붙여 놓았다.**

      층    원문            번역
      항    ２ ３ ４        2 3 4
      호    一 二 三        일 이 삼   (「일제품사양서는」 처럼 붙기도 한다)
      목    イ ロ ハ ニ     이 로 하 니
      목2   （１）（２）     (1) (2)

  그러므로 번역에서 찾을 글자는 원문 글자가 아니라 **옮겨진 낱말**이다.
  `二` 와 `イ` 가 둘 다 「이」 가 되어 겹치므로, 원문 줄의 차례를 그대로
  따라가며 앞에서 찾은 자리 뒤에서만 찾는다.

■ 어떻게 되살리는가

  ㆍ 원문 둘째 줄부터 층 표시를 읽어 번역에서 찾을 글자로 바꾼다.
  ㆍ 앞에서 찾은 자리 뒤에서만 차례대로 찾는다. 앞에서부터 다시 찾으면
    본문에 섞인 숫자나 낱말에 걸린다.
  ㆍ 숫자는 앞뒤에 다른 숫자가 붙지 아니한 온전한 수여야 한다 ——
    그러지 아니하면 「쇼와 24년」 의 2 나 「법제49조」 의 4 에서 끊긴다.
    실제로 겪은 일이다.
  ㆍ 끊은 도막이 하나라도 비거나 수가 맞지 아니하면 그 마디는 건드리지
    아니한다.
  ㆍ **글자는 한 자도 늘리거나 줄이지 아니한다.** 끊어 붙인 것을 다시
    이어 붙이면 원래 번역과 같아야 한다. 다르면 그 마디를 되돌린다.

■ 손대지 아니하는 것

  원문 줄이 층 표시로 시작하지 아니하는 마디는 끊을 자리를 가릴 수 없으므로
  그대로 둔다. 사람이 보아야 한다.

  python scripts\fixtransbr.py            무엇을 고칠지 보여만 준다
  python scripts\fixtransbr.py --write    고친다
"""
import glob
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

RE_IMG = re.compile(r'<img\s[^>]*>(?:</img>)?')
HANJA = {"一": "일", "二": "이", "三": "삼", "四": "사", "五": "오",
         "六": "육", "七": "칠", "八": "팔", "九": "구", "十": "십"}
KANA = {"イ": "이", "ロ": "로", "ハ": "하", "ニ": "니", "ホ": "호",
        "ヘ": "헤", "ト": "토", "チ": "치", "リ": "리", "ヌ": "누"}
FULL = {chr(0xFF10 + i): str(i) for i in range(10)}


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def lines(s):
    """줄을 나눈다. 표ㆍ그림 개체만 있는 줄은 세지 아니한다."""
    out = []
    for x in str(s or "").split(NL):
        y = RE_IMG.sub("", x).strip()
        if y:
            out.append(y)
    return out


def half(s):
    return "".join(FULL.get(c, c) for c in s)


def key_of(line):
    """원문 줄머리의 층 표시 → 번역에서 찾을 글자. 없으면 None"""
    s = str(line or "").lstrip()
    if not s:
        return None
    if s[0] in HANJA and (len(s) == 1 or s[1] in " 　"):
        return HANJA[s[0]]
    if s[0] in KANA and (len(s) == 1 or s[1] in " 　"):
        return KANA[s[0]]
    m = re.match(r"^([（(][０-９0-9]{1,3}[)）])", s)
    if m:
        return half(m.group(1)).replace("（", "(").replace("）", ")")
    m = re.match(r"^([０-９]{1,2}|[0-9]{1,2})[\s　]", s)
    if m:
        return half(m.group(1))
    m = re.match(r"^([①-⑳])", s)
    if m:
        return m.group(1)
    return None


def find_mark(text, key, pos):
    """번역에서 층 표시가 참말로 서는 자리 —— (자리, 길이). 없으면 (-1, 0)"""
    tail = r"(?![0-9])" if key[0].isdigit() else ""
    pat = re.compile(r"(?:(?<=[.。\s　])|\A)" + re.escape(key) + tail)
    m = pat.search(text, pos)
    return (m.start(), len(key)) if m else (-1, 0)


def split_at(text, keys):
    pos, cuts = 0, []
    for k in keys:
        at, ln = find_mark(text, k, pos)
        if at <= pos:
            return None
        cuts.append(at)
        pos = at + ln
    out, prev = [], 0
    for i in cuts:
        out.append(text[prev:i].strip())
        prev = i
    out.append(text[prev:].strip())
    return None if any(not x for x in out) else out


def main():
    write = "--write" in sys.argv
    tot = collections.Counter()
    samples = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "loc*.json"))):
        rid = os.path.splitext(os.path.basename(p))[0]
        try:
            doc = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        hit = 0
        for n in walk(doc.get("tree") or []):
            b = (n.get("body") or "").strip()
            t = (n.get("transBody") or "").strip()
            if not b or not t:
                continue
            lb, lt = lines(b), lines(t)
            if len(lb) == len(lt):
                tot["이미 맞음"] += 1
                continue
            if len(lt) != 1 or len(lb) < 2:
                tot["번역이 한 줄이 아님"] += 1
                continue
            keys = [key_of(x) for x in lb[1:]]
            if any(k is None for k in keys):
                tot["층 표시를 못 읽음"] += 1
                continue
            got = split_at(t, keys)
            if not got or len(got) != len(lb):
                tot["차례대로 못 찾음"] += 1
                continue
            new = NL.join(got)
            if "".join(new.split()) != "".join(t.split()):
                tot["글자가 달라짐"] += 1
                continue
            tot["고침"] += 1
            hit += 1
            if len(samples) < 3:
                samples.append((rid, n.get("no"), n.get("title"), lb, got))
            if write:
                n["transBody"] = new
        if write and hit:
            io.open(p, "w", encoding="utf-8", newline=NL).write(
                json.dumps(doc, ensure_ascii=False))
            print("   %-7s %d마디를 고쳤습니다" % (rid, hit))

    print()
    print("%-18s %6s" % ("갈래", "마디"))
    for k, v in tot.most_common():
        print("%-18s %6d" % (k, v))
    print()
    for rid, no, ti, lb, got in samples:
        print("── %s 제%s %s" % (rid, no, ti))
        for x, y in zip(lb, got):
            print("   %-40s | %s" % (x[:40], y[:56]))
        print()
    if not write:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")


if __name__ == "__main__":
    main()
