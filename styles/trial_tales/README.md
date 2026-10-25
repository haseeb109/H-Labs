# Style pack: Trial Tales (locked)

The original locked editing style — dark fleur-de-lis canvas, footage strip at 1920x540/y=270,
orange "In This Case" hook label, lime CASE STARTED, AI recap clips <= 18 s, gavel intro.

```
style.json     id, which renderer engine ("tt"), prompt files, style-level config knobs
assets/        bg_plain.png, bg_logo.png, logo_gold(_2x).png, logo_source.jpg, channel_intro.mp4
hf/            overlay_template.html (motion labels, CSS) + fonts/ + gsap.min.js
prompts/       master_v9.md (CASE BUILD ORDER) + json_addendum.md (plan JSON schema)
```

## Tweaking this style

* Logo / intro clip / canvas: replace the files in `assets/` (canvas: run `python3 tools/make_canvas.py`
  with `HL_STYLE_DIR=styles/trial_tales`), or edit the knobs in `style.json -> config`.
* Label motion, colors, fonts: edit `hf/overlay_template.html` and drop new `.woff2` into `hf/fonts/`.
* Content rules (hook seconds, bridge word budgets, title rules): `prompts/master_v9.md` + `style.json`.
* After changing renderer-level things, delete the run's `output/<date>_<id>/Video_*/_work/` cache
  (cached parts would keep the old look), then re-render.

## Adding a new style (2nd channel)

1. Copy this folder to `styles/<new-channel>/`, rename inside `style.json` (`id`, `name`),
   swap the assets, tweak the template and prompts.
2. `config.json` stays channel-agnostic (runtime band, brain, TTS live there).
3. The launcher lists every `styles/*/style.json` and asks which style to use on each run;
   CLI: `--style <id>`.
4. If the new style needs different editing STRUCTURE (not just look), that is a renderer job -
   ask the coding agent to add a renderer module and point `"renderer"` at it.


## v10 notes

This pack now carries `title_rules.md` (five-title system, style-specific
power-verb/emphasis/hook banks). Run modes (30/60/all), in-case overlays and the boundary
engine live in the shared engine - see the root README.
