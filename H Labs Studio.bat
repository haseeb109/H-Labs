@echo off
rem H Labs Studio - the browser app (queue many stream links, watch progress, upload kit). Double-click.
setlocal
cd /d "%~dp0"
if not exist ".venv\.hlabs-uv" (
  echo.
  echo  H Labs is not set up on this PC yet. Double-click  Setup.bat  first.
  echo.
  pause
  exit /b 1
)
call "%~dp0tools\win\env.bat"
title H Labs Studio - keep this window open
rem the Studio runs inside tools\win\studio.ps1: its Update button (exit code 88) updates H Labs and starts the Studio again
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\win\studio.ps1"
pause
