# -*- coding: utf-8 -*-
r"""변경 사유에 적힌 「제 조 번호」를 지금 조 번호에 맞춘다.

■ 무엇이 어긋났나

  조마다 붙은 변경 사유에 그 조 스스로의 번호를 적은 줄이 있다.

      * 앞의 조문이 통합/삭제되고 새 조문이 들어옴에 따라 현행 제58조가 제65조가 됨.
      * 다만 앞의 조문이 통합/삭제되어 조 번호가 제25조에서 제38조로 바뀜.

  정의 체계 개편(할일.md ㊽)에서 조 206개의 번호가 밀렸으나 이 줄은 따라
  고치지 아니했다. 2026-10-10 에 재어 보니 작업규정 개정안에서 앞의 것은
  165곳 가운데 152곳, 뒤의 것은 27곳 가운데 25곳의 둘째 번호가 지금 조
  번호와 달랐다.

  앞의 것은 「개정 내용」 도막의 첫 줄이라 신구대조표 셋째 칸(why_of() 의
  [:6])으로 그대로 나간다.

■ 무엇을 보나 —— 조 스스로를 가리키는 문형 네 가지

      A  현행 제N조가 제M조가 됨
      B  조 번호(가|만) 제N조에서 제M조로 바뀜(바뀌고)
      C  조 번호는 제N조로 현행과 같음
      D  현행 제N조의 번호를 그대로 둘 수 없음

  A ㆍ B 의 M 은 마디의 지금 `no`(`branch` 가 있으면 「의K」)로 고친다.
  N 은 마디의 `legacyNo` 와 맞대어 보아 어긋나면 **고치지 아니하고** 알린다.
  고치고 나서 N 과 M 이 같아지는 줄도 문장이 거짓이 되므로 알리기만 한다.
  C ㆍ D 는 번호를 하나만 지니므로 맞대어 보고 알리기만 한다.

  조문 본문과 현행 자료(reg01.json)는 손대지 아니한다. 이미 맞는 줄은
  건드리지 아니하므로 두 번 돌려도 같다.

  python scripts\renumreason.py            보여만 준다
  python scripts\renumreason.py --write    고친다
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
DRAFTS = ["draft2025.json", "draft_simsa.json", "draft_uav.json"]

J = r"제(\d+)조(?:의(\d+))?"
PAIR = {
    "A": re.compile(r"(현행 )" + J + r"(가 )" + J + r"(가 됨)"),
    "B": re.compile(r"(조 번호(?:가|만) )" + J + r"(에서 )" + J + r"(로 바(?:뀜|뀌))"),
}
ONE = {
    "C": re.compile(r"조 번호는 " + J + r"로 현행과 같음"),
    "D": re.compile(r"현행 " + J + r"의 번호를 그대로 둘 수 없음"),
}


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def jo(no, br):
    return "제%d조" % no + ("의%d" % br if br else "")


def num(a, b):
    return (int(a), int(b or 0))


def legacy(n):
    """legacyNo 에 적힌 조 번호들 —— 「제18조」, 「18」, 「제3조의2」 꼴을 다 받는다"""
    s = str(n.get("legacyNo") or "")
    got = {num(a, b) for a, b in re.findall(J, s)}
    if not got:
        got = {num(a, b) for a, b in re.findall(r"^(\d+)(?:의(\d+))?$", s.strip())}
    return got


def fix(n, notes):
    """마디 하나의 사유를 고쳐 돌려준다 —— 고친 곳 수와 함께"""
    cur = num(n["no"], n.get("branch"))
    leg = legacy(n)
    where = "%s %s(%s)" % (n["id"], jo(*cur), n.get("title") or "")
    r = n.get("reason") or ""
    hits = 0

    def sub(m):
        nonlocal hits
        g = m.groups()
        N, M = num(g[1], g[2]), num(g[4], g[5])
        if M == cur:
            return m.group(0)
        if N not in leg:
            notes.append("%s —— N 이 legacyNo(%r)와 다름: 「%s」"
                         % (where, n.get("legacyNo"), m.group(0)))
            return m.group(0)
        if N == cur:
            notes.append("%s —— 고치면 N 과 M 이 같아짐: 「%s」" % (where, m.group(0)))
            return m.group(0)
        hits += 1
        return g[0] + jo(*N) + g[3] + jo(*cur) + g[6]

    for p in PAIR.values():
        r = p.sub(sub, r)
    for k, p in ONE.items():
        for m in p.finditer(r):
            N = num(*m.groups())
            if N not in leg:
                notes.append("%s —— %s 의 N 이 legacyNo(%r)와 다름: 「%s」"
                             % (where, k, n.get("legacyNo"), m.group(0)))
            if k == "C" and N != cur:
                notes.append("%s —— 현행과 같다 하나 지금 번호와 다름: 「%s」"
                             % (where, m.group(0)))
    return r, hits


def main():
    write = "--write" in sys.argv
    total = 0
    for f in DRAFTS:
        path = os.path.join(ROOT, "data", f)
        doc = json.load(io.open(path, encoding="utf-8"))
        notes, done = [], []
        for n in walk(doc["tree"]):
            if n.get("level") != "조" or not n.get("reason"):
                continue
            new, hits = fix(n, notes)
            if hits:
                done.append((n, new, hits))
        k = sum(h for _n, _r, h in done)
        total += k
        print("■ %s —— 고칠 곳 %d (조 %d개) ㆍ 알릴 것 %d" % (f, k, len(done), len(notes)))
        for n, new, _h in done[:5]:
            old = [x for x in n["reason"].split(NL) if x not in new.split(NL)]
            nw = [x for x in new.split(NL) if x not in n["reason"].split(NL)]
            for a, b in zip(old, nw):
                print("    %s  %s" % (n["id"], a.strip()))
                print("    %s  %s" % (" " * len(n["id"]), b.strip()))
        if len(done) > 5:
            print("    … 그 밖에 %d개 조" % (len(done) - 5))
        for x in notes:
            print("    ! " + x)
        if write and done:
            for n, new, _h in done:
                n["reason"] = new
            io.open(path, "w", encoding="utf-8", newline=NL).write(
                json.dumps(doc, ensure_ascii=False))
    if not write:
        print("표시만 한 것임. 고치려면 --write 를 붙일 것." if total else "고칠 것 없음.")
    else:
        print("고쳤습니다 —— %d곳" % total)


if __name__ == "__main__":
    main()
