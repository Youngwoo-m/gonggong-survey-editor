# -*- coding: utf-8 -*-
"""
본문에 그림으로 들어 있으나 표·수식이 아니어서 XML 로 바꿀 수 없는 것
(도해·개념도)을 원본 HWPX 에서 그림 파일로 꺼내 색인한다.

genobjects.py 가 표와 수식만 다루므로, 그 나머지를 이 스크립트가 맡는다.
조문 안에서 나온 순서대로 본문의 <img id> 와 하나씩 맞춘다.

사용:  python scripts/genpics.py <원본.hwpx> [규정id]
출력:  data/objects/<규정id>/<imgId>.<확장자>
       index.json 에 {"kind":"image", …} 로 항목을 더한다
"""
import io, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
HC = "{http://www.hancom.co.kr/hwpml/2011/core}"
JO = re.compile(r"^제\s*(\d+)\s*조")
RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"')


def para_text(p):
    return "".join(t.text or "" for t in p.iter(HP + "t"))


def scan(root):
    """[(조번호, 종류, 그림 참조 id 또는 None), …] — 문서 순서 그대로"""
    out, cur = [], None

    def walk(el, depth):
        nonlocal cur
        for child in el:
            tag = child.tag
            if tag == HP + "p" and depth == 0:
                m = JO.match(para_text(child).strip())
                if m:
                    cur = int(m.group(1))
            if tag == HP + "tbl":
                out.append((cur, "table", None))
                continue
            if tag == HP + "equation":
                out.append((cur, "equation", None))
                continue
            if tag == HP + "pic":
                ref = None
                for img in child.iter(HC + "img"):
                    ref = img.get("binaryItemIDRef") or img.get("src")
                    break
                out.append((cur, "image", ref))
                continue
            walk(child, depth)

    walk(root, 0)
    return out


def bindata(z):
    """binaryItemIDRef → zip 안의 파일 이름"""
    out = {}
    for n in z.namelist():
        m = re.match(r"BinData/(.+)\.(\w+)$", n)
        if m:
            out[m.group(1)] = n
    return out


def main(path, reg_id="reg01"):
    reg = json.load(io.open(os.path.join(DATA, f"{reg_id}.json"), encoding="utf-8"))
    out_dir = os.path.join(DATA, "objects", reg_id)
    os.makedirs(out_dir, exist_ok=True)
    idx_path = os.path.join(out_dir, "index.json")
    index = json.load(io.open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}

    # 조문 → 본문에 적힌 <img id> 순서
    order = {}
    def walk(ns):
        for n in ns:
            if n.get("level") == "조" and not n.get("annexRef"):
                ids = RE_IMG.findall(n.get("body") or "")
                if ids:
                    k = "".join(c for c in str(n.get("legacyNo") or "") if c.isdigit())
                    if k:
                        order[int(k)] = ids
            walk(n.get("children") or [])
    walk(reg["tree"])

    with zipfile.ZipFile(path) as z:
        bins = bindata(z)
        seen, made, miss = {}, 0, 0
        for name in sorted(n for n in z.namelist()
                           if re.match(r"Contents/section\d+\.xml$", n)):
            for jo, kind, ref in scan(ET.fromstring(z.read(name))):
                if jo is None or jo not in order:
                    continue
                k = seen.get(jo, 0)
                seen[jo] = k + 1
                if kind != "image" or k >= len(order[jo]):
                    continue
                img_id = order[jo][k]
                if img_id in index:                 # 이미 표·수식으로 바꾼 것
                    continue
                src = bins.get(ref or "")
                if not src:
                    miss += 1
                    continue
                raw = z.read(src)
                ext = src.rsplit(".", 1)[-1].lower()
                if ext == "tmp":            # 한글이 확장자를 감춘 것 — 실제 형식을 본다
                    head = raw[:8]
                    ext = ("gif" if head[:4] == b"GIF8" else
                           "png" if head[1:4] == b"PNG" else
                           "jpg" if head[:3] == bytes([0xFF, 0xD8, 0xFF]) else
                           "bmp" if head[:2] == b"BM" else "bin")
                io.open(os.path.join(out_dir, f"{img_id}.{ext}"), "wb").write(raw)
                index[img_id] = {"kind": "image", "article": f"제{jo}조",
                                 "file": f"{img_id}.{ext}",
                                 "preview": f"원문 그림 (제{jo}조)"}
                made += 1

    with io.open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"그림 {made}개를 꺼냈습니다. 원본을 찾지 못한 것 {miss}개.")
    print(f"  색인 전체 {len(index)}개 → {idx_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "reg01")
