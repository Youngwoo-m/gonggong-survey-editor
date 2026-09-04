# -*- coding: utf-8 -*-
"""
일련번호를 콕 집어 규정 하나를 색인한다.

addregs.py 의 검색은 '현행' 만 골라 오기 때문에, 폐지되었거나 이름이 바뀐
규정은 이름으로 찾을 수 없다. 국가법령정보센터 웹에서 확인한 일련번호를
직접 넣어 같은 구조로 색인한다.

사용:  python scripts/addseq.py admrul 65959 sub
       python scripts/addseq.py law   123456 under
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gendata as G
import addregs as A

sys.stdout.reconfigure(encoding="utf-8")


def info(target, seq):
    """일련번호로 이름·발령번호 따위를 받아 온다"""
    key = "MST" if target == "law" else "ID"
    j = json.loads(G.get("https://www.law.go.kr/DRF/lawService.do?OC=test"
                         f"&target={target}&{key}={seq}&type=JSON"))
    if target == "admrul":
        b = (j.get("AdmRulService") or {}).get("행정규칙기본정보") or {}
        return {
            "name": b.get("행정규칙명", "").strip(),
            "seq": str(seq),
            "kind": b.get("행정규칙종류") or "고시",
            "no": b.get("발령번호") or "",
            "date": b.get("발령일자") or "",
            "ef": b.get("시행일자") or "",
            "org": b.get("소관부처명") or "",
            "current": b.get("현행여부") == "Y",
        }
    b = (j.get("법령") or {}).get("기본정보") or {}
    return {
        "name": (b.get("법령명_한글") or "").strip(), "seq": str(seq),
        "kind": b.get("법종구분", {}).get("content") if isinstance(b.get("법종구분"), dict)
        else b.get("법종구분") or "법령",
        "no": str(b.get("공포번호") or ""), "date": str(b.get("공포일자") or ""),
        "ef": str(b.get("시행일자") or ""), "org": "", "current": True,
    }


def main(target, seq, cat):
    libpath = os.path.join(G.OUT, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    hit = info(target, seq)
    if not hit["name"]:
        print("일련번호로 규정을 찾지 못했습니다"); return 1
    if any(G.norm(r["name"]) == G.norm(hit["name"]) for r in lib["regulations"]):
        print(f"이미 있습니다 — {hit['name']}"); return 0

    sid = A.next_id(lib)
    doc = A.build_doc(sid, hit, cat, target)
    if not hit["current"]:                       # 폐지·연혁본임을 밝혀 둔다
        doc["note"] = f"폐지된 규정입니다 ({hit['kind']} 제{hit['no']}호, {hit['date']} 발령)"
    with io.open(os.path.join(G.OUT, sid + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                             "lang", "category", "source", "stats")}
    e.update(file=sid + ".json", hasFullText=True, annexCount=len(doc["annex"]))
    if doc.get("note"):
        e["note"] = doc["note"]
    lib["regulations"].append(e)
    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(f"OK  {sid}  {doc['stats']['조']}조 · 별표 {len(doc['annex'])}  {doc['name']}")
    print(f"    {doc['source']}")
    if doc.get("note"):
        print(f"    {doc['note']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
