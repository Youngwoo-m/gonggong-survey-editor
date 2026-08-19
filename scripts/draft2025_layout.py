# -*- coding: utf-8 -*-
"""
호·목을 줄로 가른다 — 원문이 줄바꿈 없이 이어 붙여 놓은 것을 편다.

현행 원문은 호와 목을 줄바꿈 없이 이어 적은 곳이 많다.

    1. 공공삼각점 성과표 (별표 5)2. 성과 수치데이터3. 공공삼각점망도
    1. TS관측가. 수평위치는 …나. 표고는 …

읽기 어려울 뿐 아니라 자동으로 처리할 때 사고가 난다 — 정의 두 개가 한 호에
묶여 옛 호 번호가 그대로 남은 일이 있었다.

■ 어떻게 가르는가

번호만 보고 자르면 안 된다. '0.01' 의 01, '말한다.' 의 다 처럼 표시처럼
보이는 자리가 많다. 그래서 **차례를 따라간다** — 지금 기다리는 번호나
글자와 맞을 때에만 자른다.

    기다리는 호가 3이면 '3.' 만 자른다. 뒤에 '5.' 가 있어도 건드리지 아니한다.
    기다리는 목이 '나' 이면 '나.' 만 자른다.

그래도 헷갈리는 자리가 있어 세 가지를 더 본다.

    · 앞에 아무 글도 없으면 표시가 아니다 (자를 것이 없다)
    · 자른 뒤가 '만·음·며' 처럼 이어지는 말로 시작하면 문장을 끊은 것이다
    · '다.' 앞이 '한·된·있' 같은 풀이씨 끝이면 '…한다.' 이지 목이 아니다

이 셋으로도 가려지지 아니하면 자르지 아니한다. 잘못 자르는 것보다 그대로
두는 편이 낫다.
"""
import re

# 목은 가·나·다… 열넉 자를 다 쓰면 거·너·더… 로 이어진다 (현행 제168조가 그렇다)
MOK = "가나다라마바사아자차카타파하" + "거너더러머버서어저처커터퍼허"

# 자른 뒤에 이어지는 말 — 문장을 끊은 자리를 가려낸다.
#
# 한때 '만·음·며·고·서·시·지…' 처럼 낱글자를 늘어놓았는데, 이 글자들은 낱말의
# 첫 글자로도 흔하다. '1. 지상현황측량' 의 '지' 가 걸려 호가 갈리지 아니한
# 조문이 23개나 있었다. 뒤 글자 하나로는 가릴 수 없다.
# 이어지는 말인지는 낱글자가 아니라 '다만·이 경우' 같은 말마디로 가린다.
# '그 밖' 은 넣지 아니한다 — '그 밖에 필요한 사항' 은 호·목의 마지막에 늘 나오는 말이다
GO_ON = ("다만", "단,", "이 경우", "그러하지")
# '…한다.' 처럼 풀이씨가 끝나는 자리 — 그 '다' 는 목이 아니다.
# '같다·있다·없다' 도 함께 막는다 ('…표와 같다. 다만,' 을 목으로 잘못 본 일이 있다)
VERB_TAIL = set("한된인있없같쓴준든난논운신진친킨힌본온린슨끈른흔뜬")


def _cuts(text, marks, is_ho):
    """기다리는 차례를 따라 자를 자리를 찾는다 → [(자리, 표시길이, 표시)]"""
    out, pos, i = [], 0, 0
    while i < len(marks):
        pat = marks[i]
        p = text.find(pat, pos)
        if p < 0:
            break
        pos = p + 1                       # 못 쓰면 다음 자리를 찾는다
        before = text[p - 1] if p else ""
        after = text[p + len(pat):].lstrip()
        head = text[(out[-1][0] + out[-1][1]) if out else 0:p]

        if is_ho and (before.isdigit() or after[:1].isdigit()):
            continue                      # '0.01' · '1.5m' 처럼 숫자 가운데인 것
                                          # (마침표 뒤는 막지 아니한다 — '…한다.1. 내용')
        if not is_ho and pat[0] == "다" and before in VERB_TAIL:
            continue                      # '…한다.' 의 '다' 를 목으로 본 것이다
        if not is_ho and after[:1] == "만":
            continue                      # '다만' 의 '다' 를 떼어 간 것이다
        if out and not head.strip():
            continue                      # 앞 표시 바로 뒤 — 빈 조각이 생긴다
                                          # (첫 표시 앞이 비는 것은 정상이다)
        if not after:
            continue                      # 뒤에 아무 글도 없다
        if after.startswith(GO_ON):
            continue                      # '…같다. 다만,' 처럼 이어지는 말마디
        out.append((p, len(pat), pat))
        pos = p + len(pat)
        i += 1
    return out


def _slice(text, cuts, inner=None):
    """찾은 자리에서 잘라 줄로 만든다"""
    lines = []
    head = text[:cuts[0][0]].strip()
    if head:
        lines.append(head)
    for k, (p, ln, mark) in enumerate(cuts):
        end = cuts[k + 1][0] if k + 1 < len(cuts) else len(text)
        body = text[p + ln:end].strip()
        lines.append(f"{mark} {inner(body) if inner else body}".rstrip())
    return "\n".join(lines)


def _start_ho(s):
    """이 줄이 몇 번 호부터 시작하는가 — 늘 1부터 찾으면 안 된다.

    앞 단계가 '1. 작업수행계획' 까지만 갈라 놓아, 남은 줄이 '2. 자료의 수집3. …'
    처럼 가운데 번호로 시작하는 곳이 있다. 1을 찾다 못 찾고 그대로 멈추면
    그 줄은 하나도 갈리지 아니한다.
    """
    m = re.match(r"\s*(\d{1,2})\.", s)
    return int(m.group(1)) if m else 1


def _start_mok(s):
    """이 덩이가 몇 번째 목부터 시작하는가"""
    m = re.match(r"\s*([" + MOK + r"])\.", s)
    return MOK.index(m.group(1)) if m else 0


def _mok(s):
    """한 덩이 안의 목을 가른다"""
    i = _start_mok(s)
    cuts = _cuts(s, [f"{c}." for c in MOK[i:]], is_ho=False)
    return _slice(s, cuts) if len(cuts) >= 2 else s.strip()


def _para(p):
    """한 항 안의 호를 가르고, 호마다 목을 가른다"""
    n0 = _start_ho(p)
    cuts = _cuts(p, [f"{n}." for n in range(n0, n0 + 40)], is_ho=True)
    if len(cuts) < 2:
        return _mok(p)
    return _slice(p, cuts, inner=_mok)


def relayout(body):
    """본문의 호·목을 줄로 가른다 — 가를 것이 없으면 원문 그대로"""
    src = str(body or "")
    if not src.strip():
        return src
    return "\n".join(_para(x) for x in src.split("\n"))


def count_runon(body):
    """줄 하나에 표시가 둘 이상 붙어 있는 줄의 수 — 정비가 필요한지 재는 잣대"""
    n = 0
    for line in str(body or "").split("\n"):
        ho = len(re.findall(r"(?<![\d.])\d{1,2}\.", line))
        mok = len(re.findall("(?<![가-힣0-9])[" + MOK + r"]\.\s", line))
        if ho >= 2 or mok >= 2:
            n += 1
    return n
