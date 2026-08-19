@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [오류] Python 을 찾을 수 없습니다.
  echo   Python 설치 후 다시 실행하거나, 아래 명령을 직접 실행하세요.
  echo       npx serve .
  echo.
  pause
  exit /b 1
)

python serve.py 8765
pause
