"""yt-dlp wrappers. Must run on a residential IP (the Mac / HP laptop) - cloud IPs get bot-blocked."""
import json
import os
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
    # the best video YouTube offers (same rule as video_format: no AV1) - used to spot a cached download that is worse
    vids = [f for f in d.get("formats") or [] if f.get("vcodec") not in (None, "none") and f.get("height")
            and not str(f.get("vcodec", "")).startswith("av01") and int(f["height"]) <= int(cfg.get("max_height", 1080))]
    best_h = max((int(f["height"]) for f in vids), default=0)
    best_vbr = max((float(f.get("vbr") or f.get("tbr") or 0) for f in vids if int(f["height"]) == best_h), default=0)
    return {"id": d["id"], "title": d.get("title", ""), "duration": float(d.get("duration") or 0),
            "best_height": best_h, "best_kbps": round(best_vbr),
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


def video_format(cfg):
    """yt-dlp -f for the stream. NO codec filter on the first choice: YouTube's H.264 (avc1) 720p of a Zoom stream is often
    ~0.5 Mbps while the VP9 720p of the same stream is ~1.7 Mbps (3x the detail) - an avc1-only filter made `-S res,br` pick the
    starved one every time. AV1 is left out (slow to decode on CPU, not in every ffmpeg build); VP9 goes into the mp4 untouched."""
    h = int(cfg.get("max_height", 1080))
    return (f"bv*[height<={h}][vcodec!^=av01]+ba[ext=m4a]/bv*[height<={h}][vcodec!^=av01]+ba/"
            f"bv*[height<={h}]+ba/b[height<={h}]")


def probe_video(path):
    """-> (height, video bits per second) of a downloaded stream, (0, 0) when unreadable."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height,bit_rate:format=duration",
                            "-of", "json", str(path)], capture_output=True, text=True)
        d = json.loads(r.stdout or "{}")
        st, dur = (d.get("streams") or [{}])[0], float((d.get("format") or {}).get("duration") or 0)
        vbr = float(st.get("bit_rate") or 0) or (Path(path).stat().st_size * 8 / dur - 130_000 if dur else 0)
        return int(st.get("height") or 0), vbr
    except Exception:
        return 0, 0


def worse_than_available(path, meta):
    """Reason string when a downloaded file is clearly below what YouTube offers for this stream (else '')."""
    bh, bk = int(meta.get("best_height") or 0), float(meta.get("best_kbps") or 0)
    if not bh:
        return ""
    h, vbr = probe_video(path)
    if h and h < bh - 10:
        return f"{h}p but YouTube has {bh}p"
    if h and vbr and bk and vbr < bk * 1000 * 0.6:
        return f"{vbr / 1e6:.2f} Mbps but YouTube has {bk / 1000:.2f} Mbps"
    return ""


def describe(path, meta=None):
    """-> (one line 'source: 1280x720 vp9 30fps 1.68 Mbps', low_bitrate_bool) for a downloaded stream. With `meta` (info()), a low
    bitrate that is simply the best YouTube has for this stream is said as such (re-downloading would not help)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,avg_frame_rate,bit_rate:format=bit_rate,duration",
                            "-of", "json", str(path)], capture_output=True, text=True)
        d = json.loads(r.stdout or "{}")
        if not d.get("streams"):
            return "source: could not read the video stream", False
        st, fo = d["streams"][0], d.get("format") or {}
        size = Path(path).stat().st_size
        dur = float(fo.get("duration") or 0)
        vbr = float(st.get("bit_rate") or 0) or (size * 8 / dur - 130_000 if dur else 0)   # webm/vp9 streams often have no bit_rate
        num, _, den = str(st.get("avg_frame_rate", "0/1")).partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0
        h = int(st.get("height") or 0)
        low = bool(vbr) and h >= 700 and vbr < 900_000
        best = float((meta or {}).get("best_kbps") or 0) * 1000
        if low and best and vbr >= best * 0.6:
            note = "   (low, but it is the best YouTube has for this stream - the footage itself will look soft)"
        elif low:
            note = ("   <- LOW bitrate: this file looks soft. Delete it (work\\<id>\\source.mp4) and run again to re-download"
                    " the best version")
        else:
            note = ""
        line = f"source: {st.get('width')}x{h} {st.get('codec_name')} {fps:.0f}fps {vbr / 1e6:.2f} Mbps video" + note
        return line, low
    except Exception as e:
        return f"source: could not read ({e})", False


def fetch_video(url, vid, workdir, cfg, meta=None):
    """Download the stream. With `meta` (from info()), a download that comes out below the best YouTube offers (some fallback
    clients only get 360p) is kept aside while the next strategy tries for the real quality; the best file wins."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "source.mp4"
    low = workdir / "source_low.mp4"
    if out.exists() and out.stat().st_size > 10_000_000:
        return out
    fmt = video_format(cfg)
    sort = cfg.get("download_sort") or ""        # "res,br": highest resolution, then highest bitrate (any codec)
    tries = _strategies(cfg)
    for k, (name, extra) in enumerate(tries, 1):
        if k > 1:
            print(f"\n  download failed - trying again with {name} ({k}/{len(tries)})...", flush=True)
        r = subprocess.run(_cmd(cfg, extra) + (["-S", sort] if sort else []) + ["-f", fmt, "--merge-output-format", "mp4", "--no-playlist",
                                        "-o", str(workdir / "source.%(ext)s"), "--newline", url])
        if r.returncode == 0 and out.exists():
            print("  " + describe(out, meta)[0], flush=True)
            why = worse_than_available(out, meta or {})
            if why and k < len(tries):
                print(f"  this download is {why} - keeping it aside and trying the next way for the full quality", flush=True)
                if not low.exists() or probe_video(out)[0] > probe_video(low)[0]:
                    os.replace(out, low)
                else:
                    out.unlink()
                continue
            if low.exists():
                low.unlink()
            return out
    if low.exists():                               # nothing better came: use the best one we got
        os.replace(low, out)
        print("  (the full quality could not be downloaded - using the best copy: " + describe(out)[0] + ")", flush=True)
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
