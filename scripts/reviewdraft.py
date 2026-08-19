# -*- coding: utf-8 -*-
"""
개편안 전체 조문 검토 — 번호를 다시 매긴 뒤 어긋난 데가 없는지 훑는다.

  1) 조 번호가 1부터 끊김 없이 이어지는지
  2) 본문이 가리키는 '제○조' 가 실제로 있는 조인지, 그 조가 말이 되는지
  3) 본문이 빈 조문, 제목이 겹치는 조문
  4) '별표 ○에서 정한다' 로 위임한 것과 실제 별표 목록의 짝
  5) 상태 표시와 변경 사유 세 도막의 완비

사용:  python scripts/reviewdraft.py
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
RE_JO = re.compile(r"제\s*(\d+)\s*조")
# 별표 31 · 별지 제3호 서식 — 두 표기를 모두 읽는다
RE_ANX = re.compile(r"(별표|별지)\s*(?:제\s*)?(\d+)\s*(?:호\s*서식)?")


def main():
    doc = json.load(io.open(os.path.join(DATA, "draft2025.json"), encoding="utf-8"))
    tree = doc.get("tree") or doc["versions"][0]["tree"]

    arts, annex, path = [], [], []

    def rec(ns, part="", chap=""):
        for x in ns:
            if x.get("isDeleted"):      # 없앤 것을 모아 둔 묶음은 세지 않는다
                continue
            lv = x.get("level")
            p = x.get("title") if lv == "편" else part
            c = x.get("title") if lv == "장" else chap
            if lv == "조":
                (annex if x.get("annexRef") else arts).append((x, p, c))
            rec(x.get("children") or [], p, c)
    rec(tree)

    print(f"조문 {len(arts)}개 · 별표·별지 {len(annex)}개\n")
    bad = collections.defaultdict(list)

    # 1) 번호 이어짐
    nos = [a[0].get("no") for a in arts]
    for i, no in enumerate(nos, start=1):
        if no != i:
            bad["번호 어긋남"].append(f"{i}번째 조문의 번호가 제{no}조")
            break
    print(f"1. 번호  제{nos[0]}조 ~ 제{nos[-1]}조 · 끊김 {len(bad['번호 어긋남'])}건")

    # 2) 본문이 가리키는 조
    have = {a[0].get("no") for a in arts}
    title_of = {a[0].get("no"): a[0].get("title") for a in arts}
    refs = 0
    for x, p, c in arts:
        body = x.get("body") or ""
        # 출처 표시와 표·수식 표식은 본문의 인용이 아니다
        #   <현행 제84조 「기준도」> · <img id="…"></img>
        body = re.sub(r"<[^<>]*>", " ", body)
        # 다른 법령을 가리키는 것은 뺀다 — 「…법」 제7조 · 법 제7조 · 같은 법 시행령 제2조
        # 법 이름과 조 번호 사이에 '(이하 "법"이라 한다)' 가 끼어드는 경우가 있다
        body = re.sub(r"[「『][^」』]{2,40}[」』]\s*(?:\([^()]{0,40}\)\s*)?"
                      r"(?:제\s*\d+\s*조(?:의\s*\d+)?"
                      r"(?:\s*제\s*\d+\s*[回号項号]?)*[,·\s]*)+", " ", body)
        body = re.sub(r"(?:같은\s*법|같은\s*항|법|令|後|規則|施行令|施行規則|시행령|시행규칙|법|영|규칙)"
                      r"\s*제\s*\d+\s*조(?:의\s*\d+)?", " ", body)
        for m in RE_JO.finditer(body):
            n = int(m.group(1))
            refs += 1
            if n not in have:
                bad["없는 조 인용"].append(f"제{x['no']}조({x['title']}) → 제{n}조")
            elif n == x.get("no"):
                bad["제 조문 인용"].append(f"제{x['no']}조({x['title']})")
    print(f"2. 인용  조문 사이 인용 {refs}곳 · 없는 조 {len(bad['없는 조 인용'])}건 "
          f"· 제 조문을 가리킴 {len(bad['제 조문 인용'])}건")

    # 3) 빈 본문·겹치는 제목
    empty = [f"제{x['no']}조({x['title']})" for x, p, c in arts if not (x.get("body") or "").strip()]
    dup = collections.Counter((x.get("title"), p) for x, p, c in arts)
    dups = [f"{t}({p})×{n}" for (t, p), n in dup.items() if n > 1]
    print(f"3. 본문  빈 조문 {len(empty)}건 · 한 편 안에서 제목이 겹치는 것 {len(dups)}건")

    # 4) 별표 위임과 실제 별표
    anx_have = set()
    for x, p, c in annex:
        m = RE_ANX.search(str(x.get("legacyNo") or ""))
        if m:
            anx_have.add((m.group(1), int(m.group(2))))
    miss = set()
    for x, p, c in arts:
        for g, n in RE_ANX.findall(x.get("body") or ""):
            if (g, int(n)) not in anx_have:
                miss.add(f"제{x['no']}조 → {g} {n}")
    print(f"4. 별표  본문이 가리키는 별표·별지 가운데 목록에 없는 것 {len(miss)}건")

    # 5) 상태와 사유
    st = collections.Counter(x.get("status") for x, p, c in arts)
    noreason = [f"제{x['no']}조" for x, p, c in arts if not (x.get("reason") or "").strip()]
    part3 = sum(1 for x, p, c in arts
                if all(k in (x.get("reason") or "") for k in ("현행 규정", "관련 근거", "개정 사유")))
    print(f"5. 상태  {dict(st)}")
    print(f"   사유  세 도막 갖춘 것 {part3}/{len(arts)} · 사유 없는 것 {len(noreason)}건")

    # 6) 별표·별지 자체 검토
    print("\n[별표·별지]")
    gnum = collections.defaultdict(list)
    for x, p_, c_ in annex:
        m = RE_ANX.search(str(x.get("legacyNo") or ""))
        if m:
            gnum[m.group(1)].append((int(m.group(2)), x))
    for g, lst in gnum.items():
        lst.sort()
        ns = [n for n, _ in lst]
        gap = [i for i in range(1, max(ns) + 1) if i not in ns] if ns else []
        print(f"  {g} {len(lst)}종 · {g} 1 ~ {max(ns)} · 빠진 번호 {gap or '없음'}")
        names = collections.Counter((x.get("title") or "").strip() for _, x in lst)
        bad["별표 이름 겹침"] += [f"{t}×{n}" for t, n in names.items() if n > 1]
        bad["파일도 내용도 없음"] += [
            f"{g} {n}({x.get('title')})" for n, x in lst
            if not (x.get("annexRef") or {}).get("hwp")
            and not (x.get("annexRef") or {}).get("pdf")
            and not (x.get("body") or "").strip()]
        bad["사유 없음"] += [f"{g} {n}" for n, x in lst if not (x.get("reason") or "").strip()]

    # 어느 조문도 가리키지 아니하는 별표
    #   조문이 본문에 품은 표(<img id="t4317">) 안에서 가리키는 것도 인용이다.
    #   표만 보고 별표를 고르게 한 조문이 있어, 본문 글자만 훑으면 그 별표가
    #   아무도 가리키지 아니하는 것으로 잘못 잡힌다.
    obj_dir = os.path.join(DATA, "objects", "reg01")

    def obj_text(oid):
        f = os.path.join(obj_dir, f"{oid}.xml")
        if not os.path.exists(f):
            return ""
        return re.sub(r"<[^>]+>", " ", io.open(f, encoding="utf-8").read())

    #   별표가 다른 별표를 가리키는 것도 인용이다 — 조문이 「성과 유형별 성과패키지의
    #   구성」 을 위임하고, 그 별표가 개별 서식을 가리키는 사슬이 있다.
    cited = set()
    for x, p_, c_ in arts + annex:
        body = x.get("body") or ""
        seen_text = [body] + [obj_text(o) for o in
                              re.findall(r'<img\s+id="([\w.-]+)"', body)]
        for g, n in RE_ANX.findall(" ".join(seen_text)):
            cited.add((g, int(n)))
    # 제목이 '(…안)' 으로 끝나는 것은 아직 채택하지 아니한 안이므로, 조문이 가리키지
    # 아니하는 것이 옳다. 지적으로 세지 아니하고 따로 알린다.
    RE_DRAFT = re.compile(r"\([^)]*안\)\s*$")
    orphan, draft_only = [], []
    for g, lst in gnum.items():
        for n, x in lst:
            if (g, n) in cited:
                continue
            label = f"{g} {n}({x.get('title')})"
            (draft_only if RE_DRAFT.search(x.get("title") or "")
             else orphan).append(label)
    print(f"  규정 어디에서도 가리키지 아니하는 것 {len(orphan)}종"
          + (f" · 채택 전의 안 {len(draft_only)}종" if draft_only else ""))
    for one in draft_only:
        print(f"    (안) {one} — 채택 전이므로 가리키는 곳이 없다")
    bad["가리키는 곳 없음"] += orphan

    print("\n[지적]")
    n = 0
    for k, v in bad.items():
        for one in v[:8]:
            print(f"  {k}: {one}"); n += 1
        if len(v) > 8:
            print(f"  … {k} 그 밖에 {len(v) - 8}건"); n += len(v) - 8
    for one in empty[:5]:
        print(f"  빈 본문: {one}"); n += 1
    for one in dups[:5]:
        print(f"  제목 겹침: {one}"); n += 1
    for one in sorted(miss)[:5]:
        print(f"  없는 별표: {one}"); n += 1
    if not n:
        print("  없음")
    print(f"\n모두 {n}건")


if __name__ == "__main__":
    main()
