# -*- coding: utf-8 -*-
r"""연구보고서를 참조규정 서고에 넣는다 (loc30).

「디지털기반 지도등 간행심사 제도개선 및 효율화 방안 연구」(2026. 01,
공간정보품질관리원 수탁, ㈜예신정보기술ㆍ안양대학교 산학협력단)는 우리가
고치고 있는 「측량성과 심사수탁기관의 심사업무 및 지정절차 등에 관한 규정」의
개정안을 조문 단위로 제시한 문서다. 조문을 고칠 때 곁에 두고 보아야 하므로
서고에 넣어 화면에서 바로 열 수 있게 한다.

■ 어떻게 나누는가

  보고서에는 PDF 책갈피가 없다. 대신 앞머리의 차례(인쇄 ix~x쪽)에 장ㆍ절과
  인쇄 쪽수가 적혀 있으므로, 그것을 읽어 마디를 만들고 쪽 범위로 글을 나눈다.

      제N장            편
      1. 2. 3.         장
      가. 나. 다.       조   ← 글이 담기는 자리

  인쇄 쪽수와 PDF 쪽수는 14쪽 어긋난다(인쇄 3쪽 = PDF 17쪽). 차례에서 읽은
  인쇄 쪽수에 그만큼을 더해 실제 쪽을 집는다.

  python scripts\addreport.py            무엇을 넣을지 보여만 준다
  python scripts\addreport.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
BASE = os.path.dirname(os.path.dirname(ROOT))
NL = chr(10)

SID = "loc30"
PDF = os.path.join(BASE, "99.참고자료", "관련연구보고서",
                   "디지털기반지도등간행심사연구 연구보고서_20260310_v2.6_완료.pdf")
NAME = "디지털기반 지도등 간행심사 제도개선 및 효율화 방안 연구 (2026)"
OFFSET = 14          # 인쇄 쪽 + 14 = PDF 쪽

META = {
    "id": SID, "name": NAME, "org": "공간정보품질관리원", "kind": "연구보고서",
    "no": "2026.01", "effective": "202601", "lang": "ko",
    "category": "research",
    "source": "공간정보품질관리원 수탁 · ㈜예신정보기술, 안양대학교 산학협력단",
    "file": SID + ".json", "hasFullText": True, "indexMode": "전문",
    "localOnly": True,
}

# 차례가 실린 쪽 (PDF 쪽)
TOC_PAGES = (9, 10)
# 제목이 길면 점 대신 한 칸으로 쪽수를 잇는 줄이 있다(제4장 1., 제5장 1.).
# 점을 넷 이상 요구하면 그런 줄을 놓친다. 줄머리가 「제N장」ㆍ「N.」ㆍ「가.」
# 인지는 따로 보므로 여기서는 늦추어도 된다.
RE_TOC = re.compile(r"^(.*?)[·．.\s]+(\d{1,3})\s*$")


# PDF 에서 딸려 오는 제어문자 — 차례의 이음표 자리에 U+0001 이 박혀 있다.
# 그대로 두면 제목이 「제2장 지도등 간행심사」 처럼 나온다.
RE_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean(s):
    s = RE_CTRL.sub(" ", str(s or ""))
    s = re.sub(r"[ 	]+", " ", s)
    return NL.join(x.strip() for x in s.split(NL)).strip()


def pages_of(path):
    import fitz
    d = fitz.open(path)
    return {i: p.get_text() for i, p in enumerate(d, 1)}


def read_toc(pg):
    """차례 → [(깊이, 제목, 인쇄쪽)]"""
    out = []
    for n in TOC_PAGES:
        for raw in (pg.get(n) or "").split(NL):
            s = raw.strip()
            m = RE_TOC.match(s)
            if not m:
                continue
            t = clean(m.group(1)).strip(" ·．.")
            if not t:
                continue
            if re.match(r"^제\s*\d+\s*장", t):
                lv = 1
            elif re.match(r"^\d+\.", t):
                lv = 2
            elif re.match(r"^[가-힣]\.", t):
                lv = 3
            else:
                continue
            out.append((lv, t, int(m.group(2))))
    return out


def slice_text(pg, a, b):
    """인쇄 a쪽부터 b쪽 앞까지의 글 — 쪽 머리말과 쪽번호는 걷어 낸다"""
    buf = []
    for n in range(a + OFFSET, b + OFFSET):
        t = pg.get(n) or ""
        lines = []
        for ln in t.split(NL):
            s = ln.strip()
            if not s or s.isdigit():
                continue
            if s.startswith("디지털기반지도등간행심사") or s.startswith("제") and s.endswith("마련") and len(s) < 40:
                continue
            lines.append(s)
        buf.append(NL.join(lines))
    return clean(re.sub(NL + "{3,}", NL * 2, NL.join(buf)))


def main():
    write = "--write" in sys.argv
    if not os.path.exists(PDF):
        sys.exit("보고서를 찾지 못했습니다 — %s" % PDF)
    pg = pages_of(PDF)
    toc = read_toc(pg)
    if not toc:
        sys.exit("차례를 읽지 못했습니다")

    # 마디마다 글이 실린 인쇄 쪽 범위를 정한다
    last = max(pg) - OFFSET
    spans = []
    for i, (lv, t, p) in enumerate(toc):
        nxt = toc[i + 1][2] if i + 1 < len(toc) else last
        spans.append((lv, t, p, max(nxt, p + 1)))

    tree, stack = [], {}
    n_jo = 0
    for lv, t, a, b in spans:
        node = {"id": "%s-%d-%s" % (SID, a, re.sub(r"[^0-9]", "", t)[:4] or "0"),
                "level": {1: "편", 2: "장", 3: "조"}[lv],
                "no": 0, "branch": 0, "title": t, "body": "",
                "status": "유지", "legacyNo": "", "reason": "",
                "sourceRef": None, "history": [], "children": [],
                "collapsed": lv > 1}
        node["_span"] = (a, b)
        stack[lv] = node
        if lv == 1:
            tree.append(node)
        else:
            up = stack.get(lv - 1)
            (up["children"] if up else tree).append(node)

    # 글은 **잎 마디**에 담는다. 아래 마디가 있는 장은 제목만 지니고,
    # 아래가 없는 장은 스스로 조가 되어 글을 담는다. 아래가 없는 편은
    # 조를 하나 만들어 붙인다 — 편에는 글칸이 없기 때문이다.
    def fill(ns):
        nonlocal n_jo
        for x in ns:
            sp = x.pop("_span", None)
            if x["children"]:
                fill(x["children"])
                continue
            if x["level"] == "편":
                kid = dict(x)
                kid.update({"id": x["id"] + "-t", "level": "조",
                            "title": x["title"], "children": []})
                kid["body"] = slice_text(pg, *sp) if sp else ""
                x["children"] = [kid]
                n_jo += 1
            else:
                x["level"] = "조"
                x["body"] = slice_text(pg, *sp) if sp else ""
                n_jo += 1
    fill(tree)

    doc = dict(META)
    doc.update({"note": "PDF 232쪽. 인쇄 쪽수와 PDF 쪽수가 14쪽 어긋난다.",
                "stats": {"편": sum(1 for x in tree),
                          "장": 0, "절": 0, "관": 0, "조": n_jo},
                "tree": tree})

    print("보고서 : %s" % os.path.basename(PDF))
    print("차례에서 읽은 마디 %d개 (편 %d · 글이 담긴 마디 %d)"
          % (len(spans), len(tree), n_jo))
    for x in tree:
        print("  %s" % x["title"])
        for c in x["children"][:3]:
            print("     %s (%d자)" % (c["title"][:44], len(c.get("body") or "")
                                      + sum(len(g.get("body") or "") for g in c["children"])))
        if len(x["children"]) > 3:
            print("     … 그 밖에 %d마디" % (len(x["children"]) - 3))

    if not write:
        print()
        print("시험만 한 것입니다. 넣으려면 --write 를 붙이십시오.")
        return

    io.open(os.path.join(DATA, SID + ".json"), "w",
            encoding="utf-8", newline=NL).write(json.dumps(doc, ensure_ascii=False))

    libp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libp, encoding="utf-8"))
    lib.setdefault("categories", {})["research"] = "연구보고서"
    lib["regulations"] = [r for r in lib["regulations"] if r["id"] != SID]
    e = dict(META)
    e["stats"] = doc["stats"]
    lib["regulations"].append(e)
    io.open(libp, "w", encoding="utf-8", newline=NL).write(
        json.dumps(lib, ensure_ascii=False, indent=1))
    print()
    print("넣었습니다 — %s · 서고 %d종" % (SID, len(lib["regulations"])))


if __name__ == "__main__":
    main()
