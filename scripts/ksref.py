# -*- coding: utf-8 -*-
r"""규정에 인용된 한국산업표준(KS)을 뽑아 정리한다.

  python scripts\ksref.py                 화면에 정리해 보여 준다
  python scripts\ksref.py --md 파일.md     마크다운으로 적는다
  python scripts\ksref.py --all            측량과 무관해 보이는 것까지 모두

■ 어디를 뒤지는가

  data\*.json 의 규정 자료 전부 — 현행 규정(reg*)ㆍ개정안(draft*)ㆍ
  지침과 고시(loc*) — 의 조문 본문ㆍ제목ㆍ변경 사유, 그리고 본문에 딸린
  표(data\objects\*\*.xml).

  표준용어집과 용어사전은 규정이 아니므로 뒤지지 않는다. 다만 표준 번호에
  이름을 붙일 때 참고로 쓴다.

■ 무엇을 뽑는가

      KS X 3241            부문 한 글자 + 번호
      KS X ISO 19115-1     KS 로 받아들인 국제표준
      KS Q ISO 9001:2015   해 붙은 것

  'KS' 라는 낱말만 있고 번호가 없는 자리(예: 「한국산업표준(KS)」)는
  번호 없는 인용으로 따로 센다 — 어느 표준인지 규정이 밝히지 아니한 것이라
  그 자체가 살펴볼 거리다.
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
OBJ = os.path.join(DATA, "objects")

# KS + 부문(한 글자) + [ISO/IEC] + 번호[-가지][:해]
RE_KS = re.compile(
    r"KS\s*([A-Z])\s*(?:(ISO/IEC|ISO|IEC)\s*)?(\d{3,5})"
    r"((?:\s*-\s*\d+)*)(?:\s*:\s*(\d{4}))?")
# 번호 없이 이름만 부른 자리
RE_BARE = re.compile(r"한국산업표준|KS\s*(?:규격|표준|기준)|\(\s*KS\s*\)")
# 규정 자료가 아닌 것
SKIP = ("표준용어집", "용어사전", "library.json", "targets.json",
        "annex", "index.json")

# KS 부문 — 어느 분야의 표준인가
PART = {
    "A": "기본", "B": "기계", "C": "전기전자", "D": "금속", "E": "광산",
    "F": "건설", "G": "일용품", "H": "식료품", "I": "환경", "J": "생물",
    "K": "섬유", "L": "요업", "M": "화학", "P": "의료", "Q": "품질경영",
    "R": "수송기계", "S": "서비스", "T": "물류", "V": "조선", "W": "항공우주",
    "X": "정보", "Z": "기타",
}

# 측량과 이어지는 낱말 — 인용 자리의 앞뒤에서 찾는다
NEAR = ("측량", "좌표", "측지", "지형", "지도", "공간정보", "위성", "GNSS",
        "GPS", "항공사진", "영상", "레이저", "점군", "표고", "수준",
        "메타데이터", "품질", "정확도", "성과", "데이터", "파일", "포맷",
        "문자", "부호", "좌표계", "투영", "지오이드", "정합", "해상도")


def walk(ns):
    for n in ns or []:
        yield n
        yield from walk(n.get("children") or [])


def label(x):
    """조문을 부르는 이름"""
    no = x.get("legacyNo") or x.get("no") or ""
    ti = (x.get("title") or "").strip()
    lv = x.get("level") or ""
    s = " ".join(t for t in (str(no).strip(), ti) if t)
    return s or lv or x.get("id") or "(이름 없음)"


def ksname(m):
    """짝지은 것을 사람이 읽는 번호로"""
    part, org, num, dash, year = m.groups()
    tail = re.sub(r"\s*", "", dash or "")
    s = "KS %s %s%s%s" % (part, (org + " ") if org else "", num, tail)
    return s + (":%s" % year if year else ""), part


def around(text, i, j, span=60):
    a = max(0, i - span)
    b = min(len(text), j + span)
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("…" if a else "") + s + ("…" if b < len(text) else "")


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(s or ""))).strip()


def texts_of(node):
    """한 조문에서 글이 될 만한 자리 — (어디, 글)"""
    for k, ko in (("title", "제목"), ("body", "본문"), ("reason", "변경 사유"),
                  ("note", "적바림")):
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            yield ko, strip_tags(v)


def obj_texts(regid, node):
    """본문에 딸린 표 — <img id="…"> 가 가리키는 XML"""
    ids = re.findall(r'<img id="([\w.-]+)"', str(node.get("body") or ""))
    for oid in ids:
        p = os.path.join(OBJ, regid, oid + ".xml")
        if os.path.exists(p):
            yield "표 " + oid, strip_tags(io.open(p, encoding="utf-8").read())


def books():
    """뒤질 규정 자료 — (파일, 규정 이름, objects 자리)"""
    out = []
    for f in sorted(os.listdir(DATA)):
        if not f.endswith(".json") or any(s in f for s in SKIP):
            continue
        p = os.path.join(DATA, f)
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or "tree" not in d:
            continue
        name = d.get("title") or d.get("label") or os.path.splitext(f)[0]
        regid = d.get("id") or os.path.splitext(f)[0]
        out.append((f, name, d, regid))
    return out


def main():
    want_all = "--all" in sys.argv
    md = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None

    hits = {}          # 표준 번호 → [(규정, 조문, 어디, 앞뒤)]
    bare = []          # 번호 없는 인용
    for f, name, d, regid in books():
        revs = [d] + list(d.get("next") or [])
        for rev in revs:
            rname = rev.get("title") or name
            for x in walk(rev.get("tree")):
                places = list(texts_of(x)) + list(obj_texts(regid, x))
                for where, t in places:
                    for m in RE_KS.finditer(t):
                        key, part = ksname(m)
                        ctx = around(t, m.start(), m.end())
                        hits.setdefault(key, []).append(
                            (rname, label(x), where, ctx, part))
                    if not RE_KS.search(t):
                        for m in RE_BARE.finditer(t):
                            bare.append((rname, label(x), where,
                                         around(t, m.start(), m.end())))

    # 측량과 이어지는 것만 남긴다 — 앞뒤 어디엔가 관련 낱말이 있으면 남긴다
    def near(rows):
        return any(any(w in c for w in NEAR) for _r, _l, _w, c, _p in rows)

    keep = {k: v for k, v in hits.items() if want_all or near(v)}
    drop = {k: v for k, v in hits.items() if k not in keep}

    L = []

    def p(s=""):
        print(s)
        L.append(s)

    p("# 규정에 인용된 한국산업표준(KS)")
    p()
    p("자료 : `App\\prototype\\data` 의 규정 %d권 (현행ㆍ개정안ㆍ지침)"
      % len(books()))
    p()
    if not keep:
        p("측량과 이어지는 KS 인용을 찾지 못했습니다.")
    def sort_key(k):
        return (0 if "ISO" not in k else 1, k)

    for key in sorted(keep, key=sort_key):
        rows = keep[key]
        part = rows[0][4]
        # 본문에 박힌 것이 규범이고, 변경 사유에 적힌 것은 설명이다
        norm = [r for r in rows if r[2] in ("본문", "제목") or r[2].startswith("표 ")]
        note = [r for r in rows if r not in norm]
        p("## %s  〔%s 부문〕" % (key, PART.get(part, part)))
        p()
        p("규범 인용 %d곳 · 사유에 적은 것 %d곳" % (len(norm), len(note)))
        p()
        for title, rows2 in (("규정이 따르도록 한 자리", norm),
                             ("변경 사유에서 든 자리", note)):
            if not rows2:
                continue
            p("**%s**" % title)
            p()
            # 똑같은 글이 여러 조문에 붙어 있으면(상투구) 한 번만 보이고 센다
            byctx = {}
            for rname, lab, where, ctx, _p in rows2:
                byctx.setdefault(ctx, []).append((rname, lab, where))
            for ctx, who in sorted(byctx.items(), key=lambda z: -len(z[1])):
                rname, lab, where = who[0]
                more = (" 〔같은 글이 %d곳에 더 있음〕" % (len(who) - 1)
                        if len(who) > 1 else "")
                p("- **%s** %s (%s)%s" % (rname[:38], lab, where, more))
                p("  - %s" % ctx)
            p()
    if drop and not want_all:
        p("## 측량과 이어지지 아니해 보여 뺀 것")
        p()
        for key in sorted(drop):
            p("- %s (%d곳) — `--all` 을 주면 함께 나옵니다" % (key, len(drop[key])))
        p()
    if bare:
        p("## 번호 없이 부른 자리 — %d곳" % len(bare))
        p()
        p("어느 표준인지 규정이 밝히지 아니한 자리입니다. 개정할 때 번호를 "
          "박아 두면 다투지 아니합니다.")
        p()
        seen = set()
        for rname, lab, where, ctx in bare:
            k = (rname, lab, ctx)
            if k in seen:
                continue
            seen.add(k)
            p("- **%s** %s (%s)" % (rname[:38], lab, where))
            p("  - %s" % ctx)

    if md:
        io.open(md, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
        print()
        print("적었습니다 — %s" % md)


if __name__ == "__main__":
    main()
