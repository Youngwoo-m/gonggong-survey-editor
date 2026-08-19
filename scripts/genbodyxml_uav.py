# -*- coding: utf-8 -*-
"""
본문에 그림으로 들어간 표를 XML 로 바꾼다 — 무인비행장치 측량 작업규정

고시 원문은 표를 그림 한 장으로 넣어 두었다. 그림은 글자를 고를 수도, 견줄 수도,
비교표에 실을 수도 없다. 그림에 담긴 표를 그대로 옮겨 XML 로 두고, 본문의
자리표시를 그 표로 바꾼다. 원본 그림은 지우지 않고 objects 폴더에 남겨 둔다.

지금 다루는 것
  · reg12 제13조제2항 중복도 표 (pic1.gif → t13ovl.xml)

사용:  python scripts/genbodyxml_uav.py [--dry]
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
BASE = "reg12"

# 제13조제2항 중복도 — 원문 그림(pic1.gif)에 담긴 표를 글자로 옮긴 것
T13OVL = {
    "id": "t13ovl",
    "article": "제13조제2항 촬영 중복도",
    "source": "무인비행장치 측량 작업규정 원문 그림 (pic1.gif)",
    "rows": [
        ["구 분", "평탄한 저지대 지역", "매칭점이 부족하거나 높이차가 있는 지역",
         "높이차가 크거나, 고층 건물이 있는 지역"],
        ["촬영 방향 중복도", "65% 이상", "75% 이상", "85% 이상"],
        ["인접 코스 중복도", "60% 이상", "70% 이상", "80% 이상"],
    ],
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def to_xml(t):
    rows = t["rows"]
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="{t["id"]}" article="{esc(t["article"])}" rows="{len(rows)}"'
         f' cols="{len(rows[0])}" source="{esc(t["source"])}">']
    for ri, row in enumerate(rows):
        L.append("  <row>")
        for ci, c in enumerate(row):
            head = ' header="1"' if ri == 0 else ""
            L.append(f'    <cell col="{ci}" row="{ri}"{head}>{esc(c)}</cell>')
        L.append("  </row>")
    L.append("</table>")
    return "\n".join(L)


def main(dry=False):
    out_dir = os.path.join(DATA, "objects", BASE)
    jf = os.path.join(DATA, BASE + ".json")
    doc = json.load(io.open(jf, encoding="utf-8"))

    hit = []

    def walk(ns):
        for n in ns:
            b = n.get("body") or ""
            if '<img id="pic1">' in b:
                hit.append(n)
            walk(n.get("children") or [])

    walk(doc["tree"])
    print(f"\n  {doc['name']} — 그림 자리표시 pic1 을 쓴 조문 {len(hit)}곳"
          + (f" ({', '.join(x['legacyNo'] for x in hit)})" if hit else ""))
    rows = T13OVL["rows"]
    print(f"  옮긴 표 — {T13OVL['article']} {len(rows)}행 {len(rows[0])}열")
    for r in rows:
        print("      | " + " | ".join(r))
    if dry:
        print("\n  --dry — 고치지 않았습니다.")
        return

    io.open(os.path.join(out_dir, T13OVL["id"] + ".xml"), "w", encoding="utf-8").write(to_xml(T13OVL))
    for n in hit:
        n["body"] = n["body"].replace('<img id="pic1">', f'<img id="{T13OVL["id"]}">')
    with io.open(jf, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    ip = os.path.join(out_dir, "index.json")
    idx = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    idx[T13OVL["id"]] = {"kind": "table", "article": T13OVL["article"],
                         "rows": len(rows), "cols": len(rows[0]),
                         "preview": " | ".join(rows[0])}
    # 원본 그림은 색인에 그대로 남긴다 — 옮긴 표와 견주어 볼 수 있게
    if "pic1" in idx:
        idx["pic1"]["preview"] = "원문 그림 (제13조) — 표로 옮긴 것은 t13ovl"
    with io.open(ip, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n  objects/{BASE}/{T13OVL['id']}.xml 을 만들고 본문 자리표시를 바꾸었습니다.")
    print("  초안도 다시 만드십시오 — python scripts/gendraft_uav.py")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
