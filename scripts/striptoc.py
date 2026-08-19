# -*- coding: utf-8 -*-
"""
KDS·KCS 처럼 앞머리에 목차가 붙은 문서를 손질한다.

원본 HWP 의 목차도 '1. 일반사항 …… 1' 꼴이라 본문과 똑같은 얼개로 잡힌다.
그래서 트리에 같은 제목이 두 번 나오고, 앞엣것(목차)은 눌러도 '(내용 없음)'
만 나온다. 아래 네 가지를 손본다.

  1) 첫 본문 마디보다 앞에 있으면서 속이 통째로 빈 목차 가지를 걷어 낸다.
  2) 쪽 번호만 덩그러니 남은 빈 마디를 지운다.
  3) 쪽머리글이 눌어붙은 제목·본문을 목차 제목으로 되돌린다.
     (보기) '일반사항KCS 12 00 00 건설공사 측량' → '일반사항'
  4) '2.1' '3.1' 처럼 딴 갈래인데 첫 마디에 딸려 붙은 것을
     목차에 적힌 이름(자재·시공)으로 갈래를 새로 세워 옮긴다.

사용:  python scripts/striptoc.py            (loc* 전부)
       python scripts/striptoc.py loc23      (하나만)
"""
import io, json, os, re, sys, glob

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

PAGE = re.compile(r"\s*\d{1,3}$")               # 제목 끝의 쪽 번호
NUMONLY = re.compile(r"^[\d.\s]+$")             # 숫자만 남은 제목
STDNO = re.compile(r"(KDS|KCS)\s*\d{2}\s*\d{2}\s*\d{2}")   # 기준 번호


def clean(t):
    return PAGE.sub("", str(t or "")).strip()


def has_body(n):
    if (n.get("body") or "").strip():
        return True
    return any(has_body(c) for c in n.get("children") or [])


def walk(n):
    for c in n.get("children") or []:
        yield c
        yield from walk(c)


def toc_map(tocs):
    """목차 가지에서 '차례번호 → 제목' 을 뽑는다"""
    m = {}
    for t in tocs:
        for n in [t, *walk(t)]:
            k, v = n.get("outlineNo"), clean(n.get("title"))
            if k and v and k not in m:
                m[k] = v
    return m


def strip_toc(tree):
    """첫 본문 마디 앞의 빈 목차 가지를 떼어 낸다 → (뗀 가지들)"""
    live = next((i for i, t in enumerate(tree) if has_body(t)), None)
    if not live:                                  # 없거나 맨 앞이 본문이면 그만
        return []
    head = tree[:live]
    # 쪽 번호가 붙어 있어야 목차로 본다 (해적이 아닌 진짜 빈 장 보호)
    if not all(PAGE.search(str(t.get("title") or "")) for t in head):
        return []
    del tree[:live]
    return head


def drop_stray(nodes):
    """쪽 번호만 남은 빈 마디를 지운다"""
    n = 0
    keep = []
    for x in nodes:
        x["children"] = x.get("children") or []
        n += drop_stray(x["children"])
        if (not (x.get("body") or "").strip() and not x["children"]
                and NUMONLY.match(str(x.get("title") or ""))):
            n += 1
            continue
        keep.append(x)
    nodes[:] = keep
    return n


def flat(s):
    return re.sub(r"[\s:·]+", "", str(s or ""))


def is_runhead(body, name):
    """'옹벽 …공사 측량 KCS 10 20 15 :' 처럼 쪽머리글만 든 본문인가

    원문에 기준 번호를 잘못 적어 둔 것(10↔12)이 있어 번호는 지우고 견준다."""
    b = str(body or "").strip()
    if not b or len(b) > 60 or not STDNO.search(b):
        return False
    rest = flat(STDNO.sub("", b))
    return len(rest) >= 2 and rest in flat(name)


def drop_runhead(nodes, name):
    """쪽머리글만 든 본문을 지운다 — 목차 가려내기에 앞서 한다"""
    n = 0
    for x in nodes:
        if is_runhead(x.get("body"), name):
            x["body"] = ""
            n += 1
        n += drop_runhead(x.get("children") or [], name)
    return n


def fix_head(node, tm):
    """쪽머리글이 눌어붙은 제목을 목차 제목으로 되돌린다"""
    want = tm.get(node.get("outlineNo"))
    title = str(node.get("title") or "")
    if want and title != want and title.startswith(want):
        node["title"] = want
        return 1
    return 0


LEVELS = ["편", "장", "절", "관", "조"]


def next_lv(lv):
    """한 칸 아래 갈래 이름 — 끝이면 그대로 둔다"""
    i = LEVELS.index(lv) if lv in LEVELS else -1
    return LEVELS[min(i + 1, len(LEVELS) - 1)] if i >= 0 else (lv or "조")


def okey(s):
    """'3.10' 을 (3,10) 으로 — 차례 번호를 숫자로 견준다"""
    return tuple(int(x) if x.isdigit() else 0 for x in str(s or "").split("."))


def regroup(tree, tm, tocs):
    """목차에 적힌 갈래(1 일반사항 / 2 자재 / 3 시공)대로 마디를 제자리에 앉힌다"""
    tops = sorted(k for k in tm if k.isdigit())
    if len(tops) < 2 or not tree:
        return 0

    # 1) 갈래 마디를 마련한다 — 이미 있으면 그대로 쓴다
    group, moved = {}, 0
    for t in tree:
        no = str(t.get("outlineNo") or "")
        if no in tops and no not in group and clean(t.get("title")) == tm[no]:
            group[no] = t
    for no in tops:
        if no in group:
            continue
        src = next((t for t in tocs if str(t.get("outlineNo")) == no), None)
        group[no] = {
            "id": f"{tree[0]['id']}g{no}",
            "level": tree[0].get("level", "편"),
            "no": int(no), "branch": 0,
            "title": tm[no], "body": "",
            "status": "유지", "legacyNo": no, "reason": "", "sourceRef": None,
            "outlineNo": no,
            "outlineKind": (src or {}).get("outlineKind", "num"),
            "history": [], "origTitle": "", "collapsed": False, "children": [],
        }

    # 1-2) 옮기기 전에, 목차에 없는 조각이 원문에서 어느 마디 뒤에 있었는지 적어 둔다
    seen = [None]
    def mark(ns):
        for x in ns:
            no = str(x.get("outlineNo") or "")
            if "." in no:
                seen[0] = x
            elif clean(x.get("title")) not in set(tm.values()):
                x["_after"] = seen[0]
            mark(x.get("children") or [])
    mark(tree)

    # 2) '2.1' '3.2' 처럼 갈래가 또렷한 마디를 제 갈래로 모은다
    def pull(nodes, owner):
        nonlocal moved
        keep = []
        for x in nodes:
            x["children"] = pull(x.get("children") or [], x)
            pre = str(x.get("outlineNo") or "").split(".")[0]
            deep = "." in str(x.get("outlineNo") or "")
            if deep and pre in group and owner is not group[pre] and pre != str(
                    (owner or {}).get("outlineNo", "")).split(".")[0]:
                group[pre]["children"].append(x)
                moved += 1
                continue
            keep.append(x)
        return keep

    rest = pull([t for t in tree if t not in group.values()], None)
    for g in group.values():
        g["children"] = pull(g.get("children") or [], g)

    # 3) 목차에 없는 조각은 바로 앞 갈래의 마지막 마디에 딸려 붙인다
    left = []
    for x in rest:
        host = x.pop("_after", None)
        if host is not None and host is not x:
            host.setdefault("children", []).append(x)
            x["level"] = next_lv(host.get("level"))     # 딸린 자리에 맞춘다
            moved += 1
        else:
            left.append(x)

    def wipe(ns):
        for x in ns:
            x.pop("_after", None)
            wipe(x.get("children") or [])
    wipe(tree)
    for g in group.values():
        g["children"].sort(key=lambda n: okey(n.get("outlineNo")))
        wipe(g["children"])
    tree[:] = [group[no] for no in tops] + left
    return moved


def count(tree):
    c = {"편": 0, "장": 0, "절": 0, "관": 0, "조": 0}
    def rec(ns):
        for x in ns:
            if x.get("level") in c:
                c[x["level"]] += 1
            rec(x.get("children") or [])
    rec(tree)
    return c


def main(only=None):
    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    total = 0
    for path in sorted(glob.glob(os.path.join(DATA, "loc*.json"))):
        rid = os.path.basename(path)[:-5]
        if only and rid != only:
            continue
        doc = json.load(io.open(path, encoding="utf-8"))
        tree = doc.get("tree") or []
        n_run = drop_runhead(tree, doc.get("name"))
        tocs = strip_toc(tree)
        tm = toc_map(tocs)
        n_toc = sum(1 + sum(1 for _ in walk(t)) for t in tocs)
        n_str = drop_stray(tree)
        n_fix = 0
        def rec(ns):
            nonlocal n_fix
            for x in ns:
                n_fix += fix_head(x, tm)
                rec(x.get("children") or [])
        rec(tree)
        n_mov = regroup(tree, tm, tocs)
        if not (n_run or n_toc or n_str or n_fix or n_mov):
            continue
        c = count(tree)
        doc["tree"] = tree
        doc["stats"] = {**doc.get("stats", {}), **c}
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        for r in lib["regulations"]:
            if r["id"] == rid:
                r["stats"] = {**r.get("stats", {}), **c}
        total += 1
        print(f"  {rid}  머리글 {n_run} · 목차 {n_toc} · 빈칸 {n_str} · 제목 {n_fix} · 옮김 {n_mov}"
              f"   {doc.get('name','')[:38]}")
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"\n{total}종을 손질했습니다.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
