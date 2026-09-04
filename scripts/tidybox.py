# -*- coding: utf-8 -*-
r"""`App\관련규정` 을 규정과 정식보고서만 남도록 정리한다.

■ 규칙 넷

  ㉠ 규정이나 정식보고서가 아닌 것은 뺀다.
     교육용 동영상, 화면 갈무리, 발표자료 초안, 서식 견본이 섞여 있다.
     `App\기타자료` 로 옮긴다. 지우지는 아니한다 — 쓸모가 없는 것이 아니라
     이 폴더의 것이 아닐 뿐이다.

  ㉡ KCS 와 KDS 는 원문을 기준으로 삼는다.
     국가법령정보센터의 고시 본문은 441자짜리 껍데기이고 실제 기준은 고시
     첨부 압축파일 안에 있다(kcsget.py 로 받았다). 그러므로

        - 고시 첨부에서 받은 전문을 기준본으로 삼는다.
        - 고시번호가 붙지 아니한 옛 사본은 지운다. 머리말을 견주면
          「KDS 12 00 00 건설측량 설계기준」 으로 되어 있어 2024년 고시
          제2024-5556호가 「KDS 12 20 00 건설공사 설계측량」 으로 바꾸기
          전의 판이다.
        - 다만 「3차원 디지털 설계측량」 은 고시 첨부가 레거시 hwp 이므로,
          읽을 수 있는 hwpx 사본을 「(hwpx 변환본)」 을 달아 함께 둔다.
        - 껍데기 고시문은 규정 문서이므로 버리지 아니하고
          `건설측량_설계기준\_고시공고문` 으로 내린다.

  ㉢ 새 판이 있으면 옛 판은 지운다.
     ASPRS 와 USGS 처럼 같은 표준의 옛 판이 함께 있는 것이 있다.

  ㉣ 개정 작업물은 `App\개정안` 쪽으로 보낸다.
     `무인비행장치 측량 작업규정개정관련` 은 현행 규정 원문이 아니라
     개정 작업 자료이다. 작업규정 별표 원고를 `개정안\작업규정\별표원고`
     로 보낸 것과 같은 원칙이다.

  python scripts\tidybox.py            무엇을 할지 보여만 준다
  python scripts\tidybox.py --write    실제로 옮기고 지운다
"""
import io
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
BOX = os.path.join(APP, "관련규정")
NL = chr(10)

ETC = os.path.join(APP, "기타자료")
NOTICE = os.path.join(BOX, "건설측량_설계기준", "_고시공고문")
UAV = os.path.join(APP, "개정안", "무인비행장치 규정", "개정작업자료")

# ㉠ 규정도 정식보고서도 아닌 것 —— 폴더째 또는 파일 하나
OUT_DIRS = {
    "법제처_법령안편집기/": "법령안편집기 사용법 교육 자료(동영상ㆍ교재)",
}
OUT_FILES = {
    "U20260616_150247995_점형시설물_간담회_발표자료_초안_V5.3(최대오차수정).pdf":
        "간담회 발표자료 초안",
    "신구 조문 대비표_샘플.pdf": "서식 견본",
    "성과심사관련규정/지형도의 정확도.오류KakaoTalk_20251231_095419606.png":
        "대화 화면 갈무리",
}

# ㉡ 껍데기 고시문 —— 본문이 441자뿐이고 「첨부파일을 이용하십시오」 만 있다
SHELL = re.compile(r"^하위규정/(건설공사 측량 표준시방서|건설측량 설계기준)\(KCS|"
                   r"^하위규정/건설측량 설계기준\(KDS")

# ㉢ 새 판이 있어 지울 옛 판 —— (지울 것, 남는 새 판)
OLDER = {
    "국외관련규정/2023_ASPRS_Positional_Accuracy_Standards_Edition2_Version1.0.pdf":
        "2024_ASPRS_…_Edition2_Version2.0_영문원본.pdf",
    "국외관련규정/미국_USGS_FGDC/USGS_Lidar_Base_Specification_2024_revA.docx":
        "USGS_Lidar_Base_Specification_2025_revA.docx",
}

# ㉡ 고시번호가 붙지 아니한 옛 KDS 사본
RE_KDSOLD = re.compile(r"^건설측량_설계기준/(KDS|KCS) [\d ]+[^/]*$")
KEEP_CONV = "KDS 12 30 05 3차원 디지털 설계측량.hwpx"
CONV_NAME = ("KDS 12 30 05 3차원 디지털 설계측량"
             "(국토지리정보원고시)(제2024-5556호)(20241121)(hwpx 변환본).hwpx")

# ㉣ 개정 작업 자료
UAV_DIR = "무인비행장치 측량 작업규정개정관련/"


def files():
    for cur, dirs, fs in os.walk(BOX):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(fs):
            p = os.path.join(cur, f)
            yield p, os.path.relpath(p, BOX).replace(os.sep, "/")


def plan():
    moves, kills = [], []
    for p, rel in files():
        if rel in OUT_FILES:
            moves.append((p, os.path.join(ETC, os.path.basename(rel)),
                          "㉠ " + OUT_FILES[rel])); continue
        hit = next((k for k in OUT_DIRS if rel.startswith(k)), None)
        if hit:
            moves.append((p, os.path.join(ETC, rel), "㉠ " + OUT_DIRS[hit]))
            continue
        if rel in OLDER:
            kills.append((p, rel, "㉢ 새 판 있음 — %s" % OLDER[rel])); continue
        if SHELL.match(rel):
            moves.append((p, os.path.join(NOTICE, os.path.basename(rel)),
                          "㉡ 본문 없는 고시 공고문")); continue
        if rel.startswith(UAV_DIR):
            moves.append((p, os.path.join(UAV, rel[len(UAV_DIR):]),
                          "㉣ 개정 작업 자료")); continue
        if RE_KDSOLD.match(rel) and "(국토지리정보원고시)" not in rel:
            base = os.path.basename(rel)
            if base == KEEP_CONV:
                moves.append((p, os.path.join(os.path.dirname(p), CONV_NAME),
                              "㉡ 고시본이 레거시 hwp — 변환본으로 표시"))
            else:
                kills.append((p, rel, "㉡ 고시 전문본으로 갈음"))
    return moves, kills


def main():
    write = "--write" in sys.argv
    moves, kills = plan()
    print("옮길 것 %d건, 지울 것 %d건" % (len(moves), len(kills)))
    print()
    grp = {}
    for _p, _q, why in moves:
        grp[why] = grp.get(why, 0) + 1
    for _p, _r, why in kills:
        grp[why] = grp.get(why, 0) + 1
    for why in sorted(grp, key=lambda z: (z[0], -grp[z])):
        print("   %-58s %3d건" % (why[:58], grp[why]))
    print()
    print("지울 것")
    for _p, rel, why in kills:
        print("   %-64s %s" % (rel[:64], why[:34]))
    if not write:
        print()
        print("표시만 한 것임. 실제로 하려면 --write 를 붙일 것.")
        return

    log = []
    for p, q, why in moves:
        os.makedirs(os.path.dirname(q), exist_ok=True)
        if os.path.exists(q) and os.path.getsize(q) == os.path.getsize(p):
            os.remove(p)
        else:
            shutil.move(p, q)
        log.append([why.split()[0], os.path.relpath(p, BOX).replace(os.sep, "/"),
                    os.path.relpath(q, APP).replace(os.sep, "/")])
    for p, rel, why in kills:
        os.remove(p)
        log.append(["삭제", rel, why])
    for cur, dirs, fs in os.walk(BOX, topdown=False):
        if cur != BOX and not os.listdir(cur):
            os.rmdir(cur)
    with io.open(os.path.join(BOX, "이동내역.tsv"), "a",
                 encoding="utf-8-sig", newline=NL) as fp:
        for r in log:
            fp.write("\t".join(r) + NL)
    print()
    print("옮김 %d건, 지움 %d건" % (len(moves), len(kills)))


if __name__ == "__main__":
    main()
