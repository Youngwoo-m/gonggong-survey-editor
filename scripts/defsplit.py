# -*- coding: utf-8 -*-
r"""편별 정의 조문을 장별로 나눈다 (작업규정 개정안).

■ 왜 나누는가

  현행 규정은 용어의 뜻을 조문 곳곳에 흩어 두었다. 개정안은 그것을
  거두어 편마다 정의 조문 하나를 두었다. 그런데 응용측량 편은 한 조에
  60호가 몰려, 노선측량을 하는 사람이 토지구획정리측량의 용어까지
  훑어야 한다. 찾아 읽기 어렵기는 흩어져 있을 때와 다르지 아니하다.

  일본 「作業規程の準則」은 편의 총칙과 장의 머리에 정의를 나누어 둔다.
  그 방식에 따라, 편 공통으로 쓰는 용어만 편에 남기고 그 장에서만
  쓰는 용어는 장의 머리로 내린다.

■ 나누는 잣대

  ㆍ 두 장 이상에서 쓰는 용어      → 편의 정의 조문에 남긴다.
  ㆍ 한 장에서만 쓰는 용어         → 그 장의 머리에 정의 조문을 세워 옮긴다.
  ㆍ 남는 것이 없는 편의 정의 조문 → 없앤다 (지형측량ㆍ3차원ㆍ응용측량).

■ 조 번호가 밀리는 것

  조문이 늘어 뒤의 번호가 밀린다. 본문이 우리 규정의 조를 부르는 자리를
  옛 번호에서 새 번호로 함께 옮긴다. 남의 법령을 부르는 자리
  (「법」 제17조 따위)와 <현행 제N조> 표시는 건드리지 아니한다.

  python scripts\defsplit.py            무엇을 고칠지 보여만 준다
  python scripts\defsplit.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

import renumlib

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
NL = chr(10)

# 편의 정의 조문 id -> (편 이름, {장 이름: [호 번호…]}, 편에 남길 호 번호)
PLAN = {
    "def-659392": ("공공기준점측량", {
        "공공삼각점측량": [3, 4, 5, 6],
        "공공수준점측량": [7, 8],
        "GNSS 수준측량": [9, 10],
        "네트워크 RTK 측량": [11, 12],
    }, [1, 2, 13, 14, 15]),
    "def-950835": ("지형측량", {
        "지상현황측량": [1, 2, 3, 4],
        "무인비행장치 사진측량": [9],
        "일반지도 수치화": [5],
        "지도의 축소편집": [6, 7, 8],
    }, []),
    "def-11827": ("3차원 공간정보 구축", {
        "무인비행장치 레이저측량": [1],
        "차량기반 이동측량 및 정밀도로지도": [2, 3],
    }, []),
    "def-279461": ("응용측량", {
        "노선측량": list(range(1, 8)),
        "하천 및 연안측량": list(range(8, 16)),
        "용지측량": list(range(16, 22)),
        "토지구획정리측량": list(range(22, 51)),
        "지하시설물측량": list(range(51, 61)),
    }, []),
    "def-231569": ("안전관리", {
        "작업환경별 안전기준": [6, 7, 8, 9],
    }, [1, 2, 3, 4, 5]),
}

# 장별 정의 조문에 붙일 「관련 근거」 —— 그 장의 정의가 온 현행 자리
BASIS = {
    "공공삼각점측량": "현행 제16조(정의)ㆍ제26조ㆍ제27조",
    "공공수준점측량": "현행 제38조ㆍ제39조",
    "GNSS 수준측량": "현행 제45조(정의)",
    "네트워크 RTK 측량": "현행 제193조(정의)",
    "지상현황측량": "현행 제69조부터 제72조까지",
    "무인비행장치 사진측량": "「무인비행장치 측량 작업규정」",
    "일반지도 수치화": "현행 제79조",
    "지도의 축소편집": "현행 제83조부터 제85조까지",
    "무인비행장치 레이저측량": "「무인비행장치 측량 작업규정」 및 연구보고서",
    "차량기반 이동측량 및 정밀도로지도": "정밀도로지도 관련 연구보고서",
    "노선측량": "현행 제99조부터 제108조까지",
    "하천 및 연안측량": "현행 제110조부터 제118조까지",
    "용지측량": "현행 제123조부터 제128조까지",
    "토지구획정리측량": "현행 제131조부터 제166조까지",
    "지하시설물측량": "현행 제168조(정의)",
    "작업환경별 안전기준": "「산업안전보건기준에 관한 규칙」 제618조",
}

# 편의 정의 조문에 적혀 있던, 그 장으로 함께 옮겨야 하는 확인 기록
CARRY = {
    "지하시설물측량": [
        "* 인용 확인 —— 「고압가스 안전관리법」 제23조의6(고압가스배관의 안전조치 등)을 그대로 둠.",
        "* 그 법 개정으로 제23조 본조는 제43조로 옮겨졌으나 가지조인 제23조의6은 그대로이므로,"
        " 이 규정이 부르는 자리는 달라지지 아니함 (시행 2026.3.10., 법률 제21438호 사본 확인).",
        "* 문언을 바로잡음 —— 「부속설비」는 「고압가스 안전관리법」과 그 시행령ㆍ시행규칙"
        " 어디에도 없는 말임. 법 제23조의6제2항이 위임한 시행규칙 제52조의7제2항제1호가"
        " 「배관 및 그 부속시설의 매설 위치」라고 적고 있으므로 「그 부속시설」로 함.",
        "* 현행 규정부터 잘못 적혀 있던 것임.",
        "* 「시설물의 안전관리에 관한 특별법 시행령」이 폐지되어"
        " 「시설물의 안전 및 유지관리에 관한 특별법 시행령」으로 고침.",
        "* 다만 별표 1 제5호나목이 새 시행령에서도 같은 자리인지는 확인하지 못하였으므로"
        " 발령 전에 살펴야 함.",
        "* 이름씨 뒤의 「측량」 띄어쓰기는 되돌림 —— 국토지리정보원 「공간정보 용어사전」이"
        " 기준점측량ㆍ도근점측량ㆍ지하시설물측량ㆍ지상기준점을 모두 붙여 쓰고,"
        " 띄어 쓴 표제어가 하나도 없음.",
    ],
}

HO = re.compile(r"^\s*(\d+)\.\s")
# 우리 규정의 조를 부르는 자리인가 —— 앞말이 법령이면 남의 법령이다
LAW_TAIL = re.compile(r"(?:법|법률|규칙|규정|령|지침|고시|기준|」)\s*$")
SRC_MARK = re.compile(r"<(?:현행|신설)[^>]*>")
JO = re.compile(r"제\s*(\d+)\s*조")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def parent_of(tree, node):
    for n in walk(tree):
        if node in (n.get("children") or []):
            return n
    return None


def split_items(body):
    """머리글 한 줄과 호 묶음으로 가른다. 목(가.ㆍ나.…)은 그 호에 붙인다."""
    head, items, cur = [], {}, None
    for ln in (body or "").split(NL):
        m = HO.match(ln)
        if m:
            cur = int(m.group(1))
            items[cur] = [ln]
        elif cur is None:
            head.append(ln)
        else:
            items[cur].append(ln)
    return NL.join(head), items


def renum(nums, items):
    """골라낸 호를 1부터 다시 매긴다"""
    out = []
    for i, k in enumerate(nums, 1):
        block = list(items[k])
        block[0] = HO.sub("%d. " % i, block[0], count=1)
        out.extend(block)
    return NL.join(out)


def reason_for(pyeon, jang, n):
    b = ["[변경 사유]", "",
         "○ 현행 규정:", "",
         "* 없음 —— 신설 조문.", "",
         "○ 현행의 문제:", "",
         "* %s에서 쓰는 용어의 뜻이 조문 곳곳에 흩어져 있어 찾아 읽기 어려움." % jang,
         "* 편의 정의 조문 한 곳에 용어가 몰려, 이 장을 하는 사람이 다른 장의 용어까지 훑어야 함.",
         "",
         "○ 관련 근거:", "",
         "* %s." % BASIS.get(jang, "현행 규정의 해당 조문"),
         "* 일본 「作業規程の準則」이 편의 총칙과 장의 머리에 정의를 나누어 두는 방식.",
         "",
         "○ 개정 사유:", "",
         "* 두 장 이상에서 쓰는 용어만 편의 정의 조문에 두고, 이 장에서만 쓰는 용어는 장의 머리로 내림.",
         "* 찾아 읽는 자리를 그 용어를 쓰는 자리에 가깝게 둠.",
         "",
         "○ 개정 내용:", "",
         "* %s 편의 정의 조문에 있던 이 장의 용어 정의 %d개를 이 조로 옮김." % (pyeon, n),
         "* 호의 차례와 각 호 뒤의 출처 표시는 그대로 둠."]
    b.extend(CARRY.get(jang, []))
    return NL.join(b)


def remap_body(text, move, log, where):
    """본문이 부르는 우리 규정의 조 번호를 새 번호로 옮긴다"""
    out, last = [], 0
    for m in JO.finditer(text):
        out.append(text[last:m.start()])
        last = m.end()
        no = int(m.group(1))
        pre = text[max(0, m.start() - 16):m.start()]
        tail = text[m.start():m.end() + 30]
        # <현행 제N조 …> 표시와 남의 법령은 건드리지 아니한다
        inside = any(a.start() <= m.start() < a.end() for a in SRC_MARK.finditer(text))
        if inside or LAW_TAIL.search(pre) or pre.rstrip().endswith("현행"):
            out.append(m.group(0))
            continue
        if no in move:
            out.append("제%d조" % move[no])
            log.append((where, no, move[no], (pre[-20:] + tail).replace(NL, " ")))
        else:
            out.append(m.group(0))
    out.append(text[last:])
    return "".join(out)


def main():
    write = "--write" in sys.argv
    d = json.load(io.open(SRC, encoding="utf-8"))
    tree = d["tree"]
    byid = {n.get("id"): n for n in walk(tree)}

    oldno = {n["id"]: int(n["no"]) for n in walk(tree)
             if n.get("level") == "조" and n.get("no") and not n.get("annexRef")}

    made, dropped, kept = [], [], []
    for did, (pyeon, plan, keep) in PLAN.items():
        src = byid.get(did)
        if not src:
            print("!! 정의 조문을 찾지 못함: %s" % did)
            continue
        head, items = split_items(src.get("body"))
        used = sorted(sum(plan.values(), []) + keep)
        if used != sorted(items):
            print("!! %s —— 호를 빠짐없이 나누지 못함: 있는 것 %s / 나눈 것 %s"
                  % (pyeon, sorted(items), used))
            return

        pyeon_node = next((n for n in walk(tree)
                           if n.get("level") == "편" and n.get("title") == pyeon), None)
        assert pyeon_node, pyeon
        jangs = {c.get("title"): c for c in pyeon_node["children"] if c.get("level") == "장"}

        for jang, nums in plan.items():
            assert jang in jangs, "%s 편에 %s 장이 없음" % (pyeon, jang)
            node = {
                "id": "def-%s-%s" % (pyeon_node.get("no"), jangs[jang].get("no")),
                "level": "조", "no": 0, "branch": 0, "title": "정의",
                "status": "신설", "legacyNo": "",
                "body": "이 장에서 사용하는 용어의 뜻은 다음과 같다." + NL + renum(nums, items),
                "reason": reason_for(pyeon, jang, len(nums)),
                "sourceRef": None, "history": [], "children": [],
            }
            if write:
                jangs[jang]["children"].insert(0, node)
            made.append((pyeon, jang, len(nums)))

        if keep:
            if write:
                src["body"] = head + NL + renum(keep, items)
            kept.append((pyeon, len(keep)))
        else:
            if write:
                parent_of(tree, src)["children"].remove(src)
            dropped.append(pyeon)

    for p, j, n in made:
        print("  세움  %-16s / %-22s 정의 —— 호 %2d개" % (p, j, n))
    print()
    for p, n in kept:
        print("  남김  %-16s 편의 정의 조문 —— 편 공통 호 %d개" % (p, n))
    for p in dropped:
        print("  없앰  %-16s 편의 정의 조문 (편에 남는 호가 없음)" % p)

    if not write:
        print()
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")
        return

    renumlib.renumber(tree)
    move = {}
    for n in walk(tree):
        if n.get("id") in oldno:
            o, w = oldno[n["id"]], int(n["no"])
            if o != w:
                move[o] = w
    print()
    print("번호가 밀린 조 %d개" % len(move))

    log = []
    for n in walk(tree):
        if n.get("body"):
            n["body"] = remap_body(n["body"], move, log, "제%s조 %s" % (n.get("no"), n.get("title")))
    print("본문의 조 인용을 옮긴 자리 %d곳" % len(log))
    for w, o, t, ctx in log:
        print("   %-28s 제%d조 → 제%d조   %s" % (w[:28], o, t, ctx[:66]))

    io.open(SRC, "w", encoding="utf-8", newline=NL).write(
        json.dumps(d, ensure_ascii=False))
    io.open(os.path.join(HERE, "_defsplit_move.json"), "w", encoding="utf-8").write(
        json.dumps(move, ensure_ascii=False))
    print()
    print("적었습니다 —— data/draft2025.json · 번호 옮김표는 scripts/_defsplit_move.json")


if __name__ == "__main__":
    main()
