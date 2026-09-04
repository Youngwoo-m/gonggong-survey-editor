# -*- coding: utf-8 -*-
r"""상태와 사유가 어긋난 아홉 조를 바로잡는다.

■ 어떻게 가렸는가

  「현행의 문제」에 「고칠 것이 없음」이라 적혔는데 상태는 「수정」인 조를
  모아, 현행 조문과 글자까지 맞대어 보았다.

  **공백을 지우고 견주면 안 된다.** 처음에 낱말 사이 공백까지 지우고
  견주었더니 아홉이 모두 「글자가 같다」고 나왔다. 그러나 성과심사 다섯은
  「지도 등」을 「지도등」으로 고친 것이어서, 바로 그 공백이 변경의 전부였다.
  견주는 잣대가 변경을 지워 버린 것이다. 줄 끝 공백만 다듬고 견주어야 한다.

■ 갈린 결과

  ㉠ 작업규정 넷 —— 글자까지 같음. 상태가 잘못이다.

        제30조(현행 제17조) ㆍ 제52조(제41조) ㆍ 제53조(제46조) ㆍ 제88조(제65조)

     넷 다 「개정 내용」에 「본문은 현행과 같음」이라 스스로 적고 있다.
     앞의 조문이 통합되고 신설이 끼어들어 번호만 밀린 것이므로 「이동」이다.
     「수정」으로 두면 개정문이 고치지도 아니한 조문을 고친다고 적는다.

  ㉡ 성과심사 다섯 —— 참말 고쳤다. 사유가 잘못이다.

        제3조 ㆍ 제13조 ㆍ 제36조 ㆍ 제38조 ㆍ 제39조

     「지도 등」을 상위법의 표기인 「지도등」으로 고쳤다(㉜). 그러므로
     「고칠 사유가 확인되지 않았음」은 사실이 아니다. 상태는 그대로 둔다.

  python scripts\fixstatus9.py            보여만 준다
  python scripts\fixstatus9.py --write    고친다
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

MOVE_ONLY = ("data/draft2025.json", [30, 52, 53, 88])
TERM_FIX = ("data/draft_simsa.json", [3, 13, 36, 38, 39])

PROB_MOVE = [
    "* 이 조문의 내용에는 고칠 것이 없음.",
    "* 앞의 조문이 통합되고 새 조문이 들어와 번호만 밀림.",
]
PROB_TERM = [
    "* 본문이 「지도 등」으로 띄어 적혀 있어, 상위법의 표기인 「지도등」과 어긋남.",
    "* 「공간정보의 구축 및 관리 등에 관한 법률」 제15조제1항은 「지도등」을 "
    "하나의 심사 대상으로 묶어 정하고 있음.",
    "* 같은 것을 법과 고시가 달리 불러, 무엇이 심사 대상인지 다투게 됨.",
]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def swap_prob(reason, lines):
    """「○ 현행의 문제:」 도막의 알맹이만 갈아 끼운다"""
    out, inside = [], False
    for ln in (reason or "").split(NL):
        m = re.match(r"^\s*○\s*([^:：]{2,20})\s*[:：]", ln)
        if m:
            if inside:
                inside = False
            if m.group(1).strip() == "현행의 문제":
                out.append("○ 현행의 문제:")
                out.append("")
                out.extend(lines)
                out.append("")
                inside = True
                continue
            out.append(ln)
            continue
        if inside:
            continue
        out.append(ln)
    return NL.join(out)


def main():
    write = "--write" in sys.argv
    for path, nos, prob, newst, what in (
            (MOVE_ONLY[0], MOVE_ONLY[1], PROB_MOVE, "이동", "상태를 이동으로"),
            (TERM_FIX[0], TERM_FIX[1], PROB_TERM, None, "사유만")):
        p = os.path.join(ROOT, path)
        doc = json.load(io.open(p, encoding="utf-8"))
        hit = []
        for n in walk(doc["tree"]):
            if n.get("level") != "조" or n.get("no") not in nos:
                continue
            before = n.get("status")
            n["_prob"] = swap_prob(n.get("reason") or "", prob)
            n["_st"] = newst or before
            hit.append((n, before))
        print("── %s  (%s)" % (os.path.basename(path), what))
        for n, before in hit:
            print("   제%-4s조 %-26s %s%s"
                  % (n["no"], (n.get("title") or "")[:26], before,
                     "" if n["_st"] == before else " → " + n["_st"]))
        for ln in prob:
            print("      %s" % ln)
        if write:
            for n, _b in hit:
                n["reason"] = n.pop("_prob")
                n["status"] = n.pop("_st")
            io.open(p, "w", encoding="utf-8", newline=NL).write(
                json.dumps(doc, ensure_ascii=False))
            print("   고쳤습니다 — %d개 조" % len(hit))
        else:
            for n, _b in hit:
                n.pop("_prob", None)
                n.pop("_st", None)
        print()
    if not write:
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")


if __name__ == "__main__":
    main()
