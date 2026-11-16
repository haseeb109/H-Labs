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

## After every update: the smoke test (2-3 minutes)
Every update and every `Setup.bat` ends with it, and menu **6** runs it any time (`1) quick smoke` - Enter; `2)` is the long
self-test). It checks on THIS PC what only a real run used to find: the packages and their Windows DLLs load (Smart App Control),
ffmpeg + ffprobe, which encoder a run will use (a 2-second NVENC/x264 test encode + GPU decode), whisper on a 3-second clip in a
child process (the `0xC0000005` crash), both API keys present and ai33 + Hive reachable, a download that really offers 720p+, a
10-second test render with the watermark, and the free disk space. Every line is `[ok]` or `[FAIL] <what to do>`; the result is
kept in `state\smoke_last.json` (the Studio shows a failing check under *Needs attention*).
* All `[ok]` -> **READY**, the PC is good for a run.
* A `[FAIL]` -> the update is installed but something on this PC is wrong: fix what the line says (usually `Setup.bat` again, the
  NVIDIA driver, a key, or disk space), or go back with menu **u** (below) and tell the owner.

## Undo an update (menu u)
A new build that breaks this PC is not a lost day: menu **u) Undo the last update** puts the PC back on the build it ran before -
the code *and* the Python packages of that build (`uv.lock`), and prints `you are on the previous build`. Your videos, keys and
`state\` files are untouched. **Menu 8 returns to the newest build** whenever the owner has pushed a fix.
The last 3 good builds are remembered in `runtime\last_good.txt`. A build is only recorded as "good" when its smoke test passed,
so option u never sends the PC back to a build that was already broken.

**Broken install / strange error after an update:** just run `Setup.bat` again. To start completely clean, delete the
`runtime` and `.venv` folders first (your videos in `output\` and the keys are not touched).

## Every day

* Double-click `H Labs Studio.bat` for the browser app (below), or `H Labs.bat` for the menu.
* Option **8** updates everything: the newest code from GitHub, any new pinned tool or package, and the newest yt-dlp.
  Do this before starting work. It prints the old and the new version (`updated: H Labs v... -> v...`, or `no new code`), ends
  with the smoke test (below) and the window re-opens by itself afterwards. A PC that sits on an old branch or on a build from
  option **u** is put back on `main` first (it says so loudly); if files in the folder are edited it stops and prints the two
  `git` commands to run - a setting belongs in `config.local.json`, never in `config.json`.
* Option **1**: paste the YouTube stream URL -> pick the style -> pick the mode -> answer the voice question -> wait.
  Many streams: option **9** (bulk queue). Clips for your editor: the last entry of the channel-template list (see below).
  Videos land in `output\<date>_<stream id>\`.
* The first video on a new PC downloads the speech-recognition model once (a few hundred MB, into `runtime\hf`).

## H Labs Studio (browser app) - the easiest way
Double-click **`H Labs Studio.bat`** (or menu **0** in `H Labs.bat`). A black window opens (keep it open - it does the work) and
the browser shows the Studio at `http://127.0.0.1:8765` (only this PC can open it).
* **New run**: paste 1, 5 or 20 stream links (one per line) -> **Check links** (title, length, quality - a stream still live or
  below 720p is skipped) -> pick the channel template -> pick the output (30 min / 1 hour / one video per case / clips + editor
  guide) -> **Add to the queue**. You can add more links to the same queue any time, with another template.
* **Queue**: the stream that is running (download -> transcript -> plan -> render video 2 of 5 -> finish, with % and time left),
  the streams waiting (move up/down, remove), and the finished ones. **Pause after this stream**, **Stop**, **Retry** (when one
  video of a stream failed, Retry makes only that video again - the download and plan are kept), **Open** the output folder.
* **Library**: every finished video with its thumbnail, QC result, titles (Copy), description / chapters / tags or the editor
  guide (Copy all) and an upload checklist. **Mark as uploaded** moves it out of "Ready to upload".
* Closed the window by accident? Open the Studio again: the queue goes on from the stream that was running.
* The Studio runs the same pipeline as the menu (same quality, same cleanup); the menu still works as before.

## Your own video, 5 min cases, As-is re-edit
* **Your own downloaded video** (no download): in Studio > New run put its path on a line instead of a link, e.g.
  `D:\Streams\Smith hearing` (a folder) or `D:\Streams\Smith hearing\Smith.mp4` (the file) -> **Check**. In a folder the
  biggest video is used, and its transcript when one is there (`.json` / `.json3` / `.vtt` / `.srt`; one named like the video
  wins). No transcript -> whisper makes one. Menu: option **2**. Your file is never moved, changed or deleted.
* **Shortest case 5 or 8 minutes**: for "One video per case" and "Clips" (Studio: *Shortest case*; menu: asked after the
  mode). 8 is the default. A 5-minute run keeps its own plan, so the 8-minute plan of the same stream is not mixed in.
* **As-is re-edit** (Studio output *As-is re-edit*, menu mode **4**): for a single video link or your own file. The WHOLE video
  becomes ONE fully edited video in the chosen template (hook, overlays, cards, voice-over, titles), exactly as it is: no case
  selection, nothing skipped, rejected or cut out, whether it holds one hearing or three.

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

What keeps the render light (2026-11-15):
* every video is encoded **once**: the moving watermark (and the Trial Tales cards) are drawn inside the segment renders, there
  is no second pass over the finished video any more
* background pictures and graphic layers are decoded once per piece, not again for every frame
* a Zoom layout change cuts the piece per layout instead of running every layout on every frame
* the AI voice of the next videos is made in the background while the GPU renders
* the finished video is joined and its loudness measured in the same step (QC does not read it again)

**H Labs on a hard disk (HDD) and a small SSD in the PC?** Put the render pieces on the SSD: in `config.local.json`
```json
{ "render_temp_dir": "C:/HLabsTemp" }
```
The finished videos stay in `output\`; only the pieces (deleted after each run) go to the SSD. Needs 15 GB free there, else
the tool quietly keeps the pieces next to the video as before.

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
* **yt-dlp: newest with a safe fallback.** YouTube changes often, so every update installs the **newest** yt-dlp first and then
  probes it (does it still read a video?). If the probe fails - a bad yt-dlp release would otherwise break every laptop at once -
  Setup installs the known-good version from `tools/win/ytdlp_pin.txt` instead and says why. `runtime\ytdlp_active.txt` holds
  which one is in use, and a failed download names it. The owner raises the pinned version when a newer one has proven itself.
* **Quality rule: never below 720p.** The tool downloads the best quality YouTube has (720p+). If a YouTube client only offers
  360p it tries the next way; if no 720p copy can be had it stops with a message instead of making soft videos.
* **Download from YouTube needs a normal home/office internet connection** (not a VPS / cloud PC): YouTube blocks data-centre IPs.
* **Captions** (burned-in word captions) are Mac-only for now (they need Apple's mlx-whisper). On Windows they stay off.
* **Keep 100 GB free**; delete old `work\<stream id>\` folders when a stream is finished.
* Antivirus can slow ffmpeg a lot: ask IT to exclude the `C:\HLabs` folder if renders are very slow.
* If something fails, send the owner the last 30 lines of the window and the result of option 7.
* Do not edit files inside the repo on the PC; if you must, tell the owner (local edits can block the update).
* For the owner: the yt-dlp fallback version is `tools/win/ytdlp_pin.txt` (one line, e.g. `2026.10.26`); a new Python package goes into `pyproject.toml`, then run `uv lock` and commit both files; a new ffmpeg / Node / uv
  version is a new pin (version, URL, SHA-256) at the top of `tools/win/setup.ps1`. The next option 8 installs it on every PC.
