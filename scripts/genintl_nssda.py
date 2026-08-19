# -*- coding: utf-8 -*-
"""
FGDC-STD-007.3-1998 NSSDA 를 조문 단위로 다시 세우고 한국어 대역을 붙인다.

지금까지는 PDF 글줄을 그대로 담아 두어 조문 구조도 없고 번역도 없었다.
원문의 절 번호를 그대로 조로 삼고, body 에는 원문을, transBody 에는
한국어 번역을 넣는다. 번역은 규범 문장을 그대로 옮기는 것을 원칙으로 하되,
우리 규정에서 쓰는 말(정확도·검사점·성과 등)에 맞추었다.

사용:  python scripts/genintl_nssda.py
출력:  data/loc14.json  (덮어쓴다)
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

SRC = ("국외관련규정\\미국_USGS_FGDC\\"
       "FGDC-STD-007.3-1998_NSSDA_Geospatial_Positioning_Accuracy_Standards_Part3.pdf")

# (절 번호, 영문 제목, 한글 제목, 원문, 번역)
ART = [
    ("3.1.1", "Objective", "목적",
     "The National Standard for Spatial Data Accuracy (NSSDA) implements a statistical and "
     "testing methodology for estimating the positional accuracy of points on maps and in "
     "digital geospatial data, with respect to georeferenced ground positions of higher "
     "accuracy.",
     "국가공간자료정확도표준(NSSDA)은 지도와 수치공간자료에 있는 점의 위치정확도를, 그보다 "
     "정확도가 높은 기준 지상위치에 견주어 추정하기 위한 통계·검사 방법을 정한다."),

    ("3.1.2", "Scope", "적용범위",
     "The NSSDA applies to fully georeferenced maps and digital geospatial data, in either "
     "raster, point, or vector format, derived from sources such as aerial photographs, "
     "satellite imagery, and ground surveys. It provides a common language for reporting "
     "accuracy to facilitate the identification of spatial data for geographic applications. "
     "This standard does not define threshold accuracy values. Agencies are encouraged to "
     "establish thresholds for their product specifications and applications and for "
     "contracting purposes. Ultimately, users identify acceptable accuracies for their "
     "applications. Data and map producers must determine what accuracy exists or is "
     "achievable for their data and report it according to NSSDA.",
     "이 표준은 항공사진, 위성영상, 지상측량 등에서 얻어 좌표가 완전히 부여된 지도와 "
     "수치공간자료에 적용하며, 래스터·점·벡터 어느 형식이든 적용한다. 정확도를 알리는 공통의 "
     "말을 제공하여 이용자가 목적에 맞는 공간자료를 가려낼 수 있게 한다. "
     "이 표준은 정확도의 한계값(문턱값)을 정하지 아니한다. 기관은 제품사양과 용도, 계약을 위하여 "
     "스스로 한계값을 정하도록 권장된다. 어떤 정확도를 받아들일지는 결국 이용자가 정하며, "
     "자료와 지도를 만드는 자는 그 자료가 지닌, 또는 이룰 수 있는 정확도를 정하여 이 표준에 "
     "따라 알려야 한다."),

    ("3.1.3", "Applicability", "적용 대상",
     "Use the NSSDA to evaluate and report the positional accuracy of maps and geospatial data "
     "produced, revised, or disseminated by or for the Federal Government. Accuracy of new or "
     "revised spatial data will be reported according to the NSSDA. Accuracy of existing or "
     "legacy spatial data and maps may be reported, as specified, according to the NSSDA or the "
     "accuracy standard by which they were evaluated.",
     "연방정부가 만들거나 고치거나 배포하는(또는 그를 위하여 만들어지는) 지도와 공간자료의 "
     "위치정확도를 평가하고 알리는 데에 이 표준을 쓴다. 새로 만들거나 고친 공간자료의 정확도는 "
     "이 표준에 따라 알린다. 이미 있는 자료와 지도의 정확도는 이 표준에 따르거나, 그 자료를 "
     "평가할 때 쓴 정확도 표준에 따라 알릴 수 있다."),

    ("3.2.1", "Spatial Accuracy", "공간정확도",
     "The NSSDA uses root-mean-square error (RMSE) to estimate positional accuracy. RMSE is the "
     "square root of the average of the set of squared differences between dataset coordinate "
     "values and coordinate values from an independent source of higher accuracy for identical "
     "points. Accuracy is reported in ground distances at the 95% confidence level. Accuracy "
     "reported at the 95% confidence level means that 95% of the positions in the dataset will "
     "have an error with respect to true ground position that is equal to or smaller than the "
     "reported accuracy value. The reported accuracy value reflects all uncertainties, including "
     "those introduced by geodetic control coordinates, compilation, and final computation of "
     "ground coordinate values in the product.",
     "이 표준은 위치정확도를 평균제곱근오차(RMSE)로 추정한다. 평균제곱근오차란 같은 점에 대하여 "
     "자료의 좌표값과, 그보다 정확도가 높은 독립된 자료의 좌표값 사이의 차를 제곱하여 평균한 "
     "값의 제곱근을 말한다. "
     "정확도는 지상거리로, 95퍼센트 신뢰수준으로 알린다. 95퍼센트 신뢰수준으로 알린다는 것은 "
     "그 자료에 있는 위치의 95퍼센트가 참 지상위치에 대하여 알린 정확도값과 같거나 그보다 작은 "
     "오차를 가진다는 뜻이다. 알린 정확도값에는 기준점 좌표, 편집, 최종 지상좌표 계산에서 생긴 "
     "것을 비롯한 모든 불확실성이 담겨 있다."),

    ("3.2.2", "Accuracy Test Guidelines", "정확도 검사 지침",
     "Accuracy testing by an independent source of higher accuracy is the preferred test for "
     "positional accuracy. The independent source of higher accuracy shall be the highest "
     "accuracy feasible and practicable to evaluate the accuracy of the dataset. "
     "Horizontal accuracy shall be tested by comparing the planimetric coordinates of "
     "well-defined points in the dataset with coordinates of the same points from an independent "
     "source of higher accuracy. Vertical accuracy shall be tested by comparing the elevations in "
     "the dataset with elevations of the same points as determined from an independent source of "
     "higher accuracy. Errors in recording or processing data, such as reversing signs or "
     "inconsistencies between the dataset and independent source of higher accuracy in coordinate "
     "reference system definition, must be corrected before computing the accuracy value. "
     "A minimum of 20 check points shall be tested, distributed to reflect the geographic area of "
     "interest and the distribution of error in the dataset. When 20 points are tested, the 95% "
     "confidence level allows one point to fail the threshold given in product specifications. "
     "If fewer than twenty points can be identified for testing, use an alternative means to "
     "evaluate the accuracy of the dataset: deductive estimate, internal evidence, or comparison "
     "to source.",
     "위치정확도는 그보다 정확도가 높은 독립된 자료로 검사하는 것을 우선한다. 그 독립된 자료는 "
     "자료의 정확도를 평가하는 데에 실현할 수 있는 가장 높은 정확도의 것이어야 한다. "
     "수평정확도는 자료에 있는 명확히 정의된 점의 평면좌표를, 그보다 정확도가 높은 독립된 "
     "자료에서 얻은 같은 점의 좌표와 견주어 검사한다. 수직정확도는 자료의 표고를, 그보다 "
     "정확도가 높은 독립된 자료에서 정한 같은 점의 표고와 견주어 검사한다. 부호를 뒤바꾸었거나 "
     "두 자료의 좌표계 정의가 어긋나는 것과 같은 기록·처리의 잘못은 정확도값을 계산하기 전에 "
     "바로잡아야 한다. "
     "검사점은 적어도 20점을 검사하며, 관심 지역과 자료의 오차 분포를 반영하도록 고루 배치한다. "
     "20점을 검사하는 경우 95퍼센트 신뢰수준에서는 제품사양의 한계값을 넘는 점이 1점까지 "
     "허용된다. 검사할 점을 20점 미만밖에 찾을 수 없으면 연역적 추정, 내부 증거, 원자료와의 "
     "비교와 같은 다른 방법으로 정확도를 평가한다."),

    ("3.2.3", "Accuracy Reporting", "정확도 표기",
     "Positional accuracy values shall be reported in ground distances. Metric units shall be "
     "used when the dataset coordinates are in meters. The number of significant places for the "
     "accuracy value shall be equal to the number of significant places for the dataset point "
     "coordinates. "
     "Report accuracy at the 95% confidence level for data tested for both horizontal and "
     "vertical accuracy as: 'Tested ____ (meters, feet) horizontal accuracy at 95% confidence "
     "level; ____ (meters, feet) vertical accuracy at 95% confidence level.' "
     "Use the 'compiled to meet' statement when testing by an independent source of higher "
     "accuracy cannot be followed and an alternative means is used: 'Compiled to meet ____ "
     "(meters, feet) horizontal accuracy at 95% confidence level.' "
     "If data of varying accuracies can be identified separately in a dataset, compute and report "
     "separate accuracy values. If a composited dataset is not tested, report the accuracy value "
     "for the least accurate dataset component.",
     "위치정확도값은 지상거리로 알린다. 자료의 좌표가 미터인 경우에는 미터 단위를 쓴다. "
     "정확도값의 유효자릿수는 자료 좌표의 유효자릿수와 같게 한다. "
     "수평·수직 정확도를 모두 검사한 자료는 95퍼센트 신뢰수준으로 다음과 같이 알린다 — "
     "'검사 결과 수평정확도 ____m(95퍼센트 신뢰수준), 수직정확도 ____m(95퍼센트 신뢰수준)'. "
     "정확도가 더 높은 독립된 자료로 검사할 수 없어 다른 방법으로 평가한 경우에는 "
     "'____m의 수평정확도를 충족하도록 작성함(95퍼센트 신뢰수준)' 과 같이 적는다. "
     "한 자료 안에서 정확도가 다른 부분을 따로 가려낼 수 있으면 각각 계산하여 따로 알린다. "
     "합쳐진 자료를 검사하지 아니한 경우에는 그 가운데 가장 낮은 정확도값을 알린다."),

    ("3.3", "NSSDA and Other Map Accuracy Standards", "다른 지도정확도 표준과의 관계",
     "Accuracy of new or revised spatial data will be reported according to the NSSDA. If accuracy "
     "reporting cannot be provided using NSSDA or other recognized standards, provide information "
     "to enable users to evaluate how the data fit their application requirements. This "
     "information may include descriptions of the source material from which the data were "
     "compiled, accuracy of ground surveys associated with compilation, digitizing procedures, "
     "equipment, and quality control procedures used in production. No matter what method is used "
     "to evaluate positional accuracy, explain the accuracy of coordinate measurements and "
     "describe the tests in digital geospatial metadata.",
     "새로 만들거나 고친 공간자료의 정확도는 이 표준에 따라 알린다. 이 표준이나 그 밖에 인정된 "
     "표준으로 정확도를 알릴 수 없는 경우에는, 이용자가 그 자료가 자신의 용도에 맞는지 판단할 수 "
     "있도록 정보를 제공한다. 그 정보에는 자료를 만든 원자료의 설명, 편집에 쓰인 지상측량의 "
     "정확도, 수치화 절차, 장비, 제작에 쓰인 품질관리 절차 등이 들어간다. 어떤 방법으로 "
     "위치정확도를 평가하였든, 좌표 측정의 정확도를 설명하고 검사 내용을 수치공간 메타데이터에 "
     "적어야 한다."),

    ("3-A.1", "Horizontal Accuracy Statistic (normative)", "수평정확도 통계 (규범)",
     "Horizontal error at point i is defined as sqrt((x_data,i - x_check,i)^2 + "
     "(y_data,i - y_check,i)^2). RMSE_x = sqrt(sum(x_data,i - x_check,i)^2 / n); RMSE_y is "
     "computed in the same way; RMSE_r = sqrt(RMSE_x^2 + RMSE_y^2). "
     "If RMSE_x = RMSE_y, Accuracy_r = 2.4477 * 0.5 * (RMSE_x + RMSE_y) = 1.7308 * RMSE_r. "
     "If RMSE_x and RMSE_y differ but RMSE_min/RMSE_max is between 0.6 and 1.0, the same "
     "approximation may be used.",
     "점 i 의 수평오차는 √((자료 x_i − 검사점 x_i)² + (자료 y_i − 검사점 y_i)²) 로 정의한다. "
     "RMSE_x = √(Σ(자료 x_i − 검사점 x_i)² / n) 이며 RMSE_y 도 같은 방법으로 구하고, "
     "RMSE_r = √(RMSE_x² + RMSE_y²) 이다. "
     "RMSE_x 와 RMSE_y 가 같으면 수평정확도 = 2.4477 × 0.5 × (RMSE_x + RMSE_y) = "
     "1.7308 × RMSE_r 이다. 두 값이 다르더라도 작은 값과 큰 값의 비가 0.6 이상 1.0 이하이면 "
     "같은 근사식을 쓸 수 있다."),

    ("3-A.2", "Vertical Accuracy Statistic (normative)", "수직정확도 통계 (규범)",
     "Vertical RMSE_z = sqrt(sum(z_data,i - z_check,i)^2 / n). Vertical accuracy at the 95% "
     "confidence level, Accuracy_z = 1.9600 * RMSE_z.",
     "수직 RMSE_z = √(Σ(자료 z_i − 검사점 z_i)² / n) 이다. 95퍼센트 신뢰수준의 수직정확도는 "
     "Accuracy_z = 1.9600 × RMSE_z 이다."),

    ("3-C.1", "Well-defined points", "명확히 정의된 점",
     "Well-defined points represent features for which the horizontal position is known to a high "
     "degree of accuracy and position with respect to the geodetic datum. For the purpose of "
     "accuracy testing, well-defined points must be easily visible or recoverable on the ground, "
     "on the independent source of higher accuracy, and on the product itself. Examples are "
     "intersections of roads and railroads, and small isolated shrubs.",
     "'명확히 정의된 점'이란 측지기준계에 대한 수평위치를 높은 정확도로 알 수 있는 지물을 "
     "말한다. 정확도 검사를 위해서는 그 점이 현지에서, 정확도가 더 높은 독립된 자료에서, 그리고 "
     "성과물 자체에서 모두 쉽게 보이거나 되찾을 수 있어야 한다. 도로와 철도의 교차점, 홀로 선 "
     "작은 관목 등이 그 예이다."),

    ("3-C.3", "Distribution of check points", "검사점의 배치",
     "Check points shall be distributed so that they reflect the geographic area of interest and "
     "the distribution of error in the dataset. When the distribution of error is unknown, a "
     "quadrant-based distribution is recommended: at least 20% of the points in each quadrant of "
     "the dataset, spaced at intervals of at least 10% of the diagonal distance across the "
     "dataset.",
     "검사점은 관심 지역과 자료의 오차 분포를 반영하도록 배치한다. 오차 분포를 알 수 없는 "
     "경우에는 사분면에 따라 배치할 것을 권장한다. 곧 자료를 네 사분면으로 나누어 각 사분면에 "
     "적어도 전체의 20퍼센트를 두고, 점 사이의 간격은 자료 대각선 길이의 10퍼센트 이상으로 "
     "한다."),
]


def node(level, no, title, body, trans_title, trans_body, nid):
    return {"id": nid, "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편",
            "origTitle": title, "origBody": body,
            "transTitle": trans_title, "transBody": trans_body}


def main():
    path = os.path.join(DATA, "loc14.json")
    doc = json.load(io.open(path, encoding="utf-8"))

    root = node("편", 1, "Part 3: National Standard for Spatial Data Accuracy (NSSDA)", "",
                "제3부 국가공간자료정확도표준(NSSDA)", "", "inssda-p1")
    chaps = [
        ("3.1", "Introduction", "총설"),
        ("3.2", "Testing Methodology and Reporting Requirements", "검사 방법과 표기 요건"),
        ("3.3", "NSSDA and Other Map Accuracy Standards", "다른 표준과의 관계"),
        ("3-A", "Appendix 3-A. Accuracy Statistics (normative)", "부록 3-A 정확도 통계 (규범)"),
        ("3-C", "Appendix 3-C. Testing Guidelines (informative)", "부록 3-C 검사 지침 (참고)"),
    ]
    cmap = {}
    for i, (key, en, ko) in enumerate(chaps, start=1):
        c = node("장", i, en, "", ko, "", f"inssda-c{i}")
        cmap[key] = c
        root["children"].append(c)

    n = 0
    for sec, en, ko, body, trans in ART:
        n += 1
        key = sec.rsplit(".", 1)[0] if sec.count(".") > 1 else sec
        if sec.startswith("3-A"):
            key = "3-A"
        elif sec.startswith("3-C"):
            key = "3-C"
        elif sec.startswith("3.3"):
            key = "3.3"
        a = node("조", n, en, body, ko, trans, f"inssda-a{n}")
        a["legacyNo"] = sec
        cmap[key]["children"].append(a)

    doc["tree"] = [root]
    doc["localFile"] = SRC
    doc["indexMode"] = "조문"
    doc["stats"] = {"편": 1, "장": len(chaps), "조": n, "항": 0, "호": 0}
    doc["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    # 목록(library.json)의 통계와 표시도 함께 고친다
    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for r in lib["regulations"]:
        if r["id"] == "loc14":
            r["stats"] = {"편": 1, "장": len(chaps), "절": 0, "관": 0, "조": n,
                          "별표": 0, "별지": 0, "변경": 0}
            r["indexMode"] = "조문"
            r["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, separators=(",", ":"))
    print(f"NSSDA — 장 {len(chaps)} · 조 {n} · 모두 한국어 대역을 붙였습니다 → {path}")


if __name__ == "__main__":
    main()
