# -*- coding: utf-8 -*-
"""개정안을 데이터에서 곧바로 훑는다.

화면의 [✓검증]은 규정 한 종을 놓고 도는 규칙들이다(조번호ㆍ계층ㆍ인용ㆍ용어).
여기서는 그것이 보지 아니하는 자리를 함께 본다 — 판(버전)마다, 별표까지,
그리고 상태ㆍ사유ㆍ파일이 서로 맞는지.

  1. 조번호   중복ㆍ끊김ㆍ가지조
  2. 계층     편ㆍ장ㆍ절ㆍ관ㆍ조의 차례
  3. 별표     번호 끊김ㆍ중복ㆍ제목 겹침ㆍ빈 본문
  4. 인용     이 규정 안의 제○조ㆍ별표를 부르는데 그것이 있는가
  5. 상태     신설인데 현행번호가 있거나, 이동인데 없는가
  6. 파일     별표마다 hwp ㆍ pdf 가 실제로 있는가
  7. 사유     변경 사유가 비어 있는가
  8. 부칙     시행일이 있는가

사용:  python scripts/verifydraft.py [--full]
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TARGETS = [("draft2025.json", "작업규정"),
           ("draft_simsa.json", "성과심사 규정"),
           ("draft_uav.json", "무인비행장치 규정")]

LEVELS = ["편", "장", "절", "관", "조"]

# 다른 법령의 조ㆍ별표를 가리키는 자리 — 이 규정의 것으로 보지 아니한다.
#
# 첫 판은 인용 앞 30자만 보았다. 그래서 「…법률」 제15조제4항, 제18조제5항 및
# 제105조제2항 처럼 이음말로 길게 이어진 자리에서 뒤엣것을 이 규정의 조로
# 잘못 잡아, 성과심사 규정에서만 여덟을 헛짚었다.
#
# 화면의 검증기(js/core/objects.js 의 isSelfCite)는 이음말과 나열을 규칙에
# 담아 사슬로 좇는다. 여기서도 같은 방식을 쓴다 — 두 벌이 갈리면 화면과
# 스크립트의 결과가 서로 어긋난다.
CONN = "[\\s및과와,·ㆍ∙•･・’”\\)\\]]"
RANGE = "(?:부터|까지|내지)"
CONN2 = "(?:%s|%s)" % (CONN, RANGE)
ITEM = ("(?:제\\s*\\d+\\s*조(?:의\\s*\\d+)?(?:\\s*제\\s*\\d+\\s*[항호])*"
        "|(?:별표|별지)\\s*제?\\s*\\d+\\s*(?:호(?:\\s*서식)?)?)")
CHAIN = "(?:%s*%s)*%s*$" % (CONN2, ITEM, CONN2)
ASIDE = "(?:\\s*[\\(（][^()（）]{0,40}[\\)）])?"

OTHER = re.compile(
    "(?:[「『][^」』]{2,60}[」』]%s%s"                                  # 「○○법」(이하…) 제2조 및 …
    "|(?<![가-힣A-Za-z])(?:시행규칙|시행령|법률|법|영|규칙|고시|준칙)%s"   # 시행령 제34조 및 …
    "|(?:그|같은|해당|당해|위)\\s*(?:법|규정|고시|규칙|지침|기준)%s"       # 같은 법 제18조 및 …
    "|현행\\s*%s)" % (ASIDE, CHAIN, CHAIN, CHAIN, CHAIN))

RE_JO = re.compile(r"제\s*(\d+)\s*조")
RE_ANX = re.compile(r"(별표|별지)\s*제?\s*(\d+)")


def walk(ns, f, parent=None, path=()):
    for n in ns:
        f(n, parent, path)
        walk(n.get("children") or [], f, n, path + (n,))


def revisions(doc):
    out = [(doc.get("title") or "본판", doc["tree"])]
    for r in (doc.get("next") or []):
        out.append((r.get("title") or "다음 판", r["tree"]))
    return out


def check(regname, revname, tree):
    bad = []

    def add(lv, code, msg):
        bad.append((lv, code, msg))

    jos, anx, all_nodes = [], [], []

    def collect(n, parent, path):
        all_nodes.append((n, parent, path))
        if n.get("annexRef"):
            anx.append(n)
        elif n.get("level") == "조" and n.get("status") != "삭제":
            # 삭제한 조는 번호를 지우고 '삭제' 묶음에 모아 두므로 셈에서 뺀다 —
            # 그러지 아니하면 번호 없는 그것들이 모두 '제0조 중복' 으로 잡힌다
            jos.append(n)

    walk(tree, collect)

    # ---------------------------------------------------------------- 1 조번호
    seen = collections.Counter()
    for n in jos:
        key = (n.get("no"), n.get("branch") or 0)
        seen[key] += 1
    for (no, br), k in seen.items():
        if k > 1:
            add("오류", "조번호중복", "제%s조%s 가 %d번 있다" % (
                no, ("의%s" % br) if br else "", k))
    nums = sorted({n["no"] for n in jos if n.get("no")})
    if nums:
        miss = [x for x in range(1, max(nums) + 1) if x not in set(nums)]
        if miss:
            add("오류", "조번호끊김", "빠진 조 %d개 — %s%s" % (
                len(miss), ", ".join("제%d조" % x for x in miss[:14]),
                " …" if len(miss) > 14 else ""))

    # ---------------------------------------------------------------- 2 계층
    for n, parent, path in all_nodes:
        lv = n.get("level")
        if not lv or lv not in LEVELS or n.get("annexRef"):
            continue
        if parent and parent.get("level") in LEVELS:
            if LEVELS.index(lv) <= LEVELS.index(parent["level"]):
                add("오류", "계층위반", "%s 안에 %s 가 들어 있다 (%s)" % (
                    parent["level"], lv, (n.get("title") or "")[:26]))

    # ---------------------------------------------------------------- 3 별표
    for gubun in ("별표", "별지"):
        got = [n for n in anx if (n["annexRef"].get("gubun") or "별표") == gubun]
        ns = []
        for n in got:
            try:
                ns.append(int(n["annexRef"]["no"]))
            except (TypeError, ValueError):
                add("오류", "별표번호", "%s 번호가 숫자가 아니다 — %r" % (gubun, n["annexRef"].get("no")))
        c = collections.Counter(ns)
        for no, k in c.items():
            if k > 1:
                add("오류", "별표중복", "%s %d 이(가) %d번 있다" % (gubun, no, k))
        if ns:
            miss = [x for x in range(1, max(ns) + 1) if x not in set(ns)]
            if miss:
                add("오류", "별표끊김", "%s 번호가 끊겼다 — %s" % (
                    gubun, ", ".join(str(x) for x in miss[:14])))
        t = collections.Counter((n.get("title") or "").strip() for n in got)
        for name, k in t.items():
            if k > 1 and name:
                add("경고", "별표제목겹침", "%s 제목이 같은 것 %d건 — %s" % (gubun, k, name[:38]))
        for n in got:
            if not (n.get("body") or "").strip() and n.get("status") == "신설":
                add("경고", "별표빈본문", "%s %s 은 신설인데 내용이 비었다 — %s" % (
                    gubun, n["annexRef"]["no"], (n.get("title") or "")[:34]))

    # ---------------------------------------------------------------- 4 인용
    live_jo = {n["no"] for n in jos if n.get("no")}
    live_anx = {(n["annexRef"].get("gubun") or "별표", str(n["annexRef"]["no"])) for n in anx}
    for n in all_nodes:
        node = n[0]
        s = node.get("body") or ""
        if not s or node.get("annexRef"):
            continue
        for m in RE_JO.finditer(s):
            if OTHER.search(s[:m.start()]):
                continue
            if int(m.group(1)) not in live_jo:
                add("오류", "없는조인용", "%s 가 제%s조를 부르는데 그런 조가 없다" % (
                    label(node), m.group(1)))
        for m in RE_ANX.finditer(s):
            if OTHER.search(s[:m.start()]):
                continue
            if (m.group(1), m.group(2)) not in live_anx:
                add("오류", "없는별표인용", "%s 가 %s %s 을(를) 부르는데 그런 것이 없다" % (
                    label(node), m.group(1), m.group(2)))

    # 불려지지 아니하는 별표 — 조문과 다른 별표의 글을 모두 훑는다
    body_all = "\n".join((n.get("body") or "") for n, _p, _t in all_nodes)
    cited = {(m.group(1), m.group(2)) for m in RE_ANX.finditer(body_all)}
    orphan = [x for x in sorted(live_anx) if x not in cited]
    if orphan:
        add("경고", "안불리는별표", "어디에서도 부르지 아니하는 것 %d건 — %s" % (
            len(orphan), ", ".join("%s %s" % o for o in orphan[:12])))

    # ---------------------------------------------------------------- 5 상태
    for n, _p, _t in all_nodes:
        st, lg = n.get("status"), (n.get("legacyNo") or "").strip()
        if not st or st == "유지":
            continue
        # 신설 별표의 legacyNo 는 '현행 번호' 가 아니라 미리보기 그림을 찾는
        # 열쇠다 — 번호를 다시 매겨도 그림이 어긋나지 않게 하려는 것이다
        # (js/ui/detail.js 의 _annexPreview). 그러므로 조문일 때에만 짚는다.
        if st == "신설" and lg and not n.get("annexRef"):
            add("경고", "상태어긋남", "%s 는 신설인데 현행번호(%s)가 있다" % (label(n), lg))
        if st in ("이동", "이동·수정") and not lg:
            add("경고", "상태어긋남", "%s 는 이동인데 현행번호가 없다" % label(n))

    # ---------------------------------------------------------------- 6 파일
    for n in anx:
        a = n["annexRef"]
        for k in ("hwp", "pdf"):
            v = a.get(k)
            if not v:
                add("경고", "파일없음", "%s %s 에 %s 가 걸려 있지 않다" % (
                    a.get("gubun"), a.get("no"), k.upper()))
            elif not v.startswith("http") and not os.path.exists(os.path.join(ROOT, v)):
                add("오류", "파일깨짐", "%s %s 의 %s 길이 가리키는 파일이 없다 — %s" % (
                    a.get("gubun"), a.get("no"), k.upper(), v))

    # ---------------------------------------------------------------- 7 사유
    n_noreason = sum(1 for n, _p, _t in all_nodes
                     if n.get("status") in ("신설", "수정", "이동·수정", "삭제")
                     and not (n.get("reason") or "").strip())
    if n_noreason:
        add("경고", "사유없음", "고친다고 표시하고 변경 사유가 빈 것 %d건" % n_noreason)

    # ---------------------------------------------------------------- 8 부칙
    txt = "\n".join((n.get("title") or "") + (n.get("body") or "") for n, _p, _t in all_nodes)
    if "부칙" not in txt:
        add("경고", "부칙없음", "부칙이 보이지 아니한다 — 시행일을 정해야 한다")

    return bad, len(jos), len(anx)


def label(n):
    if n.get("annexRef"):
        a = n["annexRef"]
        return "%s %s" % (a.get("gubun"), a.get("no"))
    if n.get("no"):
        return "제%s조%s" % (n["no"], ("의%s" % n["branch"]) if n.get("branch") else "")
    return (n.get("title") or "")[:24]


if __name__ == "__main__":
    full = "--full" in sys.argv
    grand = collections.Counter()
    for fname, regname in TARGETS:
        doc = json.load(io.open(os.path.join(DATA, fname), encoding="utf-8"))
        for revname, tree in revisions(doc):
            bad, njo, nanx = check(regname, revname, tree)
            c = collections.Counter(b[0] for b in bad)
            grand.update(c)
            print("═" * 78)
            print("%s — %s   (조 %d · 별표ㆍ별지 %d)" % (regname, revname[:44], njo, nanx))
            print("   오류 %d · 경고 %d" % (c.get("오류", 0), c.get("경고", 0)))
            if not bad:
                print("   탈난 데 없음")
            by = collections.OrderedDict()
            for lv, code, msg in bad:
                by.setdefault((lv, code), []).append(msg)
            for (lv, code), msgs in by.items():
                print("   [%s] %s — %d건" % (lv, code, len(msgs)))
                for m in (msgs if full else msgs[:4]):
                    print("        · %s" % m)
                if not full and len(msgs) > 4:
                    print("        · … 그 밖에 %d건 (--full 로 모두 보기)" % (len(msgs) - 4))
    print("═" * 78)
    print("모두 합쳐 — 오류 %d · 경고 %d" % (grand.get("오류", 0), grand.get("경고", 0)))
