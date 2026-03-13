@echo off
chcp 65001 >nul
setlocal

rem 这个脚本用于把项目自带的 git hooks 安装到 .git/hooks/。
rem 注意：.git/hooks 不会被 git 提交，所以需要单独安装一次。

set ROOT=%~dp0..

if not exist "%ROOT%\.git" (
  echo [ERROR] 未找到 .git 目录：请在 git 仓库根目录运行本脚本。
  pause
  exit /b 1
)

if not exist "%ROOT%\.git\hooks" (
  mkdir "%ROOT%\.git\hooks"
)

if not exist "%ROOT%\tools\githooks\post-commit" (
  echo [ERROR] 缺少 hook 模板文件：tools\githooks\post-commit
  pause
  exit /b 1
)

copy /Y "%ROOT%\tools\githooks\post-commit" "%ROOT%\.git\hooks\post-commit" >nul
if errorlevel 1 (
  echo [ERROR] 安装失败：无法写入 .git\hooks\post-commit
  pause
  exit /b 1
)

if exist "%ROOT%\tools\githooks\reference-transaction" (
  copy /Y "%ROOT%\tools\githooks\reference-transaction" "%ROOT%\.git\hooks\reference-transaction" >nul
)

echo [OK] 已安装 git hook: .git\hooks\post-commit
if exist "%ROOT%\.git\hooks\reference-transaction" (
  echo [OK] 已安装 git hook: .git\hooks\reference-transaction
)
echo      之后每次 git commit 都会通知 ChronOS（如果 ChronOS 没运行，会自动忽略）。
pause
