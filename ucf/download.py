"""yt-dlp wrappers. Must run on a residential IP (the Mac / HP laptop) - cloud IPs get bot-blocked."""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _cmd(cfg):
    base = [shutil.which("yt-dlp")] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]
    if shutil.which("node") and not shutil.which("deno"):
        base += ["--js-runtimes", "node"]
    if cfg.get("cookies_file"):
        base += ["--cookies", str(Path(cfg["cookies_file"]).expanduser())]
    for extra in cfg.get("yt_dlp_extra_args") or []:
        base += [str(extra)]
    return base


def info(url, cfg):
    r = subprocess.run(_cmd(cfg) + ["-J", "--no-playlist", url], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp could not read the URL:\n" + r.stderr[-1500:] + _hint(r.stderr))
    d = json.loads(r.stdout)
    return {"id": d["id"], "title": d.get("title", ""), "duration": float(d.get("duration") or 0),
            "upload_date": d.get("upload_date", ""), "channel": d.get("channel", ""),
            "is_live": bool(d.get("is_live")), "was_live": bool(d.get("was_live")),
            "url": d.get("webpage_url", url)}


def _hint(stderr):
    if "Sign in to confirm" in stderr or "bot" in stderr.lower():
        return ("\nHINT: YouTube is blocking this IP. Run this on your own computer (not a server/VPN). "
                "Last resort: set config.json cookies_file to a BURNER account's cookies.txt - never a main account.")
    return ""


def fetch_video(url, vid, workdir, cfg):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "source.mp4"
    if out.exists() and out.stat().st_size > 10_000_000:
        return out
    h = int(cfg.get("max_height", 1080))
    fmt = f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]"
    sort = cfg.get("download_sort") or ""        # e.g. "res,br": highest resolution, then highest bitrate (any codec)
    r = subprocess.run(_cmd(cfg) + (["-S", sort] if sort else []) + ["-f", fmt, "--merge-output-format", "mp4", "--no-playlist",
                                    "-o", str(workdir / "source.%(ext)s"), "--newline", url])
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("video download failed" + _hint(""))
    return out


def fetch_captions(url, workdir, cfg):
    """-> path to json3 auto-captions, or None."""
    workdir = Path(workdir)
    for f in workdir.glob("subs*.json3"):
        return f
    subprocess.run(_cmd(cfg) + ["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,en",
                                "--sub-format", "json3", "--no-playlist", "-o", str(workdir / "subs"), url],
                   capture_output=True, text=True)
    # prefer the cleaned en track over the raw en-orig ASR dump
    if (workdir / "subs.en.json3").exists():
        return workdir / "subs.en.json3"
    for f in sorted(workdir.glob("subs*.json3")):
        return f
    return None
