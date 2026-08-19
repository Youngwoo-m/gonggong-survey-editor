# -*- coding: utf-8 -*-
"""
개편안이 밖을 가리키는 곳의 정합성 검토 — 상위법령·별도규정과 맞대어 본다.

기존 검사기는 개편안 안쪽만 본다.

  checkdraft   조 번호·항 번호·별표 위임 — 개편안 안
  reviewdraft  번호를 다시 매긴 뒤의 인용 — 개편안 안
  auditdraft   조문 안의 항·호·목 차례 — 조문 안

밖을 가리키는 인용은 아무도 보지 아니하였다. 「공간정보의 구축 및 관리 등에
관한 법률」 제18조처럼 다른 법령·규정을 가리키는 곳이다. 이것이 어긋나면
개정 뒤에 조문이 엉뚱한 데를 가리키게 되고, 공청회에서 바로 짚인다.

  1) 가리킨 법령·규정이 참조 규정 서고에 있는가
  2) 있다면 그 법령에 그 조가 실제로 있는가 (제13조의2 같은 가지조도 본다)
  3) 그 조에 그 항·호가 있는가
  4) 같은 법령을 여러 이름으로 적지는 아니하였는가 (띄어쓰기·약칭)
  5) 법령 이름을 낫표로 감싸지 아니한 곳은 없는가
  6) 개편안 안을 가리키는 편·장 인용이 실제로 있는가

서고에 없는 법령은 '틀렸다' 고 말하지 아니한다 — 맞대어 볼 수 없을 뿐이다.
그런 것은 따로 모아 알린다.

사용:  python scripts/checkcites.py [-v]
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

RE_PROV = re.compile(r"<현행[^<>]*>")
RE_IMG = re.compile(r'<img\s+id="[\w.-]+"></img>')
# 「이름」 뒤에 제N조(의M)[제N항][제N호] 가 따라올 수 있다
# 법령 이름과 조 사이에 약칭을 괄호로 다는 자리가 있다 —
# 「…법률」(이하 "법"이라 한다) 제2조제3호. 이 괄호를 넘기지 못해 그 인용을
# 아예 맞대어 보지 못하고 지나쳤다.
RE_CITE = re.compile(
    r"「([^」]{2,60})」"
    r"(?:\s*[\(（][^()（）]{0,40}[\)）])?"
    r"\s*(?:(?:[^\s제]{0,12}\s*)?제\s*(\d+)\s*조(?:\s*의\s*(\d+))?"
    r"(?:\s*제\s*(\d+)\s*항)?(?:\s*제\s*(\d+)\s*호)?)?")
# 낫표 없이 쓴 법령 이름 — 앞말을 물고 들어오지 아니하게 이름만 잡는다
RE_BARE = re.compile(r"(?<![「『\w\s])\s?([가-힣]{2,20}(?:법|법률))\s*제\s*\d+\s*조")
# 약칭을 정의하는 자리 — (이하 "법"이라 한다)
RE_ABBR = re.compile(r"\(\s*이하\s*[\"“]([^\"”]{1,12})[\"”]\s*(?:라|이라)\s*한다\s*\)")
# 약칭으로 쓴 것 — 법·영·규칙·시행령·시행규칙
RE_SHORT = re.compile(r"(?<![「『가-힣])(같은\s*법\s*시행령|같은\s*법\s*시행규칙|같은\s*법"
                      r"|시행령|시행규칙|영|규칙|법)\s*제\s*\d+\s*조")
# 법령·규정으로 볼 이름의 꼬리
TAIL = ("법", "법률", "시행령", "시행규칙", "규칙", "규정", "지침", "기준",
        "매뉴얼", "고시", "요령", "예규", "표준", "작업규정", "훈령")
HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

norm = lambda s: re.sub(r"\s+", "", str(s or ""))


def clean(t):
    return RE_IMG.sub("", RE_PROV.sub("", str(t or "")))


def is_law_name(s):
    """법령·규정 이름으로 볼 것인가 — 「정의」 같은 낱말과 조문 제목은 뺀다"""
    s = s.strip()
    if len(s) < 4:
        return False
    if s.endswith(")") and "(" in s:            # 「수치지도 작성 작업규칙(국토교통부령)」
        s = s[:s.rfind("(")].strip()
    return s.endswith(TAIL)


def load_library():
    """이름 → 규정. nameAlias 는 이름이 아니라 규정 id 를 가리킨다"""
    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    by, by_id, alias_of = {}, {}, {}
    for r in lib["regulations"]:
        by.setdefault(norm(r["name"]), r)
        by_id[r["id"]] = r
    for alias, rid in (lib.get("nameAlias") or {}).items():
        if rid in by_id:
            by.setdefault(norm(alias), by_id[rid])
            alias_of[norm(alias)] = by_id[rid]
    return lib, by, alias_of


_cache = {}


def articles_of(reg):
    """그 규정의 조 번호 → (제목, 항 수, 항마다의 호 수)"""
    if reg["id"] in _cache:
        return _cache[reg["id"]]
    path = os.path.join(DATA, reg.get("file") or (reg["id"] + ".json"))
    out = {}
    if os.path.exists(path):
        doc = json.load(io.open(path, encoding="utf-8"))
        tree = doc.get("tree") or (doc.get("versions") or [{}])[0].get("tree") or []

        def rec(ns):
            for x in ns:
                if x.get("level") == "조" and not x.get("isDeleted"):
                    body = clean(x.get("body"))
                    hang = [i for i, c in enumerate(body) if c in HANG]
                    n_h = len(hang) or (1 if body.strip() else 0)
                    ho = []
                    parts = re.split("[" + HANG + "]", body)
                    for p in (parts[1:] if len(parts) > 1 else parts):
                        ho.append(len(re.findall(r"(?:^|\n)\s*(\d{1,2})\.\s", p)))
                    key = str(x.get("no"))
                    if x.get("branch"):
                        key += "의" + str(x["branch"])
                    out[key] = (x.get("title") or "", n_h, ho)
                rec(x.get("children") or [])
        rec(tree)
    _cache[reg["id"]] = out
    return out


def main():
    verbose = "-v" in sys.argv
    lib, by_name, alias_of = load_library()
    doc = json.load(io.open(os.path.join(DATA, "draft2025.json"), encoding="utf-8"))
    tree = doc.get("tree") or doc["versions"][0]["tree"]

    arts, groups = [], []

    def rec(ns):
        for x in ns:
            if x.get("isDeleted"):
                continue
            if x.get("level") == "조" and not x.get("annexRef"):
                arts.append(x)
            if x.get("level") in ("편", "장"):
                groups.append(x)
            rec(x.get("children") or [])
    rec(tree)

    bad = collections.defaultdict(list)
    seen_names = collections.defaultdict(set)      # 정규화 이름 → 쓴 표기들
    unknown = collections.Counter()
    n_cite = n_checked = 0

    # 약칭을 어디에서 정의하였는가 — (이하 "법"이라 한다)
    abbr = {}
    for x in arts:
        for m in RE_ABBR.finditer(clean(x.get("body"))):
            abbr.setdefault(m.group(1), f"제{x.get('no')}조")

    for x in arts:
        label = f"제{x.get('no')}조({x.get('title')})"
        body = clean(x.get("body"))

        # 5) 낫표 없이 쓴 법령 이름
        for m in RE_BARE.finditer(body):
            nm = m.group(1).strip()
            if nm in ("이 법", "같은 법", "법"):
                continue
            bad["법령 이름에 낫표 없음"].append(f"{label} — {m.group(0).strip()}")

        # 5-1) 「…법률」시행령 — 시행령까지 낫표 안에 넣어야 한다
        for m in re.finditer(r"「([^」]*법(?:률)?)」\s*(시행령|시행규칙)\s*제\s*\d+\s*조", body):
            bad["낫표를 법률에서 끊음"].append(
                f"{label} — 「{m.group(1)}」{m.group(2)} → 「{m.group(1)} {m.group(2)}」")

        # 5-2) 약칭으로 받은 것 — 그 약칭을 어디선가 정의하였어야 한다
        for m in RE_SHORT.finditer(body):
            s = re.sub(r"\s+", " ", m.group(1)).strip()
            if s.startswith("같은"):
                if "법" not in abbr and "「" not in body[:m.start()]:
                    bad["약칭을 정의하지 아니하고 씀"].append(
                        f"{label} — {m.group(0).strip()} (앞에 가리킨 법령이 없다)")
                if "같은법" in body[max(0, m.start() - 1):m.end()]:
                    bad["약칭 띄어쓰기"].append(f"{label} — {m.group(0).strip()}")
                continue
            if s not in abbr:
                bad["약칭을 정의하지 아니하고 씀"].append(
                    f"{label} — 「{s}」 (이 규정 어디에도 「{s}」이라 한다 가 없다)")

        for m in RE_CITE.finditer(body):
            name = m.group(1).strip()
            if not is_law_name(name):
                continue
            n_cite += 1
            key = norm(name)
            seen_names[re.sub(r"\(.*?\)", "", key)].add(name)
            bare_key = re.sub(r"\(.*?\)", "", key)
            reg = by_name.get(key) or by_name.get(bare_key)
            if reg is None:
                # 가운뎃점을 다르게 쓴 것 (ㆍ U+318D · · U+00B7) 도 같은 것으로 본다
                flat = lambda t: re.sub(r"[·ㆍ・･]", "", t)
                reg = next((v for k, v in by_name.items()
                            if flat(k) == flat(bare_key)), None)
                if reg is not None:
                    bad["가운뎃점 표기가 다름"].append(
                        f"{label} — 「{name}」 (서고: 「{reg['name']}」)")
            if reg is None:
                unknown[name] += 1
                continue
            if (key in alias_of or bare_key in alias_of) and norm(reg["name"]) != bare_key:
                bad["지금 쓰지 아니하는 이름"].append(
                    f"{label} — 「{name}」 → 지금은 「{reg['name']}」")
            if not m.group(2):                     # 이름만 가리킨 것
                continue
            n_checked += 1
            jo = m.group(2) + ("의" + m.group(3) if m.group(3) else "")
            table = articles_of(reg)
            if not table:
                unknown[name + " (본문 없음)"] += 1
                continue
            if jo not in table:
                near = sorted(table, key=lambda k: abs(int(re.match(r"\d+", k).group()) - int(m.group(2))))[:3]
                show = f"제{m.group(2)}조" + (f"의{m.group(3)}" if m.group(3) else "")
                bad["가리킨 조가 없음"].append(
                    f"{label} — 「{name}」 {show} (그 사본은 조 {len(table)}개, "
                    f"가까운 것 {', '.join('제' + k.replace('의', '조의') + ('조' if '의' not in k else '') for k in near)})")
                continue
            title, n_h, ho = table[jo]
            if m.group(4) and n_h and int(m.group(4)) > n_h:
                bad["가리킨 항이 없음"].append(
                    f"{label} — 「{name}」 제{jo}조 제{m.group(4)}항 "
                    f"(그 조는 항 {n_h}개 · {title})")
                continue
            if m.group(5) and m.group(4) and n_h:
                k = int(m.group(4)) - 1
                if 0 <= k < len(ho) and ho[k] and int(m.group(5)) > ho[k]:
                    bad["가리킨 호가 없음"].append(
                        f"{label} — 「{name}」 제{jo}조 제{m.group(4)}항 "
                        f"제{m.group(5)}호 (그 항은 호 {ho[k]}개)")

    # 4) 같은 법령을 여러 이름으로 — 발령기관을 괄호로 덧붙인 것은 흠이 아니다
    for k, forms in seen_names.items():
        core = {re.sub(r"\(.*?\)", "", f).strip() for f in forms}
        if len(core) > 1:
            bad["같은 법령을 여러 이름으로"].append(" · ".join(sorted(core)))

    # 7) 근거 규정 — 이 고시가 어느 조에 기대어 서 있는가
    #
    #   조 제목이 겹치는지 재는 어림짐작은 쓸 수 없었다. 「정의」처럼 흔한
    #   제목이 걸려 잡음만 나고, 정작 근거 규정이 밀린 것은 '측량' 이라는
    #   말이 양쪽에 다 있어 그냥 넘어갔다. 근거 규정은 이 고시가 서 있는
    #   자리이니 어림짐작 대신 곧바로 짚는다.
    #   제1조는 법률을 낫표로 온전히 적기도 하고 「같은 법 시행규칙」 으로
    #   받기도 하므로 두 가지 모두 찾는다.
    WANT = [("공간정보의 구축 및 관리 등에 관한 법률", "공공측량의 실시",
             [r"「공간정보의 구축 및 관리 등에 관한 법률」\s*제\s*(\d+)\s*조"]),
            ("공간정보의 구축 및 관리 등에 관한 법률 시행규칙", "공공측량 작업계획서",
             [r"「[^」]*시행규칙」\s*제\s*(\d+)\s*조",
              r"같은\s*법\s*시행규칙\s*제\s*(\d+)\s*조"])]
    head = clean(arts[0].get("body")) if arts else ""
    for law, subject, pats in WANT:
        reg = by_name.get(norm(law))
        if reg is None:
            continue
        table = articles_of(reg)
        real = [k for k, v in table.items() if subject in (v[0] or "")]
        m = next((mm for p in pats for mm in [re.search(p, head)] if mm), None)
        cited = m.group(1) if m else None
        if real and cited and cited not in real:
            got = table.get(cited)
            bad["근거 규정이 어긋남"].append(
                f"제1조(목적) — 「{law}」 제{cited}조 라 하였으나, 그 법에서 "
                f"「{subject}」 를 정한 것은 제{real[0]}조 다"
                + (f" (제{cited}조 는 「{got[0]}」)" if got else ""))

    # 6) 개편안 안의 편·장 인용
    have_part = {int(g["no"]) for g in groups if g.get("level") == "편" and str(g.get("no")).isdigit()}
    for x in arts:
        for m in re.finditer(r"제\s*(\d+)\s*편", clean(x.get("body"))):
            if int(m.group(1)) not in have_part:
                bad["없는 편을 가리킴"].append(
                    f"제{x.get('no')}조({x.get('title')}) — 제{m.group(1)}편 "
                    f"(개편안은 {max(have_part)}편까지)")

    print(f"조문 {len(arts)}개에서 밖을 가리킨 인용 {n_cite}건 — "
          f"그 가운데 조 번호까지 맞대어 본 것 {n_checked}건\n")
    total = 0
    for k in sorted(bad, key=lambda k: -len(bad[k])):
        v = bad[k]
        total += len(v)
        print(f"■ {k} {len(v)}건")
        for one in (v if verbose else v[:8]):
            print(f"    {one}")
        if not verbose and len(v) > 8:
            print(f"    … 그 밖에 {len(v) - 8}건 (-v 로 모두 봅니다)")
        print()
    if unknown:
        print(f"□ 서고에 없어 맞대어 보지 못한 법령 {len(unknown)}가지 "
              f"— 틀렸다는 뜻이 아니다")
        for k, v in unknown.most_common(30 if verbose else 12):
            print(f"    {v:>2}회  {k}")
        print()
    print(f"어긋난 것 모두 {total}건")
    return total


if __name__ == "__main__":
    main()
