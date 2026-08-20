# -*- coding: utf-8 -*-
"""인용 검사가 '라이브러리에 없는 규정' 으로 남긴 법령을 받아 색인한다.

세 규정이 부르는데 라이브러리에 없어 '확인필요' 로 남던 것들이다 —
그 조가 성한지 사람이 손으로 살펴야 했다. 받아 두면 인용 검사가
스스로 가린다.

addregs.py 와 같은 길을 쓰되, 이미 있는 regNN.json 은 손대지 아니한다.

사용:  python scripts/addcited.py
"""
import io, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gendata as G

sys.stdout.reconfigure(encoding="utf-8")
OUT = G.OUT

# (검색어, 정식명, 갈래, target) — 갈래: under 개별법 · sub 하위규정
NEW = [
    ("전자정부법", "전자정부법", "under", "law"),
    ("공공기록물 관리에 관한 법률", "공공기록물 관리에 관한 법률", "under", "law"),
    ("공공기록물 관리에 관한 법률 시행령", "공공기록물 관리에 관한 법률 시행령", "under", "law"),
    ("형법", "형법", "under", "law"),
    ("항공안전법 시행규칙", "항공안전법 시행규칙", "under", "law"),
]


def next_id(lib):
    used = {r["id"] for r in lib["regulations"]}
    i = 1
    while f"reg{i:02d}" in used:
        i += 1
    return f"reg{i:02d}"


def build_doc(sid, hit, cat, target):
    lines, byl = G.fetch_lines(target, hit["seq"])
    tree = G.build_tree(lines)
    G.renumber(tree)                     # 편ㆍ장만 다시 매긴다 — 조는 원문 번호를 지킨다
    if isinstance(byl, dict):
        byl = [byl]

    annex = []
    for b in (byl or []):
        gubun = b.get("별표구분") or "별표"
        no = (b.get("별표번호") or "").lstrip("0") or "1"
        br = (b.get("별표가지번호") or "").lstrip("0")
        annex.append({
            "gubun": gubun,
            "no": f"{no}의{br}" if br else no,
            "title": (b.get("별표제목") or "").strip(),
            "hwp": ("https://www.law.go.kr" + b["별표서식파일링크"]) if b.get("별표서식파일링크") else "",
            "pdf": ("https://www.law.go.kr" + b["별표서식PDF파일링크"]) if b.get("별표서식PDF파일링크") else "",
        })

    stats = {k: G.count(tree, k) for k in G.LEVELS}
    if not stats["조"]:
        raise RuntimeError("조문을 받지 못했습니다")

    annex_tree = []
    if annex:
        groups = {}
        for a in annex:
            groups.setdefault(a["gubun"], []).append(a)
        for gi, (gubun, arr) in enumerate(groups.items(), start=1):
            kids = []
            for a in arr:
                links = " / ".join(f"{k.upper()} {a[k]}" for k in ("hwp", "pdf") if a.get(k))
                kids.append({
                    "id": f"{sid}-anx-{gubun}-{a['no']}", "level": "조", "no": 0, "branch": 0,
                    "title": a["title"], "body": links, "status": "유지",
                    "legacyNo": f"{gubun} {a['no']}", "reason": "", "sourceRef": None,
                    "history": [],
                    "annexRef": {"gubun": gubun, "no": a["no"], "hwp": a.get("hwp"), "pdf": a.get("pdf")},
                    "children": [], "collapsed": False,
                })
            annex_tree.append({
                "id": f"{sid}-anxgrp-{gi}", "level": "편", "no": 0, "branch": 0,
                "title": f"{gubun} ({len(arr)}건)", "body": "", "status": "유지",
                "legacyNo": "", "reason": "", "sourceRef": None, "history": [],
                "isAnnex": True, "children": kids, "collapsed": True,
            })

    url = "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=" + hit["seq"]
    return {"id": sid, "name": hit["name"], "org": hit["org"], "kind": hit["kind"],
            "no": hit["no"], "promulgated": hit["date"], "effective": hit["ef"],
            "lang": "ko", "category": cat, "source": url,
            "stats": stats, "annex": annex, "annexTree": annex_tree, "tree": tree}


def check_numbers(doc):
    """조 번호가 원문(legacyNo)과 맞는지 본다 — 들여오기가 또 밀지 않았는지"""
    bad = []

    def w(ns):
        for n in ns:
            if n.get("level") == "조" and n.get("legacyNo"):
                want = "제%d조" % n["no"] + ("의%d" % n["branch"] if n.get("branch") else "")
                if want != n["legacyNo"]:
                    bad.append((n["legacyNo"], want))
            w(n.get("children") or [])

    w(doc["tree"])
    return bad


if __name__ == "__main__":
    libpath = os.path.join(OUT, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    have = {G.norm(r["name"]) for r in lib["regulations"]}

    added, failed = [], []
    for q, name, cat, target in NEW:
        if G.norm(name) in have:
            print("  [이미 있음] %s" % name)
            continue
        try:
            hit = G.find(target, q) or G.find(target, name)
            if not hit:
                failed.append((name, "검색 결과 없음"))
                print("  [없음] %s" % name)
                continue
            sid = next_id(lib)
            doc = build_doc(sid, hit, cat, target)
            bad = check_numbers(doc)
            if bad:
                failed.append((name, "조 번호가 원문과 어긋난다 %d곳 (보기 %s)" % (len(bad), bad[:2])))
                print("  [번호 어긋남] %s — %d곳" % (name, len(bad)))
                continue
            with io.open(os.path.join(OUT, sid + ".json"), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                                     "lang", "category", "source", "stats")}
            e["file"] = sid + ".json"
            e["hasFullText"] = True
            e["annexCount"] = len(doc["annex"])
            lib["regulations"].append(e)
            have.add(G.norm(doc["name"]))
            added.append(e)
            print("  OK  %s  %4d조 · 별표 %2d  %s (시행 %s)"
                  % (sid, doc["stats"]["조"], len(doc["annex"]), doc["name"], doc["effective"]))
        except Exception as ex:
            failed.append((name, str(ex)))
            print("  [오류] %s: %s" % (name, ex))
        time.sleep(0.5)

    if added:
        lib["generated"] = time.strftime("%Y-%m-%d")
        with io.open(libpath, "w", encoding="utf-8") as f:
            json.dump(lib, f, ensure_ascii=False, indent=1)

    print("\n더한 규정 %d종 / 실패 %d종 · library.json 총 %d종"
          % (len(added), len(failed), len(lib["regulations"])))
    for n, why in failed:
        print("   - %s : %s" % (n, why))
