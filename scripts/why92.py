# -*- coding: utf-8 -*-
r"""사유가 조문과 어긋난 조를 모아, 무엇이 바뀌었는지 뽑아 준다.

■ 무엇을 하는가

  「현행의 문제」에 「고칠 것이 없음」이라 적혔는데 본문은 참말 바뀐 조를
  모은다. 조마다 현행과 개정안을 **항 단위로** 맞대어, 무엇이 늘고 줄고
  바뀌었는지 적는다.

  사유 글은 기계가 대신 쓸 수 없다. 그러나 무엇이 바뀌었는지는 셀 수 있다.
  그것만 대어 주면 사람이 채우기 쉽다.

■ 어떻게 맞대는가

  ㆍ 항 표시(①②③…)로 끊는다. 없으면 줄로 끊는다.
  ㆍ 줄 끝 공백만 다듬고 견준다. **낱말 사이 공백은 건드리지 아니한다** ——
    「지도 등」과 「지도등」의 차이가 바로 그 공백이다. 공백을 지우고 견주면
    변경이 통째로 사라진다(fixstatus9.py 의 함정).
  ㆍ 바뀐 항은 글자 단위로 한 번 더 갈라, 무엇이 무엇으로 되었는지 적는다.

■ 내는 것

  scripts\..\현행의문제_보완.md

  python scripts\why92.py            간추려 보여 준다
  python scripts\why92.py --md       표로 적는다
"""
import io
import json
import os
import re
import sys
import difflib
import collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
OUT = os.path.join(ROOT, "현행의문제_보완.md")

SETS = [("작업규정", "data/draft2025.json", "data/reg01.json"),
        ("성과심사", "data/draft_simsa.json", "data/reg29.json"),
        ("무인비행장치", "data/draft_uav.json", "data/reg12.json")]
NOPROB = ("고칠 사유가 확인되지 않았음", "지적된 것이 없음", "짚은 마디가 따로 없음",
          "고칠 것이 없음", "고칠 것이 없고")
HEAD = re.compile(r"^\s*○\s*([^:：]{2,20})\s*[:：]\s*(.*)$")
HANG = re.compile(r"(?=[①-⑳])")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def revs_of(d):
    nx = d.get("next")
    return [d] + (nx if isinstance(nx, list) else ([nx] if isinstance(nx, dict) else []))


def tidy(s):
    return NL.join(x.rstrip() for x in str(s or "").split(NL)).strip()


def parts(body):
    """항 표시로 끊는다. 없으면 줄로."""
    t = tidy(body)
    if not t:
        return []
    p = [x.strip() for x in HANG.split(t) if x.strip()]
    if len(p) > 1:
        return p
    return [x.strip() for x in t.split(NL) if x.strip()]


def secs(n):
    out, k = {}, None
    for ln in (n.get("reason") or "").split(NL):
        m = HEAD.match(ln)
        if m:
            k = m.group(1).strip()
            out.setdefault(k, [])
            if m.group(2).strip():
                out[k].append(m.group(2).strip())
        elif k and ln.strip():
            out[k].append(ln.strip())
    return out


def cut(s, n=64):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def diff_hang(a, b):
    """항 단위 견주기 → [(갈래, 현행, 개정)]"""
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            for x in b[j1:j2]:
                out.append(("보탬", "", x))
        elif tag == "delete":
            for x in a[i1:i2]:
                out.append(("뺌", x, ""))
        else:
            for k in range(max(i2 - i1, j2 - j1)):
                x = a[i1 + k] if i1 + k < i2 else ""
                y = b[j1 + k] if j1 + k < j2 else ""
                out.append(("고침" if x and y else ("보탬" if y else "뺌"), x, y))
    return out


def inner(x, y):
    """바뀐 항 안에서 무엇이 무엇으로 되었는가"""
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y).get_opcodes():
        if tag == "equal":
            continue
        out.append((x[i1:i2], y[j1:j2]))
    return out


def main():
    md = "--md" in sys.argv
    rows = []
    for name, dp, cp in SETS:
        cur = json.load(io.open(os.path.join(ROOT, cp), encoding="utf-8"))
        old = {}
        for n in walk(cur["tree"]):
            if n.get("level") == "조" and n.get("no"):
                old[int(n["no"])] = n
        doc = json.load(io.open(os.path.join(ROOT, dp), encoding="utf-8"))
        for ri, rev in enumerate(revs_of(doc)):
            for n in walk(rev.get("tree") or []):
                if n.get("level") != "조":
                    continue
                st = n.get("status") or "유지"
                if st in ("유지", "이동", "삭제"):
                    continue
                t = " ".join(secs(n).get("현행의 문제") or [])
                if not any(x in t for x in NOPROB):
                    continue
                # legacyNo 는 「제46조」 이기도 하고 「별표 46」 이기도 하다.
                # 숫자만 뽑으면 별표 46 이 제46조로 둔갑한다. 조일 때만 본다.
                lg = str(n.get("legacyNo") or "")
                m = re.match(r"^\s*제?\s*(\d+)\s*조", lg)
                o = old.get(int(m.group(1))) if m else None
                a = parts(o.get("body")) if o else []
                b = parts(n.get("body"))
                if o and tidy(o.get("body")) == tidy(n.get("body")) \
                        and tidy(o.get("title")) == tidy(n.get("title")):
                    continue                      # 글자까지 같으면 상태 문제이지 사유 문제가 아니다
                rows.append({
                    "규정": name, "판": ri, "상태": st, "조": n.get("no"),
                    "제목": n.get("title") or "", "현행": n.get("legacyNo") or "",
                    "현행제목": (o.get("title") if o else ""),
                    "현행자": len(tidy(o.get("body"))) if o else 0,
                    "개정자": len(tidy(n.get("body"))),
                    "현행항": len(a), "개정항": len(b),
                    "차이": diff_hang(a, b) if o else [("신설", "", x) for x in b],
                    "사유": t,
                    "본문": tidy(n.get("body")),
                })

    # 한 현행 조를 여러 개정 조가 가리키면 갈린 것이다. 이때 항을 맞대면
    # 엉뚱한 짝이 생겨 「고침 | 지역은 | (없음)」 같은 부스러기만 나온다.
    fam = collections.Counter((r["규정"], r["현행"]) for r in rows if r["현행"])
    for r in rows:
        r["갈림"] = fam.get((r["규정"], r["현행"]), 0) if r["현행"] else 0
        if r["갈림"] > 1:
            r["형제"] = sorted(x["조"] for x in rows
                               if x["규정"] == r["규정"] and x["현행"] == r["현행"])

    print("사유가 조문과 어긋난 조 %d개" % len(rows))
    c = collections.Counter((r["규정"], r["상태"]) for r in rows)
    print()
    print("%-14s %-10s %5s" % ("규정", "상태", "조"))
    for (nm, st), k in c.most_common():
        print("%-14s %-10s %5d" % (nm, st, k))
    print()
    big = sorted(rows, key=lambda r: -(abs(r["개정자"] - r["현행자"])))[:10]
    print("글자가 가장 많이 달라진 열")
    for r in big:
        print("   %-12s 제%-4s조 %-26s %5d자 → %5d자 (항 %d → %d)"
              % (r["규정"], r["조"], cut(r["제목"], 26), r["현행자"], r["개정자"],
                 r["현행항"], r["개정항"]))
    if not md:
        print()
        print("표로 적으려면 --md 를 붙일 것 — %s" % os.path.relpath(OUT, ROOT))
        return

    L = ["# 「현행의 문제」 보완이 필요한 조 — 변경 내역", "",
         "「현행의 문제」에 「고칠 것이 없음」 이라 적혔으나 본문이 참말 바뀐 조이다.",
         "무엇이 바뀌었는지만 기계가 뽑았다. 사유 글은 사람이 채워야 한다.", "",
         "항 표시(①②③)로 끊어 맞대었다. 줄 끝 공백만 다듬고 견주었다 —",
         "낱말 사이 공백을 지우면 「지도 등 → 지도등」 같은 변경이 사라진다.", "",
         "총 **%d개** 조." % len(rows), ""]
    for nm in ("작업규정", "성과심사", "무인비행장치"):
        sub = [r for r in rows if r["규정"] == nm]
        if not sub:
            continue
        L += ["", "## %s (%d개)" % (nm, len(sub)), ""]
        for r in sorted(sub, key=lambda z: (z["판"], z["조"] or 0)):
            L += ["### 제%s조 %s  [%s]%s" % (r["조"], r["제목"], r["상태"],
                                             "  (%d판)" % (r["판"] + 1) if r["판"] else ""),
                  "",
                  "- 현행 %s%s — %d자 %d항 → 개정 %d자 %d항"
                  % (r["현행"] or "(없음)",
                     "(%s)" % r["현행제목"] if r["현행제목"] else "",
                     r["현행자"], r["현행항"], r["개정자"], r["개정항"]),
                  "- 지금 적힌 사유 : %s" % cut(r["사유"], 90), ""]
            if r.get("갈림", 0) > 1:
                L += ["- **한 조가 여러 조로 갈렸음** — 현행 %s 하나를 제%s조로 나눔."
                      % (r["현행"], "조 · 제".join(str(x) for x in r["형제"])),
                      "  갈린 조문은 항을 맞대어도 뜻이 없으므로 이 조가 맡은 대목만 적는다.",
                      "", "  이 조가 맡은 대목 : %s" % cut(r["본문"], 130), ""]
                continue
            if not r["차이"]:
                L += ["  변경 없음(제목만 바뀜).", ""]
                continue
            L += ["| 갈래 | 현행 | 개정 |", "|---|---|---|"]
            for kind, x, y in r["차이"][:12]:
                if kind == "고침":
                    for xa, yb in inner(x, y)[:3]:
                        L.append("| 고침 | %s | %s |" % (cut(xa, 46) or "(없음)",
                                                        cut(yb, 46) or "(없음)"))
                else:
                    L.append("| %s | %s | %s |" % (kind, cut(x, 46), cut(y, 46)))
            if len(r["차이"]) > 12:
                L.append("| … | 그 밖에 %d 자리 | |" % (len(r["차이"]) - 12))
            L.append("")
    io.open(OUT, "w", encoding="utf-8", newline=NL).write(NL.join(L) + NL)
    print()
    print("적었습니다 — %s (%d줄)" % (os.path.relpath(OUT, ROOT), len(L)))


if __name__ == "__main__":
    main()
