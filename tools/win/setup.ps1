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
#   runtime\whisper_gpu.txt   'on' / 'off': whisper on the NVIDIA GPU (optional ~1.4 GB of CUDA libraries, asked once)
#   .venv               Python packages from uv.lock (+ the newest yt-dlp, or the pinned one when the newest is broken)
#   runtime\last_good.txt   the builds to go back to (menu u -> -Rollback)     runtime\ytdlp_active.txt  which yt-dlp is in use
#
# Change a pinned tool: edit $Pins below (version, url, sha256) and commit; the next update installs it everywhere.
# The yt-dlp fallback version is tools\win\ytdlp_pin.txt (a known-good release; the newest is still tried first).
# Every -Update / -Rollback / fresh setup ends with tools\smoke_test.py: 2-3 minutes that prove THIS PC still makes videos.
param([switch]$Update, [switch]$Rollback, [switch]$NoPrompt)

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

# ---- 0. update / rollback: change the code first, then run the NEW setup script (it may pin new versions) ----
# state\*.json is written by every run; older versions tracked it in git, so a local change blocked the pull. Keep a copy, reset
# the tracked copies, change the code, and put this PC's own state back.
function Save-State {
    $stBak = Join-Path $RT "_state_backup"
    if (Test-Path $stBak) { Remove-Item $stBak -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $stBak | Out-Null
    Get-ChildItem (Join-Path $Root "state") -File -ErrorAction SilentlyContinue | Copy-Item -Destination $stBak
    return $stBak
}
function Restore-State($stBak) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "state") | Out-Null
    Get-ChildItem $stBak -File | Copy-Item -Destination (Join-Path $Root "state") -Force
    Remove-Item $stBak -Recurse -Force
}
if ($Update -or $Rollback) {
    $g = Get-Command git -ErrorAction SilentlyContinue
    $gitExe = if ($g) { $g.Source } elseif (Test-Path "$RT\git\cmd\git.exe") { "$RT\git\cmd\git.exe" } else { $null }
    $py0 = Join-Path $Root ".venv\Scripts\python.exe"
    $launcher = Join-Path $Root "tools\launcher.py"
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"      # git writes progress to stderr
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        Warn "this folder was not cloned with git (downloaded as ZIP?) - code update skipped. Clone it once with git to get updates."
    } elseif (-not $gitExe) {
        Warn "git not found - code update skipped (run Setup.bat once, it installs a portable git)"
    } elseif (-not (Test-Path $py0)) {
        Warn "this PC has no .venv yet - run Setup.bat once (it installs everything); nothing to update or undo"
    } elseif ($Rollback) {
        Step "going back to the previous build (menu u)"
        # the git part (last good commit from runtime\last_good.txt, state\ kept) lives in the launcher, same as on Mac / Linux
        $stBak = Save-State
        & $py0 $launcher --rollback-git
        $rb = $LASTEXITCODE
        Restore-State $stBak
        if ($rb -ne 0) { Fail "could not go back (see above). Nothing was changed." }
    } else {
        Step "getting the newest code from GitHub"
        $env:Path = "$RT\git\cmd;" + $env:Path
        $was = ""
        if (Test-Path $py0) {
            & $py0 $launcher --record-last-good                               # the build we leave = the one menu u returns to
            $was = (& $py0 $launcher --version-commit | Out-String).Trim()    # "<version> <short commit>" before the pull
        }
        $stBak = Save-State
        $tracked = & $gitExe -C $Root ls-files state
        if ($tracked) { & $gitExe -C $Root checkout -- state }
        # a PC on an old branch (justice-served, quality-fix, stable ...) or on a rolled-back build gets "Already up to date"
        # from the pull and keeps running old code: switch it back to the main branch first (or say what to run)
        $canPull = $true
        if (Test-Path $py0) {
            & $py0 $launcher --ensure-main
            $canPull = ($LASTEXITCODE -eq 0)
        }
        if ($canPull) {
            & $gitExe -C $Root pull --ff-only
            if ($LASTEXITCODE -ne 0) { Warn "git pull failed (local edits in the folder? see the message above). Setup continues with the current code." }
        } else {
            Warn "the code was NOT updated (see the lines above) - setup continues with the code that is in the folder"
        }
        Restore-State $stBak
        if ($was -and (Test-Path $py0)) {
            $now = (& $py0 $launcher --version-commit | Out-String).Trim()
            if ($now -eq $was) { Warn "no new code: still H Labs v$was - this PC was already up to date" }
            else { Ok "updated: H Labs v$was  ->  v$now" }
        }
    }
    $ErrorActionPreference = $old
    # the setup of the code that is now in the folder: packages matching its uv.lock, pinned tools, and the smoke test at the end
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "tools\win\setup.ps1") -NoPrompt
    $rc = $LASTEXITCODE
    if ($Rollback) {
        Write-Host ""
        Write-Host "===== PREVIOUS BUILD =====  You are on the previous build (H Labs v$((Get-Content (Join-Path $Root 'VERSION') -Raw).Trim())). Menu option 8 returns to the newest." -ForegroundColor Yellow
    }
    exit $rc
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
$py = Join-Path $Root ".venv\Scripts\python.exe"
# Windows Smart App Control / Application Control blocks the unsigned files of the Python that uv downloads
# ("DLL load failed while importing _socket: An Application Control policy has blocked this file"). On such a PC the venv is
# built on the SIGNED python.org Python 3.12 instead; runtime\python-signed.txt remembers that for every later update.
$sysMark = Join-Path $RT "python-signed.txt"
$sysPy = $null
if (Test-Path $sysMark) { $sysPy = (Get-Content $sysMark -Raw).Trim(); if (-not (Test-Path $sysPy)) { $sysPy = $null } }

function Sync-Venv {
    if ($sysPy) {
        $env:UV_PYTHON_PREFERENCE = "only-system"
        & $uv sync --frozen --inexact --project $Root --python $sysPy
    } else {
        $env:UV_PYTHON_PREFERENCE = "only-managed"
        & $uv sync --frozen --inexact --project $Root
    }
    if ($LASTEXITCODE -ne 0) { Fail "installing the Python packages failed (see above)" }
    Set-Content -Path $venvMark -Value "uv" -Encoding Ascii
    Install-YtDlp
}

function Install-YtDlp {
    # Newest first (YouTube changes often), then a 20 s probe: does it read a video? A broken release would hit every laptop at
    # once, so when the probe fails the known-good version from tools\win\ytdlp_pin.txt is installed instead.
    # runtime\ytdlp_active.txt says which one is in use (the download error and the smoke test print it).
    $pinFile = Join-Path $Root "tools\win\ytdlp_pin.txt"
    $pin = if (Test-Path $pinFile) { (Get-Content $pinFile -Raw).Trim() } else { "" }
    $active = Join-Path $RT "ytdlp_active.txt"
    $probe = Join-Path $Root "tools\smoke_test.py"
    Write-Host "  newest yt-dlp (YouTube changes often) ..."
    & $uv pip install --no-config --python $py --upgrade "yt-dlp[default]"   # --no-config: the package date cutoff in pyproject must not hold yt-dlp back
    if ($LASTEXITCODE -ne 0) { Fail "installing yt-dlp failed" }
    $ver = (& $py -m yt_dlp --version 2>$null | Out-String).Trim()
    if (-not (Test-Path $probe)) { Ok "yt-dlp $ver (newest; this build has no probe)"; return }   # an older build after menu u
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $out = (& $py $probe --ytdlp-probe 2>&1 | Out-String).Trim()
    $okProbe = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    if ($okProbe) {
        Set-Content -Path $active -Value "$ver newest" -Encoding Ascii
        Ok "yt-dlp $ver (newest, reads YouTube)"
        return
    }
    $why = ($out -split "`n" | Select-Object -Last 1).Trim()
    Warn "the newest yt-dlp ($ver) does not read YouTube on this PC: $why"
    if (-not $pin) { Warn "no pinned yt-dlp version in tools\win\ytdlp_pin.txt - keeping the newest"; return }
    Write-Host "  installing the known-good yt-dlp $pin instead ..."
    & $uv pip install --no-config --python $py "yt-dlp[default]==$pin"
    if ($LASTEXITCODE -ne 0) { Fail "installing yt-dlp $pin failed" }
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $py $probe --ytdlp-probe 2>&1 | Out-Null
    $okPin = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    Set-Content -Path $active -Value "$pin pinned (the newest, $ver, failed its probe: $why)" -Encoding Ascii
    if ($okPin) { Ok "yt-dlp $pin (pinned fallback)" }
    else { Warn "yt-dlp $pin does not read YouTube either - no internet, or YouTube blocks this connection (VPN / cloud PC?)" }
}

function Test-Imports {
    # -> "" when Python + the main packages load, else the error text
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $out = & $py -c "import socket, ssl, ctypes, sqlite3, unicodedata, numpy, PIL.Image, av, yt_dlp, Cryptodome.Cipher.AES; print('IMPORT-OK')" 2>&1 | Out-String
    $ErrorActionPreference = $old
    if ($out -match "IMPORT-OK") { return "" } else { return $out }
}

function Find-SignedPython {
    $c = @()
    try { $p = & py -3.12 -c "import sys; print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $c += ([string]$p).Trim() } } catch { }
    $c += (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    $c += (Join-Path $env:ProgramFiles "Python312\python.exe")
    foreach ($x in $c) {
        if ($x -and (Test-Path $x) -and ($x -notmatch "WindowsApps") -and (-not $x.StartsWith($Root))) { return $x }
    }
    return $null
}

if ((Test-Path (Join-Path $Root ".venv")) -and -not (Test-Path $venvMark)) {
    Write-Host "  replacing the old .venv (made by the previous installer) with a locked one"
    Remove-Item (Join-Path $Root ".venv") -Recurse -Force
}
Sync-Venv
$why = Test-Imports
if ($why -and -not $sysPy -and ($why -match "Application Control|blocked")) {
    Warn "Windows Smart App Control blocks the downloaded Python - switching to the signed python.org Python 3.12"
    $sysPy = Find-SignedPython
    if (-not $sysPy) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Fail "install Python 3.12 from python.org (Windows installer, 'Install for me only'), then run Setup.bat again"
        }
        Write-Host "  installing Python 3.12 from python.org (signed) with winget ..."
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        & winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
        $ErrorActionPreference = $old
        $sysPy = Find-SignedPython
        if (-not $sysPy) { Fail "Python 3.12 could not be installed - install it from python.org ('Install for me only'), then run Setup.bat again" }
    }
    Ok "signed Python: $sysPy"
    Set-Content -Path $sysMark -Value $sysPy -Encoding Ascii
    Remove-Item (Join-Path $Root ".venv") -Recurse -Force
    Sync-Venv
    $why = Test-Imports
}
if ($why) {
    if ($why -match "Application Control|blocked") {
        Write-Host ""
        Write-Host $why
        Fail ("Windows Smart App Control blocks Python package files on this PC (no signed version of them exists, so no setup can work around it). " +
              "Turn it off: Windows Security -> App & browser control -> Smart App Control settings -> Off " +
              "(it cannot be switched back on without resetting Windows), or ask your IT. Then run Setup.bat again.")
    }
    Fail ("Python does not start correctly:`n" + $why)
}
Ok "python $(& $py -c "import platform; print(platform.python_version())")"

# ---- 2b. Microsoft C++ runtime: the whisper engines (onnxruntime, ctranslate2) use the system msvcp140.dll and crash with
# 0xC0000005 when it is older than 14.40 (a new PC, 2026-11-15). Always the newest from Microsoft (aka.ms), so instead of a
# pinned hash the download must carry a valid Microsoft signature.
Step "Microsoft Visual C++ runtime (for whisper)"
function Get-VCVersion {
    $f = Join-Path $env:SystemRoot "System32\msvcp140.dll"
    if (-not (Test-Path $f)) { return $null }
    $v = (Get-Item $f).VersionInfo
    return [version]("{0}.{1}.{2}.{3}" -f $v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart, $v.FilePrivatePart)
}
$vcNeed = [version]"14.40.0.0"
$vc = Get-VCVersion
if ($vc -and $vc -ge $vcNeed) { Ok "Visual C++ runtime $vc" } else {
    Write-Host "  this PC has $(if ($vc) { "version $vc" } else { 'none' }) - installing the current one from Microsoft"
    Write-Host "  Windows asks for permission now - click YES." -ForegroundColor Yellow
    $exe = Join-Path $env:TEMP "hlabs_vc_redist.x64.exe"
    try {
        Invoke-WebRequest -UseBasicParsing -OutFile $exe -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        $sig = Get-AuthenticodeSignature $exe
        if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=Microsoft Corporation") {
            throw "the download is not signed by Microsoft ($($sig.Status))"
        }
        $p = Start-Process -FilePath $exe -ArgumentList "/install", "/passive", "/norestart" -Verb RunAs -Wait -PassThru
        if ($p.ExitCode -eq 3010) { Warn "installed - restart the PC once after setup" }
        elseif ($p.ExitCode -ne 0 -and $p.ExitCode -ne 1638) { Warn "the installer ended with code $($p.ExitCode)" }
    } catch { Warn "Visual C++ runtime install failed: $($_.Exception.Message)" }
    Remove-Item $exe -Force -ErrorAction SilentlyContinue
    $vc = Get-VCVersion
    if ($vc -and $vc -ge $vcNeed) { Ok "Visual C++ runtime $vc" }
    else { Warn "still old/missing - install it by hand: https://aka.ms/vs/17/release/vc_redist.x64.exe (then run Setup.bat again)" }
}

# whisper canary: load both native engines in a child process (the voice filter runs a real onnxruntime model).
$old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$wout = & $py -c "import numpy as np; from faster_whisper.vad import get_speech_timestamps; get_speech_timestamps(np.zeros(32000, dtype=np.float32)); import ctranslate2; ctranslate2.get_supported_compute_types('cpu'); print('WHISPER-OK')" 2>&1 | Out-String
$wcode = $LASTEXITCODE
$ErrorActionPreference = $old
if ($wout -match "WHISPER-OK") { Ok "whisper engines load" }
else { Warn ("whisper engines crash on this PC (exit code 0x{0:X8}) - videos with YouTube captions still work; restart the PC and run Setup.bat again. {1}" -f $wcode, ($wout.Trim() -split "`n" | Select-Object -Last 1)) }

# ---- 2c. whisper on the GPU (optional): the CUDA libraries are a big extra download, so only with an NVIDIA GPU AND a yes ----
# The answer lives in runtime\whisper_gpu.txt ("on" / "off"). A fresh setup asks once; -NoPrompt (every update) keeps the answer,
# and without an answer it stays off. The run itself checks the GPU and the libraries again (ucf\transcript.py) and falls back to
# the CPU with one line when anything is wrong, so a "yes" can never make a transcript fail.
Step "whisper on the GPU (optional)"
$gpuFile = Join-Path $RT "whisper_gpu.txt"
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $smi) {
    Ok "no NVIDIA GPU found - whisper runs on the CPU (nothing to install)"
} else {
    $gpuName = ((& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null | Select-Object -First 1) | Out-String).Trim()
    $want = if (Test-Path $gpuFile) { (Get-Content $gpuFile -Raw).Trim().ToLower() } else { "" }
    if (-not $want -and -not $NoPrompt) {
        Write-Host "  NVIDIA GPU: $gpuName"
        Write-Host "  A stream without YouTube captions is transcribed by whisper: on the CPU 15-25 minutes for a 2.5 hour stream, CPU at 100%."
        Write-Host "  On the GPU it is several times faster and the CPU stays free (the run prints the measured speed)."
        Write-Host "  COST: about 1.4 GB extra download (NVIDIA cuBLAS + cuDNN, about 3 GB on disk) into .venv - once, no admin rights." -ForegroundColor Yellow
        $ans = (Read-Host "  Install whisper for the GPU? (y/N)").Trim().ToLower()
        $want = if ($ans -match "^(y|j)") { "on" } else { "off" }
        Set-Content -Path $gpuFile -Value $want -Encoding Ascii
    }
    if ($want -ne "on") {
        Ok "whisper on the CPU (GPU whisper is off). To turn it on: delete runtime\whisper_gpu.txt and run Setup.bat again."
    } else {
        Write-Host "  installing the CUDA libraries for whisper (about 1.4 GB, first time only) ..."
        if ($sysPy) { $env:UV_PYTHON_PREFERENCE = "only-system"; & $uv sync --frozen --inexact --extra whisper-gpu --project $Root --python $sysPy }
        else { $env:UV_PYTHON_PREFERENCE = "only-managed"; & $uv sync --frozen --inexact --extra whisper-gpu --project $Root }
        $gok = ($LASTEXITCODE -eq 0)
        $gout = ""
        if ($gok) {
            $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
            $gout = & $py -c "from ucf import transcript; transcript.cuda_ready(); print('GPU-WHISPER-OK')" 2>&1 | Out-String
            $ErrorActionPreference = $old
            $gok = ($gout -match "GPU-WHISPER-OK")
        }
        if ($gok) { Ok "whisper will run on the GPU ($gpuName)" }
        else {
            Set-Content -Path $gpuFile -Value "off" -Encoding Ascii
            Warn ("whisper on the GPU does not work on this PC - it stays on the CPU (videos are not affected). " +
                  "Usually the NVIDIA driver is too old (CUDA 12 needs driver 525 or newer): update it from nvidia.com, delete runtime\whisper_gpu.txt, run Setup.bat again. " +
                  (($gout.Trim() -split "`n" | Select-Object -Last 1)))
        }
    }
}

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

# ---- 7. smoke test: 2-3 minutes that prove this PC still makes videos (DLL blocks, whisper crash, NVENC, 360p, ai33 ...).
# The result (state\smoke_last.json) decides whether the next update records this build as "last good" for menu u.
$smokePy = Join-Path $Root "tools\smoke_test.py"
$smoke = 0
if (Test-Path $smokePy) {
    Step "smoke test (2-3 minutes: imports, ffmpeg, encoder, whisper, keys, download, a 10 s render)"
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $py $smokePy
    $smoke = $LASTEXITCODE
    $ErrorActionPreference = $old
}
$firstFail = ""
try {
    $sj = Get-Content (Join-Path $Root "state\smoke_last.json") -Raw | ConvertFrom-Json
    $bad = @($sj.checks | Where-Object { -not $_.ok })
    if ($bad.Count -gt 0) {
        $line1 = ($bad[0].msg -split "`n")[0]
        $firstFail = $bad[0].name + ": " + $line1
    }
} catch { }
Write-Host ""
if ($fails -eq 0 -and $smoke -eq 0) {
    Write-Host "===== READY =====  Double-click  H Labs.bat  to start." -ForegroundColor Green
} elseif ($smoke -ne 0) {
    Write-Host "===== the update is installed but this PC has a problem: $firstFail =====" -ForegroundColor Yellow
    Write-Host "      Fix it (the [FAIL] line says how; menu 6 runs the smoke test again) or use menu u to go back to the previous build." -ForegroundColor Yellow
} else {
    Write-Host "===== $fails problem(s) above =====  Fix the [FAIL] lines (empty key: menu option 4), then run the check again (menu option 7)." -ForegroundColor Yellow
}
exit 0
