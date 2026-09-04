# -*- coding: utf-8 -*-
"""
변경 사유를 개조식 다섯 도막으로 짓는다.

  ○ 현행 규정: 제12조(공공측량성과의 정리) — 제1편 총칙 제2장
  ○ 현행의 문제:
    - 같은 사항을 정한 조문이 열 곳에 흩어져 있고 요구하는 성과 목록이 서로 다르다
  ○ 관련 근거:
    - 「공공측량 성과심사 규정」 제9조
    - [품관원] 검토의견 2번(제29조제7항) — 간섭 측위 방식의 정의가 필요하다
  ○ 개정 사유:
    - 흩어져 있던 성과 정리 조문 열 곳을 총칙 한 조로 묶는다
  ○ 개정 내용:
    - 현행 제31·43·59조의 제출 목록을 제17조 제3항 각 호로 합치고, 유형별 차이는
      별표 30으로 넘긴다

'현행의 문제'는 고치지 아니하면 무엇이 잘못되는가,
'개정 사유'는 왜 고치는가, '개정 내용'은 무엇을 어떻게 고치는가를 적는다.
공청회에서 설득해야 할 것은 앞의 둘이다.

연구 내용은 근거로 삼되 '보고서 어디'라고 적지 아니한다 — 보고서의 위치
표시(부록4 X-N, [표 4-3], 제4장 2.1 …)는 그 자리의 문장으로 바꾸어 싣는다.
"""
import re

import draft2025_srcs as SRCS

HEAD_CUR, HEAD_BASE, HEAD_WHY = "현행 규정", "관련 근거", "개정 사유"
HEAD_WHAT = "개정 내용"          # 무엇을 어떻게 바꾸었는지 — 사유 다음에 적는다
HEAD_PROB = "현행의 문제"        # 고치지 아니하면 무엇이 잘못되는지 — 사유보다 먼저
NEW_CUR = "없음 — 신설 조문"


def _clean(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip(" ,·/")
    return s


class Reason:
    """한 조문의 변경 사유"""

    def __init__(self, cur=""):
        self.cur = _clean(cur)
        self.base = []
        self.why = []
        self.what_ = []
        self.prob = []

    def now(self, s):
        self.cur = _clean(s)
        return self

    def basis(self, *ss):
        for s in ss:
            s = _clean(s)
            if s and s not in self.base:
                self.base.append(s)
        return self

    def cause(self, *ss):
        for s in ss:
            s = _clean(s)
            if s and s not in self.why:
                self.why.append(s)
        return self

    def problem(self, *ss):
        """현행의 문제 — 고치지 아니하면 무엇이 잘못되는가"""
        for s in ss:
            s = _clean(s)
            if s and s not in self.prob:
                self.prob.append(s)
        return self

    def what(self, *ss):
        """개정 내용 — 무엇을 어떻게 바꾸었는지"""
        for s in ss:
            s = _clean(s)
            if s and s not in self.what_:
                self.what_.append(s)
        return self

    def __bool__(self):
        return bool(self.cur or self.base or self.why or self.what_ or self.prob)

    def render(self):
        """네 도막을 같은 구조로 — 도막마다 머리글, 빈 줄, '*' 항목"""
        out = ["[변경 사유]"]
        for head, items in ((HEAD_CUR, [self.cur or NEW_CUR]),
                            (HEAD_PROB, self.prob),
                            (HEAD_BASE, self.base),
                            (HEAD_WHY, self.why),
                            (HEAD_WHAT, self.what_)):
            out += ["", f"○ {head}:", ""]
            out += [f"* {x}" for x in (items or ["(해당 없음)"])]
        return "\n".join(out)


# ───────────── 손으로 쓴 사유 문장 가르기 ─────────────

# '… 제3항이 위임한 것이다' 처럼 근거로 옮길 글줄
DELEG_LINE = re.compile(r"위임한 것이다|위임한다|제\d+항이 위임")
# 손으로 쓴 글 안의 '[품관원] 검토의견 …' 도막
REVIEW_LINE = re.compile(r"\[품관원\]\s*검토의견")
# '부록 4 C 유형(용어 오류·불일치)' — 보고서 위치 대신 무엇을 지적했는지만 남긴다
APX_TYPE = re.compile(r"[,.]?\s*부록\s*4\s*[A-Fa-f]\s*유형\s*\(([^)]+)\)")


def split(text, fixes, bases_by_code=None):
    """손으로 쓴 사유 한 덩이 → (근거 목록, 사유 목록)

    보고서·원고·국외규정의 위치 표시는 그 자리의 문장으로 바꾸어 싣는다.
    부록 4 지적은 '문제점' 을 근거로, '개선 방향' 을 사유로 나눈다."""
    s = str(text or "")
    if not s.strip():
        return [], []

    bases, causes = [], []
    for m in SRCS.CODE.finditer(s):
        code = m.group(1).upper()
        if bases_by_code and bases_by_code.get(code):
            bases.append(bases_by_code[code])
        if fixes.get(code):
            causes.append(fixes[code])
    for m in SRCS.SEC.finditer(s):
        key = re.sub(r"\s+", " ", m.group(0)).strip()
        for k, v in SRCS.SECTION.items():
            if re.sub(r"\s+", " ", k) == key:
                bases.append(v)
                break

    # 위치 표시와 그 꼬리를 걷어 낸 나머지가 사유다
    rest = SRCS.CODE.sub("", s)
    rest = SRCS.SEC.sub("", rest)
    rest = re.sub(r"\s*[,·]\s*(?=[,·]|$)", "", rest)
    rest = re.sub(r"\s{2,}", " ", rest)
    rest = re.sub(r"\s+([.,])", r"\1", rest).strip(" ,·")
    # 코드가 여럿 붙어 있던 자리에 남은 '·E-3' 같은 부스러기를 지운다
    rest = re.sub(r"[,·]\s*[A-Fa-f]-\d+", "", rest).strip(" ,·")

    for m in APX_TYPE.finditer(rest):
        bases.append(f"연구 검토 결과 {_clean(m.group(1))}")
    rest = APX_TYPE.sub("", rest).strip(" ,·")

    for line in sentences(rest):
        if REVIEW_LINE.search(line):
            b, c = review_split(line)
            bases += b
            causes += c
        else:
            causes.append(line)
    return bases, causes


def review_split(line):
    """'[품관원] 검토의견 2번(…) — 의견: … / 반영: …' 을 근거와 사유로 가른다"""
    bases, causes = [], []
    for chunk in re.split(r"\s*/?\s*(?=\[품관원\]\s*검토의견)", line):
        chunk = _clean(chunk)
        if not chunk:
            continue
        m = re.match(r"(\[품관원\]\s*검토의견[^—]*)", chunk)
        head = _clean(m.group(1)) if m else "[품관원] 검토의견"
        opinion = " / ".join(_clean(x) for x in
                             re.findall(r"(?:의견|문제점)\s*:\s*([^/·]+)", chunk))
        fix = " / ".join(_clean(x) for x in re.findall(r"반영\s*:\s*([^/·]+)", chunk))
        pri = re.search(r"우선순위\s*([상중하])", chunk)
        bases.append(f"{head} — {opinion}" if opinion else head)
        if fix:
            causes.append(f"{head.replace('[품관원] ', '')}을 반영하여 {fix}"
                          + (f" (우선순위 {pri.group(1)})" if pri else ""))
    return bases, causes


def sentences(s):
    """한 덩이 글을 개조식 줄로 끊는다 — '…한다.' 마다 한 줄"""
    s = _clean(s)
    if not s:
        return []
    parts = re.split(r"(?<=다)\.\s+", s)
    out = []
    for p in parts:
        p = p.strip(" ,·")
        if not p:
            continue
        if not p.endswith((".", "다", "임", "함", "음", ")")):
            p += ""
        out.append(p.rstrip("."))
    return out


# 근거·사유가 비었을 때 채울 기본 줄 — 조문의 처지에 따라 다르다
DEFAULT_BASE = {
    "이동": "규정 체계 정비 — 편·장을 다시 나누는 데 따른 것",
    "이동·수정": "규정 체계 정비 — 편·장을 다시 나누는 데 따른 것",
    "유지": "현행 규정을 그대로 둔다 — 따로 든 근거 없음",
    "신설": "규정 체계 정비 — 현행 규정에 없던 사항을 새로 정한다",
    "수정": "규정 체계 정비 — 문언을 바로잡는다",
    "기타": "규정 체계 정비에 따른 것",
}

# '개정 내용' 이 비었을 때 채울 기본 줄 — 무엇을 어떻게 했는지
DEFAULT_WHAT = {
    "이동": "본문은 그대로 두고 조문의 자리만 옮긴다",
    "이동·수정": "조문의 자리를 옮기고 본문의 문언을 함께 고친다",
    "유지": "본문과 편제를 고치지 아니한다",
    "신설": "현행 규정에 없던 사항을 조문으로 새로 정한다",
    "수정": "편제는 그대로 두고 본문의 문언을 고친다",
    "삭제": "개편안에 이 조문을 두지 아니한다",
    "통합": "다른 조문에 합쳐 이 조문을 따로 두지 아니한다",
    "기타": "규정 체계를 정비한다",
}

DEFAULT_WHY = {
    "이동": "편·장 재편에 따라 자리를 옮긴다",
    "이동·수정": "편·장 재편에 따라 자리를 옮기고 문언을 고친다",
    "유지": "편제와 문언을 그대로 둔다",
    "신설": "현행 규정에 없던 사항이어서 새로 둔다",
    "수정": "문언을 바로잡는다",
    "기타": "규정 체계를 정비한다",
}
