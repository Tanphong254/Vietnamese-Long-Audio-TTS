@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Vietnamese Long Audio TTS

if exist ".venv\Scripts\python.exe" goto env_ready

echo [1/3] Dang tim Python...
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
    if not errorlevel 1 goto env_ready
    echo Khong tao duoc moi truong ao bang lenh py -3.
)

REM Fallback for installations that provide python.exe but not the py launcher.
set "FOUND_PYTHON="
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "\Microsoft\WindowsApps\" >nul
    if errorlevel 1 if not defined FOUND_PYTHON set "FOUND_PYTHON=%%P"
)
if defined FOUND_PYTHON (
    "%FOUND_PYTHON%" -m venv .venv
    if not errorlevel 1 goto env_ready
)

echo.
echo KHONG TIM THAY PYTHON HOAT DONG.
echo Hay cai Python 3.11-3.13 tu https://www.python.org/downloads/windows/
echo Trong luc cai dat, bat tuy chon Python Launcher va Add Python to PATH neu co.
echo Sau do dong mo lai Terminal va chay run.bat mot lan nua.
echo Neu Windows mo Microsoft Store, hay kiem tra App execution aliases trong Settings.
echo.
pause
exit /b 1

:env_ready
if not exist ".venv\.requirements-installed" (
    echo [2/3] Dang cai thu vien can thiet. Lan dau co the mat vai phut...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto install_failed
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto install_failed
    >".venv\.requirements-installed" echo installed
) else (
    echo [2/3] Da co thu vien co ban. Bo qua cai dat lai.
)

echo [3/3] Dang khoi dong may chu TTS...
echo Mo trinh duyet tai http://127.0.0.1:5000
echo De dung ung dung, quay lai cua so nay va nhan Ctrl+C.
echo.
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo.
    echo Ung dung da dung do co loi. Hay doc thong bao phia tren.
    pause
)
exit /b 0

:install_failed
echo.
echo Cai thu vien that bai. Hay kiem tra ket noi Internet va thu lai.
echo Neu requirements.txt thay doi sau lan cai dau, chay lenh:
echo .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
