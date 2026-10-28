"""Anti-copy watermark (every style, on by default): the channel name in white, 25% opacity, small, jumping to a NEW place
on the screen every few seconds - one place at a time, fading in and out so the jump is not noticeable. Purpose: re-uploads of
our videos are easy to spot and hard to crop out.

One ffmpeg pass, no per-position overlays (a 1-hour video costs the same per second as a 1-minute one):
* the name is drawn once to a small transparent PNG with Pillow (no browser needed)
* geq fades it in/out with a repeating envelope: alpha = opacity * clip(min(p, D-p)/fade, 0, 1), p = t mod D
* overlay moves it: the position is a pseudo-random function of floor(t / D) + seed, so it changes exactly when the text is invisible
The video is re-encoded once with the same encoder as the rest of the pipeline; audio is copied untouched.

Config keys (config.json or style.json -> config):  watermark (true) | watermark_text ("" = channel_name) | watermark_opacity (0.25)
| watermark_size (34 px on a 1080p frame) | watermark_every (9 s per position) | watermark_fade (0.8 s) | watermark_margin (48 px).
Switch off for one run: `run_stream.py ... --no-watermark`.   Stand-alone: `python tools/watermark.py video.mp4 "Channel Name"`.
"""
import os
import subprocess
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "tools" / "watermark_font" / "Inter-ExtraBold.ttf"


def render_text_png(text, out, size=34, font=FONT):
    """White text with a thin dark halo (stays readable on bright footage) on a transparent PNG. -> (w, h)."""
    ft = ImageFont.truetype(str(font), int(size))
    x0, y0, x1, y1 = ft.getbbox(text)
    pad = max(8, int(size * 0.3))
    w, h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    w, h = w + (w % 2), h + (h % 2)
    halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(halo).text((pad - x0, pad - y0 + 1), text, font=ft, fill=(0, 0, 0, 215))
    halo = halo.filter(ImageFilter.GaussianBlur(max(1.2, size / 14)))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im.alpha_composite(halo)
    ImageDraw.Draw(im).text((pad - x0, pad - y0), text, font=ft, fill=(255, 255, 255, 255))
    im.save(out)
    return w, h


def filter_graph(opacity=0.25, every=9.0, fade=0.8, margin=48, seed=0):
    d, f, m, s = float(every), float(fade), int(margin), int(seed)
    k = f"(floor(t/{d})+{s})"
    x = f"{m}+(W-w-{2 * m})*mod(abs(sin({k}*12.9898)*43758.5453),1)"
    y = f"{m}+(H-h-{2 * m})*mod(abs(sin({k}*78.233)*12543.7141),1)"
    p = f"mod(T,{d})"
    alpha = f"alpha(X,Y)*{float(opacity)}*clip(min({p},{d}-{p})/{f},0,1)"
    return (f"[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[wm];"
            f"[0:v][wm]overlay=x='{x}':y='{y}':eval=frame:shortest=1:format=auto,format=yuv420p[v]")


def _encoder_args(enc=None):
    from .render import pick_encoder, venc
    return venc(enc or pick_encoder({"encoder": "auto"}))


def apply(src, dst, text, *, opacity=0.25, size=34, every=9.0, fade=0.8, margin=48, seed=0, enc=None):
    """Burn the moving watermark into `src` -> `dst` (different files). Returns dst."""
    import tempfile
    src, dst = Path(src), Path(dst)
    with tempfile.TemporaryDirectory(prefix="wm_") as tmp:
        png = Path(tmp) / "wm.png"
        render_text_png(text, png, size)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-loop", "1", "-framerate", "30", "-i", str(png),
               "-filter_complex", filter_graph(opacity, every, fade, margin, seed), "-map", "[v]", "-map", "0:a?",
               *_encoder_args(enc), "-c:a", "copy", "-movflags", "+faststart", str(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("watermark failed:\n" + r.stderr[-1500:])
    return dst


def text_for(cfg):
    return (cfg.get("watermark_text") or cfg.get("channel_name") or cfg.get("style") or "").strip()


def enabled(cfg):
    return bool(cfg.get("watermark", True)) and bool(text_for(cfg))


def apply_in_place(path, cfg, seed_key, enc=None, ui=print):
    """Pipeline hook: watermark the finished video.mp4 in place. Returns the text used, or None when the watermark is off.
    Raises on failure (the original file is left untouched)."""
    if not enabled(cfg):
        return None
    path = Path(path)
    text = text_for(cfg)
    seed = zlib.crc32(str(seed_key).encode()) % 997           # different position sequence for every video
    tmp = path.with_name(path.stem + ".wm_tmp.mp4")
    ui(f"  watermark '{text}' ({int(cfg.get('watermark_opacity', 0.25) * 100)}%, new place every {cfg.get('watermark_every', 9.0):g} s)...")
    try:
        apply(path, tmp, text, opacity=cfg.get("watermark_opacity", 0.25), size=cfg.get("watermark_size", 34),
              every=cfg.get("watermark_every", 9.0), fade=cfg.get("watermark_fade", 0.8), margin=cfg.get("watermark_margin", 48),
              seed=seed, enc=enc)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return text
