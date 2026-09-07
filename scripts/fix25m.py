# -*- coding: utf-8 -*-
"""
제98조의 「세트 간 교차 25m」 오기를 개정안에서 바로잡는다.

■ 무엇을 확인하였나 (2026-09-07)

  현행 규정 원문(data/원문/reg01/공공측량 작업규정.2025.04.23_수식수정.오류표시.hwpx)
  을 열어 보니, 현행 제70조(개정안 제98조)의 표가 참말로

      기선벡터(R) 세트간교차 각성분마다(△X,△Y,△Z)   25m 이하

  라 적고 있다. **우리가 잘못 옮긴 것이 아니라 현행 규정의 오기다.**

  같은 문서에서 같은 항목을 정한 다른 세 자리는 모두 25mm 다.

      제27조 점검계산 허용범위      중복하는 기선벡터 요소의 교차   25mm
      제46조(개정안) 점검계산       기선벡터(R) 세트간 교차        25mm
      (현행 대응 조문도 같다)

  「25m 이하」 는 문서 전체에서 이 한 자리뿐이고, 그 밖의 25m 는 「30m 이상」ㆍ
  「25m 이상」 처럼 거리를 가리키는 자리다. 세부측량의 세트 간 교차가 25m 일 수
  없으므로 오기임이 분명하다.

■ 어떻게 고치나

  개정안 제98조제4항제3호는 이미 별표 58(축척별 세트 간 교차 허용범위)을 부르도록
  고쳐 두었다. 잘못된 값이 담긴 본문 표를 그대로 두면 별표 58과 어긋나므로,
  **본문 표를 빼고 별표 58 하나로 갈음한다.**

  현행 규정 자료(data/reg01.json)와 원문 파일은 손대지 아니한다 —— 현행은 현행
  대로 두어야 신구대조표가 맞다.

사용:  python scripts/fix25m.py          무엇을 고칠지 보여만 준다
       python scripts/fix25m.py --write  자료에 적는다
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft2025.json")
WRITE = "--write" in sys.argv
NL = chr(10)

OLD = ("3. 세트 간 교차는 ΔX, ΔY, 수평위치 교차 및 ΔH로 나누어 비교하며, "
       "축척별 허용범위는 별표 58에서 정한다. 세트 간 교차의 허용범위는 다음 표를 "
       "표준으로 한다.<img id=\"151295945\"></img>")
NEW = ("3. 세트 간 교차는 ΔX, ΔY, 수평위치 교차 및 ΔH로 나누어 비교하며, "
       "축척별 허용범위는 별표 58에서 정한다.")

MARK_OLD = "○ 확인이 필요한 것 (2026-09-07):"
MARK_NEW = "○ 확인한 것 —— 현행 규정의 오기 (2026-09-07):"
NOTE = [
    "현행 규정의 원문(공공측량 작업규정.2025.04.23)을 열어 확인한 결과, 현행 "
    "제70조의 표가 참말로 「기선벡터(R) 세트간교차 각성분마다(△X,△Y,△Z) 25m 이하」 "
    "라 적고 있다. 우리가 잘못 옮긴 것이 아니라 현행 규정의 오기다.",
    "같은 문서에서 같은 항목을 정한 다른 세 자리는 모두 25mm 다(현행 제27조의 "
    "점검계산 허용범위, 개정안 제46조제1항제3호의 표와 그 현행 대응 조문). "
    "「25m 이하」 는 문서 전체에서 이 한 자리뿐이며, 그 밖의 25m 는 「30m 이상」ㆍ"
    "「25m 이상」 처럼 거리를 가리키는 자리다.",
    "세부측량의 세트 간 교차가 25m 일 수 없다. 도상 0.3mm 를 1:10,000 축척으로 "
    "환산하여도 3m 이므로, 25m 는 어느 축척에서도 뜻을 가지지 못한다.",
    "이번 개정에서 그 본문 표를 빼고 별표 58(축척별 세트 간 교차 허용범위) 하나로 "
    "갈음한다. 별표 58 의 값은 제98조제6항의 「측정정밀도는 도상 0.3mm 이내」 를 "
    "축척마다 환산한 것이다.",
]


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    art = None
    for n in walk(doc.get("tree") or []):
        if n.get("level") == "조" and n.get("no") == 98 and not n.get("annexRef"):
            art = n
            break
    if art is None:
        raise SystemExit("제98조를 찾지 못하였습니다")

    done = []
    body = art.get("body") or ""
    if NEW in body and OLD not in body:
        print("   (건너뜀) 본문 표 — 이미 빠져 있음")
    elif OLD in body:
        art["body"] = body.replace(OLD, NEW, 1)
        done.append("제98조제4항제3호 — 25m 가 적힌 본문 표를 빼고 별표 58 로 갈음")
    else:
        raise SystemExit("제98조에서 고칠 글을 찾지 못하였습니다")

    r = art.get("reason") or ""
    if MARK_NEW in r:
        print("   (건너뜀) 검토의견 — 이미 고쳐져 있음")
    elif MARK_OLD in r:
        i = r.index(MARK_OLD)
        art["reason"] = (r[:i].rstrip() + NL + NL
                         + NL.join([MARK_NEW, ""] + ["* " + x for x in NOTE]))
        done.append("제98조 사유 — 검토의견을 확인 결과로 고침")
    else:
        art["reason"] = (r.rstrip() + NL + NL
                         + NL.join([MARK_NEW, ""] + ["* " + x for x in NOTE]))
        done.append("제98조 사유 — 확인 결과를 적음")

    for x in done:
        print("   " + x)
    if WRITE and done:
        json.dump(doc, io.open(SRC, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print("적었습니다 — %s" % os.path.relpath(SRC, ROOT))
    elif not WRITE:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
