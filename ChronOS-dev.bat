@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d %~dp0

rem Dev launcher (console visible)
start http://127.0.0.1:8000

rem Prefer python, fallback to py
python -X utf8 -u tools\dev_autoreload.py
if errorlevel 1 py -X utf8 -u tools\dev_autoreload.py

echo Server exited. Press any key to close.
pause
