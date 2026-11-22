# MASTER PROMPT — "H Labs Playground" (a style-agnostic rebuild of H Labs)

> Paste everything below into a new Claude (Claude Code) session as the first message.
> It describes the current H Labs (v2026.11.15) exactly, and asks for the same tool WITHOUT any built-in channel
> templates: every editing style is a data pack the owner adds later.

---

## 0. Your role and the goal

You are a senior Python engineer building **H Labs Playground**: a local video factory that turns a long YouTube court
livestream (or a video file on disk) into finished, ready-to-upload YouTube videos with no human editing.

It must reproduce the existing H Labs tool feature for feature (pipeline, brain, validation, voice, render quality,
speed work, Studio GUI, Windows install/update, self-tests) with ONE deliberate difference:

**There are no channel templates in the code.** H Labs has four hard-wired looks (Trial Tales, Overruled, Justice Served,
Court Beacon TV), two of them with their own Python renderer. The Playground has ONE generic renderer driven entirely
by a **style pack** (a folder of JSON + assets + prompt text). The repo ships with exactly one neutral demo pack
(`styles/_example`). Adding a new channel look = adding a folder, never editing code.

Work in small, tested steps. After each step: run the self-tests, commit. Ask before anything destructive.

---

## 1. Platform and hard rules

- Runs on the team's **Windows 10/11 laptops** (7th/8th gen Intel, 4–6 GB NVIDIA GPU, often an HDD). Develop anywhere,
  but every path, process and install step must work on Windows first.
- Python 3.12, dependencies locked with **uv** (`pyproject.toml` + `uv.lock`), ffmpeg 8.x, Node 22 (for HyperFrames
  motion graphics), Playwright Chromium (HTML graphics), yt-dlp (always newest, with a pinned fallback).
- **Secrets** only in `~/.config/umf/<name>.env` (`hive.env` → `HIVE_API_KEY`, `ai33.env` → `AI33_API_KEY`). Never in
  the repo, logs, events or the GUI. Never print a key value.
- Per-PC state is never tracked by git: `state/*.json`, `state/*.csv`, `config.local.json`, `work/`, `output/`,
  `input/`, `runtime/`, `.venv/`. (A tracked state file once blocked `git pull` on every laptop.)
- Quality is never traded for speed: the source is never downloaded below 720p (unless the stream has nothing better
  and the owner allowed it), the final video is encoded **once**.
- Every failure says **what** broke, **where** (file:line) and **what to do**, in one line. No `except Exception: pass`.
  "The run finished but the output folder is empty" must be impossible without a printed cause.
- Judge-neutral rule: voice-over and on-screen text say "the judge", never the judge's name (titles/description may
  name the judge). Enforce it in the prompt AND with a script safety net after the plan.

---

## 2. Pipeline (one command: `python run_stream.py <url|--local path> --style <id> --mode <mode>`)

Structure `run_stream.py` as `parse_args()` + a `Run` context object + stage functions:
`stage_setup → stage_info → stage_download → stage_transcript → stage_scan → stage_plan → stage_render`.
A stage returns `STOP` to end early (`--stage <name>` stops after that stage). Write `work/<id>/run_log.txt`
(console tee) and `work/<id>/events.jsonl` (one JSON event per line, flushed: run_start, stage_start/end, download,
transcript, plan, encoder, video_start/done/failed, run_end).

1. **info** – `yt-dlp -J` (try several clients until one lists ≥720p). Refuse a still-live stream. Court line from the
   title ("187th District Court"), never a judge's name.
2. **download** – best video + best audio, VP9 allowed, AV1 excluded, `[height>=720][height<=max_height]`.
   Three strategies (configured clients → yt-dlp default → tv+web_safari). A sub-720p download is kept aside while the
   next strategy tries. A cached download worse than what YouTube offers is re-downloaded (keep the old one if that
   fails). `--local <file|folder>`: use the user's own file (folder → biggest video + matching transcript
   json/json3/vtt/srt); never move/modify/delete it.
3. **transcript** – YouTube captions; if missing or < 15 words/min → **faster-whisper** in a CHILD process (a native
   crash 0xC0000005 must not kill the run): tries GPU (float16, only when opted in and ≥2 GB VRAM free) → CPU int8 with
   VAD → CPU int8 without VAD → CPU float32/2 threads. If all fail but sparse captions exist, continue with them
   (marked, so the next run retries whisper). Print the device and x-realtime.
4. **scan** – candidate case starts ("calling CR####", "cause number"), dead-air stretches, plus boundary evidence
   (call-outs, wrap-up phrases, ruling phrases, optional tile OCR).
5. **plan (the brain)** – Hive API (OpenAI-compatible SSE, model from config). Two-pass for one-video-per-case:
   - **Pass A (inventory):** every case with id, name, in/out, status used/skipped/rejected, charge, facing, the
     question, result, ruling_tc, phases (call/ruling/wrap_up with verbatim evidence), virality factors, gaps.
   - Script step: lengths, min-case rule (5 or 8 min, configurable), virality total + ranking (LIMITED monetisation
     never top 3), overlap/hole autofix, salvage (a case the brain cannot fix is set aside as needs_review; the rest
     continue).
   - **Pass B (packaging, per case, up to 3 in parallel):** hook (in/out/headline), 5 titles (one primary), thumbnail
     window + text, description, chapters, tags, pinned comment, vo_final, quiz, overlays (tc/kind/text/evidence).
   - Every reply goes through the **validator** (rule codes C-xx cases, T-xx titles, O-xx overlays, V-xx video) and up
     to N repair rounds that send back ONLY the latest JSON + the errors; fresh attempts on the same provider; repair
     output capped at 1.3× the previous reply.
   - Modes: `30` / `60` (bundle cases into 20-40 / 50-70 min videos, carry-forward of leftovers), `all` (one ranked video
     per case), `clips` (same plan, output = clean clip + EDITOR_GUIDE.txt), `asis` (the whole video as ONE case, nothing
     skipped), `download` (no plan at all, see §6).
   - Plan file per style + mode (+ min-case) so plans never leak between styles. Manual brain mode = write the prompt to
     a file, accept the pasted JSON.
6. **render** – see §3. Per video: thumbnail, metadata.txt, edit_sheet.txt, footage_log.csv, contact sheet, qc.json
   (duration, LUFS, true peak, notes, ok). One broken video never stops the others; the source is kept when a video
   failed (`--only N` re-renders it). Resume: a per-run progress file skips videos already done (same plan + version).
   End: run_report.txt, UPLOAD_LIST.txt, PROCESSING TIME breakdown, notification, open the folder, cleanup (delete
   ONLY the downloaded source and render temp files, never finished videos or the paid voice cache).

---

## 3. The ONE generic renderer (the core difference)

A video is a **timeline of segments**. The style pack decides which segments exist, in what order, and how each looks;
the renderer only knows segment KINDS:

`hook` · `channel_intro` · `case` (court footage) · `recap` (blurred footage + AI voice) · `card` (still/animated
graphic + voice) · `closing` (final VO + fade) · `broll` (stock footage montage + voice, optional) · `outro`.

**Rendering rules (all measured on real laptops, keep them):**
- Every segment is encoded exactly once (NVENC when it works, else x264 with a thread cap); the finished video is a
  stream-copy concat + loudness normalisation (−14 LUFS, measured in the same pass for QC). No second full-video pass:
  the moving watermark and the overlay cards are drawn **inside** each segment encode.
- Still images (backgrounds, frames, layers) are decoded and colour-converted ONCE per segment
  (`-i img.png` + `format=…,loop=-1:size=1,fps=30,trim=duration=d`), never `-loop 1` per frame.
- Zoom/court layout detection on keyframes (64×36 grey thumbnails) → when the layout changes inside a cut, split the cut
  per layout run (`trim=start_frame/end_frame` + concat), never run every layout branch on every frame.
- GPU decode (NVDEC) when NVENC works; NVENC option levels fall back automatically on old drivers; tell the user when the
  driver is too old for the ffmpeg's NVENC API.
- Pieces in `<video>/_work` with a fingerprint (code + style + plan + watermark settings); optional `render_temp_dir`
  on an SSD (junction on Windows); `+faststart` only on the final file.
- Process priority below-normal (Windows: `SetPriorityClass` with proper `ctypes` HANDLE types), CPU threads 75%.
- Audio: court clean-up chain (high/low pass, compressor, afftdn, gate) on court footage; AI voice clips ≤ 18 s each,
  sped up ≤ 12% or split when longer; voice for the next videos is pre-fetched in the background.

**Style pack format (`styles/<id>/`):**
```
style.json        id, name, canvas (1920x1080, background image or colour), segment order, per-segment layout,
                  fonts, colours, safe zones, overlay card design, label animations, watermark/logo settings,
                  hook/intro/recap/closing durations, title rules file, prompt extra file, b-roll settings
assets/           background PNGs, frames, logo, channel_intro.mp4, fonts, sting audio
graphics/         HTML/CSS templates rendered with Playwright (cards, lower thirds, case card) and HyperFrames
                  motion-label templates; placeholders like {{name}} {{charge}} {{facing}} {{result}}
prompts/          title_rules.md (hooks/patterns/banks), extra.md (packaging/overlay voice for this channel)
README.md         what the look is, a screenshot
```
Layouts are declarative: e.g. `"case": {"footage": {"x":0,"y":270,"w":1920,"h":540,"crop":"auto-zoom-layout"},
"layers": ["frame.png", {"html":"graphics/lower_third.html","show":"0.6-7.0"}]}`. The renderer reads this and builds
the ffmpeg filter graph. Validate every pack on load (unknown key → "did you mean …", missing asset → which file), and
list a broken pack in the menu as "(style.json unreadable: …)" instead of hiding it.

**B-roll (new, optional per pack):** `"broll": {"library": "D:/BRoll", "clip_seconds": 5, "ken_burns": true,
"grade": "…"}`. The library is folders = tags (`police_lights/`, `gavel/`, `jail_cell/` …). Pass B picks a tag per
~5 s beat ONLY from the tags that exist on disk (validator rejects others → no hallucinated footage); the renderer
picks clips per tag without repeats, adds a slow zoom + crossfade + one grade so clips match.

Ship `styles/_example` (neutral grey canvas, one lower third, one overlay card) and a
`tools/new_style.py <id>` that scaffolds a pack, plus `tools/style_preview.py <id>` that renders a 20-second preview from
a bundled fixture clip so a new pack can be checked without a real stream.

---

## 4. Watermark, overlays, thumbnails, metadata

- Anti-copy watermark: channel name, ~25% opacity, jumps to a new random place every ~9 s with fades; drawn inside every
  segment (seed per segment); if a segment command shape cannot take it, fall back to one full pass (never a video
  without watermark).
- Overlay cards from Pass B (`fact`, `coming_up`, `so_far`, `watch`, `verdict_q`), scheduled in output time (head/tail
  skip, min gap, conflict shift), drawn inside the case segments; a card cut by a segment boundary does not fade there.
- Thumbnail: candidate frames from the chosen window, face detection (mediapipe, with a cheap no-face pre-check that can
  be switched off), text placement away from faces, style-pack thumbnail template.
- metadata.txt: 5 titles (primary first), description (first line, what happens, a search question + answer), chapters
  (never in the final 60 s), tags, pinned comment, community post.

---

## 5. Windows install, update, safety nets

- `Setup.bat` → `tools/win/setup.ps1`: pinned SHA-256 downloads into `runtime\` (uv, ffmpeg, node, portable git), venv
  from `uv.lock`, newest yt-dlp + 20 s probe (fallback to `tools/win/ytdlp_pin.txt`), Microsoft C++ runtime ≥ 14.40
  (whisper crashes on older), Smart App Control detection (fallback to the signed python.org Python), Chromium,
  HyperFrames, key prompts, optional CUDA libs for GPU whisper (opt-in), then the smoke test. Pure CRLF.
- `H Labs.bat` menu: 1 stream URL · 2 own video/folder · 3 brain · 4 keys · 5 output folder · 6 smoke test / full
  self-test · 7 setup check · 8 update · 9 bulk queue · u undo update · 0 Studio · d download only · q quit.
- Update (menu 8): back up `state\`, reset tracked copies, check the branch (switch to `main` when clean, say exactly
  what to run when not), `git pull --ff-only`, print `old version (sha) -> new version (sha)`, re-run setup, smoke test.
  Record the last build that passed the smoke test; menu `u` goes back to it.
- **Smoke test** (`tools/smoke_test.py`, ~2–3 min, after every update): imports (SAC/DLL), ffmpeg, encoder + 2 s test
  encode + VRAM, whisper in a child, keys present + ai33/Hive reachable, a 720p+ format listed for a test video, a 10 s
  mini render with watermark, free disk. `[ok]/[FAIL] + remedy`, result in `state/smoke_last.json`.
- `VERSION` file (date-based) shown in the menu banner, setup check, Studio, run log and run report.

---

## 6. H Labs Studio (local web GUI)

`H Labs Studio.bat` → `tools/studio/server.py` (stdlib `ThreadingHTTPServer` on 127.0.0.1:8765-8784, vanilla JS, no build
step). Security: Host must be localhost, POST only JSON from the same origin, uploads only via PUT from the same origin.
- **Queue:** one job at a time (subprocess), live stage/percent/ETA parsed from `@@stage` / `@@videos` / progress lines,
  pause after this stream, stop, retry only failed videos, up/down/remove, finished list with ⏱ processing time,
  Events and Full log (opens at the top), KPIs, This machine (encoder, decode, keys, disk, smoke result), Needs attention.
- **New run:** links or own files (Choose from PC → native file dialog via the server; drag & drop → upload into
  `input/`), Check (title, length, best height, live?), style picker generated from the installed packs, output
  (30 / 60 / one per case / clips / as-is), shortest case 5/8, voice/watermark/cleanup options, time/cost/disk estimate.
- **Library:** finished videos with thumbnail, rank, QC, titles (copy), metadata/editor guide (copy all), upload checklist.
- **Download:** links only + max quality 1080/1440/4K → `output/downloads/<title> [id].mp4` (no style, no brain).
- Look: "Midnight Glass – Aurora" (dark purple glass, a soft shimmer sweeping over cards, liquid striped progress bars,
  reduced-motion respected), sidebar subtitle "Built by M.Haseeb".

---

## 7. Tests (the definition of done)

`tests/run_tests.py` (self-test matrix, menu 6) + `tests/test_matrix.py` (pytest). Fake the network, the brain (mock
replies), the voice (dummy TTS) and yt-dlp; never depend on the machine's free disk or on a real YouTube download.
Must cover at least: transcript + whisper fallbacks, scan, validator good/bad plans, title rules, two-pass orchestration
(parallel Pass B = same result), boundary engine, overlay scheduler + burn visible, layout detection + per-run split,
watermark inside segments, download strategies + 720p rule, resume, disk/VRAM checks, schema typos, events.jsonl,
Studio API + path guard, download-only, as-is, clips, bulk queue, update/rollback simulation in a throwaway clone, and a
**golden render**: render a short synthetic clip through the generic renderer with the example pack and compare
framemd5 against a stored reference so a refactor cannot change pixels silently.

---

## 8. Build order

1. Repo skeleton, uv, config + schema, events/log, `run_stream` stages with a mock brain and dummy TTS.
2. Download + transcript + scan (with tests).
3. Brain two-pass + validator + repair (mock replies).
4. Generic renderer + style-pack loader + `_example` pack + golden test.
5. Watermark/overlays inside segments, thumbnails, metadata, QC, reports, cleanup.
6. Clips / as-is / bundle modes / download-only / bulk queue / resume.
7. Windows setup + update + rollback + smoke test.
8. Studio GUI.
9. B-roll library support, `new_style.py`, `style_preview.py`.

Before step 4, show me the `style.json` schema and the `_example` pack and wait for my OK.
