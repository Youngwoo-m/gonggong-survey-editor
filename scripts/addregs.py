# -*- coding: utf-8 -*-
"""
규정을 목록에 '덧붙여' 색인한다 (기존 data/regNN.json 은 손대지 않는다).

gendata.py 는 전부 다시 만들기 때문에 이미 저장한 프로젝트의 노드 id 가 어긋난다.
여기서는 새 규정만 빈 번호에 얹고 library.json 에 항목을 더한다.

사용:  python scripts/addregs.py
"""
import io, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gendata as G                     # find / fetch_lines / build_tree / renumber / count

sys.stdout.reconfigure(encoding="utf-8")
OUT = G.OUT

# (검색어, 정식명, 구분, target)
#   구분: law 상위법령 · sub 하위규정 · review 성과심사 · under 개별법
NEW = [
    # ── 국토교통부령 — 작업규정이 가장 많이 인용하는 두 건
    ("지도도식규칙", "지도도식규칙", "sub", "law"),
    ("수치지도 작성 작업규칙", "수치지도 작성 작업규칙", "sub", "law"),

    # ── 국토지리정보원 고시
    ("지형도 도식 적용규정", "지형도 도식 적용규정", "sub", "admrul"),
    ("도로기반시설물정보 통합관리에 관한 지침", "도로기반시설물정보 통합관리에 관한 지침", "sub", "admrul"),
    ("지방자치단체의 도로 및 상하수도의 시설물관리를 위한 범용프로그램",
     "지방자치단체의 도로 및 상ㆍ하수도의 시설물관리를 위한 범용프로그램의 기본설계서 및 품질인증기준",
     "sub", "admrul"),

    # ── 안전
    ("산업안전보건기준에 관한 규칙", "산업안전보건기준에 관한 규칙", "law", "law"),

    # ── 지하시설물측량 관련 개별법 (제168조·제216조)
    ("국토의 계획 및 이용에 관한 법률", "국토의 계획 및 이용에 관한 법률", "under", "law"),
    ("도시철도법", "도시철도법", "under", "law"),
    ("철도의 건설 및 철도시설 유지관리에 관한 법률",
     "철도의 건설 및 철도시설 유지관리에 관한 법률", "under", "law"),
    ("시설물의 안전 및 유지관리에 관한 특별법 시행령",
     "시설물의 안전 및 유지관리에 관한 특별법 시행령", "under", "law"),
    ("고압가스 안전관리법", "고압가스 안전관리법", "under", "law"),
    ("위험물안전관리법", "위험물안전관리법", "under", "law"),
    ("화학물질관리법", "화학물질관리법", "under", "law"),
    ("지하안전관리에 관한 특별법", "지하안전관리에 관한 특별법", "under", "law"),

    # ── 법제 (재검토기한 근거)
    ("훈령ㆍ예규 등의 발령 및 관리에 관한 규정",
     "훈령ㆍ예규 등의 발령 및 관리에 관한 규정", "review", "admrul"),

    # ── 제182조가 인용한 지침의 후속 규정 (원래 이름으로는 검색되지 않는다)
    ("도로기반시설물의 정보 및 시스템 유지관리 지침",
     "도로기반시설물의 정보 및 시스템 유지관리 지침", "sub", "admrul"),

    # ── 미색인으로 남아 있던 것 — 이름을 바로잡아 다시 찾았다
    ("공간정보 제공 수수료", "공간정보 제공 수수료 조정", "sub", "admrul"),
    ("건설공사 측량 표준시방서", "건설공사 측량 표준시방서(KCS 12 00 00)", "sub", "admrul"),
    ("건설측량 설계기준", "건설측량 설계기준(KDS 12 00 00)", "sub", "admrul"),
]

# 국가법령정보센터에 원문이 없어 목록에만 올리는 것
NO_FULLTEXT = [
    ("지방자치단체의 도로 및 상ㆍ하수도의 시설물관리를 위한 범용프로그램의 기본설계서 및 품질인증기준",
     "국토교통부", "고시", "nobody",
     "국가법령정보센터에서 검색되지 않습니다 (폐지 또는 명칭 변경으로 보입니다)"),
]


def next_id(lib):
    used = {r["id"] for r in lib["regulations"]}
    i = 0
    while True:
        i += 1
        sid = f"reg{i:02d}"
        if sid not in used:
            return sid


def fetch_lines(target, seq):
    """gendata.fetch_lines 와 같되, 행정규칙에 '조문내용' 이 없으면 '조문' 을 본다
       (대통령훈령·국무총리훈령이 이 모양이다)"""
    lines, byl = G.fetch_lines(target, seq)
    if lines or target != "admrul":
        return lines, byl
    import urllib.request
    j = json.loads(G.get(f"https://www.law.go.kr/DRF/lawService.do?OC=test&target=admrul&ID={seq}&type=JSON"))
    svc = j.get("AdmRulService", {})
    jm = svc.get("조문")
    units = jm.get("조문단위") if isinstance(jm, dict) and jm.get("조문단위") else jm
    if isinstance(units, dict):
        units = [units]
    out = []
    for u in (units or []):
        if isinstance(u, str):
            out.append(u.strip())
        elif isinstance(u, dict):
            c = u.get("조문내용")
            if isinstance(c, list):
                out.extend(str(x).strip() for x in c if str(x).strip())
            elif c:
                out.append(str(c).strip())
    return [x for x in out if x], byl


def build_doc(sid, hit, cat, target):
    lines, byl = fetch_lines(target, hit["seq"])
    tree = G.build_tree(lines)
    G.renumber(tree)
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

    url = ("https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=" if target == "law"
           else "https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=") + hit["seq"]
    return {"id": sid, "name": hit["name"], "org": hit["org"], "kind": hit["kind"],
            "no": hit["no"], "promulgated": hit["date"], "effective": hit["ef"],
            "lang": "ko", "category": cat, "source": url,
            "stats": stats, "annex": annex, "annexTree": annex_tree, "tree": tree}


if __name__ == "__main__":
    libpath = os.path.join(OUT, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    have = {G.norm(r["name"]) for r in lib["regulations"]}

    added, failed = [], []
    for q, name, cat, target in NEW:
        if G.norm(name) in have:
            print(f"  [이미 있음] {name}")
            continue
        try:
            hit = G.find(target, q) or G.find(target, name)
            if not hit:
                failed.append((name, "검색 결과 없음"))
                print(f"  [없음] {name}")
                continue
            sid = next_id(lib)
            doc = build_doc(sid, hit, cat, target)
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
            print(f"  OK  {sid}  {doc['stats']['조']:>4}조 · 별표 {len(doc['annex']):>2}  {doc['name']}")
        except Exception as ex:
            failed.append((name, str(ex)))
            print(f"  [오류] {name}: {ex}")
        time.sleep(0.4)

    # 원문을 못 구한 것도 목록에는 남긴다
    for nm, org, kind, cat, note in NO_FULLTEXT:
        if G.norm(nm) in have:
            continue
        n = sum(1 for r in lib["regulations"] if str(r["id"]).startswith("ext")) + 1
        lib["regulations"].append({
            "id": f"ext{n:02d}", "name": nm, "org": org, "kind": kind, "no": "",
            "effective": "", "lang": "ko", "category": cat, "source": "",
            "stats": {}, "file": None, "hasFullText": False, "note": note,
        })
        have.add(G.norm(nm))
        print(f"  목록만  {nm}")

    lib["generated"] = time.strftime("%Y-%m-%d")
    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(f"\n더한 규정 {len(added)}종 / 실패 {len(failed)}종")
    for n, why in failed:
        print(f"   - {n} : {why}")
    print(f"library.json — 총 {len(lib['regulations'])}종")
