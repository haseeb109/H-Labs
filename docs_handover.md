# UMF Case Factory — Full Handover for Zcode

Owner: Sardar Mohsin, Unity Media Flow (UMF). Channel: **Trial Tales** (courtroom, US Tier-1 audience).
Writer's note: this document explains everything built and tested so far, so another coding agent (Zcode) can run, debug and extend it on the owner's MacBook without Claude.
Language rule when talking to the owner: **Hinglish for chat, clean English for every deliverable/doc/code comment.**

---

## 0. MANDATORY — the `/video` skill (read this first)

`/video` is the owner's existing Claude skill "UMF Doc Video Pipeline". It builds **faceless documentary/explainer videos** (script → ai33 voice → clips → motion graphics → captions → music → render). The Case Factory is a **different, sibling pipeline** (re-editing real court livestreams), but both share the **same rules, tools and machines**. Everything below in "Hard rules" applies to the Case Factory too.

### Hard rules (from the skill, non-negotiable)
1. **ALWAYS ask the owner before generating any voice/TTS over 5,000 characters** (ai33.pro or any TTS). `ai33_tts.py` enforces it; pass `--confirmed` / `--confirm-tts` only after a clear yes in chat.
2. **Never put API keys in memory, repo or chat output.** Keys live in `~/.config/umf/ai33.env`, `~/.config/umf/stock.env`, `~/.config/umf/anthropic.env` (chmod 600). If missing, ask the owner to paste them again.
3. **Never ask for or use Google/YouTube account cookies from the owner's main accounts.** Only a burner account's `cookies.txt`, kept on the Mac, and only if YouTube blocks downloads.
4. **YouTube/court footage is third-party:** always ship a footage log (source URL + timestamp per shot) and remind about Content ID / reused-content risk.
5. Music from Incompetech needs the CC BY credit line in the description (`umf_music.py` prints it).
6. **Show the owner a contact sheet (one frame per shot) before the final render of anything long.** (Exception: the owner has said, for the Case Factory, "do not show intermediate output until perfect — work silently, send ONE final message." Always still generate and self-check the contact sheet.)

### Skill pipeline (for reference / reuse)
1. Research + script (~150 words/min narration; scenes ~10–17 s in `scenes.json`).
2. Voice per scene: `python3 ai33_tts.py tts --voice <id> --text-file vo/sN.txt --out vo/sN.mp3`. Voices: `elevenlabs_nPczCjzI2devNBz1zQrb` (Brian, deep), `elevenlabs_z9ihBMCAnrOeGUbPDiwi` (Andres, documentary). ai33 base `https://api.ai33.pro`, header `xi-api-key`. **Do not use the ai33 IMAGE API** (hangs in "doing" and still charges credits).
3. Visuals: stock via `umf_collect.py` (Pixabay + NASA, CLIP-ranked); YouTube footage runs on the owner's **Mac** (cloud IPs are bot-blocked): `umf_clip_collector.py search → rank → probe → umf_clip_brain.py analyze → cut → verify`.
4. Graphics: Remotion comps (TimelineCard, StatCard, QuoteCard, LowerThird…) and **HyperFrames** (GSAP/HTML → video) for map/explainer animation. Read the hyperframes skill first; `hyperframes check`, `snapshot`, `render`.
5. Assemble: `umf_assemble.py` (push-in/out, dissolves, karaoke captions, music ducking, grain, −14 LUFS, 12 Mbps cap). Long renders: `nohup` + poll; resume skips built segments.
6. QC: contact sheet + loudness check.

### Toolkit location / restore
- Lives on the owner's Mac: `/Users/haseeb/Desktop/Claude-Cowork/UMF Clips/_tools/umf-video-toolkit.tar.gz`. Extract to `~/umf-doc`, run `bash ~/umf-doc/setup.sh` (installs melt, MoviePy, yt-dlp, faster-whisper, OpenCLIP, PySceneDetect, Manim, Remotion, HyperFrames + Chrome). Pin PyAV `av<16`. `bash ~/umf-doc/umf_check.sh` must be green.
- Capacity notes: cloud = 2 CPU, no GPU. Long (20 min) videos should render on the owner's **HP Victus (RTX 3050)** or a Mac with hardware encoder. VoiceStudio (free local TTS, OpenAI-compatible at `127.0.0.1:3900/v1/audio/speech`) is installed on the Mac.
- Mac `device_bash`-style calls die at ~3 min and background processes get killed in the Claude VM — this limit does **not** apply when Zcode runs natively on the Mac.

---

## 1. What the Case Factory is (goal)

**Input:** one long Judge **Stephanie Boyd** (187th District Court, Bexar County, TX) livestream/VOD URL (typically 2–3.5 h Zoom recording).
**Output:** one or more **finished 20–30 min videos**, hands-free, in the exact **locked Trial Tales edit style** of the owner's own video `https://youtu.be/kDtxYp0YiMY`, plus metadata (title, backup title, description, chapters, tags, pinned comment, quiz, thumbnail) following the owner's **"CASE BUILD ORDER v9.0" master prompt** (`prompts/master_v9.md`), enforced by a validator.

Owner goal for the future: run it **100% on his MacBook** with no Claude chat time. The only part that needs "intelligence" is the **brain** (choosing cases/cuts/hook, writing titles and recap text) — see §9.

---

## 2. The locked Trial Tales style (what every video looks like)

Canvas **1920×1080**, 30 fps. Dark fleur-de-lis background canvas (`assets/tt/bg_plain.png`, `bg_logo.png`).

| # | Block | Detail |
|---|---|---|
| 1 | **Hook teaser, 10–15 s** | The most important moment of the lead case (inside the back 60 % of its range). Plain canvas (no logo). Orange **"In This Case"** label top-left; white **bottom headline** caption (`hook.headline`, 3–9 words). Real court audio. |
| 2 | **Owner's gavel intro** | `assets/channel_intro.mp4` (7.47 s, cut from the owner's own video, with its sound). |
| 3 | **Case 1** | Footage strip + **TrialTales logo top-left** (permanent, baked into `bg_logo.png`), lime **"CASE STARTED"** label (appears 0.35 s in, lasts 4.2 s). |
| 4 | **AI recap** after each case except the last | Blurred strip, deep AI voice (ai33), **ONE clip ≤ 18 s** (bridge text 35–40 words). |
| 5 | **Case n** | Red-bar white-box label **"2nd Case" / "3rd Case"…** |
| … | repeat 4–5 | |
| N | **Closing recap** | Blurred strip, narrator text 45–70 words split into **sentence-aligned clips ≤ 18 s each**, fade to black. |

Geometry: the stream is a Zoom recording. The relevant video lives in a band; it is scaled into a **1920×540 strip at y=270**. Two Zoom layouts occur and the renderer switches per segment:
- **2-up** (court + witness/judge, 1280×360 band at y=180, black bars above/below) → crop `iw:ih/2:0:ih/4`, scale to 1920×540.
- **3-tile "full" grid** (court 640×360 at (0,0) | judge 480×360 at (720,0) | witness 640×360 at (320,360)) → three crops `hstack`ed to 1760×360, scaled to 1920×393, padded to 540. (Earlier version just fitted the whole frame, which looked tiny — fixed Oct 24.)

Every AI-voice clip is **≤ 18 s**: validator rejects text that cannot fit; renderer splits at sentence boundaries, speeds a clip up max 12 %, and asserts measured lengths (`qc.json → ai_clip_seconds`).

**CASE START RULE (locked Oct 24):** every case's IN point is where the judge **calls the case** — "calling CR2469", "court is calling 2024 CR…", any case number starting with **CR**. Not the plea terms. Only a jury trial already under way in the stream (no call-out inside the file) may set `"resume": true` and start at its best opening. Enforced in `ucf/validate.py` (error if no `calling` / `CR####` / `cause number` within [IN−3 s, IN+30 s]) and in `ucf/brain.py` OVERRIDES.

---

## 3. Repository layout (`umf-case-factory/`)

```
README.md                 user-facing quick start
run_stream.py             CLI + orchestration (STAGES = info, download, transcript, scan, plan, render)
config.json (optional)    overrides for ucf/config.py DEFAULTS
prompts/master_v9.md      owner's CASE BUILD ORDER v9.0 (rules 0–8, validator-enforced)
prompts/json_addendum.md  "machine output format" appended to the master prompt (JSON schema for the plan)
ucf/config.py             DEFAULTS + env loading from ~/.config/umf/*.env
ucf/download.py           yt-dlp info/video/captions (cookies optional, burner only)
ucf/transcript.py         load NexLev json / json3 / vtt, normalise, whisper fallback, compact_lines()
ucf/scan.py               deterministic Rule-0 scan: case-start markers ("court is calling", "state versus", "cause number"…), gap candidates, dead air
ucf/brain.py              builds the prompt (master + OVERRIDES + addendum), calls Anthropic API, repair loop (max 2 rounds); brain="manual" = paste prompt into Claude and pass --plan
ucf/validate.py           the rules engine (see §6) → (errors, warnings); errors block render
ucf/timeline.py           builds the timeline: removes(), case_len/case_parts, est_clips_dur, _build_tt()
ucf/vo.py                 split_clips (sentence-aligned ≤18 s), clip_issues; CLIP_MAX=18, CLIP_TARGET=17
ucf/tts.py                providers: ai33 → voicestudio → say (macOS) → dummy(tone for tests); synth_clips, _atempo, chars_needed()
ucf/hf.py                 HyperFrames bridge: render_overlay(kind,text,dur,out_webm,work) → transparent WebM
hf/overlay_template.html  GSAP overlay template (labels), hf/fonts/*.woff2, hf/gsap.min.js
ucf/render_tt.py          TTRenderer — the locked style renderer (hook/intro/case/recap/closing, overlays, locate(), layout_runs(), strip_chain(), tt_cut(), tt_recap(), render_video(), _thumb())
ucf/render.py             older generic renderer (card-style, not the locked style)
ucf/cards.py              card images + contact_sheet()
ucf/sheets.py             edit_sheet_tt(), metadata() (title/description/chapters/tags/pinned/quiz/follow-up)
tools/ai33_tts.py         bundled copy of owner's ai33 helper (CLI: tts --voice --text-file --out; enforces 5,000 chars)
tools/make_canvas.py      regenerates assets/tt/*.png (canvas, logo overlays)
assets/                   channel_intro.mp4, logo_source.jpg, tt/{bg_plain,bg_logo,logo_gold,logo_gold_2x}.png
tests/                    make_boyd_plan.py / make_rendon_plan.py (hand-authored plans), style_proof.py, nexlev transcripts
state/sources.json        source registry (see "pre-cut clips" below); state/carry_forward.json = unused cases offered to the next stream
work/<streamid>/          transcript.json, meta.json, plan.json, plan_report.txt, contact_plan.jpg, tts cache
output/<date>_<id>/Video_NN_<lead>/   video.mp4, thumbnail.jpg, metadata.txt, edit_sheet.txt, footage_log.csv, contact_sheet.jpg, qc.json, video_plan.json, _work/ (cached parts)
```
~3,000 lines of Python in `ucf/` + `run_stream.py`.

---

## 4. How to run

Setup (once, Mac):
```
brew install ffmpeg node            # ffmpeg must include libvpx (default in brew)
pip3 install yt-dlp pillow numpy faster-whisper
npm i -g hyperframes && hyperframes browser ensure
mkdir -p ~/.config/umf
echo 'ANTHROPIC_API_KEY=sk-ant-...' > ~/.config/umf/anthropic.env
echo 'AI33_API_KEY=...'            > ~/.config/umf/ai33.env
chmod 600 ~/.config/umf/*.env
```
YouTube note: yt-dlp may need `--js-runtimes node`; if YouTube blocks, use a **burner** account's cookies only.

Run:
```
python3 run_stream.py "<livestream-url>"                 # full pipeline
python3 run_stream.py <url> --stage plan                 # stop after plan; inspect work/<id>/plan_report.txt + contact_plan.jpg
python3 run_stream.py <url> --plan my_plan.json          # use a plan written elsewhere (Claude chat / hand-authored)
python3 run_stream.py <url> --only 2                     # render just video 2
# offline / already-downloaded:
python3 run_stream.py --video-file X.mp4 --stream-id ID --stream-length H:MM:SS \
  --transcript-file transcript.json --plan plan.json --tts dummy|ai33|voicestudio|say --confirm-tts
```
Flags: `--config`, `--stage`, `--plan`, `--video-file`, `--transcript-file`, `--stream-id`, `--stream-length`, `--only`, `--confirm-tts`, `--brain anthropic|manual`, `--tts`.
**TTS over 5,000 chars in one run stops** unless `--confirm-tts` (only after the owner's yes in chat).

Re-running is cheap: every rendered part in `_work/` is cached (`if not p.exists()`); delete cached parts after changing renderer code.

### Pre-cut clip sources (used when the full file is too big to move)
`state/sources.json`:
```json
{"lVQ79x0Hd_w.mp4": {"path": "…first clip…", "url": "https://youtu.be/…",
  "clips": [{"in": 3216, "out": 3255, "path": "…/r1.mp4"}, …]}}
```
`locate(sname, a, b)` maps stream time → (clip file, clip time); raises if no clip covers the range. `run_stream.py` preserves an existing `clips` map. **On the Mac you do not need this** — render straight from the full file.

---

## 5. Plan JSON (the contract between brain and renderer)

One JSON object (schema in `prompts/json_addendum.md`; example: `tests/rendon_2025-05-09_plan.json` produced by `tests/make_rendon_plan.py`). Time format everywhere: **stream clock `"H:MM:SS"`**.

Top level: `source_file, stream_length, working_note[≤12], pass1[], gaps[], cases[], videos[]`.

`cases[]`: `id, name, cause_no, in, out, remove | removes[] ({in,out,why}), ruling_tc, ruling_deferred, monetisation (OK|LIMITED), score (/50), status (used|carried|rejected), reject_reason, what_it_is, charge, facing, question, story, root_against, moment, moment_tc, ends_on, result{sentence,conditions}, resume (bool)`.
- `removes[]` (new, multi-cut) lets one long case (jury trial) keep only highlight pieces; each remove must be > 120 s; each kept piece ≥ 20 s.

`videos[]`: `n, case_ids (PLAY ORDER, strongest first), hook{in,out,spoken,headline}, intro_seconds, vo1, bridges[{after_case_id,text,split_after_sentence}], vo_final{text}, quiz{question,options{A,B,C},answer}, thumbnail{window_in,window_out,look_for,text,gold_word,placement}, title, backup_title, description{…}, chapters[{tc,label}], tags[], pinned_comment, community_post, publish{slot}, verdict_pending, followup_owed`.

---

## 6. Validator rules (`ucf/validate.py`, tt mode) — errors block render

- Case ranges valid, inside stream, no overlap; `status` of video cases must be `used`; each case in only one video.
- **CASE START:** IN must be at the judge's call-out (see §2) unless `resume: true`.
- Hook: 10–15 s, inside the **back 60 %** of the lead case's range; `hook.headline` 3–9 words, no trailing period, true to the hook audio (transcript check).
- Bridge texts: 35–40 words, ≥2 sentences, one recap clip (≤18 s). `vo_final`: 45–70 words, every sentence < 35 words, splits into ≤18 s clips.
- Runtime 20–30 min **including estimated VO**; allow_long_solo for one strong 25+ min case.
- Removes: each > 120 s; kept pieces ≥ 20 s.
- Title: 65–90 chars, 13–17 words, exactly one " — ", exactly one ALL-CAPS word in the payoff half; backup title same style; thumbnail text 2–5 words and **must not repeat title words**; warnings for no number in the title / empty cause_no.
- Chapters 5–8 in play order; first chapter = lead case IN; **none within the last 60 s**.
- Pending verdicts need `followup_owed`.
- 5-gram reuse check against source text for VO (original narration, not copied court text).
- Every case must be `used`, `carried` or `rejected` — nothing unmapped (zero-miss two-pass extraction).

---

## 7. Rendering details (what `render_tt.py` does)

1. **Voiceover:** `tts.synth_clips` per clip; ai33 → voicestudio → `say` → dummy. Each clip measured; atempo ≤ +12 %; asserted ≤ 18 s.
2. **Overlays:** `hf.render_overlay` → HyperFrames renders `hf/overlay_template.html` (GSAP) to **transparent WebM**; `hyperframes browser ensure` provides headless Chrome. ffmpeg composites using `-c:v libvpx-vp9` decode of the alpha WebM. If HyperFrames is unavailable → static PNG fallback.
3. **Hook:** plain canvas + strip + "In This Case" + headline; real audio.
4. **Intro:** `assets/channel_intro.mp4` scaled onto canvas, with its own audio.
5. **Case parts:** for each kept piece, `tt_cut` (logo canvas, strip via `strip_chain` driven by `layout_runs`, label overlay at +0.35 s for the first piece only).
6. **Layout detection:** `layout_runs(path, a, b)` samples keyframes (`-skip_frame nokey`), measures top-band YAVG (`crop=iw*0.9:ih*0.2`, threshold 24) → `full` vs `2up`; runs shorter than 4 s are merged into neighbours; `strip_chain` overlays the full-grid version with `enable=between(t,…)`.
7. **Recaps:** `tt_recap` = blurred strip (`scale=480:135, gblur=2.4, scale=1920:540`) from the end of the previous case + VO wav; closing recap clips fade to black.
8. **Join + loudness:** concat parts, normalise to the config target (−14 LUFS design; measured −15.0 on the last run), true-peak check.
9. **Thumbnail:** frame from `thumbnail.window_in/out`, text with one gold word; candidates saved in `thumbnail_candidates/`.
10. **QC:** `qc.json` (duration vs expected, LUFS, true peak, `ai_clip_seconds`, chapters, `ok`). `contact_sheet.jpg` of every block.
11. **Sheets:** `edit_sheet.txt` (editor-facing summary, REMOVE list, recap texts), `metadata.txt` (title, backup, description, chapters, tags, pinned comment, quiz, publish slot, follow-up owed), `footage_log.csv` (source URL + timestamp per shot).
Encoder: `auto` → `h264_videotoolbox` (Mac), `h264_nvenc` (NVIDIA), else `libx264`.

---

## 8. What was built and tested (history)

- **Style proof:** `trial_tales_style_proof.mp4` — synthetic + real 30 s Boyd slice rendered in the locked style.
- **Boyd 19 Oct 2026 plan** (`tests/boyd_2026-10-19_plan.json`) hand-authored; dry-run only.
- **Real video test:** `https://youtu.be/lVQ79x0Hd_w` (Boyd, 9 May 2025, 3:00:23; afternoon docket + *State v. Rendon* jury trial). Result: **28:37 video**, QC OK, −15.0 LUFS, 3 AI clips (15.5 s, 10.5 s, 12 s). Structure: hook 0:00–0:13 → gavel intro → Case 1 Rendon (9 highlight pieces, 8 removes; label CASE STARTED) → recap at 20:58–21:14 → Case 2 Maldonado (starts at the judge's "court is calling 2024 CR2071…", 13:25) → closing recap 28:13–28:37 with fade. Voice was **dummy tone** (no ai33 key in the cloud).
- **Wall time (cloud, 2 CPU):** ~23 min per 28-min render; total ≈ 1 h including clip cutting. On an M-series Mac with VideoToolbox, expect ~5–8 min render.
- **Bugs found and fixed:** cropdetect picking up Zoom watermark; unstable `hash()` in the HyperFrames cache key (now md5); malformed footage-log URL (`?t=` vs `&t=`); bridge texts > 40 words; fixed crop failing on 3-tile frames (now dynamic layouts, then hstack fit); `followup_owed` string vs dict crash in `sheets.py` (now accepts both); `run_stream.py` overwriting `sources.json` clips (now preserved).

---

## 9. The "brain" — the only non-deterministic part

Everything except these items is deterministic code (free on the Mac): choosing which case is most interesting, the hook moment, which pieces of a long trial to remove, titles/backup/thumbnail text, bridge/closing recap text, chapter labels, quiz.

Options for Zcode (in order of recommendation):
1. **Anthropic API** (`brain="anthropic"`, `model` in config — default currently `claude-sonnet-4-5`; update to whatever the owner's account offers). `brain.py` builds the prompt (master v9 + owner OVERRIDES + JSON addendum), parses the JSON, validates, and sends validator failures back for up to 2 repair rounds. Cost per stream should be small (3 h transcript ≈ tens of thousands of tokens) — measure it.
2. **Local LLM (Ollama/Qwen/Llama):** free but weaker; expect more repair rounds, weaker titles, and poor multi-cut decisions on jury trials. Validator keeps it safe.
3. **Manual:** `brain="manual"` — pipeline writes `work/<id>/prompt_for_claude.txt`; owner pastes it into Claude and passes `--plan plan.json`.

Deterministic helpers that already reduce brain risk: `scan.py` (CR/"court is calling" markers, dead-air), the validator, the zero-miss case accounting.

---

## 10. Environment facts

- **Cloud sandbox (where this was built):** ffmpeg (libvpx-vp9), Python 3.13, PIL, Playwright/Chromium; 2 CPU; **YouTube blocks cloud IPs** (so downloads were done on the owner's Mac); no ai33 / Anthropic keys.
- **Owner's Mac (Claude VM view):** ffmpeg, yt-dlp (`~/.local/bin`, needs `--js-runtimes node`), node, Python 3.10; connected folder `/Users/haseeb/Desktop/Claude-Cowork` (deliverables in `UMF Case Factory/`). HyperFrames, Pillow, numpy, faster-whisper and libvpx **not verified** on the Mac — check with `which` / import first.
- Other owner machine: **HP Victus (RTX 3050)** for long renders.
- Hardware advice: M2/M3/M4 MacBook, 16 GB RAM is best; Intel Mac is slow; Windows with NVIDIA GPU (NVENC) is also fine; keep ≥100 GB free disk (a 3 h stream ≈ 1 GB plus temp files).

---

## 11. Known gaps / TODO for Zcode (priority order)

1. **Mac bootstrap:** write `setup.sh` (brew ffmpeg node; pip yt-dlp pillow numpy faster-whisper; `npm i -g hyperframes`; `hyperframes browser ensure`; create `~/.config/umf/*.env`) and `run.command` (double-click: paste URL → full pipeline). Verify libvpx in the Mac ffmpeg (`ffmpeg -encoders | grep vp9`) and HyperFrames overlays (static PNG fallback exists).
2. **Wire real keys:** ai33 voice (test once with ≤5,000 chars after owner confirms), Anthropic key, update `config["model"]`.
3. **Hardware encoder** (`h264_videotoolbox`) — confirm quality at the current bitrates; check `qc.json` loudness lands at −14 (last run −15.0).
4. **Layout detection robustness:** only 2-up and the 3-tile court|judge|witness layouts are handled. New Zoom layouts (4 tiles, shared screen, defendant tiles) will need new crops — add a generic fallback and a QC check that flags unknown layouts.
5. **Captions quality:** YouTube auto-captions garble names ("Rendone") — prefer Whisper (`faster-whisper`, `base.en` or larger) for the transcript and fuzzy-match names.
6. **Jury trials / long hearings with no call-out:** `resume: true` path + multi-remove logic is tested on one video only.
7. **Auto-carry-forward:** `state/carry_forward.json` exists but not exercised across multiple streams.
8. **Multi-video per stream:** the brain/validator support several videos per stream (owner wants as many 20–30 min videos as the stream can honestly fill) but only single-video output has been tested end to end on real footage.
9. **Resume/caching:** renderer caches parts; delete `_work/*.mp4` after changing renderer code; consider keying the cache by a hash of inputs.
10. **Follow-up videos:** pending verdicts (`verdict_pending`, `followup_owed`) are only written into metadata; no tracker yet.
11. **Tests:** add regression tests (validator rules incl. CR rule, `split_clips`, `layout_runs` on fixtures, `strip_chain` filtergraph builds).

---

## 12. Owner preferences & constraints to respect

- Owner: Sardar Mohsin; runs YouTube/TikTok automation agency (UMF) and the Trial Tales courtroom channel; clients' channels too.
- Chat in **Hinglish**; deliverables in English; direct, structured, copy-ready, minimal filler.
- **No intermediate output**: finish, self-check (contact sheet, QC), then report once.
- **TTS > 5,000 chars → confirm first.**
- Keys never in repo/chat; no main-account cookies.
- Source footage is a public court broadcast re-edited with original narration — keep `footage_log.csv` and the source credit line in descriptions (`config.source_credit`).


---

# v10 UPDATE (2026-10-24)

Built by ZCode from Claude's v10 master spec: run modes (30/60/all), two-pass brain for mode all,
five-title system (styles/*/prompts/title_rules.md), case-boundary engine (ucf/zoom|tile_ocr|evidence|boundary|vision.py,
evidence stage between scan and plan), in-case overlays (ucf/overlay_sched.py + render_tt burn-in), ranking.md/csv,
reuse guard (state/used_cases.json). See README 'v10' section. Backup: ~/Desktop/Z Labs/H Labs_backup_v9_2026-10-24.
