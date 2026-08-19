# -*- coding: utf-8 -*-
"""
USGS 3DEP Lidar Base Specification (DOCX) 을 표제 단계에 따라 색인한다.

genlocal.py 의 자동 구조화는 이 문서를 잡지 못한다. 조문 번호도 목차 번호도
없이 워드 표제(Heading1~4)로만 짜여 있기 때문이다. 여기서는 표제 단계를
그대로 편·장·절로 삼고, 표제 사이의 글을 그 마디의 본문으로 담는다.
표제는 한국어 대역을 붙였고, 본문은 원문 그대로 둔다(분량이 커 전문 번역은
따로 한다).

사용:  python scripts/genintl_usgs.py
출력:  data/loc18.json · library.json 갱신
"""
import io, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REG = os.path.join(os.path.dirname(ROOT), "관련규정")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = "국외관련규정\\미국_USGS_FGDC\\USGS_Lidar_Base_Specification_2025_revA.docx"

# 표제의 한국어 대역 — 없는 것은 원문을 그대로 쓴다
KO = {
    "3DEP Lidar Base Specification 2025 rev. A": "3DEP 라이다 기본사양 2025 rev. A",
    "Introduction": "머리말", "Requirement Terminology": "요건 표기법",
    "Revision History": "개정 이력", "Collection Requirements": "취득 요건",
    "Collection Area": "취득 구역", "Quality Level": "품질등급(QL)",
    "Multiple Discrete Returns": "다중 이산 반사", "Intensity Values": "반사강도 값",
    "Nominal Pulse Spacing": "공칭 펄스 간격", "Data Voids": "자료 공백",
    "Spatial Distribution and Regularity": "공간 분포와 규칙성",
    "Collection Conditions": "취득 조건", "Overlap": "중복",
    "Data Processing and Handling": "자료 처리와 취급",
    "ASPRS LAS File Format": "ASPRS LAS 파일 형식", "System Identifier": "시스템 식별자",
    "Time of Global Positioning System Data": "GPS 시각 자료", "Datums": "기준계",
    "Coordinate Reference System": "좌표참조체계", "Well-Known Text": "WKT 표기",
    "Units of Reference": "단위", "File and Point Source Identification": "파일·점 출처 식별",
    "Positional Accuracy Validation": "위치정확도 검증",
    "Absolute Horizontal Accuracy": "절대 수평정확도",
    "Relative Vertical Accuracy": "상대 수직정확도",
    "Intraswath Precision (smooth surface precision)": "스왓 내부 정밀도(평활면 정밀도)",
    "Interswath (Overlap) Consistency": "스왓 간(중복) 일관성",
    "Checkpoints": "검사점", "Deliverables": "제출 성과",
    "Metadata": "메타데이터", "Breaklines": "브레이크라인",
    "Classified Point Data": "분류 점군자료", "Swath Data": "스왓 자료",
    "Digital Elevation Models": "수치표고모델",
    "Lidar Mapping Report": "라이다 매핑 보고서",
    "Tiling Scheme": "타일 체계", "Appendices": "부록",
}


def paras(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        s = st.get(W + "val") if st is not None else "Normal"
        t = "".join(n.text or "" for n in p.iter(W + "t")).strip()
        if t:
            out.append((s or "Normal", t))
    return out


def node(level, no, title, body, tt, nid):
    return {"id": nid, "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편",
            "origTitle": title, "origBody": body,
            "transTitle": tt, "transBody": ""}


def main():
    path = os.path.join(REG, SRC)
    rows = paras(path)
    tree, cur2, cur3, seq = [], None, None, [0, 0, 0]
    buf = []

    def flush(target):
        if target is not None and buf:
            target["body"] = (target["body"] + "\n" + "\n".join(buf)).strip()
        buf.clear()

    for style, text in rows:
        if style == "Heading1":
            continue                                   # 문서 제목
        if style == "Heading2":
            flush(cur3 or cur2)
            seq[0] += 1; seq[1] = 0
            cur2 = node("편", seq[0], text, "", KO.get(text, text), f"iusgs-p{seq[0]}")
            cur3 = None
            tree.append(cur2)
        elif style == "Heading3" and cur2 is not None:
            flush(cur3 or cur2)
            seq[1] += 1; seq[2] = 0
            cur3 = node("장", seq[1], text, "", KO.get(text, text),
                        f"iusgs-c{seq[0]}-{seq[1]}")
            cur2["children"].append(cur3)
        elif style == "Heading4" and cur3 is not None:
            flush(cur3)
            seq[2] += 1
            n4 = node("절", seq[2], text, "", KO.get(text, text),
                      f"iusgs-s{seq[0]}-{seq[1]}-{seq[2]}")
            cur3["children"].append(n4)
            cur3 = n4                                   # 이후 글은 이 절에 담는다
        else:
            buf.append(text)
    flush(cur3 or cur2)

    n_p = len(tree)
    n_c = sum(len(x["children"]) for x in tree)
    n_s = sum(len(y["children"]) for x in tree for y in x["children"])
    doc = {
        "id": "loc18", "name": "USGS 3DEP Lidar Base Specification 2025 rev.A",
        "org": "USGS", "kind": "사양서", "no": "-", "promulgated": "", "effective": "2025",
        "lang": "en", "category": "intl", "source": "",
        "stats": {"편": n_p, "장": n_c, "절": n_s, "관": 0, "조": 0,
                  "별표": 0, "별지": 0, "변경": 0},
        "annex": [], "annexTree": [], "indexMode": "목차",
        "localFile": SRC, "tree": tree,
        "translated": {"lang": "en", "coverage": 0.0, "by": "표제만 옮김"},
    }
    with io.open(os.path.join(DATA, "loc18.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    lib["regulations"] = [r for r in lib["regulations"]
                          if r["id"] not in ("loc18", "ext04")
                          and "USGS Lidar Base Specification" not in r["name"]]
    lib["regulations"].append({
        "id": "loc18", "name": doc["name"], "org": "USGS", "kind": "사양서", "no": "-",
        "effective": "2025", "lang": "en", "category": "intl", "source": "",
        "stats": doc["stats"], "file": "loc18.json", "hasFullText": True,
        "indexMode": "목차", "localFile": SRC,
        "translated": doc["translated"],
    })
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"USGS 라이다 기본사양 — 편 {n_p} · 장 {n_c} · 절 {n_s} 로 색인했습니다.")


if __name__ == "__main__":
    main()
