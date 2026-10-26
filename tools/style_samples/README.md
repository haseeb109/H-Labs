# Style samples (Test Style 1-8)

60-second previews of the 8 proposed styles, all cut from the same court clip so they are easy to compare.
These are **previews**, built outside the main engine. A style you approve gets built into the real renderer
afterwards (its own `styles/test_style_N/` pack + look module).

## Run (on the Mac)

```
cd "<H Labs folder>"
git pull
.venv/bin/pip install playwright pillow && .venv/bin/playwright install chromium   # once (Overruled already needs these)
.venv/bin/python3 tools/style_samples/render.py              # all 8 (~1.5 min each)
.venv/bin/python3 tools/style_samples/render.py --styles 3 5 # only some
```

Output: `output/style_samples/Test_Style_N_<Look>.mp4`

The script downloads 65 s of stream `HKURkJmb-K8` (2:07:05-2:08:10, Frank Corona probation hearing) with yt-dlp
the first time and caches it there. Already have the clip? `--source clip.mp4` (it must start at 2:07:05).
Captions come from the NexLev transcript in `tests/`, so no Whisper is needed.

## Timeline of every sample

| Time | Part | What to look at |
|---|---|---|
| 0-12 s | Hook | hook label + headline, captions (every style shows captions in the hook) |
| 12-15 s | Intro slot | placeholder card, or `styles/test_style_N/assets/channel_intro.mp4` if it exists |
| 15-41 s | Case | case label, counter / progress, info card (~21 s), **subscribe CTA (~30 s)**, quote card (~37 s) |
| 41-50 s | Ruling | "The court is going to revoke." + ruling stamp/banner (Style 3 punches in) |
| 50-56 s | Recap | blurred footage + recap card |
| 56-60 s | End screen | subscribe box + next-video slot |

In a full video the first subscribe CTA comes after the first big moment (~2-3 min), never in the first 30 s.

## Captions per style

| Style | Look | Captions |
|---|---|---|
| 1 | Confidential File | key moments |
| 2 | Breaking News | full video (TV closed captions) |
| 3 | Viral Gen-Z | full video, word-by-word pop |
| 4 | Cinematic Documentary | hook only |
| 5 | Legal Explainer | full video, legal terms highlighted |
| 6 | Human Story | key moments |
| 7 | Sports Scoreboard | key moments |
| 8 | Courtroom Sketch | hook only |

## Logo / intro

Put `logo.png` and `channel_intro.mp4` in `styles/test_style_N/assets/` and re-run: the dotted LOGO box is
replaced by the logo and the intro slot plays the first 3 s of the intro.

## Changing a style

Everything visual for a style lives in `tools/style_samples/styles.py` (one block per style: footage position,
caption mode, CSS, and the HTML of each element). Timing of the elements is `SCHEDULE` in `render.py`.
