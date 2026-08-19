# -*- coding: utf-8 -*-
"""
별표·별지 원본(HWP)에서 표를 읽어 XML 로 바꾼다.

국가법령정보센터의 별표는 옛 HWP 이진 파일이라 그림으로만 볼 수 있었다.
hwp5.py 로 표 구조를 그대로 뽑아 본문 표와 같은 XML 형식으로 만든다.

사용:  python scripts/genannexxml.py [규정id …]      (기본: reg01)
       python scripts/genannexxml.py all
출력:  data/objects/<규정id>/annex/<별표1>.xml
       data/objects/<규정id>/annex-index.json
"""
import io, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hwp5

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}
CACHE = os.path.join(ROOT, ".cache", "annexhwp")


def fetch(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2)


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def slug(s):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(s))


def to_xml(key, a, items, src):
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<annex id="{esc(key)}" gubun="{esc(a["gubun"])}" no="{esc(a["no"])}" '
         f'title="{esc(a["title"])}" source="{esc(src)}">']
    for it in items:
        if it["kind"] == "text":
            t = it["text"].strip()
            # 「[ 별표 1 ]」 같은 머리글은 화면에서 다시 보여 줄 필요가 없다
            if re.fullmatch(r"\[?\s*(별표|별지|서식)\s*[0-9의\-]*\s*\]?", t):
                continue
            L.append(f"  <text>{esc(t)}</text>")
            continue
        L.append(f'  <table rows="{it["rowCnt"]}" cols="{it["colCnt"]}">')
        for cells in it["rows"]:
            L.append("    <row>")
            for c in cells:
                at = f' col="{c["col"]}" row="{c["row"]}"'
                if c["colspan"] != 1:
                    at += f' colspan="{c["colspan"]}"'
                if c["rowspan"] != 1:
                    at += f' rowspan="{c["rowspan"]}"'
                L.append(f'      <cell{at}>{esc(c["text"])}</cell>')
            L.append("    </row>")
        L.append("  </table>")
    L.append("</annex>")
    return "\n".join(L)


def run(rid, lib):
    meta = next((r for r in lib["regulations"] if r["id"] == rid), None)
    if not meta or not meta.get("file"):
        print(f"[{rid}] 색인된 규정이 아닙니다")
        return None
    doc = json.load(io.open(os.path.join(DATA, meta["file"]), encoding="utf-8"))
    annex = doc.get("annex") or []
    if not annex:
        return None

    outdir = os.path.join(DATA, "objects", rid, "annex")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)

    index, ok, skip = {}, 0, []
    print(f"\n[{meta['name']}] 별표·별지 {len(annex)}건")
    for a in annex:
        key = f"{a['gubun']}{a['no']}"
        url = a.get("hwp")
        if not url:
            skip.append((key, "원본 파일 없음"))
            continue
        cache = os.path.join(CACHE, f"{rid}_{slug(key)}.hwp")
        try:
            if os.path.exists(cache) and os.path.getsize(cache) > 0:
                blob = io.open(cache, "rb").read()
            else:
                blob = fetch(url)
                io.open(cache, "wb").write(blob)
            if blob[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                skip.append((key, "HWP 5.0 이진 파일이 아님"))
                continue
            items = hwp5.extract(cache)
            tables = [x for x in items if x["kind"] == "table" and x["rows"]]
            if not tables:
                skip.append((key, "표를 찾지 못함"))
                continue
            io.open(os.path.join(outdir, f"{slug(key)}.xml"), "w", encoding="utf-8").write(
                to_xml(key, a, items, url))
            index[key] = {
                "file": f"{slug(key)}.xml",
                "title": a["title"],
                "tables": len(tables),
                "rows": sum(t["rowCnt"] for t in tables),
                "cols": max(t["colCnt"] for t in tables),
            }
            ok += 1
            print(f"   OK  {key:<9} 표 {len(tables)}개 "
                  f"({' + '.join(f'{t['rowCnt']}×{t['colCnt']}' for t in tables[:4])})  {a['title'][:26]}")
        except Exception as e:
            skip.append((key, f"{type(e).__name__}: {e}"))

    with io.open(os.path.join(DATA, "objects", rid, "annex-index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    print(f"   → 변환 {ok}건 / 건너뜀 {len(skip)}건")
    for k, why in skip[:12]:
        print(f"      - {k}: {why}")
    return ok


if __name__ == "__main__":
    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    args = [a for a in sys.argv[1:] if a]
    if args and args[0] == "all":
        ids = [r["id"] for r in lib["regulations"] if r.get("file") and r.get("annexCount")]
    else:
        ids = args or ["reg01"]

    total = 0
    for rid in ids:
        total += run(rid, lib) or 0
    print(f"\n모두 {total}건을 XML 로 바꿨습니다.")
