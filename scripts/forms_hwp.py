# -*- coding: utf-8 -*-
"""
서식을 한/글에게 맡겨 만든다 — HTML 을 넘기면 한/글이 HWPX 와 PDF 로 저장한다.

이 컴퓨터에는 이미 HWPX 자동화 도구가 갖추어져 있다 (환경변수 HWPX_AUTOMATION_HOME).
그 도구의 방식을 그대로 따른다 — 보안 모듈 이름은 FilePathCheckerModuleExample,
한 건을 마치면 Clear(1) 로 비우고, PageCount 로 쪽수를 확인한다.
  render_hwpx_to_pdf.ps1   HWPX → PDF (한컴 COM)
  validate_hwpx_package.py ZIP·mimetype·XML·중복 문단 ID 점검
  render_pdf_pages.py      PDF → PNG

HWPX(ZIP+XML)를 손으로 조립해 보았으나 한/글이 '손상된 파일' 로 보았다.
쪽 설정·줄 정보·목록 파일까지 맞추어도 열리지 않았다. 규격을 완전히 맞추는
대신, 이 컴퓨터에 깔린 한/글에게 저장을 맡긴다.

  HTML  →  한/글 COM(HWPFrame.HwpObject)  →  .hwpx · .pdf
  .pdf  →  PyMuPDF  →  .webp (편집기 미리보기)

한/글이 없는 컴퓨터에서는 이 길을 쓸 수 없으므로, 부르는 쪽에서
available() 로 먼저 확인하고 없으면 그림만 그린다.
"""
import os, sys

HWPX, PDF = "HWPX", "PDF"


def available():
    """이 컴퓨터에서 한/글을 부를 수 있는가"""
    try:
        import win32com.client  # noqa
        import winreg
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "HWPFrame.HwpObject")
        return True
    except Exception:
        return False


class Hwp:
    """한/글 한 벌을 열어 두고 여러 건을 잇달아 저장한다"""

    def __init__(self):
        import win32com.client as w
        self.app = w.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            # 파일 접근 때마다 뜨는 보안 물음을 끈다
            # 기존 도구(render_hwpx_to_pdf.ps1)가 쓰는 이름을 그대로 쓴다
            self.app.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample")
        except Exception:
            pass

    def convert(self, src_path, out_paths, fmt="HTML"):
        """파일 하나를 열어 여러 형식으로 저장한다 — {형식: 경로}"""
        src = os.path.abspath(src_path)
        if not self.app.Open(src, fmt, "forceopen:true"):
            raise RuntimeError(f"한/글이 파일을 열지 못했습니다({fmt}): {src}")
        done = {}
        for fmt, path in out_paths.items():
            path = os.path.abspath(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            done[fmt] = bool(self.app.SaveAs(path, fmt, ""))
        try:
            done["pages"] = int(self.app.PageCount)
        except Exception:
            done["pages"] = 0
        try:
            self.app.Clear(1)            # 다음 건을 위해 비운다
        except Exception:
            pass
        return done

    def close(self):
        try:
            self.app.Quit()
        except Exception:
            pass


def html_of(gubun, no, form, esc):
    """서식 한 건을 HTML 로 — 한/글이 표와 글자 크기를 그대로 옮겨 준다"""
    def tbl(rows):
        out = ['<table border="1" cellspacing="0" '
               'style="width:100%;border-collapse:collapse">']
        for ri, cells in enumerate(rows):
            tag = "th" if ri == 0 else "td"
            bg = ' style="background:#eef2f5"' if ri == 0 else ""
            out.append("<tr>" + "".join(
                f'<{tag}{bg}>{esc(c).replace(chr(10), "<br>")}</{tag}>' for c in cells)
                + "</tr>")
        out.append("</table>")
        return "".join(out)

    body = [f'<p style="font-size:11pt">[{esc(gubun)} {no}]</p>',
            f'<h2 style="font-size:16pt">{esc(form["title"])}</h2>']

    # 여러 도막으로 된 서식은 blocks 로 적는다 — ("h", 소제목) · ("p", [글줄]) · ("t", 표)
    # 도막이 둘뿐인 서식은 예전처럼 note·table·after·table2 로 적어도 된다.
    if form.get("blocks"):
        for kind, val in form["blocks"]:
            if kind == "h":
                body.append(f'<p style="font-size:12pt;font-weight:bold;'
                            f'margin-top:10pt">{esc(val)}</p>')
            elif kind == "p":
                for ln in (val if isinstance(val, (list, tuple)) else [val]):
                    body.append(f'<p style="font-size:11pt">{esc(ln)}</p>')
            elif kind == "t":
                body.append(tbl(val))
        return ('<html><head><meta charset="utf-8">'
                '<style>body{font-family:"맑은 고딕";} '
                'td,th{padding:4px 6px;font-size:10.5pt;vertical-align:middle}</style>'
                "</head><body>" + "".join(body) + "</body></html>")

    for ln in form.get("note") or []:
        body.append(f'<p style="font-size:11pt">{esc(ln)}</p>')
    if form.get("table"):
        body.append(tbl(form["table"]))
    for ln in form.get("after") or []:
        body.append(f'<p style="font-size:11pt">{esc(ln)}</p>')
    if form.get("table2"):
        body.append("<p></p>")
        body.append(tbl(form["table2"]))
    return ('<html><head><meta charset="utf-8">'
            '<style>body{font-family:"맑은 고딕";} '
            'td,th{padding:4px 6px;font-size:10.5pt;vertical-align:middle}</style>'
            "</head><body>" + "".join(body) + "</body></html>")


def pdf_to_webp(pdf_path, out_path, zoom=2.0):
    """PDF 첫 쪽을 그림으로 — 한/글이 조판한 그대로 보인다"""
    import fitz
    with fitz.open(pdf_path) as d:
        if not d.page_count:
            return False
        pix = d[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.pil_save(out_path, format="WEBP", quality=88, method=5)
    return True


# ───────────────────────── 표를 문서 폭에 맞추기 ─────────────────────────
def fit_tables(hwpx_path):
    """표 폭을 본문폭에 맞춘다 — 칸 비율은 그대로 두고 함께 늘리거나 줄인다.

    한/글은 HTML 의 width:100% 를 그대로 받지 않고 글자 길이로 표 폭을 정한다.
    그래서 어떤 표는 본문폭에 못 미치고 어떤 표는 넘친다(A4 세로 기준 본문폭
    42520 HWPUNIT = 150mm). 한/글이 저장해 둔 파일에서 폭 숫자만 그 자리에서
    고친다 — XML 을 다시 쓰면 이름공간 접두사가 바뀌어 한/글이 거부하므로
    구조는 손대지 않는다.

    반환: [(전, 후), …]  (HWPUNIT)
    """
    import re, shutil, tempfile, zipfile

    with zipfile.ZipFile(hwpx_path) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}

    sec = next((n for n in names if re.match(r"Contents/section\d+\.xml$", n)), None)
    if not sec:
        return []
    xml = blobs[sec].decode("utf-8")

    pp = re.search(r"<hp:pagePr\b[^>]*>", xml)
    mg = re.search(r"<hp:margin\b[^>]*>", xml)
    if not (pp and mg):
        return []

    def val(tag, key):
        m = re.search(rf'\b{key}="(\d+)"', tag)
        return int(m.group(1)) if m else 0

    target = (val(pp.group(0), "width") - val(mg.group(0), "left")
              - val(mg.group(0), "right") - val(mg.group(0), "gutter"))
    if target <= 0:
        return []

    RE_TBL = re.compile(r"<hp:tbl\b.*?</hp:tbl>", re.S)
    RE_SZ = re.compile(r'(<hp:sz\b[^>]*?\bwidth=")(\d+)(")')
    RE_TR = re.compile(r"<hp:tr\b.*?</hp:tr>", re.S)
    RE_CELL = re.compile(r'(<hp:cellSz\b[^>]*?\bwidth=")(\d+)(")')

    changed = []

    # 좁은 칸의 최소 폭 — '2.93%' 한 줄이 들어갈 만큼 (17mm)
    MIN = round(17 * 7200 / 25.4)

    def one_row(row):
        cells = RE_CELL.findall(row)
        if not cells:
            return row
        ws = [int(c[1]) for c in cells]
        tot = sum(ws) or 1
        new = [max(1, round(w * target / tot)) for w in ws]
        new[-1] += target - sum(new)              # 나머지는 마지막 칸이 받는다

        # 좁은 칸을 최소 폭까지 넓히고, 모자라는 만큼은 넉넉한 칸에서 덜어 낸다
        if MIN * len(new) <= target:
            short = sum(MIN - w for w in new if w < MIN)
            if short:
                spare = [i for i, w in enumerate(new) if w > MIN]
                room = sum(new[i] - MIN for i in spare) or 1
                for i in spare:
                    new[i] -= round(short * (new[i] - MIN) / room)
                new = [max(w, MIN) for w in new]
                big = max(range(len(new)), key=lambda i: new[i])
                new[big] += target - sum(new)      # 반올림 나머지

        it = iter(new)
        return RE_CELL.sub(lambda m: m.group(1) + str(next(it)) + m.group(3), row)

    def one_tbl(m):
        tbl = m.group(0)
        sz = RE_SZ.search(tbl)                    # 표 자체의 폭 (맨 앞의 hp:sz)
        if not sz:
            return tbl
        now = int(sz.group(2))
        if not now or now == target:
            return tbl
        changed.append((now, target))
        tbl = tbl[:sz.start()] + sz.group(1) + str(target) + sz.group(3) + tbl[sz.end():]
        return RE_TR.sub(lambda r: one_row(r.group(0)), tbl)

    fixed = RE_TBL.sub(one_tbl, xml)
    if not changed:
        return []

    blobs[sec] = fixed.encode("utf-8")
    tmp = tempfile.mktemp(suffix=".hwpx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for n in names:                            # mimetype 은 반드시 무압축·맨 앞
            out.writestr(n, blobs[n],
                         zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
    shutil.move(tmp, hwpx_path)
    return changed
