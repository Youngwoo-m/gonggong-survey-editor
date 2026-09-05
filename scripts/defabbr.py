# -*- coding: utf-8 -*-
r"""약칭을 정의에서 빼어 처음 나오는 자리로 옮긴다 (작업규정 개정안).

■ 왜 그러한가

  약칭은 용어가 아니다. 정의 조문은 여러 조가 함께 쓰는 말의 뜻을 밝히는
  자리이고, 줄여 부르는 이름은 그 말이 처음 나오는 자리에서 밝히는 것이
  법령 입안 관례다.

      정의   "지하시설물(이하 "시설물"이라 한다)"란 …          ← 이렇게 두지 아니하고
      정의   "지하시설물"이란 …
      본문   … 지하시설물(이하 "시설물"이라 한다)의 …          ← 처음 나오는 자리에서 밝힌다

■ 어떻게 옮기는가

  ㆍ 정의 호에서 괄호만 뺀다. 뜻은 그대로 둔다.
  ㆍ 조문을 차례대로 훑어, 정의 조문이 아닌 자리에서 그 말이 처음 나오는
    곳에 괄호를 끼운다.
  ㆍ 줄인 이름이 그 자리보다 앞에서 이미 쓰이고 있으면 손대지 아니하고 알린다.
    어림으로 끼우지 아니한다.

  python scripts\defabbr.py            무엇을 고칠지 보여만 준다
  python scripts\defabbr.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
NL = chr(10)
WRITE = "--write" in sys.argv

HO = re.compile(r"^\s*(\d{1,2})\.\s")
RE_MARK = re.compile(r"<[^>]*>")
# "용어(이하 "약칭"이라 한다)"란   또는   "용어"(이하 "약칭"이라 한다)란
RE_DEF_ABBR = re.compile(
    r'"([^"]+?)\(이하\s*"([^"]+)"\s*(?:이라고|라고|이라|라)\s*한다\.?\)"'
    r'|"([^"]+?)"\s*\(이하\s*"([^"]+)"\s*(?:이라고|라고|이라|라)\s*한다\.?\)')


# 못박은 자리 —— 줄인 이름 : 그 이름을 밝힐 조의 제목
#
#   「시설물」은 제4편 제129조가 「다른 차량이나 시설물에 가려」 처럼 일반
#   명사로도 쓴다. 세는 것만으로는 그 자리를 고르게 되므로, 지하시설물측량
#   장에서 처음 줄여 쓰는 조를 못박는다.
PIN = {"시설물": "지하시설물도 작성시기"}


def walk(ns):
    for n in ns:
        yield n
        for m in walk(n.get("children") or []):
            yield m


def isdef(n):
    t = (n.get("title") or "").strip()
    return t == "정의" or t.endswith("의 정의")


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    tree = doc["tree"]
    nodes = [n for n in walk(tree)]

    # ① 정의 안의 약칭을 찾는다
    found = []
    for n in nodes:
        if not isdef(n):
            continue
        for ln in (n.get("body") or "").split(NL):
            if not HO.match(ln):
                continue
            m = RE_DEF_ABBR.search(RE_MARK.sub("", ln))
            if not m:
                continue
            term = m.group(1) or m.group(3)
            abbr = m.group(2) or m.group(4)
            found.append({"마디": n, "줄": ln, "용어": term, "약칭": abbr})

    if not found:
        print("정의 안에 약칭이 없습니다.")
        return

    # ② 그 말을 줄여 쓰는 첫 조를 찾는다
    #
    #    늘어놓기만 한 자리(제56조가 측량의 종류를 호로 벌여 적는 따위)에
    #    괄호를 끼우면 줄인 이름을 쓰지도 아니하는 조가 그것을 밝히게 된다.
    #    줄인 이름이 처음 쓰이는 조를 찾아, 그 안에서 자리를 정한다.
    # 조마다 어느 장에 있는지 적어 둔다
    jang_of = {}

    def mark(ns, ja=None):
        for n in ns:
            j = n if n.get("level") == "장" else ja
            jang_of[id(n)] = j
            mark(n.get("children") or [], j)

    mark(tree)

    order = [n for n in nodes if n.get("level") == "조"]
    plan = []
    for f in found:
        term, abbr = f["용어"], f["약칭"]
        pat = re.compile(r"(?<![가-힣])" + re.escape(abbr))
        # 줄인 이름을 참말로 쓰는 자리를 장마다 센다. 온말만 늘어놓은 자리
        # (제56조가 측량의 종류를 호로 벌여 적는 따위)는 밝힐 자리가 아니다.
        # 뒤에 조사가 붙으므로 뒷글자는 재지 아니한다 —— 「하천측량의」 도 잡아야 한다.
        uses = []
        for n in order:
            if isdef(n):
                continue
            c = len(pat.findall(RE_MARK.sub("", n.get("body") or "")))
            if c:
                uses.append((n, c))
        if not uses:
            plan.append((f, None, None))
            continue
        by_jang = {}
        for n, c in uses:
            j = jang_of.get(id(n))
            by_jang.setdefault(id(j), [j, 0, []])
            by_jang[id(j)][1] += c
            by_jang[id(j)][2].append(n)
        # 세 장 넘게 쓰이면 규정을 통틀어 쓰는 말이므로 맨 처음 자리에서 밝힌다.
        # 한두 장에 몰려 있으면 그 장에서만 줄여 부르는 것이므로 그 장에서 밝힌다.
        if abbr in PIN:
            # 못박은 자리 —— 기계가 고르면 어긋나는 것만 여기에 적는다
            at = next((n for n in order if n.get("title") == PIN[abbr]), None)
        elif len(by_jang) >= 3:
            at = uses[0][0]
        else:
            best = max(by_jang.values(), key=lambda v: v[1])
            at = best[2][0]
        plan.append((f, at, None))

    print("■ 정의에서 뺄 약칭 %d개" % len(found))
    for f, at, early in plan:
        where = ("제%s조(%s)" % (at.get("no"), at.get("title"))) if at else "찾지 못함"
        how = ""
        if at:
            how = "온말이 그 조에 있음" if f["용어"] in (at.get("body") or "")                 else "줄인 이름을 온말로 펴서 밝힘"
        print("   %-18s (이하 \"%s\")  정의 제%s조 → 줄여 쓰는 첫 조 %s  %s"
              % (f["용어"], f["약칭"], f["마디"].get("no"), where, how))

    if not WRITE:
        print("\n자료에 적으려면 --write 를 붙이십시오.")
        return

    done, skip = 0, 0
    for f, at, early in plan:
        term, abbr = f["용어"], f["약칭"]
        if not at:
            skip += 1
            continue
        # 정의에서 괄호를 뺀다
        n = f["마디"]
        lines = (n.get("body") or "").split(NL)
        for i, ln in enumerate(lines):
            if ln is f["줄"] or ln == f["줄"]:
                ln2 = re.sub(r'\(이하\s*"%s"\s*(?:이라고|라고|이라|라)\s*한다\.?\)'
                             % re.escape(abbr), "", ln)
                # "용어(…)"란 꼴이었으면 따옴표가 어그러지지 아니하게 다듬는다
                lines[i] = re.sub(r'"\s*"', '"', ln2)
                break
        n["body"] = NL.join(lines)
        # 줄여 쓰는 첫 조에서 밝힌다
        # 줄인 이름을 처음 쓴 자리를 온말로 펴고 그 자리에서 밝힌다.
        #
        # 온말이 나온 자리 뒤에 괄호를 끼우려 하면 「지하시설물도」 처럼 온말로
        # 시작하는 다른 말을 가르게 된다 —— 「지하시설물(이하 …)도」 가 된다.
        # 줄인 이름을 펴는 쪽은 그러한 일이 없다.
        b = at["body"]
        m = re.search(r"(?<![가-힣])" + re.escape(abbr), b)
        at["body"] = b[:m.start()] + term + '(이하 "%s"라 한다)' % abbr + b[m.end():]
        done += 1

    io.open(SRC, "w", encoding="utf-8", newline="").write(json.dumps(doc, ensure_ascii=False))
    print("\n옮긴 것 %d개 ㆍ 손대지 아니한 것 %d개" % (done, skip))


if __name__ == "__main__":
    main()
