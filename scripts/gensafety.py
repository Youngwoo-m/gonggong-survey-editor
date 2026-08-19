# -*- coding: utf-8 -*-
"""
안전관리 매뉴얼 두 종을 목차 기준으로 색인하고 그림·표까지 옮긴다.

두 문서는 조문 규정이 아니라 매뉴얼이다. '제N조' 를 찾는 자동 색인기
(core/structure.js)에 걸면 매뉴얼이 인용한 다른 법령의 조문을 이 문서의 조로
잡거나 목차만 늘어놓는다. 그래서 문서가 스스로 밝힌 목차를 뼈대로 삼는다.

  목차 → 뼈대     쪽번호까지 읽어 본문을 그 가지에 담는다
  표   → <table>  본문 표·별표와 같은 XML (pdfplumber)
  그림 → 이미지    쪽에서 오려 내어 PNG 로 (PyMuPDF)

본문에는 <img id="…"> 자리표시를 넣어 앱이 제자리에 그리게 한다.
본문 속 표·수식을 다루는 방식(scripts/genobjects.py)과 같다.

사용:  python scripts/gensafety.py
출력:  data/loc19.json · data/loc20.json
       data/objects/loc19/*.xml · *.png · index.json  (loc20 도 같다)
       library.json 에 항목 추가
"""
import io, json, os, re, sys, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REG = os.path.join(os.path.dirname(ROOT), "관련규정", "안전관리규정")

RN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"
DOTS = re.compile(r"[·\.]{3,}")          # 목차의 점선
PAGENO = re.compile(r"^-\s*(\d+)\s*-$")   # 쪽번호 표시

MIN_W, MIN_H = 80, 50                     # 이보다 작은 그림은 장식으로 본다


def nid(seed=[0]):
    seed[0] += 1
    return f"sfty{seed[0]:04d}"


def node(level, no, title, body=""):
    return {"id": nid(), "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "children": [], "collapsed": True}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ───────────────────────── 목차 읽기 ─────────────────────────
def toc_lines(doc, pages):
    out = []
    for p in pages:
        for ln in doc[p].get_text().split("\n"):
            s = DOTS.sub("\t", ln.strip())
            if s:
                out.append(s)
    return out


def parse_toc(lines, rules):
    """[(깊이, 제목, 쪽번호|None), …] — rules 는 (깊이, 정규식) 목록"""
    out = []
    for s in lines:
        head, _, tail = s.partition("\t")
        head = head.strip()
        page = int(tail.strip()) if tail.strip().isdigit() else None
        for depth, rx in rules:
            m = rx.match(head)
            if m:
                title = (m.group("t") or "").strip()
                if title:
                    out.append((depth, title, page))
                break
    return out


# 측량 안전관리 매뉴얼 — PART / N장 / N. / 가.
RULES_MANUAL = [
    (0, re.compile(r"^PART\s*\d+\.\s*(?P<t>.+)$")),
    (1, re.compile(r"^(?P<n>\d+)장\.\s*(?P<t>.+)$")),
    (2, re.compile(r"^(?P<n>\d+)\.\s*(?P<t>.+)$")),
    (3, re.compile(r"^(?P<n>[가-힣])\.\s*(?P<t>.+)$")),
]
# 지적측량 안전매뉴얼 — Ⅰ. / N.
RULES_CAD = [
    (0, re.compile(rf"^[{RN}]\.\s*(?P<t>.+)$")),
    (1, re.compile(r"^(?P<n>\d+)\.\s*(?P<t>.+)$")),
]

LEVELS = ["편", "장", "절", "조"]
# 본문 표제에 붙은 번호를 떼어 목차 제목과 맞춘다 (가. 현장 안전 수칙 → 현장 안전 수칙)
#   '2. 떨어짐' 뿐 아니라 '2  떨어짐' 처럼 점 없이 번호만 단 표제도 받는다
RE_NUMHEAD = re.compile(rf"^(?:PART\s*\d+\.|[{RN}][.\s]|\d+장\.|\d+\.|\d+\s{{1,3}}|[가-힣]\.)\s*")
key_of = lambda s: re.sub(r"\s+", "", RE_NUMHEAD.sub("", str(s or "").strip()))


def build_tree(toc, levels=None):
    """목차를 편·장·절·조 가지로 세운다"""
    levels = levels or LEVELS
    tree, stack, seq = [], [], [0, 0, 0, 0]
    for depth, title, page in toc:
        lv = levels[min(depth, len(levels) - 1)]
        seq[depth] += 1
        for d in range(depth + 1, 4):
            seq[d] = 0
        n = node(lv, seq[depth], title)
        n["_page"] = page
        while len(stack) > depth:
            stack.pop()
        (stack[-1]["children"] if stack else tree).append(n)
        stack.append(n)
    return tree


def flatten(tree):
    out = []
    def rec(ns):
        for n in ns:
            out.append(n)
            rec(n["children"])
    rec(tree)
    return out


# ───────────────────────── 쪽 훑기 ─────────────────────────
def page_offset(doc, first_body):
    """쪽번호 표시를 찾아 '인쇄 쪽 → PDF 쪽' 차이를 잰다"""
    for p in range(first_body, min(first_body + 12, doc.page_count)):
        for ln in doc[p].get_text().split("\n"):
            m = PAGENO.match(ln.strip())
            if m:
                return p - int(m.group(1))
    return first_body


def read_tables(pdf_page):
    """pdfplumber 로 표를 읽는다 — 2행 2열 이상만 표로 본다"""
    out = []
    try:
        found = pdf_page.find_tables()
    except Exception:
        return out
    for t in found:
        try:
            rows = t.extract()
        except Exception:
            continue
        rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r] for r in rows]
        rows = [r for r in rows if any(r)]
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            continue
        out.append((t.bbox[1], rows))
    return out


def table_xml(tid, title, rows, source):
    cols = max(len(r) for r in rows)
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="{tid}" article="{esc(title)}" rows="{len(rows)}" '
         f'cols="{cols}" source="{esc(source)}">']
    for ri, cells in enumerate(rows):
        L.append("  <row>")
        for ci, c in enumerate(cells):
            head = ' header="1"' if ri == 0 else ""
            L.append(f'    <cell col="{ci}" row="{ri}"{head}>{esc(c)}</cell>')
        L.append("  </row>")
    L.append("</table>")
    return "\n".join(L)


DOCS = [
    {"id": "loc19", "file": "측량안전관리매뉴얼.2026.01.pdf",
     "name": "측량 안전관리 매뉴얼 (2026.1)", "org": "공간정보품질관리원",
     "kind": "매뉴얼", "effective": "202601",
     "toc": range(2, 8), "body": 10, "rules": RULES_MANUAL,
     "drop": [r"측량안전관리매뉴얼", r"PART\s*\d+\.\s*\S+", r"[ivxIVX]+"],
     "note": "「측량산업 안전관리 체계 정립을 통한 안전관리 지침 및 비용계상 방안 연구」의 "
             "성과물이다. 개편안 제6편 안전관리의 바탕 자료로 쓴다."},
    {"id": "loc20", "file": "지적측량 안전매뉴얼.pdf",
     "name": "지적측량 안전매뉴얼", "org": "한국국토정보공사",
     "kind": "매뉴얼", "effective": "2021",
     "toc": range(1, 4), "body": 4, "rules": RULES_CAD,
     "levels": ["편", "조"],
     "drop": [r"지적측량\s*안전\s*매뉴얼"],
     "note": "지적측량 현장의 재해유형·위험요인·안전수칙을 사례로 정리한 매뉴얼이다."},
]


def run(d):
    import fitz, pdfplumber
    path = os.path.join(REG, d["file"])
    doc = fitz.open(path)

    toc = parse_toc(toc_lines(doc, d["toc"]), d["rules"])
    tree = build_tree(toc, d.get("levels"))
    nodes = flatten(tree)
    off = page_offset(doc, d["body"])

    # 인쇄 쪽 → 그 쪽에서 시작하는 가지들
    by_page = {}
    for n in nodes:
        if n.get("_page"):
            by_page.setdefault(n["_page"], []).append(n)

    outdir = os.path.join(DATA, "objects", d["id"])
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    index = {}

    drop_re = [re.compile(p) for p in d["drop"]]
    title_of = {}
    for n in nodes:                      # 같은 제목이 여럿이면 앞의 것을 먼저 쓴다
        title_of.setdefault(key_of(n["title"]), []).append(n)
    cur = nodes[0] if nodes else None
    ntbl = npic = 0

    with pdfplumber.open(path) as pdf:
        for pno in range(d["body"], doc.page_count):
            page = doc[pno]
            printed = pno - off
            # 이 쪽에서 시작하는 목차 가지가 있으면 첫 번째 것으로 옮겨 간다
            starts = by_page.get(printed) or []
            if starts:
                cur = starts[0]
            pending = list(starts[1:])
            # 이 쪽 언저리에서 시작하는 가지 — 말꼬리가 다른 표제를 맞출 때 쓴다
            near = [n for pp in (printed - 1, printed, printed + 1)
                    for n in (by_page.get(pp) or [])]

            items = []
            for blk in page.get_text("dict")["blocks"]:
                for ln in blk.get("lines", []):
                    s = "".join(sp["text"] for sp in ln["spans"]).strip()
                    if not s or PAGENO.match(s) or DOTS.search(s):
                        continue
                    if any(rx.fullmatch(s) for rx in drop_re):
                        continue
                    items.append((ln["bbox"][1], "t", s))

            tbl_boxes = []
            if pno < len(pdf.pages):
                for y, rows in read_tables(pdf.pages[pno]):
                    items.append((y, "tbl", rows))
                    tbl_boxes.append(y)

            for info in page.get_image_info(xrefs=True):
                x0, y0, x1, y1 = info["bbox"]
                if x1 - x0 < MIN_W or y1 - y0 < MIN_H:
                    continue
                items.append((y0, "pic", (info["xref"], info["bbox"])))

            items.sort(key=lambda x: x[0])

            for _y, kind, val in items:
                if kind == "t":
                    # 본문 표제가 목차의 가지와 같으면 그 가지로 옮겨 간다
                    k = key_of(val)
                    cands = title_of.get(k) or []
                    if not cands and len(k) >= 3:
                        # 본문이 목차보다 말꼬리를 더 단 것도 받는다 (산업재해 → 산업재해란?)
                        cands = [n for n in near
                                 if k.startswith(key_of(n["title"]))
                                 and len(key_of(n["title"])) >= 3]
                    hit = next((c for c in cands if c in pending), None)
                    if hit is None:
                        hit = next((c for c in cands
                                    if c.get("_page") in (printed, printed - 1)), None)
                    if hit is not None:
                        cur = hit
                        if hit in pending:
                            pending.remove(hit)
                        continue
                    if cur is not None:
                        cur["body"] = (cur["body"] + "\n" + val).strip()
                    continue
                if cur is None:
                    continue
                if kind == "tbl":
                    ntbl += 1
                    tid = f"{d['id']}t{ntbl:03d}"
                    io.open(os.path.join(outdir, tid + ".xml"), "w", encoding="utf-8").write(
                        table_xml(tid, cur["title"], val, d["name"]))
                    index[tid] = {"kind": "table", "article": cur["title"],
                                  "rows": len(val), "cols": max(len(r) for r in val),
                                  "preview": " | ".join(val[0])[:120]}
                    cur["body"] = (cur["body"] + f'\n<img id="{tid}"></img>').strip()
                else:
                    npic += 1
                    pid = f"{d['id']}p{npic:03d}"
                    clip = fitz.Rect(val[1])
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
                    pix.save(os.path.join(outdir, pid + ".png"))
                    index[pid] = {"kind": "image", "article": cur["title"],
                                  "file": pid + ".png",
                                  "preview": f"원문 그림 ({cur['title']})"}
                    cur["body"] = (cur["body"] + f'\n<img id="{pid}"></img>').strip()

    for n in nodes:
        n.pop("_page", None)

    with io.open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    stats = {"편": 0, "장": 0, "절": 0, "관": 0, "조": 0,
             "별표": 0, "별지": 0, "변경": 0}
    for n in nodes:
        stats[n["level"]] = stats.get(n["level"], 0) + 1

    out = {"id": d["id"], "name": d["name"], "org": d["org"], "kind": d["kind"],
           "no": "-", "promulgated": "", "effective": d["effective"], "lang": "ko",
           "category": "safety", "source": "", "stats": stats,
           "annex": [], "annexTree": [], "indexMode": "목차",
           "localFile": os.path.join("안전관리규정", d["file"]),
           "note": d["note"], "tree": tree}
    with io.open(os.path.join(DATA, d["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return out, ntbl, npic


if __name__ == "__main__":
    libpath = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))

    for d in DOCS:
        if not os.path.exists(os.path.join(REG, d["file"])):
            print(f"  [파일없음] {d['file']}")
            continue
        doc, ntbl, npic = run(d)
        e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                                 "lang", "category", "source", "stats")}
        e["file"] = d["id"] + ".json"
        e["hasFullText"] = True
        e["indexMode"] = "목차"
        e["localFile"] = doc["localFile"]
        lib["regulations"] = [r for r in lib["regulations"]
                              if r["id"] != d["id"] and r["name"] != d["name"]]
        lib["regulations"].append(e)
        s = doc["stats"]
        print(f"  OK  {d['id']}  편 {s['편']} 장 {s['장']} 절 {s['절']} 항목 {s['조']}"
              f" · 표 {ntbl} · 그림 {npic}   {d['name']}")

    lib["generated"] = time.strftime("%Y-%m-%d")
    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"\n안전관리 매뉴얼 {len(DOCS)}종을 목차 기준으로 색인했습니다.")
