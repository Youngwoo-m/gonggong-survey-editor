# -*- coding: utf-8 -*-
r"""국외 규정의 번역과 대역이 원문의 구조를 지켰는지 본다.

■ 왜 보아야 하는가

  화면에서 원문ㆍ번역ㆍ대역을 골라 볼 수 있고, 이제 고른 그대로 내려받을 수도
  있다(ui/printdoc.js). 그러므로 번역이 원문과 구조가 어긋나면 그대로 문서에
  실려 나간다.

  글의 뜻이 맞는가는 기계가 가릴 수 없다. 그러나 **구조는 셀 수 있다.**

■ 무엇을 세는가

  ㉠ 짝이 없는 마디   원문만 있거나 번역만 있는 것.
  ㉡ 줄 수            원문이 여러 줄인데 번역이 한 줄로 뭉개졌는가.
  ㉢ 항ㆍ호 표시      ①②③ ㆍ 1. 2. ㆍ (1)(2) ㆍ 가. 나. 의 수가 맞는가.
  ㉣ 번역이 아닌 것   원문을 그대로 베껴 둔 마디.
  ㉤ 길이             번역이 원문의 3분의 1보다 짧거나 세 곱보다 긴 것.

  줄 수와 항 표시가 어긋나면 대역으로 나란히 놓았을 때 짝이 밀린다.

  python scripts\checktrans.py            간추려 보여 준다
  python scripts\checktrans.py --md 파일   표로 적는다
"""
import glob
import io
import json
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)

RE_HANG = re.compile(r"[①-⑳]")
RE_HO = re.compile(r"(?m)^\s*(\d{1,2})\s*\.")
RE_PAREN = re.compile(r"(?m)^\s*\((\d{1,2})\)")
RE_GA = re.compile(r"(?m)^\s*([가-힣])\s*\.")
RE_HANGUL = re.compile(r"[가-힣]")


def walk(ns, path=()):
    for n in ns:
        yield n, path
        yield from walk(n.get("children") or [], path + (n.get("title") or "",))


RE_IMG = re.compile(r'<img\s[^>]*>(?:</img>)?|<img\s[^>]*/?>')


def lines(s):
    """줄을 센다. 표ㆍ그림 개체 줄은 빼고 센다.

    본문에서 표는 `<img id="loc28t001"></img>` 한 줄로 자리를 지킨다.
    번역이 표를 옮기는 대신 「점밀도는 원문의 표와 같다」 고 글로 갈음하면
    줄 수가 어긋난다. 그것은 옳은 처리이지 잘못이 아니다."""
    out = []
    for x in str(s or "").split(NL):
        y = RE_IMG.sub("", x).strip()
        if y:
            out.append(y)
    return out


def marks(s):
    return (len(RE_HANG.findall(s or "")), len(RE_HO.findall(s or "")),
            len(RE_PAREN.findall(s or "")), len(RE_GA.findall(s or "")))


def label(n):
    lv = n.get("level") or ""
    no = n.get("no")
    return ("제%s%s " % (no, lv or "조")) if no else ""


def main():
    md = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None
    lib = json.load(io.open(os.path.join(ROOT, "data", "library.json"),
                            encoding="utf-8"))
    nm = {r["id"]: r["name"] for r in lib["regulations"]}
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "loc*.json"))):
        rid = os.path.splitext(os.path.basename(p))[0]
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        ns = list(walk(d.get("tree") or []))
        if not any((n.get("transBody") or "").strip() for n, _ in ns):
            continue
        # 자료가 「간추림」 이라 밝힌 규정은 잣대를 달리한다.
        # ISO 19157-1 은 저작물을 그대로 옮겨 담지 아니하기로 하여, 규범
        # 마디는 간추리고 표제 마디에는 무엇을 다루는 대목인지만 적었다.
        # 그러므로 줄 수와 분량과 항 번호가 맞지 아니하는 것이 정상이다.
        # 이것을 모르고 재면 250건이 헛경보로 나온다.
        brief = (d.get("transMode") == "간추림")
        skip = {str(x.get("title") or "").strip()
                for x in (d.get("transSkip") or []) if isinstance(x, dict)}
        for n, _path in ns:
            b = (n.get("body") or "").strip()
            t = (n.get("transBody") or "").strip()
            if not b and not t:
                continue
            if (n.get("title") or "").strip() in skip:
                continue                       # 옮기지 아니하기로 한 마디
            bad = []
            if b and not t:
                bad.append(("번역 없음", "%d자" % len(b), ""))
            elif t and not b:
                if not brief:
                    bad.append(("원문 없음", "", "%d자" % len(t)))
            elif brief:
                # 간추린 것에는 구조를 재지 아니한다. 참말 잘못만 본다.
                if b == t:
                    bad.append(("번역이 원문과 같음", "", ""))
                elif not RE_HANGUL.search(t):
                    bad.append(("번역에 한글이 없음", "", "%d자" % len(t)))
                elif len(b) * 3 < len(t):
                    bad.append(("간추린 것이 원문보다 긺", "%d자" % len(b), "%d자" % len(t)))
            else:
                lb, lt = len(lines(b)), len(lines(t))
                if lb != lt:
                    bad.append(("줄 수 다름", "%d줄" % lb, "%d줄" % lt))
                mb, mt = marks(b), marks(t)
                for i, what in enumerate(("①②③", "1.", "(1)", "가.")):
                    # 원문에 그 표가 하나도 없으면 견주지 아니한다.
                    # 일본 규정은 항을 「２」, 호를 「一 二 三」, 목을 「イ ロ ハ」
                    # 로 적는다. 우리말로 옮기면서 「2.」ㆍ「1)」ㆍ「가.」 로 바꾸는
                    # 것은 우리 법령 관례를 따른 것이지 잘못이 아니다.
                    if mb[i] and mb[i] != mt[i]:
                        bad.append(("%s 수 다름" % what, str(mb[i]), str(mt[i])))
                if b == t:
                    bad.append(("번역이 원문과 같음", "", ""))
                elif not RE_HANGUL.search(t):
                    bad.append(("번역에 한글이 없음", "", "%d자" % len(t)))
                elif len(t) * 3 < len(b):
                    bad.append(("번역이 너무 짧음", "%d자" % len(b), "%d자" % len(t)))
                elif len(b) * 3 < len(t):
                    bad.append(("번역이 너무 긺", "%d자" % len(b), "%d자" % len(t)))
            for kind, x, y in bad:
                rows.append({"규정": rid, "이름": nm.get(rid, rid),
                             "마디": (label(n) + (n.get("title") or "")).strip(),
                             "갈래": kind, "원문": x, "번역": y})

    print("살펴본 국외 규정 %d종, 짚인 자리 %d건"
          % (len({r["규정"] for r in rows}) if rows else 0, len(rows)))
    print()
    tab = collections.Counter((r["규정"], r["갈래"]) for r in rows)
    print("%-7s %-24s %5s" % ("규정", "갈래", "건"))
    for (rid, kind), c in sorted(tab.items(), key=lambda z: (z[0][0], -z[1])):
        print("%-7s %-24s %5d" % (rid, kind, c))
    print()
    kinds = collections.Counter(r["갈래"] for r in rows)
    print("갈래별 합계")
    for k, c in kinds.most_common():
        print("   %-24s %5d" % (k, c))

    if not md:
        print()
        print("표로 적으려면 --md 파일이름 을 붙일 것.")
        return
    L = ["# 국외 규정 번역 구조 점검", "",
         "글의 뜻이 맞는가는 기계가 가릴 수 없다. 구조만 세었다.", "",
         "짚인 자리 **%d건**." % len(rows), ""]
    for rid in sorted({r["규정"] for r in rows}):
        sub = [r for r in rows if r["규정"] == rid]
        L += ["", "## %s — %s (%d건)" % (rid, nm.get(rid, rid), len(sub)), "",
              "| 마디 | 갈래 | 원문 | 번역 |", "|---|---|---|---|"]
        for r in sub[:200]:
            L.append("| %s | %s | %s | %s |"
                     % (r["마디"][:40], r["갈래"], r["원문"], r["번역"]))
        if len(sub) > 200:
            L.append("| … | 그 밖에 %d건 | | |" % (len(sub) - 200))
    io.open(os.path.join(ROOT, md), "w", encoding="utf-8",
            newline=NL).write(NL.join(L) + NL)
    print()
    print("적었습니다 — %s" % md)


if __name__ == "__main__":
    main()
