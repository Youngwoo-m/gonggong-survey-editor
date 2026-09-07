# -*- coding: utf-8 -*-
r"""별표 58 마디를 개정안 트리에 세운다 (annexref.py 로 새로 둔 별표)."""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
os.chdir(r"D:\11.연구사업\2026년도\2026.공공측량.품관원\App\prototype")
NL = chr(10)
SRC = os.path.join("data", "draft2025.json")
WRITE = "--write" in sys.argv


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


BODY = NL.join([
    "1. 적용 범위",
    "  가. 이 표는 제98조제4항제3호에 따라 RTK-GNSS 세부측량에서 세트 간 교차의 "
    "축척별 허용범위를 정한다.",
    "  나. 기준점측량의 세트 간 교차는 이 표를 쓰지 아니하고 제46조제1항제3호의 "
    "표에 따른다.",
    "",
    "2. 값을 정한 방법",
    "  가. 이 표의 값은 제98조제6항의 「지형ㆍ지물 등의 측정정밀도는 도상 0.3mm "
    "이내로 한다」 를 축척마다 지상거리로 환산한 것이다.",
    "  나. 값을 새로 정한 것이 아니라 이미 있는 기준을 축척마다 셈하여 벌여 놓은 "
    "것이다.",
    "  다. 이 표에 없는 축척은 도상 0.3mm 에 그 축척의 분모를 곱하여 구한다.",
    "",
    "3. 견주는 성분",
    "  가. 세트 간 교차는 ΔX, ΔY, 수평위치 교차 및 ΔH 로 나누어 견준다"
    "(제98조제4항제3호).",
    "  나. 표고의 정밀도가 수평위치보다 낮은 장비를 쓰는 경우에는 ΔH 의 허용범위를 "
    "제품사양서(별표 16)에서 따로 정할 수 있다.",
    "",
    "4. 허용범위를 넘은 경우",
    "  가. 재초기화하여 다시 관측한다(제98조제4항).",
    "  나. 다시 관측하여도 넘는 경우에는 그 까닭을 살펴 관측 조건을 바꾸거나 "
    "다른 측량방법으로 갈음한다.",
])

REASON = NL.join([
    "[변경 사유]",
    "",
    "○ 현행 규정:",
    "",
    "* 없음 —— 현행 규정에는 이 표가 없다.",
    "* 현행 제98조에 해당하는 조문은 세트 간 교차를 견주도록 하면서 그 허용범위를 "
    "축척과 관계없이 하나의 값으로 두고 있었다.",
    "",
    "○ 현행의 문제:",
    "",
    "* 개정안 제98조제4항제3호가 「축척별 허용범위는 별표에서 정한다」 라 하면서 "
    "별표 번호를 적지 아니하였다. 어느 별표를 보라는 것인지 알 수 없었다.",
    "* 세부측량의 허용범위가 축척과 관계없이 하나이면, 큰 축척에서는 지나치게 "
    "느슨하고 작은 축척에서는 지나치게 촘촘해진다.",
    "",
    "○ 관련 근거:",
    "",
    "* 제98조제6항이 측정정밀도를 도상 0.3mm 로 정하고 있다 —— 축척별 허용범위는 "
    "그것을 지상거리로 환산하면 바로 나온다.",
    "",
    "○ 개정 사유:",
    "",
    "* 번호 없는 위임을 없애고, 축척마다 알맞은 허용범위를 두기 위함이다.",
    "* 값을 새로 정하지 아니하고 이미 있는 기준(도상 0.3mm)을 환산한 것이므로 "
    "지금보다 촘촘해지거나 느슨해지는 것이 아니다.",
    "",
    "○ 개정 내용:",
    "",
    "* 축척 다섯(1:500ㆍ1:1,000ㆍ1:2,500ㆍ1:5,000ㆍ1:10,000)의 허용범위를 표로 두고, "
    "표에 없는 축척은 셈하는 방법을 적었다.",
    "* 기준점측량의 세트 간 교차는 제46조제1항제3호의 표에 따르도록 갈라 적었다.",
    "",
    "○ 기대 효과와 예상 반론 (2026-09-07 더함):",
    "",
    "* [이익] 공공측량수행자 — 축척에 맞는 허용범위를 표에서 바로 찾을 수 있음.",
    "* [이익] 심사수탁기관 — 축척이 다른 성과를 같은 잣대로 견주지 아니하게 됨.",
    "* [예상 반론] (우려) 큰 축척에서 허용범위가 좁아져 재관측이 는다 → (답) "
    "도상 0.3mm 는 제98조제6항이 이미 정한 측정정밀도이며, 이 표는 그것을 축척으로 "
    "환산한 것이므로 새로 좁아지는 것이 아니다.",
])


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    grp = None
    for n in walk(doc.get("tree") or []):
        if n.get("level") == "편" and (n.get("title") or "").startswith("별표"):
            grp = n
    if grp is None:
        raise SystemExit("별표 묶음을 찾지 못하였습니다")

    kids = grp.setdefault("children", [])
    if any(str((k.get("annexRef") or {}).get("no")) == "58" for k in kids):
        print("   (건너뜀) 별표 58 마디가 이미 있습니다")
        return

    ids = {n.get("id") for n in walk(doc.get("tree") or [])}
    nid = "nanx-별표-58"
    while nid in ids:
        nid += "x"

    kids.append({
        "id": nid, "level": "조", "no": 0, "branch": 0,
        "title": "RTK-GNSS 세부측량의 축척별 세트 간 교차 허용범위",
        "body": BODY, "status": "신설", "legacyNo": "",
        "reason": REASON, "sourceRef": None, "history": [],
        "annexRef": {"gubun": "별표", "no": "58"},
        "children": [], "collapsed": True,
    })
    grp["title"] = "별표 (%d건)" % len(kids)
    print("   별표 58 마디를 세웠습니다 —— 별표 %d건" % len(kids))
    if WRITE:
        json.dump(doc, io.open(SRC, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print("적었습니다 — %s" % SRC)
    else:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
