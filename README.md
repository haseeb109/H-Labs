# H Labs — UMF Case Factory

*Auto Editing Tool Created by Claude, powered by DeepSeek API.*

One YouTube link in → finished 20–30 min Trial Tales videos out, edited exactly like your own video
(`youtu.be/kDtxYp0YiMY`). Runs **100% on this Mac**; the only network calls are the stream download and
the brain provider you choose. Part of **Z Labs** (`~/Desktop/Z Labs`).

Double-click **`H Labs.command`** to run everything from a menu.

```
.venv/bin/python3 run_stream.py "https://www.youtube.com/live/<judge-boyd-livestream>"
```

## Brain providers (pick one, switch any time)

| Provider | Key file | Default model | Price per 1M tokens (in / out) |
|---|---|---|---|
| **Hive** (default) | `~/.config/umf/hive.env` (`HIVE_API_KEY`) | `deepseek-ai/deepseek-v4.1-flash-1017` | $0.10 / $0.35 |
| **Anthropic** (fallback) | `~/.config/umf/anthropic.env` | `claude-sonnet-5-5` | $2 / $10 (~$0.34 per video measured) |
| **DeepSeek direct** (backup) | `~/.config/umf/deepseek.env` | `deepseek-flash` | $0.30 / $1.20 peak, half off-peak |
| **OpenAI (GPT)** | `~/.config/umf/openai.env` | `gpt-4o` | — |
| manual | none | — | free (paste prompt into any chat, run with `--plan`) |

Prices checked 2026-10-25 (thehive.ai/pricing, api-docs.deepseek.com). Every run prints `BRAIN USAGE` with
real dollars and saves it to `work/<id>/usage.json`.

**How the brain runs:** every pass goes to the chosen brain (default Hive). The validator checks each reply
and sends mistakes back (up to 2 repair rounds). A case that still fails - or an API failure - is retried on
`brain_fallback` (default `anthropic`), so only the hard cases cost Claude money. `ranking.md` shows which
brain built each case. Set `"brain_fallback": ""` in `config.json` for 100% cheap brain. Non-Claude brains
also get gold examples in the prompt (`prompts/shared/example_pass_a.md`, `example_pass_b.md`;
`"prompt_examples"`: auto / true / false).

Paste your key after the `=` in the env file and save. Switch with `--brain hive|anthropic|deepseek|openai|manual`
or menu option 3 (an explicit `--brain` runs every pass on that brain).

## What every video looks like (locked)

| # | Block | Detail |
|---|-------|--------|
| 1 | **Hook teaser** 10–15 s | most important moment of the *first* case, dark fleur-de-lis canvas, orange **"In This Case"** label (top-left), white bottom headline caption |
| 2 | **Your gavel intro** | `assets/channel_intro.mp4` (7.5 s, cut from your own video, with its sound) |
| 3 | **Case 1** | footage strip, **TrialTales** logo permanently top-left, lime **CASE STARTED** label |
| 4 | **AI recap** | blurred strip, deep AI voice, ONE clip ≤ 18 s |
| 5 | **Case n** | red-bar white-box **2nd Case / 3rd Case …** label |
| … | repeat 4–5 | |
| N | **Closing recap** | blurred strip, narrator split into clips ≤ 18 s each, fade to black |

* Canvas 1920×1080 @30fps, hardware-encoded (`h264_videotoolbox`). The Zoom band is detected per segment
  (2-up vs 3-tile grid) and scaled into the 1920×540 strip.
* **Every AI-voice clip is ≤ 18 s** — validator rejects text that cannot fit, renderer splits at sentence
  boundaries, speeds up max 12 %, asserts measured length in `qc.json`.
* Case IN points must sit on the judge's **CR call-out** (locked rule, enforced by the validator).
* Overlays via **HyperFrames** (headless Chrome → transparent WebM); static PNG fallback if unavailable.
* Voice chain: ai33.pro → VoiceStudio (local) → macOS `say` → dummy tone (`--tts dummy` = tests).
  **> 5,000 TTS chars per run stops unless `--confirm-tts`** (owner rule).

## Setup (already done on this Mac, Oct 2026)

ffmpeg + node (brew, vp9 + videotoolbox verified), Python deps in `.venv/` (yt-dlp, pillow, numpy,
faster-whisper, av<16), HyperFrames + headless Chrome, key templates in `~/.config/umf/*.env` (chmod 600).
If rebuilding elsewhere: `brew install ffmpeg node python@3.12`, create a venv, `pip install yt-dlp pillow
numpy faster-whisper "av<16"`, `npm i -g hyperframes && hyperframes browser ensure`.

## Run

```
.venv/bin/python3 run_stream.py <url>                  # full pipeline, sequential
.venv/bin/python3 run_stream.py <url> --stage plan     # stop after the plan; check plan_report.txt + contact_plan.jpg
.venv/bin/python3 run_stream.py <url> --brain deepseek # pick the brain
.venv/bin/python3 run_stream.py <url> --plan p.json    # manual plan from chat
.venv/bin/python3 run_stream.py <url> --only 2         # render just video 2
.venv/bin/python3 tests/run_tests.py                   # 10-check self-test matrix
```

Output: `output/<date>_<streamid>/Video_NN_<lead>/` → `video.mp4`, `thumbnail.jpg` (+ candidates),
`metadata.txt` (title, backup, description, chapters, tags, pinned comment, quiz, publish slot,
follow-up owed), `edit_sheet.txt`, `footage_log.csv`, `contact_sheet.jpg`, `qc.json`, `video_plan.json`.

## Self-test matrix (10 checks)

`tests/run_tests.py` — environment · imports · transcript+whisper · scan · validator-good ·
validator-bad-blocked · vo-splitter · brain-plumbing (mock + repair loop) · renderer-units ·
end-to-end render of the proven Rendon stream (28:37, QC-OK, from `tests/fixtures/rv_clips`).
All 10 green = the machine is healthy. `--quick` skips the long render.

## Notes

* Sequential by design — one stream at a time keeps 16 GB RAM comfortable.
* Cached parts live in `output/.../Video_NN_*/_work/`; delete them after changing renderer code.
* Cases that don't fit a video are carried forward (`state/carry_forward.json`).
* Court footage is third-party: keep `footage_log.csv` + the source credit in the description
  (Content ID / reused-content risk). Incompetech music needs its CC BY credit line.
* Keys never go in this folder, the repo, or chat — only `~/.config/umf/*.env` (chmod 600).
* Burner-account `cookies.txt` only, and only if YouTube blocks downloads.

## Styles (one pack per channel)
`styles/trial_tales/` (Trial Tales) and `styles/overruled/` (Overruled: courtroom commentary look for a 40-60 audience, same locked structure).
The launcher asks which style to use per run; CLI: `--style trial_tales|overruled`. Overruled needs
`pip install playwright numpy pillow` + `playwright install chromium` inside `.venv`. See `styles/overruled/README.md`.


## v10 — run modes, five titles, overlays, boundary engine

* **Modes** (launcher asks after style, or `--mode`): `30` (20-40 min bundles) · `60` (50-70 min bundles,
  default) · `all` (every case >= 8 min becomes its OWN video, virality-ranked, folders `01_Name/`).
  Mode "all" skips carry-forward and runs a two-pass brain: Pass A = case inventory (phases, virality
  factors, boundary evidence), Pass B = one packaging call per used case (hook, vo_final, 5 titles,
  overlays, metadata). Failed packages are marked needs_review in ranking.md and skipped, the rest render.
* **Five titles** per video (karma / quote / number / twist / human), every rule machine-checked against
  the transcript (numbers, quotes, judge-name-once, one CAPS bank verb, no verdict reveals). `titles[]`
  lands in `metadata.txt` (starred primary) and `ranking.md` / `ranking.csv`.
* **Boundary engine**: transcript wrap-up/ruling/call signals + Zoom tile-count events refine each case
  OUT inside a +/-2 min window (hard floors: never cut a ruling, never include the next call).
  `work/<id>/boundary_report.md` + confidence; red-flagged on `contact_plan.jpg` when < 60.
  Tile-label OCR is optional (`boundary.ocr`: rapidocr/ocrmac auto-detected, off = fine).
  Optional vision tie-break: `boundary.vision_check: true` (~1-3 cents per checked boundary).
* **In-case overlays**: every ~4.5 min a short, transcript-true text card in the bottom safe zone
  (never over faces). Scheduler respects labels/cards; `edit_sheet.txt` lists the final ones.
* **Reuse guard**: `state/used_cases.json` logs rendered cases per style; a warning prints when the same
  case was already used on the other channel (never blocks - owner decides).
* Config knobs live in `config.json` (`mode`, `min_case_minutes`, `overlays`, `boundary`, `title_system`).
  Manual brain in mode "all": run once -> paste `work/<id>/prompt_A.txt`, save `plan_A.json`, rerun with
  `--plan plan_A.json`, then package each `prompt_B_<case>.txt` the same way.
