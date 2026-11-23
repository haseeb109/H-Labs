# H Labs Studio, kept running: started by "H Labs Studio.bat". When the Studio page's Update button is pressed the Studio
# server exits with code 88; this script then runs the normal update (setup.ps1 -Update: newest code with state\ kept,
# packages, newest yt-dlp, smoke test) in this window and starts the Studio again - the open browser page reconnects by itself.
# PowerShell reads this whole file before it runs, so an update that changes this file is safe.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $Root ".venv\Scripts\python.exe"
$env:HL_STUDIO_LOOP = "1"
$extra = @()
while ($true) {
    & $py (Join-Path $Root "tools\studio\server.py") @extra
    $rc = $LASTEXITCODE
    if ($rc -ne 88) { exit $rc }
    Write-Host ""
    Write-Host "===== H Labs Studio: UPDATE requested from the Studio page =====" -ForegroundColor Cyan
    Write-Host "  (the page waits and shows what changed when the Studio is back - do not close this window)" -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "tools\win\setup.ps1") -Update -NoPrompt
    Write-Host ""
    Write-Host "===== update finished (exit $LASTEXITCODE) - starting H Labs Studio again =====" -ForegroundColor Cyan
    $extra = @("--no-browser")
}
