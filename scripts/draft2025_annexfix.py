# -*- coding: utf-8 -*-
"""
별표·별지 정리 — 번호를 다시 매기고, 위임 조문에 그 번호를 넣는다.

  1) 뺄 별표를 가린다. 지금은 하나도 빼지 아니한다 (DROP 이 비어 있다).
     조문은 총칙으로 통합하되 서식은 그대로 둔다 — 통합 조문의 표는 어느 서식을
     쓰는지 가리키는 색인일 뿐, 서식 자체를 갈음하지 아니하기 때문이다.
  2) 별표·별지의 번호를 앞에서부터 다시 매기고, 조문 본문이 가리키는
     번호도 함께 고친다.
  3) '별표에서 정한다' 로만 미뤄 두었던 위임 조문에 그 별표 번호를 넣는다.
  4) 사유가 빈 별표·별지에 개조식 세 도막 사유를 채운다.
"""
import re

# 통합된 조문이 갈음하여 뺄 별표
#   · 성과·점검 서식 → 총칙 「성과패키지」 가 위임한 '성과 유형별 성과패키지의 구성'
#
# 정확도 관리표(현행 별표 3·4·14·16·17·25)는 뺄 것이 아니다.
#   총칙 「정확도 관리」 조문 안의 '측량 유형별 정확도 관리표' 는 어느 서식을 쓰는지
#   가리키는 색인일 뿐, 서식 자체를 갈음하지 아니한다. 그런데도 이것들을 빼 두어,
#   그 표가 없어진 별표를 가리키는 순환이 생겼다(색인은 별표를 가리키고 별표는
#   그 표가 갈음한다고 적힌 꼴). 관리표는 그대로 두고 색인만 번호를 맞춘다.
# 성과·점검 서식(현행 별표 5·6·8·26~31)도 마찬가지다. 「성과 유형별 성과패키지의
# 구성」 표는 그 서식들을 '제출하라' 고 적은 목록이지 서식을 갈음한 것이 아니다.
# 그런데도 빼 두어, 표가 없어진 별표를 가리키는 같은 순환이 생겼다.
DROP_ACC = set()
DROP_PKG = set()
DROP = DROP_ACC | DROP_PKG

WHY_ACC = ("각 편에 흩어져 있던 「정확도 관리」 6개 조문(현행 제10·30·42·73·92·129조)을 "
           "총칙 한 조문으로 합치면서, 측량 유형별로 어느 관리표를 쓰는지를 그 조문 안의 "
           "표 하나로 모았으므로, 유형마다 따로 두던 이 관리표는 뺀다")
WHY_PKG = ("각 편에 흩어져 있던 「성과 등의 정리·관리」 10개 조문(현행 제31·43·59·74·93·"
           "109·119·130·167·191조)을 총칙 「성과패키지」 로 합치면서, 유형별로 무엇을 내는지를 "
           "별표 「성과 유형별 성과패키지의 구성」 하나로 모았으므로, 같은 내용을 나누어 담던 "
           "이 서식은 뺀다")


def drop_why(gubun, no):
    """뺀 별표의 사유 — 간 곳에 따라 달리 적는다"""
    return WHY_ACC if (gubun, no) in DROP_ACC else WHY_PKG

RE_ANX = re.compile(r"(별표|별지)\s*(\d+)")
# 별지 4 → 별지 제4호 서식 (이미 제N호 꼴인 것은 건드리지 아니한다)
RE_FORM = re.compile(r"별지\s*(\d+)\s*(?!호)")

# 사유가 '「조문 제목」 제N항이 위임한 것이다' 꼴이 아닌 별표 — 위임 자리를 손으로 짚는다
#   {별표 제목: [(조문 제목, 항 번호), …]}
HINT = {
    "안전관리비 계상 요율": [("안전관리비의 계상", 3), ("안전관리비의 계상", 4)],
    "성과 유형별 성과패키지의 구성": [("성과패키지", 4)],
    "공공기준점 점의 조서": [("공공기준점 표지의 설치", 1)],
    "안전관리비 사용내역서": [("안전관리비의 사용 및 정산", 5)],
}

HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
# 번호가 빠진 채 별표를 가리키는 문형
RE_BARE = re.compile(r"(?<!\d)(별표|별지)(?=\s*(?:에서|에|의|를|와|과|로)\b|\s*[에의])")


def find_deleg(src):
    """사유에서 '「조문 제목」 제N항이 위임' 을 모두 찾는다"""
    return [(m.group(1).strip(), int(m.group(2)))
            for m in re.finditer(r"[「『]([^」』]{2,40})[」』]\s*제(\d+)항이 위임", src)]


def put_no(art, gubun, no, hang):
    """그 조문의 지정한 항에서 번호 없는 '별표' 에 번호를 넣는다"""
    body = art.get("body") or ""
    lines = body.split("\n")
    mark = HANG[hang - 1] if 1 <= hang <= len(HANG) else None
    hit = 0
    for i, ln in enumerate(lines):
        if mark and not ln.startswith(mark):
            continue
        new, cnt = RE_BARE.subn(lambda m: f"{m.group(1)} {no}", ln)
        if cnt:
            lines[i] = new
            hit += cnt
        if mark:
            break
    if not hit:
        return False
    art["body"] = "\n".join(lines)
    return True


def key_of(node):
    m = RE_ANX.search(str(node.get("legacyNo") or ""))
    return (m.group(1), int(m.group(2))) if m else None


def collect(tree):
    """(별표 묶음, 조문) 목록"""
    groups, arts = [], []

    def rec(ns):
        for x in ns:
            if x.get("isAnnex"):
                groups.append(x)
            elif x.get("level") == "조" and not x.get("annexRef"):
                arts.append(x)
            rec(x.get("children") or [])
    rec(tree)
    return groups, arts


def run(tree, reason_of, RSN):
    groups, arts = collect(tree)
    dropped, remap = [], {}

    # 1) 갈음된 별표를 뺀다 (지금은 뺄 것이 없다)
    for g in groups:
        keep = []
        for k in g.get("children") or []:
            if key_of(k) in DROP:
                dropped.append((key_of(k), k.get("title")))
                continue
            keep.append(k)
        g["children"] = keep

    # 2) 번호를 다시 매긴다
    seq = {}
    for g in groups:
        for k in g.get("children") or []:
            old = key_of(k)
            if not old:
                continue
            gubun = old[0]
            seq[gubun] = seq.get(gubun, 0) + 1
            new = seq[gubun]
            remap[old] = (gubun, new)
            k["legacyNo"] = f"{gubun} {new}"
            if k.get("annexRef"):
                k["annexRef"]["no"] = str(new)
        if g.get("children"):
            gubun = key_of(g["children"][0])[0]
            g["title"] = f"{gubun} ({len(g['children'])}건)"

    # 조문 본문이 가리키는 번호도 함께 고친다
    n_ref = 0
    for a in arts:
        def one(m):
            nonlocal n_ref
            got = remap.get((m.group(1), int(m.group(2))))
            if not got or got == (m.group(1), int(m.group(2))):
                return m.group(0)
            n_ref += 1
            return f"{got[0]} {got[1]}"
        a["body"] = RE_ANX.sub(one, a.get("body") or "")

    # 3) 위임 조문에 번호를 넣는다 — 별표의 사유에 적힌 「조문 제목」 제N항을 실마리로
    by_title = {}
    for a in arts:
        by_title.setdefault((a.get("title") or "").strip(), a)
    n_deleg = 0
    for g in groups:
        for k in g.get("children") or []:
            gubun, no = key_of(k) or ("별표", 0)
            R0 = k.get("_R")
            src = " ".join([k.get("reason") or ""]
                           + (list(getattr(R0, "base", [])) + list(getattr(R0, "why", []))
                              if R0 is not None else []))
            for title, hang in (HINT.get((k.get("title") or "").strip())
                                or find_deleg(src)):
                art = by_title.get(title)
                if art and put_no(art, gubun, no, hang):
                    n_deleg += 1

    # 4) 사유가 빈 별표·별지를 채운다
    n_reason = 0
    for g in groups:
        for k in g.get("children") or []:
            if (k.get("reason") or "").strip() or k.get("_R"):
                continue
            R = reason_of(k)
            R.now(f"{k.get('legacyNo')}({k.get('title') or ''})")
            R.basis("현행 별표·별지를 그대로 둔다 — 따로 든 근거 없음")
            R.cause("서식을 고치지 아니하고 그대로 옮긴다",
                    "앞의 별표를 빼면서 번호만 앞으로 당겨 매긴다"
                    if dropped else "번호도 그대로 둔다")
            n_reason += 1

    # 5) 별지를 가리키는 표기를 현행 규정과 같은 꼴로 맞춘다
    #    현행 규정은 '별지 제1호 서식' 으로 적는데, 새로 지은 조문에는 '별지 4' 처럼
    #    적힌 곳이 있어 한 규정 안에서 표기가 엇갈렸다. 별표는 '별표 31' 그대로 둔다.
    n_form = [0]

    def _fix_form(ns):
        for x in ns:
            b = x.get("body") or ""
            if "별지" in b:
                new_b, cnt = RE_FORM.subn(lambda m: f"별지 제{m.group(1)}호 서식", b)
                if cnt:
                    x["body"] = new_b
                    n_form[0] += cnt
            _fix_form(x.get("children") or [])
    _fix_form(tree)

    return {"dropped": dropped, "ref": n_ref, "deleg": n_deleg,
            "reason": n_reason, "form": n_form[0]}
