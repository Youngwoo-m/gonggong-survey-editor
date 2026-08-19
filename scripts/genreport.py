# -*- coding: utf-8 -*-
r"""
개편안 보고서 한 벌을 만들어 zip 으로 묶는다.

  개정(안).hwpx                  편·장·절·관 차례대로 담은 조문 전문
  개정(안)_별표및별지모음/         별표 57 · 별지 5 — 신설한 것은 우리가 만든 서식,
                                 그대로 두는 것은 현행 원본을 새 번호로 담는다
  개정사유서.hwpx                조문마다 [변경 사유] 다섯 도막
  개정(안)_신구대조표.hwpx        현행 ↔ 개편안 두 칸 대조

■ HWPX 는 한/글에게 맡긴다

  HWPX(ZIP+XML)를 손으로 조립하면 한/글이 '손상된 파일' 로 본다 (forms_hwp.py
  주석 참고). 이 컴퓨터에 깔린 한/글에게 HTML 을 넘겨 저장하게 한다.
  한/글을 부를 수 없는 컴퓨터에서는 HTML 까지만 만들고 멈춘다.

■ 별표·별지를 어디에서 가져오는가

  신설·변경한 것   App\관련규정\서식\*.hwpx          (genforms.py 가 만든 것)
  그대로 두는 것   App\관련규정\공공측량작업규정\별표서식\*.hwp

  현행 별표는 개편안에서 번호가 다시 매겨지므로 새 번호로 이름을 바꾸어 담고,
  옛 번호를 파일 이름에 함께 적어 둔다 — 어느 것이 어느 것인지 알 수 있게.

사용:  python scripts/genreport.py [-o 출력폴더]
출력:  data/report/개정보고서_YYYYMMDD.zip  (앱에서 내려받는 자리)
"""
import datetime as _dt
import io, json, os, re, shutil, sys, tempfile, zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forms_hwp as HWP

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
APP = os.path.dirname(ROOT)
REG = os.path.join(APP, "관련규정")
FORMS_NEW = os.path.join(REG, "서식")
FORMS_OLD = os.path.join(REG, "공공측량작업규정", "별표서식", "공공측량 작업규정")
OUT_DIR = os.path.join(DATA, "report")

RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"\s*>(?:</img>)?')
RE_PROV = re.compile(r"<현행[^<>]*>")
HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
# 표 머리 색은 칸마다 직접 준다. <style> 의 th 규칙을 한/글이 검은 띠로 그려
# 머리글이 보이지 않았다 — 잘 도는 forms_hwp.html_of 도 칸마다 직접 준다.
TH_STYLE = ' style="background:#eef2f5;color:#000;font-weight:bold"' 


def esc(s):
    """글 안에 넣을 것 — 큰따옴표는 건드리지 아니한다.

    한/글의 HTML importer 는 &quot; 를 풀지 못한다. 「"공공측량"이란」 이
    「&공공측량&이란」 으로 나왔다. 글 안에서는 큰따옴표를 그대로 두어도
    HTML 에 어긋나지 아니한다 — 값 자리에 넣을 때에만 감싸면 된다.
    """
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


# ───────────────────────── 본문 속 표 ─────────────────────────
_tbl = {}


def table_html(oid, regid="reg01"):
    """objects 에 담아 둔 표 XML 을 HTML 표로"""
    if oid in _tbl:
        return _tbl[oid]
    html = ""
    for rid in (regid, "draft2025", "reg01"):
        p = os.path.join(DATA, "objects", rid, oid + ".xml")
        if os.path.exists(p):
            s = io.open(p, encoding="utf-8").read()
            rows = re.findall(r"<row>(.*?)</row>", s, re.S)
            out = ['<table border="1" cellspacing="0" cellpadding="3" width="100%">']
            for ri, r in enumerate(rows):
                cells = re.findall(r"<cell[^>]*>([^<]*)</cell>", r)
                tag = "th" if ri == 0 else "td"
                st = TH_STYLE if ri == 0 else ""
                out.append("<tr>" + "".join(f"<{tag}{st}>{esc(c)}</{tag}>"
                                            for c in cells) + "</tr>")
            out.append("</table>")
            html = "".join(out)
            break
    _tbl[oid] = html
    return html


def body_html(text, regid="reg01"):
    """조문 본문 — 항마다 줄을 바꾸고 표는 표로 그린다"""
    t = RE_PROV.sub("", str(text or ""))
    parts, last = [], 0
    for m in RE_IMG.finditer(t):
        parts.append(("t", t[last:m.start()]))
        parts.append(("tbl", m.group(1)))
        last = m.end()
    parts.append(("t", t[last:]))
    out = []
    for kind, v in parts:
        if kind == "tbl":
            out.append(table_html(v, regid))
            continue
        for line in str(v).split("\n"):
            line = line.strip()
            if line:
                out.append(f"<p>{esc(line)}</p>")
    return "".join(out) or "<p></p>"


# ───────────────────────── 개편안 읽기 ─────────────────────────
def load_draft():
    d = json.load(io.open(os.path.join(DATA, "draft2025.json"), encoding="utf-8"))
    return d, (d.get("tree") or d["versions"][0]["tree"])


def walk(tree):
    """[(깊이, 마디)] — 그린 차례 그대로"""
    out = []

    def rec(ns, depth):
        for x in ns:
            out.append((depth, x))
            rec(x.get("children") or [], depth + 1)
    rec(tree, 0)
    return out


def page(title, body):
    """한/글에게 넘길 HTML.

    머리말을 잘못 쓰면 한/글이 UTF-8 을 EUC-KR 로 읽어 글자가 통째로 깨진다
    (「공공측량」이 「怨듬났痢」로 나왔다). 이미 잘 도는 forms_hwp.html_of 와
    똑같이 쓴다 — <!doctype> 을 앞세우지 아니하고, 낫표는 겹따옴표로,
    옛 importer 가 알아보는 http-equiv 도 함께 적는다. 파일도 BOM 을 붙여
    (utf-8-sig) 적으므로 머리말을 못 읽어도 인코딩을 알아본다.
    """
    return ("<html><head>"
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
            '<meta charset="utf-8">'
            "<style>body{font-family:'맑은 고딕';font-size:10pt;line-height:1.6}"
            "h1{font-size:16pt;text-align:center;margin:0 0 18pt}"
            "h2{font-size:13pt;margin:16pt 0 6pt}h3{font-size:11.5pt;margin:12pt 0 4pt}"
            "h4{font-size:10.5pt;margin:10pt 0 3pt}"
            ".jo{font-weight:bold;margin:9pt 0 2pt}"
            "p{margin:0 0 3pt}table{border-collapse:collapse;width:100%;font-size:9pt}"
            "th,td{border:1px solid #7a8b95;padding:3px;"
            "vertical-align:top}.mut{color:#666}</style>"
            f"<title>{esc(title)}</title></head><body>{body}</body></html>")


# ───────────────────────── 세 가지 문서 ─────────────────────────
def html_draft(tree):
    L = ["<h1>공공측량 작업규정 개정(안)</h1>"]
    for depth, x in walk(tree):
        lv, no, ti = x.get("level"), x.get("no"), x.get("title") or ""
        if x.get("isDeleted"):
            continue
        if x.get("annexRef"):
            continue                       # 별표는 따로 묶는다
        if lv == "편":
            L.append(f"<h2>제{no}편 {esc(ti)}</h2>")
        elif lv == "장":
            L.append(f"<h3>제{no}장 {esc(ti)}</h3>")
        elif lv in ("절", "관"):
            L.append(f"<h4>제{no}{lv} {esc(ti)}</h4>")
        elif lv == "조":
            L.append(f"<div class='jo'>제{no}조({esc(ti)})</div>")
            L.append(body_html(x.get("body")))
    return page("공공측량 작업규정 개정(안)", "".join(L))


def html_reason(tree):
    L = ["<h1>공공측량 작업규정 개정사유서</h1>"]
    n = 0
    for _d, x in walk(tree):
        if x.get("level") != "조" or x.get("annexRef"):
            continue
        why = (x.get("reason") or "").strip()
        if not why:
            continue
        n += 1
        st = x.get("status") or ""
        old = x.get("legacyNo") or ""
        L.append(f"<div class='jo'>제{x.get('no')}조({esc(x.get('title'))})"
                 f" <span class='mut'>[{esc(st)}"
                 + (f" · {esc(old)}" if old else "") + "]</span></div>")
        for line in why.split("\n"):
            line = line.strip()
            L.append(f"<p>{esc(line)}</p>" if line else "<p><br></p>")
    return page("공공측량 작업규정 개정사유서", "".join(L)), n


def html_compare(tree):
    L = ["<h1>공공측량 작업규정 개정(안) 신구대조표</h1>",
         "<table><tr>"
         f"<th width='45%'{TH_STYLE}>현 행</th>"
         f"<th width='45%'{TH_STYLE}>개정(안)</th>"
         f"<th width='10%'{TH_STYLE}>비고</th></tr>"]
    n = 0
    for _d, x in walk(tree):
        if x.get("level") != "조" or x.get("annexRef"):
            continue
        st = x.get("status") or "유지"
        was = RE_PROV.sub("", x.get("wasBody") or "")
        now = RE_PROV.sub("", x.get("body") or "")
        if st == "유지" and not x.get("legacyNo"):
            continue                       # 손대지 아니한 조는 싣지 아니한다
        n += 1
        old_head = (f"{esc(x.get('legacyNo'))}" if x.get("legacyNo") else "&lt;신 설&gt;")
        new_head = f"제{x.get('no')}조({esc(x.get('title'))})"
        L.append("<tr><td>" + (f"<b>{old_head}</b>" if was or x.get("legacyNo") else old_head)
                 + (body_html(was) if was else "")
                 + f"</td><td><b>{new_head}</b>" + body_html(now)
                 + f"</td><td>{esc(st)}</td></tr>")
    L.append("</table>")
    return page("신구대조표", "".join(L)), n


# ───────────────────────── 별표·별지 모음 ─────────────────────────
RE_OLD = re.compile(r"^\[(별표|별지)\s*(\d+)\]\s*(.+)$")


def gather_annex(tree, dest):
    """별표·별지 파일을 모은다 → (담은 것, 못 담은 것)"""
    os.makedirs(dest, exist_ok=True)
    # 현행 원본: (구분, 옛번호) → 파일
    old = {}
    if os.path.isdir(FORMS_OLD):
        for f in os.listdir(FORMS_OLD):
            m = RE_OLD.match(os.path.splitext(f)[0])
            if m and f.lower().endswith((".hwp", ".hwpx")):
                old[(m.group(1), m.group(2))] = os.path.join(FORMS_OLD, f)
    # 우리가 만든 서식: 제목 → 파일
    new = {}
    if os.path.isdir(FORMS_NEW):
        for f in os.listdir(FORMS_NEW):
            if f.lower().endswith(".hwpx"):
                m = re.match(r"(별[표지])(\d+)_(.+)\.hwpx$", f)
                if m:
                    new[m.group(3).strip()] = os.path.join(FORMS_NEW, f)

    got, miss = [], []
    for _d, x in walk(tree):
        a = x.get("annexRef")
        if not a or x.get("isDeleted"):
            continue
        gu, no, ti = a.get("gubun") or "별표", str(a.get("no")), (x.get("title") or "").strip()
        stem = f"{gu} {no}_{ti}"
        src = new.get(ti)
        note = "신설·변경"
        if src is None:
            m = re.match(r"(별[표지])\s*(\d+)", x.get("legacyNo") or "")
            src = old.get((m.group(1), m.group(2))) if m else None
            note = f"현행 {m.group(1)} {m.group(2)}" if (m and src) else ""
        if src is None:
            miss.append(f"{gu} {no} {ti}")
            continue
        ext = os.path.splitext(src)[1]
        name = f"{stem}{' (' + note + ')' if note else ''}{ext}"
        shutil.copyfile(src, os.path.join(dest, re.sub(r'[\\/:*?"<>|]', "·", name)))
        got.append(name)
    return got, miss


def preview_ok(hwpx):
    """만든 HWPX 를 열어 글자가 성한지 본다 → (성한가, 미리보기 첫 줄)

    한/글이 인코딩을 잘못 잡으면 파일은 멀쩡히 열리고 검증도 통과하는데
    글자만 깨진다. 꾸러미 검사로는 잡히지 아니하므로 미리보기 글(PrvText)을
    읽어 한글이 제대로 들었는지 본다.
    """
    try:
        with zipfile.ZipFile(hwpx) as z:
            raw = next((z.read(n) for n in ("Preview/PrvText.txt", "Preview/PrvText")
                        if n in z.namelist()), None)
    except Exception:
        return None, ""
    if raw is None:
        return None, ""
    # 미리보기 글은 BOM 붙은 UTF-8 이다. 한때 UTF-16 으로 읽어, 멀쩡한 문서를
    # 깨졌다고 알렸다 — 읽는 쪽이 틀리면 성한 것을 깨진 것이라 말하게 된다.
    for enc in ("utf-8-sig", "utf-16-le", "cp949"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None, ""
    t = t.replace(chr(0), " ").strip()
    head = re.sub(r"\s+", " ", t)[:40]
    ko = len(re.findall(r"[가-힣]", t))
    # 깨지면 한글 자리에 엉뚱한 음절이 들어차므로, 뜻이 있는 낱말이 보이는지 본다
    good = any(w in t for w in ("공공측량", "작업규정", "개정"))
    return (good and ko > 20), head


# ───────────────────────── 묶기 ─────────────────────────
def main():
    argv = sys.argv[1:]
    out_dir = OUT_DIR
    if "-o" in argv:
        out_dir = argv[argv.index("-o") + 1]
    os.makedirs(out_dir, exist_ok=True)
    doc, tree = load_draft()

    tmp = tempfile.mkdtemp(prefix="report_")
    stage = os.path.join(tmp, "stage")
    os.makedirs(stage)
    made, bad = [], []
    try:
        jobs = [("개정(안)", html_draft(tree), None)]
        h, n_r = html_reason(tree)
        jobs.append(("개정사유서", h, f"사유를 담은 조 {n_r}개"))
        h, n_c = html_compare(tree)
        jobs.append(("개정(안)_신구대조표", h, f"대조한 조 {n_c}개"))

        hwp = None
        if HWP.available():
            try:
                hwp = HWP.Hwp()
            except Exception as ex:
                print(f"  [주의] 한/글을 부르지 못했습니다 ({ex}) — HTML 까지만 만듭니다")
        else:
            print("  [주의] 이 컴퓨터에서는 한/글을 부를 수 없습니다 — HTML 까지만 만듭니다")

        for name, html, note in jobs:
            hp = os.path.join(tmp, name + ".html")
            io.open(hp, "w", encoding="utf-8-sig").write(html)
            if hwp is None:
                shutil.copyfile(hp, os.path.join(stage, name + ".html"))
                made.append((name + ".html", note))
                continue
            dst = os.path.join(stage, name + ".hwpx")
            r = hwp.convert(hp, {HWP.HWPX: dst})
            if r.get(HWP.HWPX) and os.path.exists(dst):
                HWP.fit_tables(dst)
                ok, head = preview_ok(dst)
                if ok is False:
                    bad.append(f"{name}.hwpx — 미리보기 글이 깨졌습니다: {head}")
                made.append((name + ".hwpx",
                             f"{os.path.getsize(dst) // 1024}KB"
                             + (f" · {note}" if note else "")
                             + ("" if ok else " · [글자 확인 못 함]" if ok is None
                                else "")))
            else:
                shutil.copyfile(hp, os.path.join(stage, name + ".html"))
                made.append((name + ".html", "한/글 저장 실패 — HTML 로 담았습니다"))
        if hwp is not None:
            hwp.close()

        got, miss = gather_annex(tree, os.path.join(stage, "개정(안)_별표및별지모음"))

        today = _dt.date.today().strftime("%Y%m%d")
        zpath = os.path.join(out_dir, f"개정보고서_{today}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _dirs, files in os.walk(stage):
                for f in files:
                    p = os.path.join(base, f)
                    z.write(p, os.path.relpath(p, stage))
        latest = os.path.join(out_dir, "개정보고서.zip")
        shutil.copyfile(zpath, latest)
        meta = {"at": _dt.datetime.now().isoformat(timespec="seconds"),
                "file": os.path.basename(zpath),
                "items": [n for n, _ in made] + [f"개정(안)_별표및별지모음 ({len(got)}건)"],
                "bytes": os.path.getsize(zpath), "missing": miss}
        io.open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8").write(
            json.dumps(meta, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if bad:
        print("[깨짐] 다시 만들어야 합니다")
        for b in bad:
            print("   " + b)
        print()
    print("보고서 한 벌")
    for n, note in made:
        print(f"  {n:<28} {note or ''}")
    print(f"  {'개정(안)_별표및별지모음':<28} {len(got)}건")
    if miss:
        print(f"  [주의] 파일을 찾지 못한 별표·별지 {len(miss)}건: " + ", ".join(miss[:6]))
    print(f"\n  {zpath}  ({os.path.getsize(zpath) // 1024}KB)")


if __name__ == "__main__":
    main()
