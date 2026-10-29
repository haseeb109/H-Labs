@echo off
rem H Labs launcher for Windows (double-click). First time on a new PC: double-click Setup.bat once.
setlocal
cd /d "%~dp0"
if not exist ".venv\.hlabs-uv" (
  echo.
  echo  H Labs is not set up on this PC yet ^(or was set up with the old installer^).
  echo  Close this window and double-click  Setup.bat  first.
  echo.
  pause
  exit /b 1
)
call "%~dp0tools\win\env.bat"
".venv\Scripts\python.exe" tools\launcher.py
rem exit code 88 = menu option 8 (update): the launcher has closed so the update can replace files it was using.
rem The whole block is read before it runs, so the update may safely replace this .bat; a fresh window then opens the new one.
if errorlevel 88 if not errorlevel 89 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\win\setup.ps1" -Update
  pause
  start "H Labs" "%~dp0H Labs.bat"
  exit
)
pause
