"""HyperFrames bridge: renders the Trial Tales motion overlays (hook labels, 'CASE STARTED', 'Nth Case')
as transparent WebM clips from HTML compositions.  Falls back to static PNG overlays (cards.py) when
HyperFrames / Chrome / libvpx are not available, so the pipeline never blocks on it."""
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_HF_DIR = Path(__file__).resolve().parent.parent / "styles" / "trial_tales" / "hf"


def _hf_dir(cfg=None):
    if cfg:
        from .config import style_path
        d = style_path(cfg, "hf")
        if d.exists():
            return d
    return DEFAULT_HF_DIR


def available():
    if not shutil.which("hyperframes") and not shutil.which("npx"):
        return False
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return "libvpx-vp9" in enc


def ordinal(n):
    if n == 1:
        return "1st"
    if n == 2:
        return "2nd"
    if n == 3:
        return "3rd"
    return f"{n}th"


def _body(kind, text, text2):
    t = html.escape(text)
    t2 = html.escape(text2 or "")
    if kind == "hook":
        return ('<div class="bar" id="lbl_bar"></div><div class="box" id="lbl_box">In This Case</div>'
                '<div class="bar" id="hl_bar"></div><div class="box" id="hl_box">%s</div>' % t), \
               ["lbl_bar", "lbl_box", "hl_bar", "hl_box"]
    if kind == "case_started":
        return '<div class="lime" id="cs">CASE STARTED</div>', ["cs"]
    if kind == "nth":
        return '<div class="bar" id="nth_bar"></div><div class="box" id="nth_box">%s</div>' % t, ["nth_bar", "nth_box"]
    raise ValueError(kind)


def render_overlay(kind, text, dur, out_webm, work, text2="", cfg=None):
    """Render one overlay to a transparent 1920x1080 30fps WebM. Returns the path or None on failure."""
    work = Path(work)
    hf_dir = _hf_dir(cfg)
    key = f"{kind}_{int(__import__("hashlib").md5(f"{kind}|{text}|{text2}|{dur:.2f}".encode()).hexdigest()[:8], 16)}"
    proj = work / f"hfproj_{key}"
    proj.mkdir(parents=True, exist_ok=True)
    for sub in ("fonts",):
        dst = proj / sub
        if not dst.exists():
            try:
                dst.symlink_to(hf_dir / sub, target_is_directory=True)
            except OSError:
                shutil.copytree(hf_dir / sub, dst)
    g = proj / "gsap.min.js"
    if not g.exists():
        try:
            g.symlink_to(hf_dir / "gsap.min.js")
        except OSError:
            shutil.copy(hf_dir / "gsap.min.js", g)
    body, els = _body(kind, text, text2)
    tpl = (hf_dir / "overlay_template.html").read_text(encoding="utf-8")
    page = (tpl.replace("__DUR__", f"{dur:.3f}").replace("__BODY__", body).replace("__ELS__", json.dumps(els)))
    (proj / "index.html").write_text(page, encoding="utf-8")
    out_webm = Path(out_webm)
    out_webm.parent.mkdir(parents=True, exist_ok=True)
    # on Windows npm shims are .cmd files, which CreateProcess cannot launch from a bare list
    if shutil.which("hyperframes"):
        cmd = (["cmd", "/c", "hyperframes"] if os.name == "nt" else ["hyperframes"])
    else:
        cmd = (["cmd", "/c", "npx", "-y", "hyperframes"] if os.name == "nt" else ["npx", "-y", "hyperframes"])
    cmd = cmd + ["render", str(proj), "--format", "webm", "-o", str(out_webm), "--fps", "30", "--quiet", "--workers", "2"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or not out_webm.exists():
        return None
    return out_webm
