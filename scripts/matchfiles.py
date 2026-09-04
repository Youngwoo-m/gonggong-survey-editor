# -*- coding: utf-8 -*-
r"""App\관련규정 의 파일을 서고의 규정과 이름으로 짝짓는다 (아무것도 옮기지 아니한다).

■ 왜 짝지어야 하는가

  서고 103종 가운데 자료에 원문 파일이 이어져 있는 것은 다섯뿐이다. 나머지는
  `source` 가 law.go.kr 주소다. 그런데 App\관련규정 에는 파일이 900개 넘게
  있다. 어느 파일이 어느 규정의 것인지 자료가 모른다.

  옮기거나 이름을 바꾸기 전에 **무엇이 무엇과 짝인지 사람이 먼저 보아야 한다.**
  이 도구는 표만 낸다.

■ 어떻게 짝짓는가

  파일 이름에서 군더더기를 걷어 낸 뒤 규정 이름과 견준다.

      [별표 3] 공공측량 성과심사 세부항목…(측량성과 심사수탁기관의…규정).pdf
      → 괄호 안의 규정 이름을 먼저 본다 (별표 파일은 그것이 임자다)

      측량성과 심사수탁기관의…규정(국토지리정보원고시)(제2025-2091호)(20250423).pdf
      → 고시번호ㆍ날짜ㆍ발령기관 괄호를 뗀다

  걷어 낸 이름이 규정 이름을 품거나 규정 이름이 그것을 품으면 짝으로 본다.
  여럿이 걸리면 가장 긴 이름을 고른다 — 「공간정보의 구축 및 관리 등에 관한
  법률」과 「…법률 시행령」이 함께 걸릴 때 시행령을 놓치지 아니하려는 것이다.

  python scripts\matchfiles.py             간추려 보여 준다
  python scripts\matchfiles.py --md 파일.md  표로 적는다
  python scripts\matchfiles.py --miss       짝을 못 찾은 것만 본다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
BOX = os.path.join(APP, "관련규정")
NL = chr(10)

# 파일 이름에서 걷어 낼 것
DROP = [
    r"\([^)]*고시[^)]*\)", r"\([^)]*훈령[^)]*\)", r"\([^)]*예규[^)]*\)",
    r"\(제?\s*\d{4}-\d+호?\)", r"\(\d{8}\)", r"\(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\)",
    r"\(국토교통부령[^)]*\)", r"\(대통령령[^)]*\)", r"\(법률[^)]*\)",
    r"^\[[^\]]*\]\s*", r"^\d+[._-]\s*",
]
RE_TAIL = re.compile(r"\(([^()]{6,60})\)\s*$")     # 별표 파일 끝의 (규정 이름)


def norm(s):
    s = re.sub(r"\s+", "", str(s or ""))
    return re.sub(r"[·ㆍ,.\-_()\[\]『』「」'\"]+", "", s)


def strip_name(f):
    s = os.path.splitext(f)[0]
    for pat in DROP:
        s = re.sub(pat, "", s)
    return s.strip(" .-_")


def regs():
    lib = json.load(io.open(os.path.join(ROOT, "data", "library.json"),
                            encoding="utf-8"))
    cats = lib.get("categories", {})
    out = []
    for r in lib["regulations"]:
        out.append((r["id"], r["name"], r.get("category"),
                    cats.get(r.get("category"), r.get("category"))))
    return out


DROP_PAIR = {
    "무인비행장치 측량 작업규정개정관련/2024년.연구.한글파일/1. 표지.hwpx":
        "보고서 겉표지 — 「표지」가 「측량기준점표지」와 겹쳤을 뿐임",
    "무인비행장치 측량 작업규정개정관련/2025년.연구결과/무인비행장치 측량 작업규정개정관련.zip":
        "묶음 파일 — 규정 원문이 아님",
}

# ── 손으로 못박은 짝
#    이름이 규정명과 전혀 겹치지 아니하여 규칙으로는 닿을 수 없다.
PIN = {
    "국외관련규정/일본 공공측량 작업규정의 준칙 4장 UAV 라이다_한글.pdf": "loc28",
    "연구보고서/2025년공공측량.작업규정.개정연구.최종보고서.pdf": "loc31",
}

# ── 별칭
#
#    서고 등재명과 파일명이 다른 것이 있다. 국외 자료는 원어나 약칭으로
#    받았고, 매뉴얼과 보고서는 배포처가 붙인 이름을 그대로 쓴다.
#
#        loc18  USGS 3DEP Lidar Base Specification 2025 rev.A
#               USGS_Lidar_Base_Specification_2025_revA.docx
#
#    조각은 파일명과 폴더 경로 양쪽에 견준다. 판(에디션)을 가르는 자리까지
#    적어야 한다. ASPRS 는 2023년 Ed.2 v1 과 2024년 Ed.2 v2 가 함께 있으므로
#    「Version2」 까지 적어야 v1 이 딸려 오지 아니한다.
ALIAS = {
    # ISO 두 건은 원문을 받을 수 없어 서고 색인을 XML 로 두었다.
    # isoxml.py 가 낸 것이며 등재명과 파일명이 다르므로 번호로 잡는다.
    "loc17": ("ISO17123",),
    "loc29": ("ISO191571", "ISO19157"),
    "loc11": ("作業規程の準則", "일본작업규정의준칙", "일본측량작업규정",
              "일본작업규정"),
    "loc12": ("公共測量の手引",),
    "loc13": ("ASPRSPositionalAccuracyStandardsEdition2Version2",),
    "loc15": ("TransitioningfromRCS2010",),
    "loc18": ("LidarBaseSpecification2025",),
    "loc19": ("측량안전관리매뉴얼",),
    "loc27": ("CadastralSurveyRules2021",),
    "loc30": ("디지털기반지도등간행심사",),
}
# 현행 원문이 아니라 개정안 작업물 — 규정에 붙이지 아니한다
DRAFT_DIRS = ("무인비행장치 측량 작업규정개정관련/2020.무인비행장치 측량 작업규정/",
               "무인비행장치 측량 작업규정개정관련/2025년.연구결과/",
              "무인비행장치 측량 작업규정개정관련/2024년.연구.한글파일/")


def annex_index():
    """규정 자료가 지닌 별표ㆍ별지 목록 → {(구분, 번호, 제목) : (id, 규정명)}

    법령정보센터에서 받아 둔 목록이라 이름이 원본과 같다. 파일 이름만으로는
    임자를 알 수 없는 별표(하위규정\별표서식 에 832건이 뒤섞여 있다)를
    이것으로 맞춘다."""
    import glob
    box = {}
    lib = json.load(io.open(os.path.join(ROOT, "data", "library.json"),
                            encoding="utf-8"))
    nm = {r["id"]: r["name"] for r in lib["regulations"]}
    for p in glob.glob(os.path.join(ROOT, "data", "reg*.json")):
        rid = os.path.splitext(os.path.basename(p))[0]
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for a in (d.get("annex") or []):
            gu = (a.get("gubun") or "별표").strip()
            no = str(a.get("no") or "").strip()
            ti = norm(re.sub(r"\([^)]*관련[^)]*\)\s*$", "", a.get("title") or ""))
            if no and ti:
                box.setdefault((gu, no, ti), (rid, nm.get(rid, rid)))
    return box


RE_ANXNAME = re.compile(
    r"^\s*\[?\s*(별표|별지|부록|서식)\s*([\d의\-]+)\s*(?:호서식)?\s*\]?\s*(.*)$")


def by_annex(fname, aidx):
    """파일 이름의 「[별표 N] 제목」 을 규정의 별표 목록과 맞댄다"""
    m = RE_ANXNAME.match(os.path.splitext(fname)[0])
    if not m:
        return None
    gu, no, ti = m.group(1), m.group(2).strip(), norm(m.group(3))
    if not ti:
        return None
    got = aidx.get((gu, no, ti))
    if got:
        return got[0], got[1], "별표 목록"
    # 제목이 조금 달라도 서로 품으면 같은 것으로 본다
    for (g2, n2, t2), v in aidx.items():
        if g2 == gu and n2 == no and t2 and (t2 in ti or ti in t2):
            return v[0], v[1], "별표 목록(비슷한 제목)"
    return None


def by_hand(rel, table):
    """못박은 짝과 별칭. 규칙보다 먼저 본다.

    별칭은 파일명을 먼저 보고, 거기에 없을 때만 폴더 경로를 본다. 순서를
    지키지 아니하면 폴더 별칭이 파일 별칭을 덮는다. 「일본_작업규정의준칙_2025」
    폴더 안의 「公共測量の手引」 은 준칙(loc11)이 아니라 손안내(loc12)이다.
    """
    nm = {t[0]: t[1] for t in table}
    rid = PIN.get(rel)
    if rid:
        return rid, nm.get(rid, rid), "못박음"
    fname = norm(os.path.splitext(os.path.basename(rel))[0])
    for key, how in ((fname, "별칭(파일명)"), (norm(rel), "별칭(폴더)")):
        best = None
        for rid, frags in ALIAS.items():
            for fr in frags:
                f2 = norm(fr)
                if f2 and f2 in key and (best is None or len(f2) > best[1]):
                    best = (rid, len(f2))
        if best:
            return best[0], nm.get(best[0], best[0]), how
    return None


def pick(key, table, floor):
    """이름 겹침에서 한 규정을 고른다.

    겹치는 방향이 두 가지인데 값이 다르다.

      ㉠ 규정명이 파일명 안에 있다 (t[4] in key)
         「공공측량 작업규정(국토지리정보원고시)…」 처럼 파일이 규정명을
         품은 것으로, 가장 믿을 만하다. 여럿이면 긴 쪽이 옳다 —
         「…법률」과 「…법률 시행령」이 함께 걸리면 시행령이다.

      ㉡ 파일명이 규정명 안에 있다 (key in t[4])
         「공공측량 작업규정.hwpx」 가 「공공측량 작업규정 전부개정을 위한
         전략계획 수립 연구(2025)」 에 들어가는 꼴이다. 이때 긴 쪽을 고르면
         작업규정 파일이 연구보고서로 끌려간다. 여기서는 **짧은 쪽**,
         곧 파일명에 가장 가까운 것이 옳다.

    그러므로 ㉠ 을 먼저 보고, 없을 때만 ㉡ 을 본다.
    """
    if not key:
        return None
    cand = [t for t in table if len(t[4]) >= floor]
    inn = [t for t in cand if t[4] and t[4] in key]
    if inn:
        return max(inn, key=lambda t: len(t[4]))
    out = [t for t in cand if t[4] and key in t[4]]
    if out:
        return min(out, key=lambda t: len(t[4]))
    return None


RE_HEAD = re.compile(r"^\[([^\]]{2,60})\]\s*(?:별표|별지|부록|서식)\s*[\d의\-]+\s")


def match(fname, table):
    """파일 하나 → (규정 id, 규정 이름, 어떻게 찾았나) 또는 None"""
    base = strip_name(fname)
    # ⓪ organize.py 가 정비한 별표는 앞머리 대괄호가 임자 규정이다.
    #    「[공공측량 작업규정] 별표 10 GNSS높이측량 관측기록부.hwpx」
    #    strip_name 이 앞 대괄호를 군더더기로 보고 떼어 버리므로,
    #    떼기 전에 먼저 읽어야 한다.
    m = RE_HEAD.match(os.path.splitext(fname)[0])
    if m:
        got = pick(norm(m.group(1)), table, 0)
        if got:
            return got[0], got[1], "앞머리 규정명"
    # ① 별표ㆍ별지 파일은 끝 괄호에 임자 규정이 적혀 있다
    m = RE_TAIL.search(os.path.splitext(fname)[0])
    if m:
        got = pick(norm(m.group(1)), table, 0)
        if got:
            return got[0], got[1], "괄호 안 규정명"
    # ② 이름끼리 견준다
    key = norm(base)
    if not key:
        return None
    got = pick(key, table, 6)
    if got:
        return got[0], got[1], "이름 겹침"
    # (3) 짧은 규정명은 겹침으로 잡을 수 없다. 「도로법」 은 석 자여서
    #     길이 문턱에 걸리고, 문턱을 낮추면 「수도법」 이 「하수도법」 에
    #     붙는다. 첫 괄호 앞 토막이 규정명과 똑같을 때만 인정한다.
    head = norm(re.split(r"[(\[]", os.path.splitext(fname)[0])[0])
    if head:
        same = [x for x in table if x[4] == head]
        if len(same) == 1:
            return same[0][0], same[0][1], "괄호 앞 이름이 같음"
    return None


def main():
    md = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None
    onlymiss = "--miss" in sys.argv
    table = [(i, n, c, cl, norm(n)) for i, n, c, cl in regs()]

    rows, miss, hold = [], [], []
    files_all = []
    for cur, dirs, files in os.walk(BOX):
        dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
        for f in sorted(files):
            p = os.path.join(cur, f)
            rel = os.path.relpath(p, BOX).replace(os.sep, "/")
            files_all.append((rel, f, os.path.getsize(p)))

    # ① 이름으로 맞는 것, 그다음 별표 목록으로 맞는 것
    aidx = annex_index()
    named, draft, dropped = {}, [], []
    for rel, f, size in files_all:
        if rel in DROP_PAIR:
            dropped.append((rel, DROP_PAIR[rel], size))
            continue
        if any(rel.startswith(x) for x in DRAFT_DIRS):
            draft.append((rel, size))
            continue
        got = by_hand(rel, table) or match(f, table) or by_annex(f, aidx)
        if got:
            rows.append((rel, got[0], got[1], got[2], size))
            named[rel] = got

    # ② 폴더마다 으뜸 규정을 셈한다 — 별표ㆍ별지는 이름에 임자가 없고
    #    폴더가 임자를 알려 준다 (공공측량작업규정\[별지 1] …)
    top = {}
    for rel, (rid, rname, _h) in named.items():
        d = rel.split("/")[0] if "/" in rel else ""
        top.setdefault(d, {}).setdefault((rid, rname), 0)
        top[d][(rid, rname)] += 1
    lead = {}
    for d, box in top.items():
        best = max(box.items(), key=lambda z: z[1])
        share = best[1] / sum(box.values())
        if best[1] >= 2 and share >= 0.5:
            lead[d] = best[0]

    RE_ANX = re.compile(r"^\s*[\[]?\s*(별표|별지|부록|서식)\s*\d")
    aside = set(x[0] for x in draft) | set(x[0] for x in dropped)
    for rel, f, size in files_all:
        # 이미 자리를 정한 것은 다시 세지 아니한다 — 그러지 아니하면
        # 뗀 것과 개정안 작업물이 「못 찾음」 에 겹쳐 들어간다
        if rel in named or rel in aside:
            continue
        d = rel.split("/")[0] if "/" in rel else ""
        if RE_ANX.match(f) and d in lead:
            rid, rname = lead[d]
            hold.append((rel, rid, rname, "폴더로 미룸", size))
        else:
            miss.append((rel, size))

    tot = (len(rows) + len(hold) + len(miss) + len(draft) + len(dropped))
    print("App\\관련규정 의 파일 %d개" % tot)
    print("   규정에 붙은 것 %d · 폴더로 미룬 것 %d · 개정안 작업물 %d"
          % (len(rows), len(hold), len(draft)))
    print("   짝을 뗀 것 %d · 못 찾은 것 %d" % (len(dropped), len(miss)))
    if dropped:
        print()
        print("   짝을 뗀 것 — 사람이 보고 바로잡음")
        for rel, why, _s in dropped:
            print("      %-46s %s" % (rel.split("/")[-1][:46], why))
    print()

    # 폴더별
    by = {}
    for rel, _i, _n, _h, _s in rows:
        d = rel.split("/")[0] if "/" in rel else "(바로 아래)"
        by.setdefault(d, [0, 0, 0])[0] += 1
    for rel, _i, _n, _h, _s in hold:
        d = rel.split("/")[0] if "/" in rel else "(바로 아래)"
        by.setdefault(d, [0, 0, 0])[2] += 1
    for rel, _s in miss:
        d = rel.split("/")[0] if "/" in rel else "(바로 아래)"
        by.setdefault(d, [0, 0, 0])[1] += 1
    print("%-30s %6s %6s %6s" % ("폴더", "이름", "폴더", "못찾음"))
    for d in sorted(by, key=lambda z: -sum(by[z])):
        a, b, c = by[d]
        print("%-30s %6d %6d %6d" % (d[:30], a, c, b))

    # 규정별
    per = {}
    for _rel, rid, rname, _h, _s in rows + hold:
        per.setdefault((rid, rname), 0)
        per[(rid, rname)] += 1
    print()
    print("짝지어진 규정 %d종 · 파일이 많은 차례로" % len(per))
    for (rid, rname), n in sorted(per.items(), key=lambda z: -z[1])[:12]:
        print("   %-7s %-46s %4d개" % (rid, rname[:46], n))

    if onlymiss:
        print()
        print("짝을 못 찾은 파일 %d개" % len(miss))
        for rel, s in miss[:60]:
            print("   %-84s %6dKB" % (rel[:84], s // 1024))
        if len(miss) > 60:
            print("   … 그 밖에 %d개" % (len(miss) - 60))

    if md:
        L = ["# App\\관련규정 파일과 규정의 짝", "",
             "파일 %d개 · 짝지은 것 %d개 · 못 찾은 것 %d개" % (tot, len(rows), len(miss)),
             "", "## 짝지은 것", "",
             "| 파일 | 규정 | id | 어떻게 |", "|---|---|---|---|"]
        for rel, rid, rname, how, _s in rows + hold:
            L.append("| %s | %s | `%s` | %s |" % (rel, rname, rid, how))
        L += ["", "## 짝을 못 찾은 것", "", "| 파일 | 크기 |", "|---|---|"]
        for rel, s in miss:
            L.append("| %s | %dKB |" % (rel, s // 1024))
        io.open(md, "w", encoding="utf-8", newline=NL).write(NL.join(L) + NL)
        print()
        print("표로 적었습니다 — %s" % md)


if __name__ == "__main__":
    main()
