"""yt-dlp wrappers. Must run on a residential IP (the Mac / HP laptop) - cloud IPs get bot-blocked."""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _cmd(cfg, extra=None):
    """yt-dlp command prefix. `extra` (list) replaces config yt_dlp_extra_args (used by the download fallbacks)."""
    base = [shutil.which("yt-dlp")] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]
    if shutil.which("node") and not shutil.which("deno"):
        base += ["--js-runtimes", "node"]
    if cfg.get("cookies_file"):
        base += ["--cookies", str(Path(cfg["cookies_file"]).expanduser())]
    for e in (cfg.get("yt_dlp_extra_args") or []) if extra is None else extra:
        base += [str(e)]
    return base


_HELP = []


def _supports(flag):
    """True when the installed yt-dlp knows `flag` (older versions abort on unknown options)."""
    if not _HELP:
        r = subprocess.run(_cmd({}, extra=[]) + ["--help"], capture_output=True, text=True)
        _HELP.append(r.stdout or "")
    return flag in _HELP[0]


def info(url, cfg):
    r = None
    for _name, extra in _strategies(cfg):             # same fallbacks as the download
        r = subprocess.run(_cmd(cfg, extra) + ["-J", "--no-playlist", url], capture_output=True, text=True)
        if r.returncode == 0:
            break
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


def _strategies(cfg):
    """Ways to ask YouTube for the video, in order. YouTube changes which player clients work every few weeks (the 'android'
    client currently returns no URLs / 'page needs to be reloaded'), so a failed download tries the next one automatically.
    -> [(name, extra args replacing config yt_dlp_extra_args)]"""
    sleep = ["--sleep-requests", "1"]
    solver = ["--remote-components", "ejs:github"] if _supports("--remote-components") else []   # JS challenge solver (needs node)
    return [("configured clients", None),
            ("yt-dlp default clients", solver + sleep),
            ("tv + web_safari clients", ["--extractor-args", "youtube:player_client=tv,web_safari,mweb"] + solver + sleep)]


def fetch_video(url, vid, workdir, cfg):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "source.mp4"
    if out.exists() and out.stat().st_size > 10_000_000:
        return out
    h = int(cfg.get("max_height", 1080))
    fmt = f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]"
    sort = cfg.get("download_sort") or ""        # e.g. "res,br": highest resolution, then highest bitrate (any codec)
    tries = _strategies(cfg)
    for k, (name, extra) in enumerate(tries, 1):
        if k > 1:
            print(f"\n  download failed - trying again with {name} ({k}/{len(tries)})...", flush=True)
        r = subprocess.run(_cmd(cfg, extra) + (["-S", sort] if sort else []) + ["-f", fmt, "--merge-output-format", "mp4", "--no-playlist",
                                        "-o", str(workdir / "source.%(ext)s"), "--newline", url])
        if r.returncode == 0 and out.exists():
            return out
    raise RuntimeError("video download failed after " + str(len(tries)) + " tries. Update yt-dlp (H Labs.bat -> option 8) and run again; "
                       "if it keeps failing send the first ERROR line." + _hint(""))


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
