# -*- coding: utf-8 -*-
"""옮겨 둔 부속서 D ㆍ E ㆍ F 의 한국어를 data/loc29.json 에 붙인다.

옮긴 글 자체는 iso19157_ko_annex_def.py 에 있다 — 글이 길어 붙이는 일과
갈라 두었다. genintl_iso19157.py 도 그 파일을 읽어, 색인을 다시 지어도
옮긴 글을 잃지 않는다.

사용:  python scripts/iso19157_ko_annex.py
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P = os.path.join(ROOT, "data", "loc29.json")
sys.path.insert(0, HERE)

from iso19157_ko_annex_def import KO      # noqa: E402

if __name__ == "__main__":
    doc = json.load(io.open(P, encoding="utf-8"))
    hit, seen_cl = [], set()

    def w(ns):
        for n in ns:
            c = n.get("clause") or ""
            if c:
                seen_cl.add(c)
            if c in KO:
                n["transBody"] = KO[c]
                hit.append(c)
            w(n.get("children") or [])

    w(doc["tree"])
    miss = [c for c in KO if c not in seen_cl]
    assert not miss, "색인에 없는 마디 — %s" % ", ".join(sorted(miss))

    # 대역 딱지를 지금 상태에 맞춘다
    total, ko = 0, 0

    def count(ns):
        global total, ko
        for n in ns:
            total += 1
            if (n.get("transBody") or "").strip():
                ko += 1
            count(n.get("children") or [])

    count(doc["tree"])
    left = []

    def rest(ns):
        for n in ns:
            if not (n.get("transBody") or "").strip() and (n.get("body") or "").strip():
                left.append(n.get("clause") or (n.get("title") or "")[:30])
            rest(n.get("children") or [])

    rest(doc["tree"])

    doc["translated"] = {
        "lang": "en",
        "coverage": round(ko / max(1, total), 3),
        "by": ("사람이 옮김 — 제목 79/79. 본문은 규범 마디 전부(머리말ㆍ들어가는 말, "
               "제1~12조, 규범 부속서 A ㆍ C ㆍ H)와, 우리 별표ㆍ별지 설계에 쓰이는 "
               "참고 부속서 D(평가와 보고) ㆍ E(표본추출) ㆍ F(품질요소 사용 지침)를 "
               "옮겼다. 남은 것은 참고 부속서 B ㆍ G ㆍ I 와 참고문헌이다. "
               "고시에 인용할 한국어 정본은 「KS X ISO 19157-1」(2025. 12. 12. 제정)이다."),
    }

    io.open(P, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False))
    print("부속서 D ㆍ E ㆍ F 의 %d마디에 한국어를 붙였다" % len(hit))
    print("한국어가 있는 마디 %d/%d · %.0f%%" % (ko, total, doc["translated"]["coverage"] * 100))
    print("이번에 옮긴 글자 %d자" % sum(len(v) for v in KO.values()))
    print("\n아직 원문뿐인 마디 %d개 — %s" % (len(left), ", ".join(left[:12])))
