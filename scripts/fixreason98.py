# -*- coding: utf-8 -*-
r"""제98조부터 제100조까지의 변경 사유를 사실대로 갖춘다.

■ 제98조 —— 「현행 규정」이 틀렸다

  이렇게 적혀 있었다.

      * 제3편 지형측량에는 항공사진측량(제3장)만 있고, 무인비행장치로
        지형도를 만드는 일을 받아 주는 자리가 없음.
      …
      * 제115조(무인비행장치 측량) 한 줄로 갈음하고 있음.

  자료를 열어 보면 둘 다 사실과 다르다.

      현행 reg01  제3편 제4장이 이미 「무인비행장치 측량」이다.
                  그 아래 조는 제76조 하나뿐이며 53자이다.
      현행 제115조는 「하천 등의 횡단측량」이다.

  제115조는 **개정안에서** 현행 제76조가 옮겨 간 자리이다. 개정안의 새
  번호를 현행 번호인 양 적은 것이다.

■ 제99조ㆍ제100조 —— 「개정 내용」밖에 없다

  변경 사유가 다섯 도막인데 둘은 「개정 내용」 하나만 지녔다. 개정사유서의
  조항별 칸이 비어 나간다.

  세 조는 제3편 제4장을 함께 세우는 한 묶음이므로, 같은 현행 근거를
  나누어 적는다.

  python scripts\fixreason98.py            보여만 준다
  python scripts\fixreason98.py --write    고친다
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

ORDER = ["현행 규정", "현행의 문제", "관련 근거", "개정 사유", "개정 내용"]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def sections(reason):
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


def build(head, secs, want):
    """도막을 정한 차례로 다시 늘어놓고 없는 것은 채운다"""
    have = {s[0]: s[1] for s in secs if s[0]}
    L = list(head)
    for name in ORDER:
        lines = want.get(name) or have.get(name)
        if not lines:
            continue
        L.append("○ %s:" % name)
        body = [x for x in lines if x.strip()]
        L.append("")
        L.extend(body)
        L.append("")
    return NL.join(L).rstrip() + NL


CUR76 = ("* 현행 제3편 제4장이 「무인비행장치 측량」이나, 그 아래 조는 "
         "제76조 하나뿐임.",
         "* 제76조는 53자 한 줄로, 무인비행장치를 이용한 측량은 "
         "「무인비행장치 측량 작업규정」을 적용한다고만 정함.")

WANT = {
    98: {
        "현행 규정": list(CUR76),
        "현행의 문제": [
            "* 다른 고시를 부르는 한 줄뿐이어서, 이 규정 안에서 무인비행장치 "
            "성과에 무엇을 요구하는지 드러나지 아니함.",
            "* 지형도의 정확도와 성과의 정리가 무인비행장치 성과에 미치는지 "
            "여부를 조문에서 가릴 수 없음.",
            "* 점군을 얻는 일과 지형도를 만드는 일은 성과가 다른데, 둘을 가르는 "
            "조문이 없음.",
        ],
        "관련 근거": [
            "* 「무인비행장치 측량 작업규정」(국토지리정보원 고시) — 작업방법과 "
            "성과를 이미 정하고 있으므로 겹쳐 두지 아니함.",
            "* 「항공안전법」 — 비행 자체의 승인은 그 법 소관임.",
        ],
        "개정 사유": [
            "* 무인비행장치로 지형도를 만드는 일을 제3편이 받아 주도록 장을 "
            "세우고, 이 규정이 요구하는 것을 조문으로 밝힘.",
            "* 작업방법은 「무인비행장치 측량 작업규정」을 적용하도록 하여 "
            "규정을 겹쳐 두지 아니함.",
        ],
    },
    99: {
        "현행 규정": list(CUR76) + [
            "* 어떤 때에 무인비행장치를 쓸 수 있는지 정한 조문이 없음.",
        ],
        "현행의 문제": [
            "* 유인항공기 사진측량과 무인비행장치 사진측량 가운데 무엇을 "
            "고를 것인지 정한 바가 없어, 작업계획 단계에서 다투게 됨.",
            "* 비행이 제한되는 공역에서 무엇을 갖추어야 하는지 이 규정에 "
            "드러나지 아니함.",
        ],
        "관련 근거": [
            "* 「무인비행장치 측량 작업규정」 — 축척과 지상표본거리를 이미 "
            "정하고 있으므로 값을 옮겨 적지 아니함.",
            "* 「항공안전법」 — 비행 제한 공역과 승인은 그 법 소관임.",
        ],
        "개정 사유": [
            "* 무인비행장치를 쓸 수 있는 경우를 밝혀, 유인항공기 사진측량과의 "
            "갈림을 작업계획 단계에서 정하게 함.",
            "* 승인 사실을 작업계획서에 남기게 하는 데 그쳐, 「항공안전법」 "
            "소관과 겹치지 아니함.",
        ],
    },
    100: {
        "현행 규정": list(CUR76) + [
            "* 무인비행장치 성과의 정확도와 제출물을 정한 조문이 없음.",
        ],
        "현행의 문제": [
            "* 지형도의 정확도 기준이 무인비행장치로 만든 지형도에도 미치는지 "
            "조문에서 가릴 수 없음.",
            "* 원시 사진, 외부표정요소, 검사점 검증 결과처럼 무인비행장치 "
            "성과에서 빠지기 쉬운 것을 짚어 둔 곳이 없음.",
            "* 점군 성과가 제3편 소관인지 제4편 소관인지 드러나지 아니함.",
        ],
        "관련 근거": [
            "* 이 개정안 제86조(지형도의 정확도)와 제17조(성과패키지) — "
            "총칙과 각 편의 기준을 그대로 준용함.",
            "* 「무인비행장치 측량 작업규정」 — 지상기준점과 검사점의 배치와 "
            "수량을 이미 정하고 있음.",
        ],
        "개정 사유": [
            "* 무인비행장치로 만든 지형도에도 제86조의 정확도가 그대로 미친다는 "
            "것을 밝힘.",
            "* 성과는 제17조의 성과패키지로 내도록 하여 다른 측량과 같은 잣대를 "
            "쓰게 함.",
            "* 점군 성과는 제4편 소관임을 밝혀 두 편의 경계를 분명히 함.",
        ],
    },
}


def main():
    write = "--write" in sys.argv
    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    hit = []
    for n in walk(doc["tree"]):
        if n.get("level") != "조" or n.get("no") not in WANT:
            continue
        secs = sections(n.get("reason") or "")
        head = []
        for s in secs:
            if s[0] is None:
                head.extend(x for x in s[1] if x.strip())
            else:
                break
        if not head:
            head = ["[변경 사유]", ""]
        else:
            head = head + [""]
        n["_new"] = build(head, secs, WANT[n["no"]])
        hit.append(n)

    print("고칠 조 %d개" % len(hit))
    for n in hit:
        print()
        print("══ 제%d조 %s" % (n["no"], n.get("title")))
        print(n["_new"])
    if not write:
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")
        return
    for n in hit:
        n["reason"] = n.pop("_new")
    io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
        json.dumps(doc, ensure_ascii=False))
    print("고쳤습니다 — %d개 조" % len(hit))


if __name__ == "__main__":
    main()
