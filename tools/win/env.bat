@echo off
rem Points this window at the tools inside the H Labs folder (runtime\). Called by H Labs.bat; changes nothing on the PC.
set "HL_ROOT=%~dp0..\.."
for %%I in ("%HL_ROOT%") do set "HL_ROOT=%%~fI"
set "HL_RT=%HL_ROOT%\runtime"
if exist "%HL_RT%\ffmpeg\bin\ffmpeg.exe" set "PATH=%HL_RT%\ffmpeg\bin;%PATH%"
if exist "%HL_RT%\node\node.exe" set "PATH=%HL_RT%\node;%PATH%"
if exist "%HL_RT%\git\cmd\git.exe" set "PATH=%HL_RT%\git\cmd;%PATH%"
set "PLAYWRIGHT_BROWSERS_PATH=%HL_RT%\ms-playwright"
set "HF_HOME=%HL_RT%\hf"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
