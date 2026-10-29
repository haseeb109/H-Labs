# H Labs on Windows (for the team)

Development happens on the owner's Mac and is pushed to GitHub. The team runs the tool on Windows from the same repo,
so everyone always has the same code. Nobody edits code on the Windows PCs: menu option 8 updates them.

**PC that fits:** Windows 10/11 64-bit, 16 GB RAM, 100+ GB free disk (a 3 h stream is ~1-3 GB plus temp files).
An NVIDIA GPU makes the final encode much faster (the tool uses NVENC automatically); without one it uses the CPU (slower, same quality).

## First time on a PC (about 15-20 minutes, mostly downloads)

Nothing is installed on the PC itself: no admin rights, no winget, no PATH changes. `Setup.bat` puts exact, pinned versions of
everything (Python 3.12, ffmpeg 8.0.1, Node.js, Chromium, the Python packages from `uv.lock`) **inside the H Labs folder**
(`runtime\` and `.venv\`), so every laptop gets the same set-up, whatever is or is not installed on it.

1. **Get the code** into a short folder (not inside Desktop/OneDrive), e.g. `C:\HLabs`. Either:
   * with Git (if the PC has it): `cd C:\` then `git clone https://github.com/haseeb109/H-Labs.git HLabs`, or
   * without Git: on github.com open the repo -> **Code -> Download ZIP**, unzip it to `C:\HLabs`.
     Setup links the folder to GitHub for updates (a GitHub sign-in window may open once).
   The repo is private: the GitHub account needs access to it.
2. **Double-click `Setup.bat`.** It downloads and checks everything, asks for the two API keys (Hive + ai33; the owner gives them,
   they are never in the repo or in chat; press Enter to add them later with option 4) and ends with **READY** or a short list of
   what is still missing.
3. Double-click **`H Labs.bat`**. Option **7** (Setup check) should show `[ok]` everywhere; `[WARN]` lines are optional parts.

**PC that was set up with the old installer (`install_windows.bat`):** do option 8 once (or `git pull`), then double-click `Setup.bat`.
It replaces the old `.venv` automatically. Python / ffmpeg / Git installed earlier with winget can stay; the tool no longer uses them.

**Broken install / strange error after an update:** just run `Setup.bat` again. To start completely clean, delete the
`runtime` and `.venv` folders first (your videos in `output\` and the keys are not touched).

## Every day

* Double-click `H Labs.bat`.
* Option **8** updates everything: the newest code from GitHub, any new pinned tool or package, and the newest yt-dlp.
  Do this before starting work. The window re-opens by itself afterwards.
* Option **1**: paste the YouTube stream URL -> pick the style -> pick the mode -> answer the voice question -> wait.
  Videos land in `output\<date>_<stream id>\`.
* The first video on a new PC downloads the speech-recognition model once (a few hundred MB, into `runtime\hf`).

## End of a run
* A Windows notification + sound says the run is done (or that it stopped on an error), and the output folder opens.
* The window shows **PROCESSING TIME** (total + every stage); `state\run_history.csv` keeps one line per run.
* `UPLOAD_LIST.txt` in the output folder: the videos in upload order (best first) with title, backup title, length, QC and a
  checklist, plus the cases that need review.
* **Disk space is freed automatically** at the end of every run (no question). Deleted: only the downloaded stream
  (`work\<id>\source.mp4`, 1-3 GB) and the render temp files (`_work` folders); the window lists what was deleted. Never deleted:
  the finished videos, thumbnails, metadata, transcript, plan and the AI-voice cache. (Rendering the same stream again downloads it
  again, ~2 min.) `"cleanup_after_run": "ask"` or `"never"` in `config.json` changes this.

## Watermark
Every video gets the channel name as a small, faint (25%) watermark that moves to a new place every 9 seconds, in all styles. It runs
on Windows exactly like on the Mac (nothing extra to install; option 7 shows `watermark: ... ready`). It is applied automatically after
each video is rendered, so rendering takes a few minutes longer. Only the owner switches it off (`watermark: false` in `config.json`).

## Styles in the menu
`trial_tales`, `overruled`, `court_beacon`, `justice_served` (and any new style the owner pushes; it shows up after option 8).

## Good to know
* **Download from YouTube needs a normal home/office internet connection** (not a VPS / cloud PC): YouTube blocks data-centre IPs.
* **Captions** (burned-in word captions) are Mac-only for now (they need Apple's mlx-whisper). On Windows they stay off.
* **Keep 100 GB free**; delete old `work\<stream id>\` folders when a stream is finished.
* Antivirus can slow ffmpeg a lot: ask IT to exclude the `C:\HLabs` folder if renders are very slow.
* If something fails, send the owner the last 30 lines of the window and the result of option 7.
* Do not edit files inside the repo on the PC; if you must, tell the owner (local edits can block the update).
* For the owner: a new Python package goes into `pyproject.toml`, then run `uv lock` and commit both files; a new ffmpeg / Node / uv
  version is a new pin (version, URL, SHA-256) at the top of `tools/win/setup.ps1`. The next option 8 installs it on every PC.
