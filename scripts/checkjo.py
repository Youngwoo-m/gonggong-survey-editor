# -*- coding: utf-8 -*-
"""
법령 표시 없이 번호만 적은 인용이 말이 되는가 — 가리킨 조의 제목과 맞대어 본다.

reviewdraft 는 '있는 조인지' 만 본다. 번호가 이 규정 안에 있기만 하면 넘어가므로,
번호를 다시 매기면서 옛 번호가 그대로 남은 자리는 잡히지 아니한다. 그런 인용은
살아 있는 조를 가리키되 엉뚱한 조를 가리킨다 — 가장 알아채기 어려운 흠이다.

■ 어떻게 재는가

  규정 글은 무엇을 가리키는지 대개 이름으로 함께 밝힌다.

      제7조의 작업수행계획에 따라        → 제7조에 '작업수행계획' 이 있어야 한다
      제14조에 따른 기술검토위원회       → 제14조에 '기술검토위원회' 가 있어야 한다
      제47조에서 정한 허용범위           → 제47조에 '허용범위' 가 있어야 한다

  그 이름이 가리킨 조 안에 있는지 본다. 제목만 보아서는 안 된다 — 제47조는
  제목이 「공공수준점측량의 구분」이지만 제3항에서 정확도 기준을 정하므로
  제목만 맞대면 성한 것을 어긋났다 한다. 제목과 본문, 그리고 본문이 품은
  표까지 함께 본다.

■ 어림짐작이다 — 짚은 것이 곧 흠은 아니다

  말이 다르면 어긋난 것으로 본다. 「제47조에서 정한 허용범위」 는 제47조가
  「정확도 및 기지점에 대한 기준」 이라 적고 있어 글자로는 겹치지 아니하나
  가리키는 것은 같다. 짚인 것은 사람이 하나씩 보아야 한다.

  이름에 붙은 조사는 뗀다 ('허용범위를' → '허용범위'). 떼지 아니하면 글자가
  달라 늘 어긋난 것이 된다.

■ 무엇을 인용으로 보지 아니하는가 (앱의 링크 규칙과 같다)

  · 「법령 이름」 뒤에 딸린 조, 법·영·규칙 같은 약칭 뒤의 조
  · 「…규정」에 따르며, 그 규정 제20조 — 방금 든 그 규정의 조
  · <현행 제168조 「정의」> — 출처 표시에 적힌 현행 규정의 조

  이름을 밝히지 아니하고 번호만 적은 곳은 맞대어 볼 것이 없으므로 세기만 한다.

사용:  python scripts/checkjo.py [-v] [규정파일 …]
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

DOCS = [("공공측량 개편안", "draft2025.json"),
        ("성과심사 개정안", "draft_simsa.json"),
        ("무인비행장치 개정안", "draft_uav.json")]

RE_IMG = re.compile(r'<img\s+id="[\w.-]+"\s*>(?:</img>)?')
RE_PROV = re.compile(r"<현행[^<>]*>")
RE_JO = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*\d+)?"
                   r"(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?(?:\s*[가-하]목)?")
# 인용한 자리에서 그것을 무엇이라 부르는가
RE_NAME = re.compile(
    r"(?:에\s*따른|에\s*따라|에\s*의한|에\s*의하여|에서\s*정한|에서\s*정하는|"
    r"에\s*규정된|에\s*규정하는|의)\s*([가-힣][가-힣·A-Za-z0-9]{1,15})")
# 이름 끝에 붙는 조사 — 떼지 아니하면 글자가 달라 늘 어긋난 것이 된다
RE_JOSA = re.compile(r"(?:으로부터|로부터|으로서|으로|로서|로|에게|에서|에"
                     r"|을|를|은|는|의|와|과|이|가|도|만)$")
# 이름이 아닌 것 — 움직씨의 끝(제출된ㆍ고지된ㆍ규정한ㆍ적는다)과 어찌씨.
# 「제28조제3항에 따라 제출된 성과」 에서 '제출된' 은 그 조를 부르는 이름이
# 아니라 뒤에 오는 말을 꾸미는 말이다. 이것을 이름으로 잡으면 늘 어긋난다.
RE_VERBISH = re.compile(r"(?:된|한|는|다|며|여|고|자|서|던|킨|긴|힌|린)$")
ADVERB = ("반드시", "다시", "따로", "함께", "각각", "모두", "미리", "직접",
          "그대로", "아니", "이미", "곧", "우선", "특히", "다만")
CONN = r"[\s및과와,·’”\)\]]"
CHAIN = rf"(?:{CONN}*제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*제\s*\d+\s*[항호])*)*{CONN}*$"
ASIDE = r"(?:\s*[\(（][^()（）]{0,40}[\)）])?"
AFTER_CITE = re.compile(rf"[」』]{ASIDE}{CHAIN}")
AFTER_WORD = re.compile(rf"(?<![가-힣A-Za-z])(?:시행규칙|시행령|법률|법|영|규칙){CHAIN}")
AFTER_THAT = re.compile(rf"(?:그|같은|해당|당해|위)\s*(?:규정|고시|규칙|지침|기준){CHAIN}")
IN_PROV = re.compile(r"<현행(?:(?!>).)*$")
STOP = ("규정", "경우", "사항", "방법", "기준", "것", "때", "바", "자", "내용",
        "절차", "확인", "차례", "순서", "여부", "해당", "다음", "각", "결과",
        "구분", "작성", "적용", "실시", "제출", "관리", "요청", "통지")


RE_IMG_ID = re.compile(r'<img\s+id="([\w.-]+)"')
# 조가 「별표 54의 …와 같다」 처럼 별표에 미루는 일이 잦다. 그 별표를 읽지
# 아니하면, 제228조가 「제232조에 따른 무전기」 라 할 때 제232조 본문에는
# 무전기가 없어 어긋난 것이 된다. 무전기는 그 조가 부르는 별표 54 에 있다.
RE_ANX = re.compile(r"별표\s*(\d+)")
# 항까지 적은 인용 — 제28조제4항
RE_JOHANG = re.compile(r"제\s*(\d+)\s*조\s*제\s*(\d+)\s*항")
CIRCLE = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_obj = {}


def obj_text(oid):
    """본문이 품은 표의 글 — 값이 표 안에 있는 조를 성한 것으로 보려면 읽어야 한다"""
    if oid in _obj:
        return _obj[oid]
    out = ""
    for rid in ("reg01", "draft2025", "reg12", "reg11"):
        p = os.path.join(DATA, "objects", rid, oid + ".xml")
        if os.path.exists(p):
            out = " ".join(re.findall(r"<cell[^>]*>([^<]*)</cell>",
                                      io.open(p, encoding="utf-8").read()))
            break
    _obj[oid] = out
    return out


_anx = {}


def annex_xml(key):
    """별표의 서식 표 글 — annexxml_hwpx.py 가 떠 둔 것"""
    if key in _anx:
        return _anx[key]
    out = ""
    for rid in ("reg01", "draft2025", "reg29", "draftSimsa", "reg12", "draftUav"):
        p = os.path.join(DATA, "objects", rid, "annex", key + ".xml")
        if os.path.exists(p):
            out = " ".join(re.findall(r"<cell[^>]*>([^<]*)</cell>",
                                      io.open(p, encoding="utf-8").read()))
            break
    _anx[key] = out
    return out


def clean(t):
    return RE_IMG.sub("", str(t or ""))


def grams(s):
    s = re.sub(r"[\s·()]", "", str(s or ""))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def articles(path):
    d = json.load(io.open(path, encoding="utf-8"))
    trees = [d["tree"]] if d.get("tree") else [v.get("tree") or []
                                               for v in (d.get("versions") or [])]
    out = []
    for t in trees:
        def rec(ns):
            for x in ns:
                out.append(x)
                rec(x.get("children") or [])
        rec(t)
    return out


def audit(path):
    A = articles(path)
    arts = [x for x in A if x.get("level") == "조" and not x.get("isDeleted")]
    title = {}
    for x in arts:
        title.setdefault(int(x["no"]), x.get("title") or "")
    # 제목만이 아니라 본문까지 담는다 — 무엇을 정하는 조인지는 본문에 있다
    full = {}
    for x in arts:
        n = int(x["no"])
        body = x.get("body") or ""
        tbl = "".join(obj_text(oid) for oid in RE_IMG_ID.findall(body))
        full[n] = full.get(n, "") + re.sub(r"[\s·()]", "",
                                           (x.get("title") or "") + clean(body) + tbl)

    # 조가 부르는 별표의 글을 그 조에 얹는다.
    # 별표의 속은 본문(body)에만 있는 것이 아니다 — 표가 있는 별표는
    # data\objects\<규정>nnex\<열쇠>.xml 에 담겨 있고 본문은 비어 있다.
    # 그것을 읽지 아니하면 「제232조에 따른 무전기」 처럼, 별표에 참말 있는
    # 말을 없다고 짚는다.
    anx = {}
    for x in A:
        a = x.get("annexRef") or {}
        if a.get("gubun") == "별표" and a.get("no"):
            key = re.sub(r"\s+", "", str(x.get("legacyNo")
                                         or "별표%s" % a["no"]))
            anx[str(a["no"])] = re.sub(
                r"[\s·()]", "",
                (x.get("title") or "") + clean(x.get("body")) + annex_xml(key))
    for k in list(full):
        for no in set(RE_ANX.findall(full[k])):
            full[k] += anx.get(no, "")

    # 조마다 항이 몇 개인가 — 짐작이 아니라 셀 수 있는 것이다
    nhang = {}
    for x in arts:
        b = clean(x.get("body"))
        k = 0
        for i, c in enumerate(CIRCLE, 1):
            if c in b:
                k = i
        nhang[int(x["no"])] = k

    n_ref = n_named = 0
    bad, soft, unnamed, nohang = [], [], 0, []
    for x in arts:
        body = clean(x.get("body"))
        for m in RE_JO.finditer(body):
            n = int(m.group(1))
            if n not in title:
                continue                       # 없는 조는 reviewdraft 가 본다
            before = body[:m.start()]
            if (AFTER_CITE.search(before) or AFTER_WORD.search(before)
                    or AFTER_THAT.search(before) or IN_PROV.search(before)):
                continue                       # 남의 조를 가리킨 자리
            # 없는 항을 가리키는가 — 짐작이 아니므로 따로 센다
            hm = RE_JOHANG.match(m.group(0))
            if hm:
                want = int(hm.group(2))
                have = nhang.get(n, 0)
                if have and want > have:
                    nohang.append((x.get("no"), x.get("title"), n, title[n],
                                   want, have))
            n_ref += 1
            nm = RE_NAME.match(body[m.end():])
            if not nm:
                unnamed += 1
                continue
            name = nm.group(1).strip()
            for _ in range(2):
                name = RE_JOSA.sub("", name)
            if (len(name) < 2 or name in STOP or name in ADVERB
                    or RE_VERBISH.search(name)):
                unnamed += 1
                continue
            n_named += 1
            key = re.sub(r"[\s·()]", "", name)
            if key in full.get(n, ""):
                continue                       # 그 조 안에 있다 — 말이 된다
            # 그 이름이 있는 조가 따로 있는가 (번호가 밀린 자국)
            # 인용한 조 스스로는 빼고 본다 — 제 본문에 있는 말이라 늘 걸린다
            me = int(x["no"])
            best = [k for k, t in full.items() if k not in (n, me) and key in t]
            row = (x.get("no"), x.get("title"), n, title[n], name, best[:3])
            # 글자가 아주 어긋난 것과, 말만 다른 것을 갈라 놓는다.
            # 「요구정밀」 은 제82조제3항의 「허용 정밀도」 를 가리킨 것이라
            # 두 글자씩 끊어 보면 '정밀' 이 겹친다. 가리킨 자리는 맞고
            # 낱말만 다른 것이니 따로 모아 보인다.
            if grams(key) & grams(full.get(n, "")):
                soft.append(row)
            else:
                bad.append(row)
    return len(arts), n_ref, n_named, unnamed, bad, soft, nohang


def main():
    verbose = "-v" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    total = 0
    for lbl, f in DOCS:
        if only and f not in only:
            continue
        p = os.path.join(DATA, f)
        if not os.path.exists(p):
            continue
        n_a, n_ref, n_named, unnamed, bad, soft, nohang = audit(p)
        total += len(bad) + len(nohang)
        print(f"■ {lbl} — 조 {n_a}개 · 번호만 적은 인용 {n_ref}곳 "
              f"(이름을 함께 밝힌 것 {n_named} · 밝히지 아니한 것 {unnamed})")
        if nohang:
            print(f"    ★ 없는 항을 가리킨 것 {len(nohang)}건")
            for no, ti, tgt, ttl, want, have in nohang:
                print(f"        제{no}조({ti}) — 제{tgt}조제{want}항 을 가리키나,"
                      f" 제{tgt}조(「{ttl}」) 는 제{have}항까지다")
        if not bad and not soft and not nohang:
            print("    맞대어 본 것은 모두 맞습니다.\n")
            continue
        if not bad:
            print("    아주 어긋난 것은 없습니다.")
        else:
            print(f"    가리킨 조에 그 말이 없는 것 {len(bad)}건")
        for no, ti, tgt, ttl, name, best in (bad if verbose else bad[:8]):
            more = ("  → 더 맞는 조: "
                    + ", ".join(f"제{b}조" for b in best)) if best else ""
            print(f"        제{no}조({ti}) — 「{name}」 라 하며 제{tgt}조 를 가리키나,"
                  f" 제{tgt}조 는 「{ttl}」 다{more}")
        if not verbose and len(bad) > 8:
            print(f"        … 그 밖에 {len(bad) - 8}건 (-v 로 모두 봅니다)")
        if soft:
            print(f"    말만 다른 것 {len(soft)}건 — 가리킨 자리는 맞아 보인다")
            for no, ti, tgt, ttl, name, best in (soft if verbose else soft[:5]):
                print(f"        제{no}조({ti}) — 「{name}」 라 하며 제{tgt}조"
                      f"(「{ttl}」) 를 가리킴")
            if not verbose and len(soft) > 5:
                print(f"        … 그 밖에 {len(soft) - 5}건 (-v 로 모두 봅니다)")
        print()
    print(f"모두 {total}건")
    return total


if __name__ == "__main__":
    main()
