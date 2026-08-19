# -*- coding: utf-8 -*-
"""
ASPRS Positional Accuracy Standards for Digital Geospatial Data (Edition 2) 를
조문 단위로 세우고 한국어 대역을 붙인다.

원문의 절 번호를 조로 삼는다. 규범 부분(7장)과 검사점 지침을 옮겼고,
표 7.1~7.3 의 판정식은 문장으로 풀어 적었다.

사용:  python scripts/genintl_asprs.py
출력:  data/loc13.json  (덮어쓴다)
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
SRC = "국외관련규정\\2023_ASPRS_Positional_Accuracy_Standards_Edition2_Version1.0.pdf"

CHAPS = [
    ("1", "Purpose, Scope and Limitations", "목적·적용범위와 한계"),
    ("7", "Positional Accuracy Standards", "위치정확도 표준"),
    ("7.1x", "Checkpoints and Reporting", "검사점과 표기"),
]

ART = [
    ("1.1", "Scope and Applicability", "적용범위", "1",
     "These Standards address positional accuracy of digital orthoimagery, digital planimetric "
     "data, and digital elevation data derived from a variety of sources including "
     "photogrammetry, lidar, IFSAR, and other technologies. They are intended to be "
     "technology-agnostic and are based on RMSE rather than on map scale or contour interval.",
     "이 표준은 사진측량, 라이다, 영상레이더 등 여러 기술로 만든 수치정사영상, 수치평면자료, "
     "수치표고자료의 위치정확도를 다룬다. 특정 기술에 매이지 아니하며, 지도축척이나 등고선 "
     "간격이 아니라 평균제곱근오차(RMSE)를 기준으로 삼는다."),

    ("7.1", "Statistical Assessment of Accuracy", "정확도의 통계적 평가", "7",
     "Horizontal accuracy is to be expressed as RMSE_H, derived from the two horizontal error "
     "components RMSE_X and RMSE_Y. Vertical accuracy is to be expressed as RMSE_V. "
     "Three-dimensional positional accuracy is to be expressed as RMSE_3D, derived from RMSE_H "
     "and RMSE_V. Elevation data sets shall also be assessed for horizontal accuracy whenever "
     "possible.",
     "수평정확도는 두 수평 오차성분 RMSE_X 와 RMSE_Y 에서 구한 RMSE_H 로 나타낸다. "
     "수직정확도는 RMSE_V 로 나타낸다. 3차원 위치정확도는 RMSE_H 와 RMSE_V 에서 구한 "
     "RMSE_3D 로 나타낸다. 표고자료도 가능한 한 수평정확도를 함께 평가하여야 한다."),

    ("7.2", "Systematic Error and Mean Error Assumptions", "계통오차와 평균오차의 전제", "7",
     "Except for vertical data in vegetated terrain, the assessment methods assume that the data "
     "set errors are normally distributed and that any significant systematic errors or biases "
     "have been removed. As a rule, these Standards recommend that the mean error be less than "
     "25% of the target RMSE specified for the project. Mean error greater than 25% of the target "
     "RMSE should be investigated to diagnose the cause and reported in the metadata.",
     "식생지역의 표고자료를 빼면, 이 표준의 평가 방법은 자료의 오차가 정규분포를 이루고 뚜렷한 "
     "계통오차나 편의가 제거되었음을 전제로 한다. 원칙적으로 평균오차는 그 사업이 정한 목표 "
     "RMSE 의 25퍼센트 미만이어야 한다. 평균오차가 목표 RMSE 의 25퍼센트를 넘으면 그 까닭을 "
     "밝히고 메타데이터에 적어야 한다."),

    ("7.3", "Horizontal Positional Accuracy Standard", "수평 위치정확도 표준", "7",
     "RMSE_H = sqrt(RMSE_X^2 + RMSE_Y^2). Former ASPRS Standards used discrete accuracy classes "
     "tied to map scale; these Standards do not classify horizontal accuracy discretely, nor do "
     "they tie accuracy class to map scale. The horizontal accuracy class of a data set is "
     "expressed as a function of RMSE_H — for example, a '7.5-cm Horizontal Accuracy Class' means "
     "RMSE_H must be <= 7.5 cm. For orthoimagery mosaics, the allowable mismatch at seamlines is "
     "<= 2 * RMSE_H.",
     "RMSE_H = √(RMSE_X² + RMSE_Y²) 이다. 옛 ASPRS 표준은 지도축척에 매인 등급을 썼으나, 이 "
     "표준은 수평정확도를 등급으로 나누지 아니하고 축척에 매지도 아니한다. 자료의 수평정확도 "
     "등급은 RMSE_H 로 나타낸다. 예를 들어 '7.5cm 수평정확도 등급'이란 RMSE_H 가 7.5센티미터 "
     "이하여야 한다는 뜻이다. 정사영상 모자이크에서 접합선의 어긋남은 2 × RMSE_H 이하여야 "
     "한다."),

    ("7.4", "Vertical Positional Accuracy Standard", "수직 위치정확도 표준", "7",
     "Vertical accuracy is expressed as RMSE_V in both vegetated and non-vegetated terrain. "
     "Non-Vegetated Vertical Accuracy (NVA) must meet the specified threshold; Vegetated Vertical "
     "Accuracy (VVA) has no pass/fail criteria and needs only to be tested and reported as found. "
     "For a '#-cm Vertical Accuracy Class': NVA RMSE_V <= #; within-swath smooth-surface precision "
     "max difference <= 0.60 * #; swath-to-swath non-vegetated RMSD_Z <= 0.80 * #; swath-to-swath "
     "non-vegetated max difference <= 1.60 * #. NVA is computed from checkpoints in open and urban "
     "terrain; VVA from checkpoints in all types of vegetated terrain.",
     "수직정확도는 식생지역과 비식생지역 모두 RMSE_V 로 나타낸다. 비식생 수직정확도(NVA)는 "
     "정해진 한계값을 충족하여야 하나, 식생 수직정확도(VVA)에는 합격·불합격 기준이 없고 "
     "검사하여 나온 대로 알리기만 하면 된다. "
     "'#cm 수직정확도 등급'에서는 NVA 의 RMSE_V 가 # 이하, 스왓 내부 평활면 정밀도의 최대차가 "
     "0.60×# 이하, 스왓 간 비식생 RMSD_Z 가 0.80×# 이하, 스왓 간 비식생 최대차가 1.60×# "
     "이하여야 한다. NVA 는 나지·모래·자갈·짧은 풀과 아스팔트·콘크리트 같은 개활지와 도시지역의 "
     "검사점으로, VVA 는 키 큰 잡초·농경지·관목·숲 등 모든 식생지역의 검사점으로 계산한다."),

    ("7.5", "Three-Dimensional Positional Accuracy Standard", "3차원 위치정확도 표준", "7",
     "RMSE_3D = sqrt(RMSE_X^2 + RMSE_Y^2 + RMSE_Z^2) = sqrt(RMSE_H^2 + RMSE_V^2). "
     "Three-dimensional positional accuracy can be computed for any type of geospatial data as "
     "long as the horizontal and vertical positional accuracy are assessed and reported. Colorized "
     "point clouds and digital twins are good candidates for three-dimensional assessment.",
     "RMSE_3D = √(RMSE_X² + RMSE_Y² + RMSE_Z²) = √(RMSE_H² + RMSE_V²) 이다. "
     "수평·수직 위치정확도를 평가하여 알리기만 하면 어떤 공간자료에도 3차원 위치정확도를 계산할 "
     "수 있다. 색을 입힌 점군과 디지털트윈이 3차원 평가에 알맞은 예이다."),

    ("7.6", "Horizontal Accuracy of Elevation Data", "표고자료의 수평정확도", "7",
     "Elevation data sets shall be assessed for horizontal accuracy whenever possible. For lidar "
     "data, horizontal accuracy is typically estimated from the sensor and platform parameters "
     "rather than measured at checkpoints, and shall be reported in the metadata.",
     "표고자료는 가능한 한 수평정확도를 함께 평가하여야 한다. 라이다 자료의 수평정확도는 "
     "검사점으로 재기보다 센서와 플랫폼의 제원에서 추정하는 것이 보통이며, 그 값을 "
     "메타데이터에 적어야 한다."),

    ("7.12", "Checkpoint Accuracy and Placement", "검사점의 정확도와 배치", "7.1x",
     "Checkpoints used for product accuracy assessment shall be at least two times more accurate "
     "than the required accuracy of the geospatial product being evaluated. To avoid a biased "
     "assessment, a checkpoint should be located away from any ground control points used in the "
     "initial processing and calibration. Horizontal checkpoints shall be established at "
     "well-defined points. Checkpoints for vertical accuracy shall be surveyed in open terrain "
     "that is flat or of gentle and uniform slope, and should not be placed near vertical "
     "artifacts or abrupt changes in elevation (preferably 3 meters or more away).",
     "성과의 정확도를 평가하는 데에 쓰는 검사점은 평가 대상 성과가 요구하는 정확도보다 적어도 "
     "두 배 이상 정확하여야 한다. 평가가 한쪽으로 치우치지 아니하도록 검사점은 처음 처리와 "
     "검정에 쓴 지상기준점에서 떨어진 곳에 둔다. 수평 검사점은 명확히 정의된 점에 설치한다. "
     "수직정확도용 검사점은 평탄하거나 완만하고 고른 경사의 개활지에서 측량하며, 수직 구조물이나 "
     "표고가 급격히 바뀌는 곳 가까이(되도록 3미터 이내)에는 두지 아니한다."),

    ("7.13", "Checkpoint Density and Distribution", "검사점의 밀도와 배치", "7.1x",
     "Checkpoints should be well distributed around the project area. In no case shall the "
     "assessment of planimetric accuracy of digital orthoimagery be based on fewer than thirty "
     "(30) checkpoints. Similarly, the assessment of the NVA or VVA of elevation data should be "
     "based on no fewer than thirty (30) checkpoints each. If fewer than thirty checkpoints are "
     "used, a special reporting statement shall be included.",
     "검사점은 사업 구역에 고루 배치한다. 수치정사영상의 평면정확도 평가는 어떤 경우에도 "
     "검사점 30점 미만으로 하여서는 아니 된다. 표고자료의 NVA 와 VVA 도 각각 30점 이상으로 "
     "평가한다. 30점 미만으로 평가한 경우에는 그 사실을 밝히는 문구를 함께 적어야 한다."),

    ("7.14", "Data Internal Precision of Lidar and IFSAR Data", "라이다·영상레이더의 내부 정밀도",
     "7.1x",
     "Data internal precision (relative accuracy) is assessed by within-swath (smooth-surface) "
     "precision and swath-to-swath precision. Within-swath precision is measured as the maximum "
     "difference over smooth, hard surfaces; swath-to-swath precision is measured as RMSD_Z and "
     "maximum difference between overlapping swaths in non-vegetated terrain.",
     "자료의 내부 정밀도(상대정확도)는 스왓 내부(평활면) 정밀도와 스왓 간 정밀도로 평가한다. "
     "스왓 내부 정밀도는 평평하고 단단한 면에서의 최대차로, 스왓 간 정밀도는 겹치는 스왓 사이의 "
     "비식생지역 RMSD_Z 와 최대차로 잰다."),

    ("7.15", "Accuracy Reporting", "정확도 표기", "7.1x",
     "Accuracy shall be reported as the Accuracy Class and the computed RMSE values, together "
     "with the number of checkpoints used and their distribution. Data producers shall report "
     "the tested accuracy in the metadata, including any departures from these Standards such as "
     "the use of fewer than thirty checkpoints.",
     "정확도는 정확도 등급과 계산된 RMSE 값, 그리고 쓰인 검사점의 수와 배치를 함께 알린다. "
     "자료를 만든 자는 검사한 정확도를 메타데이터에 적어야 하며, 검사점을 30점 미만으로 쓴 "
     "것처럼 이 표준에서 벗어난 사항이 있으면 함께 적어야 한다."),
]


def node(level, no, title, body, tt, tb, nid):
    return {"id": nid, "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편",
            "origTitle": title, "origBody": body,
            "transTitle": tt, "transBody": tb}


def main():
    path = os.path.join(DATA, "loc13.json")
    doc = json.load(io.open(path, encoding="utf-8"))
    root = node("편", 1,
                "ASPRS Positional Accuracy Standards for Digital Geospatial Data, Edition 2", "",
                "ASPRS 수치공간자료 위치정확도 표준 제2판", "", "iasprs-p1")
    cmap = {}
    for i, (key, en, ko) in enumerate(CHAPS, start=1):
        c = node("장", i, en, "", ko, "", f"iasprs-c{i}")
        cmap[key] = c
        root["children"].append(c)
    n = 0
    for sec, en, ko, ch, body, trans in ART:
        n += 1
        a = node("조", n, en, body, ko, trans, f"iasprs-a{n}")
        a["legacyNo"] = sec
        cmap[ch]["children"].append(a)

    doc["tree"] = [root]
    doc["localFile"] = SRC
    doc["indexMode"] = "조문"
    doc["stats"] = {"편": 1, "장": len(CHAPS), "조": n, "항": 0, "호": 0}
    doc["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for r in lib["regulations"]:
        if r["id"] == "loc13":
            r["stats"] = {"편": 1, "장": len(CHAPS), "절": 0, "관": 0, "조": n,
                          "별표": 0, "별지": 0, "변경": 0}
            r["indexMode"] = "조문"
            r["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, separators=(",", ":"))
    print(f"ASPRS — 장 {len(CHAPS)} · 조 {n} · 모두 한국어 대역을 붙였습니다 → {path}")


if __name__ == "__main__":
    main()
