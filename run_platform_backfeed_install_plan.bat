@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "AXM_WORKSHOP_TARGET=%~1"
if not defined AXM_WORKSHOP_TARGET set "AXM_WORKSHOP_TARGET=D:\AXM_ACTIVE\workshop"
python tools\install_platform_backfeed.py --workshop "%AXM_WORKSHOP_TARGET%" --plan
exit /b %errorlevel%
