# -*- coding: utf-8 -*-
"""ISO 19157-1:2023 을 조문 단위로 색인하여 참조 규정으로 세운다.

  Geographic information — Data quality — Part 1: General requirements

작업규정 개정안 제15조(성과의 품질기준)와 별표 15(성과 유형별 품질요소
평가기준)가 이 표준의 품질모델을 따르므로, 초안을 쓰면서 곁에 두고 볼 수
있도록 참조 규정에 넣는다.

────────────────────────────────────────────────────────────────
저작권 — 이 표준은 ISO 가 파는 저작물이다. 표지 뒤에 이렇게 적혀 있다.

  "no part of this publication may be reproduced or utilized otherwise in
   any form or by any means … including photocopying, or posting on the
   internet or an intranet, without prior written permission."

그러므로
  ㆍ 원본 PDF 는 저장소에 두지 아니한다 (App\\공간정보표준\\ISO19157 에만 둔다)
  ㆍ 여기서 만드는 data/loc29.json 도 .gitignore 에 넣어 올리지 아니한다
  ㆍ library.json 의 등재만 올리되 localOnly 로 표시한다 — 내려받은 사람은
     "이 컴퓨터에만 있는 자료" 라는 안내를 보게 된다
────────────────────────────────────────────────────────────────

사용:  python scripts/genintl_iso19157.py
출력:  data/loc29.json  (덮어쓴다) · data/library.json 에 등재
"""
import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
SRC = os.path.join(os.path.dirname(ROOT), "공간정보표준", "ISO19157",
                   "ISO_19157-1_2023_ed.Publication.pdf")
REGID = "loc29"

# 조ㆍ절의 한국어 이름 — 우리 규정에서 쓰는 말에 맞춘다
KO = {
    "Foreword": "머리말",
    "Introduction": "들어가는 말",
    "1 Scope": "적용 범위",
    "2 Normative references": "인용 표준",
    "3 Terms and definitions": "용어와 정의",
    "4 Abbreviated terms and packages": "줄임말과 꾸러미",
    "4.1 Abbreviated terms": "줄임말",
    "4.2 Abbreviated packages": "꾸러미 줄임말",
    "5 Conformance": "적합성",
    "5.1 General": "일반",
    "5.2 Content of a data quality model": "자료품질모델이 담을 것",
    "5.3 XML encoding of a data quality model": "자료품질모델의 XML 표현",
    "6 General requirements for geographic information quality": "지리정보 품질의 일반 요구사항",
    "6.1 General": "일반",
    "6.2 Data quality — general requirements, recommendations and permissions":
        "자료품질 — 요구사항ㆍ권고ㆍ허용",
    "7 Overview of data quality": "자료품질 개관",
    "8 Components of data quality": "자료품질의 구성요소",
    "8.1 Overview of the components": "구성요소 개관",
    "8.2 Data quality unit": "자료품질 단위",
    "8.3 Data quality elements": "자료품질요소",
    "8.3.1 General": "일반",
    "8.3.2 Completeness": "완전성",
    "8.3.3 Logical consistency": "논리일관성",
    "8.3.4 Positional accuracy": "위치정확도",
    "8.3.5 Temporal quality": "시간품질",
    "8.3.6 Thematic quality": "주제품질",
    "8.3.7 Metaquality elements": "메타품질요소",
    "8.4 Extending the data quality information model": "자료품질 정보모델의 확장",
    "8.5 Descriptors of data quality elements": "자료품질요소의 기술항목",
    "8.5.1 General": "일반",
    "8.5.2 Measure reference": "측도 참조",
    "8.5.3 Evaluation method": "평가방법",
    "8.5.4 Quality result": "품질 결과",
    "8.5.5 Descriptors of a metaquality element": "메타품질요소의 기술항목",
    "9 Data quality measures": "자료품질 측도",
    "9.1 General": "일반",
    "9.2 Standardized data quality measures": "표준화된 자료품질 측도",
    "9.2.1 General": "일반",
    "9.2.2 Measure identifier": "측도 식별자",
    "9.2.3 Name": "이름",
    "9.2.4 Alias": "다른 이름",
    "9.2.5 Element name": "요소 이름",
    "9.2.6 Basic measure": "기본 측도",
    "9.2.7 Definition": "정의",
    "9.2.8 Description": "설명",
    "9.2.9 Parameter": "매개변수",
    "9.2.10 Value type": "값의 형",
    "9.2.11 Value structure": "값의 짜임",
    "9.2.12 Source reference": "출처",
    "9.2.13 Example": "보기",
    "9.3 User-defined data quality measures": "이용자가 정하는 자료품질 측도",
    "10 Data quality evaluation": "자료품질 평가",
    "10.1 The process for evaluating data quality": "자료품질 평가의 절차",
    "10.1.1 Introduction": "들어가는 말",
    "10.1.2 The process flow": "절차의 흐름",
    "10.1.3 Process steps": "절차의 단계",
    "10.2 Data quality evaluation methods": "자료품질 평가방법",
    "10.2.1 Classification of data quality evaluation methods": "평가방법의 갈래",
    "10.2.2 Direct evaluation": "직접 평가",
    "10.2.3 Indirect evaluation": "간접 평가",
    "10.3 Aggregation and derivation": "종합과 유도",
    "11 Data quality reporting": "자료품질의 보고",
    "11.1 General": "일반",
    "11.2 Particular cases": "특별한 경우",
    "11.2.1 Reporting aggregation (aggregated results)": "종합 결과의 보고",
    "11.2.2 Reporting derivation (derived results)": "유도 결과의 보고",
    "11.2.3 Reference to the original data quality result": "본디 품질 결과의 참조",
    "11.2.4 Hierarchy principle": "계층의 원칙",
    "12 Requirements for XML encoding": "XML 표현의 요구사항",
    "Annex A (normative) Abstract test suite": "부속서 A (규범) 추상 시험군",
    "Annex B (informative) Data quality concepts and their use":
        "부속서 B (참고) 자료품질 개념과 그 쓰임",
    "Annex C (normative) Data dictionary for data quality":
        "부속서 C (규범) 자료품질 자료사전",
    "Annex D (informative) Evaluating and reporting data quality":
        "부속서 D (참고) 자료품질의 평가와 보고",
    "Annex E (informative) Sampling methods for evaluating data quality":
        "부속서 E (참고) 자료품질 평가를 위한 표본추출 방법",
    "Annex F (informative) Guidelines for the use of quality elements":
        "부속서 F (참고) 품질요소 사용 지침",
    "Annex G (informative) Aggregation of data quality results":
        "부속서 G (참고) 자료품질 결과의 종합",
    "Annex H (normative) XML Encoding description": "부속서 H (규범) XML 표현 기술",
    "Annex I (informative) Backward compatibility with ISO 19157:2013":
        "부속서 I (참고) ISO 19157:2013 과의 호환",
    "Bibliography": "참고문헌",
}

# 우리 개정안이 곧바로 기대는 마디에는 한국어 해설을 붙인다.
# (번역이 아니라 해설이다 — 규범 문장을 통째로 옮기지 아니한다)
NOTE = {
    "8.3.2": "우리 작업규정 개정안 제15조제1항의 다섯 품질요소 가운데 '완전성' 이 이것이다. "
             "있어야 할 것이 빠졌는가(누락)와 없어야 할 것이 들어왔는가(초과)를 함께 본다.",
    "8.3.3": "'논리일관성' — 개념ㆍ값영역ㆍ형식ㆍ위상의 규칙을 지켰는가를 본다. "
             "별표 15 의 논리일관성 항목이 이 갈래를 따른다.",
    "8.3.4": "'위치정확도' — 절대(외부)ㆍ상대(내부)ㆍ격자자료의 위치정확도로 갈린다. "
             "우리 규정의 정확도 관리표가 재는 것이 이것이다.",
    "8.3.5": "'시간품질' — 시간 정확도ㆍ시간 일관성ㆍ시간 타당성. "
             "2013년판의 temporal accuracy 를 넓힌 것이다.",
    "8.3.6": "'주제품질' — 분류 정확성ㆍ비정량 속성 정확성ㆍ정량 속성 정확성.",
    "8.3.7": "'메타품질' — 신뢰성(confidence)ㆍ대표성(representativity)ㆍ동질성(homogeneity). "
             "2023년판에서 품질요소와 나란한 자리로 올라섰다. "
             "우리 개정안 제15조제4항이 이를 받는다.",
    "10.2.2": "직접 평가 — 자료 자체를 들여다보아 재는 것. 전수와 표본으로 갈린다.",
    "10.2.3": "간접 평가 — 계보ㆍ생산이력 따위 바깥 정보로 미루어 아는 것.",
    "11.1": "품질 결과를 어떻게 알릴 것인가. 우리 별표 15 의 '알리는 방법' 칸이 이를 따른다.",
}


# 옮겨 둔 한국어 본문 — 제8~11조. 따로 둔 파일에서 읽어 온다.
# (색인을 다시 지어도 옮긴 글을 잃지 않으려는 것이다)
try:
    sys.path.insert(0, HERE)
    from iso19157_ko_8_11 import KO as KO_BODY
except Exception:
    KO_BODY = {}


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


def page_text(doc, p0, p1):
    """p0쪽부터 p1쪽 앞까지의 글 (1부터 세는 쪽 번호)"""
    out = []
    for i in range(p0 - 1, min(p1 - 1, doc.page_count)):
        out.append(doc[i].get_text())
    s = "\n".join(out)
    # 쪽 머리ㆍ꼬리와 저작권 줄을 걷어낸다
    s = re.sub(r"^\s*ISO 19157-1:2023\(E\)\s*$", "", s, flags=re.M)
    s = re.sub(r"^\s*©\s*ISO 2023.*$", "", s, flags=re.M)
    s = re.sub(r"^\s*\d{1,3}\s*$", "", s, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _find_head(s, title, start=0):
    """글 안에서 그 마디의 머리글이 있는 자리를 찾는다 — (자리, 길이). 없으면 (-1, 0).

    줄머리에 있는 것만 머리글로 본다. 본문 가운데에서 다른 마디를 가리키는
    말('… see 8.3.4 Positional accuracy')을 머리글로 잘못 잡으면 그 마디의
    글이 거기서 끊긴다 — 실제로 8.3.3 이 그렇게 잘려 있었다."""
    t = clean(title)
    pat = re.escape(t).replace(r"\ ", r"\s+")
    for rx in (r"(?m)^[ \t]*" + pat, pat):          # 줄머리 먼저, 안 되면 아무 데나
        m = re.compile(rx).search(s, start)
        if m:
            return m.start(), m.end() - m.start()
    return -1, 0


def text_of(doc, toc, i, ends):
    """마디 하나의 글만 잘라 낸다.

    쪽으로만 자르면 상위 마디와 첫 하위 마디가 같은 쪽에서 시작할 때 같은
    글이 두세 번 담긴다 (4 · 4.1 · 4.2 가 모두 1,793자로 같았다).
    그래서 쪽 글 안에서 제 머리글부터 다음 머리글 앞까지로 다시 자른다."""
    lv, title, p = toc[i]
    # 다음 마디가 시작하는 쪽까지 함께 읽는다 — 마지막 월이 쪽을 넘어가는 일이
    # 잦아, 그 쪽을 빼면 글이 낱말 가운데에서 끊긴다 (8.3.3 이 그러하였다).
    # 넘겨 읽은 몫은 아래에서 다음 머리글을 찾아 잘라 낸다.
    s = page_text(doc, p, ends[i] + 1)
    at, ln = _find_head(s, title)
    a = 0 if at < 0 else at + ln
    b = len(s)
    if i + 1 < len(toc):
        c, _ = _find_head(s, toc[i + 1][1], a)
        if c > a:
            b = c
        else:
            # 다음 머리글을 못 찾았으면 넘겨 읽은 쪽을 도로 뺀다
            s = page_text(doc, p, ends[i])
            at, ln = _find_head(s, title)
            a = 0 if at < 0 else at + ln
            b = len(s)
    out = re.sub(r"\n{3,}", "\n\n", s[a:b]).strip()
    # 머리글을 자르고 남은 외톨이 글자를 걷어낸다 — 쪽에 따라 글자 사이가
    # 벌어져 있어 이름의 끝 글자 하나가 본문 첫머리에 남는 일이 있다
    out = re.sub(r"^[A-Za-z]\s*\n", "", out)
    return out.strip()


if __name__ == "__main__":
    import fitz

    if not os.path.exists(SRC):
        sys.exit("원본을 찾지 못했습니다: %s" % SRC)
    doc = fitz.open(SRC)
    toc = doc.get_toc()
    if not toc:
        sys.exit("북마크가 없어 차례를 세울 수 없습니다")

    # 마디마다 글의 끝쪽을 잡는다 — 다음 마디가 시작하는 쪽 앞까지
    ends = []
    for i, (_lv, _t, p) in enumerate(toc):
        nxt = toc[i + 1][2] if i + 1 < len(toc) else doc.page_count + 1
        ends.append(max(p + 1, nxt))

    tree, cur1, cur2 = [], None, None
    seq = named = 0
    for i, (lv, raw, p) in enumerate(toc):
        t = clean(raw)
        ko = KO.get(t, "")
        if ko:
            named += 1
        body = text_of(doc, toc, i, ends)
        num = (re.match(r"^(\d+(?:\.\d+)*)", t) or [None, ""])[1]
        seq += 1
        # 마디 번호(8.3.7)를 따로 지녀 둔다 — 규정 본문의
        # "ISO 19157-1의 8.3.7" 같은 인용이 이것을 보고 찾아온다
        # 옮겨 둔 한국어가 있으면 그것을 쓴다 — 색인을 다시 지어도 잃지 않게
        ko_body = KO_BODY.get(num) or NOTE.get(num, "")
        node = {"id": "iso19157-n%d" % seq, "clause": num,
                "level": "장" if lv == 1 else "조",
                "title": t, "transTitle": ko, "body": body,
                "transBody": ko_body, "children": []}
        if lv == 1:
            node["no"] = len(tree) + 1
            tree.append(node)
            cur1, cur2 = node, None
        else:
            parent = cur2 if (lv >= 3 and cur2) else cur1
            if parent is None:
                continue
            node["no"] = len(parent["children"]) + 1
            parent["children"].append(node)
            if lv == 2:
                cur2 = node

    n_jo = sum(len(c["children"]) + sum(len(g["children"]) for g in c["children"])
               for c in tree)
    stats = {"편": 0, "장": len(tree), "절": 0, "관": 0, "조": n_jo,
             "별표": 0, "별지": 0, "변경": 0}

    out = {
        "id": REGID,
        "name": "ISO 19157-1:2023 Geographic information — Data quality — "
                "Part 1: General requirements",
        "org": "ISO/TC 211",
        "kind": "국제표준",
        "no": "ISO 19157-1:2023",
        "promulgated": "202304",
        "effective": "202304",
        "lang": "en",
        "category": "intl",
        "source": "ISO (구입 문서) — 원본은 이 컴퓨터에만 둔다",
        "localOnly": True,
        "copyright": "© ISO 2023. 저작권이 있는 유료 표준이므로 원본과 이 색인은 "
                     "저장소에 올리지 아니한다.",
        "stats": stats,
        "annex": [], "annexTree": [],
        "indexMode": "전문",
        "localFile": SRC,
        "tree": tree,
        # 제목은 사람이 다 옮겼고, 본문은 저작권 때문에 옮기지 아니한다 —
        # 우리 개정안이 곧바로 기대는 마디에만 해설을 붙였다.
        "translated": {"lang": "en", "coverage": round(named / max(1, len(toc)), 3),
                       "by": "사람이 옮김 — 제목 %d/%d, 본문은 옮기지 아니하고 "
                             "우리 규정이 기대는 %d마디에만 해설을 붙였다"
                             % (named, len(toc), len(NOTE))},
    }
    p = os.path.join(DATA, REGID + ".json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False))
    print("%s — 장 %d · 조 %d · 한국어 이름 %d개 · 해설 %d개" % (
        os.path.basename(p), stats["장"], n_jo, named, len(NOTE)))

    # ---------------------------------------------------------------- 등재
    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    rs = lib["regulations"]
    ent = {k: out[k] for k in ("id", "name", "org", "kind", "no", "effective",
                               "lang", "category", "source", "stats")}
    ent.update({"file": REGID + ".json", "hasFullText": True,
                "indexMode": "전문", "localOnly": True})
    rs[:] = [r for r in rs if r.get("id") != REGID] + [ent]
    io.open(lp, "w", encoding="utf-8", newline="\n").write(json.dumps(lib, ensure_ascii=False))
    print("library.json — %d종 (localOnly 로 등재)" % len(rs))
