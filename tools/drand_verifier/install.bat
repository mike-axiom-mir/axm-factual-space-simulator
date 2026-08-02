@echo off
setlocal
cd /d "%~dp0"
npm ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 exit /b 1
echo Pinned AXM drand verifier dependencies installed.
endlocal & exit /b 0
