# -*- coding: utf-8 -*-
r"""화살표를 걷으면서 짝짓기가 흐려진 줄을 바로잡는다.

■ 무슨 일이 있었나

  변경 사유에서 화살표(→)를 걷어 낼 때, 'A → B' 는 'A 를 B 로' 로 풀고
  풀기 어려운 것은 쉼표로 늘어놓았다. 그런데 쉼표로 늘어놓으면 **짝이
  목록으로 읽히는** 자리가 있었다.

      전 : 조 번호만 제4조 → 제5조로 바뀐다
      후 : 조 번호만 제4조, 제5조로 바뀐다      ← 두 조를 나열한 것으로 읽힌다
      참 : 조 번호만 제4조에서 제5조로 바뀐다

  세 가지 꼴이 그러하다.

      ① 조 번호 갈이   제4조 → 제5조로 바뀐다
      ② 예상 반론      (우려) … → (답) …
      ③ 규정 이름 갈이 「옛 이름」 → 「새 이름」 (고시 제0000-0000호)

  ①은 '에서' 를 넣고, ②는 마침표에서 줄을 나누며, ③은 '가 … 로 이름이
  바뀜' 으로 푼다.

  python scripts\arrowfix.py            바꿔 본 것을 보여만 준다
  python scripts\arrowfix.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import gaejosik as G                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# ① 조 번호 갈이 — '제4조, 제5조로 바뀜' 을 '제4조에서 제5조로 바뀜' 으로
RE_JO = re.compile(
    r"(제\s*\d+조(?:제\s*\d+항)?(?:제\s*\d+호)?)\s*,\s*"
    r"(제\s*\d+조(?:제\s*\d+항)?(?:제\s*\d+호)?(?:로|으로))"
    r"(\s*(?:바뀜|바뀐다|고침|고친다))")

# ② 예상 반론 — '(우려) … , (답) …' 을 두 줄로
RE_BAN = re.compile(r"^(.*?\(우려\)\s*.+?)\s*,\s*(\(답\)\s*.+)$")

# ③ 규정 이름 갈이 — 「옛」, 「새」 (고시 …)
RE_NAME = re.compile(
    r"^(「[^」]+」)\s*,\s*(「[^」]+」(?:\s*\([^()]*\))?)\s*\.?$")

# 앞서 문체를 정비할 때 「이름씨+이다」를 움직씨로 보아 망가진 끝맺음.
# 뿌리는 gaejosik.py 에서 고쳤고, 자료에 남은 자국은 여기서 되돌린다.
#   요구다 → 요굼 (참: 요구임)   길을 연다 → 염 (참: 엶)
TAILFIX = [
    (r"(?<=[ 가-힣])요굼\.$", "요구임."),
    (r"(?<=[ 가-힣])범윔\.$", "범위임."),
    (r"(?<=[ 가-힣])잣댐\.$", "잣대임."),
    (r"(?<=[ 가-힣])심삼\.$", "심사임."),
    (r"(?<=[ 가-힣])조섬\.$", "조서임."),
    (r"(?<=[ 가-힣])뼈댐\.$", "뼈대임."),
    (r"(?<=[ 가-힣])통롐\.$", "통례임."),
    (r"(?<=[ 가-힣])근검\.$", "근거임."),
    (r"(?<= )푬\.$", "표임."),
    (r"(?<=\d)좀\.$", "조임."),
    (r"(?<= )염\.$", "엶."),
    (r"(?<= )암\.$", "앎."),
    (r"(?<=[ 가-힣])갖음\.$", "가짐."),
    (r"(?<=[ 가-힣])그렇음\.$", "그러함."),
]

# 손으로 다듬는 자리 — 규칙으로 가리기 어려운 셋
HAND = [
    ("연구 검토 결과 기술 진부화 — 래스터, 벡터 자동화 기술은",
     "연구 검토 결과 기술 진부화 — 래스터를 벡터로 바꾸는 자동화 기술은"),
    ("옮기면서 다듬은 것은 글자가 깨진 자리뿐이다 — "
     "'1 2㎝', '12㎝', '0. 08', '0.08', '1 /250', '1/250', '1 . 30', '1.30'.",
     "옮기면서 다듬은 것은 글자가 깨진 자리뿐임. "
     "'1 2㎝' 은 '12㎝' 로, '0. 08' 은 '0.08' 로, "
     "'1 /250' 은 '1/250' 로, '1 . 30' 은 '1.30' 으로 바로잡음."),
    ("성과심사 수수료는 법 제106조제1항제5호, 시행규칙 제115조제2항, "
     "별표 5이 산정방법을 정함",
     "성과심사 수수료는 법 제106조제1항제5호에서 시행규칙 제115조제2항으로, "
     "다시 별표 5로 위임되어 별표 5가 산정방법을 정함"),
]


def repair(line):
    """한 줄 → 바로잡은 여러 줄 (바꿀 것이 없으면 [원래 줄])"""
    s = line.rstrip()
    mark = ""
    m = re.match(r"^(\s*[*○]\s*)(.*)$", s)
    if m:
        mark, s = m.group(1), m.group(2)

    for a, b in HAND:
        if a in s:
            s = s.replace(a, b)

    for pat, to in TAILFIX:
        s = re.sub(pat, to, s)

    s = RE_JO.sub(lambda m: "%s에서 %s%s" % (m.group(1), m.group(2), m.group(3)), s)

    m = RE_NAME.match(s)
    if m:
        s = "%s 가 %s 로 이름이 바뀜." % (m.group(1), m.group(2))

    m = RE_BAN.match(s)
    if m:
        head = G._one(m.group(1)).strip()
        tail = G._one(m.group(2)).strip()
        return [mark + head, mark + tail]

    # 마침표가 여럿이면 개조식대로 줄을 나눈다
    out = [t for t in G.endify(s) if t]
    return [mark + t for t in out] if out else [mark + s]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    shown = 0
    total = 0
    for f in sorted(x for x in os.listdir(DATA)
                    if x.startswith("draft") and x.endswith(".json")):
        p = os.path.join(DATA, f)
        d = json.load(io.open(p, encoding="utf-8"))
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                r = x.get("reason")
                if not r:
                    continue
                out = []
                for ln in str(r).split("\n"):
                    s = ln.strip()
                    if not s or s == "[변경 사유]" or s.endswith(":"):
                        out.append(ln)
                        continue
                    got = repair(ln)
                    if got != [ln.rstrip()]:
                        total += 1
                        if shown < 40:
                            shown += 1
                            print("  전 : " + ln.strip()[:150])
                            for g in got:
                                print("  후 : " + g.strip()[:150])
                            print()
                    out.extend(got)
                new = "\n".join(out)
                if new != r:
                    x["reason"] = new
        if write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False))
    print("바로잡은 줄 %d개" % total)
    if not write:
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
