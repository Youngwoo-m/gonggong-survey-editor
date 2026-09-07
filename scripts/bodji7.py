# -*- coding: utf-8 -*-
r"""별지 7(심사필증)의 본문을 세운다.

  간행심사 서식 넷은 연구보고서 부록의 표를 그대로 옮긴 것이라 서식 XML
  (data/objects/draftSimsa/annex/별지7.xml)만 있고 마디 본문이 비어 있었다.
  그래서 gen_annex_files 가 「본문이 있는 것」만 고르는 통에 hwpx ㆍ pdf 가
  지어지지 아니하였고, 보고서 꾸러미에서 「파일이 없는 별표ㆍ별지 1건」 으로
  잡혔다.

  이웃 별지 1~6 과 같은 꼴로 본문을 세운다. 값은 XML 에 있는 것을 그대로
  옮기며 새로 짓지 아니한다. 보기값 〔 〕 은 글자 그대로 둔다.

사용:  python scripts/bodji7.py          보여만 준다
       python scripts/bodji7.py --write  자료에 적는다
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "draft_simsa.json")
WRITE = "--write" in sys.argv
NL = chr(10)

BODY = NL.join([
    "심 사 필 증",
    "(「공간정보의 구축 및 관리 등에 관한 법률 시행규칙」 제17조제4항ㆍ제5항의",
    " 신설을 전제로 한다)",
    "",
    "※ 〔 〕 안은 적는 보기이며 규정 문언이 아니다.",
    "",
    "1. 증서의 표시",
    "  ┌ 증서번호 ├ 심사일자",
    "  적는 보기",
    "  〔제 2026-0031 호 · 2026년 10월 27일〕",
    "",
    "2. 간행물의 표시",
    "  ┌ 간행물명 ├ 발행자 ├ 심사필 번호 ├ 간행종류",
    "  적는 보기",
    "  〔○○시 도시계획도(1:5,000) · ○○시장 · 제2026-0031호 ·",
    "   최초간행 (    ) / 수정간행 ( ○ )〕",
    "",
    "3. 비고",
    "  지도의 보안사항, 주요 지형ㆍ지물의 위치 및 표현 적정성, 행정경계 검토 완료",
    "",
    "4. 증명 문구",
    "  이 지도등은 「공간정보의 구축 및 관리 등에 관한 법률」 제15조 및 제15조의2에",
    "  따라 관련 법령과 제반 절차를 지켜 공정하게 심사되었음을 증명하며, 이",
    "  심사필증을 발급합니다.",
    "",
    "                                  년        월        일",
    "",
    "                                        ○ ○ 기관장       직인",
    "",
    "5. 기재 요령",
    "  가. 이 서식은 「공간정보의 구축 및 관리 등에 관한 법률 시행규칙」 제17조에",
    "      심사필증의 발급 근거(제4항ㆍ제5항)가 신설된 뒤에 쓴다.",
    "  나. 수정간행으로 새 심사필번호를 부여한 경우에는 종전 번호를 비고란에 함께",
    "      적는다(제35조제6항ㆍ제7항).",
    "  다. 증서번호는 심사수탁기관이 연도별로 매기며, 심사필번호와 다른 번호다.",
])


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    node = None
    for n in walk(doc.get("tree") or []):
        a = n.get("annexRef") or {}
        if a.get("gubun") == "별지" and str(a.get("no")) == "7":
            node = n
            break
    if node is None:
        raise SystemExit("별지 7 마디를 찾지 못하였습니다")

    now = str(node.get("body") or "").strip()
    if now == BODY.strip():
        print("   (건너뜀) 별지 7 본문이 이미 같습니다")
        return
    if now:
        print("   [주의] 별지 7 에 이미 본문이 %d자 있습니다 — 덮어씁니다" % len(now))
    node["body"] = BODY
    print("   별지 7 본문 %d자를 세웠습니다" % len(BODY))
    if WRITE:
        json.dump(doc, io.open(SRC, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print("적었습니다 — %s" % os.path.relpath(SRC, ROOT))
    else:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
