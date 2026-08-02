@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python -m axm_star_sim.rooted_crew_cli %*
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%
