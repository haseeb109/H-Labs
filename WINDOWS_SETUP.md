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

**"An Application Control policy has blocked this file" (Windows Smart App Control):** run `Setup.bat` again. It notices
the block and rebuilds the tool on the signed python.org Python 3.12 (installs it with winget if the PC has none). Only if
Windows still blocks the packages after that, Smart App Control has to be switched off (Windows Security -> App & browser
control -> Smart App Control settings -> Off; it cannot be switched back on without resetting Windows) - or ask IT.

**Broken install / strange error after an update:** just run `Setup.bat` again. To start completely clean, delete the
`runtime` and `.venv` folders first (your videos in `output\` and the keys are not touched).

## Every day

* Double-click `H Labs.bat`.
* Option **8** updates everything: the newest code from GitHub, any new pinned tool or package, and the newest yt-dlp.
  Do this before starting work. The window re-opens by itself afterwards.
* Option **1**: paste the YouTube stream URL -> pick the style -> pick the mode -> answer the voice question -> wait.
  Many streams: option **9** (bulk queue). Clips for your editor: the last entry of the channel-template list (see below).
  Videos land in `output\<date>_<stream id>\`.
* The first video on a new PC downloads the speech-recognition model once (a few hundred MB, into `runtime\hf`).

## Clips only (last entry of the template list)
For channels where your own editor finishes the video. In the channel-template list pick the last entry, **CLIPS ONLY**,
then the channel the clips are for (its name and title style go into the guide). There is no mode question: every verified
case of 8:00 or more becomes a clip:
* `clip.mp4`: the hook (10-20 s, from inside the case) + the whole case, dead air cut out. Native resolution (no upscale),
  frame-accurate cuts, H.264 (opens in Premiere / CapCut / Resolve). No overlays, no AI voice, no graphics, no watermark.
* `EDITOR_GUIDE.txt`: what the full render would have added, with **clip** timestamps: the hook title text, every text overlay
  (time, position, text), the Subscribe CTAs, the closing voice-over script (paste it into any TTS), titles, thumbnail text,
  description, chapters, tags, and the list of cuts (source times).
* `thumbnail_frame_*.jpg`: frame candidates for the thumbnail.
The output folder ends with `_clips`. No ai33 credits are used. Settings: `clips_dead_air_s` (10 s), `clips_crf` (14).

## Bulk queue (menu 9)
Paste many stream links at once (one per line, or a `.txt` file with the links), pick the style and the mode once, and leave the PC
on. The streams run one after the other until the list is done; each finished stream is cleaned up, so the disk does not fill.
A link that fails (still live, private, brain could not plan it) is noted in `state\queue_failed.txt` and the queue goes on.
Closed the window by accident? Menu 9 again offers to continue the remaining links. One notification when the whole queue is done.

## Settings for one PC only: config.local.json
Never edit `config.json` on a team PC (an edited file blocks menu 8). Put this PC's own settings in `config.local.json` next to it
instead (it is not in git, it overrides config.json), for example:
```
{ "x264_preset": "fast", "cpu_threads": 6 }
```
Useful keys: `x264_preset` (CPU encode speed: medium / fast / veryfast), `cpu_threads` (0 = 75% of the cores), `process_priority`
(below_normal / normal), `hw_decode` (auto / off), `brain_parallel_b` (3), `cleanup_after_run` (always / ask / never).

## GPU / CPU load
Option 7 shows `video encoder` and `video decode`. With an NVIDIA GPU and a driver of version 570 or newer both say GPU
(h264_nvenc + cuda): the GPU encodes and decodes the video, the CPU only does the graphics and filters. With `libx264` the CPU does
everything; the tool then uses 75% of the cores at low priority so the PC stays usable. Old driver? Update it from nvidia.com
(GeForce 10 series and newer: Studio driver), restart, check option 7 again.

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
