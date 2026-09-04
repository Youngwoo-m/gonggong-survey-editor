# -*- coding: utf-8 -*-
r"""표가 없는 별표의 본문을 원본 hwpx 에서 떠서 자료에 넣는다.

■ 왜 두 건뿐인가

  별표ㆍ별지의 속은 두 갈래로 자료에 담긴다.

      표가 있는 것    scripts\annexxml_hwpx.py 가 표를 떠서
                      data\objects\<규정>\annex\<열쇠>.xml 로 넣는다.
                      화면이 「서식 표」로 그려 준다.
      표가 없는 것    떠 갈 표가 없어 아무것도 담기지 아니한다.

  본문(body)이 빈 별표는 쉰여덟이지만, 그 가운데 쉰여섯은 위의 첫째 갈래라
  화면에 이미 표로 보인다. 거기에 본문까지 채우면 같은 것이 두 번 보인다
  (js\ui\detail.js 가 서식 표와 내용을 나란히 붙인다).

  참말로 아무것도 없는 것은 둘뿐이다 — 둘 다 표가 아니라 글월이다.

      별표 35 투영변환식        수식 2개 ㆍ 그림 1개 ㆍ 글월
      별표 53 안전작업 배치도    그림 9개 ㆍ 범례 글월

■ 어떻게 담는가

  수식은 이 자료가 이미 쓰는 규약을 따른다 — 개체로 떼어 놓고 본문은
  <img id="…"> 로 부른다. 화면은 core\eqmath.js 로 MathML 을 그린다.

      data\objects\reg01\<id>.xml       <equation><script>…</script></equation>
      data\objects\reg01\index.json     id → {kind, article, readable}

  그림은 개체로 담지 아니한다. 원본에 있다는 것을 ※ 로 밝혀 둔다
  (무인비행장치 별표를 손볼 때 쓴 방식과 같다).

  python scripts\annexbody.py            무엇을 넣을지 보여만 준다
  python scripts\annexbody.py --write    자료에 적는다
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
NL = chr(10)

# (개정안 자료, 구분, 개정안 번호, 개체를 둘 자리)
JOBS = [("draft2025.json", "별표", "35", "reg01"),
        ("draft2025.json", "별표", "53", "reg01")]

RE_SEC = re.compile(r"Contents/section\d+\.xml$")
RE_P = re.compile(r"<hp:p\b[^>]*>(.*?)</hp:p>", re.S)
RE_T = re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", re.S)
RE_EQ = re.compile(r"<hp:equation\b.*?</hp:equation>", re.S)
# 수식 스크립트에 xml:space="preserve" 가 붙은 것이 여덟 가운데 여섯이었다.
# 속성 없는 꼴만 보다가 둘만 잡혔다.
RE_SCRIPT = re.compile(r"<hp:script(?:\s[^>]*)?>(.*?)</hp:script>", re.S)
RE_PIC = re.compile(r"<hp:pic\b")
RE_TAG = re.compile(r"<[^>]*>")
# 차례대로 훑을 때 잡을 것 — 문단 시작 ㆍ 수식 ㆍ 그림 ㆍ 글 ㆍ 줄바꿈
RE_TOK = re.compile(
    r"<hp:p\b[^>]*>"
    r"|<hp:equation\b.*?</hp:equation>"
    r"|<hp:pic\b"
    r"|<hp:lineBreak\s*/>"
    r"|<hp:t(?:\s[^>]*)?>(?P<txt>.*?)</hp:t>", re.S)


def unesc(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


def esc(s):
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def read_hwpx(path):
    with zipfile.ZipFile(path) as z:
        return "".join(z.read(n).decode("utf-8")
                       for n in sorted(z.namelist()) if RE_SEC.match(n))


def para_text(blk):
    """한 문단의 글 — 줄바꿈 표시는 살리고 태그는 뗀다"""
    body = blk.replace("<hp:lineBreak/>", NL)
    out = [unesc(RE_TAG.sub("", m.group(1))) for m in RE_T.finditer(body)]
    s = "".join(out)
    s = re.sub(r"[ \t]+", " ", s)
    return NL.join(x.strip() for x in s.split(NL)).strip()


def pull(path):
    """원본을 차례대로 → [('글', 글) | ('수식', 스크립트) | ('그림', '')]

    문단(<hp:p>) 단위로 자르면 안 된다. 문단 태그가 겹쳐 있는 자리에서
    짝이 어긋나 수식 여덟 개 가운데 둘만 잡히는 일이 있었다. 태그를
    차례대로 훑으면서 문단 시작에서 줄만 끊는다."""
    xml = read_hwpx(path)
    out, buf = [], []

    def flush():
        s = "".join(buf)
        buf.clear()
        s = re.sub(r"[ \t]+", " ", s).strip()
        if s:
            out.append(("글", s))

    for m in RE_TOK.finditer(xml):
        g = m.group(0)
        # <hp:pic> 를 먼저 본다 — "<hp:pic" 은 "<hp:p" 로 시작하므로
        # 문단을 먼저 보면 그림이 모두 문단으로 오인된다
        if g.startswith("<hp:pic"):
            flush()
            out.append(("그림", ""))
        elif g.startswith("<hp:equation"):
            flush()
            sm = RE_SCRIPT.search(g)
            if sm:
                out.append(("수식", unesc(sm.group(1)).strip()))
        elif g.startswith("<hp:p"):
            flush()
        elif g.startswith("<hp:lineBreak"):
            flush()
        else:
            # 글 안에 든 줄바꿈은 토큰으로 잡히지 아니한다 — 여기서 끊는다
            raw = m.group("txt") or ""
            for k, part in enumerate(re.split(r"<hp:lineBreak\s*/>", raw)):
                if k:
                    flush()
                buf.append(unesc(RE_TAG.sub("", part)))
    flush()
    return out


def readable(script):
    """수식 스크립트를 한 줄로 줄여 색인에 적는다 — 사람이 알아보라는 것"""
    s = re.sub(r"\s+", " ", script)
    s = s.replace("`", " ").replace("~", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80]


def main():
    write = "--write" in sys.argv
    made, skip = [], []
    # 자료와 색인은 **한 번만** 읽어 함께 쓴다. 건마다 따로 읽으면 뒤엣것을
    # 적을 때 앞엣것이 되돌아가 사라진다 (별표 35 가 그렇게 날아갔다).
    docs, idxs = {}, {}

    def load(path, box):
        if path not in box:
            box[path] = json.load(io.open(path, encoding="utf-8"))
        return box[path]

    for f, gubun, no, objreg in JOBS:
        p = os.path.join(DATA, f)
        doc = load(p, docs)
        node = None
        for rev in [doc] + list(doc.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef") or {}
                if a.get("gubun") == gubun and str(a.get("no")) == str(no):
                    node = x
        if node is None:
            skip.append(("%s %s" % (gubun, no), "그런 별표가 없습니다"))
            continue
        cur = RE_TAG.sub("", node.get("body") or "").strip()
        if len(cur) >= 20:
            skip.append(("%s %s" % (gubun, no), "본문이 이미 있습니다 — 건드리지 않습니다"))
            continue
        src = os.path.join(ROOT, (node.get("annexRef") or {}).get("hwpx") or "")
        if not os.path.exists(src):
            skip.append(("%s %s" % (gubun, no), "원본을 찾지 못했습니다"))
            continue

        bits = pull(src)
        # 머리(「[ 별표 42 ]」와 제목)는 마디의 제목에 이미 있다 — 뺀다
        while bits and bits[0][0] == "글" and (
                re.match(r"^\[?\s*별[표지]\s*\d+", bits[0][1])
                or bits[0][1] == (node.get("title") or "").strip()):
            bits.pop(0)

        idx_path = os.path.join(DATA, "objects", objreg, "index.json")
        idx = load(idx_path, idxs)
        lines, eqs, npic = [], [], 0
        seq = 0
        for kind, val in bits:
            if kind == "글":
                lines.append(val)
            elif kind == "수식":
                seq += 1
                oid = "anx%s%s-eq%d" % (gubun == "별지" and "j" or "", no, seq)
                eqs.append((oid, val))
                lines.append('<img id="%s"></img>' % oid)
            else:
                npic += 1
        if npic:
            lines.append("※ 원본에는 그림 %d개가 함께 실려 있다. 화면에는 옮기지 "
                         "아니하였으므로 내려받기의 원본 파일을 함께 보아야 한다."
                         % npic)
        body = NL.join(lines).strip()
        made.append((gubun, no, node, body, eqs, npic, objreg, idx_path, idx, p, doc))

    for gubun, no, node, body, eqs, npic, objreg, ip, idx, p, doc in made:
        print("━━ %s %s  %s" % (gubun, no, node.get("title")))
        print("   글 %d자 · 수식 %d개 · 그림 %d개"
              % (len(RE_TAG.sub("", body)), len(eqs), npic))
        for ln in body.split(NL)[:4]:
            print("     " + ln[:96])
        if len(body.split(NL)) > 4:
            print("     … 그 밖에 %d줄" % (len(body.split(NL)) - 4))
        print()
    for k, why in skip:
        print("   ! %-8s %s" % (k, why))

    if not write:
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")
        return

    touched = {}
    for gubun, no, node, body, eqs, npic, objreg, ip, idx, p, doc in made:
        node["body"] = body
        d = os.path.join(DATA, "objects", objreg)
        for oid, script in eqs:
            io.open(os.path.join(d, oid + ".xml"), "w", encoding="utf-8",
                    newline=NL).write(
                '<?xml version="1.0" encoding="UTF-8"?>' + NL
                + '<equation id="%s" article="%s %s" font="HYhwpEQ" source="%s">'
                % (esc(oid), gubun, no,
                   esc(os.path.basename((node.get("annexRef") or {}).get("hwpx") or "")))
                + NL + "  <script>" + esc(script) + "</script>" + NL
                + "</equation>" + NL)
            idx[oid] = {"kind": "equation", "article": "%s %s" % (gubun, no),
                        "readable": readable(script)}
        touched[p] = doc

    for path, obj in list(docs.items()) + list(idxs.items()):
        io.open(path, "w", encoding="utf-8", newline=NL).write(
            json.dumps(obj, ensure_ascii=False))
    print()
    print("자료에 적었습니다 — 별표 %d건 · 수식 개체 %d개"
          % (len(made), sum(len(x[4]) for x in made)))


if __name__ == "__main__":
    main()
