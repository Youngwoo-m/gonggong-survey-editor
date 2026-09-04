# -*- coding: utf-8 -*-
r"""변경 사유를 개조식으로 — 문장 끝을 '~음/~임/~함/~필요함' 으로 맺는다.

■ 왜

  보고서에 실리는 개정 사유는 개조식으로 쓰고 명사형으로 맺는 것이 관례다.
  그런데 자료에 쌓인 사유는 '~한다 / ~된다 / ~고쳤다' 처럼 줄글 체다.

■ 어떻게

  한국어의 명사형은 어간에 -(으)ㅁ 을 붙여 만든다.

      받침이 없으면  어간에 ㅁ 을 받쳐 쓴다      되다 → 됨, 하다 → 함
      받침이 있으면  어간에 '음' 을 붙인다        있다 → 있음, 같다 → 같음

  다만 불규칙이 있어(어렵다 → 어려움, 만들다 → 만듦) 규칙만으로는 어긋난다.
  그래서 자주 나오는 끝맺음은 표로 못박고, 표에 없는 것만 규칙으로 만든다.
  표에도 규칙에도 걸리지 않으면 **손대지 아니한다** — 어설프게 바꾸느니
  그대로 두는 편이 낫다.

■ 기호

  가운데점(·)과 화살표(→)는 쓰지 아니한다. 가운데점은 쉼표로 바꾸고,
  화살표는 'A 를 B 로' 로 풀어 쓴다.

  python scripts\gaejosik.py --check      바꿔 본 것을 보여만 준다
  python scripts\gaejosik.py --write      자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

MID = chr(183)          # ·
ARROW = chr(8594)       # →
MID2 = chr(0x318D)      # ㆍ  아래아 — 가운데점 자리에 섞여 쓰이고 있다

# 자주 나오는 끝맺음 — 규칙보다 앞선다 (불규칙과 과거형을 여기서 잡는다)
TAIL = [
    # 쓰기로 정한 낱말 — 규칙보다 먼저 맞춰 본다
    ("옮겼다", "이동"), ("옮긴다", "이동"), ("옮김", "이동"),
    ("냈다", "냄"), ("낸다", "냄"),
    ("따랐다", "따름"), ("따른다", "따름"),
    ("어렵다", "어려움"),
    ("아니한다", "아니함"), ("아니된다", "아니됨"), ("아니다", "아님"),
    ("하였다", "함"), ("했다", "함"), ("한다", "함"),
    ("되었다", "됨"), ("됐다", "됨"), ("된다", "됨"),
    ("이었다", "이었음"), ("였다", "였음"), ("이다", "임"),
    ("있었다", "있었음"), ("있다", "있음"),
    ("없었다", "없었음"), ("없다", "없음"),
    ("옮겼다", "옮김"), ("옮긴다", "옮김"),
    ("고쳤다", "고침"), ("고친다", "고침"),
    ("바뀌었다", "바뀜"), ("바뀐다", "바뀜"),
    ("두었다", "둠"), ("둔다", "둠"),
    ("넣었다", "넣음"), ("넣는다", "넣음"),
    ("뺐다", "뺌"), ("뺀다", "뺌"),
    ("붙였다", "붙임"), ("붙인다", "붙임"),
    ("남았다", "남음"), ("남는다", "남음"),
    ("짰다", "짬"), ("짠다", "짬"),
    ("썼다", "씀"), ("쓴다", "씀"),
    ("만들었다", "만듦"), ("만든다", "만듦"),
    ("들었다", "듦"), ("든다", "듦"),
    ("어렵다", "어려움"), ("쉽다", "쉬움"), ("가깝다", "가까움"),
    ("같다", "같음"), ("다르다", "다름"), ("맞다", "맞음"),
    ("많다", "많음"), ("적다", "적음"), ("크다", "큼"), ("작다", "작음"),
    ("필요하다", "필요함"), ("가능하다", "가능함"),
    ("따른다", "따름"), ("따랐다", "따름"),
    ("이룬다", "이룸"), ("삼는다", "삼음"), ("삼았다", "삼음"),
    ("맞춘다", "맞춤"), ("맞췄다", "맞춤"),
    ("낸다", "냄"), ("냈다", "냄"),
    ("본다", "봄"), ("봤다", "봄"), ("보았다", "봄"),
    # ㄹ 불규칙 — 어간의 ㄹ 이 살아난다 (알다 → 앎, 열다 → 엶, 늘다 → 늚)
    ("안다", "앎"), ("알았다", "앎"),
    ("연다", "엶"), ("열었다", "엶"),
    (" 는다", " 늚"), (" 늘었다", " 늚"),
    ("조다", "조임"), ("표다", "표임"),      # 제32조다, 큰 표다
    ("그렇다", "그러함"), ("그러하다", "그러함"),
    ("갖는다", "가짐"), ("갖다", "가짐"), ("갖췄다", "갖춤"),
]

# 규칙으로 만들 수 있는 것 — 어간이 이 글자들로 끝날 때만 손댄다.
# 어설픈 자동 변환을 막으려고 아는 것만 좁게 잡는다.
STEM_OK = re.compile(r"[가-힣]$")

# 받침 없는 어간이지만 이름씨가 아니라 움직씨인 것들
VERBISH = {"하": "함", "되": "됨", "지": "짐"}


def _nounify(stem):
    """어간 → 명사형. 받침이 없으면 ㅁ 을 받쳐 쓰고, 있으면 '음' 을 붙인다."""
    if not stem or not STEM_OK.match(stem[-1]):
        return None
    ch = ord(stem[-1]) - 0xAC00
    if ch < 0 or ch > 11171:
        return None
    jong = ch % 28
    if jong == 0:                      # 받침 없음 → ㅁ(16) 을 받쳐 쓴다
        return stem[:-1] + chr(0xAC00 + ch + 16)
    return stem + "음"


def _one(t):
    """문장 하나의 끝맺음을 명사형으로. 못 바꾸겠으면 그대로 돌려준다."""
    t = t.rstrip()
    while t and t[-1] in ".。":         # 있던 마침표는 떼었다가 끝에 다시 찍는다
        t = t[:-1]
    if not t:
        return t
    # 끝에 붙은 괄호말(「… 인용을 맞춘다 (제24조를 제37조로)」)은 잠시 떼어
    # 놓는다. 그대로 두면 맺음이 괄호 앞에 있어 못 고치고 마침표도 못 찍는다.
    m = re.match(r"^(.*[가-힣])(\s*\([^()]*\))$", t)
    if m:
        return _one(m.group(1))[:-1] + m.group(2) + "."
    for a, b in TAIL:
        if t.endswith(a):
            return t[: -len(a)] + b + "."
    # '-는다' 는 자음 어간의 현재형 — '는' 을 떼고 '음' 을 붙인다
    m = re.search(r"([가-힣]+)는다$", t)
    if m:
        return t[: m.end(1)] + "음."
    # '요구다 / 범위다 / 잣대다' 는 움직씨가 아니라 이름씨에 '이다' 가 붙어
    # 줄어든 꼴이다. 움직씨로 보고 ㅁ 을 받쳐 쓰면 '요굼 / 범윔 / 잣댐' 이
    # 되어 말이 되지 아니한다. 어간이 두 음절 이상이고 받침이 없으면
    # 이름씨로 보아 '임' 을 붙인다.
    #
    # 다만 '-하다 / -되다 / -지다' 처럼 움직씨를 만드는 끝은 가려 낸다.
    m = re.search(r"([가-힣]{2,})다$", t)
    if m:
        stem = m.group(1)
        c = ord(stem[-1]) - 0xAC00
        if 0 <= c <= 11171 and c % 28 == 0:            # 받침이 없다
            got = VERBISH.get(stem[-1])
            if got:
                return t[: m.start(1)] + stem[:-1] + got + "."
            return t[: m.start(1)] + stem + "임."

    # '-ㄴ다' 는 모음 어간의 현재형 — 받침 ㄴ 을 떼어야 어간이 나온다.
    #   올린다 → 올리 → 올림   (그냥 '음' 을 붙이면 '올린음' 이 되어 어긋난다)
    m = re.search(r"([가-힣]+)다$", t)
    if m:
        stem = m.group(1)
        c = ord(stem[-1]) - 0xAC00
        if 0 <= c <= 11171 and c % 28 == 4:          # 받침이 ㄴ
            stem = stem[:-1] + chr(0xAC00 + c - 4)
        got = _nounify(stem)
        if got:
            return t[: m.start(1)] + got + "."
    # 바꾸지 못한 줄에도 마침표는 찍는다 — 문체가 그러하기 때문이다
    return t + ("" if t.endswith((".", ":")) else ".")


def endify(s):
    """한 줄 → 개조식 여러 줄.

    개조식에서는 한 줄에 한 가지만 담는다. 그래서 마침표가 나오면 거기서
    줄을 바꾸고, 줄마다 끝을 명사형으로 맺는다. 마침표는 남기지 아니한다.

    소수점과 조 번호의 점은 건드리면 안 된다 — 앞 글자가 '다/음/임/함'
    일 때에만 문장 끝으로 본다."""
    parts = re.split(r"(?<=[다음임함])\.\s*", s.strip())
    out = []
    for p in parts:
        t = _one(p).strip()
        if t:
            out.append(t)
    return out


# ────────────────────────────────── 아래아 ㆍ
#
# ㆍ(U+318D)는 가운데점 자리에 섞여 쓰이고 있다. 그런데 일률로 걷으면
# 뜻이 망가지는 자리가 있어, 세 갈래로 나누어 다룬다.
#
#   ① 이름 안   「훈령ㆍ예규 등의 발령 및 관리에 관한 규정」
#               제169조(밀폐공간 작업 프로그램의 수립ㆍ시행)
#               → 손대지 아니한다. 바꾸면 없는 규정ㆍ없는 조문을 가리킨다.
#
#   ② 수 늘어놓기  중복도 65/60ㆍ75/70ㆍ85/80%,  지상표본거리 2ㆍ4ㆍ8ㆍ12㎝
#               → 쉼표. 빗금으로 바꾸면 세 짝이 여섯 값으로 읽힌다.
#
#   ③ 그 밖의 말  정확도ㆍ요율ㆍ시간
#               → 빗금. 한 낱말을 잇는 자리라 쉼표로 바꾸면 두 항목으로 읽힌다.

ARAEA = chr(0x318D)             # ㆍ
_HOLD = chr(0)                  # 지켜 둘 것을 잠시 세워 두는 표
_SLASH = chr(1)                 # 빗금으로 바꿀 것을 세워 두는 표

# 이름이 담기는 따옴표 — 이 안의 ㆍ 는 그 이름의 일부다
_QUOTED = re.compile("「[^「」]*」|『[^『』]*』|'[^']*'|\"[^\"]*\"")

# 이름을 담은 괄호를 여는 자리 — 제169조( / 별표 16( / 별지 제3호서식(
_TITLE_OPEN = re.compile(
    r"(?:제\s*\d+\s*[조항호][의\d]*|별표\s*\d+|별지\s*(?:제\s*\d+\s*호)?"
    r"|[가-힣]*서식|규정|규칙|법률)\s*\(")


def _close_of(s, i):
    """s[i] 가 여는 괄호일 때 짝이 되는 닫는 괄호의 자리 (없으면 -1)"""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _hold_titles(s):
    """이름을 담은 괄호 안의 ㆍ 를 세워 둔다 (괄호가 겹쳐 있어도 통째로)"""
    out = s
    pos = 0
    while True:
        m = _TITLE_OPEN.search(out, pos)
        if not m:
            return out
        i = m.end() - 1                      # 여는 괄호 자리
        j = _close_of(out, i)
        if j < 0:
            return out
        inner = out[i:j + 1].replace(ARAEA, _HOLD)
        out = out[:i] + inner + out[j + 1:]
        pos = j + 1


def _numeric_around(left, right):
    """ㆍ 좌우 가운데 어느 한쪽이라도 수인가 — 붙어 있는 한 도막만 본다"""
    a = re.split(r"[\s,(]", left)[-1] if left else ""
    b = re.split(r"[\s,)]", right)[0] if right else ""
    return bool(re.search(r"\d", a)) or bool(re.search(r"\d", b))


def dearaea(s):
    """ㆍ 를 자리에 맞추어 걷는다

    ① 이름 안(따옴표ㆍ이름을 담은 괄호)은 손대지 아니한다.
    ② 수를 늘어놓은 자리는 쉼표로 바꾼다.
    ③ 그 밖의 말은 빗금으로 잇는다."""
    s = str(s)
    if ARAEA not in s:
        return s
    s = _QUOTED.sub(lambda m: m.group(0).replace(ARAEA, _HOLD), s)
    s = _hold_titles(s)
    out = []
    for i, ch in enumerate(s):
        if ch != ARAEA:
            out.append(ch)
        elif _numeric_around(s[:i], s[i + 1:]):
            out.append(", ")
        else:
            out.append(_SLASH)
    s = "".join(out)
    s = re.sub(r"\s*" + _SLASH + r"\s*", "/", s)
    s = re.sub(r",\s+", ", ", s)
    return s.replace(_HOLD, ARAEA)


def desymbol(s):
    """가운데점과 화살표를 걷어 낸다"""
    s = dearaea(s)      # ㆍ 는 자리를 가려 걷는다
    # 'A → B' 는 'A를 B로' 로 푼다.
    #
    # 두 번 헛짚었다. 쉼표까지 한 도막으로 잡으니 괄호와 쉼표를 넘어 들러붙었고
    # (「제126조) 로」), 공백 없는 한 낱말만 잡으니 여러 낱말로 된 오른쪽을
    # 잘라 먹었다 (「UAV LiDAR를 무인비행장치로 레이저측량」).
    #
    # 그래서 쉼표로 먼저 끊고, 도막 안에서 화살표 하나를 기준으로 좌우를
    # 통째로 가른다. 오른쪽 끝의 닫는 괄호는 조사 뒤로 물린다.
    def one_chunk(c):
        n = c.count(ARROW)
        if n == 0:
            return c
        # 화살표가 둘 이상이면 차례를 나타내는 흐름이다
        # (「접수 → 심사 → 판정 → 보완」). 'A를 B로' 로 풀면 뜻이 어긋나므로
        # 쉼표로 늘어놓는다.
        if n > 1:
            return re.sub(r"\s*" + ARROW + r"\s*", ", ", c)
        a, _sep, b = c.partition(ARROW)
        a, b = a.strip(), b.strip()
        m = re.match(r"^(.*?)([)\]}.\s]*)$", b, re.S)
        b, tail = m.group(1), m.group(2)
        # 'A를 B로' 로 풀 수 있는 것은 **낱말을 낱말로 갈음하는** 경우뿐이다.
        # 다음은 아니므로 쉼표로 늘어놓는다.
        #
        #   수치 대응표   「지도정보레벨 250 → 0.02m 이내」
        #   뒤가 문장     「보완 요구 → 그 기간은 … 제외의 차례를 담는다」
        word = re.compile(r"[가-힣A-Za-z]")
        num = re.compile(r"^[\d.,]+$")
        bad = (not a or not b
               or not word.search(a) or not word.search(b)
               or num.match(a.split()[-1]) or num.match(b.split()[0])
               or b.endswith("다") or len(b) > 28)
        if bad:
            return re.sub(r"\s*" + ARROW + r"\s*", ", ", c)
        return "%s%s %s%s%s" % (a, _eul(a), b, _ro(b), tail)

    parts = re.split(r"(\s*,\s*)", s)
    s = "".join(p if i % 2 else one_chunk(p) for i, p in enumerate(parts))
    # 가운데점은 두 가지로 쓰이고 있어 한 가지로 바꾸면 뜻이 흐려진다.
    #
    #   띄어 쓴 것   목록을 잇는다      「법령 불일치 13건 · 중복·누락 5건」
    #   붙여 쓴 것   한 낱말을 잇는다   「중복·누락·불명확」, 「이동·수정」
    #
    # 둘 다 쉼표로 바꾸면 「이동, 수정 1개」 처럼 한 낱말이 두 항목으로 읽힌다.
    # 그래서 목록은 쉼표로, 낱말은 빗금으로 바꾼다.
    s = re.sub(r"\s+" + MID + r"\s+", ", ", s)
    s = s.replace(MID, "/")
    return re.sub(r"\s{2,}", " ", s)


def _has_jong(ch):
    c = ord(ch) - 0xAC00
    return 0 <= c <= 11171 and c % 28 != 0


def _eul(w):
    return "을" if (w and _has_jong(w[-1])) else "를"


def _ro(w):
    if not w:
        return "로"
    c = ord(w[-1]) - 0xAC00
    if not (0 <= c <= 11171):
        return "로"
    j = c % 28
    return "로" if j in (0, 8) else "으로"      # 받침 없거나 ㄹ 이면 '로'


def fix(line):
    """사유 한 줄 → 개조식 여러 줄 (기호를 걷고 끝맺음을 명사형으로)"""
    return endify(desymbol(str(line or "").strip()))


def fix1(line):
    """한 줄로 붙여 돌려준다 — 시험하거나 한 칸에 넣을 때 쓴다"""
    return " ".join(fix(line))


# ────────────────────────────────── 자료에 적기
def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def sweep(write=False, show=25):
    files = sorted(f for f in os.listdir(DATA)
                   if f.startswith("draft") and f.endswith(".json"))
    seen, changed, samples = 0, 0, []
    for f in files:
        p = os.path.join(DATA, f)
        d = json.load(io.open(p, encoding="utf-8"))
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                r = x.get("reason")
                if not r:
                    continue
                # 줄바꿈으로 접힌 문장은 먼저 되붙인다. 접힌 줄을 저마다
                # 한 문장으로 보면 '… 하천 및.' 처럼 토막에 마침표가 찍힌다.
                raw = []
                for ln in str(r).split("\n"):
                    if (raw and raw[-1].strip()
                            and re.match(r"^\s{2,}\S", ln)
                            and not ln.lstrip().startswith(("*", "○", "["))):
                        raw[-1] = raw[-1].rstrip() + " " + ln.strip()
                    else:
                        raw.append(ln)
                out = []
                for ln in raw:
                    s = ln.strip()
                    if not s or s == "[변경 사유]" or s.endswith(":"):
                        out.append(ln)
                        continue
                    mark = (s[0] + " ") if s[:1] in "*○" else ""
                    body = s.lstrip("*○ ").strip()
                    seen += 1
                    got = fix(body)
                    joined = " ".join(got)
                    if joined != body:
                        changed += 1
                        if len(samples) < show:
                            samples.append((body, got))
                    # 마침표에서 갈린 것은 저마다 한 줄이 된다
                    for g in got:
                        out.append(mark + g)
                new = "\n".join(out)
                if new != r:
                    x["reason"] = new
        if write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False))
    return seen, changed, samples, files


def main():
    write = "--write" in sys.argv
    seen, changed, samples, files = sweep(write=write)
    print("사유 줄 %d개 가운데 %d개를 고쳤습니다 (%s)"
          % (seen, changed, ", ".join(files)))
    print()
    for a, b in samples:
        print("  전 : " + a[:96])
        for i, g in enumerate(b):
            print(("  후 : " if i == 0 else "       ") + g[:96])
        print()
    if not write:
        print("시험만 한 것입니다. 자료에 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
