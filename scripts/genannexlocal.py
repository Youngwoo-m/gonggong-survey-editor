# -*- coding: utf-8 -*-
"""
손에 있는 별표·서식 원본 폴더 하나로 별표를 다 갖춘다

genannex.py·genannexxml.py 는 국가법령정보센터에서 파일을 받아 온다. 이 스크립트는
이미 내려받아 폴더에 둔 원본을 쓴다 — 인터넷이 없어도 되고, 연구 자료로 받아 둔
원본과 화면에 보이는 것이 어긋나지 않는다.

세 가지를 한꺼번에 한다.
  1. 미리보기   PDF → data/annex/<규정id>/<별표N>_<쪽>.webp
  2. 원본 갈무리 HWP·PDF → data/annex/<규정id>/원본/<별표N>.hwp|.pdf
                 규정 자료(regNN.json)의 내려받기 주소를 이 파일로 바꾼다
                 (법제처 주소는 annexRef.source 에 남긴다)
  3. 서식 표     HWP → data/objects/<규정id>/annex/<별표N>.xml
                 표 안에 그림만 있는 별표는 그림을 꺼내 <image> 로 싣는다

파일 이름에서 '[별표 3]' 꼴을 읽어 규정의 별표 목록과 짝지운다.

사용:
    python scripts/genannexlocal.py reg12 "..\\관련규정\\...\\2020.무인비행장치 측량 작업규정"
    python scripts/genannexlocal.py reg12 <폴더> --dry     (만들지 않고 짝만 맞춰 보기)
"""
import io, json, os, re, sys, shutil, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "annex")
sys.path.insert(0, HERE)
import genannex as A            # render() · slug() · WIDTH · QUALITY · MAX_PAGES
import genannexxml as X         # to_xml()
import hwp5

RE_NAME = re.compile(r"\[?\s*(별표|별지|서식)\s*(\d+(?:\s*의\s*\d+)?)\s*\]?")

# 한 줄에 나란히 둘 그림 — {규정id: {별표: [[그림 번호…], …]}}
# 별표 1(지상기준점의 배치)은 배치도 두 장이 짝을 이루므로 한 줄에 둔다.
ROWS = {"reg12": {"별표1": [[1, 2], [3]]}}
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def key_of(fname):
    """'[별표 5] 검사표(…).pdf' → '별표5'"""
    m = RE_NAME.search(os.path.basename(fname))
    return m.group(1) + re.sub(r"\s+", "", m.group(2)) if m else None


def find_files(folder):
    """{'별표1': {'hwp': 경로, 'pdf': 경로}}"""
    out = {}
    for fn in sorted(os.listdir(folder)):
        ext = fn.rsplit(".", 1)[-1].lower()
        if ext not in ("hwp", "pdf"):
            continue
        k = key_of(fn)
        if k:
            out.setdefault(k, {}).setdefault(ext, os.path.join(folder, fn))
    return out


# ───────────── HWP 안의 그림 ─────────────
def pictures(path):
    """옛 HWP(OLE2) 의 BinData 그림 → [(바이트, 폭, 높이), …]

    한글은 BinData 스트림을 raw deflate 로 눌러 둔다 (FileHeader 37번째 바이트의
    첫 비트가 눌림 표시). 표 대신 그림만 든 별표는 이것을 꺼내야 볼 수 있다.
    """
    import olefile
    from PIL import Image
    ole = olefile.OleFileIO(path)
    comp = ole.openstream("FileHeader").read()[36] & 1
    out = []
    for s in sorted(ole.listdir()):
        if s[0] != "BinData":
            continue
        raw = ole.openstream("/".join(s)).read()
        if comp:
            try:
                raw = zlib.decompress(raw, -15)
            except Exception:
                continue
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            continue
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=A.QUALITY, method=4)
        out.append((buf.getvalue(), im.width, im.height))
    return out


def blank(table):
    return not any((c["text"] or "").strip() for row in table["rows"] for c in row)


def main(sid, folder, dry=False):
    jf = os.path.join(DATA, sid + ".json")
    doc = json.load(io.open(jf, encoding="utf-8"))
    annex = doc.get("annex") or []
    want = {f"{a['gubun']}{a['no']}": a for a in annex}
    have = find_files(folder)

    print(f"\n  {doc['name']} — {os.path.basename(os.path.abspath(folder))}")
    print(f"  규정의 별표 {len(want)}건 · 폴더에서 찾은 원본 {len(have)}건")
    for k, a in want.items():
        f = have.get(k, {})
        print(f"    {'○' if f else '×'} {k:<8} {' · '.join(sorted(f)) or '폴더에 없음':<12} {a['title'][:30]}")
    if dry:
        print("\n  --dry — 만들지 않았습니다.")
        return

    prev_dir = os.path.join(OUT, sid)
    src_dir = os.path.join(prev_dir, "원본")
    xml_dir = os.path.join(DATA, "objects", sid, "annex")
    for d in (prev_dir, src_dir, xml_dir):
        os.makedirs(d, exist_ok=True)

    preview, xindex = {}, {}
    imgs = pages = tables = kept_src = 0

    for k, a in want.items():
        f = have.get(k)
        if not f:
            continue
        stem = A.slug(k)

        # 1. 미리보기 — PDF 를 쪽마다 그림으로
        if f.get("pdf"):
            blob = io.open(f["pdf"], "rb").read()
            if blob[:4] == b"%PDF":
                names = []
                for pi, img in enumerate(A.render(blob), start=1):
                    fn = f"{stem}_{pi}.webp"
                    io.open(os.path.join(prev_dir, fn), "wb").write(img)
                    names.append(fn)
                preview[k] = names
                pages += len(names)

        # 2. 원본 갈무리 — 앱에서 그대로 내려받게
        for ext in ("hwp", "pdf"):
            if f.get(ext):
                shutil.copyfile(f[ext], os.path.join(src_dir, f"{stem}.{ext}"))
                kept_src += 1
        rel = f"data/annex/{sid}/원본/{stem}"
        if not a.get("source"):
            a["source"] = a.get("hwp") or a.get("pdf") or ""     # 법제처 주소를 남긴다
        a["hwp"] = f"{rel}.hwp" if f.get("hwp") else ""
        a["pdf"] = f"{rel}.pdf" if f.get("pdf") else ""

        # 3. 서식 표 — HWP 의 표를 XML 로, 그림만 든 별표는 그림을 꺼내
        if not f.get("hwp"):
            continue
        if io.open(f["hwp"], "rb").read(8) != OLE_MAGIC:
            print(f"    [건너뜀] {k} — HWP 5.0 이진 파일이 아닙니다")
            continue
        items = hwp5.extract(f["hwp"])
        tbl = [x for x in items if x["kind"] == "table" and x["rows"]]
        pics = pictures(f["hwp"])
        if pics:
            # 그림이 든 별표는 빈 표(그림을 담고 있던 칸)를 빼고 그림을 싣는다
            items = [x for x in items if not (x["kind"] == "table" and blank(x))]
            rows = ROWS.get(sid, {}).get(k)
            for i, (blob, w, h) in enumerate(pics, start=1):
                fn = f"{stem}_img{i}.webp"
                io.open(os.path.join(xml_dir, fn), "wb").write(blob)
                # 한 줄에 나란히 둘 그림은 같은 row 를 준다 (화면에서 가로로 붙는다)
                row = next((ri for ri, g in enumerate(rows or [], start=1) if i in g), i)
                items.append({"kind": "image", "src": f"data/objects/{sid}/annex/{fn}",
                              "w": w, "h": h, "row": row,
                              "alt": f"{k} {a['title']} 그림 {i}"})
                imgs += 1
        io.open(os.path.join(xml_dir, f"{stem}.xml"), "w", encoding="utf-8").write(
            to_xml(k, a, items, os.path.basename(f["hwp"])))
        real = [x for x in items if x["kind"] == "table"]
        tables += len(real)
        xindex[k] = {"file": f"{stem}.xml", "title": a["title"], "tables": len(real),
                     "rows": sum(t["rowCnt"] for t in real) if real else 0,
                     "cols": max([t["colCnt"] for t in real], default=0),
                     "images": len(pics)}
        print(f"    OK  {k:<8} 표 {len(real)}개 · 그림 {len(pics)}개"
              + (f" · 미리보기 {len(preview.get(k, []))}쪽" if preview.get(k) else ""))

    # ── 색인 세 벌을 고친다 ────────────────────────────────
    ip = os.path.join(OUT, "index.json")
    index = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    if preview:
        index[sid] = preview                    # 이 규정 것만 갈아 끼운다
        with io.open(ip, "w", encoding="utf-8") as fp:
            json.dump(index, fp, ensure_ascii=False, separators=(",", ":"))
    with io.open(os.path.join(DATA, "objects", sid, "annex-index.json"), "w", encoding="utf-8") as fp:
        json.dump(xindex, fp, ensure_ascii=False, separators=(",", ":"))

    # 조문 트리의 별표 가지에도 같은 주소를 넣는다
    fixed = 0
    for g in doc.get("annexTree") or []:
        for n in g.get("children") or []:
            ref = n.get("annexRef") or {}
            a = want.get(f"{ref.get('gubun')}{ref.get('no')}")
            if not a:
                continue
            ref["source"] = a.get("source", "")
            ref["hwp"], ref["pdf"] = a.get("hwp", ""), a.get("pdf", "")
            n["annexRef"] = ref
            fixed += 1
    with io.open(jf, "w", encoding="utf-8") as fp:
        json.dump(doc, fp, ensure_ascii=False, separators=(",", ":"))

    print(f"\n  미리보기 {pages}쪽 · 원본 {kept_src}개 · 서식 표 {tables}개 · 표 속 그림 {imgs}개")
    print(f"  {sid}.json 의 별표 {fixed}건이 앱 안의 원본 파일을 가리킵니다"
          f" (법제처 주소는 source 에 남겼습니다).")
    print("  초안을 쓰는 편집기라면 초안도 다시 만드십시오 — python scripts/gendraft_uav.py")


def to_xml(key, a, items, src):
    """genannexxml.to_xml 에 <image> 를 더한 것"""
    body = X.to_xml(key, a, [x for x in items if x["kind"] != "image"], src)
    pics = [x for x in items if x["kind"] == "image"]
    if not pics:
        return body
    add = "\n".join(
        f'  <image src="{X.esc(p["src"])}" w="{p["w"]}" h="{p["h"]}"'
        f' row="{p.get("row", 0)}" alt="{X.esc(p["alt"])}"/>'
        for p in pics)
    return body.replace("</annex>", add + "\n</annex>")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2:
        print(__doc__)
        raise SystemExit(1)
    main(a[0], a[1], dry="--dry" in sys.argv)
