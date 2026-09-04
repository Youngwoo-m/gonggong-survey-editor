# -*- coding: utf-8 -*-
r"""안전매뉴얼 둘을 원문 그대로 다시 색인한다 (loc19 ㆍ loc20).

■ 왜 다시 하는가

  매뉴얼은 조문으로 짜인 글이 아니다. PART 와 장ㆍ절, 또는 Ⅰㆍ1 로 나뉜
  안내서다. 그런데 지금 자료는 마디를 모두 「조」로 세우고 번호를 1부터
  다시 매겨 두어, 화면에 「제1조」처럼 보인다. 원문에 없는 이름이다.

  이 서고에는 조문이 아닌 글을 담는 규약이 이미 있다 — `outlineNo` 다.
  화면(model.displayLabel)이 그 글자를 그대로 보인다. loc01ㆍloc27 등
  열여섯 규정이 그렇게 쓰고 있다. 두 매뉴얼도 그 규약을 따른다.

■ 원문의 짜임

  측량안전관리 매뉴얼 (loc19, 132쪽)
      PART 1.   →  편        1장.  →  장        1.  →  절        가.  →  조
  지적측량 안전매뉴얼 (loc20, 36쪽)
      Ⅰ.        →  편        1.    →  장

  목차에 쪽수가 거의 적혀 있지 아니하므로(점줄만 있고 숫자가 빠진 줄이
  대부분이다) 쪽은 목차에서 읽지 아니한다. 제목을 본문에서 앞에서부터
  차례로 찾는다 — 목차 차례가 곧 문서 차례이기 때문이다.

  python scripts\indexmanual.py            무엇을 할지 보여만 준다
  python scripts\indexmanual.py --write    자료에 적는다
  python scripts\indexmanual.py --only loc20
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
APP = os.path.dirname(ROOT)
NL = chr(10)

RE_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# 매뉴얼마다 : (자료 id, PDF, 목차 쪽, 머리말로 버릴 글, 마디를 가리는 규칙)
#   규칙 = [(정규식, 층, 층이름), …]  — 목차 줄에 견준다
BOOKS = {
    "loc19": {
        "pdf": os.path.join(APP, "관련규정", "안전관리규정",
                            "측량안전관리매뉴얼.2026.01.pdf"),
        "toc": (3, 4, 5, 6, 7, 8),
        "drop": ("❙목차❙", "측량안전관리 매뉴얼"),
        "rules": [(r"^(PART\s*\d+)\.\s*(.+)$", 1, "편"),
                  (r"^(\d+장)\.\s*(.+)$", 2, "장"),
                  (r"^(\d+)\.\s*(.+)$", 3, "절"),
                  (r"^([가-힣])\.\s*(.+)$", 4, "조")],
    },
    "loc20": {
        "pdf": os.path.join(APP, "관련규정", "안전관리규정",
                            "지적측량 안전매뉴얼.pdf"),
        "toc": (2, 3, 4),
        "drop": ("지적측량 안전 매뉴얼", "[ 목 차 ]"),
        "rules": [(r"^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)\.\s*(.+)$", 1, "편"),
                  (r"^(\d+)\.\s*(.+)$", 2, "장")],
        # 이 매뉴얼은 목차 제목과 본문 제목이 다르다.
        #   목차 「1. 안전사고」   ↔ 본문 「안전사고란?」
        #   목차 「4. 사고발생 요인」 ↔ 본문 「사고는 왜 일어나는가?」
        # 제목으로는 찾을 수 없으므로 **원문의 번호**로 자리를 잡는다.
        "find": "ordinal",
        "ord1": r"^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])(?:\s|$)",
        "ord2": r"^(\d{1,2})(?:\s|$)",
    },
    "loc31": {
        "pdf": os.path.join(os.path.dirname(APP),
                            "99.참고자료", "관련연구보고서",
                            "2025년공공측량.작업규정.개정연구.최종보고서.pdf"),
        "toc": (11, 12, 13, 14),
        "drop": ("❙목차❙", "❙표목차❙"),
        # 더 잘게 나뉜 것을 먼저 견준다 — 「1.1.」 이 「1.」 로 잡히면 안 된다
        "rules": [(r"^(제\d+장)\s*(.+)$", 1, "편"),
                  (r"^(부록)$", 1, "편"),
                  (r"^(참고문헌|Abstract)$", 1, "편"),
                  (r"^(부록\s*\d+)\.\s*(.+)$", 2, "장"),
                  (r"^(\d+\.\d+)\.\s*(.+)$", 3, "절"),
                  (r"^(\d+)\.\s*(.+)$", 2, "장")],
        "meta": {
            "name": "공공측량 작업규정 전부개정을 위한 전략계획 수립 연구 (2025)",
            "org": "공간정보품질관리원", "kind": "연구보고서",
            "no": "2026.03", "effective": "202603", "lang": "ko",
            "category": "research",
            "source": "공간정보품질관리원 수탁 · 2025년도 연구",
            "hasFullText": True, "indexMode": "목차", "localOnly": True,
        },
    },
}
LEVELS = {1: "편", 2: "장", 3: "절", 4: "조"}


def clean(s):
    s = RE_CTRL.sub(" ", str(s or ""))
    s = re.sub(r"[ \t]+", " ", s)
    return NL.join(x.strip() for x in s.split(NL)).strip()


def flat(s):
    return re.sub(r"\s", "", clean(s))


def read_toc(pdf, cfg):
    """목차 → [(층, 번호, 제목)] — 쪽수는 읽지 아니한다"""
    out = []
    for n in cfg["toc"]:
        for raw in pdf[n - 1].get_text().split(NL):
            s = clean(raw)
            s = re.sub(r"[·．.]{2,}.*$", "", s).strip()      # 점줄과 쪽수를 뗀다
            s = re.sub(r"\s*\d{1,3}$", "", s).strip()
            if not s or s in cfg["drop"] or re.match(r"^-\s*[ivx]+\s*-$", s):
                continue
            for pat, lv, _nm in cfg["rules"]:
                m = re.match(pat, s)
                if m:
                    # 「부록」ㆍ「참고문헌」처럼 번호가 없는 마디는 잡은 것이
                    # 곧 제목이다 — 번호 자리를 비운다
                    if m.lastindex and m.lastindex >= 2:
                        out.append((lv, m.group(1).strip(), clean(m.group(2))))
                    else:
                        out.append((lv, "", clean(m.group(1))))
                    break
    return out


def _by_title(toc, flatln):
    """제목이 놓인 줄자리 — 앞에서부터 차례로 찾는다.

    목차 차례가 곧 문서 차례이므로 앞 마디를 찾은 다음부터만 훑는다.
    온 제목이 없으면 제목만, 그것도 없으면 앞머리 열두 글자로 견준다."""
    cur, at = 0, []
    for lv, no, ti in toc:
        keys = [flat(no + "." + ti), flat(ti)]
        k2 = flat(ti)[:12]
        if len(k2) >= 6:
            keys.append(k2)
        pos = None
        for k in keys:
            for i in range(cur, len(flatln)):
                if k and k in flatln[i]:
                    pos = i
                    break
            if pos is not None:
                break
        if pos is not None:
            cur = pos + 1
        at.append(pos)
    return at


def main():
    write = "--write" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    import fitz

    for sid, cfg in BOOKS.items():
        if only and sid != only:
            continue
        if not os.path.exists(cfg["pdf"]):
            print("! %s — 원본을 찾지 못했습니다 : %s" % (sid, cfg["pdf"]))
            continue
        pdf = fitz.open(cfg["pdf"])
        n = pdf.page_count
        toc = read_toc(pdf, cfg)
        print("━━ %s  %s  %d쪽 · 목차에서 읽은 마디 %d개"
              % (sid, os.path.basename(cfg["pdf"]), n, len(toc)))
        if not toc:
            print("   ! 목차를 읽지 못했습니다")
            continue

        # 글줄을 쪽ㆍ세로자리 차례로 늘어놓는다. 쪽 단위로 자르면 한 쪽에 제목이
        # 둘 있을 때 범위가 비고, 목차 쪽에서 제목이 먼저 걸린다.
        body_from = max(cfg["toc"]) + 1
        lines = []
        for pi in range(body_from, n + 1):
            for b in pdf[pi - 1].get_text("blocks"):
                for ln in str(b[4]).split(NL):
                    s = clean(ln)
                    if not s:
                        continue
                    lines.append((pi, b[1], s))
        lines.sort(key=lambda z: (z[0], z[1]))
        flatln = [flat(s) for _p, _y, s in lines]

        # 제목이 놓인 줄자리를 앞에서부터 차례로 찾는다
        cur, at = 0, []
        if cfg.get("find") == "ordinal":
            import re as _re
            r1 = _re.compile(cfg["ord1"])
            r2 = _re.compile(cfg["ord2"])
            want1 = 0
            for lv, no, ti in toc:
                pos = None
                if lv == 1:
                    want1 += 1
                    # 편은 제목으로 먼저 찾는다. 이 매뉴얼은 목차와 본문의
                    # 번호가 어긋나 있다 — 목차는 「Ⅷ. 지적측량 8대 안전수칙」
                    # 인데 본문은 「Ⅶ 지적측량 8대 안전수칙」 이다.
                    tail = flat(ti)[-6:]
                    for i2 in range(cur, len(lines)):
                        s2 = flat(lines[i2][2])
                        if len(tail) >= 4 and tail in s2 and len(s2) < 40:
                            pos = i2
                            break
                    if pos is None:
                        for i2 in range(cur, len(lines)):
                            m = r1.match(lines[i2][2])
                            if m and m.group(1) == no:
                                pos = i2
                                break
                else:
                    for i2 in range(cur, len(lines)):
                        m = r2.match(lines[i2][2])
                        if m and m.group(1) == no:
                            pos = i2
                            break
                if pos is None:
                    # 번호로 못 찾는 마디가 있다 — 마지막 편은 본문에서
                    # 「[8대 안전수칙]」 처럼 로마숫자 없이 적혀 있다.
                    # 제목 꼬리로 한 번 더 찾는다.
                    tail = flat(ti)[-6:]
                    if len(tail) >= 4:
                        for i2 in range(cur, len(lines)):
                            if tail in flat(lines[i2][2]):
                                pos = i2
                                break
                if pos is not None:
                    cur = pos + 1
                at.append(pos)
            heads = at
        else:
            at = _by_title(toc, flatln)
            heads = at
        tree, stack, cnt = [], {}, {}
        for i2, (lv, no, ti) in enumerate(toc):
            a = at[i2]
            b = next((at[j2] for j2 in range(i2 + 1, len(toc))
                      if at[j2] is not None), len(lines))
            cnt[lv] = cnt.get(lv, 0) + 1
            node = {"id": "%s-%d" % (sid, i2 + 1), "level": LEVELS[lv],
                    "no": cnt[lv], "branch": 0, "outlineNo": no,
                    "title": ti, "body": "", "status": "유지", "legacyNo": "",
                    "reason": "", "sourceRef": None, "history": [],
                    "children": [], "collapsed": lv > 1,
                    "_span": None if a is None else (a + 1, b)}
            stack[lv] = node
            up = next((stack[k] for k in range(lv - 1, 0, -1) if k in stack), None)
            (up["children"] if up else tree).append(node)

        def fill(ns):
            for x in ns:
                sp = x.pop("_span", None)
                if x["children"]:
                    fill(x["children"])
                    continue
                if not sp:
                    continue
                buf = []
                for _p, _y, s in lines[sp[0]:sp[1]]:
                    if (s.isdigit() or s in cfg["drop"]
                            or re.match(r"^-\s*[\div]+\s*-$", s)):
                        continue
                    buf.append(s)
                x["body"] = clean(NL.join(buf))
        fill(tree)
        heads = at

        deep = {}
        for x in walk(tree):
            deep[x["level"]] = deep.get(x["level"], 0) + 1
        leaves = [x for x in walk(tree) if not x["children"]]
        print("   %s · 글이 담긴 잎 %d개 · 쪽 못 찾은 것 %d개"
              % (" · ".join("%s %d" % (k, v) for k, v in deep.items()),
                 len([x for x in leaves if x["body"]]),
                 len([h for h in heads if not h])))
        for x in tree[:3]:
            print("     %s %s" % (x["outlineNo"], x["title"][:40]))
            for c in x["children"][:3]:
                print("        %s %-34s %d자"
                      % (c["outlineNo"], c["title"][:34],
                         len(c["body"]) + sum(len(g["body"]) for g in walk(c["children"]))))
        if not write:
            continue

        p = os.path.join(DATA, sid + ".json")
        if os.path.exists(p):
            doc = json.load(io.open(p, encoding="utf-8"))
        else:
            doc = dict(cfg["meta"])
            doc["id"] = sid
            doc["file"] = sid + ".json"
        doc["tree"] = tree
        doc["indexMode"] = "목차"
        doc["stats"] = {k: deep.get(k, 0) for k in ("편", "장", "절", "관", "조")}
        io.open(p, "w", encoding="utf-8", newline=NL).write(
            json.dumps(doc, ensure_ascii=False))

        libp = os.path.join(DATA, "library.json")
        lib = json.load(io.open(libp, encoding="utf-8"))
        got = False
        for r in lib["regulations"]:
            if r["id"] == sid:
                r["stats"] = doc["stats"]
                r["indexMode"] = "목차"
                got = True
        if not got:
            e = {k: doc[k] for k in ("id", "name", "org", "kind", "no",
                                     "effective", "lang", "category", "source")}
            e.update({"file": sid + ".json", "hasFullText": True,
                      "indexMode": "목차", "localOnly": True,
                      "stats": doc["stats"]})
            lib["regulations"].append(e)
            print("   서고에 새로 넣었습니다 — %s" % sid)
        io.open(libp, "w", encoding="utf-8", newline=NL).write(
            json.dumps(lib, ensure_ascii=False, indent=1))
        print("   적었습니다.")
    if not write:
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")


def walk(ns):
    for x in ns:
        yield x
        yield from walk(x.get("children") or [])


if __name__ == "__main__":
    main()
