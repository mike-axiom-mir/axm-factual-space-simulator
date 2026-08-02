@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python scripts\build_all_demos_v0_15.py
if errorlevel 1 exit /b 1
echo Open: %CD%\OPEN_LOCAL_HANDOFF.html
endlocal & exit /b 0
