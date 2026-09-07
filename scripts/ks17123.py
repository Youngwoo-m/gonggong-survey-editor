# -*- coding: utf-8 -*-
r"""ISO 17123 의 KS 부합화를 건의하기로 정한 것을 자료에 적는다 (할일 ㉯).

  2026-09-07 사람이 「건의하는 것으로」 정하였다. 조문은 이미 단서로 길을 열어
  두었으므로 고칠 것이 없고, 정한 사실과 그 뒤에 할 일을 사유와 안내문에 남긴다.

  · 작업규정 개정안 제25조 사유 —— 건의하기로 정한 것과, 부합화가 이루어지면
    고칠 세 자리를 적는다.
  · 서고 data/loc17.json 머리글 —— 「찾지 못함」 뒤에 건의 결정을 잇는다.

사용:  python scripts/ks17123.py          보여만 준다
       python scripts/ks17123.py --write  자료에 적는다
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "data", "draft2025.json")
LOC17 = os.path.join(ROOT, "data", "loc17.json")
WRITE = "--write" in sys.argv
NL = chr(10)
MARK = "○ KS 부합화 건의 (2026-09-07 정함):"


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


NOTE = [
    "ISO 17123 시리즈의 한국산업표준 제정(부합화)을 국가기술표준원에 건의하기로 "
    "정하였다. 건의서 밑글은 docs/ISO17123_KS부합화_건의.md 에 두었다.",
    "건의하는 대상은 시리즈 10부다. 법정 검사 대상 6종(시행령 제97조) 가운데 "
    "관로탐지기만 대응하는 부가 없어, 그것은 「측량기기 성능검사 규정」 제10조에 "
    "그대로 둔다.",
    "차례는 제1부(통계 이론)와 제5부(토털스테이션)를 먼저, 다음으로 제2ㆍ3ㆍ4부, "
    "GNSS 는 제11부가 ISO 최종단계를 마친 뒤에 하는 것으로 적었다 —— 판을 두 번 "
    "고치지 아니하려는 것이다.",
    "부합화는 이 개정과 별개로 간다. 제2항 본문이 국제표준을 준용하도록 하고 "
    "있으므로 부합화 전에도 시행에 걸림이 없다.",
    "부합화가 이루어지면 세 자리를 함께 고친다 —— 이 조 제2항의 단서를 지우고 KS "
    "번호를 곧바로 적는 것, 별표 21의 시험항목을 KS 번호로 바꾸는 것, 서고 "
    "loc17 의 안내문을 KS 번호와 제정일로 갈음하는 것.",
]

LOC17_ADD = (
    "[KS 부합화 건의 — 2026년 9월 7일 정함] "
    "위 확인 결과에 따라, ISO 17123 시리즈의 한국산업표준 제정을 국가기술표준원에 "
    "건의하기로 정하였습니다. 건의서 밑글은 저장소의 docs/ISO17123_KS부합화_건의.md "
    "에 있습니다. 부합화가 이루어지면 공공측량 작업규정 개정안 제25조제2항의 단서를 "
    "지우고 KS 번호를 곧바로 적으며, 별표 21의 시험항목도 KS 번호로 바꿉니다."
)


def main():
    done = []

    # ── 작업규정 제25조 사유 ──
    doc = json.load(io.open(WORK, encoding="utf-8"))
    art = None
    for n in walk(doc.get("tree") or []):
        if n.get("level") == "조" and n.get("no") == 25 and not n.get("annexRef"):
            art = n
            break
    if art is None:
        raise SystemExit("작업규정 제25조를 찾지 못하였습니다")
    if MARK in (art.get("reason") or ""):
        print("   (건너뜀) 제25조 사유 — 이미 있음")
    else:
        art["reason"] = ((art.get("reason") or "").rstrip() + NL + NL
                         + NL.join([MARK, ""] + ["* " + x for x in NOTE]))
        done.append(("work", "제25조 사유에 건의 결정 %d줄" % len(NOTE)))

    # ── 서고 loc17 머리글 ──
    lo = json.load(io.open(LOC17, encoding="utf-8"))
    head = None
    for n in walk(lo.get("tree") or []):
        if n.get("level") == "편":
            head = n
            break
    if head is None:
        raise SystemExit("loc17 의 머리글을 찾지 못하였습니다")
    if "KS 부합화 건의" in (head.get("body") or ""):
        print("   (건너뜀) loc17 안내문 — 이미 있음")
    else:
        head["body"] = (head.get("body") or "").rstrip() + NL + LOC17_ADD
        done.append(("loc17", "서고 안내문에 건의 결정"))

    for _, what in done:
        print("   " + what)
    if WRITE:
        if any(k == "work" for k, _ in done):
            json.dump(doc, io.open(WORK, "w", encoding="utf-8", newline="\n"),
                      ensure_ascii=False, indent=1)
        if any(k == "loc17" for k, _ in done):
            json.dump(lo, io.open(LOC17, "w", encoding="utf-8", newline="\n"),
                      ensure_ascii=False, indent=1)
        print("적었습니다 — %d곳" % len(done))
    else:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
