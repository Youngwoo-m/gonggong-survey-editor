# -*- coding: utf-8 -*-
r"""일본 준칙 조문별 재번역을 위한 일감 꺼내기ㆍ넣기 도구.

기계번역을 사람이 조문별로 다시 옮기는 일이 669개 조에 걸쳐 있다. 한 번에
다 볼 수 없으므로 글자 수로 끊어 꺼내고, 옮긴 것을 도로 넣는다.

■ 꺼내기

    python scripts\jpbatch.py out 4000

  아직 옮기지 아니한 조를 앞에서부터 원문 4,000자만큼 꺼내 보여 준다.
  **기계번역은 함께 보이지 아니한다.** 다시 옮길 것이므로 볼 까닭이 없고,
  잘못된 말에 눈이 끌리면 오히려 해롭다.

■ 넣기

    python scripts\jpbatch.py in 파일.json

  {"조번호": "옮긴 글", …} 꼴의 json 을 읽어 transBody 에 넣고, 원문과 줄
  수가 맞는지 바로 센다. 넣기 전에 뒷간(scratchpad)에 판을 하나 떠 둔다.

■ 어디까지 왔는가

    python scripts\jpbatch.py stat

■ 무엇을 「마친 것」 으로 보는가

  transDone 에 조 번호를 적어 둔다. 기계번역과 사람이 옮긴 것을 글만 보고
  가릴 수 없기 때문이다. 넣기를 할 때마다 저절로 쌓인다.
"""
import io
import json
import os
import sys
import shutil
import datetime

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
SRC = os.path.join(ROOT, "data", "loc11.json")
BAK = os.environ.get("SCRATCH") or os.path.join(ROOT, ".bak")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def load():
    return json.load(io.open(SRC, encoding="utf-8"))


def save(d):
    io.open(SRC, "w", encoding="utf-8", newline=NL).write(
        json.dumps(d, ensure_ascii=False))


def lines(s):
    return [x for x in str(s or "").split(NL) if x.strip()]


def jo(d):
    """본문이 있는 조 —— (번호, 마디) 차례대로"""
    for n in walk(d.get("tree") or []):
        if n.get("level") == "조" and (n.get("body") or "").strip():
            yield n.get("no"), n


def done_set(d):
    return set(d.get("transDone") or [])


def cmd_out(budget):
    d = load()
    done = done_set(d)
    got = 0
    for no, n in jo(d):
        if no in done:
            continue
        b = n["body"]
        if got and got + len(b) > budget:
            break
        got += len(b)
        print("=== 제%s조 %s" % (no, n.get("title") or ""))
        for ln in lines(b):
            print("  " + ln)
        print()
    print("---- 원문 %d자" % got)


def cmd_in(path):
    ko = json.load(io.open(path, encoding="utf-8"))
    ko = {int(k): v for k, v in ko.items() if str(k).isdigit()}
    if not ko:
        print("넣을 것이 없습니다."); return
    d = load()
    os.makedirs(BAK, exist_ok=True)
    shutil.copy(SRC, os.path.join(
        BAK, "loc11.%s.json" % datetime.datetime.now().strftime("%H%M%S")))
    hit, bad = 0, []
    for no, n in jo(d):
        if no in ko:
            n["transBody"] = ko[no]
            hit += 1
            lb, lt = len(lines(n["body"])), len(lines(ko[no]))
            if lb != lt:
                bad.append("제%s조 %d/%d" % (no, lb, lt))
    d["transDone"] = sorted(set(d.get("transDone") or []) | set(ko))
    save(d)
    print("넣은 조 %d개 (준 것 %d개)" % (hit, len(ko)))
    print("줄 어긋남: %s" % (", ".join(bad) if bad else "없음"))
    cmd_stat(d)


def cmd_stat(d=None):
    d = d or load()
    done = done_set(d)
    tot = left = ch = 0
    for no, n in jo(d):
        tot += 1
        if no not in done:
            left += 1
            ch += len(n["body"])
    print("조 %d개 · 마친 것 %d · 남은 것 %d · 남은 원문 %d자"
          % (tot, tot - left, left, ch))


if __name__ == "__main__":
    a = sys.argv[1:] or ["stat"]
    if a[0] == "out":
        cmd_out(int(a[1]) if len(a) > 1 else 4000)
    elif a[0] == "in":
        cmd_in(a[1])
    else:
        cmd_stat()
