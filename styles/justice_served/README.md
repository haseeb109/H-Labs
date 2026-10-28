# Style pack: Justice Served

Fourth H Labs style (next to `trial_tales`, `overruled`, `court_beacon`). Look: **sports scoreboard** - every case is a
ROUND, the hearing is a matchup (STATE vs the defendant), the closing board is the FINAL SCORE.
Charcoal `#121417`, amber `#FFB000`, turf green `#1F8A4C`. Fonts: Big Shoulders Display, DM Mono, Inter (SIL OFL).

**Owner decisions**
* **No channel intro.** Hook -> Case 1 straight away (the case starts at "calling CR####").
* **Logo = small corner branding** (bottom-right, `assets/logo_transparent.png`) on every frame after the hook.
* Subscribe CTA in every video (see below). Everything lives in this folder; H Labs core (`ucf/`) is not changed.

## Folder
```
style.json     id justice_served, structure family "tt" + look "js", renderer_module engine/render_js.py (JSRenderer)
assets/        logo_transparent.png (corner logo, thumbnail, closing board), logo_source.png (original 2000x2000)
hf/fonts/      Big Shoulders Display 800/900, DM Mono 500, Inter 600/800
engine/        render_js.py (renderer, subclass of H Labs' Overruled compose engine), js_gfx.py (HTML/CSS graphics),
               smoke_test.py (offline render on a court clip, dummy voice)
prompts/       master_v9.md + json_addendum.md + title_rules.md (same as Court Beacon) + justice_served_extra.md
```

## What is on screen
| Element | Where / when |
|---|---|
| Hook | "TODAY'S MATCHUP" tag + big headline slab (one word can be wrapped in `*stars*` for an amber block), no logo |
| Lower third | `ROUND n · PROCEEDING` / `STATE vs NAME` / court line, first 7 s of each case |
| THE MATCHUP card | side column: defendant, charge + facing, the one question |
| Ticker + progress line | bottom of every case |
| Cards (bottom band) | KEY STAT, PLAY BY PLAY, WATCH THIS, YOUR CALL, COMING UP (plan `overlays`), THE CALL (`video.takes`), ON THE RECORD (`video.exchanges`) |
| Recap | blurred footage + POST-GAME REPORT card, AI voice (<= 18 s clips), SUBSCRIBE button on the card |
| Closing | FINAL SCORE board + YOUR CALL quiz + SUBSCRIBE NOW box under the closing narration, fade out |

## Subscribe (every video)
Corner SUBSCRIBE button (first one ~2.5 min into case 1, so viewers are asked after they are invested; 30 s into later cases),
SUBSCRIBE pill every ~6 min, one full-width banner mid-video, SUBSCRIBE button on every recap card, SUBSCRIBE NOW box on the
closing board, and a spoken line in `vo_final` (the brain prompt requires it).

## Run
`H Labs.command` -> paste URL -> style `justice_served` -> mode. CLI: `--style justice_served`.
Needs the same tools as Overruled: `pip install playwright numpy pillow` + `playwright install chromium` inside `.venv`.
Smoke test (no network, dummy voice): `python3 styles/justice_served/engine/smoke_test.py path/to/court_clip.mp4`.
`HL_CHROMIUM=/path/to/chrome` points the graphics at a specific Chromium binary (optional).

## Tweaking
* Colours / cards / fonts: `engine/js_gfx.py` (CSS block at the top + one function per element).
* Timing of cards and subscribe prompts: `engine/render_js.py` (`HEAD_SKIP`, `FIRST_CTA_AT`, ...) and `schedule_subs()`.
* Logo: replace `assets/logo_transparent.png` (size is set in `js_gfx.brand()`).
* Delete `output/<run>/Video_*/_work/` after changing the look, then re-render.
