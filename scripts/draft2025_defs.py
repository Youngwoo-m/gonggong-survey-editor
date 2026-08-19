# -*- coding: utf-8 -*-
"""
흩어져 있는 용어 정의를 총칙 제2조(정의)로 모은다.

두 갈래로 나누어 거둔다.
  A) 제목이 '정의' 인 조문 — 조문 전체가 정의이므로 통째로 흡수하고 그 조문은 없앤다.
  B) 그 밖의 조문 — 항(項) 가운데 '"○○"이란 …을 말한다.' 하나로 끝나는 항만 떼어 온다.
     규율이 섞인 항, '(이하 "○○"이라 한다)' 꼴의 약칭은 건드리지 아니한다.

떼어 내고 남은 항은 번호를 다시 매기고, 남는 것이 없으면 그 조문은 없앤다.
거둔 정의는 그 정의가 있던 현행 조문의 차례로 붙이고, 어느 조문에서 왔는지 함께 적는다.
"""
import re

MARK = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
# '(이하 "○○"라 한다)' 같은 약칭 — 정의로 보지 아니한다
ALIAS = re.compile(r'\((?:이하\s*)?["“][^"”]{1,40}["”](?:이)?(?:라|라고)\s*(?:한다|하며|하고)[^)]*\)')
# '"○○"이란 … 말한다.' 하나로 끝나는 항
PURE = re.compile(r'^["“]([^"”]{1,40})["”]\s*'
                  r'(?:이란|란|이라 함은|라 함은|이라 함이란|은|는|이)\s*'
                  r'.*?(?:말한다|가리킨다|한다)\.?$', re.S)
TERM = re.compile(r'^["“]([^"”]{1,40})["”]')
# 정의 조문의 각 호 — '1. "○○"이란 …'
HO = re.compile(r'^\s*(\d+)\.\s*(.+)$')


def paras(body):
    """항(項) 단위로 자른다. 항 표시가 없으면 통째로 한 덩이."""
    body = (body or "").strip()
    if not body:
        return []
    if body[0] not in MARK:
        return [body]
    out, cur = [], ""
    for ch in body:
        if ch in MARK and cur.strip():
            out.append(cur.strip())
            cur = ch
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def strip_mark(p):
    return re.sub(r"^[①-⑳]\s*", "", p).strip()


def renumber(ps):
    """남은 항에 번호를 다시 매긴다"""
    if len(ps) == 1:
        return strip_mark(ps[0])
    return "\n".join(f"{MARK[i]} {strip_mark(p)}" for i, p in enumerate(ps))


def is_def_article(title):
    t = (title or "").strip()
    return t == "정의" or t.endswith("의 정의") or t == "용어의 정의"


HANG = re.compile(r"제\s*(\d+)\s*항")
JO_HANG = re.compile(r"제\s*\d+\s*조\s*제\s*\d+\s*항")


def _renumber_refs(text, dropped):
    """
    정의 항을 뗀 뒤 남은 항의 '제N항' 참조를 다시 매긴다.
    dropped = 떼어 낸 항의 번호(1부터) 집합.
    떼어 낸 항 자체를 가리키는 참조가 있으면 None 을 돌려준다.
    """
    broken = [False]

    def fix(m):
        # '제210조제3항' 처럼 다른 조의 항을 가리키는 것은 건드리지 아니한다
        pre = text[max(0, m.start() - 14):m.start()]
        if re.search(r"제\s*\d+\s*조\s*$", pre):
            return m.group(0)      # 다른 조의 항이다
        n = int(m.group(1))
        if n in dropped:
            broken[0] = True
            return m.group(0)
        return f"제{n - sum(1 for d in dropped if d < n)}항"

    out = HANG.sub(fix, text)
    return None if broken[0] else out


def pick(body, renum=False):
    """(거둔 정의 문장들, 남은 본문) — B 갈래. renum 이면 항 참조를 다시 매긴다."""
    got, left, dropped = [], [], set()
    for i, p in enumerate(paras(body), start=1):
        t = strip_mark(p)
        bare = ALIAS.sub("", t).strip()
        # 각 호가 딸린 항은 규율이 섞인 것으로 본다
        if re.search(r"\n\s*\d+\.", bare) or "다음 각 호" in bare:
            left.append(p)
            continue
        # '(이하 "TS"라 한다)' 같은 약칭이 문장 안에 있어도 그 항은 정의다.
        # 약칭을 뺀 문장으로 판정하고, 옮길 때에는 원문 그대로 옮긴다.
        if PURE.match(bare):
            got.append(t)
            dropped.add(i)
        else:
            left.append(p)

    if renum and got and left and dropped:
        fixed = []
        for p in left:
            r = _renumber_refs(p, dropped)
            if r is None:
                return None, None
            fixed.append(r)
        left = fixed
    return got, left


# 한 줄 안에서 다음 호가 시작하는 자리 — '…부속설비2. "지하시설물측량"이란'
RE_HO_INLINE = re.compile(r'(?<=[^\d\s])\s*\d{1,2}\.\s*(?=["“])')


def split_ho(body):
    """정의 조문의 각 호를 문장 목록으로 — A 갈래

    원문에는 호가 줄바꿈 없이 이어 붙은 곳이 있다. 줄만 보고 자르면 두 정의가
    한 호에 묶이고 그 안에 옛 호 번호가 그대로 남는다. 줄 안에서 다음 호가
    시작하는 자리도 함께 자른다.
    """
    out = []
    for line in (body or "").split("\n"):
        m = HO.match(line)
        if m:
            out.append(m.group(2).strip())
        elif out and line.strip() and not re.match(r"^\s*[①-⑳]", line):
            out[-1] += " " + line.strip()

    split = []
    for s in out:
        split += [x.strip() for x in RE_HO_INLINE.split(s) if x.strip()]
    return split


def term_of(sent):
    m = TERM.match(sent.strip())
    return m.group(1) if m else ""


def collect(tree, keep_titles=(), skip_ids=(), cur_titles=None):
    """
    tree 를 훑어 정의를 거두고 본문을 고친다.
    반환: [(term, sentence, 출처label)] · 없앤 조문 [(label, title)] · {용어: 나온 편}
    """
    got, dropped, part_of = [], [], {}

    def label_of(n, part, chap):
        no = n.get("legacyNo")
        if no:
            # 제목은 현행 규정의 것을 적는다 — 개편안에서 고친 제목을 적으면
            # '현행 제199조 「네트워크 RTK 측량의 선점」' 처럼 있지도 않은 짝이 된다
            was = (cur_titles or {}).get(no) or n["title"]
            return f"현행 {no} 「{was}」"
        where = " ".join(x for x in (part, chap) if x)
        return f"신설 {where} 「{n['title']}」"

    def walk(ns, part, chap):
        keep = []
        for x in ns:
            lv = x.get("level")
            if lv == "편":
                walk(x.get("children") or [], x["title"], "")
                keep.append(x)
                continue
            if lv == "장":
                walk(x.get("children") or [], part, x["title"])
                keep.append(x)
                continue
            if (lv != "조" or x.get("annexRef") or x["title"] in keep_titles
                    or x.get("id") in skip_ids or x.get("legacyNo") == "제2조"):
                keep.append(x)
                continue

            body = x.get("body") or ""
            if is_def_article(x["title"]):
                sents = split_ho(body)
                if not sents:            # 각 호가 아니라 항으로 늘어놓은 정의 조문
                    sents = [strip_mark(p) for p in paras(body)]
                # 용어를 정하지 아니한 호(적용례 등)는 옮기지 아니하고 그 자리에 남긴다
                defs = [s for s in sents if term_of(s)]
                rest = [s for s in sents if not term_of(s)]
                if defs:
                    lb = label_of(x, part, chap)
                    for s in defs:
                        got.append((term_of(s), s, lb))
                        part_of.setdefault(term_of(s), part)
                    if rest:
                        if len(rest) == 1:
                            x["body"] = rest[0]      # 한 호만 남으면 문장으로 편다
                        else:
                            head = (body.split("\n") or [""])[0]
                            x["body"] = "\n".join(
                                [head] + [f"{i}. {s}" for i, s in enumerate(rest, start=1)])
                        # 정의가 하나도 남지 않았으므로 제목도 남은 내용에 맞춘다
                        x["title"] = ("다른 규정의 적용"
                                      if "적용한다" in x["body"] else "그 밖의 사항")
                        add = ("용어 정의는 「정의」 조문으로 옮기고, 용어를 정하지 아니한 "
                               f"호만 남겨 제목을 「{x['title']}」 으로 고쳤다.")
                        x["reason"] = f"{x.get('reason') or ''} / {add}".strip(" /")
                        keep.append(x)
                    else:
                        dropped.append((lb, x["title"]))
                    continue
                keep.append(x)
                continue

            picked, left = pick(body, renum=True)
            if picked is None:            # 떼면 항 참조가 깨지는 조문은 그대로 둔다
                keep.append(x)
                continue
            if picked:
                lb = label_of(x, part, chap)
                for s in picked:
                    got.append((term_of(s), s, lb))
                    part_of.setdefault(term_of(s), part)
                if left:
                    x["body"] = renumber(left)
                    x["reason"] = (x.get("reason") or "")
                    add = f"용어 정의({', '.join(term_of(s) for s in picked)})를 「정의」 조문으로 옮겼다."
                    x["reason"] = f"{x['reason']} / {add}" if x["reason"] else add
                else:
                    dropped.append((lb, x["title"]))
                    continue
            keep.append(x)
        ns[:] = keep

    for p in tree:
        if p.get("isAnnex"):
            continue
        walk([p], "", "")
    return got, dropped, part_of


# ───────────────────────── 편별로 정의를 나눈다 ─────────────────────────
# 총칙 한 조에 정의를 다 모으니 131호·1만 3천 자가 되어 읽기 어렵다.
# 그 편에서만 쓰는 말은 그 편의 정의 조문으로 내려보내고,
# 여러 편이 함께 쓰는 말과 총칙에서 온 말만 총칙에 남긴다.

def parts_using(tree, terms):
    """용어마다 그 말이 나오는 편의 이름을 모은다 (정의 조문 자체는 세지 아니한다)"""
    bodies = {}                       # 편 이름 → 그 편의 본문을 이어 붙인 글

    def rec(ns, part):
        for x in ns:
            lv = x.get("level")
            if lv == "편":
                rec(x.get("children") or [], x.get("title") or "")
                continue
            if lv == "조" and part and not is_def_article(x.get("title")):
                bodies[part] = bodies.get(part, "") + "\n" + (x.get("title") or "") \
                               + "\n" + (x.get("body") or "")
            rec(x.get("children") or [], part)

    rec([n for n in tree if not n.get("isAnnex")], "")
    out = {}
    for t in terms:
        if not t:
            continue
        out[t] = {p for p, b in bodies.items() if t in b}
    return out


def split_by_part(tree, got, part_of):
    """총칙에 남길 정의와 편별로 내려보낼 정의를 가른다

    반환: (총칙 몫, {편 이름: [(term, sent, src)…]})
    """
    used = parts_using(tree, [g[0] for g in got])
    keep, by_part = [], {}
    for term, sent, src in got:
        home = part_of.get(term) or ""
        # 총칙에서 온 말·약칭·여러 편이 함께 쓰는 말은 총칙에 남긴다
        if not home or home == "총칙" or len(used.get(term) or set()) > 1:
            keep.append((term, sent, src))
        else:
            by_part.setdefault(home, []).append((term, sent, src))
    return keep, by_part


def body_of(items, head):
    """정의 조문 본문 한 덩이 — 현행 조문 차례로 호를 매긴다"""
    seen, rows = set(), []
    for term, sent, src in items:
        if not term or term in seen:
            continue
        seen.add(term)
        rows.append((src_key(src), f"{sent} <{src}>" if src else sent))
    # 같은 조문에서 온 것끼리는 거둔 차례(그 조문 안의 차례)를 지킨다 — 안정 정렬
    rows.sort(key=lambda x: x[0])
    return "\n".join([head] + [f"{i}. {s}" for i, (_, s) in enumerate(rows, start=1)])


# 출처 표시에서 현행 조번호를 뽑는다 — '현행 제150조 「정의」'
RE_SRC_JO = re.compile(r"현행\s*제(\d+)조")


def src_key(src):
    """정의를 늘어놓는 차례 — 그 정의가 있던 현행 조문의 번호 순.

    가나다순으로 늘어놓으면 한 조문에서 온 정의가 여기저기 흩어져, 개정 전후를
    견줄 때 어느 조문이 어디로 갔는지 따라가기 어렵다. 조문 차례로 둔다.
    현행 조문에서 오지 아니한 것(약칭·신설)은 맨 뒤에 둔다.
    """
    m = RE_SRC_JO.search(str(src or ""))
    return (0, int(m.group(1))) if m else (1, 0)


def merge_into(node, got, own_terms=()):
    """제2조 본문 뒤에 거둔 정의를 호로 붙이고 현행 조문 차례로 정렬한다

    own_terms 는 현행 제2조가 본래 갖고 있던 용어다. 이 조의 본문에는 그 밖에
    검토의견을 받아 새로 넣은 정의도 섞여 있으므로, 둘을 가려 현행에 있던 것만
    앞자리에 둔다 — 현행과 견줄 때 자리가 덜 움직인다.
    """
    body = (node.get("body") or "").strip()
    lines = body.split("\n")
    head = lines[0] if lines else "이 규정에서 사용하는 용어의 뜻은 다음과 같다."

    own = set(own_terms or ())
    HERE = src_key("현행 제2조")         # 현행 제2조가 본래 갖고 있던 호
    LAST = (1, 0)                        # 현행에 근거가 없는 것(신설·약칭)은 맨 뒤

    items, seen = [], set()
    for l in lines[1:]:
        if not l.strip():
            continue
        s = re.sub(r"^\s*\d+\.\s*", "", l).strip()
        t = term_of(s)
        if t and t in seen:
            continue
        seen.add(t)
        items.append((HERE if t in own else LAST, s))
    for term, sent, src in got:
        if term and term in seen:
            continue
        seen.add(term)
        items.append((src_key(src), f"{sent} <{src}>"))

    # 가나다순이 아니라 그 정의가 있던 현행 조문의 차례로 늘어놓는다
    items.sort(key=lambda x: x[0])
    return "\n".join([head] + [f"{i}. {s}" for i, (_, s) in enumerate(items, start=1)])
