# -*- coding: utf-8 -*-
"""
신설 별표·별지의 서식을 만든다 — HWPX 파일과 편집기용 그림.

HWPX(ZIP+XML)를 손으로 조립해 보았으나 한/글이 '손상된 파일' 로 보았다
(zip·mimetype·XML·중복 문단 ID 는 모두 정상이었는데도 Open 이 실패했다).
규격을 끝까지 맞추는 대신, 이 컴퓨터에 깔린 한/글에게 저장을 맡긴다.

  내용(forms_data.py) → HTML → 한/글 COM → .hwpx · .pdf → .webp

이 컴퓨터에 이미 있는 HWPX 자동화 도구의 방식을 따른다
(환경변수 HWPX_AUTOMATION_HOME · scripts/forms_hwp.py 주석 참고).
한/글을 부를 수 없으면 HWPX 는 건너뛰고 그림만 그린다.

  서식 파일   App\관련규정\서식\별표29_안전관리비 계상 요율.hwpx
  편집기 그림 data/annex/draft2025/별표29_1.webp

사용:  python scripts/genforms.py
"""
import io, json, os, re, shutil, sys, tempfile, zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from forms_data import FORMS
import forms_hwp as HWP

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
APP = os.path.dirname(ROOT)
OUT_HWPX = os.path.join(APP, "관련규정", "서식")
# 개편안의 신설 별표는 현행 별표와 번호가 겹친다(현행 별표 29~40 이 따로 있다).
# 그림을 같은 자리에 두면 현행 것을 덮어쓰므로 개편안 전용 자리에 둔다.
DRAFT_KEY = "draft2025"
OUT_IMG = os.path.join(DATA, "annex", DRAFT_KEY)


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ───────────────────────── 편집기용 그림 ─────────────────────────
def draw(gubun, no, form, path):
    from PIL import Image, ImageDraw, ImageFont
    F = r"C:\Windows\Fonts\malgun.ttf"
    FB = r"C:\Windows\Fonts\malgunbd.ttf"
    f_title = ImageFont.truetype(FB, 30)
    f_head = ImageFont.truetype(FB, 17)
    f_body = ImageFont.truetype(F, 17)
    W, PAD = 1240, 44
    tmp = Image.new("RGB", (10, 10)); d0 = ImageDraw.Draw(tmp)

    def wrap(txt, font, w):
        out, line = [], ""
        for ch in str(txt or ""):
            if ch == "\n":
                out.append(line); line = ""; continue
            if d0.textlength(line + ch, font=font) > w and line:
                out.append(line); line = ch
            else:
                line += ch
        out.append(line)
        return out

    blocks = []                       # (종류, 값)
    blocks.append(("title", f"[{gubun} {no}] {form['title']}"))
    if form.get("blocks"):            # 여러 도막으로 된 서식
        for kind, val in form["blocks"]:
            if kind == "t":
                blocks.append(("table", val))
            else:
                for ln in (val if isinstance(val, (list, tuple)) else [val]):
                    blocks.append(("text", ln))
    else:
        for ln in form.get("note") or []:
            blocks.append(("text", ln))
        if form.get("table"):
            blocks.append(("table", form["table"]))
        for ln in form.get("after") or []:
            blocks.append(("text", ln))
        if form.get("table2"):
            blocks.append(("table", form["table2"]))

    # 높이 재기
    y = PAD
    plan = []
    for kind, val in blocks:
        if kind == "title":
            lines = wrap(val, f_title, W - 2 * PAD)
            plan.append((kind, lines)); y += 40 * len(lines) + 18
        elif kind == "text":
            lines = wrap(val, f_body, W - 2 * PAD)
            plan.append((kind, lines)); y += 26 * len(lines) + 8
        else:
            cols = max(len(r) for r in val)
            cw = (W - 2 * PAD) // cols
            rows = []
            for ri, cells in enumerate(val):
                fnt = f_head if ri == 0 else f_body
                cl = [wrap(cells[ci] if ci < len(cells) else "", fnt, cw - 18)
                      for ci in range(cols)]
                rows.append((cl, max(len(c) for c in cl)))
            plan.append((kind, (rows, cw, cols)))
            y += sum(26 * n + 16 for _, n in rows) + 16

    img = Image.new("RGB", (W, y + PAD), "white")
    d = ImageDraw.Draw(img)
    y = PAD
    for kind, val in plan:
        if kind == "title":
            for ln in val:
                d.text((PAD, y), ln, font=f_title, fill=(20, 30, 40)); y += 40
            y += 6
            d.line([(PAD, y), (W - PAD, y)], fill=(90, 110, 120), width=2); y += 12
        elif kind == "text":
            for ln in val:
                d.text((PAD, y), ln, font=f_body, fill=(30, 30, 30)); y += 26
            y += 8
        else:
            rows, cw, cols = val
            for ri, (cl, nl) in enumerate(rows):
                h = 26 * nl + 16
                if ri == 0:
                    d.rectangle([PAD, y, PAD + cw * cols, y + h], fill=(238, 242, 245))
                for ci in range(cols):
                    x = PAD + cw * ci
                    d.rectangle([x, y, x + cw, y + h], outline=(120, 135, 145), width=1)
                    for k, ln in enumerate(cl[ci]):
                        d.text((x + 9, y + 8 + 26 * k), ln,
                               font=f_head if ri == 0 else f_body, fill=(25, 25, 25))
                y += h
            y += 16
    img.save(path, "WEBP", quality=88, method=5)


if __name__ == "__main__":
    os.makedirs(OUT_HWPX, exist_ok=True)
    os.makedirs(OUT_IMG, exist_ok=True)

    ipath = os.path.join(DATA, "annex", "index.json")
    idx = json.load(io.open(ipath, encoding="utf-8")) if os.path.exists(ipath) else {}
    reg = idx.setdefault(DRAFT_KEY, {})

    hwp = None
    if HWP.available():
        try:
            hwp = HWP.Hwp()
        except Exception as ex:
            print(f"  [주의] 한/글을 부르지 못했습니다 ({ex}) — 그림만 만듭니다")
    else:
        print("  [주의] 이 컴퓨터에서는 한/글을 부를 수 없습니다 — 그림만 만듭니다")

    # 별표 번호는 개편안에서 다시 매겨지므로 손으로 적어 둔 것과 어긋날 수 있다.
    # 제목으로 찾아 실제 번호를 쓴다 — 제목은 그대로여도 번호는 바뀐다.
    live_no = {}
    dpath = os.path.join(DATA, "draft2025.json")
    if os.path.exists(dpath):
        doc = json.load(io.open(dpath, encoding="utf-8"))
        def _rec(ns):
            for x in ns:
                if not x.get("isDeleted") and x.get("annexRef"):
                    a = x["annexRef"]
                    live_no[(a.get("gubun") or "별표", (x.get("title") or "").strip())] =                         str(a.get("no"))
                _rec(x.get("children") or [])
        _rec(doc.get("tree") or [])

    tmp = tempfile.mkdtemp(prefix="forms_")
    n_hwpx = n_img = n_fix = 0
    try:
        for (gubun, key_no), form in sorted(FORMS.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            no = live_no.get((gubun, form["title"].strip()), str(key_no))
            if str(no) != str(key_no):
                n_fix += 1
                print(f"  [번호 맞춤] {gubun} {key_no} → {gubun} {no}  {form['title']}")
            stem = f"{gubun}{no}"
            img = os.path.join(OUT_IMG, f"{stem}_1.webp")
            made = ""

            if hwp is not None:
                html = os.path.join(tmp, stem + ".html")
                io.open(html, "w", encoding="utf-8").write(
                    HWP.html_of(gubun, no, form, esc))
                hwpx = os.path.join(OUT_HWPX, f"{stem}_{form['title']}.hwpx")
                pdf = os.path.join(tmp, stem + ".pdf")
                try:
                    r = hwp.convert(html, {HWP.HWPX: hwpx})
                    if r.get(HWP.HWPX):
                        # 한/글은 HTML 의 width:100% 를 글자 길이로 바꾸어 놓는다.
                        # 저장된 파일에서 표 폭을 본문폭에 맞춘 뒤 다시 열어 PDF 로 뽑는다
                        # (다시 열리는 것으로 파일이 성한지도 함께 확인된다).
                        fit = HWP.fit_tables(hwpx)
                        r = hwp.convert(hwpx, {HWP.PDF: pdf}, fmt=HWP.HWPX)
                        n_hwpx += 1
                        made = (f"{os.path.getsize(hwpx)//1024:>4}KB · {r.get('pages', 0)}쪽"
                                + (f" · 표 {len(fit)}개 폭맞춤" if fit else ""))
                    if r.get(HWP.PDF) and os.path.exists(pdf):
                        HWP.pdf_to_webp(pdf, img)      # 한/글이 조판한 그대로
                except Exception as ex:
                    print(f"  [오류] {stem}: {ex}")

            if not os.path.exists(img):
                draw(gubun, no, form, img)             # 한/글이 없을 때의 대비
            reg[stem] = [f"{stem}_1.webp"]
            n_img += 1
            print(f"  {stem:>6}  {form['title'][:32]:<34} {made}"
                  f"{' · 그림 ' + str(os.path.getsize(img)//1024) + 'KB'}")
    finally:
        if hwp is not None:
            hwp.close()
        shutil.rmtree(tmp, ignore_errors=True)

    # 별표 번호가 바뀌면 옛 번호로 만든 파일이 그대로 남아, 서식 폴더를 열었을 때
    # 어느 것이 지금 것인지 알 수 없다. 지우지는 아니하고 '_지난번호' 로 치운다.
    keep = {f"{g}{live_no.get((g, fm['title'].strip()), str(n))}_{fm['title']}.hwpx"
            for (g, n), fm in FORMS.items()}
    old_dir = os.path.join(OUT_HWPX, "_지난번호")
    moved = 0
    for f in os.listdir(OUT_HWPX):
        if not f.endswith(".hwpx") or f in keep:
            continue
        m = re.match(r"(별[표지]\d+)_(.+)\.hwpx$", f)
        if not m:
            continue                       # 우리가 만든 이름이 아니면 건드리지 아니한다
        os.makedirs(old_dir, exist_ok=True)
        dst = os.path.join(old_dir, f)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.move(os.path.join(OUT_HWPX, f), dst)
        moved += 1

    with io.open(ipath, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))

    print()
    print(f"서식 HWPX {n_hwpx}건 → {OUT_HWPX}")
    print(f"편집기 그림 {n_img}장 → {OUT_IMG}")
    if moved:
        print(f"옛 번호로 남아 있던 서식 {moved}건을 _지난번호 로 치웠습니다")
    if n_fix:
        print(f"개편안에서 번호가 바뀌어 맞춘 서식 {n_fix}건")
