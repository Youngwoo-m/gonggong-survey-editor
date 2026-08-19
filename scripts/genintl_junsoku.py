# -*- coding: utf-8 -*-
"""
작업규정의 준칙 전문(2025년판)을 원본 PDF 에서 다시 읽는다 — loc11.

서고 사본을 훑다가(checklib) 이 사본에서 조 91개의 본문이 통째로 비어 있는
것을 보았다. 제목 자리에 본문이 들어앉아 조 제목이 「作業計画は、第１１条の
規定によるほか…」 처럼 문장으로 되어 있었다. 표도 글줄로 풀려 칸 값이 빠졌다
(제444조의 0.15m·0.2m·0.3m, 제462조의 0.3m·0.10m·0.15m).

이 준칙은 개편안이 견주어 보는 바탕이므로 사본이 성해야 한다. 앞서 제4편
제4장만 원본에서 다시 읽어 loc28 로 담았는데(genintl_uavlas), 그때 만든 부품을
그대로 써서 이번에는 전문을 읽는다.

  본문 10~189쪽 · 제1조~제715조 · 편 5 · 장 26 · 절 148 · 관 55
  겉장 1쪽과 목차 2~9쪽은 건너뛰고, 189쪽의 附則 에서 멈춘다.

우리말 대역은 여기에서 만들지 아니한다. 원문(origTitle·origBody)만 담고,
대역은 이미 있는 scripts/retranslate_ja.mjs 가 낱말 사전으로 다시 만든다.

사용:  python scripts/genintl_junsoku.py
       node scripts/retranslate_ja.mjs      ← 대역을 다시 만든다
출력:  data/loc11.json · data/objects/loc11/*.xml · index.json · library.json 갱신
"""
import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import junsoku_pdf as J

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REG = os.path.join(os.path.dirname(ROOT), "관련규정")

LOC = "loc11"
SRC = os.path.join("국외관련규정", "일본_작업규정의준칙_2025",
                   "00_作業規程の準則_전문.pdf")
NAME = "作業規程の準則 (일본 국토지리원 2025)"
PAGES = range(9, 189)               # 10~189쪽 — 겉장·목차를 건너뛴다

_seq = [0]


def nid():
    _seq[0] += 1
    return f"{LOC}n{_seq[0]:04d}"


def node(level, no, title):
    return {"id": nid(), "level": level, "no": no, "branch": 0, "title": title,
            "body": "", "status": "유지", "legacyNo": "", "reason": "",
            "sourceRef": None, "origTitle": title, "origBody": "",
            "children": [], "collapsed": True}


def main():
    import fitz, pdfplumber
    path = os.path.join(REG, SRC)
    if not os.path.exists(path):
        sys.exit(f"파일이 없습니다: {path}")

    doc = fitz.open(path)
    items, carry = [], None
    with pdfplumber.open(path) as pdf:
        for pno in PAGES:
            got, carry = J.read_items(pdf.pages[pno], doc[pno], carry)
            items += got
    items = J.assemble(items)
    marks, count, tables, cited = J.parse(items, node, first_jo=1)
    tree = J.build_tree(marks)
    arts = [n for lv, n in marks if lv == "조"]

    # ── 본문 속 표 ──
    outdir = os.path.join(DATA, "objects", LOC)
    os.makedirs(outdir, exist_ok=True)
    keep = {"annex-index.json"}         # 별표 색인은 다른 데서 만든다
    for f in os.listdir(outdir):
        if f not in keep:
            os.remove(os.path.join(outdir, f))
    index = {}
    for k, (art, rows) in enumerate(tables):
        tid = f"{LOC}t{k + 1:04d}"
        label = f"제{art['no']}조({art['title']})"
        io.open(os.path.join(outdir, tid + ".xml"), "w", encoding="utf-8").write(
            J.table_xml(tid, label, rows, NAME))
        index[tid] = {"kind": "table", "article": label, "rows": len(rows),
                      "cols": max(len(r) for r in rows),
                      "preview": " | ".join(rows[0])[:120]}
        for fld in ("body", "origBody"):
            art[fld] = art[fld].replace(J.TBL_MARK % k, f'<img id="{tid}"></img>')
    for x in arts:                       # 못 채운 자리표시가 남지 아니하게
        for fld in ("body", "origBody"):
            x[fld] = re.sub(r"\x00TBL\d+\x00", "", x[fld])
    with io.open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    # ── 앞서 담아 둔 것에서 이어받을 것 ──
    old_path = os.path.join(DATA, LOC + ".json")
    old = json.load(io.open(old_path, encoding="utf-8")) if os.path.exists(old_path) else {}

    stats = {"편": count["편"], "장": count["장"], "절": count["절"],
             "관": count["관"], "조": len(arts), "별표": 0, "별지": 0, "변경": 0}
    out = {"id": LOC, "name": NAME, "org": "일본 국토지리원", "kind": "준칙",
           "no": "-", "promulgated": old.get("promulgated", "2008"),
           "effective": old.get("effective", "2025"), "lang": "ja",
           "category": "intl", "source": old.get("source", ""), "stats": stats,
           "annex": [], "annexTree": [], "indexMode": "조문",
           "localFile": SRC, "tree": tree,
           "translated": {"lang": "ja", "coverage": 0,
                          "dict": (old.get("translated") or {}).get("dict", 0)}}
    with io.open(old_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for r in lib["regulations"]:
        if r["id"] == LOC:
            r["stats"] = stats
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(NAME)
    print(f"  편 {count['편']} · 장 {count['장']} · 절 {count['절']} · "
          f"관 {count['관']} · 조 {len(arts)} · 표 {len(tables)}")
    empty = [x for x in arts if not x["body"].strip()]
    if empty:
        print(f"  [주의] 본문이 빈 조 {len(empty)}건: "
              + ", ".join(f"제{x['no']}조" for x in empty[:8]))
    notitle = [x for x in arts if not x["title"].strip()]
    if notitle:
        print(f"  제목이 없는 조 {len(notitle)}건 — 준칙은 제목 없는 조가 흔하다 "
              f"({', '.join('제%s조' % x['no'] for x in notitle[:5])} …)")
    nos = [x["no"] for x in arts]
    gap = [n for n in range(1, (nos[-1] if nos else 0) + 1) if n not in set(nos)]
    if gap:
        print(f"  [주의] 빠진 조 번호 {len(gap)}개: {gap[:12]}")
    if cited:
        print(f"  인용으로 보아 넘긴 조 표시 {len(cited)}건")
    print("\n  대역은 다음으로 다시 만듭니다:  node scripts/retranslate_ja.mjs")


if __name__ == "__main__":
    main()
