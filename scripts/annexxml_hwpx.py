# -*- coding: utf-8 -*-
r"""별표ㆍ별지의 한/글 원본(.hwpx)에서 표를 읽어 XML 로 바꾼다.

■ 왜 다시 만드는가

  여태 이 XML 은 국가법령정보센터에서 받은 **옛 이진 HWP** 를 손수 풀어
  만든 것이었다(genannexxml.py + hwp5.py). 이진 파일을 짐작으로 읽는 일이라
  칸 병합이나 빈 칸에서 어긋나는 자리가 있었고, 아예 만들지 못한 별표도
  서른넷이나 되었다.

  원본을 모두 .hwpx 로 바꾸었으므로 이제 짐작할 것이 없다. HWPX 는
  ZIP + XML 이고 표가 이미 XML 로 적혀 있다.

      <hp:tbl rowCnt colCnt>
        <hp:tr><hp:tc><hp:cellAddr colAddr rowAddr/>
                      <hp:cellSpan colSpan rowSpan/> … <hp:t>글</hp:t>

  그것을 그대로 옮긴다.

■ 어디에 넣는가

  화면(ui/detail.js 의 _annexTables)이 찾는 자리와 열쇠를 그대로 따른다.

      신설      data/objects/<개정안 id>/annex/<구분><번호>.xml
      그 밖     data/objects/<현행 규정 id>/annex/<현행 번호>.xml

  칸 안에 또 표가 있어도 속지 않도록 깊이를 세어 겉 표만 센다.

  python scripts\annexxml_hwpx.py            무엇을 만들지 보여만 준다
  python scripts\annexxml_hwpx.py --write    자료에 적는다
  python scripts\annexxml_hwpx.py --write --only draftUav
"""
import io
import json
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OBJ = os.path.join(DATA, "objects")

# (개정안 파일, 개정안 id, 현행 규정 id)
BOOKS = [("draft2025.json", "draft2025", "reg01"),
         ("draft_simsa.json", "draftSimsa", "reg29"),
         ("draft_uav.json", "draftUav", "reg12")]

RE_T = re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", re.S)


def unesc(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))


def esc(s):
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def match_close(x, pos, open_tag, close_tag):
    """짝이 맞는 닫는 태그 자리 — 표 안에 또 표가 있어도 속지 않는다"""
    depth, i = 0, pos
    while True:
        a = x.find(open_tag, i)
        b = x.find(close_tag, i)
        if b < 0:
            return len(x)
        if 0 <= a < b:
            depth += 1
            i = a + len(open_tag)
            continue
        if depth == 0:
            return b
        depth -= 1
        i = b + len(close_tag)


def spans(x, open_tag, close_tag, start=0, end=None):
    """겉 태그의 (시작, 끝) 목록"""
    end = len(x) if end is None else end
    out, i = [], start
    while True:
        s = x.find(open_tag, i)
        if s < 0 or s >= end:
            return out
        e = match_close(x, s + len(open_tag), open_tag, close_tag) + len(close_tag)
        out.append((s, e))
        i = e


def cell_text(tc):
    """칸의 글 — 속 표의 글은 빼고 이 칸의 문단만 모은다"""
    inner = spans(tc, "<hp:tbl ", "</hp:tbl>")
    keep, last = [], 0
    for s, e in inner:
        keep.append(tc[last:s])
        last = e
    keep.append(tc[last:])
    body = "".join(keep)
    out = [unesc(m.group(1)) for m in RE_T.finditer(body)]
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


def tables_of(path):
    """hwpx → [{rows, cols, cells:[{col,row,cs,rs,text}]}] (겉 표만)"""
    with zipfile.ZipFile(path) as z:
        secs = sorted(n for n in z.namelist()
                      if re.match(r"Contents/section\d+\.xml$", n))
        xml = "".join(z.read(n).decode("utf-8") for n in secs)
    out = []
    for s, e in spans(xml, "<hp:tbl ", "</hp:tbl>"):
        tbl = xml[s:e]
        head = tbl[:tbl.find(">") + 1]
        rc = re.search(r'rowCnt="(\d+)"', head)
        cc = re.search(r'colCnt="(\d+)"', head)
        cells = []
        for rs_, re_ in spans(tbl, "<hp:tr>", "</hp:tr>"):
            for cs_, ce_ in spans(tbl, "<hp:tc ", "</hp:tc>", rs_, re_):
                tc = tbl[cs_:ce_]
                addr = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"', tc)
                span = re.search(r'<hp:cellSpan colSpan="(\d+)" rowSpan="(\d+)"', tc)
                if not addr:
                    continue
                cells.append({"col": int(addr.group(1)), "row": int(addr.group(2)),
                              "cs": int(span.group(1)) if span else 1,
                              "rs": int(span.group(2)) if span else 1,
                              "text": cell_text(tc)})
        if not cells:
            continue
        out.append({"rows": int(rc.group(1)) if rc else
                    (max(c["row"] for c in cells) + 1),
                    "cols": int(cc.group(1)) if cc else
                    (max(c["col"] for c in cells) + 1),
                    "cells": cells})
    return out


def to_xml(key, gubun, no, title, source, tbls):
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<annex id="%s" gubun="%s" no="%s" title="%s" source="%s">'
         % (esc(key), esc(gubun), esc(no), esc(title), esc(source))]
    for t in tbls:
        L.append('  <table rows="%d" cols="%d">' % (t["rows"], t["cols"]))
        byrow = {}
        for c in t["cells"]:
            byrow.setdefault(c["row"], []).append(c)
        for r in sorted(byrow):
            L.append("    <row>")
            for c in sorted(byrow[r], key=lambda z: z["col"]):
                at = 'col="%d" row="%d"' % (c["col"], c["row"])
                if c["cs"] > 1:
                    at += ' colspan="%d"' % c["cs"]
                if c["rs"] > 1:
                    at += ' rowspan="%d"' % c["rs"]
                L.append("      <cell %s>%s</cell>" % (at, esc(c["text"])))
            L.append("    </row>")
        L.append("  </table>")
    L.append("</annex>")
    return "\n".join(L) + "\n"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    made, skip, fail = {}, 0, []
    touched = set()
    for f, draftid, baseid in BOOKS:
        doc = json.load(io.open(os.path.join(DATA, f), encoding="utf-8"))
        for rev in [doc] + list(doc.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a or not a.get("hwpx"):
                    continue
                gubun = a.get("gubun") or "별표"
                no = str(a.get("no"))
                # 화면이 찾는 열쇠 그대로
                if x.get("status") == "신설":
                    reg, key = draftid, "%s%s" % (gubun, no)
                else:
                    reg = baseid
                    key = str(x.get("legacyNo") or "%s%s" % (gubun, no))
                key = re.sub(r"\s+", "", key)
                if only and reg != only:
                    continue
                src = os.path.join(ROOT, a["hwpx"])
                if not os.path.exists(src):
                    fail.append((reg, key, "원본이 없음"))
                    continue
                try:
                    tbls = tables_of(src)
                except Exception as err:
                    fail.append((reg, key, str(err)[:44]))
                    continue
                if not tbls:
                    skip += 1
                    continue
                made[(reg, key)] = (gubun, no, x.get("title") or "",
                                    a["hwpx"], tbls)
                touched.add(reg)

    print("표를 뽑은 별표ㆍ별지 %d개 · 표가 없는 것 %d · 못 읽은 것 %d"
          % (len(made), skip, len(fail)))
    for r in fail[:8]:
        print("   ! %-11s %-9s %s" % r)
    if not write:
        print()
        print("자리별로 몇 개인지")
        cnt = {}
        for (reg, _k) in made:
            cnt[reg] = cnt.get(reg, 0) + 1
        for k in sorted(cnt):
            print("   %-12s %d개" % (k, cnt[k]))
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")
        return

    for (reg, key), (gubun, no, title, src, tbls) in made.items():
        d = os.path.join(OBJ, reg, "annex")
        os.makedirs(d, exist_ok=True)
        io.open(os.path.join(d, key + ".xml"), "w",
                encoding="utf-8", newline="\n").write(
            to_xml(key, gubun, no, title, src, tbls))

    # 자리마다 색인을 다시 짓는다 — 손으로 넣은 것이 있을 수 있어 합쳐 쓴다
    for reg in sorted(touched):
        p = os.path.join(OBJ, reg, "annex-index.json")
        idx = {}
        if os.path.exists(p):
            try:
                idx = json.load(io.open(p, encoding="utf-8"))
            except Exception:
                idx = {}
        for (r2, key), (gubun, no, title, src, tbls) in made.items():
            if r2 != reg:
                continue
            idx[key] = {"file": key + ".xml", "title": title,
                        "tables": len(tbls),
                        "rows": max(t["rows"] for t in tbls),
                        "cols": max(t["cols"] for t in tbls)}
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(idx, ensure_ascii=False))
        print("   %-12s 색인 %d개" % (reg, len(idx)))
    print()
    print("자료에 적었습니다.")


if __name__ == "__main__":
    main()
