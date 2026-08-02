@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if "%~1"=="" (
  echo Usage: run_github_pr_publish.bat ^<reviewed-plan-digest^>
  exit /b 2
)
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\New-VerifiedPullRequest.ps1" -Publish -PlanDigest "%~1" -Confirmation "PUSH VERIFIED FACTUAL SPACE PR"
set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%
