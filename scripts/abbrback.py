# -*- coding: utf-8 -*-
r"""약칭 「(이하 "○○"라 한다)」 를 조문 본문의 제자리로 되돌린다.

■ 무엇을 되돌리는가

  개정안은 문장 안에 있던 약칭 괄호를 지우고 그 뜻을 총칙 정의 조문으로
  올렸다. 사람이 2026-09-04 에 그 방침을 뒤집었다 ——

      「(이하 "○○"…」 는 용어의 정의에 포함하지 아니하고,
      그 말이 처음 나오는 자리에서 쓴다.

  법령 입안 관례가 그러하다. 정의 조문은 여러 조가 함께 쓰는 말을 담는
  자리이고, 한 조문 안에서만 줄여 부르는 말은 그 자리에서 밝히는 것이다.

■ 어떻게 되돌리는가

  ㆍ 현행 조문에서 괄호를 찾아, 그 **앞말**(바로 앞 24자)을 실마리로
    개정 본문에서 같은 자리를 찾아 끼워 넣는다.
  ㆍ 앞말을 못 찾으면 손대지 아니하고 알린다. 어림으로 끼우지 아니한다.
  ㆍ 이미 괄호가 있으면 건너뛴다.
  ㆍ 총칙 정의 조문에서 「…에서 옮김」 으로 표시된 약칭 호를 뺀다.

  괄호의 꼴은 하나가 아니다 —— 「이라 한다」ㆍ「이라고 한다」ㆍ「한다.)」
  가 섞여 있어 모두 문다.

  python scripts\abbrback.py            무엇을 고칠지 보여만 준다
  python scripts\abbrback.py --write    고친다
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
CUR = os.path.join(ROOT, "data", "reg01.json")

RE_ABBR = re.compile(
    r'\(이하\s*[“"]([^”"]{1,40})[”"]\s*(?:이라고|라고|이라|라)\s*한다\.?\)')
MARK = "이 조에서는 괄호를 지움"
# 총칙 정의에서 뺄 호 —— 「…에서 옮김」 표시가 있는 약칭과, 그 짝으로 새로 둔 것
MOVED = re.compile(r"<현행 제\d+조에서 옮김>")
DROP_NEW = ("안전관리비", "시행령")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def revs(d):
    nx = d.get("next")
    return [d] + (nx if isinstance(nx, list) else ([nx] if isinstance(nx, dict) else []))


def put_back(cur_body, new_body):
    """현행에만 있는 약칭 괄호를 개정 본문의 제자리에 끼운다."""
    out, done, miss = new_body, [], []
    for m in RE_ABBR.finditer(cur_body):
        par = m.group(0)
        if par in out:
            continue
        # 바로 앞말을 실마리로 삼는다. 짧으면 그만큼만.
        for k in (24, 18, 12, 8):
            key = cur_body[max(0, m.start() - k):m.start()]
            if not key.strip():
                continue
            if out.count(key) == 1:
                i = out.index(key) + len(key)
                out = out[:i] + par + out[i:]
                done.append(par)
                break
        else:
            miss.append(par)
    return out, done, miss


def main():
    write = "--write" in sys.argv
    cur = json.load(io.open(CUR, encoding="utf-8"))
    dra = json.load(io.open(DRAFT, encoding="utf-8"))
    old = {}
    for n in walk(cur["tree"]):
        if n.get("level") == "조" and n.get("no"):
            old[int(n["no"])] = n

    n_body = n_par = 0
    miss_all = []
    for rev in revs(dra):
        for n in walk(rev.get("tree") or []):
            if n.get("level") != "조" or MARK not in (n.get("reason") or ""):
                continue
            m = re.match(r"^\s*제?\s*(\d+)\s*조", str(n.get("legacyNo") or ""))
            o = old.get(int(m.group(1))) if m else None
            if not o:
                miss_all.append("제%s조 %s —— 현행 조문이 없음(신설)"
                                % (n.get("no"), n.get("title")))
                continue
            got, done, miss = put_back(o.get("body") or "", n.get("body") or "")
            if done:
                n_body += 1
                n_par += len(done)
                print("  제%-4s %-26s 되돌림 %d: %s"
                      % (n.get("no"), (n.get("title") or "")[:26], len(done),
                         " / ".join(x[:34] for x in done)))
                if write:
                    n["body"] = got
            for x in miss:
                miss_all.append("제%s조 —— 앞말을 못 찾음: %s" % (n.get("no"), x[:40]))

    # 총칙 정의에서 약칭 호를 뺀다
    n_ho = 0
    for rev in revs(dra):
        for n in walk(rev.get("tree") or []):
            if n.get("level") != "조" or "정의" not in (n.get("title") or ""):
                continue
            keep, drop = [], []
            for ln in (n.get("body") or "").split(NL):
                mm = re.match(r'^\s*(\d+)\.\s*[“"]([^”"]{1,40})[”"]', ln)
                is_abbr = bool(mm) and (MOVED.search(ln) or mm.group(2).strip() in DROP_NEW)
                (drop if is_abbr else keep).append(ln)
            if drop:
                n_ho += len(drop)
                print("  제%s조 정의 —— 약칭 호 %d개를 뺌 (%s)"
                      % (n.get("no"), len(drop),
                         ", ".join(re.match(r'^\s*\d+\.\s*[“"]([^”"]+)', x).group(1)
                                   for x in drop[:6])))
                if write:
                    n["body"] = NL.join(keep)

    print()
    print("본문을 되돌린 조 %d개 · 괄호 %d곳 · 뺀 정의 호 %d개" % (n_body, n_par, n_ho))
    if miss_all:
        print()
        print("사람이 볼 것 %d건" % len(miss_all))
        for x in miss_all:
            print("   " + x)
    if write:
        io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
            json.dumps(dra, ensure_ascii=False))
        print()
        print("적었습니다 — data/draft2025.json")
    else:
        print()
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")


if __name__ == "__main__":
    main()
