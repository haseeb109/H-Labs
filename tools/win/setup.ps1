# H Labs - Windows setup / update (run through Setup.bat, or menu option 8 in H Labs.bat).
#
# Everything the tool needs goes into THIS folder (runtime\ and .venv\): nothing is installed system-wide, no admin rights,
# no winget, no PATH changes. Every download is an exact pinned version checked by SHA-256, so every laptop ends up identical.
# Safe to run again: what is already in place with the right version is skipped.
#
#   runtime\uv          uv 0.9.5 (installs Python + the locked packages)
#   runtime\python      Python 3.12 (managed by uv, only used by this tool)
#   runtime\ffmpeg      ffmpeg 8.0.1 essentials (libass, x264, NVENC that works with older NVIDIA drivers)
#   runtime\node        Node.js 22 LTS (yt-dlp challenge solving, hyperframes)
#   runtime\git         PortableGit 2.51.2 - only when Git is not installed on the PC
#   runtime\ms-playwright   Chromium for the graphics       runtime\hf   whisper model cache
#   .venv               Python packages from uv.lock (+ newest yt-dlp)
#
# Change a pinned tool: edit $Pins below (version, url, sha256) and commit; the next update installs it everywhere.
param([switch]$Update, [switch]$NoPrompt)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"       # Invoke-WebRequest is ~10x faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RT = Join-Path $Root "runtime"
$DL = Join-Path $RT "_downloads"
Set-Location $Root

$Pins = @{
    uv     = @{ ver = "0.9.5";  sha = "515dc53d7553f1357d0abc1f70acd921fbb9e30230b1d9a08737236daa6ee920"; inner = "";
                url = "https://github.com/astral-sh/uv/releases/download/0.9.5/uv-x86_64-pc-windows-msvc.zip" }
    ffmpeg = @{ ver = "8.0.1";  sha = "e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673"; inner = "ffmpeg-8.0.1-essentials_build";
                url = "https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-essentials_build.zip" }
    node   = @{ ver = "22.20.0"; sha = "bb819d6eb8f5bfda294bbc83a7e4ec6539da67c4233d54b0d655b9248b15e29d"; inner = "node-v22.20.0-win-x64";
                url = "https://nodejs.org/dist/v22.20.0/node-v22.20.0-win-x64.zip" }
    git    = @{ ver = "2.51.2"; sha = "f5764d546ff9a2511b50ec4e20424c5f4669de1695abc3fa4128e7f7d4a7b2cd"; inner = "";
                url = "https://github.com/git-for-windows/git/releases/download/v2.51.2.windows.1/PortableGit-2.51.2-64-bit.7z.exe" }
}

function Step($m) { Write-Host ""; Write-Host "[setup] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [ok] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Fail($m) {
    Write-Host ""; Write-Host "[X] $m" -ForegroundColor Red
    Write-Host "    Nothing outside this folder was changed. Fix the problem above (usually internet) and run Setup.bat again."
    exit 1
}

function Get-Pinned($name) {
    # download + verify + unpack one pinned tool into runtime\<name>; skipped when runtime\<name>\.version already matches
    $p = $Pins[$name]
    $dest = Join-Path $RT $name
    $mark = Join-Path $dest ".version"
    if ((Test-Path $mark) -and ((Get-Content $mark -Raw).Trim() -eq $p.ver)) { Ok "$name $($p.ver)"; return }
    New-Item -ItemType Directory -Force -Path $DL | Out-Null
    $file = Join-Path $DL ([IO.Path]::GetFileName($p.url))
    $good = (Test-Path $file) -and ((Get-FileHash $file -Algorithm SHA256).Hash -eq $p.sha.ToUpper())
    if (-not $good) {
        Write-Host "  downloading $name $($p.ver) ..."
        for ($i = 1; $i -le 3; $i++) {
            try { Invoke-WebRequest -UseBasicParsing -Uri $p.url -OutFile $file; break }
            catch { if ($i -eq 3) { Fail "could not download $name from $($p.url): $($_.Exception.Message)" }; Start-Sleep -Seconds (3 * $i) }
        }
        if ((Get-FileHash $file -Algorithm SHA256).Hash -ne $p.sha.ToUpper()) {
            Remove-Item $file -Force
            Fail "$name download is damaged or not the expected file (SHA-256 mismatch)"
        }
    }
    $tmp = Join-Path $RT "_unpack_$name"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    Write-Host "  unpacking $name ..."
    if ($file.EndsWith(".7z.exe")) {
        $pr = Start-Process -FilePath $file -ArgumentList @("-y", "-o`"$tmp`"") -Wait -PassThru -WindowStyle Hidden
        if ($pr.ExitCode -ne 0) { Fail "could not unpack $name (exit $($pr.ExitCode))" }
    } elseif (Get-Command tar.exe -ErrorAction SilentlyContinue) {
        & tar.exe -xf $file -C $tmp
        if ($LASTEXITCODE -ne 0) { Fail "could not unpack $name" }
    } else {
        Expand-Archive -Path $file -DestinationPath $tmp -Force
    }
    $src = $tmp
    if ($p.inner) { $src = Join-Path $tmp $p.inner }
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    Move-Item $src $dest
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Set-Content -Path $mark -Value $p.ver -Encoding Ascii
    Ok "$name $($p.ver)"
}

function Write-NoBom($path, $text) { [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false)) }

Write-Host "===== H Labs setup  ($Root) =====" -ForegroundColor Cyan
if (-not [Environment]::Is64BitOperatingSystem) { Fail "this tool needs 64-bit Windows" }
if ($Root -match "OneDrive") { Warn "this folder is inside OneDrive - syncing big video files slows everything down. Better: C:\HLabs" }
New-Item -ItemType Directory -Force -Path $RT | Out-Null

# ---- 0. update: get the newest code first, then run the NEW setup script (it may pin new versions) ----
if ($Update) {
    Step "getting the newest code from GitHub"
    $g = Get-Command git -ErrorAction SilentlyContinue
    $gitExe = if ($g) { $g.Source } elseif (Test-Path "$RT\git\cmd\git.exe") { "$RT\git\cmd\git.exe" } else { $null }
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        Warn "this folder was not cloned with git (downloaded as ZIP?) - code update skipped. Clone it once with git to get updates."
    } elseif (-not $gitExe) {
        Warn "git not found - code update skipped (run Setup.bat once, it installs a portable git)"
    } else {
        & $gitExe -C $Root pull --ff-only
        if ($LASTEXITCODE -ne 0) { Warn "git pull failed (local edits in the folder? see the message above). Setup continues with the current code." }
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "tools\win\setup.ps1") -NoPrompt
    exit $LASTEXITCODE
}

# ---- 1. pinned tools ----
Step "tools (exact versions, into runtime\)"
Get-Pinned "uv"
Get-Pinned "ffmpeg"
Get-Pinned "node"
if (Get-Command git -ErrorAction SilentlyContinue) { Ok "git (installed on this PC)" } else { Get-Pinned "git" }

# only this process and its children see the runtime tools (H Labs.bat does the same through tools\win\env.bat)
$env:Path = "$RT\ffmpeg\bin;$RT\node;$RT\git\cmd;$RT\uv;" + $env:Path
$env:UV_PYTHON_INSTALL_DIR = "$RT\python"
$env:UV_CACHE_DIR = "$RT\uv-cache"
$env:UV_PYTHON_PREFERENCE = "only-managed"     # never pick up a system Python (3.14, Store stub, ...)
$env:PLAYWRIGHT_BROWSERS_PATH = "$RT\ms-playwright"
$env:HF_HOME = "$RT\hf"
$env:PYTHONUTF8 = "1"
$uv = "$RT\uv\uv.exe"

# folder downloaded as a ZIP from GitHub: turn it into a git clone once, so menu option 8 can update it
if (-not (Test-Path (Join-Path $Root ".git")) -and -not $NoPrompt) {
    Step "linking this folder to GitHub (for updates; a GitHub sign-in window may open)"
    $gitExe = (Get-Command git).Source
    & $gitExe -C $Root init -q -b main
    & $gitExe -C $Root remote add origin "https://github.com/haseeb109/H-Labs.git"
    & $gitExe -C $Root fetch -q origin main
    if ($LASTEXITCODE -eq 0) {
        & $gitExe -C $Root reset -q --hard origin/main
        & $gitExe -C $Root branch -q --set-upstream-to=origin/main main
        Ok "linked - updates work through menu option 8"
    } else {
        Remove-Item (Join-Path $Root ".git") -Recurse -Force
        Warn "could not reach the GitHub repo (no access / not signed in). The tool works, but option 8 cannot update it."
    }
}

# ---- 2. Python + locked packages ----
Step "Python 3.12 + packages from uv.lock (first time: a few minutes)"
$venvMark = Join-Path $Root ".venv\.hlabs-uv"
if ((Test-Path (Join-Path $Root ".venv")) -and -not (Test-Path $venvMark)) {
    Write-Host "  replacing the old .venv (made by the previous installer) with a locked one"
    Remove-Item (Join-Path $Root ".venv") -Recurse -Force
}
& $uv sync --frozen --inexact --project $Root
if ($LASTEXITCODE -ne 0) { Fail "installing the Python packages failed (see above)" }
Set-Content -Path $venvMark -Value "uv" -Encoding Ascii
$py = Join-Path $Root ".venv\Scripts\python.exe"
Write-Host "  newest yt-dlp (YouTube changes often) ..."
& $uv pip install --no-config --python $py --upgrade "yt-dlp[default]"   # --no-config: the package date cutoff in pyproject must not hold yt-dlp back
if ($LASTEXITCODE -ne 0) { Fail "installing yt-dlp failed" }
Ok "python $(& $py -c "import platform; print(platform.python_version())")"

# ---- 3. graphics browser ----
Step "Chromium for the graphics"
& $py -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Fail "Chromium download failed" }
Ok "chromium"

# ---- 4. optional extras (a failure here never stops the setup) ----
Step "optional extras"
$face = Join-Path $Root "models\blaze_face_short_range.tflite"
if (-not (Test-Path $face)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "models") | Out-Null
    try {
        Invoke-WebRequest -UseBasicParsing -OutFile $face -Uri "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
        Ok "face model (thumbnails)"
    } catch { Warn "face model download skipped (thumbnails still work, without face placement)" }
} else { Ok "face model (thumbnails)" }
if (Test-Path "$RT\node\hyperframes.cmd") { Ok "hyperframes (Trial Tales motion labels)" } else {
    try {
        & "$RT\node\npm.cmd" install -g --prefix "$RT\node" hyperframes --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw "npm failed" }
        & "$RT\node\hyperframes.cmd" browser ensure
        if ($LASTEXITCODE -ne 0) { throw "browser ensure failed" }
        Ok "hyperframes (Trial Tales motion labels)"
    } catch { Warn "hyperframes skipped (only Trial Tales motion labels need it)" }
}

# ---- 5. API keys (only these two; they stay on this PC, never in the folder or on GitHub) ----
Step "API keys"
$kd = Join-Path $env:USERPROFILE ".config\umf"
New-Item -ItemType Directory -Force -Path $kd | Out-Null
foreach ($k in @(@("hive.env", "HIVE_API_KEY", "Hive"), @("ai33.env", "AI33_API_KEY", "ai33 (AI voice)"))) {
    $f = Join-Path $kd $k[0]
    $cur = ""
    if (Test-Path $f) {
        $line = Get-Content $f | Where-Object { $_ -match "^\s*$($k[1])\s*=" } | Select-Object -First 1
        if ($line) { $cur = ($line -split "=", 2)[1].Trim().Trim('"') }
    }
    if ($cur) { Ok "$($k[2]) key is set"; continue }
    $val = ""
    if (-not $NoPrompt) { $val = (Read-Host "  Paste the $($k[2]) key (Enter = later, via menu option 4)").Trim() }
    Write-NoBom $f "$($k[1])=$val`r`n"
    if ($val) { Ok "$($k[2]) key saved" } else { Warn "$($k[2]) key is still empty - add it later with menu option 4" }
}

# ---- 6. final check ----
Step "checking the installation"
& $py (Join-Path $Root "tools\launcher.py") --check
$fails = $LASTEXITCODE
if (Test-Path $DL) { Remove-Item $DL -Recurse -Force -ErrorAction SilentlyContinue }   # installed archives are not needed any more
Write-Host ""
if ($fails -eq 0) {
    Write-Host "===== READY =====  Double-click  H Labs.bat  to start." -ForegroundColor Green
} else {
    Write-Host "===== $fails problem(s) above =====  Fix the [FAIL] lines (empty key: menu option 4), then run the check again (menu option 7)." -ForegroundColor Yellow
}
exit 0
