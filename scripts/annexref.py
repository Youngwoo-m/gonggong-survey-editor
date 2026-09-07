# -*- coding: utf-8 -*-
"""
번호 없이 「별표에서 정한다」 라 한 자리 여섯을 정리한다 (2026-09-07).

■ 무엇이 문제였나

  조문이 별표에 위임하면서 번호를 적지 아니한 자리가 여섯 있었다. 번호가 없으면
  어느 별표를 보라는 것인지 알 수 없고, 별표를 새로 지을 때 빠뜨리게 된다.

■ 어떻게 갈랐나 (2026-09-07 사람이 정함)

  다섯은 이미 있는 표나 조문으로 갈음하고, 참말 새 표가 필요한 하나만 별표로 둔다.

    제45조제5호   세트 사이의 교차 허용범위
                  → 제46조제1항제3호의 표가 이미 정하고 있다. 그것을 가리킨다.
    제46조제2항제2호 폐합경로의 선정과 좌표폐합차의 계산방법
                  → 한 문장으로 조문에 직접 적는다. 환의 구성은 같은 항 제1호가
                     이미 정하고 있다.
    제65조제5항   국가 지오이드모델이 갱신된 경우의 성과 처리
                  → 조문에 직접 적는다. 이미 낸 성과를 다시 계산하지 아니하되,
                     적용한 모델을 성과에 밝히도록 제2항이 정하고 있다.
    제98조제4항제1호 점검점의 설치와 보존 조건
                  → 조문에 직접 적는다.
    제98조제4항제3호 축척별 허용범위
                  → **새 별표 58** 을 둔다. 축척마다 값이 다르므로 표라야 한다.
    제98조제11항  표본의 크기와 뽑는 방법
                  → 「공간정보의 구축 및 관리 등에 관한 법률 시행규칙」 별표 13
                     제3호가 정한다. 그것을 가리킨다 (같은 것을 두 규정이 각각
                     정하지 아니한다는 잣대 —— 할일 ㉳).

■ 함께 남긴 검토의견

  제98조제4항제3호의 본문 표에 「기선벡터(R) 세트간교차 … 25m 이하」 라 적혀
  있는데, 같은 항목을 제46조의 표는 25mm 로 적었다. 오기로 보이나 원문을 확인하지
  못하였으므로 사유에 적어 두고 사람이 확인한 뒤 고친다.

사용:  python scripts/annexref.py          무엇을 고칠지 보여만 준다
       python scripts/annexref.py --write  자료에 적는다
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
WRITE = "--write" in sys.argv
NL = chr(10)


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def bump(a):
    st = a.get("status") or "유지"
    if st in ("삭제", "신설"):
        return
    a["status"] = "이동·수정" if st == "이동" else "수정"


EDITS = [
    (45,
     "세트 사이의 수평·수직 교차 허용범위는 별표에서 정한다.",
     "세트 사이의 수평·수직 교차 허용범위는 제46조제1항제3호의 표에 따른다.",
     "그 표가 「기선벡터(R) 세트간 교차」 를 이미 정하고 있다"),
    (46,
     "2. 폐합경로의 선정과 좌표폐합차의 계산방법은 별표에서 정한다.",
     "2. 폐합경로는 기지점과 기지점을 잇는 노선 가운데 가장 짧은 것으로 선정하며, "
     "좌표폐합차는 환을 이루는 기선벡터의 성분을 차례로 더하여 계산한다.",
     "환의 구성은 같은 항 제1호가 이미 정하고 있어 한 문장으로 족하다"),
    (65,
     "⑤ 국가 지오이드모델이 갱신된 경우의 성과 처리 기준은 별표에서 정한다.",
     "⑤ 국가 지오이드모델이 갱신된 경우에도 이미 낸 성과는 다시 계산하지 아니한다. "
     "다만, 갱신된 모델로 다시 계산할 필요가 있다고 시행자가 인정하는 경우에는 그 "
     "범위와 방법을 정하여 요구할 수 있으며, 이 경우 제2항에 따라 적용한 모델을 "
     "성과에 밝혀 적는다.",
     "적용한 모델을 밝히는 것은 제2항이 이미 정하고 있다"),
    (98,
     "다만, 관측은 점검점을 설치하여 실시하며, 점검점의 설치와 보존 조건은 "
     "별표에서 정한다.",
     "다만, 관측은 점검점을 설치하여 실시하며, 점검점은 관측 구역 안의 움직이지 "
     "아니하는 지물에 두고 그 작업이 끝날 때까지 보존한다.",
     "한 문장으로 족한 조건이다"),
    (98,
     "3. 세트 간 교차는 ΔX, ΔY, 수평위치 교차 및 ΔH로 나누어 비교하며, "
     "축척별 허용범위는 별표에서 정한다.",
     "3. 세트 간 교차는 ΔX, ΔY, 수평위치 교차 및 ΔH로 나누어 비교하며, "
     "축척별 허용범위는 별표 58에서 정한다.",
     "축척마다 값이 다르므로 표라야 한다 —— 별표 58 을 새로 둔다"),
    (98,
     "표본의 크기와 뽑는 방법은 별표에서 정한다.",
     "표본의 크기와 뽑는 방법은 「공간정보의 구축 및 관리 등에 관한 법률 시행규칙」 "
     "별표 13 제3호에 따른다.",
     "표본은 상위 법령이 정한다 —— 같은 것을 두 규정이 각각 정하지 아니한다"),
]

NOTE_98 = [
    "제4항제3호의 표에 「기선벡터(R) 세트간교차 … 25m 이하」 라 적혀 있으나, 같은 "
    "항목을 제46조제1항제3호의 표는 25mm 로 적고 있다. 세트 간 교차가 25m 일 수는 "
    "없으므로 오기로 보인다.",
    "다만 현행 규정의 원문을 확인하지 못하였으므로 이번 개정에서는 고치지 아니하고 "
    "적어만 둔다. 원문을 확인한 뒤 25mm 로 바로잡아야 한다.",
]
MARK_98 = "○ 확인이 필요한 것 (2026-09-07):"


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    arts = {}
    for n in walk(doc.get("tree") or []):
        if n.get("level") == "조" and not n.get("annexRef") and n.get("no"):
            arts.setdefault(n["no"], n)

    done, skip = [], []
    for no, old, new, why in EDITS:
        a = arts.get(no)
        if a is None:
            raise SystemExit("제%d조를 찾지 못하였습니다" % no)
        body = a.get("body") or ""
        if new in body:
            skip.append("제%d조 (이미 되어 있음)" % no)
            continue
        if old not in body:
            raise SystemExit("제%d조에서 고칠 글을 찾지 못하였습니다 —— %s" % (no, old[:44]))
        a["body"] = body.replace(old, new, 1)
        bump(a)
        done.append("제%-3d조 — %s" % (no, why))

    a98 = arts[98]
    if MARK_98 in (a98.get("reason") or ""):
        skip.append("제98조 검토의견 (이미 있음)")
    else:
        a98["reason"] = ((a98.get("reason") or "").rstrip() + NL + NL
                         + NL.join([MARK_98, ""] + ["* " + x for x in NOTE_98]))
        done.append("제98조 — 25m 오기를 검토의견으로 남김")

    for x in done:
        print("   " + x)
    for x in skip:
        print("   (건너뜀) " + x)
    if WRITE and done:
        json.dump(doc, io.open(SRC, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print("적었습니다 — %s" % os.path.relpath(SRC, ROOT))
    elif not WRITE:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
