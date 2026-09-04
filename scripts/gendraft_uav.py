# -*- coding: utf-8 -*-
"""
무인비행장치 측량 작업규정 — 개정안 초안(v1·v2) 만들기

읽는 곳 (관련규정\\무인비행장치 측량 작업규정개정관련)
  · 2020.무인비행장치 측량 작업규정\\          고시 원본·별표 원본 — 기준 대조용
  · 2024년.연구.한글파일\\                     v1 의 관련근거
      2024.연구성과.무인비행장치 측량 작업규정.개정안_25.07.18.pdf  (부록 1 신구대조표)
  · 2025년.연구결과\\                          v2 의 관련근거
      무인비행장치 측량 작업규정 개정(안).hwpx             (개정 전문 42조)
      무인비행장치 측량 작업규정 개정(안).별표수정(안).hwpx  (별표 15건)
      무인비행장치 측량 작업규정 개정(안).개정사유서.hwpx    (조항별·별표별 사유)

만드는 것 — data/draft_uav.json
  기준 : 현행 40조 (data/reg12.json)
  v1   : 2024년 연구성과 개정(안) — 현행에서 여섯 곳을 고치고 별표 3건을 새로 단다
  v2   : 2025년 연구결과 개정(안) — 드론 다중센서 기반 10장 42조 전부개정

사용:  python scripts/gendraft_uav.py [--dry]
"""
import io, os, re, sys, json, copy, zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import gendata as G
import genhwpml as H
import genannex as A

BASE = "reg12"
DRAFT_ID = "draftUav"
OUTFILE = "draft_uav.json"
SRC = os.path.join(ROOT, "..", "관련규정", "무인비행장치 측량 작업규정개정관련")
F2020 = os.path.join(SRC, "2020.무인비행장치 측량 작업규정")
BODY_HWP = "2.무인비행장치 측량 작업규정.2020.hwp"
PDF2024 = os.path.join(SRC, "2024년.연구.한글파일",
                       "2024.연구성과.무인비행장치 측량 작업규정.개정안_25.07.18.pdf")
F2025 = os.path.join(SRC, "2025년.연구결과")
HWPX_BODY = "무인비행장치 측량 작업규정 개정(안).hwpx"
HWPX_ANNEX = "무인비행장치 측량 작업규정 개정(안).별표수정(안).hwpx"
HWPX_WHY = "무인비행장치 측량 작업규정 개정(안).개정사유서.hwpx"

# 관보 원본은 가운뎃점에 옛 한글 낱자(ㆍ)를 쓴다. 규정 자료 63종은 모두 가운뎃점(·)
# 이므로 견줄 때 이것을 맞춘다. 따옴표 모양도 genhwpml.bare 가 같게 보아 준다.
MIDDOT = {"ㆍ": "·"}
fix = lambda s: "".join(MIDDOT.get(c, c) for c in (s or ""))

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def hwpx_lines(path, tables=None):
    """HWPX 의 문단을 차례대로

    표는 칸마다 <p> 가 또 들어 있어, 문단을 모두 훑으면 표가 글줄로 풀어져 본문에
    두 번 박힌다. 그러므로 섹션 바로 아래 문단만 보고, 표가 든 문단은 글자 대신
    자리표시(<img id="…">)를 남긴다. 표의 알맹이는 tables 에 담아 준다.
    """
    z = zipfile.ZipFile(path)
    out = []
    for n in sorted(x for x in z.namelist() if re.match(r"Contents/section\d+\.xml", x)):
        for p in list(ET.fromstring(z.read(n))):
            if p.tag != HP + "p":
                continue
            tbl = p.find(".//" + HP + "tbl")
            if tbl is not None:
                rows = [[("".join(x.text or "" for x in tc.iter(HP + "t"))).strip()
                         for tc in tr.iter(HP + "tc")]
                        for tr in tbl.iter(HP + "tr")]
                if tables is None:
                    continue                       # 표를 받을 곳이 없으면 버린다
                tid = f"t2v{len(tables) + 1}"
                tables.append({"id": tid, "rows": rows})
                out.append(f'<img id="{tid}"></img>')
                continue
            t = "".join(x.text or "" for x in p.iter(HP + "t")).strip()
            if t:
                out.append(t)
    return out


# ══════════════════════════════════════════════════════════════
#  용어 정비 — 초안(v1·v2)의 조문·별표 글에만 적용한다
#  기준(현행)은 법제처 원문 그대로 두어야 하므로 손대지 아니한다.
#  긴 말부터 바꾼다 (수치표면모델 → 수치표면모형 이 표면모델 규칙보다 앞선다).
#  '모델링' 처럼 뒤에 말이 이어지는 것은 건드리지 않는다.
# ══════════════════════════════════════════════════════════════
def reason(now=None, problem=None, ground=None, why=None, what=None):
    """작업규정 편집기(개편안 초안)와 같은 다섯 마디로 변경 사유를 적는다

      현행 규정 → 현행의 문제 → 관련 근거 → 개정 사유 → 개정 내용

    마디 이름과 빈 줄 자리를 draft2025 와 똑같이 맞춘다. 사람이 두 편집기를
    오갈 때 같은 꼴로 읽히고, 개정 전후 비교표의 '변경 사유' 칸도 같아진다.
    """
    L = ["[변경 사유]", ""]
    for head, items in (("현행 규정", now), ("현행의 문제", problem),
                        ("관련 근거", ground), ("개정 사유", why), ("개정 내용", what)):
        L.append(f"○ {head}:")
        L.append("")
        for x in (items or ["확인된 내용이 없다"]):
            L.append(f"* {x}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


TERMS = [
    # 'UAV LiDAR' 는 한 낱말로 본다 — UAV 를 먼저 바꾸면 '무인비행장치 LiDAR' 가 되므로
    # 그 꼴도 함께 받는다. 반드시 UAV 규칙보다 앞에 둔다.
    (re.compile(r"UAV\s*LiDAR"), "무인비행장치 레이저측량"),
    (re.compile(r"무인비행장치\s*LiDAR"), "무인비행장치 레이저측량"),
    # 우리말로 적고 원어를 괄호로 단 꼴 — 통째로 갈음한다. 낱낱이 바꾸면
    # 「라이다(레이저측량)」 처럼 우스운 것이 남으므로 아래 규칙보다 앞에 둔다.
    (re.compile(r"라이다\s*[(（]\s*Li[Dd][Aa][Rr]\s*[)）]"), "레이저측량"),
    # 홀로 쓰인 LiDAR·라이다 도 우리말로 — 위 규칙들 뒤에 두어야 'UAV LiDAR' 가
    # 먼저 걸린다. 대소문자를 가리지 아니한다 (원문에 'Lidar' 로 적힌 데가 있다).
    (re.compile(r"Li[Dd][Aa][Rr]"), "레이저측량"),
    (re.compile(r"라이다"), "레이저측량"),
    (re.compile(r"수치표면모델"), "수치표면모형"),
    (re.compile(r"수치표고모델"), "수치표고모형"),
    (re.compile(r"표면모델(?!링)"), "표면모형"),
    (re.compile(r"표고모델(?!링)"), "표고모형"),
    (re.compile(r"드론"), "무인비행장치"),
    (re.compile(r"(?<![A-Za-z])UAV(?![A-Za-z])"), "무인비행장치"),
]

TERM_REASON = reason(
    now=["말·표기가 규정마다 다르게 쓰이고 있다"],
    problem=["같은 것을 드론·UAV·무인비행장치로, 모델·모형으로 섞어 불러 성과 판정과"
             " 인용에서 다툼이 생길 수 있다"],
    ground=["연구진 용어 정비 (2026) — 드론·UAV → 무인비행장치, UAV LiDAR → 무인비행장치"
            " 레이저측량, LiDAR → 레이저측량,"
            " 수치표면모델·수치표고모델 → 수치표면모형·수치표고모형",
            "상위 법령과 다른 고시가 쓰는 말에 맞춘다"],
    why=["규정 안에서 한 가지 말로 통일하여 읽는 사람이 헷갈리지 않게 한다"],
    what=["드론·UAV → 무인비행장치", "UAV LiDAR → 무인비행장치 레이저측량",
          "LiDAR → 레이저측량",
          "수치표면모델·수치표고모델 → 수치표면모형·수치표고모형",
          "뜻은 그대로이고 말만 바꾸었다"],
)


# 인용된 규정 이름이 지금 이름과 다른 것 — 「…」 안에서만 고친다
# (gencites.py 가 library.json 에 적어 둔 nameAlias 와 같은 갈래의 일이다)
REFNAMES = {
    "항공사진측량 작업규정": "항공사진측량 작업 및 성과에 관한 규정",
    "영상지도제작에 관한 작업규정": "정사영상 제작 작업 및 성과에 관한 규정",
    "영상지도 제작에 관한 작업규정": "정사영상 제작 작업 및 성과에 관한 규정",
    "항공레이저측량 작업규정": "수치표고모형의 구축 및 관리 등에 관한 규정",
    "수치지형도 작성 작업규정": "수치지형도 작성 작업 및 성과에 관한 규정",
}
RE_CITE = re.compile(r"([「『])([^」』]{2,60})([」』])")

REF_REASON = reason(
    now=["인용한 규정 이름이 그 규정이 바뀌기 전 이름이다"],
    problem=["지금 없는 이름을 인용하고 있어, 어느 규정을 따라야 하는지 찾아가기 어렵다"],
    ground=["「항공사진측량 작업규정」 → 「항공사진측량 작업 및 성과에 관한 규정」"
            " (국토지리정보원고시 제2022-3487호)",
            "「영상지도 제작에 관한 작업규정」 → 「정사영상 제작 작업 및 성과에 관한 규정」"
            " (고시 제2022-3487호)",
            "「항공레이저측량 작업규정」 → 「수치표고모형의 구축 및 관리 등에 관한 규정」"
            " (고시 제2026-283호)",
            "「수치지형도 작성 작업규정」 → 「수치지형도 작성 작업 및 성과에 관한 규정」"
            " (고시 제2026-2524호)"],
    why=["인용이 끊기지 않도록 지금 이름으로 맞춘다 — 참조규정 창에서 바로 열린다"],
    what=["「…」 안의 규정 이름만 고쳤고 조문 내용은 그대로다"],
)


TERM_LINE = ("* 함께 용어를 손질했다 — 드론·UAV → 무인비행장치,"
             " UAV LiDAR → 무인비행장치 레이저측량, LiDAR → 레이저측량,"
             " 수치표면모델·수치표고모델 → 수치표면모형·수치표고모형")
REF_LINE = "* 함께 인용한 규정 이름을 지금 이름으로 바로잡았다"


def fix_refs(tree, mark_kept=True):
    """참조규정 인용 이름을 지금 이름으로 — 무엇을 고쳤는지 세어 돌려준다"""
    hit = {}

    def one(m):
        new = REFNAMES.get(m.group(2))
        if not new:
            return m.group(0)
        hit[m.group(2)] = hit.get(m.group(2), 0) + 1
        return m.group(1) + new + m.group(3)

    def walk(ns):
        for n in ns:
            b0 = n.get("body") or ""
            b1 = RE_CITE.sub(one, b0)
            if b1 != b0:
                # 손질이 있었으면 상태와 상관없이 '용어' 로 표시한다 — 개정으로 이미
                # 고쳐지는 조문이라도 [용어] 골라 보기에서 함께 걸러 볼 수 있게 한다
                n["changeKind"] = "용어"
                if mark_kept and n.get("status") == "유지":
                    if not n.get("wasBody"):
                        n["wasBody"] = b0
                    n["status"] = "수정"
                    n["reason"] = (n.get("reason") or "") + REF_REASON
                else:
                    n["reason"] = (n.get("reason") or "").rstrip() + chr(10) + REF_LINE + chr(10)
                n["body"] = b1
            walk(n.get("children") or [])

    walk(tree)
    return hit


def term(s):
    out = s or ""
    for pat, to in TERMS:
        out = pat.sub(to, out)
    # 바꾼 말이 잇달아 겹치는 것을 막는다 (무인비행장치 무인비행장치 …)
    out = re.sub(r"무인비행장치(\s*무인비행장치)+", "무인비행장치", out)
    out = re.sub(r"레이저측량(\s*레이저측량)+", "레이저측량", out)
    return out


def apply_terms(tree, mark_kept):
    """조문·별표의 제목과 본문에 용어 정비를 적용한다

    말만 바뀐 조문은 '수정 · 용어' 로 표시해 두어, 편집기의 [용어] 골라 보기에서
    공청회에서 다툴 것과 다투지 아니할 것을 가를 수 있게 한다.
    """
    hit = 0

    def walk(ns):
        nonlocal hit
        for n in ns:
            # 사유 글에도 같은 말을 쓴다. 제목·본문만 정비하고 사유를 그냥 두었더니
            # 조문은 「무인비행장치 레이저측량」인데 그 조의 사유에는 「UAV LiDAR」가
            # 그대로 남아 여덟 곳에서 어긋났다. TERM_REASON 을 붙이기 전에 손본다
            # — 그 글은 「UAV LiDAR → 무인비행장치 레이저측량」처럼 바꾼 내력을
            # 적은 것이라, 거기까지 바꾸면 무엇을 바꾸었는지 알 수 없게 된다.
            r0 = n.get("reason") or ""
            r1 = term(r0)
            if r1 != r0:
                n["reason"] = r1
            t0, b0 = n.get("title") or "", n.get("body") or ""
            t1, b1 = term(t0), term(b0)
            if t1 != t0 or b1 != b0:
                hit += 1
                # 상태와 별개로 표시한다 (신설·수정 조문의 용어 손질도 걸러 보인다)
                n["changeKind"] = "용어"
                if mark_kept and n.get("status") == "유지":
                    if not n.get("wasBody"):
                        n["wasBody"] = b0
                    n["status"] = "수정"
                    n["reason"] = (n.get("reason") or "") + TERM_REASON
                else:
                    n["reason"] = (n.get("reason") or "").rstrip() + chr(10) + TERM_LINE + chr(10)
                n["title"], n["body"] = t1, b1
            walk(n.get("children") or [])

    walk(tree)
    return hit


# ══════════════════════════════════════════════════════════════
#  v1 — 2024년 연구성과 개정(안)
#  PDF 부록 1 의 신구대조표 여섯 마디. 개정안 칸의 '------' 는 현행 글자를
#  그대로 둔다는 뜻이므로, 현행 조문에서 바뀌는 말만 갈아 끼운다.
#  expect 는 갈아 끼우기 전에 현행이 우리가 아는 그 글월인지 보는 자물쇠다.
# ══════════════════════════════════════════════════════════════
AMEND2024 = [
    {
        "jo": "제8조", "page": 3, "item": "2) 대공표지의 형상 부분",
        "expect": "대공표지의 설치는 「항공사진측량 작업규정」을 따른다.",
        "body": "대공표지의 설치는 「항공사진측량 작업 및 성과에 관한 규정」이나 별표 8을 따른다."
                " 다만, 측량목적 달성에 지장이 없는 경우 측량시행자와 협의하여 형태 및"
                " 설치방법을 다르게 할 수 있다.",
                "found": [
            "별표 8(무인비행장치용 대공표지의 형상) 초안 — 별형·X형·+형·O형 등, 한 변 또는 지름이 촬영 영상에서 15화소 이상, 짙은 색과 밝은 색을 조합",
        ],
        "what": ["준용 규정에 별표 8(무인비행장치용 대공표지의 형상)을 나란히 둔다",
                 "인용 규정 이름을 지금 이름(「항공사진측량 작업 및 성과에 관한 규정」)으로 고친다"],
        "why": [
            "「항공사진측량 작업 및 성과에 관한 규정」에 제시되어 있는 대공표지의 형상은"
            " 무인비행장치를 이용하여 취득한 고해상도 영상에서 충분한 포인팅 정확도를"
            " 기대하기 어려운 경우가 많음",
            "일본과 미국의 관련 규정에서도 무인비행장치에 적합한 대공표지 형상의 기준을"
            " 별도로 제시함",
        ],
    },
    {
        "jo": "제9조", "page": 4, "item": "3) 비행 중 실시간 측위 성과의 활용 부분",
        "expect": "③ 지상기준점의 수량은 1㎢당 9점 이상을 원칙으로 한다.",
        "sub": ("③ 지상기준점의 수량은 1㎢당 9점 이상을 원칙으로 한다.",
                "③ 지상기준점의 수량은 다음 호에 따른다.\n"
                "1. 지상기준점의 수량은 1㎢당 9점 이상을 원칙으로 한다.\n"
                "2. 촬영 중 수집된 GNSS 데이터를 처리한 PPK 측위 결과를 함께 사용하는 경우"
                " 지상기준점의 수량은 1㎢당 4점 이상으로 조정할 수 있다.\n"
                "3. GNSS PPK 측위 결과를 함께 사용할 수 있는 경우와 방법 등은 <별표 9>에 의한다."),
                "found": [
            "<표 3> PPK 성과와 GCP 기반 항공삼각측량 성과의 정확도 평가 — PPK+GCP 4점 10cm 이내 · PPK+GCP 1~3점 24cm 이내 · PPK 단독 32cm 이내",
            "<그림 1> 지오리퍼런싱 방식(PPK · GCP 4점 · GCP 9점)에 따른 수평 RMSE 분포 (Tomastik 등, 2019)",
        ],
        "what": ["PPK 측위 결과를 함께 쓰면 지상기준점을 1㎢당 4점 이상으로 줄일 수 있게 한다",
                 "쓸 수 있는 경우와 방법은 별표 9 로 따로 정한다"],
        "why": [
            "GNSS PPK 성과를 쓰되 GCP 의 수량을 바꾸어 가며 항공삼각측량을 수행하고 정확도의"
            " 변화를 분석한 결과, 적정 수량의 GCP 와 GNSS PPK 성과를 함께 쓰면 충분한 정확도의"
            " 항공삼각측량 성과를 얻을 수 있음을 확인함"
            " (PPK+GCP 4점 10cm 이내 · PPK+GCP 1~3점 24cm 이내 · PPK 단독 32cm 이내)",
            "여러 해외 연구사례에서도 PPK 성과만 쓰거나 PPK 와 GCP 를 혼용한 경우 모두 충분한"
            " 정확도가 확보된다는 사실을 확인할 수 있음",
        ],
    },
    {
        "jo": "제10조", "page": 6, "item": "4) 표고기준점 측량 부분",
        "expect": "2. 표고기준점측량은 「공공측량 작업규정」의 공공수준점측량 방법을 준용함을 원칙으로 한다.",
        "sub": ("2. 표고기준점측량은 「공공측량 작업규정」의 공공수준점측량 방법을 준용함을 원칙으로 한다.",
                "2. 표고기준점측량은 「공공측량 작업규정」의 공공수준점측량 방법이나 GNSS 높이측량"
                " 방법 또는 「항공사진측량 작업 및 성과에 관한 규정」의 지상기준점측량 방법을"
                " 준용함을 원칙으로 한다."),
                "found": [
            "<표 4> GNSS 간접수준측량 방법별 오차량 — 검사점·지상기준점 29점의 직접수준측량 성과와 견줌. GNSS 정적 측위 -0.001~0.051m · 네트워크 RTK 측위 -0.056~0.039m (산지 8점 포함)",
            "<표 5> 미국 ASPRS 표준의 지상기준점 정확도 기준 — 폐합 디지털레벨 수직 5mm · Real-Time Network 10/16/19mm · Real-Time PPP 15/24/28mm · RTK 20/32/38mm",
        ],
        "what": ["표고기준점측량에 GNSS 높이측량과 항공사진측량 규정의 지상기준점측량 방법을 더한다"],
        "why": [
            "29개의 검사점과 지상기준점에 대한 직접수준측량 성과를 기준으로 GNSS 에 의한"
            " 간접수준측량(정적 측위·네트워크 RTK 측위) 결과를 평가한 결과가 매우 양호하였음",
            "일본과 미국의 무인비행장치 측량 관련 규정에서도 표고기준점의 높이값 결정에"
            " 간접수준측량 성과를 쓸 수 있도록 허용함 (미국 ASPRS 표준의 지상기준점 정확도 기준)",
            "국내 「항공사진측량 및 성과관리에 관한 규정」에서도 간접수준측량 성과를 허용함",
        ],
    },
    {
        "jo": "제13조", "page": 1, "item": "1) 지상분해능과 촬영고도 부분",
        "expect": "「항공사진측량 작업규정」의 축척별 지상표본거리 이내 이어야 한다.",
        "subs": [
            ("「항공사진측량 작업규정」의 축척별 지상표본거리 이내 이어야 한다.",
             "「항공사진측량 작업규정」의 축척별 지상표본거리 이내 이어야 하며, 1/500을"
             " 초과하는 축척의 경우에는 다음 표를 따른다.\n<img id=\"t13gsd\"></img>"),
            ("촬영 소요시간, 사진 매수 등의 정보를 확인한다.",
             "촬영 소요시간, 사진 매수 등의 정보를 확인하여야 하며, 촬영고도의 경우 다음 조건을"
             " 충족하여야 한다.\n촬영고도 ≤ 지상표본거리 × 초점거리 ÷ 디지털카메라 화소의 크기"),
        ],
                "found": [
            "<표 1> 일본 작업규정(공공측량작업규정준칙)의 지상표본거리 기준 — 지도정보레벨 250 → 0.02m 이내 · 500 → 0.03m 이내",
            "<표 2> 무인비행장치 영상의 지상표본거리에 대한 미국 ASPRS 권장안 — RMSEH 2.5cm → 화소 1.25~2.5cm(1:100) · 5.0 → 2.5~5.0(1:200) · 7.5 → 3.8~7.5(1:300) · 10.0 → 5.0~10.0(1:400) · 12.5 → 6.3~12.5(1:500)",
            "개정(안)이 새로 두는 표 — 도화축척 1/125~1/150(항공사진축척 1/625~1/900) 2cm 이내 · 1/250~1/300(1/1,250~1/1,800) 4cm 이내",
        ],
        "what": ["1/500을 초과하는 대축척의 지상표본거리 기준표를 제3항에 새로 넣는다",
                 "제4항에 촬영고도 산정식을 넣어 계획 단계에서 점검하게 한다"],
        "why": [
            "무인비행장치로 확보 가능한 지상표본거리가 항공사진측량의 경우보다 정밀할 수 있기"
            " 때문에 1/500 축척을 초과하는 대축척에 대한 지침의 제시가 필요함",
            "일본 국토지리원의 「공공측량작업규정준칙」과 미국 사진측량학회(ASPRS)의 표준에는"
            " 1/500 축척을 초과하는 작업에 대한 지상표본거리 지침이 제시되어 있음"
            " (일본 지도정보레벨 250 → 0.02m 이내 · 500 → 0.03m 이내)",
            "일본 작업규정은 목표 지상표본거리를 기준으로 촬영고도를 점검할 수 있는 기준을"
            " 제공하여 작업의 혼란을 막고 이해를 돕고 있음",
        ],
    },
    {
        "jo": "제32조", "page": 8, "item": "5) 지형지물의 수치묘사 부분",
        "expect": "③ 벡터화에 의한 지형·지물의 묘사의 허용범위는 「항공사진측량 작업규정」의"
                  " 평면위치에 대한 기준을 준용함을 원칙으로 한다.",
        "sub": ("③ 벡터화에 의한 지형·지물의 묘사의 허용범위는 「항공사진측량 작업규정」의"
                " 평면위치에 대한 기준을 준용함을 원칙으로 한다.",
                "③ 벡터화에 의한 지형·지물의 묘사의 품질과 정확도를 확보하기 위하여 다음 각 호의"
                " 사항을 따라야 한다.\n"
                "1. 묘사 결과의 평면위치 정확도는 「항공사진측량 작업 및 성과에 관한 규정」의"
                " 평면위치에 대한 기준을 준용함을 원칙으로 한다.\n"
                "2. 기복변위로 인한 지형지물 묘사 누락 및 과대 평면위치 오차 발생이 없어야 한다."),
                "found": [
            "시범 구축 작업에서 확인한 것 — 기복변위가 소거되지 못한 정사영상에서는 건물에 가려진 도로의 형상을 묘사하기 어렵고, 경계 묘사에도 과대한 수평위치오차가 낌",
        ],
        "what": ["허용범위 한 줄을 각 호로 나누어 기복변위로 인한 묘사 누락까지 막는다"],
        "why": [
            "시범 구축 작업에서 기복변위가 제대로 소거되지 못한 정사영상을 쓰는 경우 건물에"
            " 가려진 도로와 같이 그 형상을 제대로 묘사하기 어려운 경우가 많았음",
            "기복변위가 제대로 소거되지 못한 지형지물의 경계 묘사 결과에도 과대한 수평위치오차가"
            " 끼어드는 경우가 많았음",
        ],
        "note": "개정(안) 문서는 이 조문을 '제43조' 로 적었으나 현행에서 벡터화 묘사는 제32조다."
                " 조 번호는 현행에 맞추었다.",
    },
    {
        "jo": "제38조", "page": 9, "item": "6) 중간 및 최종 성과물의 정확도 부분",
        "expect": "③ 종·횡단면도는 「공공측량 작업규정」제73조, 제74조에 의한 정확도를 유지하여야 한다.",
        "append": "④ 무인비행장치 측량 성과의 품질관리를 위하여 별표 10에 따라 공정별·최종 성과물의"
                  " 품질관리를 수행하여야 한다.",
                "found": [
            "별표 10(품질관리기준) 초안의 칸 구성 — 작업공정 · 대상데이터 · 품질요소 · 검증항목(항목명 · 세부검증사항) · 검증방법(구분 · 방법) · 검증기준 · 표본추출법",
            "검증기준 보기 — 기준국 거리 50km 이내(도서지역 70km) 전수 · 촬영코스 수평이탈 20% · 수직이탈 10% 이내 자동평가 전수 · 카메라 검정 적합/부적합 전수",
        ],
        "what": ["품질관리 조문에 제4항을 신설하여 별표 10(품질관리기준)을 따르게 한다"],
        "why": [
            "현행 규정에는 중간 성과물에 대한 정확도 규정만 흩어져 있어, 최종 성과물의 정확도를"
            " 확인하려면 별도의 규정을 찾아보아야 하는 불편이 있음",
            "중간 및 최종 성과물의 품질과 정확도 규정을 별표로 일목요연하게 정리하면 측량"
            " 수행자와 시행자 모두의 편의가 늘고 오류와 혼란을 막을 수 있음",
        ],
    },
]

# 1/500 을 초과하는 축척의 지상표본거리 (제13조제3항 표)
T13 = [["도화 축척", "항공사진 축척", "지상표본거리"],
       ["1/125 ~ 1/150", "1/625 ~ 1/900", "2cm 이내"],
       ["1/250 ~ 1/300", "1/1,250 ~ 1/1,800", "4cm 이내"]]

ANNEX2024 = [
    {"no": "8", "title": "무인비행장치용 대공표지의 형상", "pages": [3],
     "body": "가. 다음 예시와 같이 별형, X형, +형, O형으로 구성하거나 영상에서 대표지점을"
             " 포인팅하기 용이한 다양한 형태를 적용할 수 있다.\n"
             "나. 대공표지의 한 변의 길이 또는 원형의 지름은, 촬영 영상에서 15화소 이상으로"
             " 나타나도록 제작되어야 한다.\n"
             "다. 표지의 색상은 짙은 색(검정색, 남색 등)과 밝은 색(흰색, 노란색 등)을 조합하여"
             " 배경과 대비되고 용이하게 식별될 수 있도록 해야 한다.",
     "why": "제8조(대공표지) 개정에 따라 새로 다는 별표. 형상 예시 그림은 미리보기에 있다."},
    {"no": "9", "title": "GNSS PPK 측위 결과의 활용", "pages": [4, 5],
     "body": "가. PPK 측위법의 사용이 가능한 경우\n"
             "· 인력의 접근이 어려워 지상기준점의 설치가 용이하지 않은 북한 접경지역, 하천 등이"
             " 포함된 영역을 대상으로 무인비행장치 측량을 시행하는 경우\n"
             "· 재난 대응, 피해 조사 등 신속한 공간정보 취득이 필요한 비상 상황\n"
             "· 제작되는 수치지도의 축척은 1/1,000 이하이어야 함\n"
             "나. PPK 측위용 GNSS 수신기의 성능\n"
             "· 「항공사진측량 작업 및 성과에 관한 규정」 제12조에 규정된 GNSS 와 동등 이상의 성능\n"
             "· 카메라 셔터 타이밍과 GNSS 시간 동기화를 할 수 있는 구조이어야 함\n"
             "다. PPK 용 데이터의 수집과 처리\n"
             "· GNSS 기준국은 작업 반경 50㎞ 이내의 GNSS 상시관측소를 이용\n"
             "· 도서지역 등 부득이한 경우 작업 반경 70㎞ 이내의 GNSS 상시관측소를 이용할 수 있음\n"
             "· 상기한 조건의 상시관측소가 없는 경우 작업반경 내에 GNSS 기준국을 직접 설치\n"
             "· ① 관측 데이터 입력 → ② 기준국 보정 적용 → ③ 카메라 위치 추출(CSV) 순으로 처리",
     "why": "제9조(지상기준점의 배치) 제3항제3호가 부르는 별표."},
    {"no": "10", "title": "품질관리기준", "pages": [9, 10],
     "body": "작업공정·대상데이터·품질요소·검증항목(항목명·세부검증사항)·검증방법(구분·방법)·"
             "검증기준·표본추출법의 여덟 칸으로 짜인 큰 표다. 촬영(카메라 검정·촬영기록부·"
             "기준국 위치·코스 유지·중복도), 항공영상, 항공삼각측량성과, 수치표고모델, 정사영상,"
             " 수치도화·벡터화 성과까지 공정별로 검증기준과 표본추출법을 정한다.\n"
             "표 전체는 미리보기(개정(안) 부록 9~10쪽)에서 확인한다. 서식으로 옮길 때 칸마다"
             " 값을 다시 확인해야 한다.",
     "why": "제38조(품질관리) 제4항 신설에 따라 새로 다는 별표."},
]


def reason_2024(a, cur_body=""):
    """v1 — 2024년 연구성과 개정(안) 한 마디"""
    head = (cur_body or "").split("\n")[0]
    src = (f"2024.연구성과.무인비행장치 측량 작업규정.개정안_25.07.18.pdf 부록 1 {a.get('page')}쪽"
           + (f" — {a['item']}" if a.get("item") else ""))
    return reason(
        now=[f"현행 {a['jo']}" + (f" — {head[:70]}…" if head else "")],
        problem=a.get("why", []),
        ground=(a.get("found") or []) + [f"출처 — {src}"],
        why=["2024년 연구(기본측량 성과 적용을 위한 무인비행장치 활용 연구)가 낸 개정(안)을"
             " 그대로 옮긴다"]
            + ([a["note"]] if a.get("note") else []),
        what=a.get("what", []),
    )


def swap(body, old, new, jo):
    """빈칸이 다를 수 있으므로 빈칸을 무시하고 찾아 바꾼다"""
    if old in body:
        return body.replace(old, new, 1)
    pat = re.compile(r"\s*".join(map(re.escape, old.replace(" ", ""))))
    body, cnt = pat.subn(lambda m: new, body, count=1)
    if not cnt:
        raise SystemExit(f"  [멈춤] {jo} 에서 바꿀 자리를 찾지 못했습니다: {old[:40]}…")
    return body


def build_v1(base, out_dir, dry):
    tree = copy.deepcopy(base["tree"])
    annex_tree = copy.deepcopy(base.get("annexTree") or [])
    for n in H.flat(tree, "조"):
        n["status"], n["reason"], n["history"], n["sourceRef"] = "유지", "", [], None
    for g in annex_tree:
        for n in g.get("children") or []:
            # 별표 가지의 본문은 내려받기 주소일 뿐 — 기준 판처럼 비워 둔다
            if re.match(r"^\s*(HWP|PDF)\s+https?:", n.get("body") or "", re.I):
                n["body"] = ""
            n["status"], n["reason"] = "유지", ""

    by = {n["legacyNo"]: n for n in H.flat(tree, "조")}
    fixed = []
    for a in AMEND2024:
        n = by.get(a["jo"])
        if not n:
            raise SystemExit(f"  [멈춤] 현행에 {a['jo']} 가 없습니다.")
        if a["expect"].replace(" ", "") not in n["body"].replace(" ", ""):
            raise SystemExit(f"  [멈춤] {a['jo']} 의 현행 글월이 개정(안)이 적은 것과 다릅니다.\n"
                             f"        찾던 글: {a['expect'][:50]}…")
        body = n["body"]
        for old, new in ([a["sub"]] if a.get("sub") else a.get("subs", [])):
            body = swap(body, old, new, a["jo"])
        if a.get("body"):
            body = a["body"]
        if a.get("append"):
            body = body.rstrip() + "\n" + a["append"]
        # 현행 본문을 함께 담아 두면 편집기가 바뀐 말을 푸르게 짚어 보인다
        # (ui/detail.js 의 _bodyDiff — 개편안 초안도 같은 방식이다)
        n["wasBody"] = n["body"]
        n["body"], n["status"], n["reason"] = body, "수정", reason_2024(a, n["wasBody"])
        fixed.append(a["jo"])

    grp = annex_tree[0]
    added = []
    for a in ANNEX2024:
        grp["children"].append({
            "id": f"{DRAFT_ID}-anx-별표-{a['no']}", "level": "조", "no": 0, "branch": 0,
            "title": a["title"], "body": a["body"], "status": "신설", "legacyNo": "",
            "reason": reason(
                now=["없음 — 신설 별표"],
                problem=["현행에는 이 별표가 없어 조문만으로는 판정 기준이 서지 않는다"],
                ground=[a["body"].splitlines()[0],
                        "출처 — 2024.연구성과.무인비행장치 측량 작업규정.개정안_25.07.18.pdf"
                        " 부록 1 " + "·".join(str(p) for p in a["pages"]) + "쪽"],
                why=[a["why"]],
                what=[f"별표 {a['no']}({a['title']})를 새로 둔다",
                      "서식·표는 근거 자료의 미리보기를 보고 옮겨야 한다"],
            ),
            "sourceRef": None, "history": [],
            "annexRef": {"gubun": "별표", "no": a["no"], "hwp": "", "pdf": "",
                         "source": "2024년 연구성과 개정(안)"},
            "children": [], "collapsed": False,
        })
        added.append(f"별표 {a['no']}")
    grp["title"] = f"별표 ({len(grp['children'])}건)"

    if not dry:
        # 조문 본문의 표는 기준 규정의 자리에 둔다 — 편집기가 본문의 <img id> 를
        # 기준 규정(baseRegId)의 색인에서 찾기 때문이다 (개편안 초안도 같은 방식이다)
        make_table_v1(os.path.join(DATA, "objects", BASE))
        make_previews_v1()
    return tree + annex_tree, fixed, added


def make_table_v1(out_dir):
    """제13조제3항의 지상표본거리 표 — 본문의 <img id="t13gsd"> 자리에 그려진다

    조문 본문의 표는 초안 전용 자리가 아니라 기준 규정(data/objects/reg12)에 둔다.
    개편안 초안(draft2025)도 표를 reg01 자리에 두고 같은 방식으로 그린다.
    """
    os.makedirs(out_dir, exist_ok=True)
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="t13gsd" article="제13조제3항 1/500을 초과하는 축척의 지상표본거리"'
         f' rows="{len(T13)}" cols="3" source="2024년 연구성과 개정(안)">']
    for ri, row in enumerate(T13):
        L.append("  <row>")
        for ci, c in enumerate(row):
            L.append(f'    <cell col="{ci}" row="{ri}"{" header=\"1\"" if ri == 0 else ""}>{c}</cell>')
        L.append("  </row>")
    L.append("</table>")
    io.open(os.path.join(out_dir, "t13gsd.xml"), "w", encoding="utf-8").write("\n".join(L))

    ip = os.path.join(out_dir, "index.json")
    idx = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    idx["t13gsd"] = {"kind": "table", "article": "제13조제3항 지상표본거리",
                     "rows": len(T13), "cols": 3, "preview": " | ".join(T13[0])}
    with io.open(ip, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))


def make_previews_v1():
    """신설 별표의 근거 쪽(PDF)을 미리보기 그림으로"""
    import fitz
    d = os.path.join(DATA, "annex", DRAFT_ID)
    os.makedirs(d, exist_ok=True)
    doc = fitz.open(PDF2024)
    entry = {}
    for a in ANNEX2024:
        names = []
        for i, pno in enumerate(a["pages"], start=1):
            page = doc[pno - 1]
            zoom = A.WIDTH / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            fn = f"별표{a['no']}_{i}.webp"
            io.open(os.path.join(d, fn), "wb").write(
                pix.pil_tobytes(format="WEBP", quality=A.QUALITY, method=4))
            names.append(fn)
        entry[f"별표{a['no']}"] = names
    ip = os.path.join(DATA, "annex", "index.json")
    idx = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    idx[DRAFT_ID] = entry
    with io.open(ip, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))


# ══════════════════════════════════════════════════════════════
#  v2 — 2025년 연구결과 개정(안) (드론 다중센서)
# ══════════════════════════════════════════════════════════════
RANGE = re.compile(r"^제\s*(\d+)\s*조(?:부터\s*제\s*(\d+)\s*조(?:까지)?)?")


def why_tables(lines):
    """개정사유서의 '4. 조항별 개정 사유' 와 '5. 별표 개정 및 신설 사유' 를 읽는다

    HWPX 의 표는 칸이 문단 하나씩으로 나온다. 머리 칸을 만난 다음부터 세 칸
    (조항·개정 항목·개정 사유) 또는 네 칸(구분·별표명·조치·사유) 씩 끊어 읽는다.
    """
    jo, anx = [], []
    i = 0
    while i < len(lines):
        if lines[i] == "조항" and lines[i + 1:i + 3] == ["개정 항목", "개정 사유"]:
            i += 3
            while i + 2 < len(lines) and RANGE.match(lines[i]):
                jo.append((lines[i], lines[i + 1], lines[i + 2]))
                i += 3
            continue
        if lines[i] == "구분" and lines[i + 1:i + 4] == ["별표명", "조치", "개정 또는 신설 사유"]:
            i += 4
            while i + 3 < len(lines) and re.match(r"^별표\s*\d+$", lines[i]):
                anx.append((lines[i], lines[i + 1], lines[i + 2], lines[i + 3]))
                i += 4
            continue
        i += 1
    return jo, anx


def annex_bodies(lines):
    """별표수정(안) — [별표 N] 제목 아래의 글을 모은다"""
    out, cur = {}, None
    for l in lines:
        m = re.match(r"^\[별표\s*(\d+)\]\s*(.*)$", l)
        if m:
            cur = m.group(1)
            out[cur] = {"title": m.group(2).strip(), "lines": []}
            continue
        if cur:
            out[cur]["lines"].append(l)
    return out


# 개정사유서 '3. 주요 개정 내용' 의 분야를 조문 범위에 이어 둔다 (관련 근거에 싣는다)
MAIN = {
    "용어": "주요 개정 내용 — 용어체계 정비: 무인비행장치 다중센서 측량,"
            " LiDAR 자료, GNSS/INS 자료, RTK/PPK 보정, 조준선 검정, 블록 조정, 점군분류,"
            " 다중센서 정합, 표준 포맷 등 신규·보완 용어를 정의",
    "장비": "주요 개정 내용 — 장비 및 소프트웨어 기준 보완: 광학카메라,"
            " LiDAR 센서, GNSS/INS 장치와 처리 소프트웨어가 갖출 기능·성능요건을 반영",
    "순서": "주요 개정 내용 — 작업순서 정비: 작업계획·장비점검·기준점 측량부터"
            " 품질관리·납품까지 전 공정 흐름을 체계화",
    "기준점": "주요 개정 내용 — 기준점 및 검사점 운용 보완: 직접지오리퍼런싱"
              " 적용 시 지상기준점 수량 조정을 인정하되, 검사점의 독립성과 성과품별 정확도"
              " 검증 기준을 명확히 함",
    "라이다": "주요 개정 내용 — LiDAR 처리 기준 신설: 조준선 검정, 시간동기,"
              " 궤적자료, 좌표변환, 블록 조정, 점군분류, 수치지면자료 제작, DSM/DTM/DEM"
              " 제작과 검수 항목을 반영",
    "정합": "주요 개정 내용 — 다중센서 정합 기준 신설: 정사영상, DSM, DTM,"
            " 점군, 기준점·검사점으로 평면 및 수직 위치 차이를 검토하도록 함",
    "성과품": "주요 개정 내용 — 성과품 및 품질관리 기준 보완: 표준 포맷,"
              " 메타데이터, 품질평가 보고서, 처리로그, 오류정정·보완조치, 정리점검 기준을 정비",
}


def mainkey(no):
    if no <= 2:
        return "용어"
    if no == 6:
        return "장비"
    if no == 7:
        return "순서"
    if 8 <= no <= 12:
        return "기준점"
    if 20 <= no <= 25:
        return "라이다"
    if 26 <= no <= 29:
        return "정합"
    if 39 <= no <= 41:
        return "성과품"
    return ""


# ── 별표를 부르는 조문 ────────────────────────────────────
# 개정(안)은 별표 15건을 두었으나 본문이 별표 2~15 를 부르지 않아, 어느 조문의
# 서식인지 규정만으로는 알 수 없었다 (편집기 검증의 '인용되지 않는 별표' 경고).
# 현행 규정이 하던 방식대로 성과 정리 호 뒤에 <별표 N> 를 달고, 그 자리가 없는
# 신설 별표는 그 별표를 만들어 내는 공정 조문에 항을 하나 더 둔다.
CITE_HO = [          # (조, 호가 담은 말, 별표)
    (12, "지상기준점 및 검사점 성과표", "2"),
    (16, "촬영기록부 및 레이저측량 취득기록부", "3"),
    (16, "촬영 코스 검사표 및 레이저측량 데이터 취득 검사표", "4"),
    (25, "수치표고모형 검사표", "5"),
    (25, "수치표고모형 오류정정표", "6"),
    (25, "블록 조정 결과보고서", "10"),
    (25, "점군밀도 및 결측률 검토 결과", "11"),
    (29, "정사영상 검사표", "7"),
]
CITE_HANG = [        # (조, 새로 다는 항)
    (20, "GNSS/INS 후처리 결과는 <별표 8>의 품질검사표에 따라 정리한다."),
    (21, "조준선 검정 결과는 <별표 9>의 성과표에 따라 정리한다."),
    (22, "점군분류 성과와 그 정확도는 <별표 12>의 평가표에 따라 정리한다."),
    (39, "성과품에는 <별표 13>의 다중센서 성과 메타데이터 필수 항목을 갖춘 메타데이터를"
         " 함께 제출하여야 한다."),
    (39, "성과품의 납품 폴더구조는 <별표 14>에 따른다."),
    (40, "품질 부적합의 판정과 보완조치는 <별표 15>에 따른다."),
]
HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"

CITE_LINE = "* 개정(안)이 별표만 두고 조문에서 부르지 않아 <별표 N> 인용을 달았다"


def add_annex_cites(tree):
    """조문에 <별표 N> 인용을 단다 — 몇 곳을 달았는지 돌려준다"""
    jo = {n["no"]: n for n in H.flat(tree, "조") if not n.get("annexRef")}
    done = 0

    def mark(n):
        r = (n.get("reason") or "").rstrip()
        if CITE_LINE not in r:
            n["reason"] = r + chr(10) + CITE_LINE + chr(10)

    for no, needle, anx in CITE_HO:
        n = jo.get(no)
        if not n:
            continue
        lines = (n["body"] or "").split(chr(10))
        for i, l in enumerate(lines):
            if needle in l and f"<별표 {anx}>" not in l:
                lines[i] = l.rstrip() + f" <별표 {anx}>"
                done += 1
                break
        else:
            print(f"        [못 찾음] 제{no}조 — {needle[:26]}…")
            continue
        n["body"] = chr(10).join(lines)
        mark(n)

    for no, sentence in CITE_HANG:
        n = jo.get(no)
        if not n or sentence in (n["body"] or ""):
            continue
        used = [c for c in (n["body"] or "") if c in HANG]
        nxt = HANG[len(set(used))] if used else "①"
        n["body"] = (n["body"] or "").rstrip() + chr(10) + nxt + " " + sentence
        done += 1
        mark(n)
    return done


def write_tables(tables):
    """개정(안) 본문의 표를 XML 로 — 자리는 기준 규정의 objects 폴더다

    편집기가 본문의 <img id> 를 기준 규정(baseRegId)의 색인에서 찾기 때문이다.
    현행에 이미 같은 표가 있으면(제13조 중복도) 그것을 그대로 가리킨다.
    """
    out_dir = os.path.join(DATA, "objects", BASE)
    os.makedirs(out_dir, exist_ok=True)
    ip = os.path.join(out_dir, "index.json")
    idx = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    for t in tables:
        rows = t["rows"]
        L = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<table id="{t["id"]}" article="2025년 연구결과 개정(안) 본문 표"'
             f' rows="{len(rows)}" cols="{max(len(r) for r in rows)}"'
             f' source="{HWPX_BODY}">']
        for ri, row in enumerate(rows):
            L.append("  <row>")
            for ci, c in enumerate(row):
                head = ' header="1"' if ri == 0 else ""
                L.append(f'    <cell col="{ci}" row="{ri}"{head}>'
                         + c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                         + "</cell>")
            L.append("  </row>")
        L.append("</table>")
        io.open(os.path.join(out_dir, t["id"] + ".xml"), "w", encoding="utf-8").write(
            chr(10).join(L))
        idx[t["id"]] = {"kind": "table", "article": "개정(안) 본문 표",
                        "rows": len(rows), "cols": max(len(r) for r in rows),
                        "preview": " | ".join(rows[0])}
    with io.open(ip, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    if tables:
        print(f"  v2 본문 표 {len(tables)}개를 XML 로 바꾸었다"
              f" ({' · '.join(t['id'] for t in tables)})")


PREV2 = "draftUav2"          # v2 별표 미리보기 자리 (v1 의 draftUav 와 번호가 겹친다)


def make_previews_v2():
    """별표수정(안).hwpx → PDF → 별표마다 미리보기 그림

    한/글이 깔린 자리에서만 된다. 한 쪽에 별표 하나씩 들어 있어 쪽을 그대로 쓴다.
    PDF 는 다시 만들지 않고 임시 폴더에 남겨 둔다.
    """
    import subprocess, tempfile
    import fitz
    src = os.path.abspath(os.path.join(F2025, HWPX_ANNEX))
    # tempfile.gettempdir() 는 다른 프로그램이 TMP 를 바꿔 놓으면 엉뚱한 곳을 가리킨다
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    pdf = os.path.join(tmp, "claude", "uav_annex2025.pdf")
    if not os.path.exists(pdf):
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        ps = (f"$h = New-Object -ComObject HWPFrame.HwpObject; "
              f"$h.RegisterModule('FilePathCheckDLL','FilePathCheckerModule') | Out-Null; "
              f"$null = $h.Open('{src}', '', 'forceopen:true'); "
              f"$null = $h.SaveAs('{pdf}', 'PDF', ''); $h.Quit()")
        try:
            exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                               "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
            subprocess.run([exe, "-NoProfile", "-Command", ps],
                           check=True, capture_output=True, timeout=300)
        except Exception as e:
            print(f"  [건너뜀] 별표 미리보기 — 한/글 변환에 실패했습니다 ({type(e).__name__})")
            return {}
    if not os.path.exists(pdf):
        print("  [건너뜀] 별표 미리보기 — PDF 가 만들어지지 않았습니다")
        return {}

    d = os.path.join(DATA, "annex", PREV2)
    os.makedirs(d, exist_ok=True)
    doc = fitz.open(pdf)
    entry, made = {}, 0
    for page in doc:
        m = re.search(r"\[별표\s*(\d+)\]", page.get_text())
        if not m:
            continue
        no = m.group(1)
        zoom = A.WIDTH / max(page.rect.width, 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        names = entry.setdefault(f"별표{no}", [])
        fn = f"별표{no}_{len(names) + 1}.webp"
        io.open(os.path.join(d, fn), "wb").write(
            pix.pil_tobytes(format="WEBP", quality=A.QUALITY, method=4))
        names.append(fn)
        made += 1
    ip = os.path.join(DATA, "annex", "index.json")
    idx = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    idx[PREV2] = entry
    with io.open(ip, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  v2 별표 미리보기 {made}쪽을 data/annex/{PREV2}/ 에 만들었다")
    return entry


def build_v2(base):
    tables = []
    body = hwpx_lines(os.path.join(F2025, HWPX_BODY), tables)
    # 고시 머리와 부칙은 뺀다 — 다른 규정 63종과 같은 구조로 둔다
    start = next(i for i, l in enumerate(body) if re.match(r"^제\s*1\s*장", l))
    end = next((i for i, l in enumerate(body) if re.match(r"^부\s*칙", l)), len(body))
    tree = G.build_tree(body[start:end])
    G.renumber(tree)

    # 편집기는 '현행에서 사라진 조문' 을 노드 id 로 가린다(core/validate.js). 새로 지은
    # 트리의 id 가 기준의 id 와 우연히 겹치면 엉뚱한 조문끼리 이어지므로, 먼저 모두
    # 다른 이름으로 바꾸어 두고 현행과 짝지어진 것만 기준의 id 를 물려받게 한다.
    def walk(ns):
        for n in ns:
            yield n
            yield from walk(n.get("children") or [])
    for n in walk(tree):
        n["id"] = "u2" + n["id"]

    # 제목이 같은 조문이 여럿이다 ('성과 등' 은 현행에 여섯 곳). 한 번 짝지은 현행
    # 조문은 빼고 다음 것을 준다 — 그러지 아니하면 여럿이 같은 조문을 물려받는다.
    cur = {}
    for n in H.flat(base["tree"], "조"):
        cur.setdefault((n["title"] or "").replace(" ", ""), []).append(n)

    def take(title):
        lst = cur.get((title or "").replace(" ", ""))
        return lst.pop(0) if lst else None
    jo_why, anx_why = why_tables(hwpx_lines(os.path.join(F2025, HWPX_WHY)))

    def why_of(no):
        for rng, item, txt in jo_why:
            m = RANGE.match(rng)
            if int(m.group(1)) <= no <= int(m.group(2) or m.group(1)):
                return item, txt, rng
        return None

    # 1벌 — 제목이 같은 것끼리 짝짓는다
    pair = {}
    for n in H.flat(tree, "조"):
        got = take(n["title"])
        if got:
            pair[n["no"]] = (got, False)

    # 2벌 — 제목까지 바뀌어 짝이 없는 것은 조 번호가 같은 현행 조문에 잇는다
    # (현행 제13조 촬영계획 ↔ 개정 제13조 촬영 및 스캔계획 처럼 제목만 바뀐 경우다.
    #  잇지 아니하면 한 조문이 '삭제 + 신설' 두 건으로 잡혀 비교표가 부풀어 오른다)
    left = {o["no"]: o for lst in cur.values() for o in lst}
    by_num = []
    for n in H.flat(tree, "조"):
        if n["no"] in pair:
            continue
        got = left.pop(n["no"], None)
        if got:
            pair[n["no"]] = (got, True)
            by_num.append((got, n))
    if by_num:
        print(f"  v2 조 번호로 이어 붙인 것 {len(by_num)}건")
        for o, n in by_num:
            print(f"        {o['legacyNo']}({o['title']}) → 제{n['no']}조({n['title']})")

    n_new = n_mod = n_same = 0
    for n in H.flat(tree, "조"):
        old, by_no = pair.get(n["no"], (None, False))
        w = why_of(n["no"])
        if old:
            n["id"] = old["id"]                 # 현행 조문을 물려받는다 (사라짐 오탐 방지)
            n["legacyNo"] = old["legacyNo"]
            if H.bare(old["body"]) == H.bare(n["body"]):
                n["status"] = "유지"
                n_same += 1
            else:
                n["status"] = "수정" if old["legacyNo"] == f"제{n['no']}조" else "이동·수정"
                n["wasBody"] = old["body"]      # 바뀐 말을 푸르게 짚기 위한 현행 본문
                n_mod += 1
            now = [f"현행 {old['legacyNo']}({old['title']}) — "
                   + (old["body"] or "").split("\n")[0][:70] + "…"]
            what = [f"제{n['no']}조로 두고 본문을 고쳤다"]
            if old["legacyNo"] != f"제{n['no']}조":
                what.append(f"현행 {old['legacyNo']} 자리에서 제{n['no']}조로 옮겼다")
            if by_no:
                what.append(f"제목이 '{old['title']}' 에서 '{n['title']}' 로 바뀌었다 —"
                            " 조 번호가 같아 현행 조문에 이어 붙였으니 같은 조문으로 볼지"
                            " 확인이 필요하다")
        else:
            n["legacyNo"], n["status"] = "", "신설"
            n_new += 1
            now = ["없음 — 신설 조문"]
            what = [f"제{n['no']}조({n['title']})를 새로 둔다"]

        problem = [w[1]] if w else ["개정사유서에 이 조문을 짚은 마디가 따로 없다"]
        ground = ([f"조항별 개정 사유 — {w[2]} ({w[0]})"] if w else [])
        key = mainkey(n["no"])
        if key:
            ground.append(MAIN[key])
        n["reason"] = reason(
            now, problem, ground,
            ["광학영상 중심 체계를 무인비행장치 다중센서(레이저측량·GNSS/INS·RTK/PPK)"
             " 기반으로 넓히는 개정이다"],
            what)
        n["history"], n["sourceRef"] = [], None

    write_tables(tables)

    bodies = annex_bodies(hwpx_lines(os.path.join(F2025, HWPX_ANNEX)))
    cur_anx = {f"{a['gubun']}{a['no']}": a for a in (base.get("annex") or [])}
    cur_anx_id = {}
    for g in base.get("annexTree") or []:
        for n in g.get("children") or []:
            r = n.get("annexRef") or {}
            cur_anx_id[f"{r.get('gubun')}{r.get('no')}"] = n["id"]
    kids = []
    for no in sorted(bodies, key=int):
        b = bodies[no]
        act = next((x[2] for x in anx_why if x[0].replace(" ", "") == f"별표{no}"), "")
        why = next((x[3] for x in anx_why if x[0].replace(" ", "") == f"별표{no}"), "")
        new = "신설" in (act or "") or "신설" in b["title"]
        kids.append({
            # 현행에 있던 별표는 기준의 id 를 물려받는다 (신설은 새 id)
            "id": (cur_anx_id.get(f"별표{no}") if not new else None)
                  or f"{DRAFT_ID}v2-anx-별표-{no}",
            "level": "조", "no": 0, "branch": 0,
            "title": re.sub(r"\s*\(안\)\s*(신설)?$", "", b["title"]).strip(),
            "body": "\n".join(b["lines"][:60]),
            "status": "신설" if new else "수정",
            "legacyNo": "" if new else f"별표 {no}",
            # 이름이 바뀐 별표는 편집기가 현행 이름과 견주어 붉게 짚는다
            "wasTitle": "" if new else (cur_anx.get(f"별표{no}", {}).get("title") or ""),
            "reason": reason(
                now=(["없음 — 신설 별표"] if new
                     else [f"현행 별표 {no}"
                           + (f"({cur_anx.get(f'별표{no}', {}).get('title')})"
                              if cur_anx.get(f"별표{no}") else "")]),
                problem=[why or "개정사유서에 이 별표를 짚은 마디가 따로 없다"],
                ground=[f"별표 개정 및 신설 사유 — 별표 {no} ({act or '수정'})"],
                why=["다중센서 성과의 검수·납품에 필요한 서식을 갖춘다"],
                what=([f"별표 {no}({b['title']})를 새로 둔다"] if new
                      else [f"별표 {no}의 내용을 고친다"])
                     + ["표는 원본을 보고 서식으로 옮겨야 한다"],
            ),
            "sourceRef": None, "history": [],
            "annexRef": {"gubun": "별표", "no": no, "hwp": "", "pdf": "",
                         # 미리보기는 v1 과 번호가 겹치므로 자리를 따로 적어 둔다
                         "previewDir": PREV2,
                         "source": "2025년 연구결과 별표수정(안)"},
            "children": [], "collapsed": False,
        })
    grp = {"id": f"{DRAFT_ID}v2-anxgrp-1", "level": "편", "no": 0, "branch": 0,
           "title": f"별표 ({len(kids)}건)", "body": "", "status": "유지", "legacyNo": "",
           "reason": "", "sourceRef": None, "history": [], "isAnnex": True,
           "children": kids, "collapsed": True}
    return tree + [grp], (n_new, n_mod, n_same), len(kids)


# ══════════════════════════════════════════════════════════════
def main(dry=False):
    base = json.load(io.open(os.path.join(DATA, BASE + ".json"), encoding="utf-8"))
    out_dir = os.path.join(DATA, "objects", DRAFT_ID)

    # 0. 기준이 우리가 아는 그 글월인가 — 2020년 고시 원본과 견준다
    b, bochik = H.body_lines(H.paragraphs(os.path.join(F2020, BODY_HWP)), base["name"])
    lines, _ = H.to_lines(b, {}, "", save=False)
    read = G.build_tree([fix(l) for l in lines])
    G.renumber(read)
    same, diff, layout = H.compare(base["tree"], read)
    print(f"\n  기준 대조 (2020년 고시 원본) — 글자까지 같음 {same} · 줄 구조만 다름 {layout}"
          f" · 글자가 다름 {len(diff)}")
    if diff:
        raise SystemExit("  [멈춤] 기준과 글자가 다릅니다.")

    v1, fixed, added = build_v1(base, out_dir, dry)
    t1 = apply_terms(v1, mark_kept=True)
    r1 = fix_refs(v1)
    print(f"  v1 (2024년 연구성과) — 고친 조문 {len(fixed)}건 {' '.join(fixed)}"
          f" · 새 별표 {len(added)}건 · 용어 정비 {t1}건"
          f" · 참조규정 이름 {sum(r1.values())}곳")
    for k, c in r1.items():
        print(f"        「{k}」 {c}곳 → 「{REFNAMES[k]}」")

    v2, (n_new, n_mod, n_same), n_anx = build_v2(base)
    t2 = apply_terms(v2, mark_kept=True)
    r2 = fix_refs(v2)
    c2 = add_annex_cites(v2)
    if not dry:
        make_previews_v2()
    print(f"  v2 별표 인용 {c2}곳을 달았다")
    print(f"  v2 용어 정비 {t2}건 · 참조규정 이름 {sum(r2.values())}곳")
    for k, c in r2.items():
        print(f"        「{k}」 {c}곳 → 「{REFNAMES[k]}」")
    jo2 = sum(1 for x in H.flat(v2, "조") if not x.get("annexRef"))
    print(f"  v2 (2025년 연구결과) — 조 {jo2} (신설 {n_new} · 고침 {n_mod} · 그대로 {n_same})"
          f" · 별표 {n_anx}건")

    draft = {
        "id": DRAFT_ID, "label": "v1", "title": "개정안 초안 (2024년 연구성과)",
        "base": BASE, "readonly": False,
        "source": "2024.연구성과.무인비행장치 측량 작업규정.개정안_25.07.18.pdf 부록 1",
        "sourceFile": "2024년.연구.한글파일",
        "note": (
            "2024년 연구(기본측량 성과 적용을 위한 무인비행장치 활용 연구)의 개정(안)을 현행 "
            "40조에 얹은 판입니다. 신구대조표 여섯 마디를 그대로 옮겨 제8조·제9조·제10조·제13조·"
            "제32조·제38조를 고치고, 별표 8(대공표지 형상)·별표 9(GNSS PPK 활용)·"
            "별표 10(품질관리기준)을 새로 달았습니다. 개정(안)의 '------' 는 현행 글자를 그대로 "
            "둔다는 뜻이므로 바뀌는 말만 갈아 끼웠고, 갈아 끼우기 전에 현행 글월이 개정(안)이 적은 "
            "것과 같은지 확인합니다. 개정(안) 문서가 벡터화 묘사 조문을 '제43조' 로 적었으나 현행은 "
            "제32조여서 조 번호는 현행에 맞추었습니다. 관련근거는 "
            "관련규정\\무인비행장치 측량 작업규정개정관련\\2024년.연구.한글파일 폴더입니다."
        ),
        "tree": v1,
        "next": [{
            "label": "v2", "title": "개정안 초안 (2025년 연구결과 · 무인비행장치 다중센서)",
            "readonly": False,
            "note": (
                "2025년 연구결과의 「무인비행장치 측량 작업규정 개정(안)」 전문을 옮긴 판입니다. "
                "광학영상 중심의 현행 체계를 무인비행장치 다중센서(LiDAR·GNSS/INS·RTK/PPK) 기반으로 "
                "넓혀 10장 42조로 다시 짰고, 별표는 15건(현행 7건 수정 + 8건 신설)입니다. 조문마다 "
                "개정사유서 '4. 조항별 개정 사유' 의 해당 마디를, 별표마다 '5. 별표 개정 및 신설 "
                "사유' 를 사유로 달았습니다. 조문의 상태(수정·이동·수정·신설)는 현행 조문과 제목을 "
                "맞대어 정했습니다. 별표 본문은 별표수정(안) 문서의 표를 글로 옮긴 것이라 칸 구분이 "
                "성글 수 있어, 서식으로 옮길 때 원본을 함께 보아야 합니다. 부칙 3조는 다른 규정 "
                "63종과 마찬가지로 싣지 않았습니다. 관련근거는 "
                "관련규정\\무인비행장치 측량 작업규정개정관련\\2025년.연구결과 폴더입니다."
            ),
            "tree": v2,
        }],
    }
    if dry:
        print("\n  --dry — 파일을 쓰지 않았습니다.")
        return
    with io.open(os.path.join(DATA, OUTFILE), "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(out_dir, exist_ok=True)
    for fn in ("index.json", "annex-index.json"):
        p = os.path.join(out_dir, fn)
        if not os.path.exists(p):
            io.open(p, "w", encoding="utf-8").write("{}")
    print(f"\n  data/{OUTFILE} 를 썼습니다 — 기준 · v1 · v2")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
