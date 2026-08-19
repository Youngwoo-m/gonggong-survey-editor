# -*- coding: utf-8 -*-
"""
호주 WA Main Roads 측지기준점측량 표준과 뉴질랜드 LINZ 지적측량규칙 전환 안내를
조문 단위로 세우고 한국어 대역을 붙인다.

원문의 절 번호를 조로 삼고, body 에 원문을, transBody 에 번역을 넣는다.
수치 기준(0.012√K, 0.006m, 50분+2분/km 등)은 원문 그대로 옮겼다.

사용:  python scripts/genintl_wa_linz.py
출력:  data/loc16.json (WA) · data/loc15.json (LINZ)
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


def node(level, no, title, body, tt, tb, nid):
    return {"id": nid, "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편",
            "origTitle": title, "origBody": body,
            "transTitle": tt, "transBody": tb}


def build(doc_id, part_en, part_ko, chaps, arts, src):
    path = os.path.join(DATA, f"{doc_id}.json")
    doc = json.load(io.open(path, encoding="utf-8"))
    root = node("편", 1, part_en, "", part_ko, "", f"i{doc_id}-p1")
    cmap = {}
    for i, (key, en, ko) in enumerate(chaps, start=1):
        c = node("장", i, en, "", ko, "", f"i{doc_id}-c{i}")
        cmap[key] = c
        root["children"].append(c)
    n = 0
    for sec, en, ko, ch, body, trans in arts:
        n += 1
        a = node("조", n, en, body, ko, trans, f"i{doc_id}-a{n}")
        a["legacyNo"] = sec
        cmap[ch]["children"].append(a)
    doc["tree"] = [root]
    doc["localFile"] = src
    doc["indexMode"] = "조문"
    doc["stats"] = {"편": 1, "장": len(chaps), "조": n, "항": 0, "호": 0}
    doc["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for r in lib["regulations"]:
        if r["id"] == doc_id:
            r["stats"] = {"편": 1, "장": len(chaps), "절": 0, "관": 0, "조": n,
                          "별표": 0, "별지": 0, "변경": 0}
            r["indexMode"] = "조문"
            r["translated"] = {"lang": "en", "coverage": 1.0, "by": "사람이 옮김"}
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, separators=(",", ":"))
    return n


# ════════════════ 호주 WA Main Roads ════════════════
WA_CHAPS = [
    ("A", "Purpose, Scope and Datum", "목적·적용범위와 기준계"),
    ("B", "Observations", "관측"),
    ("C", "Geodetic Control Point Precision", "기준점 정밀도"),
    ("D", "Adjustment and Lodgement", "조정과 성과 제출"),
]
WA = [
    ("1", "Purpose", "목적", "A",
     "The purpose of this Standard is to detail Main Roads requirements for Geodetic Control "
     "Surveys that provide the survey control for projects. This standard replaces MRWA standards "
     "Standard Survey Mark Control 67-08-35, Road Reference Marks 67-08-36, Minor Control Points "
     "67-08-37 and Differential Levelling 67-08-38.",
     "이 표준은 사업의 측량기준을 이루는 측지기준점측량에 대하여 주도로청(Main Roads)이 요구하는 "
     "사항을 정한다. 이 표준은 종전의 표준측량표 관리(67-08-35), 도로기준표(67-08-36), "
     "소기준점(67-08-37), 직접수준측량(67-08-38)을 갈음한다."),

    ("2", "Scope", "적용범위", "A",
     "This Standard shall apply for all Geodetic Control established for Main Roads projects.",
     "이 표준은 주도로청 사업을 위하여 설치하는 모든 측지기준점에 적용한다."),

    ("5", "Reference Datum", "기준계", "A",
     "The horizontal positions of all MRWA projects will be supplied in the GDA2020 datum and the "
     "coordinates projected using the relevant project grid. Under no circumstances is data "
     "transformed from superseded datums (such as GDA94) to be presented as GDA2020. If requested "
     "to provide transformed data, the use of a transformation is to be clearly highlighted on the "
     "metadata statement and in the accompanying report, stating which transformation method has "
     "been used. The level datum shall be AHD71 unless an alternative is specified.",
     "모든 사업의 수평위치는 GDA2020 기준계로 제출하며, 좌표는 해당 사업의 투영에 따른다. "
     "폐지된 기준계(GDA94 등)에서 변환한 자료를 GDA2020 성과인 것처럼 제출하여서는 어떠한 경우에도 "
     "아니 된다. 변환 자료를 요구받아 제출하는 경우에는 변환을 썼다는 사실과 쓴 변환 방법을 "
     "메타데이터와 보고서에 뚜렷이 밝혀야 한다. 높이 기준은 따로 정하지 아니하면 AHD71 로 한다."),

    ("6", "GNSS Observations", "GNSS 관측", "B",
     "The use of GNSS baselines is the preferred method to observe both SSMs and RRMs. All survey "
     "control networks should contain only independent baselines; trivial baselines within a "
     "network should be removed to allow the network to adjust freely and report the uncertainties "
     "correctly. For each GNSS session with n receivers logging, there are n-1 independent "
     "baselines. The network within the project area must be fully connected and cohesive, with "
     "ties out to the geodetic framework to connect it to the datum.",
     "표준측량표와 도로기준표는 GNSS 기선으로 관측하는 것을 우선한다. 모든 기준점망은 독립기선만으로 "
     "이루어져야 하며, 망 안의 종속기선은 걷어 내어 망이 자유롭게 조정되고 불확실도가 바르게 "
     "산출되도록 한다. 수신기 n 대가 동시에 기록하는 세션 하나에서 독립기선은 n−1 개다. "
     "사업 구역 안의 망은 빠짐없이 이어져 하나로 묶여야 하며, 기준계에 잇기 위하여 측지기준망까지 "
     "연결하여야 한다."),

    ("7", "Differential Levelling", "직접수준측량", "B",
     "For every new project it is first necessary to verify the stability of any existing survey "
     "marks on which the new work is to be based. To verify height, original reference marks at "
     "existing control must be found and the height difference to the primary mark measured where "
     "the RMs exist. This documentation must be supplied to MRWA.",
     "새 사업에서는 먼저 그 사업이 딛고 설 기존 측량표가 안정되어 있는지 확인하여야 한다. 높이를 "
     "확인하려면 기존 기준점의 원래 참조표를 찾아, 참조표가 있는 곳에서는 주표와의 고저차를 재어야 "
     "한다. 그 기록은 주도로청에 제출한다."),

    ("12", "Horizontal Precision", "수평 정밀도", "C",
     "New RRMs and MCPs are to be established by closed survey network or traverse from a minimum "
     "of two and preferably more existing registered RRMs and/or Landgate SSMs of suitable "
     "positional uncertainty (PU). A minimum of two RMs (if available) that agree to the published "
     "values within 10 mm are required. In metropolitan or townsite areas, ideally only SSMs of "
     "30 mm PU (GDA2020) or less are to be used; in rural areas, marks of 50 mm PU or less are "
     "preferable. The Survey Uncertainty (SU) for each adjusted control point should not exceed "
     "0.006 m at the 95% confidence level. GNSS static baselines are to be observed for a period "
     "no less than 50 minutes plus 2 minutes per km of baseline length. Rapid static baselines are "
     "not acceptable.",
     "새 도로기준표와 소기준점은 위치불확실도가 알맞은 기존 등록 도로기준표나 랜드게이트 "
     "표준측량표 두 점 이상(많을수록 좋다)에서 폐합망이나 폐합다각으로 설치한다. 참조표가 있으면 "
     "고시값과 10밀리미터 이내로 맞는 참조표 두 점 이상이 있어야 한다. 도시·읍 지역에서는 위치 "
     "불확실도 30밀리미터(GDA2020) 이하의 표준측량표만 쓰는 것이 바람직하고, 농촌 지역에서는 "
     "50밀리미터 이하가 바람직하다. 조정한 기준점의 측량불확실도(SU)는 95퍼센트 신뢰수준에서 "
     "0.006미터를 넘지 아니하여야 한다. GNSS 정지측량 기선은 50분에 기선 길이 1킬로미터마다 2분을 "
     "더한 시간 이상 관측한다. 신속정지측량 기선은 인정하지 아니한다."),

    ("12.1.1", "RTK Use for Observations Not Permitted", "RTK 관측 금지", "C",
     "Static GNSS baselines or total station measurements are required for new mark placement. The "
     "use of RTK techniques to coordinate new RRMs or MCPs is not an acceptable method for MRWA "
     "control surveys as the techniques do not meet the required SU. This is in line with the ICSM "
     "Guideline for Control Surveys by GNSS v2.2.",
     "새 측량표를 설치할 때에는 GNSS 정지측량 기선이나 토털스테이션 관측을 써야 한다. 새 "
     "도로기준표나 소기준점의 좌표를 정하는 데에 RTK 기법을 쓰는 것은 요구되는 측량불확실도를 "
     "충족하지 못하므로 인정하지 아니한다. 이는 ICSM 의 GNSS 기준점측량 지침 v2.2 와도 맞는다."),

    ("12.1.2", "Areas Remote from Existing CORS and/or Standard Survey Marks",
     "상시관측소·표준측량표에서 먼 지역", "C",
     "In some areas it will be necessary to bring coordinates and/or height in utilising the AUSPOS "
     "online processing service with a minimum of 4 hours of GNSS data. In these cases, newly "
     "placed RRMs must be linked by conventional levelling (and ideally a traverse) by adopting one "
     "of the AUSPOS derived AHD values. A least squares adjustment incorporating all data should be "
     "performed to reveal and report on any inconsistencies.",
     "일부 지역에서는 GNSS 자료를 4시간 이상 받아 AUSPOS 온라인 처리 서비스로 좌표와 높이를 "
     "끌어와야 한다. 이 경우 새로 설치한 도로기준표는 AUSPOS 로 얻은 AHD 높이 가운데 하나를 "
     "채택하여 직접수준측량(되도록 다각측량까지)으로 이어야 한다. 모든 자료를 넣은 최소제곱조정을 "
     "실시하여 어긋남이 있는지 드러내고 보고하여야 한다."),

    ("12.2.1", "Section Tolerances", "구간 허용범위", "C",
     "All new RRMs and MCPs shall be levelled with a two-way traverse. The level run must include a "
     "minimum of one validated Landgate benchmark or two existing RRMs validated from reference "
     "marks. The difference between the forward and backward levelling of any section or any "
     "combination of adjacent sections shall not exceed 0.012√K metres, where K is the distance in "
     "kilometres. The vertical accuracy for distances less than 1 km shall be on a pro-rata basis "
     "relative to the 1 km tolerance (0.012 m); for example, the tolerance for a 260 m section is "
     "±0.0031 m or better.",
     "새 도로기준표와 소기준점은 모두 왕복 수준측량으로 표고를 정한다. 수준노선에는 검증된 "
     "랜드게이트 수준점 1점 이상, 또는 참조표로 검증한 기존 도로기준표 2점 이상이 들어가야 한다. "
     "어느 구간이든, 또는 이웃한 구간을 합치든, 왕복 관측의 차는 0.012√K 미터를 넘지 아니하여야 "
     "한다(K 는 킬로미터 단위 거리). 1킬로미터 미만의 허용범위는 1킬로미터 허용범위(0.012미터)에 "
     "거리비례로 정한다. 예를 들어 260미터 구간의 허용범위는 ±0.0031미터 이하이다."),

    ("12.2.2", "Traverse Tolerance", "폐합 허용범위", "C",
     "The misclose of a traverse between validated datum benchmarks should not exceed 0.012√K "
     "metres, where K is the total distance in kilometres. When this tolerance is achieved, both "
     "AHD values of the marks are to be adopted and the level traverse adjusted to those datum "
     "values proportionally according to distance. Where there are large (over 20 m) height "
     "changes, the measured height difference should be corrected for staff calibration.",
     "검증된 기준 수준점 사이 다각의 폐합차는 0.012√K 미터를 넘지 아니하여야 한다(K 는 킬로미터 "
     "단위 총거리). 이 허용범위를 만족하면 두 측량표의 AHD 값을 모두 채택하고, 수준노선을 거리에 "
     "비례하여 그 기준값에 맞추어 조정한다. 높이차가 20미터를 넘는 큰 구간에서는 관측 고저차에 "
     "표척 검정 보정을 하여야 한다."),

    ("13", "Adjustment of Survey Control", "기준점망 조정", "D",
     "All horizontal networks or traverses must be adjusted using a least squares adjustment. When "
     "using software that incorporates transformations within the adjustment, this function must be "
     "disabled; adjustments submitted with transformation parameters may be rejected.",
     "모든 수평망과 다각은 최소제곱조정으로 조정하여야 한다. 조정 과정에 좌표변환이 들어가는 "
     "소프트웨어를 쓰는 경우에는 그 기능을 꺼야 하며, 변환 계수가 들어간 조정 결과는 반려될 수 "
     "있다."),

    ("15", "Data Lodgement", "성과 제출", "D",
     "Survey data, adjustment reports, mark summaries and metadata statements are to be lodged in "
     "the formats specified by Main Roads, including a statement of the datum, the adjustment "
     "method and the uncertainties achieved.",
     "측량자료, 조정 보고서, 측량표 요약, 메타데이터 진술서는 주도로청이 정한 형식으로 제출한다. "
     "여기에는 기준계, 조정 방법, 이룬 불확실도를 밝혀 적어야 한다."),
]

# ════════════════ 뉴질랜드 LINZ ════════════════
LINZ_CHAPS = [
    ("A", "Transition and Terminology", "전환과 용어"),
    ("B", "Fieldwork Implications", "현장작업에 미치는 영향"),
    ("C", "Accuracy Standards", "정확도 표준"),
]
LINZ = [
    ("1", "Coming into Force and Transition", "시행과 전환", "A",
     "The Cadastral Survey Rules 2021 came into effect on 30 August 2021. There was a transition "
     "period between 30 August 2021 and 25 February 2022: surveys already started under the Rules "
     "for Cadastral Survey 2010 could still be lodged until 25 February 2022. After that date "
     "Cadastral Survey Datasets (CSDs) can only be certified in terms of the 2021 Rules. During "
     "the transition period the Surveyor Declaration on the Title Plan shows which Rules the CSD "
     "has been prepared under.",
     "「지적측량규칙 2021」은 2021년 8월 30일에 시행되었다. 2021년 8월 30일부터 2022년 2월 25일까지 "
     "전환기간을 두어, 「지적측량규칙 2010」에 따라 이미 시작한 측량은 2022년 2월 25일까지 제출할 수 "
     "있었다. 그 뒤로는 지적측량자료(CSD)를 2021년 규칙에 따라서만 인증할 수 있다. 전환기간에는 "
     "등기도면의 측량사 선언에 그 자료가 어느 규칙에 따라 작성되었는지 나타냈다."),

    ("2", "New Terms", "바뀐 용어", "A",
     "The Rules use new terms: Title Diagram (replaces Diagram of Parcels), Survey Diagram "
     "(replaces Diagram of Survey), and Record of Survey (replaces CSD Plan). Easement memoranda "
     "and schedules now refer to benefited and burdened land.",
     "규칙은 새 용어를 쓴다 — 등기도(Title Diagram, 종전 '필지도'), 측량도(Survey Diagram, 종전 "
     "'측량성과도'), 측량기록(Record of Survey, 종전 'CSD 도면'). 지역권 각서와 명세서는 이제 "
     "'편익지'와 '승역지'라는 말을 쓴다."),

    ("3.1", "Field Information", "야장 정보", "B",
     "The Rules require field information to be recorded and provided in a prescribed way, with a "
     "stronger emphasis on the evidence used to define boundaries.",
     "규칙은 야장 정보를 정해진 방식으로 기록하여 제출하도록 요구하며, 경계를 정하는 데에 쓴 "
     "증거를 더 무겁게 다룬다."),

    ("3.2", "Occupation Diagram", "점유도", "B",
     "The Rules now specifically require occupation information to be provided in graphic form "
     "(r 81(2)). An occupation diagram must be saved as a supporting document with the type "
     "'Occupation Diagram' so that it becomes part of the Record of Survey. Occupation information "
     "is now required for all new boundary points (r 81(3)); where there is no occupation, a "
     "'No Occupation' annotation must be recorded against the boundary point and related lines "
     "(r 81(4)).",
     "규칙은 점유 상태를 그림으로 제출하도록 분명히 요구한다(제81조제2항). 점유도는 '점유도' 종류의 "
     "첨부문서로 저장하여 측량기록의 일부가 되게 하여야 한다. 이제 모든 새 경계점에 점유 정보가 "
     "필요하며(제81조제3항), 점유가 없으면 그 경계점과 관련 선에 '점유 없음'을 적어야 한다"
     "(제81조제4항)."),

    ("3.3", "Reference Marks (PRMs)", "영구기준표(PRM)", "B",
     "Witness marks are no longer referred to and have been replaced by a stronger requirement for "
     "three Permanent Reference Marks (PRMs) (r 32). Each boundary point that is required to be "
     "referenced must have a PRM within the specified distance — 150 m for Class A, 500 m for "
     "Class B and 1,000 m for Class C — and each of the three PRMs must be within the applicable "
     "distance of a boundary point that is required to be referenced. PRMs are expected to remain "
     "useable in the foreseeable future, but a 50-year term is no longer explicitly specified "
     "(r 33). At least two PRMs within the applicable distance must have reduced levels when "
     "referencing of a height-limited boundary point is required (r 34).",
     "종전의 '입회표'는 더 이상 쓰지 아니하고, 영구기준표(PRM) 세 점을 두도록 요건을 강화하였다"
     "(제32조). 기준표를 두어야 하는 경계점마다 정해진 거리 안에 영구기준표가 있어야 하며, 그 "
     "거리는 A등급 150미터, B등급 500미터, C등급 1,000미터이다. 또 세 영구기준표는 각각 기준표를 "
     "두어야 하는 경계점에서 그 거리 안에 있어야 한다. 영구기준표는 앞으로도 오래 쓸 수 있도록 "
     "설치하되, 종전의 '50년' 이라는 기한은 더 이상 명시하지 아니한다(제33조). 높이가 제한된 "
     "경계점에 기준표를 두어야 하는 경우에는 해당 거리 안의 영구기준표 두 점 이상에 표고가 있어야 "
     "한다(제34조)."),

    ("3.4", "Accuracy Standards", "정확도 표준", "C",
     "The standards are now specified as a single tier. Key changes: a new vertical accuracy "
     "standard applies between a vertical control mark and a height-limited boundary point; all "
     "vertical accuracy standards now apply to the slope distance between survey marks; all "
     "non-boundary accuracy standards are capped at 0.20 m rather than the previous 0.50 m; and a "
     "reduced horizontal tolerance applies between a Class A boundary point required to be "
     "referenced and all old and new non-boundary marks (r 21). "
     "Non-boundary marks — horizontal: 0.025 + (dist x 0.00005) m, max 0.20 m; vertical: "
     "0.030 + (dist x 0.0001) m, max 0.20 m. Connection to the control network — horizontal: "
     "0.025 + (dist x 0.00015) m, max 0.20 m; vertical (VCM to a new height-limited boundary "
     "point): 0.030 + (dist x 0.0001) m, max 0.20 m. Boundary referencing — horizontal accuracy "
     "between a Class A boundary point and all old and new non-boundary marks within 150 m must "
     "not exceed 0.03 m (previously 0.04 m). Horizontal accuracy standards are tested by Landonline "
     "internal consistency and network adjustments; vertical accuracy remains untested in "
     "Landonline.",
     "정확도 표준을 하나의 단계로 정하였다. 주요 변화는 다음과 같다 — 수직기준표와 높이제한 "
     "경계점 사이에 새로운 수직정확도 기준을 두었고, 모든 수직정확도 기준을 측량표 사이의 경사거리에 "
     "적용하며, 경계점이 아닌 표지의 정확도 상한을 종전 0.50미터에서 0.20미터로 낮추었고, 기준표를 "
     "두어야 하는 A등급 경계점과 신·구 비경계표지 사이에는 더 엄격한 수평 허용범위를 적용한다"
     "(제21조). "
     "비경계표지 — 수평: 0.025 + (거리 × 0.00005) 미터, 최대 0.20미터 / 수직: "
     "0.030 + (거리 × 0.0001) 미터, 최대 0.20미터. "
     "기준망과의 연결 — 수평: 0.025 + (거리 × 0.00015) 미터, 최대 0.20미터 / 수직(수직기준표와 새 "
     "높이제한 경계점 사이): 0.030 + (거리 × 0.0001) 미터, 최대 0.20미터. "
     "경계 기준표 — A등급 경계점과 150미터 안의 모든 신·구 비경계표지 사이의 수평정확도는 "
     "0.03미터를 넘지 아니한다(종전 0.04미터). "
     "수평정확도는 랜드온라인의 내부 일관성 검사와 망조정으로 검증하며, 수직정확도는 랜드온라인에서 "
     "검증하지 아니한다."),

    ("3.5", "Non-primary Parcels", "비주요 필지", "B",
     "Where the underlying parcel is not being created by the survey, the Rules provide greater "
     "flexibility when defining non-primary parcels. Under rule 51(1)(a), a Class B non-primary "
     "parcel may be defined in terms of the control network and PRMs, even where the underlying "
     "parcel meets the applicable accuracy standards. Where none of the underlying primary parcel "
     "boundaries meet the applicable accuracy standards, the non-primary parcel must be defined in "
     "terms of the control network and PRMs.",
     "그 측량으로 바탕 필지를 새로 만들지 아니하는 경우, 규칙은 비주요 필지를 정의하는 데에 더 "
     "넓은 재량을 준다. 제51조제1항가목에 따라, 바탕 필지가 해당 정확도 기준을 충족하더라도 B등급 "
     "비주요 필지를 기준망과 영구기준표로 정의할 수 있다. 바탕 주요 필지의 경계가 어느 것도 해당 "
     "정확도 기준을 충족하지 못하는 경우에는 비주요 필지를 반드시 기준망과 영구기준표로 정의하여야 "
     "한다."),

    ("4", "Non-primary Parcels Crossing Primary Parcels", "주요 필지를 가로지르는 비주요 필지", "A",
     "Non-primary parcels (such as a parcel depicting easement, covenant or lease areas) are now "
     "able to cross primary parcels (e.g. fee simple parcels) that are held in the same record of "
     "title. The schedule of easements will show each primary parcel as the burdened land. A title "
     "plan must also include details of the easements to be surrendered and land covenants to be "
     "revoked. Where a parcel is restricted in height (a strata parcel), the appellation includes "
     "the prefix 'height-limited'.",
     "지역권·약정·임차 구역을 나타내는 비주요 필지가, 같은 등기기록에 속한 주요 필지(예: 소유권 "
     "필지)를 가로지를 수 있게 되었다. 지역권 명세서에는 각 주요 필지를 승역지로 적는다. 또 "
     "등기도면에는 포기할 지역권과 취소할 토지약정의 내용을 함께 적어야 한다. 높이가 제한된 "
     "필지(구분 필지)의 지번 표기에는 '높이제한'이라는 머리말을 붙인다."),
]


def main():
    n1 = build("loc16",
               "WA Main Roads — Geodetic Control Survey Standard",
               "호주 서부 주도로청 측지기준점측량 표준",
               WA_CHAPS, WA,
               "국외관련규정\\호주_ICSM_SP1\\WA-MainRoads_Geodetic-Control-Survey-Standard.pdf")
    n2 = build("loc15",
               "LINZ — Transitioning from RCS 2010 to CSR 2021",
               "뉴질랜드 LINZ 지적측량규칙 2021 전환 안내",
               LINZ_CHAPS, LINZ,
               "국외관련규정\\뉴질랜드_LINZ\\LINZ_Transitioning_from_RCS2010_to_CSR2021_v4.0.pdf")
    print(f"WA — 조 {n1} · LINZ — 조 {n2} · 모두 한국어 대역을 붙였습니다.")


if __name__ == "__main__":
    main()
