@echo off
rem H Labs launcher for Windows (double-click). First time on a new PC: run install_windows.bat once.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\launcher.py
) else (
  echo.
  echo  The setup has not been run on this PC yet.
  echo  Close this window and double-click  install_windows.bat  first.
  echo.
)
pause
