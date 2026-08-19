# -*- coding: utf-8 -*-
"""
조문마다 '개정 내용' 을 짓는다 — 무엇이 어떻게 되었는지.

손으로 쓴 사유가 없는 조문은 그 처지에 맞는 한 줄로만 채워 두었더니
('본문은 그대로 두고 조문의 자리만 옮긴다') 어느 조문이나 같은 말이 되어
읽을 값어치가 없었다. 현행 조문과 실제로 견주어 조문마다 다른 글을 짓는다.

  · 번호가 어떻게 바뀌었는가        제29조 → 제42조
  · 자리가 어떻게 바뀌었는가        제2편 제2장 → 제2편 「공공삼각점측량」 장
  · 본문이 바뀌었는가, 어느 항이     제6항·제10항의 문언을 고친다
  · 새 조문이면 무엇으로 짜였는가    4개 항 12개 호로 정하고 별표 33에 위임한다

번호를 다시 매기면서 본문의 '제○조' 인용이 바뀐 것은 내용이 바뀐 것으로 보지
아니한다. 그 자리는 이미 따로 사유를 적는다.
"""
import re

import draft2025_defs as DEFS

RE_MARK = re.compile(r"^\s*[①-⑳]")
RE_HO = re.compile(r"^\s*\d+\.\s")
RE_ANNEX = re.compile(r"(별표|별지)\s*(\d+)")
HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _norm(s):
    """견주기 위한 꼴 — 출처 표시와 조 번호, 띄어쓰기는 셈에 넣지 아니한다"""
    s = re.sub(r"<현행[^<>]*>", "", str(s or ""))
    s = re.sub(r"제\s*\d+\s*조", "제○조", s)
    return re.sub(r"\s+", "", s)


def _changed(now, was):
    """바뀐 항의 번호 목록 — 항의 수가 다르면 None(항 단위로 견줄 수 없다)"""
    a = [_norm(p) for p in DEFS.paras(now)]
    b = [_norm(p) for p in DEFS.paras(was)]
    if not a or not b:
        return None
    if len(a) != len(b):
        return None
    return [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]


def _hang_label(nums):
    return "·".join(f"제{n}항" for n in nums)


def _shape(body):
    """조문이 몇 개 항과 호로 짜였는가"""
    lines = str(body or "").split("\n")
    hang = sum(1 for l in lines if RE_MARK.match(l))
    ho = sum(1 for l in lines if RE_HO.match(l))
    bits = []
    if hang:
        bits.append(f"{hang}개 항")
    if ho:
        bits.append(f"{ho}개 호")
    return " ".join(bits)


def _annexes(body):
    """이 조문이 위임한 별표·별지"""
    seen, out = set(), []
    for g, n in RE_ANNEX.findall(str(body or "")):
        k = f"{g} {n}"
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def what_of(node, was, old_where, new_where, obj_fixed=False):
    """개정 내용 줄들 — was 는 현행 조문(없으면 None)

    obj_fixed 는 본문에 딸린 표·수식을 고친 조문이다. 글은 그대로여도
    내용이 바뀐 것이므로 '현행과 같다' 고 적어서는 아니 된다.
    """
    st = str(node.get("status") or "")
    body = node.get("body") or ""
    new_no = node.get("no")
    out = []

    if st == "신설":
        shape = _shape(body)
        line = "현행 규정에 없던 사항을 제%s조로 새로 정한다" % new_no
        if shape:
            line += f" — {shape}으로 짠다"
        out.append(line)
        anx = _annexes(body)
        if anx:
            out.append("세부 기준은 " + "·".join(anx) + "에 위임한다")
        return out

    if not was:
        return []

    m = re.match(r"제(\d+)조", str(node.get("legacyNo") or ""))
    old_no = int(m.group(1)) if m else None

    # 1) 번호
    if old_no and old_no != new_no:
        out.append(f"앞의 조문이 통합·삭제되고 새 조문이 들어옴에 따라 "
                   f"현행 제{old_no}조가 제{new_no}조가 된다")
    elif old_no:
        out.append(f"조 번호는 제{new_no}조로 현행과 같다")

    # 2) 자리
    if st.startswith("이동") and old_where and new_where and old_where != new_where:
        out.append(f"{old_where}에 있던 것을 {new_where}으로 옮긴다")

    # 3) 본문
    diff = _changed(body, was.get("body") or "")
    same_title = (node.get("title") or "") == (was.get("title") or "")
    if diff is None:
        # 항의 수가 달라졌다 — 항을 더하거나 뺐다
        a, b = len(DEFS.paras(body)), len(DEFS.paras(was.get("body") or ""))
        if a != b:
            out.append(f"항의 수가 {b}개에서 {a}개로 바뀐다")
        elif _norm(body) != _norm(was.get("body") or ""):
            out.append("본문의 문언을 고친다")
        elif obj_fixed:
            out.append("글은 현행과 같고, 본문에 딸린 표를 고친다")
        else:
            out.append("본문은 현행과 같다")
    elif diff:
        out.append(f"{_hang_label(diff)}의 문언을 고치고, 나머지 항은 현행과 같다")
    elif obj_fixed:
        out.append("글은 현행과 같고, 본문에 딸린 표를 고친다")
    else:
        out.append("본문은 현행과 같다")

    if not same_title:
        out.append(f"제목을 「{was.get('title')}」 에서 「{node.get('title')}」 으로 고친다")

    return out


def why_kept(node, old_no):
    """'유지' 조문의 개정 사유 — 왜 그대로 두는가"""
    if old_no and old_no != node.get("no"):
        return (f"현행 조문에 고칠 것이 없어 문언을 그대로 둔다. 다만 앞의 조문이 "
                f"통합·삭제되어 조 번호가 제{old_no}조에서 제{node.get('no')}조로 바뀐다")
    return "현행 조문에 고칠 것이 없어 편제와 문언을 그대로 둔다"


def why_moved(old_part, new_part, old_chap, new_chap, old_where, new_where):
    """'이동' 조문의 개정 사유 — 왜 그 자리로 옮기는가

    같은 문장을 백 곳에 되풀이하지 아니하고, 옮긴 갈래를 가려 적는다.
      · 편 번호만 밀림  편과 장의 이름은 현행 그대로여서
      · 총칙으로 올림   여러 편에 두루 미치는 사항이어서
      · 다른 편으로     규율 대상이 그 편의 것이어서
      · 같은 편 안에서  공정 차례에 맞추어 장을 옮겨서
    """
    op, np_ = (old_part or "").strip(), (new_part or "").strip()
    oc, nc = (old_chap or "").strip(), (new_chap or "").strip()

    # 편도 장도 이름이 같다 — 앞에 편이 늘어 편 번호만 밀린 것이지 자리를 옮긴 것이 아니다
    if op and op == np_ and oc == nc:
        m1 = re.match(r"(제\d+편)", str(old_where or ""))
        m2 = re.match(r"(제\d+편)", str(new_where or ""))
        move = (f"{m1.group(1)}에서 {m2.group(1)}으로" if m1 and m2 else "")
        return (f"이 조문이 놓인 편과 장은 「{np_}」 편 「{nc}」 장으로 현행과 같다. "
                f"앞에 편이 늘어 편 번호가 {move} 밀린 데 따른 것이다".replace("  ", " ")
                if move else
                f"이 조문이 놓인 편과 장은 「{np_}」 편 「{nc}」 장으로 현행과 같고, "
                f"앞에 편이 늘어 편 번호만 밀린다")

    if np_ == "총칙" and op != "총칙":
        return (f"측량의 종류를 가리지 아니하고 두루 미치는 사항이므로, 「{op}」 편에 묻어 두지 "
                f"아니하고 총칙 「{nc}」 장으로 올린다")
    if np_ == "보칙":
        return (f"규정의 시행과 관리에 관한 사항이므로 「{op}」 편에서 보칙으로 옮긴다")
    if op and np_ and op != np_:
        return (f"이 조문이 규율하는 것은 「{np_}」 에 관한 것이므로, 현행 「{op}」 편에서 "
                f"「{np_}」 편 「{nc}」 장으로 옮긴다")
    if nc and oc != nc:
        return (f"같은 편 안에서 공정의 차례에 맞추어 「{nc}」 장으로 옮긴다")
    return (f"규율 성격이 같은 조문끼리 모으기 위하여 {new_where}으로 편제를 옮긴다"
            if new_where else "편·장을 다시 나누면서 자리를 옮긴다")


def what_annex(node):
    """별표·별지의 개정 내용 — 번호가 어떻게 바뀌는가"""
    a = node.get("annexRef") or {}
    g, no = a.get("gubun") or "별표", a.get("no")
    st = str(node.get("status") or "")
    if st == "신설":
        return [f"현행 규정에 없던 서식을 {g} {no}으로 새로 정한다"]
    m = re.match(r"(별표|별지)\s*(\d+)", str(node.get("legacyNo") or ""))
    if not m:
        return []
    was_g, was_no = m.group(1), m.group(2)
    out = []
    if was_g != g or str(was_no) != str(no):
        out.append(f"갈음되어 뺀 서식이 있어 현행 {was_g} {was_no}이 {g} {no}이 된다")
    else:
        out.append(f"{g} 번호는 {no}으로 현행과 같다")
    out.append("서식은 현행의 것을 그대로 쓴다" if st in ("유지", "이동")
               else "서식의 내용을 고친다")
    return out


def what_group(node):
    """편·장 머리의 개정 내용 — 이 아래에 무엇을 몇 개 두는가"""
    kinds = {}
    olds = []

    # 별표·별지 묶음 머리는 딸린 서식을 센다
    anx = [x for x in (node.get("children") or []) if x.get("annexRef")]
    if anx:
        g = (anx[0].get("annexRef") or {}).get("gubun") or "별표"
        by = {}
        for x in anx:
            by[x.get("status") or "유지"] = by.get(x.get("status") or "유지", 0) + 1
        order = ["유지", "이동", "이동·수정", "수정", "신설"]
        bits = [f"{k} {by[k]}건" for k in order if by.get(k)]
        out = [f"{g} {len(anx)}건을 둔다 — " + " · ".join(bits)]
        if by.get("신설"):
            out.append(f"신설 {by['신설']}건은 조문이 위임했으나 서식이 없던 것이다")
        return out

    def rec(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef") and not x.get("isDeleted"):
                kinds[x.get("status") or "유지"] = kinds.get(x.get("status") or "유지", 0) + 1
                m = re.match(r"제(\d+)조", str(x.get("legacyNo") or ""))
                if m:
                    olds.append(int(m.group(1)))
            rec(x.get("children") or [])

    rec(node.get("children") or [])
    total = sum(kinds.values())
    if not total:
        return []
    order = ["유지", "이동", "이동·수정", "수정", "신설", "통합"]
    bits = [f"{k} {kinds[k]}개" for k in order if kinds.get(k)]
    out = [f"이 {node.get('level')}에 조문 {total}개를 둔다 — " + " · ".join(bits)]
    if olds:
        out.append(f"현행 제{min(olds)}조부터 제{max(olds)}조까지에서 "
                   f"{len(olds)}개를 가져온다")
    return out
