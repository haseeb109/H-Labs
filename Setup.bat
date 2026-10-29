@echo off
rem H Labs - first-time setup on a Windows PC (double-click). Safe to run again; also repairs a broken install.
rem Everything goes into this folder: no admin rights, no winget, nothing installed system-wide.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\win\setup.ps1"
pause
