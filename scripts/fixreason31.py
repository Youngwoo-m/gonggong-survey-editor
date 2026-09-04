# -*- coding: utf-8 -*-
r"""제31조부터 제34조까지의 「현행의 문제」와 「개정 사유」를 사실대로 고친다.

■ 무엇이 틀렸는가

  네 조 모두 「현행의 문제」가 이렇게 적혀 있었다.

      연구 검토 결과 중복/누락/불명확 — 두 조항 모두 "도화작업/편집 과정에서의
      기준"을 규정하며 내용이 상당 부분 중복.

  제31조는 공공기준점측량의 공정별 작업구분, 제32조는 작업수행계획,
  제33조는 선점, 제34조는 표지의 설치이다. **도화작업도 편집도 아니다.**
  연구보고서의 다른 항목 문구가 통째로 잘못 옮겨 붙은 것이다.

  「개정 사유」의 앞 두 줄도 같은 잘못을 지녔다 —— 「두 조문이 같은 편집
  기준을 겹쳐 정하고 있어」.

  「현행 규정」도 「없음 — 신설 조문」이라 적혀 있으나, 네 조 모두 현행
  조문 둘을 합쳐 만든 것이다(㊵ 의 통합ㆍ신설).

■ 무엇으로 갈음하는가

  자료에서 잰 것만 적는다. 현행 조문의 번호와 제목과 분량은 reg01 에서
  바로 읽을 수 있고, 무엇을 합쳤는지는 그 조의 「개정 사유」 끝줄이
  이미 밝히고 있다.

      제31조  현행 제20조(122자) + 제34조(121자)
      제32조  현행 제21조( 76자) + 제35조( 74자)
      제33조  현행 제22조(182자) + 제36조(172자)
      제34조  현행 제23조(235자) + 제37조(232자)

  「연구가 매긴 개정 시급성은 '매우 높음' 임」도 함께 뗀다. 잘못 옮겨 온
  덩이의 일부이므로 이 네 조에 대한 판정이라고 볼 근거가 없다.

  python scripts\fixreason31.py            무엇을 고칠지 보여만 준다
  python scripts\fixreason31.py --write    고친다
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

# 개정안 조 번호 → 합친 현행 조 번호 둘
MERGED = {31: (20, 34), 32: (21, 35), 33: (22, 36), 34: (23, 37)}

BAD_PROB = "연구 검토 결과 중복/누락/불명확"
BAD_URGENT = "연구가 매긴 개정 시급성"
BAD_WHY = ("두 조문이 같은 편집 기준을 겹쳐 정하고 있어",
           "공통 기준을 한 곳에 두고 각 편이 이를 준용함")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def sections(reason):
    """「○ 이름:」 으로 갈린 도막을 차례를 지켜 돌려준다"""
    out, cur = [], None
    for ln in (reason or "").split(NL):
        m = re.match(r"^\s*○\s*([^:：]{2,20})\s*[:：]\s*(.*)$", ln)
        if m:
            cur = [m.group(1).strip(), []]
            out.append(cur)
            if m.group(2).strip():
                cur[1].append(m.group(2).strip())
        elif cur is not None:
            cur[1].append(ln)
        else:
            out.append([None, [ln]])
    return out


def render(secs):
    L = []
    for name, lines in secs:
        if name is None:
            L.extend(lines)
            continue
        L.append("○ %s:" % name)
        L.extend(lines)
    return NL.join(L)


def main():
    write = "--write" in sys.argv
    cur = json.load(io.open(CUR, encoding="utf-8"))
    old = {}
    for n in walk(cur["tree"]):
        if n.get("level") == "조" and n.get("no"):
            old[int(n["no"])] = (n.get("title") or "", len(n.get("body") or ""))

    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    done = []
    for n in walk(doc["tree"]):
        if n.get("level") != "조" or n.get("no") not in MERGED:
            continue
        if BAD_PROB not in (n.get("reason") or ""):
            continue
        a, b = MERGED[n["no"]]
        (ta, la), (tb, lb) = old[a], old[b]
        secs = sections(n["reason"])
        for s in secs:
            if s[0] == "현행 규정":
                s[1] = ["",
                        "* 현행 제%d조(%s)와 제%d조(%s) 둘로 나뉘어 있었음."
                        % (a, ta, b, tb),
                        ""]
            elif s[0] == "현행의 문제":
                s[1] = ["",
                        "* 공공삼각점측량과 공공수준점측량에 같은 절차를 정한 "
                        "조문이 장마다 따로 있음.",
                        "* 분량이 %d자와 %d자로 거의 같아 내용이 사실상 같음."
                        % (la, lb),
                        "* 한쪽만 고치면 두 조문이 서로 다른 것을 요구하게 되어, "
                        "어느 것을 따라야 하는지 다투게 됨.",
                        ""]
            elif s[0] == "개정 사유":
                keep = [x for x in s[1]
                        if not any(w in x for w in BAD_WHY)]
                s[1] = ["",
                        "* 같은 절차를 정한 두 조문을 한 곳에 모아, 고칠 때 "
                        "한 자리만 보면 되게 함."] + [x for x in keep if x.strip()] + [""]
        n["_new"] = render(secs)
        done.append(n)

    print("고칠 조 %d개" % len(done))
    for n in done:
        a, b = MERGED[n["no"]]
        print()
        print("── 제%d조 %s   (현행 제%d조 + 제%d조)"
              % (n["no"], n.get("title"), a, b))
        for s in sections(n["_new"]):
            if s[0] in ("현행 규정", "현행의 문제"):
                for ln in s[1]:
                    if ln.strip():
                        print("     %s" % ln.strip())
    if not write:
        print()
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")
        return
    for n in done:
        n["reason"] = n.pop("_new")
    io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("고쳤습니다 — %d개 조" % len(done))


if __name__ == "__main__":
    main()
