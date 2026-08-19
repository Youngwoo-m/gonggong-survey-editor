# -*- coding: utf-8 -*-
"""
일본 작업규정의 준칙 PDF 를 읽는 공통 부품.

이 PDF 는 편·장·절·관·조로 짜인 조문 규정인데, 글자를 그냥 뽑으면 세 군데에서
어긋난다. 그 세 가지를 여기에서 한 번만 다룬다 — 한 장만 담는 genintl_uavlas 와
전문을 담는 genintl_junsoku 가 같은 부품을 쓴다.

  1) 같은 줄인데 조각의 밑선이 0.5pt 어긋난 곳이 있다 (「要　旨」 처럼 사이를
     벌린 표제). 높이만 보고 세우면 표제에 '旨' 가 따로 붙는다. 가까운 높이를
     한 줄로 묶고 줄 안에서는 왼쪽자리로 세운다.
  2) 표가 쪽을 넘어가면 앞쪽에 머리글만 한 줄로 걸린다. 한 줄짜리라고 버리면서
     자리까지 지우면 그 머리글이 본문으로 샌다. 자리는 지우되 머리글은 다음 쪽
     첫 표의 머리로 넘긴다.
  3) 줄이 넘어가며 인용이 줄머리로 올라온 것을 조로 잘못 세우는 일이 있다
     (「…필터링의 대상은 / 제559조 제3항의 표」). 조 번호는 차례를 따라간다.

조 제목은 조 앞줄에 괄호로 붙는데 관 표제가 사이에 끼는 곳이 있다
(（계측）→ 第４款 計測 → 第４５７条). 다음 마디가 조이거나 편·장·절·관이면
조 제목으로 본다.
"""
import re

ZEN_NUM = str.maketrans("０１２３４５６７８９", "0123456789")
ZEN_AL = str.maketrans("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                       "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
KAN = "一二三四五六七八九十"
KANA = "イロハニホヘトチリヌ"

# 표제는 번호 뒤에 사이띄개가 온다. 그것이 없으면 표제가 아니라 인용이 줄머리로
# 올라온 것이다 — 「…第３編第２章第４節の細部測量及び…」 가 줄을 넘으며
# 「第４節の細部測量…」 로 시작해 절 하나가 더 서 버렸다.
RE_PYEON = re.compile(r"^第([０-９]{1,2})編(?:[ 　]+(.*))?$")
RE_JANG = re.compile(r"^第([０-９]{1,2})章(?:[ 　]+(.*))?$")
RE_JEOL = re.compile(r"^第([０-９]{1,2})節(?:[ 　]+(.*))?$")
RE_GWAN = re.compile(r"^第([０-９]{1,2})款(?:[ 　]+(.*))?$")
RE_JO = re.compile(r"^第([０-９]{1,3})条\s*(.*)$")
RE_PAREN = re.compile(r"^（(.+)）$")
# 새 줄을 여는 표시 — 이 가운데 하나로 시작하면 앞줄에 잇지 아니한다
RE_NEW = re.compile(r"^(?:第[０-９]+[編章節款]|第[０-９]{1,3}条|（"
                    r"|[" + KAN + r"]{1,2}\s|[" + KANA + r"]\s|[０-９]{1,2}\s)")
RE_PAGENO = re.compile(r"^\d{1,3}$")
RE_BOOK = re.compile(r"^附\s*則")

TBL_MARK = "\x00TBL%d\x00"          # 표가 놓일 자리 — 뒤에 <img id> 로 바꾼다
LEVELS = (("편", RE_PYEON), ("장", RE_JANG), ("절", RE_JEOL), ("관", RE_GWAN))


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def table_xml(tid, article, rows, source):
    cols = max(len(r) for r in rows)
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="{tid}" article="{esc(article)}" rows="{len(rows)}" '
         f'cols="{cols}" source="{esc(source)}">']
    for ri, cells in enumerate(rows):
        L.append("  <row>")
        for ci, c in enumerate(cells):
            head = ' header="1"' if ri == 0 else ""
            L.append(f'    <cell col="{ci}" row="{ri}"{head}>{esc(c)}</cell>')
        L.append("  </row>")
    L.append("</table>")
    return "\n".join(L)


def cell_rows(page, table):
    """표의 칸 글자를 자리로 다시 읽는다.

    pdfplumber 가 뽑아 주는 칸 글자는 차례가 뒤엉킬 때가 있다. 허용오차 식의
    √·Σ 는 밑선이 달라 딴 글자로 잡히는데, 그것이 칸 머리로 튀어나와
    「100mm+20mm√NΣS」 가 「100mm+20mm NΣS」 로, 「200mm＋50mmΣS/√N」 이
    「√ 200mm＋50mm S/ N」 으로 나왔다. 값이 아주 사라지지는 아니하나 식이
    망가진다. 그래서 칸의 자리(bbox)만 얻어 글자는 쪽에서 다시 읽는다.
    """
    import fitz
    out = []
    for row in table.rows:
        cells = []
        for c in row.cells:
            if not c:
                cells.append("")
                continue
            x0, y0, x1, y1 = c
            t = page.get_textbox(fitz.Rect(x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5))
            cells.append(re.sub(r"\s+", " ", t or "").strip())
        out.append(cells)
    return out


def read_items(pdf_page, page, carry=None):
    """한 쪽의 글줄과 표를 자리 차례로 모은다 — 표 자리에 든 글줄은 뺀다.
    → (모은 것, 다음 쪽으로 넘길 표 머리글)
    """
    boxes, items, nxt = [], [], None
    try:
        found = pdf_page.find_tables()
    except Exception:
        found = []
    for t in found:
        try:
            rows = cell_rows(page, t)
        except Exception:
            try:
                rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r]
                        for r in t.extract()]
            except Exception:
                continue
        rows = [r for r in rows if any(r)]
        boxes.append(t.bbox)            # 담지 아니할 표라도 자리는 적어 둔다
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            if len(rows) == 1 and max(len(r) for r in rows) >= 2:
                nxt = rows[0]
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

    items.sort(key=lambda v: v[0])
    row, rows = [], []
    for it in items:
        if row and it[0] - row[0][0] > 6:   # 줄 사이는 15pt 남짓
            rows.append(row); row = []
        row.append(it)
    if row:
        rows.append(row)
    out = []
    for r in rows:
        out += sorted(r, key=lambda v: v[1])
    return [(k, v) for _y, _x, k, v in out], nxt


def assemble(items, is_new=None):
    """줄이 넘어간 것을 잇는다 — 새 마디를 여는 표시로만 줄을 끊는다"""
    is_new = is_new or (lambda s: RE_NEW.match(s))
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


def parse(items, mk_node, first_jo=1, levels=LEVELS, jo=RE_JO, paren=RE_PAREN,
          stop=RE_BOOK):
    """편·장·절·관·조로 가른다.

    → (마디 목록 [(층, 마디)], 층별 셈, 표 [(조, 행)], 인용으로 보아 넘긴 번호)
    """
    out, cited, tables = [], [], []
    stack = {}                        # 층 이름 → 마디
    art, pending, lines = None, None, []
    count = {lv: 0 for lv, _ in levels}
    nxt_jo = first_jo

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
        if stop and stop.match(s):
            break

        hit = None
        for k, (lv, rx) in enumerate(levels):
            m = rx.match(s)
            if m:
                hit = (k, lv, m)
                break
        if hit is not None:
            k, lv, m = hit
            flush(); art, lines = None, []
            count[lv] += 1
            n = mk_node(lv, int(m.group(1).translate(ZEN_NUM)),
                        paren.sub(r"\1", (m.group(2) or "").strip()))
            for lv2, _ in levels[k:]:   # 아래 층은 새로 시작한다
                stack.pop(lv2, None)
            stack[lv] = n
            out.append((lv, n))
            continue

        m = jo.match(s)
        if m:
            # 차례를 따라간다 — 인용이 줄머리로 올라온 것을 조로 세우지 아니한다
            n = int(m.group(1).translate(ZEN_NUM))
            if n == nxt_jo:
                flush()
                art = mk_node("조", n, pending or "")
                pending, nxt_jo = None, n + 1
                lines = [m.group(2).strip()] if m.group(2).strip() else []
                out.append(("조", art))
                continue
            cited.append(n)

        m = paren.match(s)
        if m:
            nx = next((v.strip() for k2, v in items[i + 1:]
                       if k2 == "t" and v.strip()), "")
            if jo.match(nx) or any(rx.match(nx) for _, rx in levels):
                pending = m.group(1).strip()
                continue
        if art is None:
            continue
        lines.append(s)
    flush()
    return out, count, tables, cited


def build_tree(marks, levels=LEVELS):
    """[(층, 마디)] 를 나무로 세운다 — 위 층이 없으면 바로 위의 것에 붙인다"""
    order = [lv for lv, _ in levels] + ["조"]
    root, stack = [], {}
    for lv, n in marks:
        k = order.index(lv)
        parent = next((stack[order[j]] for j in range(k - 1, -1, -1)
                       if order[j] in stack), None)
        (parent["children"] if parent else root).append(n)
        stack[lv] = n
        for lv2 in order[k + 1:]:
            stack.pop(lv2, None)
    return root
