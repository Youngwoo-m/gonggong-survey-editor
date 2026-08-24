# -*- coding: utf-8 -*-
r"""규정 하나의 보고서를 한/글 문서(HWPX)로 짓는다 — 별표ㆍ별지까지 함께.

genreport.py 는 작업규정에 박혀 있다(draft2025 · reg01, 별표는 폴더 이름으로
짐작해 찾는다). 이것은 어느 규정이든 받고, 별표는 개정안에 적힌 파일 길을
그대로 쓴다 — 110건이 모두 갖추어져 있으므로 짐작할 까닭이 없다.

  개정(안).hwpx                편ㆍ장ㆍ절ㆍ관 차례대로 담은 조문 전문
  개정사유서.hwpx              조문마다 [변경 사유]
  개정(안)_신구대조표.hwpx      현행 ↔ 개정안 두 칸
  별표및별지모음\              별표ㆍ별지의 한/글 파일과 PDF

■ HWPX 는 한/글에게 맡긴다

  HWPX(ZIP+XML)를 손으로 조립하면 한/글이 '손상된 파일' 로 본다. 그래서 HTML 을
  지어 한/글(HWPFrame.HwpObject)에게 넘겨 저장하게 한다. 한/글을 부를 수 없는
  컴퓨터에서는 HTML 까지만 만들고 멈춘다.

사용:
  python scripts/genreport_hwpx.py --reg uav --rev 2 --out "D:\어느\폴더"
  python scripts/genreport_hwpx.py --list
"""
import datetime as _dt
import io, json, os, re, shutil, sys, tempfile, zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

import forms_hwp as HWP                                   # noqa: E402
from genreport import esc, page, walk, body_html, preview_ok, RE_PROV, TH_STYLE  # noqa: E402


def arg(name, dflt=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and len(a) > a.index(name) + 1 else dflt


def rj(p):
    return json.load(io.open(p, encoding="utf-8"))


# ─────────────────────────────────────────────────────── 본문 짓기
def html_draft(tree, regname, regid):
    L = [f"<h1>{esc(regname)} 개정(안)</h1>"]
    for _d, x in walk(tree):
        if x.get("isDeleted") or x.get("status") == "삭제" or x.get("annexRef"):
            continue
        lv, no, ti = x.get("level"), x.get("no"), x.get("title") or ""
        if lv == "편":
            L.append(f"<h2>제{no}편 {esc(ti)}</h2>")
        elif lv == "장":
            L.append(f"<h3>제{no}장 {esc(ti)}</h3>")
        elif lv in ("절", "관"):
            L.append(f"<h4>제{no}{lv} {esc(ti)}</h4>")
        elif lv == "조":
            br = f"의{x['branch']}" if x.get("branch") else ""
            L.append(f"<div class='jo'>제{no}조{br}({esc(ti)})</div>")
            L.append(body_html(x.get("body"), regid))
    return page(f"{regname} 개정(안)", "".join(L))


def html_reason(tree, regname, regid):
    L = [f"<h1>{esc(regname)} 개정사유서</h1>"]
    n = 0
    for _d, x in walk(tree):
        r = (x.get("reason") or "").strip()
        if not r:
            continue
        n += 1
        if x.get("annexRef"):
            a = x["annexRef"]
            head = f"[{a.get('gubun') or '별표'} {a.get('no')}] {esc(x.get('title') or '')}"
        else:
            br = f"의{x['branch']}" if x.get("branch") else ""
            head = f"제{x.get('no')}조{br}({esc(x.get('title') or '')})"
        L.append(f"<div class='jo'>{head}"
                 f"{' · ' + esc(x.get('status')) if x.get('status') else ''}</div>")
        L.append(body_html(r, regid))
    return page(f"{regname} 개정사유서", "".join(L)), n


def html_compare(tree, regname, regid):
    L = [f"<h1>{esc(regname)} 개정(안) 신구대조표</h1>",
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
            continue
        n += 1
        old_head = esc(x.get("legacyNo")) if x.get("legacyNo") else "&lt;신 설&gt;"
        br = f"의{x['branch']}" if x.get("branch") else ""
        new_head = f"제{x.get('no')}조{br}({esc(x.get('title') or '')})"
        L.append("<tr><td>" + (f"<b>{old_head}</b>" if was or x.get("legacyNo") else old_head)
                 + (body_html(was, regid) if was else "")
                 + f"</td><td><b>{new_head}</b>" + body_html(now, regid)
                 + f"</td><td>{esc(st)}</td></tr>")
    L.append("</table>")
    return page(f"{regname} 신구대조표", "".join(L)), n


# ─────────────────────────────────────────── 별표ㆍ별지 모으기
BAD = re.compile(r'[\\/:*?"<>|]')


def gather_annex(tree, dest):
    """개정안에 적힌 파일 길 그대로 모은다 → (담은 것, 못 담은 것)"""
    os.makedirs(dest, exist_ok=True)
    got, miss = [], []
    for _d, x in walk(tree):
        a = x.get("annexRef")
        if not a or x.get("isDeleted"):
            continue
        gu, no = a.get("gubun") or "별표", str(a.get("no"))
        ti = (x.get("title") or "").strip()
        stem = BAD.sub("·", f"{gu} {no}_{ti}")[:110]
        one = False
        for key in ("hwp", "pdf"):
            src = a.get(key) or ""
            if not src or src.startswith("http"):
                continue
            p = os.path.join(ROOT, src)
            if not os.path.exists(p):
                continue
            shutil.copyfile(p, os.path.join(dest, stem + os.path.splitext(p)[1]))
            one = True
        if one:
            got.append(f"{gu} {no} {ti}")
        else:
            miss.append(f"{gu} {no} {ti}")
    return got, miss


# ──────────────────────────────────────────────────────── 짓기
def main():
    lib = rj(os.path.join(DATA, "library.json"))
    tj = rj(os.path.join(DATA, "targets.json"))
    targets = tj.get("targets") or tj

    if "--list" in sys.argv:
        for t in targets:
            print(f"  {t['id']:<8} {t.get('short') or t['base']}")
        return

    want = arg("--reg", "work")
    t = next((x for x in targets if x["id"] == want), None)
    if not t:
        sys.exit(f"등록부에 없는 규정입니다 — {want}")
    meta = next((r for r in lib.get("regulations", []) if r["name"] == t["base"]), None)
    if not meta:
        sys.exit(f"라이브러리에서 못 찾음 — {t['base']}")

    draft = rj(os.path.join(ROOT, t["draft"]))
    revs = [(draft.get("title") or "개정안", draft["tree"])] + [
        (r.get("title") or f"개정안 {i + 2}판", r["tree"])
        for i, r in enumerate(draft.get("next") or [])]
    ri = int(arg("--rev", "0") or 0)
    if ri:
        if not 1 <= ri <= len(revs):
            sys.exit(f"--rev 는 1..{len(revs)} 입니다")
        ri -= 1
    else:
        ri = len(revs) - 1                      # 안 주면 마지막 판
    revname, tree = revs[ri]
    regname = t.get("base") or t.get("short")
    regid = meta["id"]                          # 본문 속 표·수식을 찾을 자리

    print(f"규정 : {regname}")
    print(f"판   : {revname}  ({ri + 1}/{len(revs)})")

    out_dir = arg("--out", os.path.join(DATA, "report"))
    os.makedirs(out_dir, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="hwpxreport_")
    stage = os.path.join(tmp, "stage")
    os.makedirs(stage)
    made, bad = [], []
    try:
        jobs = [("개정(안)", html_draft(tree, regname, regid), None)]
        h, nr = html_reason(tree, regname, regid)
        jobs.append(("개정사유서", h, f"사유를 담은 항목 {nr}개"))
        h, nc = html_compare(tree, regname, regid)
        jobs.append(("개정(안)_신구대조표", h, f"대조한 조 {nc}개"))

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
                made.append((name + ".hwpx", f"{os.path.getsize(dst) // 1024}KB"
                             + (f" · {note}" if note else "")))
            else:
                shutil.copyfile(hp, os.path.join(stage, name + ".html"))
                made.append((name + ".html", "한/글 저장 실패 — HTML 로 담았습니다"))
        if hwp is not None:
            hwp.close()

        got, miss = gather_annex(tree, os.path.join(stage, "별표및별지모음"))

        today = _dt.datetime.now().strftime("%Y%m%d_%H%M")
        short = BAD.sub("_", t.get("short") or want)
        # 판 이름은 화면과 같은 규칙으로 짓는다 — 등록부의 ver 를 머리글자로
        # 삼아 1.00 에서 0.01 씩 올린다 (vC-1.00 · vC-1.01).
        # 초안 파일의 제목은 두 판이 모두 '개정안 초안…' 으로 시작하여
        # 그대로 쓰면 판이 갈리지 아니한다.
        tag = f"v{t.get('ver') or 'X'}-1.{ri:02d}" if len(revs) > 1 else ""
        zname = f"개정보고서(한글)_{short}{'_' + tag if tag else ''}_{today}.zip"
        zpath = os.path.join(out_dir, zname)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _dirs, files in os.walk(stage):
                for f in files:
                    p = os.path.join(base, f)
                    z.write(p, os.path.relpath(p, stage))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if bad:
        print("\n[깨짐] 다시 만들어야 합니다")
        for b in bad:
            print("   " + b)
    print("\n보고서 한 벌")
    for n, note in made:
        print(f"  {n:<28} {note or ''}")
    print(f"  {'별표및별지모음':<28} {len(got)}건")
    if miss:
        print(f"  [주의] 파일이 없는 별표ㆍ별지 {len(miss)}건: " + ", ".join(miss[:6]))
    print(f"\n  {zpath}  ({os.path.getsize(zpath) // 1024}KB)")


if __name__ == "__main__":
    main()
