# -*- coding: utf-8 -*-
r"""「산업표준화법」을 참조규정에 reg72 로 넣는다.

공공측량 작업규정 개정안 제25조제2항이 "부합하는 한국산업표준이 제정된
경우에는 그 표준에 따른다" 는 단서를 두었다. 그 단서의 근거가 이 법
제12조(한국산업표준의 제정)이므로 변경 사유에서 「산업표준화법」을 부른다.

그런데 이 법이 참조규정에 없어 눌러도 열리지 아니한다. 넣는다.

addregs.py 의 연장이되 다른 점이 둘 있다.

  ㆍ 번호를 손으로 준다 — addregs 의 next_id() 는 빈 번호를 앞에서부터
    채우므로 중간에 구멍이 있으면 reg72 가 아닌 것을 준다.
  ㆍ 그 번호나 이름이 이미 쓰이고 있으면 아무것도 하지 아니하고 멎는다.

  python scripts\addsanup.py            무엇을 넣을지 보여만 준다
  python scripts\addsanup.py --write    자료에 적는다
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gendata as G                                    # noqa: E402
import addregs as A                                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = G.OUT

SID = "reg72"
QUERY = "산업표준화법"
NAME = "산업표준화법"
CATEGORY = "law"        # 상위법령
TARGET = "law"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    libpath = os.path.join(OUT, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))

    if SID in {r["id"] for r in lib["regulations"]}:
        sys.exit("%s 는 이미 쓰이고 있습니다 — 다른 번호를 주십시오" % SID)
    if G.norm(NAME) in {G.norm(r["name"]) for r in lib["regulations"]}:
        sys.exit("「%s」 은 이미 참조규정에 있습니다" % NAME)

    hit = G.find(TARGET, QUERY) or G.find(TARGET, NAME)
    if not hit:
        sys.exit("국가법령정보센터에서 찾지 못했습니다 — %s" % QUERY)
    print("찾았습니다")
    print("   이름 : %s" % hit["name"])
    print("   소관 : %s · %s 제%s호" % (hit["org"], hit["kind"], hit["no"]))
    print("   시행 : %s" % hit["ef"])

    doc = A.build_doc(SID, hit, CATEGORY, TARGET)
    print("   조문 : %d조 (편 %d · 장 %d · 절 %d)"
          % (doc["stats"]["조"], doc["stats"]["편"],
             doc["stats"]["장"], doc["stats"]["절"]))
    print("   별표 : %d건" % len(doc["annex"]))

    # 단서의 근거인 제12조가 실제로 들어왔는지 본다 — 없으면 헛일이다
    j12 = [x for x in walk(doc["tree"])
           if x.get("level") == "조" and str(x.get("no")) == "12"]
    if j12:
        one = " ".join(str(j12[0].get("body") or "").split())
        print("   제12조 : %s" % (j12[0].get("title") or "(제목 없음)"))
        print("            %s" % one[:96])
    else:
        print("   ! 제12조를 받지 못했습니다 — 넣기 전에 살펴보십시오")

    if not write:
        print()
        print("시험만 한 것입니다. 넣으려면 --write 를 붙이십시오.")
        return

    with io.open(os.path.join(OUT, SID + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                             "lang", "category", "source", "stats")}
    e["file"] = SID + ".json"
    e["hasFullText"] = True
    e["annexCount"] = len(doc["annex"])
    lib["regulations"].append(e)
    lib["generated"] = time.strftime("%Y-%m-%d")
    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print()
    print("넣었습니다 — %s (%s) · 참조규정 %d종"
          % (SID, doc["name"], len(lib["regulations"])))


if __name__ == "__main__":
    main()
