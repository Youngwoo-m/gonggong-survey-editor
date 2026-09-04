# -*- coding: utf-8 -*-
r"""따옴표 안에서 끊긴 덩이가 남은 두 자리를 고친다 —— 제2장과 별표 17.

fixreason17.py 가 제17조를 고쳤으나, 같은 덩이가 두 곳에 더 붙어 있었다.
이번에는 「현행의 문제」가 아니라 「관련 근거」 안이다.

    ○ 관련 근거:
    * 연구 검토 결과 서술 방식 불일치 — • 제11조: "성과 등을 제출함.
    * " • 제31조: "성과 등은…정리함.
    * " • 제43조: "성과 등은…정리함.
    * " "성과", "기록", "메타데이터", "성과 등" 혼재.

「마침표가 나오면 줄을 바꾼다」는 문체 규칙이 인용부호 안의 마침표까지
끊은 탓이다. 따옴표만 남은 줄이 개정사유서에 그대로 나간다.

넉 줄을 한 줄로 갈음한다. 셈은 reg01 에서 직접 세었다.

    성과 등  여덟 조 ㆍ 기록  일곱 조 ㆍ 메타데이터  네 조

별표 17(종전 별표 45)은 이참에 「없음 — 신설 조문」ㆍ「이 서식 자체에는
지적된 것이 없음」도 함께 고친다. 이 별표는 현행 조문 열 개에 흩어져
있던 유형별 열거를 모은 것이므로 없던 것이 아니다.

  python scripts\fixreason17b.py            보여만 준다
  python scripts\fixreason17b.py --write    고친다
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
DRAFT = os.path.join(ROOT, "data", "draft2025.json")
SRC = [31, 43, 59, 74, 93, 109, 119, 130, 167, 191]

MARK = '"성과", "기록", "메타데이터", "성과 등" 혼재'
BROKEN_HEAD = "* 연구 검토 결과 서술 방식 불일치 —"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    cur = json.load(io.open(os.path.join(ROOT, "data", "reg01.json"),
                            encoding="utf-8"))
    bodies = {}
    for n in walk(cur["tree"]):
        if n.get("level") == "조" and n.get("no") in SRC:
            bodies[n["no"]] = n.get("body") or ""
    n_deung = sum(1 for b in bodies.values() if "성과 등" in b)
    n_rec = sum(1 for b in bodies.values() if "기록" in b)
    n_meta = sum(1 for b in bodies.values() if "메타데이터" in b)
    ONE = ("* 성과를 부르는 이름이 갈려 있음 — 「성과 등」 %d조, 「기록」 %d조, "
           "「메타데이터」 %d조에서 쓰나 무엇을 가리키는지 정한 곳이 없음."
           % (n_deung, n_rec, n_meta))

    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    hit = []
    for n in walk(doc["tree"]):
        r = n.get("reason") or ""
        if MARK not in r:
            continue
        out, drop = [], False
        for ln in r.split(NL):
            s = ln.strip()
            if s.startswith(BROKEN_HEAD):
                out.append(ONE)          # 넉 줄을 한 줄로
                drop = True
                continue
            if drop:
                if s.startswith('* "'):
                    continue             # 따옴표만 남은 줄
                drop = False
            out.append(ln)
        r2 = NL.join(out)

        # 별표 17 —— 「없던 것」 이라 적힌 세 자리도 함께
        if n.get("legacyNo") == "별표 45":
            r2 = r2.replace(
                "* 없음 — 신설 조문.",
                "* 현행 제%s조 열 곳의 본문에 유형별 열거로 들어 있었음."
                % "ㆍ".join(str(x) for x in SRC), 1)
            r2 = r2.replace(
                "* 이 서식 자체에는 지적된 것이 없음.",
                "* 낼 것의 유형별 열거가 조문 열 곳에 흩어져 있어, 편마다 "
                "다른 것을 요구하게 됨.", 1)
            r2 = r2.replace(
                "* 현행 규정에 없던 서식을 별표 17으로 새로 정함.",
                "* 조문 열 개에 흩어져 있던 유형별 열거를 별표 17로 모은다.", 1)
        n["_new"] = r2
        hit.append(n)

    print("고칠 마디 %d개" % len(hit))
    for n in hit:
        print()
        print("── %s 제%s %s" % (n.get("level"), n.get("no"), n.get("title")))
        old = set((n.get("reason") or "").split(NL))
        for ln in n["_new"].split(NL):
            if ln.strip() and ln not in old:
                print("     + %s" % ln.strip())
    if not write:
        print()
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")
        return
    for n in hit:
        n["reason"] = n.pop("_new")
    io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("고쳤습니다 — %d개 마디" % len(hit))


if __name__ == "__main__":
    main()
