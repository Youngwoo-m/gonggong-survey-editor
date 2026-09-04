# -*- coding: utf-8 -*-
r"""서고에 넣은 연구보고서(loc30)를 제대로 색인한다.

addreport.py 는 차례를 읽어 마디만 세웠다. 그것만으로는 다른 참조규정처럼
쓰이지 아니한다. 빠진 것이 넷이다.

  ㉠ 조에 번호가 없다        모두 0 이라 화면이 조문을 부르지 못한다.
  ㉡ 표가 하나도 없다         예순 남짓한 표가 글줄로 풀려 본문에 섞여 있다.
  ㉢ 본문에 장 제목이 겹친다   쪽 머리말과 제 제목이 글 앞에 되풀이된다.
  ㉣ manifest 에 없다         화면이 개체를 찾을 자리를 알지 못한다.

이 도구가 넷을 채운다.

■ 표를 어떻게 뽑는가

  PDF 에는 표가 선과 글자로만 있다. PyMuPDF 의 find_tables() 로 칸을 잡아
  다른 규정과 같은 꼴의 개체 XML 로 적는다.

      data\objects\loc30\loc30-t<쪽>-<차례>.xml
        <table id rows cols article source><row><cell col row>…

  본문에서는 표가 있던 자리에 <img id="…"> 를 놓아 차례를 지킨다. 글은
  표 칸을 뺀 나머지 덩이에서 모은다 — 그러지 아니하면 표가 두 번 나온다.

  python scripts\indexreport.py            무엇을 할지 보여만 준다
  python scripts\indexreport.py --write    자료에 적는다
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
OFFSET = 14

# 쪽마다 되풀이되는 머리말 — 띄어쓰기가 없어 통째로 견준다
RUNNING = ("디지털기반지도등간행심사제도개선및효율화방안연구",)
RE_CHAPHEAD = re.compile(r"^제\d+장[가-힣ㆍ·A-Za-z0-9()\[\]/,.\s]{0,60}$")
RE_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
RE_IMG = re.compile(r'<img id="[\w.-]+"></img>')


def clean(s):
    s = RE_CTRL.sub(" ", str(s or ""))
    s = re.sub(r"[ \t]+", " ", s)
    return NL.join(x.strip() for x in s.split(NL)).strip()


def esc(s):
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def page_parts(page, pno):
    """한 쪽 → [('글', 글) | ('표', [[칸,…],…])] 를 위에서 아래 차례로"""
    try:
        tabs = list(page.find_tables().tables)
    except Exception:
        tabs = []
    boxes = [t.bbox for t in tabs]
    items = []
    for t in tabs:
        rows = [[("" if c is None else str(c)).replace(NL, " ").strip()
                 for c in r] for r in t.extract()]
        items.append((t.bbox[1], "표", rows))
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
        # 표 칸 안에 든 덩이는 건너뛴다 — 표로 이미 담았다
        if any(not (x1 < bx0 or x0 > bx2 or y1 < by0 or y0 > by3)
               for bx0, by0, bx2, by3 in boxes):
            continue
        items.append((y0, "글", txt))
    items.sort(key=lambda z: z[0])
    return [(k, v) for _y, k, v in items]


def strip_noise(line, title):
    s = line.strip()
    if not s or s.isdigit():
        return ""
    flat = re.sub(r"\s", "", s)
    if flat in RUNNING or (RE_CHAPHEAD.match(flat) and len(flat) < 60):
        return ""
    if title and flat == re.sub(r"\s", "", title):
        return ""
    return s


def main():
    write = "--write" in sys.argv
    import fitz
    if not os.path.exists(PDF):
        sys.exit("보고서를 찾지 못했습니다")
    doc = json.load(io.open(os.path.join(DATA, SID + ".json"), encoding="utf-8"))
    pdf = fitz.open(PDF)

    # 마디마다 인쇄 쪽 범위를 되찾는다 — addreport 가 쓴 차례 순서를 그대로 쓴다
    leaves = [x for x in walk(doc["tree"]) if x.get("level") == "조"]
    # 쪽 범위는 본문 첫 줄이 실린 쪽을 찾아 다시 잡는다
    spans, n = [], len(pdf)
    heads = []
    flat = [re.sub(r"\s", "", pdf[i - 1].get_text()) for i in range(1, n + 1)]
    # 차례는 문서 차례 그대로이므로 **앞 마디를 찾은 쪽 다음부터** 훑는다.
    # 그러지 아니하면 뒤 마디의 제목 조각이 앞쪽에서 먼저 걸린다.
    cur = 1
    for x in leaves:
        tt = re.sub(r"\s", "", x.get("title") or "")
        pg = None
        # 온 제목 ㆍ 앞머리 열 글자 ㆍ 뒤꼬리 열 글자 차례로 견준다.
        # 차례가 제목을 줄여 적은 자리가 있다 —
        # 「나. POI 데이터 심사효율화 방안」 은 본문에서
        # 「나. POI(관심지점, point-of-interest) 데이터 심사효율화 방안」 이다.
        for key in (tt, tt[:10], tt[-10:]):
            if not key:
                continue
            for i in range(cur, n + 1):
                if key in flat[i - 1]:
                    pg = i
                    break
            if pg:
                break
        if pg:
            cur = pg
        heads.append(pg)
    for i, x in enumerate(leaves):
        a = heads[i]
        b = next((heads[j] for j in range(i + 1, len(heads)) if heads[j]), n + 1)
        spans.append((x, a, b if (a and b and b > a) else (a + 1 if a else None)))

    objs, made, n_tbl = {}, [], 0
    for x, a, b in spans:
        if not a:
            made.append((x, 0, 0))
            continue
        lines, seq = [], 0
        for p in range(a, min(b, n + 1)):
            for kind, val in page_parts(pdf[p - 1], p):
                if kind == "글":
                    for ln in str(val).split(NL):
                        s = strip_noise(ln, x.get("title"))
                        if s:
                            lines.append(s)
                else:
                    seq += 1
                    oid = "%s-t%d-%d" % (SID, p, seq)
                    objs[oid] = (val, x.get("title") or "")
                    lines.append('<img id="%s"></img>' % oid)
                    n_tbl += 1
        body = clean(NL.join(lines))
        made.append((x, len(RE_IMG.sub("", body)), len(RE_IMG.findall(body))))
        x["_body"] = body

    print("마디 %d개 · 표 %d개" % (len(leaves), n_tbl))
    print()
    print("%-46s %8s %5s" % ("마디", "글", "표"))
    for x, c, t in made[:14]:
        print("%-46s %8d %5d" % ((x.get("title") or "")[:46], c, t))
    if len(made) > 14:
        print("… 그 밖에 %d마디" % (len(made) - 14))
    miss = [x.get("title") for x, a, b in spans if not a]
    if miss:
        print()
        print("쪽을 못 찾은 마디 %d개 : %s" % (len(miss), ", ".join(m[:26] for m in miss)))

    if not write:
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")
        return

    # ── 본문과 조 번호
    no = 0
    for x in walk(doc["tree"]):
        if x.get("level") != "조":
            continue
        no += 1
        x["no"] = no
        if "_body" in x:
            x["body"] = x.pop("_body")

    # ── 개체
    d = os.path.join(DATA, "objects", SID)
    os.makedirs(d, exist_ok=True)
    idx = {}
    for oid, (rows, art) in objs.items():
        cols = max(len(r) for r in rows) if rows else 0
        L = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<table id="%s" article="%s" rows="%d" cols="%d" source="%s">'
             % (esc(oid), esc(art), len(rows), cols, esc(os.path.basename(PDF)))]
        for ri, r in enumerate(rows):
            L.append("  <row>")
            for ci, c in enumerate(r):
                L.append('    <cell col="%d" row="%d">%s</cell>' % (ci, ri, esc(c)))
            L.append("  </row>")
        L.append("</table>")
        io.open(os.path.join(d, oid + ".xml"), "w", encoding="utf-8",
                newline=NL).write(NL.join(L) + NL)
        head = " | ".join(str(c) for c in (rows[0] if rows else []))[:60]
        idx[oid] = {"kind": "table", "article": art,
                    "rows": len(rows), "cols": cols, "preview": head}
    io.open(os.path.join(d, "index.json"), "w", encoding="utf-8",
            newline=NL).write(json.dumps(idx, ensure_ascii=False))

    mfp = os.path.join(DATA, "objects", "manifest.json")
    mf = json.load(io.open(mfp, encoding="utf-8"))
    mf[SID] = {"index": True, "annex": False}
    io.open(mfp, "w", encoding="utf-8", newline=NL).write(
        json.dumps(mf, ensure_ascii=False))

    doc["stats"]["조"] = no
    io.open(os.path.join(DATA, SID + ".json"), "w", encoding="utf-8",
            newline=NL).write(json.dumps(doc, ensure_ascii=False))
    print()
    print("색인했습니다 — 조 %d개 · 표 개체 %d개 · manifest 등록" % (no, len(idx)))


if __name__ == "__main__":
    main()
