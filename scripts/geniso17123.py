# -*- coding: utf-8 -*-
"""
ISO 17123 시리즈(측량기기 현장 시험방법) 색인 만들기

ISO 표준은 유료 저작물이므로 본문은 담지 않는다.
공개된 서지정보(표준번호·제목·판·적용 대상)와 ISO 카탈로그 링크만 모아
참조 규정 창에서 훑어볼 수 있게 한다.

개편안 초안(2025)의 다음 조문이 이 시리즈를 근거로 삼는다.
  · 제1편 「기술중립성 및 신기술 특례」 제4항
  · 제7편 「측량장비의 성능검사」 제2항
  근거: 2025년 전략수립 연구보고서 부록4 A-4

사용:  python scripts/geniso17123.py
출력:  data/iso17123.json, library.json 에 항목 추가
"""
import io, json, os, sys, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

BUY = ("본문은 ISO 유료 표준입니다. iso.org 또는 한국표준협회에서 구입하고, "
       "국내 부합화(KS) 여부는 e나라표준인증(standard.go.kr)에서 확인하십시오.")

# (파트, 제목(영문), 제목(국문), 판, ISO 카탈로그 번호, 적용 대상, 공공측량에서의 쓰임)
PARTS = [
    ("1", "Theory", "이론", "2014", "64156",
     "시험 결과의 통계 처리 — 표준편차 산정, 통계 검정(카이제곱·F 검정)의 공통 이론",
     "각 파트의 판정에 쓰는 통계 절차의 근거. 성능검사 결과를 신뢰수준과 함께 적을 때 준거가 된다."),
    ("2", "Levels", "레벨", "2001", "30199",
     "기포관 레벨, 컴펜세이터 레벨, 디지털 레벨과 부속 장비의 정밀도",
     "공공수준점측량에 쓰는 레벨의 성능 확인. 개편안이 디지털레벨을 기본 장비로 두는 근거와 짝을 이룬다."),
    ("3", "Theodolites", "데오드라이트", "2001", "30200",
     "수평각·연직각 측정 정밀도",
     "각 측정 장비의 성능 확인. 현행 규정의 '트랜싯트/데오드라이트' 용어 혼용 정비와 함께 본다."),
    ("4", "Electro-optical distance meters (EDM measurements to reflectors)",
     "광파거리측량기 (반사경 대상 거리측정)", "2012", "54624",
     "반사경을 대상으로 하는 광파거리측량기의 거리 측정 정밀도",
     "거리 관측 장비의 성능 확인."),
    ("5", "Total stations", "토털스테이션", "2018", "71689",
     "토털스테이션의 좌표 측정 정밀도",
     "공공삼각점측량·세부측량에 쓰는 주력 장비의 성능 확인."),
    ("6", "Rotating lasers", "회전 레이저", "2022", "78133",
     "회전 레이저의 정밀도",
     "시공측량·건축측량에서 쓰는 레벨링 장비."),
    ("7", "Optical plumbing instruments", "광학 구심기", "2005", "38911",
     "구심(鉛直) 장비의 정밀도",
     "고층 구조물 연직 관측 장비."),
    ("8", "GNSS field measurement systems in real-time kinematic (RTK)",
     "실시간 이동측위(RTK) GNSS 현장 측량 시스템", "2015", "62961",
     "RTK 방식 GNSS 측량 시스템의 정밀도",
     "RTK-GNSS 공공삼각점측량·세부측량과 네트워크 RTK 측량 장비의 성능 확인. "
     "품관원 검토의견이 지적한 RTK 반복관측·교차기준과 직접 이어진다."),
    ("9", "Terrestrial laser scanners", "지상레이저 스캐너", "2018", "68382",
     "지상레이저 스캐너의 정밀도",
     "개편안 제4편 제2장 지상레이저측량의 장비 성능 기준. "
     "'요구 성능을 갖춘 것을 쓴다'는 조문의 시험방법 근거."),
    ("11", "GNSS instruments", "GNSS 측량기", "제정 진행 중", "85271",
     "GNSS 측량기 전반의 시험방법 (ISO/FDIS 단계)",
     "제정되면 제8부와 함께 GNSS 장비 성능검사의 근거가 된다."),
]

SERIES_EN = "Optics and optical instruments — Field procedures for testing geodetic and surveying instruments"
SERIES_KO = "광학 및 광학기기 — 측지·측량 기기의 현장 시험방법"


def node(level, no, title, body, legacy=""):
    return {"id": f"iso17123-{level}-{no}", "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": legacy,
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편"}


if __name__ == "__main__":
    kids = []
    for i, (part, en, ko, ed, cat, scope, use) in enumerate(PARTS, start=1):
        body = (f"영문 제목  {SERIES_EN} — Part {part}: {en}\n"
                f"판        {ed}\n"
                f"적용 대상  {scope}\n"
                f"공공측량에서의 쓰임  {use}\n"
                f"원문      https://www.iso.org/standard/{cat}.html\n"
                f"안내      {BUY}")
        kids.append(node("조", i, f"제{part}부 {ko}", body, f"ISO 17123-{part}"))

    tree = [{
        "id": "iso17123-part-1", "level": "편", "no": 1, "branch": 0,
        "title": f"ISO 17123 시리즈 — {SERIES_KO}",
        "body": ("이 색인은 서지정보와 적용 대상만 담은 것으로, 표준 본문이 아닙니다.\n"
                 + BUY),
        "status": "유지", "legacyNo": "", "reason": "", "sourceRef": None,
        "history": [], "children": kids, "collapsed": False,
    }]

    doc = {
        "id": "loc17", "name": "ISO 17123 시리즈 (측량기기 현장 시험방법) — 목록·개요",
        "org": "ISO/TC 172", "kind": "국제표준", "no": "ISO 17123",
        "promulgated": "", "effective": "2001~", "lang": "ko", "category": "intl",
        "source": "https://www.iso.org/committee/53832/x/catalogue/",
        "stats": {"편": 1, "장": 0, "절": 0, "관": 0, "조": len(kids)},
        "annex": [], "annexTree": [], "indexMode": "목록",
        "note": "ISO 표준은 유료 저작물이므로 본문은 담지 않았습니다. " + BUY,
        "tree": tree,
    }
    with io.open(os.path.join(DATA, "loc17.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    libpath = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    lib["regulations"] = [r for r in lib["regulations"] if r["id"] != "loc17"]
    e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                             "lang", "category", "source", "stats")}
    e["file"] = "loc17.json"
    e["hasFullText"] = True
    e["indexMode"] = "목록"
    e["metaOnly"] = True          # 본문이 아니라 서지정보만
    lib["regulations"].append(e)
    lib["generated"] = time.strftime("%Y-%m-%d")
    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(f"ISO 17123 색인 {len(kids)}개 파트 → data/loc17.json")
    for p in PARTS:
        print(f"  ISO 17123-{p[0]:<2} ({p[3]:>4})  {p[2]}")
