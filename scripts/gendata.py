# -*- coding: utf-8 -*-
"""
국가법령정보센터 Open API → 프로토타입용 조문 트리 JSON 생성

  · target=admrul : 고시·예규·훈령 (행정규칙)
  · target=law    : 법률·시행령·시행규칙

사용:  python scripts/gendata.py
출력:  data/regNN.json, data/library.json
"""
import json, re, sys, os, io, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode("utf-8")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2)


def tag(x, t):
    m = re.search(rf"<{t}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>", x, re.S)
    return m.group(1).strip() if m else ""


norm = lambda s: re.sub(r"[\s·ㆍ・()]", "", s)


def find(target, name):
    q = urllib.parse.quote(name)
    xml = get(f"https://www.law.go.kr/DRF/lawSearch.do?OC=test&target={target}&query={q}&type=XML&display=100")
    items = re.findall(r"<(?:admrul|law) id=.*?</(?:admrul|law)>", xml, re.S)
    tgt, best = norm(name), None
    for it in items:
        if target == "admrul" and tag(it, "현행연혁구분") != "현행":
            continue
        nm = tag(it, "행정규칙명") or tag(it, "법령명한글")
        rec = {
            "name": nm,
            "seq": tag(it, "행정규칙일련번호") or tag(it, "법령일련번호"),
            "kind": tag(it, "행정규칙종류") or tag(it, "법령구분명"),
            "no": tag(it, "발령번호") or tag(it, "공포번호"),
            "date": tag(it, "발령일자") or tag(it, "공포일자"),
            "ef": tag(it, "시행일자"),
            "org": tag(it, "소관부처명"),
        }
        if norm(nm) == tgt:
            return rec
        if best is None and tgt in norm(nm):
            best = rec
    return best


# ───────────── 조문 파싱 ─────────────
RE = {
    "편": re.compile(r"^제\s*(\d+)\s*편\s*(.*)$"),
    "장": re.compile(r"^제\s*(\d+)\s*장\s*(.*)$"),
    "절": re.compile(r"^제\s*(\d+)\s*절\s*(.*)$"),
    "관": re.compile(r"^제\s*(\d+)\s*관\s*(.*)$"),
}
RE_JO = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*\(([^)]*)\)\s*([\s\S]*)$")
RE_JO2 = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*([\s\S]*)$")
LEVELS = ["편", "장", "절", "관", "조"]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draft2025_layout as LAYOUT      # 호·목을 줄로 가른다


def fmt_body(t):
    """받아온 한 줄을 항·호·목으로 갈라 놓는다.

    공개 API 는 조문을 한 줄로 준다 — 고시 원문에는 있던 줄바꿈이 없다.
    항(①②③)은 여기서 가르고, 호와 목은 draft2025_layout 이 가른다.
    (예전에는 '.' 뒤에 붙은 '1. ' 만 갈랐는데, 원문은 '내용2. 선임' 처럼
     띄어쓰기 없이 이어 붙인 곳이 많아 거의 걸리지 아니하였다.)
    """
    t = re.sub(r"\s+", " ", (t or "")).strip()
    t = re.sub(r"(?<!^)([①-⑳])", r"\n\1", t)
    return LAYOUT.relayout(t).strip()


def build_tree(lines):
    root, stack, seq = {"children": []}, [(-1, {"children": []})], [0]
    stack[0] = (-1, root)

    def nid(k):
        seq[0] += 1
        return f"{k}{seq[0]}"

    def push(node, lv):
        while stack and stack[-1][0] >= lv:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((lv, node))

    def mk(level, no, br, title, body=""):
        return {"id": nid("a" if level == "조" else "h"), "level": level, "no": no, "branch": br,
                "title": (title or "").strip(), "body": body, "status": "유지",
                "legacyNo": f"제{no}조" + (f"의{br}" if br else "") if level == "조" else "",
                "reason": "", "sourceRef": None, "history": [], "children": []}

    last = None
    for raw in lines:
        s = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not s:
            continue
        hit = False
        for i, lv in enumerate(["편", "장", "절", "관"]):
            m = RE[lv].match(s)
            if m:
                last = mk(lv, int(m.group(1)), 0, m.group(2))
                push(last, i)
                hit = True
                break
        if hit:
            continue
        m = RE_JO.match(s) or RE_JO2.match(s)
        if m:
            g = m.groups()
            no, br = int(g[0]), int(g[1]) if g[1] else 0
            title, body = (g[2], g[3]) if len(g) == 4 else ("", g[2])
            last = mk("조", no, br, title, fmt_body(body))
            push(last, 4)
            continue
        if last:
            last["body"] = (last["body"] + "\n" + s).strip()
    return root["children"]


def renumber(tree):
    jo = [0]

    def rec(list_):
        c = {"편": 0, "장": 0, "절": 0, "관": 0}
        for n in list_:
            if n["level"] == "조":
                jo[0] += 1
                n["no"] = jo[0]
            else:
                c[n["level"]] += 1
                n["no"] = c[n["level"]]
            rec(n["children"])
    rec(tree)


def count(ns, lv):
    return sum((1 if x["level"] == lv else 0) + count(x["children"], lv) for x in ns)


def fetch_lines(target, seq):
    key = "MST" if target == "law" else "ID"
    j = json.loads(get(f"https://www.law.go.kr/DRF/lawService.do?OC=test&target={target}&{key}={seq}&type=JSON"))
    if target == "admrul":
        svc = j.get("AdmRulService", {})
        lines = svc.get("조문내용") or []
        if isinstance(lines, str):
            lines = [lines]
        byl = (svc.get("별표") or {}).get("별표단위") or []
        return lines, byl
    svc = j.get("법령", {})
    units = (svc.get("조문") or {}).get("조문단위") or []
    if isinstance(units, dict):
        units = [units]
    def as_list(v):
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

    def text_of(v, key):
        """dict 면 key 값을, 문자열이면 그대로, 리스트면 이어붙여 돌려준다"""
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return " ".join(text_of(x, key) for x in v)
        return str(v.get(key) or "")

    lines = []
    for u in units:
        if not isinstance(u, dict):
            if u:
                lines.append(str(u).strip())
            continue
        c = text_of(u.get("조문내용"), "조문내용")
        if c:
            lines.append(c.strip())
        for h in as_list(u.get("항")):
            hc = text_of(h, "항내용") if not isinstance(h, dict) else text_of(h.get("항내용"), "항내용")
            if hc:
                lines.append(hc.strip())
            if isinstance(h, dict):
                for ho in as_list(h.get("호")):
                    hoc = text_of(ho, "호내용") if not isinstance(ho, dict) else text_of(ho.get("호내용"), "호내용")
                    if hoc:
                        lines.append(hoc.strip())
    byl = (svc.get("별표") or {}).get("별표단위") or []
    return lines, byl


# ───────────── 대상 목록 ─────────────
# (검색어, 정식명, 구분, target)
TARGETS = [
    ("공공측량 작업규정", "공공측량 작업규정", "core", "admrul"),

    # 상위 법령
    ("공간정보의 구축 및 관리 등에 관한 법률", "공간정보의 구축 및 관리 등에 관한 법률", "law", "law"),
    ("공간정보의 구축 및 관리 등에 관한 법률 시행령", "공간정보의 구축 및 관리 등에 관한 법률 시행령", "law", "law"),
    ("공간정보의 구축 및 관리 등에 관한 법률 시행규칙", "공간정보의 구축 및 관리 등에 관한 법률 시행규칙", "law", "law"),
    ("국가공간정보 기본법", "국가공간정보 기본법", "law", "law"),
    ("국가공간정보 기본법 시행령", "국가공간정보 기본법 시행령", "law", "law"),
    ("공간정보산업 진흥법", "공간정보산업 진흥법", "law", "law"),
    ("건설기술 진흥법", "건설기술 진흥법", "law", "law"),
    ("산업안전보건법", "산업안전보건법", "law", "law"),

    # 하위 규정 (고시·예규)
    ("국가기준점 관리규정", "국가기준점 관리규정", "sub", "admrul"),
    ("국가기준점측량 작업규정", "국가기준점측량 작업규정", "sub", "admrul"),
    ("무인비행장치 측량 작업규정", "무인비행장치 측량 작업규정", "sub", "admrul"),
    ("항공사진측량", "항공사진측량 작업 및 성과에 관한 규정", "sub", "admrul"),
    ("정사영상", "정사영상 제작 작업 및 성과에 관한 규정", "sub", "admrul"),
    ("수치지형도", "수치지형도 작성 작업 및 성과에 관한 규정", "sub", "admrul"),
    ("수치표고모형", "수치표고모형의 구축 및 관리 등에 관한 규정", "sub", "admrul"),
    ("3차원국토공간정보", "3차원국토공간정보구축작업규정", "sub", "admrul"),
    ("정밀도로지도", "정밀도로지도의 구축 및 갱신 등에 관한 규정", "sub", "admrul"),
    ("실내공간정보", "실내공간정보 구축 작업규정", "sub", "admrul"),
    ("지하공간통합지도", "지하공간통합지도 제작 작업규정", "sub", "admrul"),
    ("일반측량 작업규정", "일반측량 작업규정", "sub", "admrul"),
    ("측량기기 성능검사 규정", "측량기기 성능검사 규정", "sub", "admrul"),
    ("측량대가", "측량대가의 기준", "sub", "admrul"),
    ("국가공간정보 보안관리", "국토지리정보원 국가공간정보 보안관리규정", "sub", "admrul"),
    ("공간정보 표준화지침", "국토지리정보원 공간정보 표준화지침", "sub", "admrul"),
    ("기본공간정보", "기본공간정보 구축규정", "sub", "admrul"),
    ("지구물리측량", "지구물리측량 작업규정", "sub", "admrul"),
    ("적용받지 아니하는 측량", "공간정보 구축 및 관리 등에 관한 법률을 적용받지 아니하는 측량", "sub", "admrul"),

    # 성과심사·검사·검증
    ("측량성과 심사수탁기관", "측량성과 심사수탁기관의 심사업무 및 지정절차 등에 관한 규정", "review", "admrul"),
    ("국토지리정보원 용역사업 검사업무", "국토지리정보원 용역사업 검사업무 규정", "review", "admrul"),
    ("기본측량성과 검증기관", "국토지리정보원 기본측량성과 검증기관 지정 및 검증업무에 관한 규정", "review", "admrul"),
    ("공개제한 공간정보의 보안심사", "공개제한 공간정보의 보안심사 규정", "review", "admrul"),
    ("기본수로측량 품질관리", "기본수로측량 품질관리 규정", "review", "admrul"),
    ("측량기기 성능검사 대행업무 실태점검", "측량기기 성능검사 대행업무 실태점검 지침", "review", "admrul"),
    ("측량기기 성능검사대행자 교육", "측량기기 성능검사대행자 교육에 관한 규정", "review", "admrul"),
    ("측량성과 국외반출 허가심사", "측량성과 국외반출 허가심사 운영규정", "review", "admrul"),
    ("측량성과 국외반출 협의체", "측량성과 국외반출 협의체 운영규정", "review", "admrul"),
    ("공간정보 제공 및 관리에 관한 규정", "국토지리정보원 공간정보 제공 및 관리에 관한 규정", "review", "admrul"),
    ("측량 및 공간정보 전문가위원회", "측량 및 공간정보 전문가위원회 운영에 관한 규정", "review", "admrul"),
    ("측량기준점표지 현황조사 보고", "측량기준점표지 현황조사 보고 지침", "review", "admrul"),
    ("수치지도 수정용 건설공사준공도면", "수치지도 수정용 건설공사준공도면 작성에 관한 지침", "review", "admrul"),

    # 지하시설물측량 관련 개별법
    ("도로법", "도로법", "under", "law"),
    ("하수도법", "하수도법", "under", "law"),
    ("수도법", "수도법", "under", "law"),
    ("전기통신기본법", "전기통신기본법", "under", "law"),
    ("도시가스사업법", "도시가스사업법", "under", "law"),
    ("전기사업법", "전기사업법", "under", "law"),
    ("집단에너지사업법", "집단에너지사업법", "under", "law"),
    ("송유관 안전관리법", "송유관 안전관리법", "under", "law"),
]

# 본문을 API 로 받을 수 없어 파일로만 보유하는 것 (목록에만 표시)
EXTRA = [
    ("作業規程の準則 (일본 국토지리원 2025)", "국토교통성", "고시", "2025", "ja", "intl",
     "국외관련규정\\일본_작업규정의준칙_2025\\00_作業規程の準則_전문.pdf"),
    ("公共測量の手引 (일본 2026년도판)", "국토지리원", "안내서", "2026", "ja", "intl",
     "국외관련규정\\일본_작업규정의준칙_2025\\公共測量の手引_2026년도판.pdf"),
    ("ASPRS Positional Accuracy Standards Ed.2 v2", "ASPRS", "표준", "2024", "en", "intl",
     "국외관련규정\\2024_ASPRS_Positional_Accuracy_Standards_Edition2_Version2.0_영문원본.pdf"),
    ("USGS Lidar Base Specification 2025 rev.A", "USGS", "표준", "2025", "en", "intl",
     "국외관련규정\\미국_USGS_FGDC\\USGS_Lidar_Base_Specification_2025_revA.docx"),
    ("FGDC-STD-007.3-1998 NSSDA", "FGDC", "표준", "1998", "en", "intl",
     "국외관련규정\\미국_USGS_FGDC\\FGDC-STD-007.3-1998_NSSDA...pdf"),
    ("Cadastral Survey Rules 2021 (LINZ)", "LINZ", "규칙", "2021", "en", "intl",
     "국외관련규정\\뉴질랜드_LINZ\\"),
    ("건설공사 측량 표준시방서 (KCS 12 00 00)", "국토지리정보원", "고시", "20241121", "ko", "nobody",
     "하위규정\\건설공사 측량 표준시방서(KCS 12 00 00)...pdf"),
    ("건설공사 측량 표준시방서 (KCS 12 30 00)", "국토지리정보원", "고시", "20260812", "ko", "nobody",
     "하위규정\\건설공사 측량 표준시방서(KCS 12 30 00)...pdf"),
    ("건설측량 설계기준 (KDS 12 00 00)", "국토지리정보원", "고시", "20241121", "ko", "nobody",
     "하위규정\\건설측량 설계기준(KDS 12 00 00)...pdf"),
    ("공간정보 제공 수수료 조정", "국토지리정보원", "고시", "20230331", "ko", "nobody",
     "성과심사관련규정\\공간정보 제공 수수료 조정...pdf"),
]

CAT_LABEL = {
    "core": "핵심 규정", "law": "상위 법령", "sub": "하위 규정",
    "review": "성과심사 관련", "under": "지하시설물 관련 법령",
    "intl": "국외 기준", "nobody": "본문 없음 (별도 기준서)",
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    lib, i = [], 0
    for q, name, cat, target in TARGETS:
        i += 1
        sid = f"reg{i:02d}"
        try:
            hit = find(target, name)
            if not hit:
                print(f"  [없음] {name}")
                continue
            lines, byl = fetch_lines(target, hit["seq"])
            tree = build_tree(lines)
            renumber(tree)
            if isinstance(byl, dict):
                byl = [byl]
            annex = []
            for b in byl:
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
            stats = {k: count(tree, k) for k in LEVELS}
            if not stats["조"]:
                print(f"  [조문없음] {name}")
                continue
            url = ("https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=" if target == "law"
                   else "https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=") + hit["seq"]
            # 별표·서식을 조문 트리와 같은 형태의 가지로 만든다 (참조 창에서 함께 펼쳐 보기)
            annex_tree = []
            if annex:
                groups = {}
                for a in annex:
                    groups.setdefault(a["gubun"], []).append(a)
                for gi, (gubun, arr) in enumerate(groups.items(), start=1):
                    kids = []
                    for a in arr:
                        links = " / ".join(
                            f"{k.upper()} {a[k]}" for k in ("hwp", "pdf") if a.get(k))
                        kids.append({
                            "id": f"{sid}-anx-{gubun}-{a['no']}", "level": "조", "no": 0, "branch": 0,
                            "title": a["title"],
                            "body": links, "status": "유지", "legacyNo": f"{gubun} {a['no']}",
                            "reason": "", "sourceRef": None, "history": [],
                            "annexRef": {"gubun": gubun, "no": a["no"], "hwp": a.get("hwp"), "pdf": a.get("pdf")},
                            "children": [], "collapsed": False,
                        })
                    annex_tree.append({
                        "id": f"{sid}-anxgrp-{gi}", "level": "편", "no": 0, "branch": 0,
                        "title": f"{gubun} ({len(arr)}건)", "body": "", "status": "유지",
                        "legacyNo": "", "reason": "", "sourceRef": None, "history": [],
                        "isAnnex": True, "children": kids, "collapsed": True,
                    })

            doc = {"id": sid, "name": hit["name"], "org": hit["org"], "kind": hit["kind"],
                   "no": hit["no"], "promulgated": hit["date"], "effective": hit["ef"],
                   "lang": "ko", "category": cat, "source": url,
                   "stats": stats, "annex": annex, "annexTree": annex_tree, "tree": tree}
            with io.open(os.path.join(OUT, sid + ".json"), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective", "lang", "category", "source", "stats")}
            e["file"] = sid + ".json"
            e["hasFullText"] = True
            e["annexCount"] = len(annex)
            lib.append(e)
            print(f"  OK  {stats['조']:>4}조  [{CAT_LABEL[cat]}] {hit['name']}")
        except Exception as ex:
            print(f"  [오류] {name}: {ex}")

    for j, (nm, org, kind, ef, lang, cat, path) in enumerate(EXTRA, start=1):
        lib.append({"id": f"ext{j:02d}", "name": nm, "org": org, "kind": kind, "no": "",
                    "effective": ef, "lang": lang, "category": cat, "source": "",
                    "stats": {}, "file": None, "hasFullText": False, "path": path})

    with io.open(os.path.join(OUT, "library.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d"), "categories": CAT_LABEL,
                   "regulations": lib}, f, ensure_ascii=False, indent=1)
    idx = sum(1 for x in lib if x["hasFullText"])
    print(f"\nlibrary.json — 총 {len(lib)}종 (본문 색인 {idx}종 / 파일만 {len(lib)-idx}종)")
