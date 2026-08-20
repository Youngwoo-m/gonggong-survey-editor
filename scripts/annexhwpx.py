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
import annexdoc

# 마디 깊이별 왼쪽 들여쓰기 (mm)
INDENT = [0.0, 6.0, 12.0, 18.0]
BODY_PT = 10.0
NOTE_PT = 9.0
# 표의 너비 — A4 너비 210mm 에서 좌우 여백 40mm 를 뺀 170mm.
# 한글의 자리단위(HWPUNIT)는 1인치가 7200 이다.
TABLE_W = int(170.0 / 25.4 * 7200)


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
             before=0.0, after=0.0, hanging=True):
        p = self.doc.add_paragraph(text, char_pr_id_ref=self.st[style])
        idx = len(self.doc.paragraphs) - 1
        # 정렬은 반드시 못박는다 — 빈 문서의 물림값이 가운데라, 맡겨 두면
        # 본문 둘째 줄부터 가운데로 몰려 규정 글로 보이지 아니한다
        kw = {"paragraph_index": idx, "line_spacing_percent": 160,
              "alignment": align or "JUSTIFY",
              "spacing_before_pt": before, "spacing_after_pt": after}
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
            self.para(caption, "cap", before=4, after=1, hanging=False)
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
        # 칸너비 — 그 칸에 들어가는 가장 긴 글에 맞추어 저울질한다.
        # (몫으로 주면 되고, 실제 너비는 한글이 나눈다)
        try:
            w = []
            for c in range(ncol):
                n = max([len(str(head[c]))] + [len(str(r[c])) for r in rows if c < len(r)])
                w.append(max(4, min(36, n)))
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
        if fixns:
            fixns(dst)
        return dst


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
