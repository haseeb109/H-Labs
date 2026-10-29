"""Config + secrets. Keys live in ~/.config/umf/*.env (chmod 600) - never in the repo or in chat."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "channel_name": "Trial Tales",
    "style": "trial_tales",                            # id inside styles/<id>/style.json (editing style pack)
    "style_dir": "styles/trial_tales",
    "intro_seconds_tt": 7.47,                          # length of assets/channel_intro.mp4 (your gavel animation)
    "vo_clip_max": 18.0,                               # EVERY AI-voice clip stays <= this many seconds
    "vo_clip_target": 17.0,
    "wps": 2.6,
    "use_hyperframes": True,                           # animated overlays via HyperFrames (falls back to static PNGs)
    "logo_file": "assets/logo_source.jpg",            # your channel logo (square). Better: a 512px+ PNG
    "logo_corner": "top-left",                         # top-left | top-right | bottom-right | bottom-left
    "logo_size": 132,                                  # watermark width in px (on 1920x1080)
    "logo_opacity": 0.92,
    "logo_on_intro": True,                             # big logo on the generated intro / corner logo on your own intro file
    "coming_up_tag": True,                             # small "COMING UP" label on the hook teaser
    "channel_intro_file": "assets/channel_intro.mp4",   # your 5-8 s animation; if missing a title card is generated
    "output_dir": "output",
    "work_dir": "work",
    "state_dir": "state",
    # --- brain (Master Prompt v9) ---
    "brain": "hive",                       # hive (DeepSeek V4.1 Flash via Hive) | anthropic | deepseek | openai | manual | mock
                                           #   manual = you paste the prompt into Claude and give --plan
                                           #   mock   = offline replay (tests only)
    "model": "claude-sonnet-5-5",          # active model; run_stream swaps in provider_models[brain] if left at the default
    "provider_models": {"hive": "deepseek-ai/deepseek-v4.1-flash-1017", "anthropic": "claude-sonnet-5-5",
                        "deepseek": "deepseek-flash", "openai": "gpt-4o"},
    "max_tokens": 32000,
    "effort": "medium",                    # anthropic thinking depth: low | medium | high | xhigh | max | "" (= model default)
                                           #   at the model default (high) Pass A spent ~59k of 64k tokens thinking
    "max_repair_rounds": 2,
    # --- stream handling ---
    "cookies_file": "",                    # ONLY a burner account's cookies.txt, and only if YouTube blocks downloads
    "max_height": 1080,
    "notify_when_done": True,              # desktop notification + sound when a run ends (or stops on an error)
    "open_output_after_run": True,         # open the output folder at the end of a run
    "cleanup_after_run": "ask",            # ask | always | never - delete the downloaded stream + render temp files (never the videos)
    "watermark": True,                      # anti-copy watermark in every video (see ucf/watermark.py); --no-watermark switches it off for one run
    "watermark_text": "",                   # "" = channel_name of the style
    "watermark_opacity": 0.25,
    "watermark_size": 34,                   # px on a 1080p frame
    "watermark_every": 9.0,                 # seconds per position
    "watermark_fade": 0.8,
    "watermark_margin": 48,
    "download_sort": "",                    # yt-dlp -S sort for the stream download; "" = yt-dlp default. "res,br" = best bitrate at the top resolution
    "captions": "auto",                    # auto = YouTube captions first, whisper if missing/sparse | whisper
    "whisper_model": "base.en",
    # --- rendering ---
    "encoder": "auto",                     # auto | libx264 | h264_videotoolbox | h264_nvenc
    "x264_preset": "medium",               # only used when no GPU encoder is available: medium (best) | fast | veryfast (quicker renders)
    "x264_crf": 16,                        # lower = better quality / bigger file (16 is near-transparent)
    "runtime_min": 20 * 60,                # a video is 20-30 min (owner rule, Oct 2026)
    "runtime_max": 30 * 60,
    "allow_long_solo": True,               # one strong 25+ min case may exceed the cap (Master Prompt Rule 4)
    "hook_min": 10.0,                       # hook teaser 10-15 s (owner rule, Oct 2026)
    "hook_max": 15.0,
    "cut_pad_in": 0.0,
    "cut_pad_out": 0.5,
    "final_min_hold": 12.0,
    "final_max_hold": 60.0,
    "vo_lead": 0.35,
    "vo_tail": 0.6,
    "loudness_lufs": -14,
    "burn_captions": False,                # word-by-word captions burned into the video (ucf/captions.py) - off by owner choice
    "audio_cleanup": True,                 # court speech: band-limit + even out speakers + denoise + soft gate
    # --- v10: run modes, titles, overlays, boundary, reports ---
    "mode": "60",                          # "30" | "60" | "all" (preset bands below; legacy custom band if unset)
    "modes": {
        "30": {"runtime_min": 20 * 60, "runtime_max": 40 * 60},      # v9 native band
        "60": {"runtime_min": 50 * 60, "runtime_max": 70 * 60},
        "all": {"min_case_minutes": 8.0},
    },
    "min_case_minutes": 8.0,               # mode "all": minimum hearing per standalone video
    "judge_name": "Judge Boyd",            # brand name for titles; brain confirms/corrects from transcript
    "title_system": "v10",                 # "v10" = 5 titles | "v9" = legacy 2-title rules
    "overlays": {"enabled": True, "every_s": 270, "min_gap_s": 180, "skip_head_s": 40, "skip_tail_s": 30,
                 "dur_s": 7.0, "max_words": 20},
    "boundary": {"enabled": True, "window_s": 120, "vision_check": False, "vision_model": "claude-sonnet-5-5",
                 "ocr": "auto",            # auto | rapidocr | ocrmac | off
                 "weights": {"next_call": 3.0, "wrap_up": 2.0, "tile_count": 1.5, "tile_label": 1.5,
                             "last_name": 1.0, "silence": 1.0, "before_ruling": -4.0, "call_inside": -5.0}},
    "brain_two_pass": "auto",              # auto (= on for mode all) | on | off
    "brain_pass_a": "",                    # hybrid: provider for Pass A inventory ("" = same as brain)
    "brain_pass_b": "",                    # hybrid: provider for Pass B packaging ("" = same as brain)
    "brain_fallback": "",                  # OFF (owner decision 2026-10-29: everything runs on Hive, no Claude fallback). A provider name here
                                           #   would retry a failed case on that brain - leave it empty.
    "brain_attempts": 3,                   # fresh conversations per pass on the same brain before a pass counts as failed (mode all)
    "prompt_examples": "auto",             # gold Pass A/B examples in the prompt: auto = every brain except anthropic
    "reuse_guard": True,                   # warn when a case was already rendered on another style
    # --- voice ---
    "tts_order": ["ai33", "voicestudio", "say"],
    "ai33_voice": "elevenlabs_nPczCjzI2devNBz1zQrb",      # Brian (deep). Andres documentary: elevenlabs_z9ihBMCAnrOeGUbPDiwi
    "ai33_script": "tools/ai33_tts.py",                 # bundled copy of your UMF ai33.pro helper (reads ~/.config/umf/ai33.env)
    "voicestudio_url": "http://127.0.0.1:3900/v1/audio/speech",
    "voicestudio_voice": "alloy",
    "say_voice": "Daniel",
    "tts_confirm_chars": 5000,             # more than this per run needs --confirm-tts (after you said yes in chat)
    # --- metadata ---
    "base_tags": ["judge boyd", "judge stephanie boyd", "judge boyd sentencing", "judge boyd courtroom",
                  "courtroom drama", "courtroom drama texas", "court cam", "courtroom footage", "real courtroom",
                  "court hearing", "sentencing day", "187th district court"],
    "source_credit": "Source footage: public proceedings of the 187th District Court, Bexar County, Texas "
                     "(livestream: {source_url}). Re-edited with original narration and on-screen context for commentary and education.",
}


def _find_style_dir(sid):
    """styles/<sid>/ if it holds a style.json, else scan packs for a matching id."""
    d = ROOT / "styles" / sid
    if (d / "style.json").exists():
        return d
    for d in sorted((ROOT / "styles").glob("*/style.json")) if (ROOT / "styles").exists() else []:
        try:
            if json.loads(d.read_text(encoding="utf-8")).get("id") == sid:
                return d.parent
        except Exception:
            continue
    return None


def load(path=None, style=None):
    """Merge order: engine DEFAULTS <- style pack (style.json) <- config.json <- env. CLI flags win last."""
    cfg = dict(DEFAULTS)
    p = Path(path) if path else ROOT / "config.json"
    user = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    sid = style or user.get("style") or cfg["style"]
    d = _find_style_dir(str(sid))
    if d:
        cfg["style"], cfg["style_dir"] = str(sid), d.relative_to(ROOT).as_posix()
        s = json.loads((d / "style.json").read_text(encoding="utf-8"))
        cfg["_renderer"] = s.get("renderer", "tt")
        cfg["_look"] = s.get("look", "tt")                  # "ov" = Overruled renderer (same locked structure family)
        cfg["_prompt_extra"] = s.get("prompt_extra")
        cfg["_title_rules"] = s.get("title_rules")
        cfg["_prompt_master"] = s.get("prompt_master", "prompts/master_v9.md")
        cfg["_prompt_addendum"] = s.get("prompt_addendum", "prompts/json_addendum.md")
        for k, v in (s.get("config") or {}).items():
            if k in ("logo_file", "channel_intro_file") and not Path(v).is_absolute():
                v = f"{cfg['style_dir']}/{v}"
            cfg[k] = v
    else:
        raise RuntimeError(f"editing style '{sid}' not found - expected styles/{sid}/style.json "
                           f"(available: {[d.parent.name for d in (ROOT / 'styles').glob('*/style.json')]})")
    for k, v in user.items():
        if not k.startswith("_"):
            cfg[k] = v
            if k == "mode":
                cfg["_mode_source"] = "config"
    if "_mode_source" not in cfg:
        cfg["_mode_source"] = "default"
    load_env()
    return cfg


def apply_mode(cfg, cli_mode=None):
    """Resolve the run mode and its band. Precedence: CLI > config.json > DEFAULTS.
    No explicit mode anywhere -> the config.json band stands untouched (legacy behaviour).
    Returns the resolved mode ('custom' when the band came straight from config.json)."""
    mode = cli_mode or (cfg.get("mode") if cfg.get("_mode_source") in ("config", "cli") else None)
    if cli_mode:
        cfg["_mode_source"] = "cli"
    if mode and str(mode) in cfg.get("modes", {}):
        cfg["mode"] = str(mode)
        cfg.update(cfg["modes"][str(mode)])
    elif not mode:
        cfg["mode"] = "custom"
    return cfg["mode"]


def style_list():
    """All installed style pack ids."""
    root = ROOT / "styles"
    out = []
    for sj in sorted(root.glob("*/style.json")) if root.exists() else []:
        try:
            out.append(json.loads(sj.read_text(encoding="utf-8")).get("id", sj.parent.name))
        except Exception:
            out.append(sj.parent.name)
    return out


def style_path(cfg, rel=""):
    """Absolute path inside the active style pack."""
    d = Path(cfg["style_dir"])
    if not d.is_absolute():
        d = ROOT / d
    return d / rel if rel else d


def load_env():
    d = Path.home() / ".config" / "umf"
    if not d.exists():
        return
    for f in d.glob("*.env"):
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rel(cfg, key):
    p = Path(os.path.expanduser(cfg[key]))
    return p if p.is_absolute() else ROOT / p
