# -*- coding: utf-8 -*-
r"""별표ㆍ별지의 미리보기와 쪽수를 자료와 맞춘다.

■ 무엇이 어긋나 있었나

  ① 미리보기 색인(data/annex/index.json)이 **다른 별표의 그림**을 가리켰다.

        무인비행장치 별표 8 → 별표5_1.webp
        무인비행장치 별표 9 → 별표6_1.webp
        무인비행장치 별표 10 → 별표7_1.webp

     그림 파일은 멀쩡하다. 「별표8_1.webp」 는 정말로 별표 8이다. 색인만
     어긋났다. 그림을 만들 때 트리 차례와 파일 차례를 짝지었는데, 그 둘이
     같지 아니하였던 것이다.

  ② 색인에 없는 자리가 있었다. data/annex/formwork 에 그림 17장이 있는데
     색인에 등록되지 아니하여, 작업규정 신설 별표 17개가 옛 draft2025
     자리로 떨어져 **번호가 다른 별표**를 보여 주었다 (별표 15 → 별표46).

  ③ 성과심사 신설 11개는 그림이 아예 없어 **현행 규정의 별표**를 보여 주거나
     미리보기가 비어 있었다.

  ④ annexRef.pages 가 실제 PDF 쪽수와 달랐다 (34개). 지난번 갈이 때 파일만
     바꾸고 쪽수를 그대로 두었다.

■ 어떻게 고치는가

  ㆍ 색인은 **파일 이름대로** 다시 짓는다. 「별표8_1.webp」 는 「별표8」 의
    첫 쪽이다. 이름이 곧 열쇠이므로 어긋날 자리가 없다.
  ㆍ 없는 그림은 곁에 있는 PDF 에서 만든다.
  ㆍ 쪽수는 PDF 를 세어 적는다.

  python scripts\annexfix.py            바꿔 볼 것을 보여만 준다
  python scripts\annexfix.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ANNEX = os.path.join(ROOT, "data", "annex")
INDEX = os.path.join(ANNEX, "index.json")

# 본문 글로 지은 별표는 data/annex/gen/<자리>/ 에 있다. 그 곁의 PDF 에서
# 미리보기를 만들고, 색인에는 gen<자리> 라는 이름으로 올린다.
GEN = os.path.join(ANNEX, "gen")


def make_list():
    """[(색인 이름, PDF 폴더)] — gen 아래를 훑는다"""
    if not os.path.isdir(GEN):
        return []
    return [("gen" + d, os.path.join(GEN, d))
            for d in sorted(os.listdir(GEN))
            if os.path.isdir(os.path.join(GEN, d))]


def dir_of(pdf):
    """annexRef.pdf 가 gen 아래면 그 마디가 쓸 미리보기 자리를 돌려준다"""
    m = re.match(r"data/annex/gen/([^/]+)/", str(pdf or "").replace("\\", "/"))
    return ("gen" + m.group(1)) if m else None

RE_FILE = re.compile(r"^(.+?)_(\d+)\.webp$")


def bins_from_disk():
    """폴더마다 그림 파일 이름을 읽어 색인을 짓는다 — 이름이 곧 열쇠다"""
    out = {}
    for d in sorted(os.listdir(ANNEX)):
        p = os.path.join(ANNEX, d)
        if not os.path.isdir(p):
            continue
        got = {}
        for fn in os.listdir(p):
            m = RE_FILE.match(fn)
            if not m:
                continue
            got.setdefault(m.group(1), []).append((int(m.group(2)), fn))
        if got:
            out[d] = {k: [fn for _n, fn in sorted(v)] for k, v in got.items()}
    return out


def render_missing(write):
    """PDF 만 있고 그림이 없는 자리에 그림을 만든다 → 만든 자리 이름들"""
    made = []
    for name, src in make_list():
        if not os.path.isdir(src):
            continue
        dst = os.path.join(ANNEX, name)
        pdfs = sorted(f for f in os.listdir(src) if f.lower().endswith(".pdf"))
        if not pdfs:
            continue
        n = 0
        if write:
            os.makedirs(dst, exist_ok=True)
        import fitz                                    # noqa: E402
        for f in pdfs:
            key = os.path.splitext(f)[0].replace(" ", "")
            with fitz.open(os.path.join(src, f)) as doc:
                for i, page in enumerate(doc, 1):
                    # genannex.py 와 같은 크기ㆍ품질로 (PyMuPDF 는 webp 를
                    # 바로 못 쓰므로 PIL 을 거친다)
                    zoom = 1400 / max(page.rect.width, 1)
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    if write:
                        io.open(os.path.join(dst, "%s_%d.webp" % (key, i)),
                                "wb").write(pix.pil_tobytes(format="WEBP",
                                                            quality=82, method=4))
                    n += 1
        made.append((name, len(pdfs), n))
    return made


# 미리보기로 그릴 최대 쪽수. genannex.py 는 4쪽에서 끊었는데, 그러면 51쪽짜리
# 별표 1 은 앞 네 쪽만 보인다. 여기서는 넉넉히 두되 끝은 있어야 한다.
MAX_PAGE = 12


def fill_pages(bins, write):
    """미리보기 장수가 PDF 쪽수보다 적으면 모자란 쪽을 그린다"""
    import fitz
    made = []
    for f in ("draft2025.json", "draft_simsa.json", "draft_uav.json"):
        d = json.load(io.open(os.path.join(ROOT, "data", f), encoding="utf-8"))
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a or not a.get("previewDir") or not a.get("pdf"):
                    continue
                # 제 미리보기 자리를 가진 마디는 **제 번호**로 담겨 있다.
                # 신설 별표의 legacyNo 는 앞선 초안의 번호라 열쇠가 못 된다.
                key = re.sub(r"[ ]+", "",
                             "%s%s" % (a.get("gubun"), a.get("no")))
                got = len((bins.get(a["previewDir"]) or {}).get(key) or [])
                pdf = os.path.join(ROOT, a["pdf"])
                if not os.path.exists(pdf):
                    continue
                with fitz.open(pdf) as doc:
                    want = min(len(doc), MAX_PAGE)
                    if got >= want:
                        continue
                    for i in range(got, want):
                        page = doc[i]
                        zoom = 1400 / max(page.rect.width, 1)
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                                              alpha=False)
                        if write:
                            io.open(os.path.join(ANNEX, a["previewDir"],
                                                 "%s_%d.webp" % (key, i + 1)),
                                    "wb").write(pix.pil_tobytes(
                                        format="WEBP", quality=82, method=4))
                    made.append((f[:12], key, got, want))
    return made


def set_dirs(write):
    """본문 글로 지은 별표는 제 gen 자리를 미리보기 자리로 삼는다.

    이것을 fill_pages 보다 **먼저** 해야 한다. 나중에 하면 모자란 쪽이 옛
    자리에 그려져, 첫 쪽은 옛 문서이고 뒷쪽은 새 문서인 자리가 생긴다."""
    n = 0
    for f in ("draft2025.json", "draft_simsa.json", "draft_uav.json"):
        p = os.path.join(ROOT, "data", f)
        d = json.load(io.open(p, encoding="utf-8"))
        touched = False
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a:
                    continue
                want = dir_of(a.get("pdf"))
                if want and a.get("previewDir") != want:
                    a["previewDir"] = want
                    touched = True
                    n += 1
        if write and touched:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False))
    return n


def walk(ns):
    for x in ns:
        yield x
        yield from walk(x.get("children") or [])


def main():
    write = "--write" in sys.argv
    print("■ 없는 미리보기 만들기")
    for name, k, n in render_missing(write) or [("(없음)", 0, 0)]:
        print("   %-12s 별표ㆍ별지 %d개 · 그림 %d장" % (name, k, n))

    print()
    print("■ 색인 다시 짓기 — 파일 이름대로")
    old = json.load(io.open(INDEX, encoding="utf-8"))
    new = bins_from_disk()
    add = sorted(set(new) - set(old))
    gone = sorted(set(old) - set(new))
    moved = []
    for b in sorted(set(old) & set(new)):
        for k, v in old[b].items():
            if new[b].get(k) != v:
                moved.append((b, k, ", ".join(v), ", ".join(new[b].get(k) or ["없음"])))
    print("   새로 든 자리 %d개 : %s" % (len(add), ", ".join(add) or "-"))
    print("   빠지는 자리 %d개 : %s" % (len(gone), ", ".join(gone) or "-"))
    print("   가리키는 그림이 바뀌는 것 %d개" % len(moved))
    for b, k, a, c in moved[:40]:
        print("      %-11s %-9s %-22s → %s" % (b, k, a, c))

    print()
    print("■ 미리보기 자리 정하기 — 본문 글로 지은 것은 gen 자리를 쓴다")
    n_dir = set_dirs(write)
    print("   자리를 새로 적은 마디 %d개" % n_dir)

    print()
    print("■ 모자란 미리보기 쪽 채우기")
    for r in fill_pages(new, write) or [("(없음)", "-", 0, 0)]:
        print("   %-13s %-9s %d장 → %d장" % r)
    if write:
        new = bins_from_disk()

    print()
    print("■ 쪽수 맞추기")
    try:
        import pypdf
    except ImportError:
        import PyPDF2 as pypdf
    fixed = 0
    for f in ("draft2025.json", "draft_simsa.json", "draft_uav.json"):
        p = os.path.join(ROOT, "data", f)
        d = json.load(io.open(p, encoding="utf-8"))
        touched = False
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a:
                    continue
                # 본문 글로 지은 것이면 그 자리를 미리보기 자리로 삼는다
                want = dir_of(a.get("pdf"))
                if want and a.get("previewDir") != want:
                    a["previewDir"] = want
                    touched = True
                pdf = a.get("pdf")
                if not pdf:
                    continue
                full = os.path.join(ROOT, pdf) if not os.path.isabs(pdf) else pdf
                if not os.path.exists(full):
                    continue
                try:
                    real = len(pypdf.PdfReader(full).pages)
                except Exception:
                    continue
                if a.get("pages") != real:
                    print("   %-16s %s %-4s  %s → %s"
                          % (f[:15], a.get("gubun"), a.get("no"), a.get("pages"), real))
                    a["pages"] = real
                    fixed += 1
                    touched = True
        if write and touched:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False))
    print("   쪽수를 고친 것 %d개" % fixed)

    if write:
        io.open(INDEX, "w", encoding="utf-8", newline="\n").write(
            json.dumps(new, ensure_ascii=False, indent=1))
        print()
        print("자료에 적었습니다.")
    else:
        print()
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
