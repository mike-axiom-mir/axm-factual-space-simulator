@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if "%~1"=="" (
  echo Usage: %~nx0 ^<plan-digest^> [workshop-root]
  exit /b 2
)
set "AXM_BACKFEED_DIGEST=%~1"
set "AXM_WORKSHOP_TARGET=%~2"
if not defined AXM_WORKSHOP_TARGET set "AXM_WORKSHOP_TARGET=D:\AXM_ACTIVE\workshop"
python tools\install_platform_backfeed.py --workshop "%AXM_WORKSHOP_TARGET%" --apply --plan-digest "%AXM_BACKFEED_DIGEST%"
exit /b %errorlevel%
