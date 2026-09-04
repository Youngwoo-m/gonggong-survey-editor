# -*- coding: utf-8 -*-
r"""서고의 ISO 표준 색인을 XML 로 내어 놓는다.

■ 왜 XML 인가

  ISO 표준은 유료 저작물이라 원문 파일을 받을 수 없다. `관련규정` 의 다른
  103종은 hwpx 와 pdf 를 갖추었으나 ISO 두 건만 빈자리로 남았다. 서고가
  지닌 색인을 XML 로 적어 그 자리를 채운다.

  꼴은 `data\objects` 의 개체 XML 과 결을 맞추었다. 속성으로 서지사항을
  적고, 조문 나무를 `node` 로 겹쳐 적는다.

■ 본문을 담는 기준

  loc17 ISO 17123 시리즈
      서지사항과 적용 대상만 있고 표준 본문이 없다. 통째로 적는다.

  loc29 ISO 19157-1:2023
      본문 색인이 163조까지 들어 있다. 자료 자체에 다음이 적혀 있다.

          localOnly  : true
          copyright  : © ISO 2023. 저작권이 있는 유료 표준이므로
                       원본과 이 색인은 저장소에 올리지 아니한다.

      그러므로 두 벌로 나눈다.

          관련규정\국외관련규정\        목차만 (본문 없음)
          공간정보표준\ISO19157\        전문 — 구입한 원본 PDF 가 있는 곳

      본문을 담은 XML 은 원본과 같은 자리에 둔다. 그 폴더가 이미 이
      컴퓨터에만 두기로 한 자리이며, 배포용 묶음은 `prototype` 만 담으므로
      밖으로 나가지 아니한다.

  python scripts\isoxml.py            무엇을 적을지 보여만 준다
  python scripts\isoxml.py --write    적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
NL = chr(10)

BOX = os.path.join(APP, "관련규정", "국외관련규정")
LOCAL = os.path.join(APP, "공간정보표준", "ISO19157")

# (서고 id, 낼 자리, 파일 이름, 본문을 담는가)
JOBS = [
    ("loc17", BOX, "ISO 17123 시리즈 (측량기기 현장 시험방법) 색인.xml", True),
    ("loc29", BOX, "ISO 19157-1_2023 (공간정보 데이터 품질) 목차.xml", False),
    ("loc29", LOCAL, "ISO_19157-1_2023 색인 전문.xml", True),
]
RE_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
HEAD = ("id", "name", "org", "kind", "no", "promulgated", "effective",
        "lang", "category", "indexMode")


def esc(s):
    # `str(s or "")` 로 적으면 숫자 0 이 빈 값이 된다. 셈이 0 인 갈래
    # (장ㆍ절ㆍ관)가 빈칸으로 나가므로 None 만 걸러야 한다.
    s = RE_CTRL.sub("", "" if s is None else str(s))
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def node_xml(n, out, dep, body):
    pad = "  " * dep
    at = ['level="%s"' % esc(n.get("level") or "")]
    for k in ("id", "no", "branch"):
        v = n.get(k)
        if v not in (None, "", 0):
            at.append('%s="%s"' % (k, esc(v)))
    at.append('title="%s"' % esc(n.get("title")))
    kids = n.get("children") or []
    txt = (n.get("body") or "") if body else ""
    if not txt and not kids:
        out.append("%s<node %s/>" % (pad, " ".join(at)))
        return
    out.append("%s<node %s>" % (pad, " ".join(at)))
    if txt:
        out.append("%s  <body>%s</body>" % (pad, esc(txt)))
    for k in kids:
        node_xml(k, out, dep + 1, body)
    out.append("%s</node>" % pad)


def build(rid, body):
    d = json.load(io.open(os.path.join(ROOT, "data", rid + ".json"),
                          encoding="utf-8"))
    at = " ".join('%s="%s"' % (k, esc(d.get(k))) for k in HEAD if d.get(k))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           "<!-- 서고 %s 의 색인. 편집기 자료 data/%s.json 에서 뽑았다. -->"
           % (rid, rid),
           "<!-- bodyIncluded 는 서고 색인의 설명글을 담았는지를 뜻한다."
           " ISO 표준 본문은 어느 쪽에도 담기지 아니한다. -->",
           '<regulation %s bodyIncluded="%s">' % (at, "예" if body else "아니오")]
    for k, tag in (("source", "source"), ("note", "note"),
                   ("copyright", "copyright"), ("localFile", "localFile")):
        if d.get(k):
            out.append("  <%s>%s</%s>" % (tag, esc(d[k]), tag))
    if not body:
        out.append("  <note>본문은 저작권이 있는 유료 표준이므로 담지 "
                   "아니하였다. 제목 차례만 담았다.</note>")
    st = d.get("stats") or {}
    if st:
        out.append("  <stats %s/>"
                   % " ".join('%s="%s"' % (k, esc(v)) for k, v in st.items()))
    out.append("  <tree>")
    for n in (d.get("tree") or []):
        node_xml(n, out, 2, body)
    out.append("  </tree>")
    out.append("</regulation>")
    return NL.join(out) + NL


def main():
    write = "--write" in sys.argv
    made = []
    for rid, d, name, body in JOBS:
        x = build(rid, body)
        made.append((rid, os.path.join(d, name), x, body))
    print("%-7s %-5s %9s  %s" % ("서고", "본문", "글자", "낼 자리"))
    for rid, p, x, body in made:
        print("%-7s %-5s %9d  %s"
              % (rid, "담음" if body else "목차만", len(x),
                 os.path.relpath(p, APP)))
    if not write:
        print()
        print("표시만 한 것임. 적으려면 --write 를 붙일 것.")
        return
    import xml.etree.ElementTree as ET
    print()
    for rid, p, x, _b in made:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8", newline=NL).write(x)
        ET.parse(p)                     # 제대로 된 XML 인지 곧바로 확인한다
        print("   %-7s %8d bytes  %s"
              % (rid, os.path.getsize(p), os.path.basename(p)))
    print()
    print("적었습니다 — %d개" % len(made))


if __name__ == "__main__":
    main()
