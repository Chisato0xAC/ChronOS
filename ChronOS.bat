@echo off
REM 这行切换到当前项目目录，避免路径错误。
cd /d "%~dp0"

REM 这行先打开浏览器。
start "" http://127.0.0.1:8000

REM 这行优先用 python 启动服务。
python server.py

REM 如果 python 启动失败，再尝试 py 启动器。
if errorlevel 1 py server.py

REM 服务退出后，窗口停住，避免闪退。
echo 服务已退出。按任意键关闭窗口。
pause
