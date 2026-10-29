@echo off
rem H Labs - one-time setup for Windows 10/11. Safe to run again (it skips what is already installed).
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set PYTHONUTF8=1
set NEED_RESTART=0
echo.
echo ===== H Labs Windows setup =====
echo.

where winget >nul 2>nul
if errorlevel 1 (
  echo [!] winget was not found. Install "App Installer" from the Microsoft Store, or install Python 3.12, ffmpeg, Node.js LTS and Git by hand,
  echo     then run this file again.
  pause
  exit /b 1
)

rem python: the tool needs Python 3.10-3.13 (3.12 recommended; 3.14 is too new for some libraries).
rem "python" may be missing from PATH or be the Microsoft Store stub, so use the "py" launcher first.
set PYCMD=
py -3.12 --version >nul 2>nul && set PYCMD=py -3.12
if not defined PYCMD py -3.11 --version >nul 2>nul && set PYCMD=py -3.11
if not defined PYCMD py -3.13 --version >nul 2>nul && set PYCMD=py -3.13
if not defined PYCMD python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul && set PYCMD=python
if not defined PYCMD (
  echo [install] Python 3.12  ^(a suitable Python was not found; any newer Python stays installed, it is simply not used^)
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [ok] python via %PYCMD%
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [install] ffmpeg
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [ok] ffmpeg
)
where node >nul 2>nul
if errorlevel 1 (
  echo [install] Node.js LTS
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [ok] node
)
where git >nul 2>nul
if errorlevel 1 (
  echo [install] Git
  winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [ok] git
)

if "!NEED_RESTART!"=="1" (
  echo.
  echo  Some tools were just installed. CLOSE this window, open a new one and double-click install_windows.bat again.
  echo.
  pause
  exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
  echo [setup] creating .venv
  %PYCMD% -m venv .venv
  if errorlevel 1 ( echo [!] could not create .venv & pause & exit /b 1 )
)
set PY=.venv\Scripts\python.exe
echo [setup] installing Python packages (a few minutes)
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install "yt-dlp[default]" pillow numpy "av<16" faster-whisper playwright
if errorlevel 1 ( echo [!] pip install failed & pause & exit /b 1 )
echo [setup] installing the graphics browser (Chromium)
"%PY%" -m playwright install chromium
echo [setup] optional: face-aware thumbnails
"%PY%" -m pip install mediapipe
if not exist models mkdir models
if not exist models\blaze_face_short_range.tflite (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite' -OutFile 'models\blaze_face_short_range.tflite' } catch { Write-Host 'face model download skipped' }"
)
echo [setup] optional: HyperFrames (motion labels for Trial Tales)
call npm install -g hyperframes
call hyperframes browser ensure

rem key files (empty templates: the keys themselves come from the owner, they are never in the repo)
set KD=%USERPROFILE%\.config\umf
if not exist "%KD%" mkdir "%KD%"
if not exist "%KD%\hive.env" echo HIVE_API_KEY=>"%KD%\hive.env"
if not exist "%KD%\anthropic.env" echo ANTHROPIC_API_KEY=>"%KD%\anthropic.env"
if not exist "%KD%\deepseek.env" echo DEEPSEEK_API_KEY=>"%KD%\deepseek.env"
if not exist "%KD%\openai.env" echo OPENAI_API_KEY=>"%KD%\openai.env"
if not exist "%KD%\ai33.env" echo AI33_API_KEY=>"%KD%\ai33.env"

echo.
echo ===== Done =====
echo  1. Put the API keys into the files in  %KD%   (menu option 4 in H Labs.bat opens them)
echo  2. Double-click  H Labs.bat   and pick option 7 (Setup check) to confirm everything is green.
echo.
pause
