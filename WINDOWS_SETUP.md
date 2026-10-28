# H Labs on Windows (for the team)

Development happens on the owner's Mac and is pushed to GitHub. The team runs the tool on Windows from the same repo,
so everyone always has the same code. Nobody edits code on the Windows PCs: you only `git pull` to update.

**PC that fits:** Windows 10/11 64-bit, 16 GB RAM, 100+ GB free disk (a 3 h stream is ~1-3 GB plus temp files).
An NVIDIA GPU makes the final encode much faster (the tool uses NVENC automatically); without one it uses the CPU (slower, same quality).

## First time on a PC (about 15 minutes)

1. **Get the code.** Install Git for Windows (https://git-scm.com), then in a short folder (not deep inside Desktop/OneDrive):
   ```
   cd C:\
   git clone https://github.com/haseeb109/H-Labs.git HLabs
   ```
   The repo is private: Git asks you to sign in to GitHub once. The account needs access to the repo.
2. **Install everything.** Double-click `install_windows.bat` in `C:\HLabs`.
   It installs Python 3.12, ffmpeg, Node.js and Git with winget (if missing), builds the `.venv`, installs the Python packages,
   Chromium (for the graphics) and creates empty key files in `C:\Users\<you>\.config\umf\`.
   If it says some tools were just installed, **close the window and run it again** (Windows needs a new window to see them).
3. **Add the API keys** (the owner gives you these, they are never in the repo or in chat):
   double-click `H Labs.bat` -> option **4**, paste each key after the `=` and save.
   Needed: `hive.env` (the brain), `ai33.env` (the AI voice). The others are optional backups.
4. **Check.** `H Labs.bat` -> option **7** (Setup check). Everything should say `[ok]`.
   `[WARN]` for the optional parts (anthropic/deepseek/openai keys, faster_whisper) is fine. `[FAIL]` must be fixed first.

## Every day

* Double-click `H Labs.bat`.
* Option **8** updates the tool from GitHub (`git pull`). Do this before starting work, so you have the owner's latest styles and fixes.
* Option **1**: paste the YouTube stream URL -> pick the style -> pick the mode -> answer the voice question -> wait.
  Videos land in `output\<date>_<stream id>\`.

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
* Do not edit files inside the repo on the PC; if you must, tell the owner (local edits can block `git pull`).
