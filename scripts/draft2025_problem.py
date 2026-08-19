# -*- coding: utf-8 -*-
"""
'현행의 문제' 를 짓는다 — 왜 지금 고쳐야 하는가.

공청회에서 설득해야 할 상대는 시행자·수행자·심사기관이다. 그들에게는
'무엇을 어떻게 바꾸었는가'(개정 내용)보다 '고치지 아니하면 무엇이 잘못되는가'
가 먼저다. 그런데 사유가 개편 작업의 절차만 적고 있어 그 대목이 비어 있었다.

세 갈래로 짓는다.
  1) 연구 검토(부록 4)가 짚은 조문 — 그 지적을 문제로 적고, 유형별로 현장에
     무엇이 생기는지와 시급성을 덧붙인다. 유형별 영향은 보고서의 문제 유형표를
     그대로 따른다.
  2) 통합·삭제한 조문 — 같은 내용을 여러 곳에 되풀이 적어 서로 어긋난 사실을
     현행 조문에서 직접 세어 적는다. 말이 아니라 숫자로 보인다.
  3) 자리만 옮긴 조문 — 고칠 것이 없다고 분명히 적는다. 공청회에서 다툴 것이
     아닌 것을 다툴 거리로 만들지 아니한다.
"""
import re

# 보고서 「문제 유형별 현장 영향과 개정 시급성」 표 — 유형: (현장에 생기는 일, 시급성)
TYPE_HARM = {
    "A": ("상위 법령과 어긋나 법적 분쟁과 행정처분의 불안정을 낳는다", "매우 높음"),
    "B": ("규정이 특정 기술에 묶여 있어 새 장비를 쓰면 규정 위반인지 다투게 되고, "
          "기술 도입이 막힌다", "높음"),
    "C": ("용어가 어긋나 장비 검수에서 혼선이 생기고, 행정 마찰과 자료 처리 오류를 부른다",
          "높음"),
    "D": ("판정 기준이 서술마다 달라 심사자에 따라 결과가 갈리고 재량이 넓어진다", "높음"),
    "E": ("같은 사항이 여러 곳에 흩어지거나 빠져 있어 품질 분쟁과 성과 반려가 생기고, "
          "안전 사각지대가 남는다", "매우 높음"),
    "F": ("새 기술을 다룰 조문이 없어 기술 도입에 제도적 장벽이 되고, "
          "성과심사가 일관되지 못하다", "매우 높음"),
}


def harm_line(code_type):
    """유형 지적에 덧붙일 '현장에 무엇이 생기는가' 한 줄"""
    got = TYPE_HARM.get(str(code_type or "").upper())
    if not got:
        return ""
    harm, urg = got
    return f"이대로 두면 {harm}. 연구가 매긴 개정 시급성은 '{urg}' 이다"


# ───────────────────── 통합 대상 조문의 어긋남을 센다 ─────────────────────
RE_HO = re.compile(r"(?:^|\n)\s*\d+\.\s*([^\n]+)")
RE_IMG = re.compile(r"<img[^>]*>")
# 호 표시 — 줄머리의 것과 글 가운데 이어 붙은 것을 함께 잡는다
RE_HO_ANY = re.compile(r"(?:(?<=^)|(?<=[^\d]))(\d{1,2})\.\s*")


def _head(body):
    """무엇을 하라는 머리 문장 — 각 호를 뗀 부분"""
    s = re.sub(r"^[①-⑳]\s*", "", RE_IMG.sub("", str(body or "")).strip())
    s = s.split("\n")[0]
    m = RE_HO_ANY.search(s)
    if m:
        s = s[:m.start()]
    return re.sub(r"\s+", " ", s).strip(" .")


def _items(body):
    """각 호가 무엇을 내라고 하는지 — 괄호 안의 별표 번호는 떼고 견준다

    현행 원문은 '1. 성과표 (별표 5)2. 수치데이터3. 망도' 처럼 호가 줄바꿈 없이
    이어 붙은 곳이 많다. 줄머리만 보면 첫 호밖에 세지 못하므로 글 가운데의
    호 표시도 함께 잡는다.
    """
    parts = RE_HO_ANY.split(RE_IMG.sub("", str(body or "")))
    out = []
    for i in range(2, len(parts), 2):          # [머리, 번호, 내용, 번호, 내용, …]
        it = re.sub(r"\s*\([^)]*\)\s*", " ", parts[i])
        it = re.split(r"[①-⑳]", it)[0]        # 다음 항으로 넘어가는 꼬리를 자른다
        it = re.sub(r"\s+", " ", it).strip(" .,·")
        if it:
            out.append(it)
    return out


def divergence(arts, what):
    """같은 일을 하는 현행 조문들이 실제로 얼마나 어긋나는지 — 사실만 적는다

    arts = [(조번호, 제목, 본문)]
    """
    if len(arts) < 2:
        return []

    titles = {}
    for no, ti, _b in arts:
        titles.setdefault((ti or "").strip(), []).append(no)
    heads = {_head(b) for _no, _t, b in arts}
    lens = [len(re.sub(r"\s+", "", RE_IMG.sub("", b or ""))) for _n, _t, b in arts]

    out = [f"같은 일을 정하는 조문이 각 편에 {len(arts)}개 흩어져 있고, "
           f"그 내용이 서로 어긋난다"]

    if len(titles) > 1:
        li = " · ".join(
            f"「{t}」 {len(ns)}개(제" + "조·제".join(str(x) for x in ns) + "조)"
            for t, ns in sorted(titles.items(), key=lambda kv: -len(kv[1])))
        out.append(f"조문 제목부터 갈린다 — {li}")

    if len(heads) > 1:
        out.append(f"무엇을 하라는 문두가 {len(heads)}가지로 제각각이어서, "
                   f"같은 의무인지 다른 의무인지 읽는 사람마다 달리 본다")

    # 무엇을 내라고 하는지 — 글로 적은 조문끼리만 견준다.
    # 목록을 표로 둔 조문은 글에서 셀 수 없으므로 함께 세면 '모두에 있는 항목 0가지'
    # 같은 잘못된 셈이 된다. 적는 방식이 갈리는 것 자체를 따로 적는다.
    listed = [(no, _items(b)) for no, _t, b in arts]
    with_text = [(no, its) for no, its in listed if its]
    as_table = [no for no, its in listed if not its]
    if as_table and with_text:
        out.append(f"적는 방식조차 갈린다 — {len(with_text)}개 조문은 각 호로 적고, "
                   f"{len(as_table)}개 조문(제"
                   + "조·제".join(str(x) for x in as_table)
                   + "조)은 표로 적어 무엇이 같고 다른지 견주기 어렵다")

    seen = {}
    for no, its in with_text:
        for it in its:
            seen.setdefault(it, set()).add(no)
    if seen and len(with_text) >= 2:
        only = [it for it, ns in seen.items() if len(ns) == 1]
        common = [it for it, ns in seen.items() if len(ns) == len(with_text)]
        out.append(f"각 호로 적은 {len(with_text)}개 조문만 견주어도 제출하라는 항목이 "
                   f"모두 {len(seen)}가지인데, 그 가운데 {len(common)}가지만 그 조문 "
                   f"모두에 함께 있고 {len(only)}가지는 어느 한 조문에만 있다")

    if lens and max(lens) >= 2 * max(1, min(lens)) and not as_table:
        out.append(f"분량도 {min(lens)}자에서 {max(lens)}자까지 벌어져, "
                   f"어느 측량이냐에 따라 요구 수준이 달라진다")

    out.append(f"수행자는 편마다 다른 조문을 찾아 읽어야 하고, 한 곳을 고치면 "
               f"나머지 {len(arts) - 1}곳이 어긋난다. {what}")
    return out


# ───────────────────── 고칠 것이 없는 조문 ─────────────────────
def none_line(kind="이동"):
    if kind == "번호":
        return ("이 조문 자체에는 고칠 것이 없다. 앞의 편이 늘어 번호만 밀리는 것이므로 "
                "실질적인 개정 사항이 아니다")
    if kind == "유지":
        return "이 조문에는 연구 검토와 검토의견에서 지적된 것이 없다"
    return ("이 조문의 내용에는 고칠 것이 없고, 규정 전체의 편제를 다시 나누는 데 따라 "
            "자리만 옮긴다")


# ───────────────────── 편·장 단위의 문제 ─────────────────────
# 유형 이름에 띄어쓰기가 있어 느슨한 패턴으로는 '법령' 처럼 잘린다.
# 아는 이름으로만 센다.
TYPE_NAMES = ["법령 불일치", "기술 진부화", "용어 오류·불일치",
              "서술 방식 불일치", "중복·누락·불명확", "신기술 규정 공백"]
RE_FOUND = re.compile("연구 검토 결과 (" + "|".join(TYPE_NAMES) + ")")


def group_line(node):
    """편·장 머리의 '현행의 문제' — 이 아래 조문에 걸린 연구 지적을 셈한다

    공청회에서 편 단위로 설명할 때, 이 편에 무엇이 몇 건 걸려 있는지가
    먼저 필요하다. 조문마다 흩어진 지적을 여기서 한 번에 보인다.
    """
    # 별표·별지 묶음은 편이 아니다 — 조문 수를 세어 '이 편에 둘 조문' 이라 적으면
    # 없는 말이 된다. 서식이 모자란다는 사실을 적는다.
    anx = [x for x in (node.get("children") or []) if x.get("annexRef")]
    if anx:
        g = (anx[0].get("annexRef") or {}).get("gubun") or "별표"
        new_n = sum(1 for x in anx if (x.get("status") or "") == "신설")
        if not new_n:
            return [f"현행 {g}에 모자란 것이 없다"]
        return [f"조문이 서식으로 정하도록 위임하였는데 그 서식이 없는 것이 {new_n}건 "
                f"있어, 무엇을 어떤 꼴로 내야 하는지 정해진 바가 없다",
                "서식이 없으면 발주처마다 요구가 달라지고, 심사에서도 같은 잣대로 "
                "볼 수 없다"]

    kinds, jo = {}, 0

    def rec(ns):
        nonlocal jo
        for x in ns:
            if x.get("level") == "조" and not x.get("isDeleted"):
                jo += 1
                R = x.get("_R")
                text = " ".join(list(getattr(R, "prob", []) or [])
                                + list(getattr(R, "base", []) or [])) if R else ""
                for m in RE_FOUND.finditer(text):
                    kinds[m.group(1)] = kinds.get(m.group(1), 0) + 1
            rec(x.get("children") or [])

    rec(node.get("children") or [])
    if not kinds:
        return [f"이 {node.get('level')}의 조문에는 연구 검토에서 지적된 것이 없다"]
    tot = sum(kinds.values())
    li = " · ".join(f"{k} {v}건" for k, v in
                    sorted(kinds.items(), key=lambda kv: -kv[1]))
    urg = {k for k in kinds if k in ("법령 불일치", "중복·누락·불명확", "신기술 규정 공백")}
    out = [f"이 {node.get('level')}에 둘 조문 {jo}개 가운데 {tot}건이 연구 검토에서 "
           f"고쳐야 할 것으로 지적되었다 — {li}"]
    if urg:
        out.append("그 가운데 " + "·".join(sorted(urg))
                   + " 은 연구가 개정 시급성을 '매우 높음' 으로 매긴 유형이다")
    return out
