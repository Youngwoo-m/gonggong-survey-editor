# -*- coding: utf-8 -*-
"""
2025년 전략수립 연구보고서를 근거로 「공공측량 작업규정」 개편안 초안을 만든다.

근거 문서
  2025년.전략수립용역\\04.연구보고서_공공측량.작업규정.개정.최종보고서.5.31.hwp
    · [표 4-3] 현행 체계와 신체계 편별 구성 비교(안)  → 편 재편
    · 제4장 2.2 편(篇) 구성의 재편 방향             → 장 배치
    · 제4장 3. 최신 측량 기술 적용 신설 방안         → 신설 장·절
    · 부록 4. 조문별 문제점 상세 분석표 (A~F 44건)  → 조문별 변경 사유

하는 일
  현행 217조를 신체계 편·장으로 옮기고, 보고서가 짚은 조문에 변경 사유를 단다.
  보고서에 조문안(條文案)까지는 없으므로 신설 조문은 '제목과 사유'만 둔 자리표시다.

사용:  python scripts/gendraft2025.py
출력:  data/draft2025.json   (앱이 'v1. 개편안 초안(2025)' 버전으로 읽는다)
"""
import io, json, os, re, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hwp5

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REPORT = os.path.join(os.path.dirname(os.path.dirname(ROOT)),
                      "2025년.전략수립용역",
                      "04.연구보고서_공공측량.작업규정.개정.최종보고서.5.31.hwp")

SRC = "2025년 전략수립 연구보고서"
REVIEW_FILE = os.path.join(os.path.dirname(os.path.dirname(ROOT)),
                           "99.참고자료", "품관원의견.2026.07.27",
                           "품관원.이한.작업규정 변경(안)-2026.07.27_검토의견.hwpx")

# 검토의견이 가리키는 '제4장' = 현행 제2편 제4장 GNSS높이측량 (신체계에서는 GNSS 수준측량)
REVIEW_CHAPTER = "GNSS 수준측량"


# ───────────────────────── 부록 4 읽기 ─────────────────────────
def read_apx4(path):
    """[{code, articles:[조번호], fix:개선방향, issue:문제점}, …]"""
    rows, ROW = [], re.compile(r"^([A-F])-(\d+)\s*\|")
    for line in hwp5.text_lines(path):
        m = ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in line.split("|")][1:]
        if not cells:
            continue
        rows.append({
            "code": f"{m.group(1)}-{m.group(2)}",
            "type": m.group(1),
            # 조문 번호는 칸의 자리가 표마다 달라, 개선 방향 칸을 뺀 모든 칸에서 찾는다.
            # 앞 세 칸만 보면 '제89조 vs. 제190조' 처럼 문제점 칸에 적힌 용어 지적이
            # 어느 조문에도 붙지 못한다.
            "articles": sorted({int(x) for x in
                                re.findall(r"제\s*(\d+)\s*조", " ".join(cells[:-1]))}),
            "issue": cells[-3] if len(cells) >= 3 else cells[0],
            "fix": cells[-1],
        })
    return rows


TYPE_NAME = {
    "A": "법령 불일치", "B": "기술 진부화", "C": "용어 오류·불일치",
    "D": "서술 방식 불일치", "E": "중복·누락·불명확", "F": "신기술 규정 공백",
}


def cut(s, n=170):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def apx4_basis(r, no):
    """부록 4 지적의 '문제점' 을 근거 줄로 — 보고서 어디라고는 적지 아니한다"""
    others = [x for x in r.get("articles") or [] if x != no]
    what = TYPE_NAME[r["type"]]
    if others:                    # 여러 조문에 걸친 지적은 문제점 서술이 다른 조문까지 다룬다
        li = "·".join(f"제{x}조" for x in others)
        return f"연구 검토 결과 {what} — 이 조와 {li}에 함께 걸린 지적"
    return f"연구 검토 결과 {what} — {cut(r['issue'], 150)}"


def apx4_cause(r, no):
    """부록 4 지적의 개정 사유 — 규정 문체로 다시 쓴 글을 쓴다

    보고서의 '개선 방향' 칸은 연구 메모여서 사유로 그대로 실으면 읽히지 아니한다.
    44건을 규정 문체로 옮겨 둔 것이 draft2025_apx4why.WHY 다.
    """
    return APXWHY.why(r["code"], cut(r["fix"], 200))


def apx4_sentence(r, no):
    """부록4 지적을 그 조문의 사유 한 줄로 — 다른 조문 이야기는 끌고 오지 않는다"""
    others = [x for x in r.get("articles") or [] if x != no]
    # '부록4 X-N' 꼴로 적으면 뒤에서 코드가 다시 풀려 버리므로 띄어 쓴다
    bits = [f"[부록 4 {r['code']} {TYPE_NAME[r['type']]}]"]
    # 여러 조문에 걸친 지적은 문제점 서술이 다른 조문까지 다루므로 개선 방향만 적는다
    if not others:
        bits.append(f"문제점: {cut(r['issue'], 150)}")
    bits.append(f"개선 방향: {cut(r['fix'], 200)}")
    if others:
        li = "·".join(f"제{x}조" for x in others)
        bits.append(f"이 조와 {li}에 함께 걸린 지적입니다")
    return " / ".join(bits)


# ───────────────────────── 신체계 설계 ─────────────────────────
# (편 제목, [ (장 제목, 현행 조 범위 또는 None, 장 사유) … ], 편 사유)
#   조 범위 (a, b) = 현행 제a조~제b조를 그대로 옮긴다
PLAN = [
    ("총칙", "현행 총칙을 강화한다. 목적·적용범위·정의·측량기준에 더해 작업 종류, 제품사양서, "
             "품질요소, 전자성과 원칙, 기술중립성을 총칙에 올린다. [표 4-3]", [
        ("통칙", [(1, 7), (9, 15)], None),
        ("성과와 품질", None,
         "성과 중심 체계로 전환하기 위해 신설한다. 품질요소·제품사양서·성과패키지·전자성과·"
         "성과심사 기준을 총칙에 두고 각 편이 준용하도록 한다. [표 4-3], 부록4 D-3·E-3·E-5·E-7"),
        ("측량기기", [(8, 8), (96, 96)],
         "현행 제8조(측량기기 사용) 하나로는 성능검사·동등성 인정·현장 점검을 담기 어려워 "
         "장으로 세운다. 용어는 상위법(법 제92조, 시행령 제97조, 시행규칙 제101조)이 쓰는 "
         "'측량기기' 로 통일한다. 자리를 총칙에 두는 것은 모든 편에 공통으로 걸리는 사항이고, "
         "「무인비행장치 측량 작업규정」 제6조·「수치지형도 작성 작업 및 성과에 관한 규정」 "
         "제5조·「정밀도로지도의 구축 및 갱신 등에 관한 규정」 제7조·「일반측량 작업규정」 "
         "제7조가 모두 총칙에 두고 있기 때문이다. 편별 특유 기기 요건(현행 제96조 응용측량기기, "
         "지상라이다 성능검정, UAV 시스템 등)은 각 편에 남긴다. 응용측량 편에 홀로 있던 "
         "현행 제96조(응용측량기기)도 이 장으로 옮겨 기기에 관한 표를 한곳에 모은다. "
         "부록4 A-4"),
    ]),

    ("기준점측량", "현행 제2편의 골격을 유지하되 GNSS 수준측량을 독립 장으로 두고, "
                  "제4편에 흩어져 있던 네트워크 RTK 측량을 이 편으로 통합한다. 제4장 2.2", [
        ("개설", (16, 17), None),
        ("공공삼각점측량", (18, 31), None),
        ("공공수준점측량", (32, 43), None),
        ("GNSS 수준측량", (44, 59),
         "GNSS 높이측량을 독립 장으로 세우고 명칭을 'GNSS 수준측량'으로 정비한다. 제4장 2.2"),
        ("네트워크 RTK 측량", (192, 211),
         "기준점측량 기법이므로 응용측량 편에서 기준점측량 편으로 옮긴다. 제4장 2.2"),
    ]),

    ("지형측량", "현행 골격을 유지하되 '별도 규정을 따른다'는 위임 조항을 본문으로 끌어올리고, "
                "점군 기반 측량은 제4편으로 옮긴다. 제4장 2.2", [
        ("개설", (60, 63), None),
        ("지상현황측량", (64, 74),
         "고정형 지상라이다 측량은 지상현황측량에 포함되므로, "
         "「지상라이다 측량 작업 및 성과에 관한 지침」(제정안)의 조문을 이 장에 들여온다. "
         "지침이 정한 것이 먼저 적용되고, 지침에 없는 것만 이 규정으로 메운다. 제4장 3"),
        ("항공사진측량", (75, 75),
         "위임 조항에 머물러 있던 항공사진측량의 작업 기준을 본문에 수록한다. 제4장 2.2"),
        ("영상지도제작", (77, 77), None),
        ("일반지도 수치화", (79, 82), None),
        ("지도의 축소편집", (83, 93), None),
    ]),

    ("3차원 공간정보 구축", "전부개정의 가장 큰 변화로 신설하는 편이다. 현행 제3편 제4장(무인비행장치 측량)과 "
                          "제5편에 흩어진 3차원 관련 조문을 모으고, 점군 기반 분야를 장으로 세운다. "
                          "다만 고정형 지상라이다 측량은 지상현황측량에 들어가므로 제3편에 둔다. "
                          "[표 4-3], 제4장 3", [
        ("통칙", None,
         "점군 성과의 공통 사항(성능 입증 중심 수용, 좌표계·정확도·점밀도·분류 코드, "
         "성과패키지)을 먼저 규정한다. 제4장 3, 부록4 F-1"),
        ("무인비행장치 사진점군측량", (76, 76),
         "「무인비행장치측량 작업규정」으로 전부 위임하던 것을 본문으로 끌어올리고 "
         "비행계획·GCP·중복도·GSD 기준을 규정한다. 제4장 3, 부록4 F-2"),
        ("무인비행장치 레이저측량", None,
         "「무인비행장치 측량 작업규정」과 「항공레이저측량 작업규정」이 이미 규율하는 "
         "분야이므로 작업방법을 새로 적지 아니하고 그 규정을 가리키는 조문 하나만 둔다. "
         "제4장 3, 부록4 F-1"),
        ("차량기반 이동측량 및 정밀도로지도", (215, 215),
         "MMS 측량 조문이 없고 정밀도로지도는 별도 고시 위임만 있어, 장으로 올리고 "
         "검정·주행 취득·위성항법 음영구간·정합 검증을 규정한다. 차로 중심선의 정확도와 "
         "객체의 속성체계는 「정밀도로지도의 구축 및 갱신 등에 관한 규정」 제23조·제24조와 "
         "정밀도로지도 데이터 모델 기관표준이 이미 정하고 있으므로 여기에 옮겨 적지 "
         "아니한다. 제4장 3, 부록4 F-3"),
        ("항공레이저측량", (78, 78),
         "수치표고모델 제작 조문을 항공 LiDAR 장으로 확장하고 QL 등급·점밀도·분류 기준을 둔다. "
         "제4장 3, 부록4 F-1"),
        ("3차원 공간정보 성과", (213, 214),
         "3차원국토공간정보·실내공간정보 구축을 이 편으로 옮겨 3D 성과 기준을 한곳에 모은다. "
         "[표 4-3], 부록4 F-4"),
        ("지하공간통합지도", (216, 216),
         "지하공간통합지도 제작을 3차원 공간정보 편으로 옮긴다. 부록4 F-4"),
    ]),

    ("응용측량", "현행 제4편과 제5편에 걸쳐 흩어진 응용측량 분야를 하나로 묶고, "
                "지하시설물측량은 안전관리·도통테스트·GPR 탐사를 더해 크게 보강한다. [표 4-3], 제4장 3", [
        ("개설", [(94, 95), (97, 98)],
         "기기에 관한 조문(현행 제96조 응용측량기기)은 제1편 총칙 측량기기 장으로 옮긴다."),
        ("노선측량", (99, 109), None),
        ("하천 및 연안측량", (110, 119), None),
        ("용지측량", (120, 130), None),
        ("토지구획정리측량", (131, 167), None),
        ("지하시설물측량", [(168, 168), (179, 191)],
         "매설 상황별(기존 매설·신설·변경) 측량 방법을 구분하고, 도통테스트·GPR 탐사를 "
         "절로 신설한다. 밀폐공간 작업 등 안전에 관한 조문(현행 제169조부터 제178조까지)은 "
         "제6편 안전관리로 옮긴다. 제4장 3, 부록4 E-9·F-5"),
        ("수치주제도 제작", (212, 212), None),
    ]),

    ("안전관리", "측량 작업의 안전관리를 흩어 놓지 않고 별도의 편으로 세운다. "
                "현장작업 환경 구분과 위험특성은 현장작업 환경별 위험특성 분석 결과를, 밀폐공간 등 개별 기준은 「산업안전보건기준에 관한 규칙」을 "
                "근거로 삼았다. 부록4 E-8", [
        ("통칙", None,
         "안전관리의 목적·적용·계획·위험성평가·작업중지·안전관리비를 먼저 정한다. 부록4 E-8"),
        ("작업환경별 안전기준", [(169, 178)],
         "도심·도로·산악·수변·건설시설·지하밀폐·무인비행장치의 일곱 가지 환경으로 나누어 "
         "환경별 안전기준을 둔다. 지하시설물측량 장에 흩어져 있던 밀폐공간 작업 안전 조문"
         "(현행 제169조부터 제178조까지)을 이 장으로 옮겨 안전관리 조문과 한데 모은다. "
         "부록4 E-8"),
        ("안전교육 및 훈련", None,
         "현장작업 환경별로 갖추어야 할 역량을 정하고 교육·훈련을 실시하게 한다. "
         "안전훈련의 평가지표는 연구가 진행 중이므로 이번 초안에서는 담지 아니하고, "
         "평가지표 개발이 끝난 뒤에 반영한다."),
    ]),
]

# 현행에 장 구분이 없어 자동으로는 잡히지 않는 이동 — 장을 갈라 옮긴 조문
FORCE_MOVE = {8}

# 옮기면서 제목만 다듬은 조문 (조번호 → 새 제목, 사유)
TITLE_FIX = {
    # 제2조의 제목은 현행 그대로 「정의」 로 둔다 — 편마다 같은 이름의 정의 조문을
    # 두게 되었으므로, 제목을 길게 하지 아니하고 편 이름으로 가린다
    196: ("네트워크 RTK 측량의 작업구분 및 순서",
          "같은 편에 「작업구분 및 순서」 가 둘이어서 가려낼 수 없다. 무엇의 순서인지 "
          "제목에 밝힌다. 부록 4 C 유형(용어 오류·불일치)"),
    199: ("네트워크 RTK 측량의 선점",
          "같은 편에 「선점」 이 둘이어서 가려낼 수 없다. 무엇의 선점인지 제목에 밝힌다. "
          "부록 4 C 유형(용어 오류·불일치)"),
    158: ("가구확정측량의 점검측량",
          "같은 장에 「점검측량」 이 둘이어서 가려낼 수 없었다. 무엇을 점검하는지 제목에 "
          "밝힌다. 부록 4 C 유형(용어 오류·불일치)"),
    165: ("획지확정측량의 점검측량",
          "같은 장에 「점검측량」 이 둘이어서 가려낼 수 없었다. 무엇을 점검하는지 제목에 "
          "밝힌다. 부록 4 C 유형(용어 오류·불일치)"),
    96: ("응용측량에 사용하는 측량기기",
         "총칙 측량기기 장으로 옮기면서 제목에 적용 범위를 밝힌다. 조문 본문과 기기 표는 "
         "그대로 두었다."),
}

# 옮겨 온 조문을 신설 조문 뒤에 붙이는 장
# 본문에 딸린 표의 부호를 바로잡은 조문 — 표 자체는 scripts/genobjects.py 가 고친다
#   {현행 조번호: 사유}
SIGN_WHY = ("허용오차와 확률오차는 '기준값 ± 비례항' 이 옳은데 원문 표에는 "
            "'20mm + 4ppm · D' · '10cm + 2cm√N' 처럼 ＋ 로 적혀 있어 한쪽으로만 "
            "벌어지는 것처럼 읽힌다. 같은 규정 안에서도 '±(5mm + 1PPM×D)' 처럼 "
            "부호를 붙여 적은 표가 있어 표기가 엇갈린다. 비례항 앞의 부호를 ± 로 "
            "바로잡는다. 부호 수정")
OBJ_FIX = {no: SIGN_WHY for no in (27, 28, 96)}

TAIL = {("안전관리", "작업환경별 안전기준"),
        # 이동측량 일반의 신설 조문이 먼저 오고, 별도 규정으로 미루는
        # 정밀도로지도 제작 조문이 그 뒤에 온다
        ("3차원 공간정보 구축", "차량기반 이동측량 및 정밀도로지도")}

# 신설 조문을 장의 끝이 아니라 짝이 되는 조문 바로 뒤에 앉힌다
#   {(편, 장): {옮길 조문 제목: 그 앞에 올 조문 제목}}
PLACE_AFTER = {
    ("지형측량", "지상현황측량"): {
        # 세부측량 방식끼리 나란히 두어야 견주기 쉽다 (TS → RTK-GNSS → 지상레이저)
        "지상레이저측량에 의한 세부측량": "RTK-GNSS에 의한 세부측량",
    },
}

# 통합해 없앤 조문 (조번호 → 그 내용을 받은 조문의 제목)
# 제목으로 적어 두고, 사유를 지을 때 개편안에서 그 조문을 찾아 번호까지 적는다.
MERGED = {}
MERGED.update({n: "성과패키지" for n in [31, 43, 59, 74, 93, 109, 119, 130, 167, 191]})
MERGED.update({n: "정확도 관리" for n in [30, 42, 73, 92, 129]})
# 공공삼각점·공공수준점에 같은 말로 나뉘어 있던 네 쌍 → 기준점측량 개설 장의 공통조문
MERGED.update({n: "공공기준점측량의 공정별 작업구분 및 순서" for n in [20, 34]})
MERGED.update({n: "공공기준점측량의 작업수행계획" for n in [21, 35]})
MERGED.update({n: "공공기준점측량의 선점" for n in [22, 36]})
MERGED.update({n: "공공기준점 표지의 설치" for n in [23, 37]})

# 한 조문이 받은 현행 조문들 — '무엇을 무엇으로 합쳤는가' 를 적을 때 쓴다
MERGED_PEERS = {}
for _n, _t in MERGED.items():
    MERGED_PEERS.setdefault(_t, []).append(_n)
for _t in MERGED_PEERS:
    MERGED_PEERS[_t].sort()

from draft2025_articles import NEW_ARTICLES     # 신설 조문안 (조 제목, 사유, 조문안)
import draft2025_review as REVIEW               # 품관원 검토의견
import draft2025_amend as AMEND                 # 검토의견을 조문 본문에 반영
import draft2025_tables as TABLES               # 보고서 표 → XML
import draft2025_srcs as SRCS                   # 위치 표시 → 원문 문장
import draft2025_reason as RSN
import draft2025_annexfix as ANXFIX                  # 개조식 변경 사유 (현행/근거/사유)
import draft2025_split as SPLIT                      # 주제가 뒤섞인 긴 조문 나누기
import draft2025_layout as LAYOUT                    # 호·목을 줄로 가르기
import draft2025_detail as DETAIL                    # 조문별 '개정 내용' 짓기
import draft2025_problem as PROB                     # 조문별 '현행의 문제' 짓기
import draft2025_apx4why as APXWHY                   # 부록4 44건 사유를 규정 문체로
import draft2025_defs as DEFS                   # 흩어진 용어 정의 → 총칙 제2조

RE_HO_MARK = re.compile(r"제\s*2\s*조\s*제\s*⟪([^⟫]{2,20})⟫\s*호")


def _resolve_ho(tree, a2):
    """제2조제⟪실시간 간섭측위⟫호 → 제2조제20호

    정의 조문의 호 번호는 어느 정의를 거두어 오느냐에 따라 움직인다. 그래서
    개정 문안에 번호를 박아 두면 어긋난다 — 실제로 「제2조제6호에 따른 실시간
    간섭측위」라 적혀 있었는데 제6호는 「공공기준점측량」이었다. 문안에는 용어
    이름을 적어 두고, 제2조가 다 세워진 뒤 여기에서 번호로 바꾼다.
    """
    no_of = {}
    for line in (a2.get("body") or "").splitlines():
        m = re.match(r"\s*(\d{1,2})\.\s*[\"“]([^\"”]{2,30})[\"”]", line)
        if m:
            no_of[m.group(2)] = int(m.group(1))

    def walk(ns):
        for n in ns:
            b = n.get("body") or ""
            if "⟪" in b:
                def sub(m):
                    k = no_of.get(m.group(1))
                    if k is None:
                        raise SystemExit(
                            f"제2조에 「{m.group(1)}」 정의가 없습니다 — "
                            f"draft2025_amend.py 의 용어 표시를 고치십시오")
                    return f"제2조제{k}호"
                n["body"] = RE_HO_MARK.sub(sub, b)
            walk(n.get("children") or [])
    walk(tree)
import draft2025_alias as ALIAS                 # 문장 속 약칭 → 총칙 제2조


# ───────────────────────── 만들기 ─────────────────────────
def collect(tree):
    """조번호 → 노드 (별표 제외)"""
    out = {}
    def rec(ns):
        for n in ns:
            if n.get("annexRef") or n.get("isAnnex"):
                continue
            if n["level"] == "조":
                out[n["no"]] = n
            rec(n.get("children") or [])
    rec(tree)
    return out


def where_of(reg_tree):
    """조번호 → ('제N편 제M장' 현행 위치, 그 장의 id)"""
    out = {}
    for p in reg_tree:
        if p.get("isAnnex"):
            continue
        for c in p.get("children") or []:
            if c["level"] == "조":
                out[c["no"]] = (f"제{p['no']}편", None)
                continue
            where = (f"제{p['no']}편 제{c['no']}장", c["id"])
            for g in [c] + list(c.get("children") or []):
                if g["level"] == "조":
                    out[g["no"]] = where
                for h in g.get("children") or []:
                    if h["level"] == "조":
                        out[h["no"]] = where
    return out


# 신체계 편 → 현행 편 (같은 줄기로 보아 마디 id 를 물려준다 → 비교표가 '이동/수정'으로 잡힌다)
PART_OF = {1: 1, 2: 2, 3: 3, 4: None, 5: 4, 6: None, 7: 5}
CH_ALIAS = {"GNSS 수준측량": "GNSS높이측량"}


def base_ids(reg_tree):
    """(편번호, 장제목) → id, 그리고 장제목 → id"""
    by_pair, by_title, part = {}, {}, {}
    for p in reg_tree:
        if p.get("isAnnex"):
            continue
        part[p["no"]] = p["id"]
        for c in p.get("children") or []:
            if c["level"] != "장":
                continue
            by_pair[(p["no"], c["title"].strip())] = c["id"]
            by_title.setdefault(c["title"].strip(), c["id"])
    return part, by_pair, by_title


def reason_of(n):
    """마디에 달아 둔 사유 얼개 — 없으면 새로 만든다"""
    if not isinstance(n.get("_R"), RSN.Reason):
        n["_R"] = RSN.Reason()
    return n["_R"]


def render_reasons(ns):
    """얼개를 글로 바꾼다 — 저장하기 바로 앞에서 한 번 부른다"""
    n = 0
    for x in ns:
        x.pop("_defnote", None)
        R = x.pop("_R", None)
        if isinstance(R, RSN.Reason) and R:
            x["reason"] = R.render()
            n += 1
        n += render_reasons(x.get("children") or [])
    return n


def stable_id(text):
    """글에서 늘 같은 번호를 얻는다.

    파이썬의 hash() 는 실행할 때마다 값이 달라져서(해시 뿌림), 그것으로 id 를
    지으면 다시 만들 때마다 노드 id 가 바뀐다. 그러면 저장해 둔 편집·이력·
    판 비교가 그 노드를 잃는다. crc32 는 늘 같은 값을 준다.
    """
    return zlib.crc32(str(text or "").encode("utf-8")) % 10 ** 6


def node(level, no, title, status, reason, **kw):
    d = {"id": kw.pop("id", f"d{level}{no}-{stable_id(title)}"),
         "level": level, "no": no, "branch": 0, "title": title, "body": kw.pop("body", ""),
         "status": status, "legacyNo": kw.pop("legacyNo", ""), "reason": reason,
         "sourceRef": None, "history": [], "children": [], "collapsed": level != "편"}
    d.update(kw)
    return d


if __name__ == "__main__":
    reg = json.load(io.open(os.path.join(DATA, "reg01.json"), encoding="utf-8"))
    by_no = collect(reg["tree"])
    where = where_of(reg["tree"])

    # 현행 조문이 어느 편·장에 있었는지 — 이동 사유를 갈래별로 짓는 데 쓴다
    cur_part, cur_chap = {}, {}
    for _p in reg["tree"]:
        if _p.get("isAnnex"):
            continue
        for _c in _p.get("children") or []:
            if _c.get("level") == "조":
                cur_part[_c["no"]] = _p.get("title") or ""
                cur_chap[_c["no"]] = ""
                continue
            for _g in [_c] + list(_c.get("children") or []):
                if _g.get("level") == "조":
                    cur_part[_g["no"]] = _p.get("title") or ""
                    cur_chap[_g["no"]] = _c.get("title") or ""

    print(f"근거 보고서 읽는 중 — {os.path.basename(REPORT)}")
    apx4 = read_apx4(REPORT)
    print(f"  부록 4 조문별 문제점 {len(apx4)}건")

    review, rv_by_jo, rv_chapter = [], {}, []
    if os.path.exists(REVIEW_FILE):
        review = REVIEW.read(REVIEW_FILE)
        print(f"품관원 검토의견 읽는 중 — {os.path.basename(REVIEW_FILE)}")
        print(f"  검토의견 {len(review)}건")
        for r in review:
            for a in r["articles"]:
                rv_by_jo.setdefault(a, []).append(r)
            if r["chapters"] and not r["articles"]:
                rv_chapter.append(r)
            elif r["chapters"]:
                rv_chapter.append(r)
    else:
        print(f"  [건너뜀] 검토의견 파일이 없습니다: {REVIEW_FILE}")

    # 조번호 → 사유 목록
    fixes = {}
    for r in apx4:
        for a in r["articles"]:
            fixes.setdefault(a, []).append(r)

    # 보고서 위치 표시를 문장으로 풀 때 쓰는 자료 — 앞에서 마련해 둔다
    code_fix = {r["code"]: APXWHY.why(r["code"], cut(r["fix"], 200)) for r in apx4}
    code_type = {r["code"]: r["type"] for r in apx4}
    code_basis = {r["code"]: f"연구 검토 결과 {TYPE_NAME[r['type']]} — {cut(r['issue'], 150)}"
                  for r in apx4}

    part_id, pair_id, title_id = base_ids(reg["tree"])
    tree, used, moved, edited, created, amended = [], set(), 0, 0, 0, 0
    merged = 0
    objfixed = 0
    taken = set()

    for pi, (ptitle, preason, chapters) in enumerate(PLAN, start=1):
        bp = PART_OF.get(pi)
        pnode = node("편", pi, ptitle, "수정" if bp else "신설", "",
                     id=part_id.get(bp) or f"dp{pi}")
        bs, ws = RSN.split(preason, code_fix, code_basis)
        reason_of(pnode).now(f"현행 제{bp}편" if bp else "").basis(*bs).cause(*ws)
        if pi == 1:
            pnode["body"] = (
                "이 개편안은 2025년 전략수립 연구보고서를 근거로 만든 초안이다. "
                "편별 구성과 연구 검토 결과의 유형별 빈도는 아래 첫째·둘째 표와 같으며, "
                "두 표는 개편안을 고칠 때마다 이 초안에서 다시 세어 만든다. "
                "셋째 표의 개정 우선순위는 연구보고서가 매긴 것을 그대로 옮긴 것이다."
                "<img id=\"t4301\"></img><img id=\"t4302\"></img><img id=\"t4303\"></img>")
        for ci, (ctitle, rng, creason) in enumerate(chapters, start=1):
            key = CH_ALIAS.get(ctitle, ctitle)
            cid = pair_id.get((bp, key)) or title_id.get(key)
            if cid in taken:
                cid = None
            if cid:
                taken.add(cid)
            cnode = node("장", ci, ctitle, "유지", "",
                         id=cid or f"dc{pi}-{ci}")
            bs, ws = RSN.split(creason or "", code_fix, code_basis)
            reason_of(cnode).now("현행 같은 장" if cid else "").basis(*bs).cause(*ws)
            if ctitle == REVIEW_CHAPTER and rv_chapter:
                R = reason_of(cnode)
                for r in rv_chapter:
                    R.basis(REVIEW.basis(r)).cause(REVIEW.cause(r))
                cnode["status"] = "수정"
            n_moved_here = 0
            if rng:
                # 조 범위는 (a, b) 하나 또는 [(a, b), …] 여럿을 받는다
                spans = rng if isinstance(rng, list) else [rng]
                nos = [no for a, b in spans for no in range(a, b + 1)]
                for no in nos:
                    src = by_no.get(no)
                    if not src:
                        continue
                    if no in MERGED:
                        # 총칙의 해당 조문으로 통합했다
                        used.add(no)
                        merged += 1
                        continue
                    used.add(no)
                    n = json.loads(json.dumps(src))
                    n["children"] = []
                    n["history"] = []
                    n["legacyNo"] = n.get("legacyNo") or f"제{no}조"

                    R = reason_of(n)
                    was_title = n.get("title") or ""     # 제목을 고치기 전의 현행 제목
                    if no in TITLE_FIX:
                        new_t, fix_why = TITLE_FIX[no]
                        n["title"] = new_t
                        bs, ws = RSN.split(fix_why, code_fix, code_basis)
                        R.basis(*bs).cause(*ws)
                    for r in fixes.get(no, []):
                        # 문제점은 '현행의 문제' 로 올린다 — 공청회에서 먼저 읽힐 자리다
                        R.problem(apx4_basis(r, no), PROB.harm_line(r.get("type")))
                        R.cause(apx4_cause(r, no))
                        # 용어를 바로잡은 것은 따로 골라 볼 수 있게 표시해 둔다.
                        # 공청회에서 다툴 것과 다투지 아니할 것을 가르는 데 쓴다
                        if r.get("type") == "C":
                            n["changeKind"] = "용어"
                    for r in rv_by_jo.get(no, []):
                        R.problem(REVIEW.basis(r)).cause(REVIEW.cause(r))
                    # 본문에 딸린 표의 부호를 바로잡은 조문 (scripts/genobjects.py)
                    if no in OBJ_FIX:
                        bs, ws = RSN.split(OBJ_FIX[no], code_fix, code_basis)
                        R.basis(*bs).cause(*ws)
                        objfixed += 1
                    # 검토의견을 조문 본문에도 반영한다
                    n["body"], hit = AMEND.apply(no, n.get("body") or "")
                    if hit:
                        amended += hit
                        if AMEND.NOTE.get(no):
                            bs, ws = RSN.split(AMEND.NOTE[no], code_fix, code_basis)
                            R.basis(*bs).cause(*ws)
                        elif not rv_by_jo.get(no):
                            R.cause(f"검토의견을 본문 {hit}곳에 반영하여 문언을 고친다")
                    old, old_cid = where.get(no, ("", None))
                    newp = f"제{pi}편 {ptitle} 「{ctitle}」 장"
                    # 편이나 장이 바뀌었으면 옮긴 것으로 본다
                    # (장 이름만 고친 경우는 장 id 가 같아 옮긴 것으로 보지 아니한다)
                    old_p = old.split(" ")[0] if old else ""
                    was_moved = (old_p != f"제{pi}편" or old_cid != (cid or None)
                                 or no in FORCE_MOVE)
                    cur = f"{n['legacyNo']}({was_title})"
                    R.now(f"{cur} — {old}" if old else cur)
                    if was_moved:
                        # 어디에서 어디로 옮겼는지는 '개정 내용' 이 적는다.
                        # 여기에는 왜 옮기는지만 남겨 같은 말이 겹치지 아니하게 한다
                        R.cause(DETAIL.why_moved(
                            cur_part.get(no, ""), ptitle,
                            cur_chap.get(no, ""), ctitle, old, newp))

                    # 본문이 실제로 바뀐 때만 '수정' 이다.
                    # 부록4·검토의견의 지적은 사유로만 남기고 표시는 바꾸지 않는다.
                    # 본문에 딸린 표를 고친 것도 내용이 바뀐 것이므로 '수정' 으로 본다.
                    was_edited = hit > 0 or no in OBJ_FIX
                    # 본문이 바뀐 조문에는 현행 본문을 남겨 둔다 —
                    # 화면에서 달라진 말을 짚어 보이는 데 쓴다 (detail.js _bodyDiff)
                    if (n.get("body") or "") != (src.get("body") or ""):
                        n["wasBody"] = src.get("body") or ""
                    if was_edited and was_moved:
                        n["status"] = "이동·수정"
                        moved += 1; edited += 1
                    elif was_edited:
                        n["status"] = "수정"; edited += 1
                    elif was_moved:
                        n["status"] = "이동"; moved += 1
                    else:
                        n["status"] = "유지"
                        if not R.why:
                            R.cause("편제와 문언을 그대로 둔다")
                    cnode["children"].append(n)
                    n_moved_here += 1
            else:
                cnode["status"] = "신설"

            for j, (t, why, text) in enumerate(NEW_ARTICLES.get((ptitle, ctitle), []), start=1):
                nn = node("조", j, t, "신설", "", id=f"n{pi}-{ci}-{j}", body=text)
                bs, ws = RSN.split(why, code_fix, code_basis)
                # 연구 검토가 짚은 문제점은 근거가 아니라 '현행의 문제' 다
                R0 = reason_of(nn)
                R0.problem(*[b for b in bs if b.startswith("연구 검토 결과")])
                R0.problem(*[PROB.harm_line(code_type.get(m.group(1).upper()))
                             for m in SRCS.CODE.finditer(why)])
                R0.basis(*[b for b in bs if not b.startswith("연구 검토 결과")])
                R0.cause(*ws)
                cnode["children"].append(nn)
                created += 1

            # 신설 조문을 짝이 되는 조문 바로 뒤로 옮긴다
            for what, after in PLACE_AFTER.get((ptitle, ctitle), {}).items():
                kids = cnode["children"]
                src = next((i for i, k in enumerate(kids) if k.get("title") == what), None)
                dst = next((i for i, k in enumerate(kids) if k.get("title") == after), None)
                if src is None or dst is None:
                    print(f"  [자리 옮김 건너뜀] {ctitle} — {what}")
                    continue
                kids.insert(dst + 1 if dst < src else dst, kids.pop(src))

            # 옮겨 온 조문을 신설 조문 뒤에 붙일 장 — 총칙 성격의 신설 조문이 앞에 오게 한다
            if (ptitle, ctitle) in TAIL and n_moved_here:
                cnode["children"] = (cnode["children"][n_moved_here:]
                                     + cnode["children"][:n_moved_here])

            pnode["children"].append(cnode)
        tree.append(pnode)

    # 옮기지 못한 조문 — 제217조(재검토기한) 등
    left = [no for no in sorted(by_no) if no not in used]
    if left:
        pi = len(tree) + 1
        p = node("편", pi, "보칙", "수정", "",
                 id=part_id.get(PART_OF.get(pi)) or f"dp{pi}")
        reason_of(p).now("현행 각 편에 흩어져 있던 조문").cause(
            "편을 다시 나누면서 어느 편에도 들지 아니하는 조문을 보칙으로 모은다",
            "측량기기 규정은 총칙으로 옮긴다")
        c = node("장", 1, "보칙", "신설", "")
        for no in left:
            n = json.loads(json.dumps(by_no[no]))
            n["children"] = []; n["history"] = []
            n["legacyNo"] = n.get("legacyNo") or f"제{no}조"
            n["status"] = "이동"
            old = where.get(no, ("", None))[0]
            R = reason_of(n)
            R.now(f"{n['legacyNo']}({n.get('title') or ''})" + (f" — {old}" if old else ""))
            R.cause(f"편을 다시 나누면서 어느 편에도 들지 아니하여 제{len(tree)+1}편 보칙으로 옮긴다")
            # 부록4 의 지적은 사유로만 남기고, 본문을 고치지 아니했으면 '이동' 그대로 둔다
            for r in fixes.get(no, []):
                R.basis(apx4_basis(r, no)).cause(apx4_cause(r, no))
            c["children"].append(n)
        p["children"].append(c)
        tree.append(p)
        moved += len(left)

    # 별표·별지는 그대로 옮기고 확대 방향만 사유로 남긴다
    annex = json.loads(json.dumps(reg.get("annexTree") or []))
    for g in annex:
        g["status"] = "수정"
        # 종수는 여기에 적지 아니한다 — 신설 서식을 붙이기 전이라 셈이 맞지 아니한다.
        # 최종 종수는 '개정 내용' 이 트리를 세어 적는다 (draft2025_detail.what_group).
        # '약 60종' 은 연구보고서의 예상치였으므로 쓰지 아니한다.
        bs, ws = RSN.split("성과 유형별 품질요소 평가기준, 제품사양서 서식, 전자성과 표준 "
                           "규격, 안전관리 서식 등 조문이 위임하고도 서식이 없던 것을 "
                           "새로 만들어 더한다. 현행 서식은 하나도 빼지 아니한다. [표 4-3]",
                           code_fix, code_basis)
        reason_of(g).now("현행 별표·별지 묶음").basis(*bs).cause(*ws)
        g["history"] = []
        for k in g.get("children") or []:
            k["history"] = []

    # 이름이 같아 가려낼 수 없던 별표를 쓰임에 맞추어 고친다
    ANNEX_RENAME = {
        "별표 2": ("공공기준점 점의 조서",
                   "별표 20과 이름이 같아 가려낼 수 없었다. 서식이 고시번호·급수·좌표원점·"
                   "삼각점성과·수준점성과를 담는 공공기준점용이므로 이름에 쓰임을 밝힌다. "
                   "현행 제23조·제31조·제37조·제43조·제59조·제201조·제211조가 쓰는 서식이다."),
        "별표 20": ("노선측량 점의 조서",
                    "별표 2와 이름이 같아 가려낼 수 없었다. 서식이 노선번호·점번호·표지의 "
                    "종류(목항·석항·못·각인)·소재지·약도를 담는 노선측량용이므로 이름에 쓰임을 "
                    "밝힌다. 현행 제103조 중심선측량이 쓰는 서식이다."),
    }
    for g in annex:
        for k in g.get("children") or []:
            got = ANNEX_RENAME.get(str(k.get("legacyNo")).strip())
            if got:
                # 고치기 전의 이름을 남겨 둔다 — 화면에서 달라진 말을 짚어 보이는 데 쓴다
                k["wasTitle"] = k.get("title") or ""
                k["title"] = got[0]
                k["status"] = "수정"
                cur = f"{k.get('legacyNo')}({k.get('origTitle') or ''})".replace("()", "")
                reason_of(k).now(cur).cause(*RSN.sentences(got[1]))

    # 고정형 지상라이다 작업매뉴얼(개정안) 제8장 표준양식을 별표·별지로 들여온다
    MAN_WHY = ("고정형 지상라이다 작업매뉴얼 개정(안)(공간정보품질관리원, 2026.3) 제8장 "
               "표준양식을 지상레이저측량에 의한 세부측량의 서식으로 들여온다.")
    MAN_ANNEX = []
    SAFETY_WHY = ("제6편 안전관리의 안전관리비 조문이 위임한 서식이다. "
                  "「측량대가의 기준」 제9조의 직접경비에 안전관리비 항목이 없어 "
                  "계상·사용·정산의 근거 서식을 함께 마련한다. 부록4 E-8")
    RATE_BODY = (
        "1. 안전관리비는 대상액에 다음 표의 적용비율을 곱한 금액(기초액이 있는 경우에는 그 "
        "금액을 더한 금액)으로 계상한다.<img id=\"t4314\"></img>\n"
        "2. 제1호의 요율은 「건설업 산업안전보건관리비 계상 및 사용기준」(고용노동부고시 "
        "제2025-11호, 2025.2.12. 시행) 별표 1의 계상기준표 가운데 특수건설공사 요율을 준용한 "
        "것이다. 그 계상기준표는 다음과 같다.<img id=\"t4313\"></img>\n"
        "3. 작업 구간에 포함된 현장작업 환경에 따라 다음 표의 가산율을 더한다. 이 경우 "
        "계상액은 구간별 대상액 × 적용비율 × (1 + 가산율)을 모두 더한 금액으로 한다."
        "<img id=\"t4315\"></img>\n"
        "4. 「산업안전보건법」 제72조에 따라 산업안전보건관리비를 계상하는 사업의 경우에는 "
        "그 고시에서 정하는 공사종류의 요율에 따르며, 이 표를 거듭 적용하지 아니한다.")
    PKG_BODY = (
        "1. 성과패키지에 담는 성과 등은 측량의 유형별로 다음 표와 같다."
        "<img id=\"t4316\"></img>\n"
        "2. 노선측량의 성과 등의 종류는 다음과 같다.<img id=\"151295961\"></img>\n"
        "3. 하천 및 연안측량의 성과 등의 종류는 다음과 같다.<img id=\"151295965\"></img>\n"
        "4. 용지측량의 성과 등의 종류는 다음과 같다.<img id=\"151295987\"></img>")
    PKG_WHY = ("각 편에 흩어져 같은 말을 되풀이하던 '성과 등의 정리(관리)' 조문 열 개"
               "(현행 제31조·제43조·제59조·제74조·제93조·제109조·제119조·제130조·"
               "제167조·제191조)를 총칙 「성과패키지」 조문으로 통합하면서, 유형별 열거는 "
               "이 별표로 옮겼다. 열거 내용은 각 조문에서 그대로 가져왔고, 노선·하천·용지의 "
               "성과 종류 표는 현행 조문에 실려 있던 표를 그대로 옮겼다. 부록4 D-3")
    # 조문이 '별표(별지)에서 정한다' 로 위임했으나 아직 서식이 없는 것을 목록에 올린다
    DELEG_WHY = ("조문이 위임했으나 서식이 없던 것을 목록에 올린다. 위임한 조문과 짝이 "
                 "맞지 아니하면 규정이 작동하지 아니한다.")
    DELEG = [
        ("별표", "성과 유형별 품질요소 평가기준",
         "완전성·논리일관성·위치정확도·주제품질·시간품질의 평가 항목과 정량 기준을 성과의 "
         "유형별로 정한다. 총칙 「공공측량 성과의 품질요소」 제2항이 위임한 것이다."),
        ("별표", "제품사양서 서식",
         "총칙 「제품사양서」 제4항이 위임한 것이다."),
        ("별표", "전자성과 제출 표준 규격",
         "폴더 구조, 파일명 규칙 및 메타데이터 필수 항목을 정한다. 총칙 「전자성과의 제출 및 "
         "메타데이터」 제3항과 「성과패키지」 제7항이 위임한 것이다."),
        ("별표", "공공측량성과 심사·재심사의 절차 및 기한",
         "총칙 「공공측량성과 심사의 기준」 제4항이 위임한 것이다."),
                                        ("별표", "지하시설물 매설 상황별 측량방법 및 정확도 기준",
         "제5편 「매설 상황별 측량 방법」 제2항이 위임한 것이다."),
        ("별표", "지하시설물 탐사장비의 성능 요건 및 탐사 세부 기준",
         "지표투과레이더의 주파수·측선 간격·취득 속도와 비금속관 탐사장비의 성능 요건을 "
         "정한다. 제5편 「지표투과레이더 탐사」 제5항과 「비금속관 탐사」 제3항이 위임한 "
         "것이다."),
        ("별표", "안전교육·훈련의 시간 및 주기",
         "제6편 「안전교육 및 훈련」 제3항이 위임한 것이다."),
        ("별표", "측량기기의 종류별 요구 성능",
         "제1편 총칙 「측량기기의 일반 기준」 제3항이 위임한 것이다."),
        ("별표", "측량기기 유형별 성능검사 시험항목 및 주기",
         "제1편 총칙 「측량기기의 성능검사」 제4항이 위임한 것이다."),
        ("별지", "현장 위험성평가서",
         "제6편 「현장 위험성평가 및 재평가」 제4항이 위임한 것이다."),
        # 유형별 관리표 14종을 하나로 합치는 안 — 결정 전이므로 목록 맨 뒤에 둔다.
        # 기존 관리표는 그대로 두므로, 채택하기 전에는 이 표를 쓰지 아니한다.
        ("별표", "정확도 관리표(통합안)",
         "유형별 정확도 관리표 14종의 뼈대를 하나로 합치는 안이다. 채택 여부가 정해지기 "
         "전에는 유형별 관리표를 그대로 쓴다. 총칙 「정확도 관리」 조문이 위임한 것이다."),
        ("별표", SPLIT.COLOR_ANNEX,
         "지하시설물의 종류별 기본색상과 그 색상코드를 정한다. 제5편 「시설물의 표시 "
         "색상」 제1항이 위임한 것이다."),
        ("별지", "안전관리 기록부",
         "안전관리계획서, 위험성평가서, 교육·훈련 기록, 작업중지·재개 기록, 사고 조치 기록을 "
         "한 서식으로 묶는다. 제6편 「안전관리 기록」 제2항이 위임한 것이다."),
    ]
    MMS_BODY = (
        "1. 차량기반 이동측량 성과의 정확도 허용범위는 「정밀도로지도의 구축 및 갱신 등에 "
        "관한 규정」 별표 1(위치정확도 기준)에 따른다. 점군의 위치정확도는 같은 규정 "
        "제20조제1항, 인접·중복 점군 사이의 정합정확도는 같은 규정 제21조제1항에서 "
        "정하는 바에 따른다.\n"
        "2. 조정점과 검증점의 배치·수량은 「정밀도로지도의 구축 및 갱신 등에 관한 규정」 "
        "제18조제2항에 따른다. 이 경우 같은 항의 보정점은 이 규정의 조정점으로, 검사점은 "
        "이 규정의 검증점으로 본다.\n"
        "3. 정합 정확도와 검증점 검증은 수평성분과 수직성분으로 나누어 판정하고, "
        "평균제곱근오차(RMSE)와 최대오차를 함께 적는다.\n"
        "4. 위성항법 신호를 받기 어려운 구간(음영구간)에서는 제2호의 기준에 더하여 "
        "조정점을 구간마다 2점 이상 둔다. 조정점의 정확도와 점간거리 허용범위는 "
        "제4편 「위성항법 음영구간과 조정점」에서 정하는 바에 따른다.\n"
        "5. 정밀도로지도를 제작하는 경우가 아니어서 제1호와 제2호를 그대로 적용하기 "
        "어려운 경우에는 공공측량 작업계획으로 달리 정할 수 있다. 이 경우 그 사유와 "
        "적용한 기준을 성과패키지의 처리이력에 적는다.")
    MMS_WHY = ("제4편 「취득 성과의 점검과 정합」 제7항이 위임한 것이다. 정확도 허용범위와 "
               "점의 배치는 「정밀도로지도의 구축 및 갱신 등에 관한 규정」이 이미 정하고 "
               "있으므로, 그 값을 이 별표에 옮겨 적지 아니하고 그 규정을 가리키는 데 "
               "그친다. 옮겨 적으면 그 규정이 바뀔 때 두 곳이 어긋난다. 다만 그 규정과 "
               "이 규정이 쓰는 점의 이름이 다르므로(보정점·검사점 ↔ 조정점·검증점) "
               "무엇이 무엇에 해당하는지만 밝힌다.")

    # 위임 목록의 제자리(안전교육·훈련 앞)에 둔다 — 별표 번호가 흔들리지 않게 한다
    DELEG.insert(6, ("별표", "차량기반 이동측량의 정합 허용범위 및 검증점 배치", MMS_BODY))

    MAN_ANNEX += [
        ("별표", "안전관리비 계상 요율", RATE_BODY),
        ("별표", "성과 유형별 성과패키지의 구성", PKG_BODY),
        ("별지", "안전관리비 사용내역서", "사용 항목별 금액과 증빙, 정산 결과를 적는다."),
    ] + DELEG
    ANNEX_WHY = {
        "정확도 관리표(통합안)":
            "유형별 정확도 관리표가 14종에 이르는데 뼈대는 둘뿐이다. 구간·측점마다 관측값을 "
            "허용범위와 견주는 것(현행 별표 3·4·7·15·18·19·21·22·23·24·25)과 도면의 항목마다 "
            "오기·누락을 세는 것(현행 별표 14·16·17)이다. 머리(사업 정보·사용 기기)와 꼬리"
            "(점검측량·재측률·특기사항)는 서식마다 거의 같으면서 칸의 이름과 차례만 달라, "
            "수행자는 측량마다 다른 서식을 익혀야 하고 심사자는 같은 것을 다른 자리에서 찾아야 "
            "한다. 뼈대를 하나로 하고 그 측량에 해당하지 아니하는 도막은 비워 두게 하면 이 "
            "부담이 사라진다. 점검 항목은 「성과 유형별 품질요소 평가기준」 의 품질요소에 "
            "맞추어 성과심사와 잣대를 같이한다. 다만 서식을 합치는 것은 현장의 관행에 미치는 "
            "바가 크므로 이 별표는 안으로 두고, 채택 여부가 정해지기 전에는 유형별 관리표를 "
            "그대로 쓴다.",
        "차량기반 이동측량의 정합 허용범위 및 검증점 배치": MMS_WHY,
        "안전관리비 계상 요율": SAFETY_WHY + " 요율은 「건설업 산업안전보건관리비 계상 및 "
                               "사용기준」(고용노동부고시 제2025-11호) 별표 1의 특수건설공사 "
                               "요율을 준용했다. 측량용역은 건설공사가 아니어서 그 고시가 직접 "
                               "적용되지 아니하나, 특수건설공사가 다른 공사와 분리하여 발주되고 "
                               "시간적·장소적으로도 독립하여 행하는 공사를 가리키는 점에서 "
                               "측량용역의 수행 형태와 가장 가깝다. 환경별 가산율도 같은 "
                               "고시 안에서 공사종류 사이의 요율 격차를 그대로 옮겼다. "
                               "기준 요율 대비 건축공사 +45퍼센트, 토목공사 +59퍼센트, "
                               "중건설공사 +90퍼센트이며, 이를 각각 Ⅱ·Ⅲ·Ⅳ 등급에 "
                               "대응시켰다. 등급 배정은 환경별 핵심 위험에 따른 것으로 "
                               "위험특성 분석 결과가 나오면 다시 검토한다.",
        "안전관리비 사용내역서": SAFETY_WHY,
        "성과 유형별 성과패키지의 구성": PKG_WHY,
    }
    for _g, _t, _n in DELEG:
        # 이미 사유를 따로 지어 둔 것(본문까지 갖춘 별표)은 그대로 둔다
        ANNEX_WHY.setdefault(_t, f"{DELEG_WHY} {_n}")
    for g in annex:
        gubun = "별지" if g["title"].startswith("별지") else "별표"
        rows = [x for x in MAN_ANNEX if x[0] == gubun]
        if not rows:
            continue
        base = len(g.get("children") or [])
        for i, (_, title, note) in enumerate(rows, start=1):
            why = ANNEX_WHY.get(title) or (MAN_WHY + (" " + note if note else ""))
            an = node("조", 0, title, "신설", "", id=f"nanx-{gubun}-{i}", body=note,
                      legacyNo=f"{gubun} {base + i}",
                      annexRef={"gubun": gubun, "no": str(base + i), "hwp": "", "pdf": ""})
            bs, ws = RSN.split(why, code_fix, code_basis)
            R = reason_of(an).basis(*bs).cause(*ws)
            # '… 제○항이 위임한 것이다' 는 근거로 옮긴다
            R.why[:] = [w for w in R.why if not RSN.DELEG_LINE.search(w)]
            for w in RSN.sentences(why):
                if RSN.DELEG_LINE.search(w):
                    R.basis(w)
            created += 1
            g.setdefault("children", []).append(an)
        g["title"] = f"{gubun} ({base + len(rows)}건)"
    tree.extend(annex)

    doc = {
        "id": "draft2025",
        "label": "v1",
        "title": "개편안 초안(2025)",
        "base": reg["name"],
        "source": SRC,
        "sourceFile": os.path.basename(REPORT),
        "readonly": True,
        "review": os.path.basename(REVIEW_FILE) if review else "",
        "note": ("2025년 전략수립 연구보고서의 [표 4-3] 편별 구성 비교(안), 제4장 개정 방안, "
                 "부록 4 조문별 문제점 분석표를 근거로 만든 구조 개편안입니다. "
                 "품관원 검토의견(2026.07.27)을 함께 반영했으며, 그 사유는 [품관원] 으로 시작합니다. "
                 "조문 표시는 본문이 실제로 바뀐 때에만 '수정' 으로 하고, 자리만 옮긴 "
                 "경우에는 '이동' 으로 두었습니다. 보고서가 짚은 문제는 표시를 바꾸지 "
                 "아니하고 사유에만 적었습니다. "
                 "읽기 전용이며, 고치면 상위 버전으로 갈라 나갑니다."),
        "tree": tree,
    }
    def expand(text):
        return SRCS.rewrite(text, code_fix)
    expanded = [0]
    def walk_reason(ns):
        for n in ns:
            if n.get("reason"):
                new = expand(n["reason"])
                if new != n["reason"]:
                    n["reason"] = new
                    expanded[0] += 1
            walk_reason(n.get("children") or [])
    walk_reason(tree)

    # 흩어진 용어 정의를 총칙 제2조로 모은다
    def find_a2(ns):
        for x in ns:
            if x.get("legacyNo") == "제2조" and x.get("level") == "조":
                return x
            got = find_a2(x.get("children") or [])
            if got:
                return got
        return None

    a2 = find_a2(tree)

    # 문장 안에 숨어 있던 약칭을 먼저 걷어 낸다
    n_alias = [0]
    def strip_alias(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef") and x.get("legacyNo") != "제2조":
                body, got = ALIAS.strip_from(x.get("body") or "")
                if got:
                    x["body"] = body
                    n_alias[0] += len(got)
                    reason_of(x).cause(
                        f"문장 안에 있던 약칭({', '.join(got)})의 뜻은 총칙 정의 조문으로 "
                        f"올리고, 이 조에서는 괄호를 지운다")
            strip_alias(x.get("children") or [])
    strip_alias([n for n in tree if not n.get("isAnnex")])

    cur_titles = {f"제{k}조": (v.get('title') or '') for k, v in by_no.items()}
    defs_got, defs_dropped, defs_part = DEFS.collect(tree, cur_titles=cur_titles)
    defs_got += [(t, s, "약칭에서 옮김") for t, s in ALIAS.sentences()]

    # 총칙 한 조에 다 모으면 130호가 넘어 읽기 어렵다.
    # 그 편에서만 쓰는 말은 그 편의 정의 조문으로 내려보낸다.
    # DEFS 가 조문에 남긴 기록(정의 항을 떼어 냈다)은 그냥 두면 렌더 단계에서
    # 버려진다. 개정 내용으로 옮겨 담는다
    def _keep_defs_note(ns):
        for x in ns:
            note = str(x.get("reason") or "").strip()
            if note and x.get("level") == "조":
                # 곧바로 넣으면 조문별로 지은 개정 내용이 밀려나므로 따로 들고 있다가
                # fill 단계에서 계산한 줄 뒤에 붙인다
                x["_defnote"] = RSN.sentences(note)
                x["reason"] = ""
            _keep_defs_note(x.get("children") or [])
    _keep_defs_note(tree)

    defs_keep, defs_by_part = DEFS.split_by_part(tree, defs_got, defs_part)
    n_part_defs = 0
    for part in [p for p in tree if p.get("level") == "편" and not p.get("isAnnex")]:
        items = defs_by_part.get(part.get("title") or "")
        if not items:
            continue
        head = f"이 편에서 사용하는 용어의 뜻은 다음과 같다."
        art = node("조", 0, "정의", "신설", "",
                   id=f"def-{stable_id(part.get('title'))}",
                   body=DEFS.body_of(items, head))
        R = reason_of(art)
        R.now("없음 — 신설 조문")
        R.basis(f"현행 규정에서 「{part.get('title')}」 에 해당하는 편·장의 정의 조문")
        R.cause(f"이 편에서만 쓰는 용어 {len(items)}개를 한자리에 모아 둔다",
                "총칙 정의 조문이 130호를 넘어 찾아 읽기 어려우므로 편별로 나눈다")
        R.what(f"현행 규정에 흩어져 있던 이 편의 용어 정의 {len(items)}개를 이 조로 모으고, "
               f"각 호 뒤에 어느 조문에서 온 것인지 적는다. 호의 차례는 그 정의가 있던 "
               f"현행 조문의 차례로 하여, 개정 전후를 조문별로 따라갈 수 있게 한다")
        # 그 편의 첫 장(개설·통칙) 맨 앞에 둔다. 장이 없으면 편 바로 아래에 둔다
        chap = next((c for c in (part.get("children") or [])
                     if c.get("level") == "장"), None)
        (chap or part)["children"].insert(0, art)
        n_part_defs += len(items)

    if a2 and defs_keep:
        # 현행 제2조가 본래 갖고 있던 용어 — 이 조에 뒤에 넣은 신설 정의와 가른다
        own2 = [DEFS.term_of(re.sub(r"^\s*\d+\.\s*", "", l).strip())
                for l in (by_no[2].get("body") or "").splitlines()[1:]]
        a2["body"] = DEFS.merge_into(a2, defs_keep, [x for x in own2 if x])
        a2["status"] = "수정"
        _resolve_ho(tree, a2)
        add = (f"각 편에 흩어져 있던 용어 정의 {len(defs_got)}개를 거두어, 여러 편이 함께 쓰는 말 "
               f"{len(defs_keep)}개만 이 조에 남기고 나머지 {n_part_defs}개는 그 말을 쓰는 편의 "
               f"「정의」 조문으로 내려보냈다. "
               f"정의만 있던 조문 {len(defs_dropped)}개는 없애고, 규율이 함께 있던 조문은 "
               f"정의 항만 떼어 냈다. 각 정의 뒤에 어느 조문에서 온 것인지 적었다. "
               f"다만 '(이하 \"○○\"라 한다)' 꼴의 약칭은 그 정의 문장에 딸린 것으로 보아 함께 "
               f"옮겼다. "
               f"호의 차례는 가나다순이 아니라 현행 규정의 차례를 따랐다. 현행 제2조가 본래 "
               f"갖고 있던 호를 그대로 앞에 두고, 다른 조문에서 옮겨 온 것은 그 현행 조문의 "
               f"번호 차례로 이어 붙였으며, 현행에 근거가 없는 신설 정의와 약칭은 맨 뒤에 "
               f"두었다. 가나다순으로 두면 한 조문에서 온 정의가 흩어져 개정 전후를 "
               f"견주기 어렵다.")
        reason_of(a2).cause(*RSN.sentences(add))

    # 조·장·편 번호를 앞에서부터 다시 매긴다 (앱이 화면에서 하는 것과 같게)
    def renumber(tree):
        jo = [0]
        def rec(ns, lv_part=0):
            ch = 0
            for x in ns:
                if x.get("isAnnex"):
                    continue
                if x.get("level") == "편":
                    rec(x.get("children") or [])
                elif x.get("level") == "장":
                    ch += 1
                    x["no"] = ch
                    rec(x.get("children") or [])
                elif x.get("level") == "조":
                    jo[0] += 1
                    x["no"] = jo[0]
                    rec(x.get("children") or [])
                else:
                    rec(x.get("children") or [])
        pi = 0
        for p in tree:
            if p.get("isAnnex"):
                continue
            pi += 1
            p["no"] = pi
            rec(p.get("children") or [])
        return jo[0]

    # ── 여러 주제가 뒤섞인 긴 조문을 여러 조문으로 나눈다 ──────────
    #    번호를 다시 매기기 전에 해야 뒤 조문의 번호가 한 번에 밀린다
    n_split = [0, 0]
    def _split_all(ns):
        out = []
        for x in ns:
            _split_all(x.get("children") or [])
            got = (SPLIT.parts(x.get("legacyNo"), x.get("body") or "")
                   if x.get("level") == "조" and not x.get("annexRef") else None)
            if not got:
                out.append(x)
                continue
            was = reason_of(x)
            # 나눈 조각은 모두 본문이 바뀐 것이다. 원래 옮겨 온 조문이었으면
            # 옮김 표시를 잃지 아니하게 '이동·수정' 으로 둔다
            st = "이동·수정" if str(x.get("status") or "").startswith("이동") else "수정"
            for i, (t, b, why, what) in enumerate(got):
                k = node("조", 0, t, st, "",
                         legacyNo=x.get("legacyNo"), id=f"{x['id']}-s{i + 1}", body=b)
                R = reason_of(k)
                R.now(was.cur)
                R.basis(*was.base)
                R.cause(f"한 조에 {len(got)}개 주제가 뒤섞여 있어 조문을 나눈다 — "
                        f"{x.get('legacyNo')}({x.get('title')})를 {len(got)}개 조로 가른다",
                        why)
                R.what(what)
                out.append(k)
            n_split[0] += 1
            n_split[1] += len(got)
        ns[:] = out
    _split_all(tree)

    # 별표·별지 정리 — 갈음된 것 빼기, 번호 다시 매기기, 위임 조문에 번호 넣기
    anx_got = ANXFIX.run(tree, reason_of, RSN)

    n_jo = renumber(tree)

    # ── 본문이 가리키는 '제○조' 를 새 번호로 맞춘다 ──────────────
    #    번호를 다시 매겼으므로 본문의 인용도 함께 옮겨야 한다. 한 번에,
    #    한 자리에서만 한다 — 미리 손으로 고쳐 두면 여기서 다시 매겨져
    #    두 번 어긋난다 (draft2025_amend.py 의 주석 참고).
    old2new = {}
    def _collect(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef"):
                m = re.match(r"제(\d+)조", str(x.get("legacyNo") or ""))
                if m:
                    old2new[int(m.group(1))] = x["no"]
            _collect(x.get("children") or [])
    _collect(tree)

    # 다른 법령·규정을 가리키는 자리는 건드리지 아니한다
    RE_LAWJO = re.compile(
        r"(?:[「『][^」』]{2,60}[」』]|(?:그|같은|이)\s*(?:규정|지침|준칙|고시|기준)"
        r"|같은\s*법(?:\s*시행령|\s*시행규칙)?|시행령|시행규칙|법률|법|영|규칙)"
        r"\s*(?:제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*[항호])*[,·\s및과와]*)+")
    RE_PROV = re.compile(r"<[^<>]*>")          # <현행 제150조 「정의」> 는 출처 표시다
    RE_ONEJO = re.compile(r"제\s*(\d+)\s*조")

    def _swap(seg, hits):
        def one(m):
            new = old2new.get(int(m.group(1)))
            if not new or new == int(m.group(1)):
                return m.group(0)
            hits.append((int(m.group(1)), new))
            return f"제{new}조"
        return RE_ONEJO.sub(one, seg)

    def restamp(text, hits):
        """법령 인용과 출처 표시는 그대로 두고, 이 규정의 조 번호만 바꾼다"""
        out, last = [], 0
        # 두 갈래로 찾은 자리를 앞에서부터 훑도록 위치순으로 합친다.
        # 그냥 이어 붙이면 뒤쪽 갈래의 앞자리가 last 에 걸려 건너뛰어지고,
        # 그 자리의 <현행 제N조 …> 출처 표시까지 새 번호로 덧칠된다.
        marks = sorted(list(RE_LAWJO.finditer(text)) + list(RE_PROV.finditer(text)),
                       key=lambda m: (m.start(), -m.end()))
        for m in marks:
            if m.start() < last:
                continue
            out.append(_swap(text[last:m.start()], hits))
            out.append(m.group(0))
            last = m.end()
        out.append(_swap(text[last:], hits))
        return "".join(out)

    restamped = [0]
    def _restamp_all(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef") and x.get("body"):
                hits = []
                x["body"] = restamp(x["body"], hits)
                if hits:
                    restamped[0] += 1
                    R = reason_of(x)
                    li = ", ".join(f"제{a}조→제{b}조" for a, b in dict(hits).items())
                    R.cause(f"번호를 다시 매기면서 본문이 가리키던 조문의 번호가 바뀌었으므로 "
                            f"인용을 맞춘다 ({li})")
            _restamp_all(x.get("children") or [])
    _restamp_all(tree)

    # ── 호·목을 줄로 가른다 ──────────────────────────────────────
    #    현행 원문은 호와 목을 줄바꿈 없이 이어 적은 곳이 많다. 읽기 어렵고
    #    자동 처리에서 사고가 난다. 본문을 다 손질한 뒤 맨 마지막에 편다
    #    (앞 단계들이 줄 얼개에 기대고 있어 먼저 하면 어긋난다).
    n_layout = [0]

    def _relayout_all(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef"):
                was = x.get("body") or ""
                now = LAYOUT.relayout(was)
                if now != was:
                    x["body"] = now
                    n_layout[0] += 1
            _relayout_all(x.get("children") or [])
    _relayout_all(tree)

    # ── 없앤 조문·별표·별지를 따로 모아 보인다 ────────────────────
    #    트리에서 사라지면 무엇이 왜 없어졌는지 알 길이 없다. 맨 뒤에
    #    '삭제' 묶음을 세워 현행 번호·제목과 없앤 까닭을 남긴다.
    live_jo = set()
    def _live(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef"):
                m = re.match(r"제(\d+)조", str(x.get("legacyNo") or ""))
                if m:
                    live_jo.add(int(m.group(1)))
            _live(x.get("children") or [])
    _live(tree)

    # 없앤 까닭을 사실로 뒷받침하기 위한 자료
    #  · 정의를 어디로 올렸는지 — 거둔 정의의 출처 표시에서 현행 조번호를 뽑는다
    #  · 통합 조문이 개편안에서 몇 조가 되었는지 — 제목으로 찾는다
    def_terms = {}                       # 현행 조번호 → 그 조에서 올린 용어 목록
    for _term, _s, _lb in defs_got:
        m = re.match(r"현행 제(\d+)조", str(_lb or ""))
        if m and _term:
            def_terms.setdefault(int(m.group(1)), []).append(_term)
    def_home = {}                        # 용어 → 그 정의가 놓인 편 ("" 이면 총칙)
    for _part, _items in defs_by_part.items():
        for _t, _s, _src in _items:
            def_home[_t] = _part

    live_at = {}                         # 조문 제목 → "제N조"
    def _index_live(ns):
        for x in ns:
            if x.get("level") == "조" and not x.get("annexRef") and not x.get("isDeleted"):
                live_at.setdefault(str(x.get("title") or "").strip(), f"제{x.get('no')}조")
            _index_live(x.get("children") or [])
    _index_live(tree)

    def _why_gone(no, title):
        """왜 없앴는가 · 무엇이 어떻게 되었는가 — (사유들, 내용들)"""
        if no in MERGED:
            tgt = MERGED[no]
            group = MERGED_PEERS.get(tgt, [no])
            # 현행 조문을 직접 견주어 얼마나 어긋나는지 세어 둔다 (공청회 근거)
            prob = PROB.divergence(
                [(x, (by_no[x].get("title") or ""), (by_no[x].get("body") or ""))
                 for x in group if x in by_no],
                "고쳐야 할 곳이 열 곳이면 열 곳이 다 고쳐지기를 기대하기 어렵다"
                if len(group) >= 5 else
                "한쪽만 고치면 두 조문이 서로 다른 것을 요구하게 된다")
            at = live_at.get(tgt, "")
            peers = [p for p in MERGED_PEERS.get(tgt, []) if p != no]
            spot = f"{at}({tgt})" if at else f"「{tgt}」"
            # 흩어져 있던 범위를 사실대로 적는다 — 여러 편인지, 한 편의 여러 장인지
            parts = {re.match(r"(제\d+편)", (where.get(p) or ("", ""))[0]).group(1)
                     for p in group
                     if re.match(r"(제\d+편)", (where.get(p) or ("", ""))[0])}
            spread = "여러 편에" if len(parts) > 1 else "같은 편의 여러 장에"
            why = [f"{spread} 같은 말로 나뉘어 있던 조문 {len(group)}개를 {spot} 한 조로 통합하였다"]
            what = [f"현행 제{no}조의 내용은 {spot} 에 들어 있다"]
            if peers:
                # '현행' 을 번호 바로 앞에 둔다 — 화면에서 사유의 조문을 링크로 이을 때
                # 앞말이 '현행' 인 것만 걸러 내므로, 떨어져 있으면 개편안 번호로 오인된다
                what.append("같은 조로 합친 것은 현행 제"
                            + "조·제".join(str(p) for p in peers) + "조이다")
            return why, what, prob

        terms = def_terms.get(no) or []
        if terms:
            homes = {def_home.get(t, "총칙") for t in terms}
            at = live_at.get("정의", "제2조")
            spot = (f"「{list(homes)[0]}」 편의 「정의」 조문"
                    if len(homes) == 1 and list(homes)[0] != "총칙"
                    else f"총칙 {at}(정의)")
            why = [f"용어의 뜻만 정하던 조문이므로 그 정의를 {spot} 으로 올리고 없앴다"]
            what = [f"이 조가 정하던 용어 {len(terms)}개("
                    + ", ".join(f"「{t}」" for t in terms[:6])
                    + (" 등" if len(terms) > 6 else "") + ")를 그 조의 각 호로 옮겼다",
                    "각 호 뒤에 어느 조문에서 온 것인지 적어 두었다"]
            if len(homes) > 1:
                what.append("여러 편이 함께 쓰는 말은 총칙에, 한 편에서만 쓰는 말은 "
                            "그 편의 정의 조문에 나누어 두었다")
            prob = ["용어의 뜻이 편마다 흩어져 있어, 같은 말을 쓰면서도 어느 조문의 "
                    "뜻인지 찾아 헤매게 된다",
                    "정의만 있는 조문이 본문 조문과 같은 차례로 섞여 있어 "
                    "조문 수만 늘리고 규율 내용은 없다"]
            return why, what, prob

        return (["현행 규정을 정비하면서 이 조를 두지 아니하기로 하였다"],
                ["개편안에 이 조를 이어받은 조문이 없다"],
                [])

    gone_jo, gone_anx = [], []
    for no in sorted(by_no):
        if no in live_jo:
            continue
        src = by_no[no]
        t = src.get("title") or ""
        why, what, prob = _why_gone(no, t)
        k = node("조", 0, f"제{no}조 {t}", "삭제", "", legacyNo=f"제{no}조",
                 id=f"del-jo-{no}", isDeleted=True, isAppendix=True)
        R = reason_of(k)
        R.now(f"제{no}조({t}) — {(where.get(no) or ('', ''))[0]}".rstrip(" —"))
        R.problem(*prob)
        R.basis("현행 조문 — 개편안에서 없앤다")
        R.cause(*why)
        R.what(*what)
        gone_jo.append(k)

    for (gubun, no), t in (anx_got.get("dropped") or []):
        k = node("조", 0, f"{gubun} {no} {t or ''}".strip(), "삭제", "",
                 legacyNo=f"{gubun} {no}",
                 id=f"del-anx-{gubun}{no}", isDeleted=True, isAppendix=True)
        R = reason_of(k)
        R.now(f"{gubun} {no}({t or ''})")
        R.basis("현행 별표·별지 — 개편안에서 없앤다")
        R.cause(ANXFIX.drop_why(gubun, no))
        if (gubun, no) in ANXFIX.DROP_ACC:
            at = live_at.get("정확도 관리", "제9조")
            R.what(f"이 관리표가 담던 항목은 {at}(정확도 관리) 제3항의 "
                   f"「측량 유형별 정확도 관리표」 표에 측량 유형별로 한 줄씩 들어 있다")
        else:
            at = live_at.get("성과패키지", "제17조")
            R.what(f"이 서식이 담던 항목은 {at}(성과패키지) 제4항이 위임한 "
                   f"별표 「성과 유형별 성과패키지의 구성」 에 측량 유형별로 들어 있다",
                   f"측량의 유형과 관계없이 내야 하는 것은 {at} 제3항 각 호로 따로 적었다")
        gone_anx.append(k)

    if gone_jo or gone_anx:
        grp = node("편", 0, f"삭제 ({len(gone_jo) + len(gone_anx)}건)", "삭제", "",
                   id="del-group", isDeleted=True, isAppendix=True)
        grp["children"] = gone_jo + gone_anx
        # 별표·별지를 하나도 빼지 아니하게 되었으므로 '0건' 이라 적지 아니한다
        _gone = (f"없앤 조문 {len(gone_jo)}개"
                 + (f" · 별표·별지 {len(gone_anx)}건" if gone_anx else ""))
        _what = (f"별표·별지 {len(gone_anx)}건도 함께 모아 둔다" if gone_anx
                 else "현행 별표·별지는 하나도 빼지 아니하였다")
        reason_of(grp).now(_gone) \
            .problem("없앤 것을 트리에서 지워 버리면 무엇이 어디로 갔는지 좇을 수 없다. "
                     "개정 전후 비교표를 만들 수 없고, 없어진 조문을 두고 묻는 말에 "
                     "답할 근거도 남지 아니한다") \
            .basis("현행 규정에는 있으나 개편안에는 두지 아니한 것") \
            .cause("무엇이 왜 없어졌는지 남겨 두어야 개정 전후를 견줄 수 있다",
                   "통합·이관으로 없앤 것은 어느 조문이 대신하는지 함께 적었다") \
            .what(f"개편안에 두지 아니한 현행 조문 {len(gone_jo)}개를 이 묶음에 모아 둔다",
                  _what,
                  "항목마다 현행 번호와 제목을 이름 앞에 적고, 그 내용을 이어받은 "
                  "조문을 개정 내용에 밝힌다",
                  "이 묶음은 대조를 위한 것이므로 조문 수와 별표 수에는 넣지 아니한다")
        tree.append(grp)

    # 근거·사유가 빈 자리를 채운다.
    # 개정 내용은 현행 조문과 실제로 견주어 조문마다 다른 글을 짓는다
    # (scripts/draft2025_detail.py). 지어내지 못한 것만 기본 줄로 둔다.
    n_detail = [0]

    def fill(ns, part="", chap=""):
        for x in ns:
            lv = x.get("level")
            p2 = x.get("title") if lv == "편" else part
            c2 = x.get("title") if lv == "장" else (chap if lv != "편" else "")
            R = x.get("_R")
            if isinstance(R, RSN.Reason):
                st = x.get("status") or ""
                m = re.match(r"제(\d+)조", str(x.get("legacyNo") or ""))
                old_no = int(m.group(1)) if m else None
                was = by_no.get(old_no) if old_no else None
                if not R.base:
                    R.basis(RSN.DEFAULT_BASE.get(st, RSN.DEFAULT_BASE["기타"]))
                KEPT = "편제와 문언을 그대로 둔다"
                if st == "유지" and not x.get("isDeleted") and R.why in ([], [KEPT]):
                    R.why[:] = [DETAIL.why_kept(x, old_no)]
                elif not R.why:
                    R.cause(RSN.DEFAULT_WHY.get(st, RSN.DEFAULT_WHY["기타"]))
                if not R.prob and lv in ("편", "장") and not x.get("isDeleted"):
                    R.problem(*PROB.group_line(x))
                if not R.prob and lv == "조" and not x.get("isDeleted"):
                    # 연구 검토·검토의견에서 지적된 것이 없는 조문이다.
                    # 공청회에서 다툴 것이 아닌 것을 다툴 거리로 만들지 아니한다
                    if x.get("annexRef"):
                        R.problem("이 서식 자체에는 지적된 것이 없다")
                    elif st == "유지":
                        R.problem(PROB.none_line("유지"))
                    elif st == "이동":
                        same = ("현행과 같다" in " ".join(R.why)
                                or "현행과 같고" in " ".join(R.why))
                        R.problem(PROB.none_line("번호" if same else "이동"))
                    elif st == "신설":
                        R.problem("현행 규정에는 이 사항을 정한 조문이 없어, "
                                  "무엇을 어떻게 하여야 하는지 정해진 바가 없다")
                    else:
                        R.problem(PROB.none_line("이동"))

                if not R.what_:
                    lines = []
                    if x.get("isDeleted"):
                        pass                       # 삭제 묶음은 이미 따로 적었다
                    elif x.get("annexRef"):
                        lines = DETAIL.what_annex(x)
                    elif lv in ("편", "장"):
                        lines = DETAIL.what_group(x)
                    elif lv == "조":
                        here = f"제{x.get('no')}편 {p2}" if lv == "편" else \
                               (f"{p2} 「{c2}」 장" if c2 else p2)
                        lines = DETAIL.what_of(
                            x, was, (where.get(old_no) or ("", ""))[0], here,
                            obj_fixed=(old_no in OBJ_FIX))
                    lines += x.pop("_defnote", [])
                    if lines:
                        n_detail[0] += 1
                        R.what(*lines)
                    else:
                        R.what(RSN.DEFAULT_WHAT.get(st, RSN.DEFAULT_WHAT["기타"]))
                else:
                    R.what(*x.pop("_defnote", []))
            fill(x.get("children") or [], p2, c2)
    fill(tree)

    # 사유 얼개를 개조식 글로 바꾼다 (현행 규정 / 관련 근거 / 개정 사유)
    n_reason = render_reasons(tree)

    # 표 4-3 과 유형별 건수 표는 개편안 트리에서 세어 만든다 —
    # 조문을 더하거나 빼면 표가 저절로 따라오게 한다
    ntab, tbl_cites = TABLES.write(DATA, tree=tree, reg_tree=reg["tree"], apx4=apx4,
                                   cur_annex=reg.get("annex"))

    # 조문이 품은 표가 가리키는 별표를 그 조문에 적어 둔다 —
    # 검증기가 표까지 읽지는 못하므로, 표로 별표를 고르게 한 조문의 인용이
    # 사라진 것처럼 보이는 것을 막는다
    def _mark_tbl_cites(ns):
        for x in ns:
            ids = re.findall(r'<img\s+id="([\w.-]+)"', x.get("body") or "")
            got = sorted({c for i in ids for c in tbl_cites.get(i, [])})
            if got:
                x["citesAnnex"] = got
            _mark_tbl_cites(x.get("children") or [])
    _mark_tbl_cites(tree)

    with io.open(os.path.join(DATA, "draft2025.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n개편안 초안(2025) 을 만들었습니다.")
    print(f"  편 {len(PLAN)}(+보칙) · 옮긴 조문 {moved} · 본문을 고친 조문 {edited} · 신설 조문 {created}")
    # 검토의견뿐 아니라 인용 정정·법령명 정정도 이 수에 든다
    print(f"  본문을 손질한 곳 {amended}(검토의견·인용 정정) · 통합해 없앤 조문 {merged}"
          + (f" · 표의 부호를 바로잡은 조문 {objfixed}" if objfixed else ""))
    print(f"  별표·별지 — 갈음되어 뺀 것 {len(anx_got['dropped'])}종 · "
          f"본문의 번호 {anx_got['ref']}곳 고침 · 위임 조문에 번호 {anx_got['deleg']}곳 넣음 · 별지 표기 {anx_got['form']}곳 맞춤 · "
          f"사유 {anx_got['reason']}건 채움")
    print(f"  변경 사유 {n_reason}건을 개조식(현행 규정·관련 근거·개정 사유·개정 내용)으로 지었습니다")
    print(f"  부록4 코드를 실제 문장으로 푼 사유 {expanded[0]}건 · 보고서 표 {ntab}개를 XML 로")
    print(f"  주제가 뒤섞인 조문 {n_split[0]}개를 {n_split[1]}개 조로 나눴습니다")
    print(f"  호·목을 줄로 가른 조문 {n_layout[0]}")
    print(f"  현행과 견주어 개정 내용을 지은 조문 {n_detail[0]}")
    print(f"  본문의 조문 인용을 새 번호로 맞춘 조문 {restamped[0]}")
    print(f"  조 번호를 앞에서부터 다시 매겼습니다 — 제1조 ~ 제{n_jo}조")
    print(f"  문장 속 약칭 {n_alias[0]}곳을 총칙 정의로 올렸습니다")
    print(f"  총칙 정의로 모은 용어 {len(defs_got)}개 · 정의만 있어 없앤 조문 {len(defs_dropped)}개")
    print(f"  옮기지 못한 조문: {left if left else '없음'}")
    print(f"  출력: data/draft2025.json")
