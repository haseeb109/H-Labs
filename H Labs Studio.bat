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
".venv\Scripts\python.exe" tools\studio\server.py
pause
