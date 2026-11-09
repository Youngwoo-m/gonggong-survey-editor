# -*- coding: utf-8 -*-
r"""작업규정 개정안 제90조(지형도의 정확도)의 개정 사유를 본문과 맞춘다.

■ 무엇이 어긋났나

  상태는 「유지」이고 「개정 내용」도 본문이 현행과 같다고 하는데, 「개정
  사유」는 「신뢰수준을 밝히는 방식으로 두 규정의 기준을 맞춤」이라 하여
  이 조를 고친 것처럼 읽혔다. 신뢰수준을 밝히는 일은 신설 제19조(정확도의
  표기)가 개정안 전체에 걸쳐 정하므로 이 조는 그대로 두는 것이 맞다.
  사유를 그에 맞게 고친다(2026-11-09, 사람이 정함).

  「현행의 문제」의 「법령 불일치 —— 상위 법령과 어긋나」는 연구가 매긴
  갈래를 옮긴 것인데, 이 조에서 상위 법령과 어긋나는 곳은 확인되지
  아니하였다. 확인한 것만 적는다.

  결과를 정해 두고 그대로 적으므로 여러 번 돌려도 같다.

  python scripts\fix90.py            보여만 준다
  python scripts\fix90.py --write    자료에 적는다
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "data", "draft2025.json")
NL = chr(10)

REASON = """[변경 사유]

○ 현행 규정:

* 제62조(지형도의 정확도) — 제3편 제1장.

○ 현행의 문제:

* 표의 수치가 표준편차임은 칸 제목으로만 알 수 있고 신뢰수준은 적혀 있지 아니함.
* 수치지형도 규정은 정확도를 신뢰구간으로 환산하여 판정하므로, 같은 성과를 두 규정이 다르게 판정할 수 있음.
* 연구는 이 조를 현행 제13조와 함께 「법령 불일치」로 분류하였으나, 이 조에서 상위 법령과 어긋나는 곳은 확인되지 아니함.

○ 관련 근거:

* 개정안 제19조(정확도의 표기) — 허용오차에 신뢰수준을 함께 밝히게 하고, 다른 규정과 기준이 다르면 신뢰수준을 밝힌 기준에 따르게 함.

○ 개정 사유:

* 신뢰수준을 밝히는 일은 개정안 제19조가 모든 허용오차에 걸쳐 정하므로, 이 조의 본문과 표는 현행대로 둠.
* 표의 수치를 신뢰구간 값으로 고쳐 적으면 성과의 합격 기준 자체가 바뀌므로 이번 개정에서는 하지 아니함.

○ 개정 내용:

* 앞에 조문을 새로 넣어 현행 제62조가 제90조가 됨.
* 본문은 현행과 같음."""


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    d = json.load(io.open(SRC, encoding="utf-8"))
    n = next(x for x in walk(d["tree"]) if x["id"] == "a70")
    if n.get("reason") == REASON:
        print("바꿀 것: 없음 (이미 적용됨)")
        return
    if n.get("status") != "유지" or n.get("no") != 90:
        print("!! 제90조의 상태나 번호가 예상과 다름 —— %s %s" % (n.get("no"), n.get("status")))
        sys.exit(1)
    print("바꿀 것: 제90조 reason")
    if "--write" not in sys.argv:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")
        return
    n["reason"] = REASON
    io.open(SRC, "w", encoding="utf-8", newline=NL).write(json.dumps(d, ensure_ascii=False))
    print("적었습니다 —— data/draft2025.json")


if __name__ == "__main__":
    main()
