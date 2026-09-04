@echo off
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

set SCRIPT=도구\make_hwpx.py
if not exist "%SCRIPT%" set SCRIPT=tools\make_hwpx.py
if not exist "%SCRIPT%" (
  echo  [멈춤] 도구\make_hwpx.py 를 찾지 못했습니다.
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
