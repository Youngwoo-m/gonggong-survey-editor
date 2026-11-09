# -*- coding: utf-8 -*-
r"""보류 지적 가운데 표 개체를 고칠 것 둘을 고친다 (2026-11-09).

■ 1편-4 —— 제9조 표(t4317)의 별표 번호

  정확도 관리표 14종을 개정안이 별표 1부터 별표 14까지로 다시 매겼는데,
  제9조 제3항의 표는 현행 번호(별표 3ㆍ4ㆍ7ㆍ14ㆍ15ㆍ16ㆍ17ㆍ18ㆍ19ㆍ21~25)로
  불렀다. t4317 은 연구보고서에서 온 **개정안 전용 표**이고 현행 규정은 쓰지
  아니하므로 제자리에서 고친다.

■ 2편A-13 —— 제37조제4항 표의 「GPS 수신기」

  표(151295863)는 현행 제19조와 함께 쓰는 개체이므로 고치면 현행까지 바뀐다.
  같은 자리(data/objects/reg01)에 개정안 전용 사본(151295863n)을 두고 글자만
  고친 뒤 개정안 제37조가 그것을 가리키게 한다. 신구대조표에서는 현행 표와
  개정안 표가 나란히 나온다.

  이미 되어 있으면 아무것도 하지 아니한다.

  python scripts\fixtables1109.py            보여만 준다
  python scripts\fixtables1109.py --write    고친다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OBJ = os.path.join(ROOT, "data", "objects", "reg01")
SRC = os.path.join(ROOT, "data", "draft2025.json")
REG = os.path.join(ROOT, "data", "reg01.json")
NL = chr(10)

# 현행 별표 번호 → 개정안 별표 번호 (정확도 관리표 14종)
RENUM = {3: 1, 4: 2, 7: 3, 14: 4, 15: 5, 16: 6, 17: 7, 18: 8, 19: 9,
         21: 10, 22: 11, 23: 12, 24: 13, 25: 14}
OLD_MARK = "별표 25 「경계측량 정확도 관리표」"
NEW_ID = "151295863n"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    todo = []

    t = os.path.join(OBJ, "t4317.xml")
    xml = io.open(t, encoding="utf-8").read()
    if OLD_MARK in xml:
        new = re.sub(r"별표 (\d+) 「", lambda m: "별표 %d 「" % RENUM[int(m.group(1))], xml)
        todo.append(("t4317 별표 번호", lambda: io.open(t, "w", encoding="utf-8", newline=NL).write(new)))

    src = os.path.join(OBJ, "151295863.xml")
    dst = os.path.join(OBJ, NEW_ID + ".xml")
    if not os.path.exists(dst):
        x = io.open(src, encoding="utf-8").read()
        x = x.replace('id="151295863"', 'id="%s"' % NEW_ID, 1).replace("GPS 수신기", "GNSS 수신기")
        todo.append(("%s 사본(GNSS 수신기)" % NEW_ID,
                     lambda: io.open(dst, "w", encoding="utf-8", newline=NL).write(x)))

    ixp = os.path.join(OBJ, "index.json")
    ix = json.load(io.open(ixp, encoding="utf-8"))
    if NEW_ID not in ix:
        meta = dict(ix["151295863"])
        meta["article"] = "제37조(개정안)"
        ix[NEW_ID] = meta
        todo.append(("index.json 에 %s" % NEW_ID,
                     lambda: io.open(ixp, "w", encoding="utf-8", newline=NL).write(
                         json.dumps(ix, ensure_ascii=False))))

    d = json.load(io.open(SRC, encoding="utf-8"))
    by = {n["id"]: n for n in walk(d["tree"])}
    a11, a23 = by["a11"], by["a23"]
    dirty = False
    line = "* 가리키는 별표는 그대로 둠."
    if line in a11["reason"]:
        a11["reason"] = a11["reason"].replace(
            line, "* 표가 가리키는 정확도 관리표는 개정안의 새 번호(별표 1부터 별표 14까지)로 맞춤 (2026-11-09).")
        dirty = True
    if '<img id="151295863">' in a23["body"]:
        a23["body"] = a23["body"].replace('<img id="151295863">', '<img id="%s">' % NEW_ID)
        if not a23.get("wasBody"):
            reg = next(n for n in walk(json.load(io.open(REG, encoding="utf-8"))["tree"])
                       if n.get("level") == "조" and n.get("no") == 19)
            a23["wasBody"] = reg["body"]
        a23["reason"] = a23["reason"].replace(
            "* 나머지 문언은 현행과 같음.",
            "* 제4항 표의 「GPS 수신기를 사용하는 경우」를 「GNSS 수신기를 사용하는 경우」로 고침 —— 이 규정의 다른 곳과 같이 위성항법 전체를 가리키는 말을 씀 (2026-11-09).\n* 나머지 문언은 현행과 같음.")
        dirty = True
    if dirty:
        todo.append(("draft2025.json 제9조 사유, 제37조 표와 사유",
                     lambda: io.open(SRC, "w", encoding="utf-8", newline=NL).write(
                         json.dumps(d, ensure_ascii=False))))

    if not todo:
        print("바꿀 것: 없음 (이미 적용됨)")
        return
    for name, _f in todo:
        print("바꿀 것: " + name)
    if not write:
        print("보여만 준 것임. 고치려면 --write 를 붙일 것.")
        return
    for name, f in todo:
        f()
    print("고쳤습니다.")


if __name__ == "__main__":
    main()
