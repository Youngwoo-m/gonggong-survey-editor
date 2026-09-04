# -*- coding: utf-8 -*-
r"""웹 꾸러미에 함께 담을 것들을 kit\ 로 모은다.

[보고서 생성] 으로 받은 zip 만으로 다른 PC 에서 한/글 문서를 지을 수 있어야
한다. 그러려면 도구와 양식이 zip 안에 들어 있어야 하고, 브라우저가 그것들을
넣으려면 웹에 올라가 있어야 한다 — 그래서 App\prototype\kit\ 에 복사해 둔다.

원본이 바뀌면 이것을 다시 돌린다. 복사본이라 손으로 고치면 안 된다.

  python scripts\synckit.py
"""
import io
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # …\App\prototype
BASE = os.path.dirname(os.path.dirname(ROOT))      # …\2026.공공측량.품관원
FORM = os.path.join(BASE, "Form")
SKILL = os.environ.get("HWPX_SKILL") or os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "hwpx")
KIT = os.path.join(ROOT, "kit")

# (원본, 꾸러미 안의 자리)
TOOLS = ["make_hwpx.py", "formfill.py", "formdocs.py", "forms_hwp.py",
         "genreport.py", "genreport_hwpx.py"]
SKILLS = ["fix_namespaces.py", "validate_hwpx_package.py",
          "render_hwpx_to_pdf.ps1", "render_pdf_pages.py"]
FORMS = [("01.개정안", "[양식] 규정 개정(안).hwpx"),
         ("02.신구대조표", "[양식] 규정.신구대조표.hwpx"),
         ("03.개정사유서", "[양식] 작업규정 개정안_개정사유서.hwpx"),
         ("04.별표별지", "[양식] 별표수정(안).hwpx")]

BAT = """@echo off
chcp 65001 > nul
setlocal
pushd "%~dp0"

echo.
echo  공공측량 규정 개정 - 한/글 문서 만들기
echo  ---------------------------------------------------------------
echo  이 꾸러미의 편집 상태로 개정(안), 신구대조표, 개정사유서를 작성합니다.
echo  한/글이 잠깐 떴다 사라집니다. 창을 닫지 마십시오.
echo.

set PY=
where py    > nul 2>&1 && set PY=py -3
if "%PY%"=="" ( where python > nul 2>&1 && set PY=python )
if "%PY%"=="" (
  echo  [멈춤] 파이썬을 찾지 못했습니다.
  echo         https://www.python.org/downloads/ 에서 받아 까신 뒤,
  echo         설치 화면의 "Add python.exe to PATH" 를 꼭 켜 주십시오.
  echo.
  pause
  exit /b 1
)

set SCRIPT=도구\\make_hwpx.py
if not exist "%SCRIPT%" set SCRIPT=tools\\make_hwpx.py
if not exist "%SCRIPT%" (
  echo  [멈춤] 도구\\make_hwpx.py 를 찾지 못했습니다.
  echo         zip 을 통째로 푸셨는지 보십시오 — 폴더째 풀어야 합니다.
  echo.
  pause
  exit /b 1
)

%PY% "%SCRIPT%" %*
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo  작성을 마쳤습니다. 출력 폴더를 엽니다.
  start "" "%~dp0출력"
) else (
  echo  [멈춤] 작성하지 못했습니다. 위의 글을 읽어 보십시오.
)
echo.
pause
popd
endlocal
"""


def put(src, rel):
    dst = os.path.join(KIT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return rel.replace("\\", "/"), os.path.getsize(dst)


def main():
    if os.path.isdir(KIT):
        shutil.rmtree(KIT)
    os.makedirs(KIT)

    listed, missing = [], []

    for n in TOOLS:
        p = os.path.join(HERE, n)
        if os.path.exists(p):
            listed.append(put(p, os.path.join("도구", n)))
        else:
            missing.append(n)

    for n in SKILLS:
        p = os.path.join(SKILL, "scripts", n)
        if os.path.exists(p):
            listed.append(put(p, os.path.join("도구", "hwpx", "scripts", n)))
        else:
            missing.append("hwpx/" + n)

    for sub, n in FORMS:
        p = os.path.join(FORM, sub, n)
        if os.path.exists(p):
            listed.append(put(p, os.path.join("양식", sub, n)))
        else:
            missing.append(sub + "/" + n)

    bat = os.path.join(KIT, "한글문서만들기.bat")
    # bat 은 UTF-8 로, BOM 없이 적는다.
    #
    # 처음에는 CP949 로 적었더니 화면의 한글이 통째로 깨지고, 깨진 경로 때문에
    # 스크립트조차 못 찾았다. 첫 줄에서 chcp 65001(UTF-8)로 바꿔 놓고 본문은
    # CP949 로 적었으니 어긋난 것이다.
    #
    # BOM 은 붙이면 안 된다 — cmd 가 그 세 바이트를 명령으로 읽어 첫 줄에
    # 알 수 없는 글자가 찍힌다.
    io.open(bat, "w", encoding="utf-8", newline="\r\n").write(BAT)
    listed.append(("한글문서만들기.bat", os.path.getsize(bat)))

    man = {"note": "이 목록은 scripts/synckit.py 가 씁니다. 손으로 고치지 마십시오.",
           "files": [{"path": p, "size": s} for p, s in listed]}
    io.open(os.path.join(KIT, "kit.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(man, ensure_ascii=False, indent=1))

    tot = sum(s for _p, s in listed)
    print("kit\\ 에 모았습니다 — %d개 · %.0f KB" % (len(listed), tot / 1024))
    for p, s in listed:
        print("   %7.0f KB  %s" % (s / 1024, p))
    if missing:
        print("\n[주의] 못 찾은 것 %d개:" % len(missing))
        for m in missing:
            print("   " + m)


if __name__ == "__main__":
    main()
