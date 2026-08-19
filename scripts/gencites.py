# -*- coding: utf-8 -*-
"""
공공측량 작업규정(reg01) 조문이 인용하는 '별도 규정'을 찾아 library.json 에 표시한다.

  · 조문 본문의 「…」 인용을 모아 규정명을 뽑는다
  · 목록(library.json)의 규정명과 맞춰 본다 (띄어쓰기·괄호 무시)
  · 맞으면  regulations[].citedIn = ["제61조", …]  로 적어 넣는다
  · 못 맞춘 인용은 화면에 찍어 준다 (= 아직 확보하지 못한 규정)

사용:  python scripts/gencites.py
"""
import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

CORE = "reg01"

# 인용이지만 규정 이름이 아닌 것들
STOP = {
    "법", "이 법", "같은 법", "같은법", "영", "규칙", "이 규정", "규정", "고시",
    "공공측량", "측량", "성과", "작업규정", "작업규칙",
}
# 이름이 바뀐 규정 — 조문 인용명 → 현행 규정명
ALIAS = {
    "정밀도로지도 제작 작업규정": "정밀도로지도의 구축 및 갱신 등에 관한 규정",
    "수치지도작성작업규칙": "수치지도 작성 작업규칙",
    "시설물의 안전관리에 관한 특별법 시행령": "시설물의 안전 및 유지관리에 관한 특별법 시행령",
    "도로기반시설물정보 통합관리에 관한 지침": "도로기반시설물의 정보 및 시스템 유지관리 지침",
}

# 규정명으로 끝나는 꼬리말 — 이걸로 끝나야 규정으로 본다
TAIL = ("법", "법률", "시행령", "시행규칙", "규칙", "규정", "지침", "기준",
        "고시", "훈령", "예규", "요령", "준칙", "표준", "특별법", "기본법")


def norm(s):
    """비교용 정규화 — 띄어쓰기·괄호·가운뎃점을 없앤다"""
    s = re.sub(r"\([^)]*\)", "", str(s))
    return re.sub(r"[\s·ㆍ・,]+", "", s)


def label_of(node):
    return node.get("legacyNo") or node.get("no") or ""


def collect(tree):
    out = []
    def walk(ns):
        for n in ns:
            if n.get("body"):
                out.append((label_of(n), n.get("title", ""), n["body"]))
            walk(n.get("children") or [])
    walk(tree)
    return out


if __name__ == "__main__":
    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    core = next(r for r in lib["regulations"] if r["id"] == CORE)
    doc = json.load(io.open(os.path.join(DATA, core["file"]), encoding="utf-8"))
    arts = collect(doc["tree"])

    quoted = re.compile(r"[「『]\s*([^」』\n]{2,80}?)\s*[」』]")
    cites = {}                      # 원문 규정명 → [조번호, …]
    for no, _t, body in arts:
        for m in quoted.findall(body):
            m = re.sub(r"\s+", " ", m).strip()
            if m in STOP or not m.endswith(TAIL):
                continue
            cites.setdefault(m, [])
            if no and no not in cites[m]:
                cites[m].append(no)

    # 목록과 맞춰 본다
    by_norm = {}
    for r in lib["regulations"]:
        by_norm.setdefault(norm(r["name"]), r)

    matched, unmatched = {}, {}
    for name, nos in cites.items():
        n = norm(ALIAS.get(name, name))
        hit = by_norm.get(n)
        if not hit:                                   # 부분 일치도 허용
            for k, r in by_norm.items():
                if len(n) >= 6 and (n in k or k in n):
                    hit = r
                    break
        if hit and hit["id"] != CORE:
            matched.setdefault(hit["id"], {"name": hit["name"], "cited": [], "as": set()})
            matched[hit["id"]]["as"].add(name)
            for x in nos:
                if x not in matched[hit["id"]]["cited"]:
                    matched[hit["id"]]["cited"].append(x)
        elif not hit:
            unmatched[name] = nos

    def keyno(s):
        m = re.search(r"\d+", s or "")
        return int(m.group()) if m else 9999

    for r in lib["regulations"]:
        got = matched.get(r["id"])
        if got:
            r["citedIn"] = sorted(got["cited"], key=keyno)
        else:
            r.pop("citedIn", None)

    lib["citedUnmatched"] = [
        {"name": k, "citedIn": sorted(v, key=keyno)}
        for k, v in sorted(unmatched.items(), key=lambda kv: -len(kv[1]))
    ]
    # 이름이 바뀐 규정 — 앱도 옛 이름으로 한 인용을 링크로 이을 수 있게 함께 싣는다
    byname = {norm(r["name"]): r["id"] for r in lib["regulations"]}
    lib["nameAlias"] = {k: byname[norm(v)] for k, v in ALIAS.items()
                        if norm(v) in byname}

    with io.open(os.path.join(DATA, "library.json"), "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, separators=(",", ":"))

    print(f"조문 {len(arts)}건에서 인용 {len(cites)}종 확인\n")
    print(f"■ 목록에 있는 규정 {len(matched)}종 — '규정 내 별도규정' 으로 묶습니다")
    for rid, v in sorted(matched.items(), key=lambda kv: -len(kv[1]["cited"])):
        print(f"  {rid}  {v['name']}")
        print(f"        인용 {len(v['cited'])}곳 — {', '.join(v['cited'][:12])}"
              + (" …" if len(v["cited"]) > 12 else ""))
    print(f"\n■ 목록에 없는 인용 {len(unmatched)}종 — 아직 확보하지 못한 규정")
    for k, v in sorted(unmatched.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}   ← {', '.join(v[:10])}{' …' if len(v) > 10 else ''}")
