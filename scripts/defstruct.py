# -*- coding: utf-8 -*-
r"""정의 체계를 세 층으로 세운다 (작업규정 개정안).

■ 세 층

    제1편 총칙의 정의        여러 편이 함께 쓰는 말
    편의 개설(제1장)의 정의   그 편 안 두 장 이상이 쓰는 말
    장의 머리의 정의          그 장에서만 쓰는 말

■ 자리를 정하는 차례

  ① 편ㆍ장의 이름이 그 용어이면 그 자리로 간다.
     「지형측량」은 제3편의 이름이므로 제3편이다. 쓰임을 세면 제5편에서 더
     자주 나오나(응용측량이 지형측량을 인용한다) 그것은 인용이지 소속이 아니다.
  ② 그러하지 아니하면 쓰임으로 정한다 —— 세 편 이상이면 총칙, 한 편 안
     두 장 이상이면 그 편의 개설, 그 밖에는 그 장.
  ③ 한 번도 쓰이지 아니하는 말은 지운다. 다만 편ㆍ장의 이름인 말은 남긴다.

  쓰임은 긴 용어부터 덮어 가며 센다. 「지하시설물」을 먼저 덮어야 「시설물」이
  그 안에서 다시 잡히지 아니한다.

■ 조 번호가 밀리는 것

  정의 조문을 세우면 뒤의 조 번호가 밀린다. 본문이 우리 규정의 조를 부르는
  자리를 옛 번호에서 새 번호로 함께 옮긴다. 남의 법령을 부르는 자리와
  <현행 제N조> 표시는 건드리지 아니한다 (defsplit.py 와 같은 잣대).

  python scripts\defstruct.py            무엇을 고칠지 보여만 준다
  python scripts\defstruct.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys
import collections

import renumlib

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
NL = chr(10)
WRITE = "--write" in sys.argv

HO = re.compile(r"^\s*(\d{1,2})\.\s")
JO = re.compile(r"제\s*(\d+)\s*조")
SRC_MARK = re.compile(r"<[^<>]*>")
LAW_TAIL = re.compile(r"(?:법|영|규칙|법률|준칙|규정|고시)\s*(?:」)?\s*$")
RE_MARK = re.compile(r"<[^>]*>")
RE_TERM = re.compile(
    r'^"([^"]+?)(?:\(이하\s*"([^"]+)"[^)]*\))?"'
    r'(?:\s*\(이하\s*"([^"]+)"[^)]*\))?'
    r'\s*(?:란|이란|이라|는|은|라)')


def walk(ns):
    for n in ns:
        yield n
        for m in walk(n.get("children") or []):
            yield m


def isdef(n):
    t = (n.get("title") or "").strip()
    return t == "정의" or t.endswith("의 정의")


def split_items(body):
    """머리글 한 줄과 호 묶음으로 가른다. 목(가.ㆍ나.…)은 그 호에 붙인다."""
    head, items, order, cur = [], {}, [], None
    for ln in (body or "").split(NL):
        m = HO.match(ln)
        if m:
            cur = int(m.group(1))
            items[cur] = [ln]
            order.append(cur)
        elif cur is None:
            head.append(ln)
        else:
            items[cur].append(ln)
    return NL.join(head), items, order


def renum_block(blocks):
    """호 묶음을 1부터 다시 매긴다"""
    out = []
    for i, block in enumerate(blocks, 1):
        b = list(block)
        b[0] = HO.sub("%d. " % i, b[0], count=1)
        out.extend(b)
    return out


def remap_body(text, move, log, where):
    """본문이 부르는 우리 규정의 조 번호를 새 번호로 옮긴다"""
    out, last = [], 0
    for m in JO.finditer(text):
        out.append(text[last:m.start()])
        last = m.end()
        no = int(m.group(1))
        pre = text[max(0, m.start() - 16):m.start()]
        inside = any(a.start() <= m.start() < a.end() for a in SRC_MARK.finditer(text))
        if inside or LAW_TAIL.search(pre) or pre.rstrip().endswith("현행"):
            out.append(m.group(0))
            continue
        if no in move:
            out.append("제%d조" % move[no])
            log.append((where, no, move[no]))
        else:
            out.append(m.group(0))
    out.append(text[last:])
    return "".join(out)


# ── 자리를 재는 자 ─────────────────────────────────────────
def measure(tree):
    """정의 호마다 (마디, 호번호, 용어, 약칭) 과 쓰임을 잰다"""
    anc = {}

    def rec(ns, py=None, ja=None):
        for n in ns:
            p = n if n.get("level") == "편" else py
            j = n if n.get("level") == "장" else ja
            anc[id(n)] = (p, j)
            rec(n.get("children") or [], p, j)

    rec(tree)

    defs = []
    for n in walk(tree):
        if not isdef(n):
            continue
        py, ja = anc[id(n)]
        _head, items, order = split_items(n.get("body") or "")
        for ho in order:
            raw = HO.sub("", RE_MARK.sub("", items[ho][0])).strip()
            m = RE_TERM.match(raw)
            if not m:
                continue
            defs.append({"마디": n, "편": py, "장": ja, "호": ho,
                         "용어": m.group(1).strip(), "약칭": m.group(2) or m.group(3)})

    bodies = []
    for n in walk(tree):
        py, ja = anc[id(n)]
        if not py or py.get("no") in (0, 8) or n.get("level") != "조" or isdef(n):
            continue
        bodies.append((py.get("no"), ja.get("no") if ja else None,
                       RE_MARK.sub("", (n.get("title") or "") + " " + (n.get("body") or ""))))

    keyed = []
    for i, x in enumerate(defs):
        for k in [x["용어"].split("(")[0].strip()] + ([x["약칭"]] if x["약칭"] else []):
            if k:
                keyed.append((k, i))
    keyed.sort(key=lambda t: -len(t[0]))

    hits = collections.defaultdict(collections.Counter)
    for py, ja, txt in bodies:
        left = txt
        for k, i in keyed:
            c = left.count(k)
            if c:
                hits[i][(py, ja)] += c
                left = left.replace(k, "\x00" * len(k))

    for i, x in enumerate(defs):
        h = hits.get(i, collections.Counter())
        x["횟수"] = sum(h.values())
        x["편들"] = sorted({p for p, _ in h})
        x["장들"] = sorted({j for p, j in h if x["편"] and p == x["편"].get("no")})
        x["편별"] = collections.Counter()
        for (p, _j), c in h.items():
            x["편별"][p] += c
        x["장별"] = {p: sorted({j for (pp, j) in h if pp == p}) for p in x["편별"]}
    return defs


def head_line(kind):
    return {"총칙": "이 규정에서 사용하는 용어의 뜻은 다음과 같다.",
            "편": "이 편에서 사용하는 용어의 뜻은 다음과 같다.",
            "장": "이 장에서 사용하는 용어의 뜻은 다음과 같다."}[kind]


def new_reason(kind, pyeon_name, n, froms):
    """새로 세우는 정의 조문의 변경 사유"""
    where = "편" if kind == "편" else "장"
    L = ["[변경 사유]", "",
         "○ 현행 규정:", "",
         "* 없음 —— 신설 조문.", "",
         "○ 현행의 문제:", "",
         "* 이 %s의 여러 장이 함께 쓰는 용어의 뜻이 총칙과 장에 나뉘어 있어 "
         "어느 자리를 보아야 하는지 알기 어려움." % where,
         "* 총칙 정의 조문에 이 %s에서만 쓰는 말이 섞여 있어 다른 편을 하는 "
         "사람도 그것을 훑어야 함." % where, "",
         "○ 관련 근거:", "",
         "* 규정 체계 정비 —— 정의를 총칙ㆍ편ㆍ장 세 층으로 세움.",
         "* 일본 「作業規程の準則」이 편의 총칙과 장의 머리에 정의를 나누어 두는 방식.", "",
         "○ 개정 사유:", "",
         "* 여러 편이 함께 쓰는 말은 총칙에, 한 편의 두 장 이상이 쓰는 말은 그 편의 "
         "개설에, 한 장에서만 쓰는 말은 그 장에 둠.",
         "* 찾아 읽는 자리를 그 말을 쓰는 자리에 가깝게 둠.", "",
         "○ 개정 내용:", "",
         "* 이 %s의 두 장 이상이 쓰는 용어 %d개를 이 조에 둔다." % (where, n)]
    if froms:
        L.append("* 옮겨 온 자리는 %s임." % "ㆍ".join(froms))
    return NL.join(L)


def note_lines(into, out, killed):
    """이미 있던 정의 조문의 「개정 내용」 에 덧붙일 줄"""
    L = []
    if into:
        L.append("* 정의 체계를 세 층으로 세우면서 %s를 이 조로 옮겨 옴."
                 % "ㆍ".join("「%s」" % t for t in into))
    if out:
        L.append("* %s는 쓰이는 자리에 가깝게 내려 옮김."
                 % "ㆍ".join("「%s」" % t for t in out))
    if killed:
        L.append("* 본문에서 한 번도 쓰이지 아니하는 %s를 지움."
                 % "ㆍ".join("「%s」" % t for t in killed))
    return L


def apply(doc, tree, moves, kills, news, pyeon, jang):
    """옮기고ㆍ지우고ㆍ세운다"""
    # ① 마디마다 빼낼 호와 받을 호를 모은다
    take = collections.defaultdict(list)      # 마디 id -> [호번호]
    give = collections.defaultdict(list)      # 마디 id -> [(용어, 블록)]
    hosts = {}                                # 새 조문을 세울 장 마디
    log = {"into": collections.defaultdict(list), "out": collections.defaultdict(list),
           "kill": collections.defaultdict(list)}

    for x, to, host, _why in moves:
        take[id(x["마디"])].append(x["호"])
        log["out"][id(x["마디"])].append(x["용어"])
        if to is not None:
            give[id(to)].append(x)
            log["into"][id(to)].append(x["용어"])
        else:
            hosts[id(host)] = host
            give[("새", id(host))].append(x)
    for x, why in kills:
        take[id(x["마디"])].append(x["호"])
        log["kill"][id(x["마디"])].append(x["용어"])

    # ② 옮길 호의 글을 먼저 떠 둔다 (마디를 고치기 전에)
    blocks = {}
    for n in walk(tree):
        if not isdef(n):
            continue
        _h, items, _o = split_items(n.get("body") or "")
        for ho, block in items.items():
            blocks[(id(n), ho)] = block

    # ③ 이미 있던 정의 조문을 다시 짠다
    for n in walk(tree):
        if not isdef(n):
            continue
        head, items, order = split_items(n.get("body") or "")
        drop = set(take.get(id(n), []))
        keep = [items[h] for h in order if h not in drop]
        for x in give.get(id(n), []):
            keep.append(blocks[(id(x["마디"]), x["호"])])
        if not keep and not head.strip():
            continue
        n["body"] = NL.join([head] + renum_block(keep)).strip(NL)
        add = note_lines(log["into"].get(id(n), []), log["out"].get(id(n), []),
                         log["kill"].get(id(n), []))
        if add:
            r = n.get("reason") or ""
            m = re.search(r"(○\s*개정 내용:\s*\n\n)", r)
            if m:
                n["reason"] = r[:m.end()] + NL.join(add) + NL + r[m.end():]
            else:
                n["reason"] = (r.rstrip() + NL * 2 + "○ 개정 내용:" + NL * 2
                               + NL.join(add))
        # 「편 공통으로 쓰는 N개」 처럼 수를 적은 자리를 지금 수로 맞춘다
        cnt = len([1 for ln in n["body"].split(NL) if HO.match(ln)])
        n["reason"] = re.sub(r"(편 공통으로 쓰는 )\d+(개를 이 조에 둠)",
                             lambda mm: mm.group(1) + str(cnt) + mm.group(2),
                             n.get("reason") or "")

    # ④ 새 정의 조문을 세운다
    made = []
    for key, xs in give.items():
        if not (isinstance(key, tuple) and key[0] == "새"):
            continue
        host = hosts[key[1]]
        py = next(p for p in pyeon.values()
                  if host in (p.get("children") or []))
        kids = renum_block([blocks[(id(x["마디"]), x["호"])] for x in xs])
        node = {
            "id": "def-p%d" % py["no"],
            "level": "조", "no": 0, "branch": 0, "title": "정의",
            "body": NL.join([head_line("편")] + kids),
            "status": "신설", "legacyNo": "",
            "reason": new_reason("편", py.get("title"), len(xs),
                                 sorted({"제%s조" % x["마디"].get("no") for x in xs})),
            "sourceRef": None, "history": [], "children": [],
        }
        host.setdefault("children", []).insert(0, node)
        made.append((py.get("no"), host.get("title"), len(xs)))
    return made


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    tree = doc["tree"]

    # 편ㆍ장의 이름
    pyeon = {p["no"]: p for p in tree if p.get("level") == "편" and p.get("no") not in (0, 8)}
    jang = {}
    for p in pyeon.values():
        for c in p.get("children") or []:
            if c.get("level") == "장":
                jang[(p["no"], c["no"])] = c
    norm = lambda s: re.sub(r"[\s·ㆍ()]", "", s or "")
    name_jang = {norm(c.get("title")): k for k, c in jang.items()}
    name_pyeon = {norm(p.get("title")): k for k, p in pyeon.items()}

    defs = measure(tree)

    plan = []
    for x in defs:
        term, t = x["용어"], norm(x["용어"])
        if t in name_jang:
            p, j = name_jang[t]
            plan.append((x, "그 장", p, j, "이름이 장과 같음"))
            continue
        if t in name_pyeon:
            plan.append((x, "편 개설", name_pyeon[t], None, "이름이 편과 같음"))
            continue
        if x["횟수"] == 0:
            plan.append((x, "지움", None, None, "쓰이지 아니함"))
            continue
        if len(x["편들"]) >= 3:
            plan.append((x, "총칙", 1, 1, "%d개 편에서 쓰임" % len(x["편들"])))
            continue
        here = x["편"].get("no") if x["편"] else None
        if here == 1 and 1 in x["편들"]:
            plan.append((x, "총칙", 1, 1, "총칙과 다른 편에 걸침"))
            continue
        home = here if here != 1 else x["편별"].most_common(1)[0][0]
        jangs = x["장별"].get(home, [])
        if len(jangs) >= 2:
            plan.append((x, "편 개설", home, None, "그 편 %d개 장에서 쓰임" % len(jangs)))
        else:
            plan.append((x, "그 장", home, jangs[0] if jangs else
                         (x["장"].get("no") if x["장"] else None), "한 장에서만 쓰임"))

    # 같은 용어가 두 곳에 정의되어 있으면 하나만 남긴다
    seen, dups = {}, []
    final = []
    for x, a, p, j, why in plan:
        k = norm(x["용어"])
        if a != "지움" and k in seen:
            dups.append((x, seen[k]))
            final.append((x, "지움", None, None, "겹친 정의 —— 한 곳만 남김"))
            continue
        if a != "지움":
            seen[k] = x
        final.append((x, a, p, j, why))

    # 갈 자리를 마디로 옮긴다
    def target_node(a, p, j):
        if a == "총칙":
            return next(n for n in walk(tree) if isdef(n) and n.get("no") == 2)
        if a == "편 개설":
            ch = pyeon[p].get("children") or []
            first = next((c for c in ch if c.get("level") == "장"), None)
            return ("새", first)
        k = (p, j)
        c = jang.get(k)
        if c is None:
            return None
        got = next((n for n in (c.get("children") or []) if isdef(n)), None)
        return got if got else ("새", c)

    moves, kills, news = [], [], collections.OrderedDict()
    for x, a, p, j, why in final:
        if a == "지움":
            kills.append((x, why))
            continue
        t = target_node(a, p, j)
        if isinstance(t, tuple):                    # 정의 조문이 없는 자리
            host = t[1]
            got = next((n for n in (host.get("children") or []) if isdef(n)), None)
            if got is None:
                news.setdefault(id(host), (host, p, a, []))
                if x["마디"] is not host:
                    moves.append((x, None, host, why))
                continue
            t = got
        if t is not x["마디"]:
            moves.append((x, t, None, why))

    print("■ 옮길 것 %d개 ㆍ 지울 것 %d개 ㆍ 새 정의 조문 %d개"
          % (len(moves), len(kills), len(news)))
    for x, to, host, why in moves:
        where = ("제%s조" % to.get("no")) if to is not None else \
                ("제%s편 %s(새 정의 조문)" % (host and host.get("no"), host and host.get("title")))
        print("   %-24s 제%s조 → %-22s %s" % (x["용어"], x["마디"].get("no"), where, why))
    print()
    for x, why in kills:
        print("   지움  %-24s 제%s조 제%d호  %s" % (x["용어"], x["마디"].get("no"), x["호"], why))
    print()
    for host, p, a, _ in news.values():
        print("   새 정의 조문  제%s편 %s" % (p, host.get("title")))

    if not WRITE:
        print("\n자료에 적으려면 --write 를 붙이십시오.")
        return

    before = {id(n): n.get("no") for n in walk(tree) if n.get("level") == "조"}
    made = apply(doc, tree, moves, kills, news, pyeon, jang)
    renumlib.renumber(tree)

    # 조 번호가 밀린 만큼 본문의 인용도 함께 옮긴다
    move = {}
    for n in walk(tree):
        if n.get("level") != "조":
            continue
        old_no = before.get(id(n))
        if old_no and old_no != n.get("no"):
            move[old_no] = n.get("no")
    log = []
    for n in walk(tree):
        if n.get("body"):
            n["body"] = remap_body(n["body"], move, log, "제%s조" % n.get("no"))
    io.open(SRC, "w", encoding="utf-8", newline="").write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("담았습니다 —— 새 정의 조문 %d개 ㆍ 밀린 조 %d개 ㆍ 고친 인용 %d곳"
          % (len(made), len(move), len(log)))
    for p_no, name, cnt in made:
        print("   제%s편 %s 에 정의 조문 (용어 %d개)" % (p_no, name, cnt))


if __name__ == "__main__":
    main()
