# Style pack: Overruled

Second channel. SAME locked structure as Trial Tales (hook 10-15 s -> intro -> cases -> AI recap <= 18 s -> closing narration,
CASE START at "calling CR####"), DIFFERENT look, built for a 40-60 audience: courtroom commentary + overview, calm, readable.

```
style.json      id, renderer "tt" (structure family) + look "ov" (Overruled renderer), prompts, channel/voice/tags knobs
hf/fonts/       Archivo 800/900, Playfair Display 700/900, Montserrat 700/800 (used by the HTML->PNG graphics)
prompts/        master_v9.md + json_addendum.md (shared with Trial Tales) + overruled_extra.md (takes/exchanges/quiz/subscribe)
assets/         channel_intro.mp4 (10 s animated logo intro, plays after the hook, keeps its sound), logo_transparent.png (corner logo + docket),
                logo_square.png (profile/thumbnail use)
```

Palette: navy #0E1A2B / #16273E / #1E3452, cream #F4EDE0, gold #E3B45A, crimson #D1222F. Slow 0.6 s fades, min text 24 px.
Elements: brand bug, bottom ticker, lower third, "The Brief" card, "Our Take", "The Exchange", progress line,
"The Overview" recap card, "Today's Docket" end card. Zoom gallery 1/2/3/4 tiles auto-detected (ucf/ov_layout.py).
Subscribe x6 per video (corner button, SUBSCRIBE NOW pill, bell banner, Overview buttons, spoken line, docket box).

## Tweaking
* Colours / card layout: `ucf/ov_gfx.py` (CSS + builders).  Zoom tile rules: `ucf/ov_layout.py`.  Timeline/subscribe schedule: `ucf/render_ov.py`.
* Voice, tags, court line, intro length: `style.json -> config`.  Logo = assets/logo_transparent.png (falls back to a CSS gold seal if missing).
* Delete `output/<run>/Video_*/_work/` after changing the look, then re-render.
* Needs: `pip install playwright numpy pillow` + `playwright install chromium`.


## v10 notes

This pack now carries `title_rules.md` (five-title system, style-specific
power-verb/emphasis/hook banks). Run modes (30/60/all), in-case overlays and the boundary
engine live in the shared engine - see the root README.
