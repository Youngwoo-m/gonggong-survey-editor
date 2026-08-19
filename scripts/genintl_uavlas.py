# -*- coding: utf-8 -*-
"""
작업규정의 준칙 제4편 제4장 「UAV 레이저 측량」 을 2025년판으로 담는다.

■ 왜 전문(loc11)에서 떼어 오지 아니하는가

  전문은 PDF 를 통째로 훑어 담은 것이라 이 장에서 글이 샜다. 표를 글줄로
  풀어 담느라 칸 값이 빠졌고(제444조의 0.15m·0.2m·0.3m, 제462조의
  0.3m·0.10m·0.15m), 제483조는 호 여섯 가운데 둘만 남았으며, 제480조는
  줄이 넘어가는 자리에서 글자가 떨어졌다. 기준을 짤 때 곁에 두고 볼 것이니
  이 장만은 원본 PDF 에서 다시 읽는다.

■ 우리말은 2023년 옮김본에서 가져온다

  이 장만 우리말로 옮긴 것이 따로 있다(서광항업, 2023년 3월 개정판).
  2023년판과 2025년판은 조 번호가 어긋나고 글도 더러 고쳐졌으므로,
  제목이 닮은 차례대로 맞대어(Needleman-Wunsch) 짝을 지은 뒤 그 우리말을
  옮겨 붙인다. 글이 고쳐진 조는 KO_FIX 에 손으로 적어 갈음한다.

  옮김본 자체는 규정 목록에 세우지 아니한다 — 2025년판이 최종이고,
  옮김본은 문구를 빌려 오는 바탕으로만 쓴다.

  우리말이 어디에서 왔는지는 장 마디의 대응표에 조마다 적어 둔다.

■ 어떻게 읽는가

  · 같은 줄인데 글자가 따로 놓인 곳이 있다 (「要　旨」 처럼 사이를 벌린
    표제). 높이만 보고 줄을 세우면 뒤섞이므로 높이와 왼쪽자리를 함께 본다.
  · 조 제목은 조 앞줄에 괄호로 붙는데 관 표제가 사이에 끼는 곳이 있다.
    다음 마디가 조이거나 절·관이면 조 제목으로 본다.
  · 조 번호는 차례를 따라간다. 줄이 넘어가며 인용이 줄머리로 올라온 것을
    조로 잘못 세운 일이 있다.
  · 표는 글자가 쪽 아래에 흩어져 나온다. 표 자리(bbox)에 든 줄은 본문에서
    빼고 표는 그 높이로 끼워 넣는다.

사용:  python scripts/genintl_uavlas.py
출력:  data/loc28.json · data/objects/loc28/*.xml · index.json · library.json 갱신
"""
import difflib
import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REG = os.path.join(os.path.dirname(ROOT), "관련규정")

LOC = "loc28"
SRC = os.path.join("국외관련규정", "일본_작업규정의준칙_2025",
                   "00_作業規程の準則_전문.pdf")
SRC_KO = os.path.join("무인비행장치 측량 작업규정개정관련",
                      "일본 공공측량 작업규정의 준칙 4장 UAV 라이다_한글.pdf")
NAME = "作業規程の準則 제4편 제4장 UAV 레이저 측량 (2025년판)"
PAGES = range(120, 132)             # 121~132쪽 — 제440조~제483조
KO_PAGES_FROM = 2                   # 옮김본 0쪽 겉장 · 1쪽 목차
PART_NO, PART_TITLE = 4, "地形測量及び写真測量（三次元点群測量）"
PART_KO = "지형측량 및 사진측량 (3차원 점군측량)"
CHAP_NO, CHAP_TITLE, CHAP_KO = 4, "ＵＡＶレーザ測量", "UAV 레이저 측량"

ZEN_NUM = str.maketrans("０１２３４５６７８９", "0123456789")
ZEN_AL = str.maketrans("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                       "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
KAN = "一二三四五六七八九十"
KANA = "イロハニホヘトチリヌ"

# ── 2025년판(일본어) 읽기 ──
J_JEOL = re.compile(r"^第([０-９]{1,2})節\s*(.*)$")
J_GWAN = re.compile(r"^第([０-９]{1,2})款\s*(.*)$")
J_JO = re.compile(r"^第([０-９]{1,3})条\s*(.*)$")
J_PAREN = re.compile(r"^（(.+)）$")
# 새 줄을 여는 표시 — 이 가운데 하나로 시작하면 앞줄에 잇지 아니한다
J_NEW = re.compile(r"^(?:第[０-９]+[節款]|第[０-９]{1,3}条|（"
                   r"|[" + KAN + r"]{1,2}\s|[" + KANA + r"]\s|[０-９]{1,2}\s)")
# ── 2023년 옮김본(우리말) 읽기 ──
K_JO = re.compile(r"^제\s*(\d{3})\s*조\s*(.*)$")
K_JEOL = re.compile(r"^제\s*(\d{1,2})\s*절\s*(.*)$")
K_GWAN = re.compile(r"^제\s*(\d{1,2})\s*관\s*(.*)$")
K_PAREN = re.compile(r"^\((.+)\)$")
K_NEW = re.compile(r"^(?:\d{1,2}[.)]\s|[가-하]\.\s|\d{1,2}\s+[가-힣])")
RE_PAGENO = re.compile(r"^\d{1,3}$")

_seq = [0]


def nid():
    _seq[0] += 1
    return f"{LOC}n{_seq[0]:04d}"


def node(level, no, title, body="", ko_title="", ko_body=""):
    n = {"id": nid(), "level": level, "no": no, "branch": 0, "title": title,
         "body": body, "status": "유지", "legacyNo": "", "reason": "",
         "sourceRef": None, "origTitle": title, "origBody": body,
         "children": [], "collapsed": True}
    if ko_title:
        n["transTitle"] = ko_title
    if ko_body:
        n["transBody"] = ko_body
    return n


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def table_xml(tid, article, rows):
    cols = max(len(r) for r in rows)
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="{tid}" article="{esc(article)}" rows="{len(rows)}" '
         f'cols="{cols}" source="{esc(NAME)}">']
    for ri, cells in enumerate(rows):
        L.append("  <row>")
        for ci, c in enumerate(cells):
            head = ' header="1"' if ri == 0 else ""
            L.append(f'    <cell col="{ci}" row="{ri}"{head}>{esc(c)}</cell>')
        L.append("  </row>")
    L.append("</table>")
    return "\n".join(L)


def read_items(pdf_page, page, carry=None):
    """한 쪽의 글줄과 표를 자리 차례로 모은다 — 표 자리에 든 글줄은 뺀다.

    높이만으로 줄을 세우면 안 된다. 「要　旨」 처럼 사이를 벌려 놓은 표제는
    같은 높이에 조각이 둘이라, 넣은 차례대로 두면 뒤섞인다 (제4장 표제에
    '旨' 가 붙어 버렸다). 높이가 같으면 왼쪽자리로 가른다.

    표가 쪽을 넘어가면 앞쪽에 머리글만 한 줄로 남는다. 그 한 줄은 이 쪽의
    표로 삼지 아니하고 다음 쪽 첫 표의 머리로 넘긴다 (carry).
    → (모은 것, 다음 쪽으로 넘길 머리글)
    """
    boxes, items, nxt = [], [], None
    try:
        found = pdf_page.find_tables()
    except Exception:
        found = []
    for t in found:
        try:
            rows = t.extract()
        except Exception:
            continue
        rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r] for r in rows]
        rows = [r for r in rows if any(r)]
        # 표로 담지 아니할 것이라도 자리는 적어 둔다. 쪽을 넘어가는 표는 앞쪽에
        # 머리글만 걸려 한 줄짜리로 잡히는데, 걸러 내면서 자리까지 지우면
        # 그 머리글이 본문으로 새어 든다 (제444조에 '要求精度成果品目点密度' 가 붙었다).
        boxes.append(t.bbox)
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            if len(rows) == 1 and max(len(r) for r in rows) >= 2:
                nxt = rows[0]           # 쪽 끝에 걸린 머리글 — 다음 쪽으로 넘긴다
            continue
        if carry:
            rows = [carry] + rows
            carry = None
        items.append((t.bbox[1], t.bbox[0], "tbl", rows))

    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            s = "".join(sp["text"] for sp in ln["spans"])
            if not s.strip() or RE_PAGENO.match(s.strip()):
                continue
            x0, y0, x1, y1 = ln["bbox"]
            cy = (y0 + y1) / 2
            if any(b[0] - 2 <= x0 and b[1] - 2 <= cy <= b[3] + 2 for b in boxes):
                continue
            items.append((y0, x0, "t", s))

    # 같은 줄인데 밑선이 0.5pt 남짓 어긋난 조각이 있다 (「（要　旨）」 의 '旨）' 가
    # '（要' 보다 위로 잡혀 표제에 뒤엉켰다). 가까운 높이는 한 줄로 묶은 뒤
    # 줄 안에서는 왼쪽자리로 세운다. 줄 사이는 15pt 남짓이라 6pt 로 가른다.
    items.sort(key=lambda v: v[0])
    row, rows = [], []
    for it in items:
        if row and it[0] - row[0][0] > 6:
            rows.append(row); row = []
        row.append(it)
    if row:
        rows.append(row)
    out = []
    for r in rows:
        out += sorted(r, key=lambda v: v[1])
    return [(k, v) for _y, _x, k, v in out], nxt


def assemble(items, is_new):
    """줄이 넘어간 것을 잇는다 — 새 마디를 여는 표시로만 줄을 끊는다"""
    out = []
    for kind, val in items:
        if kind != "t":
            out.append((kind, val))
            continue
        s = val.strip()
        if not s:
            continue
        if out and out[-1][0] == "t" and not is_new(s):
            out[-1] = ("t", out[-1][1] + s)
        else:
            out.append(("t", s))
    return out


TBL_MARK = "\x00TBL%d\x00"          # 표가 놓일 자리 — 뒤에 <img id> 로 바꾼다


def parse(items, rx, want_jo, mk_node):
    """절·관·조로 가른다 → (마디 목록, 절 수, 관 수, 표, 인용으로 넘긴 번호)"""
    JEOL, GWAN, JO, PAREN = rx
    arts, cited, tables = [], [], []
    jeol = gwan = art = None
    pending, lines = None, []
    n_jeol = n_gwan = 0
    nxt_jo = want_jo

    def flush():
        if art is not None:
            art["body"] = "\n".join(lines).strip()
            art["origBody"] = art["body"]

    for i, (kind, val) in enumerate(items):
        if kind == "tbl":
            if art is not None:
                lines.append(TBL_MARK % len(tables))
                tables.append((art, val))
            continue
        s = val.strip()

        m = JEOL.match(s)
        if m:
            flush(); art, lines = None, []
            n_jeol += 1
            jeol = mk_node("절", int(m.group(1).translate(ZEN_NUM)),
                           PAREN.sub(r"\1", m.group(2).strip()))
            gwan = None
            arts.append(("절", jeol))
            continue
        m = GWAN.match(s)
        if m and jeol is not None:
            flush(); art, lines = None, []
            n_gwan += 1
            gwan = mk_node("관", int(m.group(1).translate(ZEN_NUM)),
                           m.group(2).strip())
            arts.append(("관", gwan))
            continue
        m = JO.match(s)
        if m:
            n = int(m.group(1).translate(ZEN_NUM))
            if n == nxt_jo:
                flush()
                art = mk_node("조", n, pending or "")
                pending, nxt_jo = None, n + 1
                lines = [m.group(2).strip()] if m.group(2).strip() else []
                arts.append(("조", art))
                continue
            cited.append(n)
        m = PAREN.match(s)
        if m:
            nx = next((v.strip() for k, v in items[i + 1:] if k == "t" and v.strip()), "")
            if JO.match(nx) or JEOL.match(nx) or GWAN.match(nx):
                pending = m.group(1).strip()
                continue
        if art is None:
            continue
        lines.append(s)
    flush()
    return arts, n_jeol, n_gwan, tables, cited


# ───────── 2023년 옮김본과 맞대기 ─────────
# 제목으로는 맞댈 수 없다. 한쪽은 일본어, 한쪽은 우리말이라 글자가 하나도
# 겹치지 않아 어느 짝이나 닮음이 0 이 된다 — 그러면 끼어든 조를 못 찾고
# 그냥 앞에서부터 하나씩 이어 붙여 뒤쪽 일곱 조가 통째로 어긋난다.
# 그래서 말을 타지 않는 것으로 잰다: 마디(항·호·목) 수와 글 길이.
J_ITEM = (re.compile(r"^[０-９]{1,2}\s"), re.compile(r"^[" + KAN + r"]{1,2}\s"),
          re.compile(r"^[" + KANA + r"]\s"))
K_ITEM = (re.compile(r"^\d{1,2}[.)]\s"), re.compile(r"^\d{1,2}\s+[가-힣]"),
          re.compile(r"^[가-하]\.\s"))


def shape(body, marks):
    """(마디 수, 글자 수) — 판이 달라도 크게 바뀌지 아니하는 생김새"""
    t = re.sub(r"<img id=\"[^\"]+\"></img>", "", str(body or ""))
    L = [x.strip() for x in t.split("\n")]
    n = sum(1 for x in L for rx in marks if rx.match(x))
    return n, len(re.sub(r"\s", "", t))


def align(A, B, gap=-0.35):
    """앞뒤 차례를 지키면서 가장 닮게 맞춘다 → [(A자리|None, B자리|None)]"""
    def sim(a, b):
        (ia, sa), (ib, sb) = a, b
        d = 1 - min(1.0, abs(ia - ib) / max(ia, ib, 1))
        r = min(sa, sb) / max(sa, sb, 1)
        return 0.5 * d + 0.5 * r
    n, m = len(A), len(B)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    P = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0], P[i][0] = D[i - 1][0] + gap, "u"
    for j in range(1, m + 1):
        D[0][j], P[0][j] = D[0][j - 1] + gap, "l"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j], P[i][j] = max((D[i - 1][j - 1] + sim(A[i - 1], B[j - 1]), "d"),
                                   (D[i - 1][j] + gap, "u"),
                                   (D[i][j - 1] + gap, "l"))
    i, j, out = n, m, []
    while i > 0 or j > 0:
        t = P[i][j]
        if t == "d":
            out.append((i - 1, j - 1)); i -= 1; j -= 1
        elif t == "u":
            out.append((i - 1, None)); i -= 1
        else:
            out.append((None, j - 1)); j -= 1
    out.reverse()
    return out


from uavlas_ko import KO_FIX, KO_TITLE, KO_TERM, KO_HEAD   # 손으로 갈음한 우리말


def polish(t):
    """옮김본이 같은 말을 여러 가지로 적은 것을 하나로 맞춘다"""
    for rx, to in KO_TERM:
        t = re.sub(rx, to, str(t or ""))
    return t


def main():
    import fitz, pdfplumber

    # ── 2025년판 ──
    path = os.path.join(REG, SRC)
    if not os.path.exists(path):
        sys.exit(f"파일이 없습니다: {path}")
    doc = fitz.open(path)
    items = []
    with pdfplumber.open(path) as pdf:
        carry = None
        for pno in PAGES:
            got, carry = read_items(pdf.pages[pno], doc[pno], carry)
            items += got
    items = assemble(items, lambda s: J_NEW.match(s))
    nodes, n_jeol, n_gwan, tables, cited = parse(
        items, (J_JEOL, J_GWAN, J_JO, J_PAREN), 440,
        lambda lv, no, t: node(lv, no, t))

    # ── 2023년 옮김본 ──
    kpath = os.path.join(REG, SRC_KO)
    kdoc = fitz.open(kpath)
    kitems = []
    with pdfplumber.open(kpath) as pdf:
        carry = None
        for pno in range(KO_PAGES_FROM, kdoc.page_count):
            got, carry = read_items(pdf.pages[pno], kdoc[pno], carry)
            kitems += got
    kitems = [(k, v) for k, v in kitems
              if not (k == "t" and v.strip().startswith("제4장") and "UAV" in v)]
    kitems = assemble(kitems, lambda s: K_NEW.match(s) or K_JO.match(s)
                      or K_JEOL.match(s) or K_GWAN.match(s) or K_PAREN.match(s))
    knodes, _, _, ktables, _ = parse(kitems, (K_JEOL, K_GWAN, K_JO, K_PAREN), 437,
                                     lambda lv, no, t: node(lv, no, t))
    ko = [x for lv, x in knodes if lv == "조"]
    for x in ko:                        # 옮김본의 표는 문구를 빌릴 때만 쓴다
        x["body"] = re.sub(r"\x00TBL\d+\x00", "", x["body"]).strip()

    # ── 짝짓기 ──
    ja = [x for lv, x in nodes if lv == "조"]
    pairs = align([shape(x["body"], J_ITEM) for x in ja],
                  [shape(x["body"], K_ITEM) for x in ko])
    mate = {}
    for a, b in pairs:
        if a is not None and b is not None:
            mate[ja[a]["no"]] = ko[b]

    src_of = {}
    for x in ja:
        k = mate.get(x["no"])
        if x["no"] in KO_FIX:
            x["transTitle"] = KO_TITLE.get(x["no"]) or polish(k["title"] if k else "")
            x["transBody"] = polish(KO_FIX[x["no"]])
            # 손본 조는 옮김본의 옛 문구를 함께 담아 둔다 — 앱이 바뀐 말을
            # 푸르게 짚어 보인다 (개편안 조문의 wasBody 와 같은 구실)
            if k and k["body"].strip():
                x["transWasBody"] = polish(k["body"])
            src_of[x["no"]] = "고침" if k else "새로 옮김"
        elif k:
            x["transTitle"] = polish(k["title"])
            x["transBody"] = polish(k["body"])
            src_of[x["no"]] = "옮김본 그대로"
        else:
            src_of[x["no"]] = "우리말 없음"
        if not x.get("transTitle"):     # 「要旨」처럼 옮김본에 제목이 없던 것
            x["transTitle"] = KO_HEAD.get(x["title"], "")
        if k:
            x["legacyNo"] = f"2023년판 제{k['no']}조"

    # ── 나무 세우기 ──
    part = node("편", PART_NO, PART_TITLE, ko_title=PART_KO)
    chap = node("장", CHAP_NO, CHAP_TITLE, ko_title=CHAP_KO)
    part["children"].append(chap)
    for lv, x in nodes:                 # 절·관 표제의 우리말
        if lv in ("절", "관") and KO_HEAD.get(x["title"]):
            x["transTitle"] = KO_HEAD[x["title"]]
    jeol = gwan = None
    for lv, x in nodes:
        if lv == "절":
            chap["children"].append(x); jeol, gwan = x, None
        elif lv == "관":
            (jeol or chap)["children"].append(x); gwan = x
        else:
            (gwan or jeol or chap)["children"].append(x)

    # ── 본문 속 표를 파일로 빼고 자리표시를 남긴다 ──
    outdir = os.path.join(DATA, "objects", LOC)
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    index = {}
    for k, (art, rows) in enumerate(tables):
        tid = f"{LOC}t{k + 1:03d}"
        label = f"제{art['no']}조({art['title']})"
        io.open(os.path.join(outdir, tid + ".xml"), "w", encoding="utf-8").write(
            table_xml(tid, label, rows))
        index[tid] = {"kind": "table", "article": label, "rows": len(rows),
                      "cols": max(len(r) for r in rows),
                      "preview": " | ".join(rows[0])[:120]}
        for fld in ("body", "origBody"):
            art[fld] = art[fld].replace(TBL_MARK % k, f'<img id="{tid}"></img>')
    for x in ja:                        # 못 채운 자리표시가 남지 아니하게
        for fld in ("body", "origBody"):
            x[fld] = re.sub(r"\x00TBL\d+\x00", "", x[fld])

    # ── 조문 대응표 ──
    rows = [["2023년 옮김본", "2025년판", "제목", "차이", "우리말"]]
    n_new = 0
    for a, b in pairs:
        if a is None:
            continue                    # 옮김본에만 있는 조는 없다
        x = ja[a]
        if b is None:
            n_new += 1
            rows.append(["—", f"제{x['no']}조", x.get("transTitle") or x["title"],
                         "2025년판 신설", src_of.get(x["no"], "")])
        else:
            d = x["no"] - ko[b]["no"]
            rows.append([f"제{ko[b]['no']}조", f"제{x['no']}조",
                         x.get("transTitle") or x["title"], f"{d:+d}",
                         src_of.get(x["no"], "")])
    mid = f"{LOC}m001"
    io.open(os.path.join(outdir, mid + ".xml"), "w", encoding="utf-8").write(
        table_xml(mid, f"제{CHAP_NO}장 조문 대응표", rows))
    index[mid] = {"kind": "table", "article": f"제{CHAP_NO}장 조문 대응표",
                  "rows": len(rows), "cols": 5, "preview": " | ".join(rows[0])}
    n_keep = sum(1 for v in src_of.values() if v == "옮김본 그대로")
    n_fix = sum(1 for v in src_of.values() if v == "고침")
    n_tr = sum(1 for v in src_of.values() if v == "새로 옮김")
    chap["body"] = (
        "이 장은 2025년판 원본에서 읽었다. 전문(loc11)은 이 장에서 표 값과 호 일부가 "
        "빠져 있어 쓰지 아니하였다.\n"
        "우리말은 2023년 3월 개정판 옮김본(서광항업)에서 가져왔다 — "
        f"그대로 쓴 조 {n_keep}건, 2025년판에 맞추어 고친 조 {n_fix}건, "
        f"새로 옮긴 조 {n_tr}건. 조마다 어디에서 왔는지 다음 표에 적었다.\n"
        f'<img id="{mid}"></img>')
    chap["origBody"] = chap["body"]

    with io.open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    stats = {"편": 1, "장": 1, "절": n_jeol, "관": n_gwan, "조": len(ja),
             "별표": 0, "별지": 0, "변경": 0}
    note = ("일본 국토지리원 작업규정의 준칙 2025년판 가운데 UAV 레이저 측량 장이다. "
            "준칙 전문(loc11)에도 같은 장이 있으나 PDF 를 통째로 훑는 과정에서 표 값과 "
            "호 일부가 빠져(제444조·제462조의 표 값, 제483조의 호 4개) 이 장만 원본에서 "
            "다시 읽었다. 우리말은 2023년 3월 개정판 옮김본(서광항업)의 문구를 바탕으로 "
            f"2025년판에 맞추어 정리하였다 — 그대로 {n_keep}건 · 고침 {n_fix}건 · "
            f"새로 옮김 {n_tr}건. 조 번호는 2023년판과 어긋나므로(앞쪽 +3, "
            "「단면도 데이터의 작성」 관 뒤로 +5) 장 본문의 대응표를 함께 본다. "
            "무인비행장치 라이다 측량 기준을 짤 때의 견줌 자료로 쓴다.")
    out = {"id": LOC, "name": NAME, "org": "일본 국토지리원", "kind": "준칙",
           "no": "-", "promulgated": "2008", "effective": "2025", "lang": "ja",
           "category": "intl", "source": "", "stats": stats,
           "annex": [], "annexTree": [], "indexMode": "조문",
           "localFile": SRC, "note": note, "tree": [part],
           "translated": {"lang": "ja", "coverage": round(
               sum(1 for x in ja if x.get("transBody")) / max(len(ja), 1), 2),
               "by": "2023년 옮김본(서광항업)을 2025년판에 맞추어 정리"}}
    with io.open(os.path.join(DATA, LOC + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    lib["regulations"] = [r for r in lib["regulations"] if r["id"] != LOC]
    lib["regulations"].append({
        "id": LOC, "name": NAME, "org": "일본 국토지리원", "kind": "준칙", "no": "-",
        "effective": "2025", "lang": "ja", "category": "intl", "source": "",
        "stats": stats, "file": LOC + ".json", "hasFullText": True,
        "indexMode": "조문", "localFile": SRC, "note": note,
        "translated": out["translated"]})
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(NAME)
    print(f"  편 1 · 장 1 · 절 {n_jeol} · 관 {n_gwan} · 조 {len(ja)} · 표 {len(tables)}")
    print(f"  우리말 — 옮김본 그대로 {n_keep} · 고침 {n_fix} · 새로 옮김 {n_tr}"
          + (f" · 없음 {len(ja) - n_keep - n_fix - n_tr}"
             if len(ja) - n_keep - n_fix - n_tr else ""))
    print(f"  2025년판에서 늘어난 조 {n_new}건")
    if cited:
        print("  인용으로 보아 넘긴 조 표시: "
              + ", ".join(f"제{n}조" for n in cited[:8]))
    nos = [x["no"] for x in ja]
    gap = [n for n in range(nos[0], nos[-1] + 1) if n not in nos]
    if gap:
        print(f"  [주의] 빠진 조 번호: {gap}")


if __name__ == "__main__":
    main()
