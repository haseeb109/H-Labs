"""Anti-copy watermark: the channel name in white, 25% opacity, small, jumping to a NEW place on the screen every few seconds
(one place at a time, fading in and out so the jump is not noticeable). Meant to make re-uploads of our videos easy to spot
and hard to crop out.

    python tools/watermark.py video.mp4 "Trial Tales"                      # -> video_wm.mp4
    python tools/watermark.py video.mp4 "Trial Tales" out.mp4 --opacity 0.25 --size 34 --every 9

How it works (one ffmpeg pass, no per-position overlays, so a 1-hour video costs the same as a 1-minute one):
* the name is rendered once to a small transparent PNG with Chromium (same engine as the style graphics)
* geq fades it in/out with a repeating envelope: alpha = opacity * clip(min(p, D-p)/fade, 0, 1), p = t mod D
* overlay moves it: the position is a pseudo-random function of floor(t / D) (+ seed), so it changes exactly when the text is invisible
Video is re-encoded once (audio is copied). Encoder: NVENC / VideoToolbox when available, else x264 crf 18.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "tools" / "watermark_font" / "inter-800.woff2"


def render_text_png(text, out, size=34, font=FONT):
    """Transparent PNG of `text` (white, thin dark halo so it stays readable on bright footage). Returns (w, h)."""
    from playwright.sync_api import sync_playwright
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f'@font-face{{font-family:WM;font-weight:800;src:url({Path(font).resolve().as_uri()})}}'
            f'html,body{{margin:0;background:transparent}}'
            f'#t{{display:inline-block;font:800 {size}px WM,Arial,sans-serif;color:#fff;letter-spacing:.5px;white-space:nowrap;padding:8px 10px;'
            f'text-shadow:0 0 3px rgba(0,0,0,.85),0 1px 2px rgba(0,0,0,.8)}}'
            f'</style></head><body><span id="t"></span></body></html>')
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("HL_CHROMIUM") or None)
        pg = b.new_page(viewport={"width": 1400, "height": 200})
        hp = Path(out).with_suffix(".html")
        hp.write_text(html, encoding="utf-8")
        pg.goto(hp.resolve().as_uri())
        pg.evaluate("t => { document.getElementById('t').textContent = t }", text)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        el = pg.query_selector("#t")
        box = el.bounding_box()
        pg.screenshot(path=str(out), omit_background=True,
                      clip={"x": 0, "y": box["y"], "width": int(box["width"]) + 1 - (int(box["width"]) + 1) % 2, "height": int(box["height"]) + 1 - (int(box["height"]) + 1) % 2})
        b.close()
    try:
        hp.unlink()
    except OSError:
        pass
    from PIL import Image
    w, h = Image.open(out).size
    return w, h


def video_encoder_args():
    """Same choice as the main renderer (NVENC / VideoToolbox when they work), else x264 crf 18."""
    sys.path.insert(0, str(ROOT))
    try:
        from ucf import render
        enc = render.pick_encoder({"encoder": "auto"})
    except Exception:
        enc = "libx264"
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-b:v", "12M", "-pix_fmt", "yuv420p"]
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]


def watermark(src, dst, text, *, opacity=0.25, size=34, every=9.0, fade=0.8, margin=48, seed=0):
    """Burn the moving watermark into `src` -> `dst`. Returns dst."""
    src, dst = Path(src), Path(dst)
    with tempfile.TemporaryDirectory(prefix="wm_") as tmp:
        png = Path(tmp) / "wm.png"
        render_text_png(text, png, size)
        d, f, m, s = float(every), float(fade), int(margin), int(seed)
        k = f"(floor(t/{d})+{s})"
        x = f"{m}+(W-w-{2 * m})*mod(abs(sin({k}*12.9898)*43758.5453),1)"
        y = f"{m}+(H-h-{2 * m})*mod(abs(sin({k}*78.233)*12543.7141),1)"
        p = f"mod(T,{d})"
        alpha = f"alpha(X,Y)*{opacity}*clip(min({p},{d}-{p})/{f},0,1)"
        fc = (f"[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[wm];"
              f"[0:v][wm]overlay=x='{x}':y='{y}':eval=frame:shortest=1:format=auto,format=yuv420p[v]")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-loop", "1", "-framerate", "30", "-i", str(png),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", *video_encoder_args(), "-c:a", "copy", "-movflags", "+faststart", str(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("watermark failed:\n" + r.stderr[-1500:])
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("text", help="channel name, e.g. 'Trial Tales'")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--opacity", type=float, default=0.25)
    ap.add_argument("--size", type=int, default=34, help="font size in px on a 1080p frame")
    ap.add_argument("--every", type=float, default=9.0, help="seconds per position")
    ap.add_argument("--fade", type=float, default=0.8)
    ap.add_argument("--margin", type=int, default=48)
    ap.add_argument("--seed", type=int, default=0, help="changes the position sequence (use a different one per video if you like)")
    a = ap.parse_args()
    out = a.out or str(Path(a.video).with_name(Path(a.video).stem + "_wm.mp4"))
    print("->", watermark(a.video, out, a.text, opacity=a.opacity, size=a.size, every=a.every, fade=a.fade, margin=a.margin, seed=a.seed))


if __name__ == "__main__":
    main()
