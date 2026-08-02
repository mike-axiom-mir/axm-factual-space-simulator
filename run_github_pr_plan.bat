@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\New-VerifiedPullRequest.ps1"
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%
