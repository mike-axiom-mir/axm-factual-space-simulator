@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python verify_package.py
if errorlevel 1 exit /b 1
python -m axm_star_sim.handoff_cli audit --full
if errorlevel 1 exit /b 1
echo.
echo LOCAL HANDOFF ACCEPTED
endlocal & exit /b 0
