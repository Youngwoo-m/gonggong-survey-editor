# -*- coding: utf-8 -*-
"""덩이로 나눈 별표 본문을 HWPX 로 조판한다.

여태는 본문 글을 그대로 한 줄씩 흘렸다. 그러면
  ㆍ 표가 '┌ ├' 글자로 남아 종이에서 표로 읽히지 아니하고
  ㆍ <img id="tNNNN"> 표식이 글자 그대로 박히며 정작 표는 빠지고
  ㆍ 마디의 깊이(1. 가. 1) 가) 가 눈에 들어오지 아니한다
그래서 annexdoc.parse() 가 나눈 덩이를 보고 표는 표로, 마디는 들여쓰기로 세운다.

  머리     [별표 15]  ·  제목(가운데ㆍ굵게)  ·  규정 이름(작게)
  마디     1. → 0mm · 가. → 6mm · 1) → 12mm · 가) → 18mm
  주(※)    한 단 더 들여 작은 글씨
  표       머리줄에 바탕색을 깔고 칸너비를 글자 수에 맞추어 나눈다
  보기값   〔 〕 는 글자 그대로 둔다 — 종이에서도 보기값임이 드러나야 한다
"""
import os
import re
import annexdoc

# 마디 깊이별 왼쪽 들여쓰기 (mm)
INDENT = [0.0, 6.0, 12.0, 18.0]
BODY_PT = 10.0
NOTE_PT = 9.0
# 표의 너비 — A4 너비 210mm 에서 좌우 여백 40mm 를 뺀 170mm.
# 한글의 자리단위(HWPUNIT)는 1인치가 7200 이다.
TABLE_W = int(170.0 / 25.4 * 7200)


# 머리글 한 글자의 어림 너비(mm). 9pt 함초롬돋움 한글 기준으로 잡았다.
HEAD_CHAR_MM = 3.4
HEAD_PAD_MM = 3.0
TABLE_MM = 170.0


# 접히면 안 되는 낱말의 길이를 여기까지만 센다. 긴 낱말 하나가 표를
# 통째로 끌고 가지 못하게 하는 마개다.
FLOOR_CAP = 6


def _longest_word(xs):
    """가장 긴 낱말의 글자 수 — 빈칸에서 끊기지 않는 덩어리를 잰다"""
    n = 0
    for t in xs:
        for w in re.split(r"\s+", str(t or "")):
            n = max(n, len(w))
    return n


def fit_head(w, head, rows=None, total_mm=TABLE_MM):
    """칸 폭을 정한다 — 바닥을 먼저 채우고 남은 자리를 몫대로 나눈다.

    처음에는 몫만 주었다. 표 전체 너비가 정해져 있어 몫이 작은 칸은 아주
    좁아졌고, 「지속 시간」이 12mm 로 눌려 머리글이 옆 칸과 겹쳤다.

    그 다음에는 머리글이 들어갈 만큼만 넓혔다. 그래도 「공사종류」 칸은
    8mm 밖에 되지 않아 「특수건설공사」가 '특수/건설/공사' 로 접혔다.
    머리글은 넉 자인데 칸 글이 여섯 자였기 때문이다. 게다가 머리글이 긴
    표에서는 바닥의 합이 표를 넘어, 모두 비례로 줄면서 작은 칸이 다시
    눌렸다.

    그래서 두 걸음으로 나눈다.

      바닥   그 칸에서 가장 긴 '낱말' 이 접히지 않을 만큼 (여섯 자까지)
      나머지 남은 자리를 글자 수 몫대로

    바닥의 합이 표의 아홉 할을 넘으면 바닥끼리 고르게 줄인다 — 넘칠 바에는
    고르게 좁히는 편이 한 칸만 뭉개지는 것보다 낫다."""
    n = len(head)
    w = [float(x) for x in w]
    floor = []
    for i in range(n):
        xs = [head[i]]
        if rows:
            xs += [r[i] for r in rows if i < len(r)]
        c = min(_longest_word(xs), FLOOR_CAP)
        floor.append(max(c, 2) * HEAD_CHAR_MM + HEAD_PAD_MM)
    cap = total_mm * 0.9
    if sum(floor) > cap:
        k = cap / sum(floor)
        floor = [x * k for x in floor]
    rest = total_mm - sum(floor)
    s = sum(w) or 1.0
    mm = [floor[i] + rest * w[i] / s for i in range(n)]
    # 몫으로 돌려준다 — 실제 너비는 한글이 이 몫대로 나눈다
    return [max(1, int(round(x * 100.0 / total_mm))) for x in mm]


class Builder:
    def __init__(self):
        from hwpx.document import HwpxDocument
        self.doc = HwpxDocument.new()
        self.doc.set_page_setup(paper_size="A4", orientation="portrait",
                                margin_left_mm=20, margin_right_mm=20,
                                margin_top_mm=20, margin_bottom_mm=18)
        self._first = True
        self.left_pr = self._para_pr(alignment="LEFT", line_spacing_percent=130)
        self.st = {
            "title": self.doc.ensure_run_style(bold=True, size=15, font="함초롬돋움"),
            "label": self.doc.ensure_run_style(size=10, font="함초롬돋움"),
            "sub": self.doc.ensure_run_style(size=9, font="함초롬바탕", color="#666666"),
            "body": self.doc.ensure_run_style(size=BODY_PT, font="함초롬바탕"),
            "note": self.doc.ensure_run_style(size=NOTE_PT, font="함초롬바탕", color="#444444"),
            "th": self.doc.ensure_run_style(bold=True, size=9, font="함초롬돋움"),
            "td": self.doc.ensure_run_style(size=9, font="함초롬바탕"),
            "cap": self.doc.ensure_run_style(size=9, font="함초롬돋움", color="#333333"),
        }

    def _para_pr(self, **fmt):
        """문단 모양 하나를 만들어 그 번호만 얻는다 — 표 칸에 물려 주려는 것이다.

        만들 길이 이것뿐이라, 임시 글줄을 하나 두었다가 걷어낸다."""
        self.doc.add_paragraph("")
        idx = len(self.doc.paragraphs) - 1
        try:
            r = self.doc.set_paragraph_format(paragraph_index=idx, **fmt)
            pid = (r.get("paragraphs") or [{}])[0].get("paraPrIDRef")
        except Exception:
            pid = None
        try:
            self.doc.remove_paragraph(idx)
        except Exception:
            pass
        return pid

    # ------------------------------------------------------------------ 글줄
    def para(self, text="", style="body", *, indent=0.0, align=None,
             before=0.0, after=0.0, hanging=True, keep=False):
        p = self.doc.add_paragraph(text, char_pr_id_ref=self.st[style])
        idx = len(self.doc.paragraphs) - 1
        # 정렬은 반드시 못박는다 — 빈 문서의 물림값이 가운데라, 맡겨 두면
        # 본문 둘째 줄부터 가운데로 몰려 규정 글로 보이지 아니한다
        kw = {"paragraph_index": idx, "line_spacing_percent": 160,
              "alignment": align or "JUSTIFY",
              "spacing_before_pt": before, "spacing_after_pt": after}
        # 표 이름은 표와 붙여 둔다 — 쪽이 갈리면 이름만 앞 쪽에 홀로 남는다
        if keep:
            kw["keep_with_next"] = True
        if indent:
            kw["indent_left_mm"] = indent
            # 글머리(1. 가.)가 왼쪽으로 걸리게 첫 줄만 내어 쓴다
            if hanging:
                kw["first_line_indent_mm"] = -5.0
        try:
            self.doc.set_paragraph_format(**kw)
        except Exception:
            pass
        return p

    # ------------------------------------------------------------------ 머리
    def head(self, gubun, no, title, regname, subtitle=""):
        self.para("[%s %s]" % (gubun, no), "label", after=2)
        self.para(title, "title", align="center", before=2, after=2, hanging=False)
        if subtitle:
            self.para(subtitle, "sub", align="center", after=2, hanging=False)
        self.para(regname, "sub", align="center", after=8, hanging=False)

    # -------------------------------------------------------------------- 표
    def table(self, head, rows, caption=""):
        if caption:
            self.para(caption, "cap", before=4, after=1, hanging=False, keep=True)
        ncol = len(head)
        # (비고)처럼 첫 칸에만 글이 있는 줄은 표 밑의 주로 내린다 —
        # 표 안에 두면 한 칸이 길게 늘어져 나머지 칸이 빈 채로 벌어진다
        notes = []
        body = []
        for r in rows:
            cells = [str(x or "").strip() for x in r]
            if ncol > 1 and cells[0] and not any(cells[1:]):
                notes.append(cells[0])
            else:
                body.append(r)
        rows = body
        if not rows:
            for x in notes:
                self.para(x, "note", indent=INDENT[1], hanging=False)
            return None
        t = self.doc.add_table(len(rows) + 1, ncol,
                               width=TABLE_W, para_pr_id_ref=self.left_pr)
        for c, txt in enumerate(head):
            t.set_cell_text(0, c, str(txt), preserve_format=False)
            try:
                t.set_cell_shading(0, c, "#EFEFEF")
            except Exception:
                pass
        for r, row in enumerate(rows, start=1):
            for c in range(ncol):
                t.set_cell_text(r, c, str(row[c]) if c < len(row) else "",
                                preserve_format=False)
        # 칸너비 — 몫으로 준다 (실제 너비는 한글이 나눈다).
        #
        # 처음에는 그 칸의 '가장 긴 글' 에 맞추었다. 그러니 긴 칸 하나가 몫을
        # 다 가져가, 짧은 칸이 지나치게 눌려 「1구역」이 「1 구 / 역」으로
        # 접혔다(별지 4의 표본 표).
        #
        # 그래서 머리글 길이를 바닥으로 삼고 칸 글의 평균으로 저울질한다.
        # 머리글이 접히면 표를 읽을 수 없으므로 그것이 바닥이 되어야 한다.
        try:
            w = []
            for c in range(ncol):
                xs = [len(str(r[c])) for r in rows if c < len(r) and str(r[c]).strip()]
                avg = (sum(xs) / len(xs)) if xs else 0
                n = max(len(str(head[c])), avg)
                w.append(int(max(6, min(30, round(n)))))
            # 머리글이 접히면 표를 읽을 수 없다 — 한 줄에 담기도록 넓힌다
            w = fit_head(w, head, rows)
            t.set_column_widths(w)
        except Exception:
            pass
        for x in notes:
            self.para(x, "note", indent=INDENT[1], hanging=False)
        return t

    def obj_table(self, path):
        got = annexdoc.obj_table(path)
        if not got:
            return False
        head, rows, name = got
        self.table(head, rows, caption=("〈%s〉" % name) if name else "")
        return True

    # ---------------------------------------------------------------- 덩이들
    def blocks(self, blocks, objdir=None):
        for b in blocks:
            k = b["kind"]
            if k == "blank":
                continue
            if k == "para":
                lv = int(b.get("level", 0))
                self.para(b["text"], "body", indent=INDENT[min(lv, 3)],
                          before=(3.0 if lv == 0 else 1.0))
            elif k == "note":
                self.para(b["text"], "note", indent=INDENT[1], before=2, hanging=False)
            elif k == "table":
                self.table(b["head"], b["rows"])
                self.para("", "body", after=2, hanging=False)
            elif k == "obj":
                p = os.path.join(objdir or "", b["id"] + ".xml")
                if not (objdir and os.path.exists(p) and self.obj_table(p)):
                    self.para("(표 %s — 원본에서 옮겨야 합니다)" % b["id"], "note",
                              indent=INDENT[1], hanging=False)
                self.para("", "body", after=2, hanging=False)

    def save(self, dst, fixns=None):
        self.doc.save_to_path(dst)
        _fix_orientation(dst)
        _left_align_cells(dst, self.left_pr)
        if fixns:
            fixns(dst)
        return dst


def _match_close(x, pos, open_tag, close_tag):
    """짝이 맞는 닫는 태그 자리 — 칸 안에 또 표가 있어도 속지 않는다"""
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


def _left_align_cells(path, left_pr):
    """표 칸 안의 문단을 왼쪽 정렬로 바꾼다.

    set_cell_text 는 칸 문단의 문단모양을 0번으로 되돌린다. 0번은 양쪽
    정렬이라, 좁은 칸에서 'C-05' 한 낱말이 칸 너비만큼 늘어나
    'C  -  0  5' 처럼 벌어졌다. add_table 에 왼쪽 정렬을 주어도 칸 글을
    쓰는 순간 지워지므로, 다 쓴 뒤에 표 안의 문단만 골라 바꾼다."""
    import re as _re
    import shutil as _sh
    import zipfile as _zip
    if not left_pr:
        return
    with _zip.ZipFile(path) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}
    sec = next((n for n in names
                if _re.match(r"Contents/section\d+\.xml$", n)), None)
    if not sec:
        return
    x = blobs[sec].decode("utf-8")
    out, i = [], 0
    while True:
        s = x.find("<hp:tbl ", i)
        if s < 0:
            out.append(x[i:])
            break
        e = _match_close(x, s + len("<hp:tbl "), "<hp:tbl ", "</hp:tbl>")
        e += len("</hp:tbl>")
        out.append(x[i:s])
        out.append(_re.sub(r'(<hp:p [^>]*paraPrIDRef=")0(")',
                           r"\g<1>%s\g<2>" % left_pr, x[s:e]))
        i = e
    blobs[sec] = "".join(out).encode("utf-8")
    tmp = path + ".tmp"
    with _zip.ZipFile(tmp, "w") as o:
        for n in names:
            o.writestr(n, blobs[n],
                       _zip.ZIP_STORED if n == "mimetype" else _zip.ZIP_DEFLATED)
    _sh.move(tmp, path)


MIN_ROW = 2000          # 칸의 밑높이 (한 줄)
# 글 한 줄의 높이. 10pt 글자에 줄 간격이 160% 이므로 16pt, 곧 1600 이다.
# 처음에 1150 으로 잡았다가 세 줄짜리 칸의 마지막 줄이 잘렸다.
LINE_H = 1700
CHAR_W = 1000           # 한글 한 글자의 너비 (10pt)
PAD = 1100              # 칸의 좌우 여백을 합한 것


def _row_height(cells):
    """한 행에 필요한 높이 — 칸마다 몇 줄로 접히는지 재어 가장 긴 것을 쓴다.

    python-hwpx 는 칸 높이를 3600 으로 박아 넣고, 한/글은 열 때 그 값을 그대로
    지킨다. 그래서 글이 길면 칸 밖으로 넘쳐 잘렸다(별지 4의 마지막 행에서
    '뽑았다' 가 잘렸다). 낮게 적어 두어도 한/글이 늘려 주지 아니하였다.
    그러니 필요한 높이를 우리가 재어 넣는다.

    cells 는 [(칸 너비, 글)] 이다."""
    import math
    need = 1
    for w, t in cells:
        per = max(1, (w - PAD) / CHAR_W)
        lines = 0
        for seg in str(t).split("\n"):
            lines += max(1, math.ceil(len(seg) / per))
        need = max(need, lines)
    return max(MIN_ROW, int(need * LINE_H + 350))


def _loosen_rows(xml):
    """표의 행 높이를 글에 맞추어 다시 잡는다"""
    import re as _re

    RE_T = _re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", _re.S)

    def one_tbl(m):
        s = m.group(0)
        total = 0

        def one_row(rm):
            nonlocal total
            row = rm.group(0)
            cells = []
            for tc in _re.finditer(r"<hp:tc\b.*?</hp:tc>", row, _re.S):
                c = tc.group(0)
                wm = _re.search(r'<hp:cellSz width="(\d+)"', c)
                txt = "".join(t.group(1) for t in RE_T.finditer(c))
                cells.append((int(wm.group(1)) if wm else 5000, txt))
            h = _row_height(cells)
            total += h
            return _re.sub(r'(<hp:cellSz\b[^>]*\bheight=")\d+(")',
                           r"\g<1>" + str(h) + r"\g<2>", row)

        s = _re.sub(r"<hp:tr>.*?</hp:tr>", one_row, s, flags=_re.S)
        return _re.sub(r'(<hp:sz\b[^>]*\bheight=")\d+(")',
                       r"\g<1>" + str(max(total, MIN_ROW)) + r"\g<2>",
                       s, count=1)

    return _re.sub(r"<hp:tbl\s[^>]*>.*?</hp:tbl>", one_tbl, xml, flags=_re.S)


def _fix_orientation(path):
    """쪽 방향을 세로로 바로잡는다.

    python-hwpx 는 pagePr 의 landscape 에 'PORTRAIT' 를 적는데, 한글은 그 값을
    알아듣지 못하고 쪽을 가로로 눕혀 버린다. A4 세로로 세운 별표가 가로로
    나오던 까닭이 이것이다.

    셋을 다 뽑아 재어 보았다 (쪽 크기, 단위 pt).
        PORTRAIT   841 x 595   ← 가로
        NARROWLY   841 x 595   ← 가로
        WIDELY     595 x 841   ← 세로
    이름과 뜻이 어긋나 보이나, 재어 본 것이 이러하므로 WIDELY 를 쓴다."""
    import zipfile, shutil, os as _os
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename.startswith("Contents/") and it.filename.endswith(".xml"):
                t = data.decode("utf-8")
                t = t.replace('landscape="PORTRAIT"', 'landscape="WIDELY"')
                t = t.replace('landscape="NARROWLY"', 'landscape="WIDELY"')
                t = _loosen_rows(t)
                data = t.encode("utf-8")
            zout.writestr(it, data)
    _os.replace(tmp, path)


def build(dst, *, gubun, no, title, regname, body, objdir=None, fixns=None):
    """별표 하나를 HWPX 로 짓는다"""
    b = Builder()
    blocks = annexdoc.parse(body)
    # 본문 첫 줄이 제목을 되풀이하면 부제로 올린다
    sub = ""
    if blocks and blocks[0]["kind"] == "para" and blocks[0]["text"].strip() == title.strip():
        blocks = blocks[1:]
        while blocks and blocks[0]["kind"] == "blank":
            blocks = blocks[1:]
    if blocks and blocks[0]["kind"] == "para":
        t0 = blocks[0]["text"].strip()
        if t0.startswith("(제") and t0.endswith(")"):      # (제28조제2항) 따위
            sub = t0
            blocks = blocks[1:]
    b.head(gubun, no, title, regname, sub)
    b.blocks(blocks, objdir=objdir)
    return b.save(dst, fixns=fixns)
