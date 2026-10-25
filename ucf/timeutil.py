"""Timecode helpers. Stream clock = seconds (float)."""
import re


def parse_tc(v):
    """'2:23:27' / '23:27' / '1:02:03.5' / 83 -> seconds (float)."""
    if v is None:
        raise ValueError("timecode is None")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("–", "-")
    if not re.fullmatch(r"\d+(:\d{1,2}){0,2}(\.\d+)?", s):
        raise ValueError(f"bad timecode: {v!r}")
    secs = 0.0
    for p in s.split(":"):
        secs = secs * 60 + float(p)
    return secs


def fmt_tc(sec, force_h=True):
    """seconds -> H:MM:SS (stream clock)."""
    sec = int(round(max(0, sec)))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if (h or force_h) else f"{m}:{s:02d}"


def fmt_dur(sec):
    """seconds -> MM:SS where MM may exceed 59 (e.g. 70:00)."""
    sec = int(round(max(0, sec)))
    return f"{sec // 60}:{sec % 60:02d}"


def fmt_chapter(sec):
    """YouTube chapter stamp: M:SS or H:MM:SS, first one must be 0:00 -> '00:00'."""
    sec = int(round(max(0, sec)))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def safe_slug(s, n=40):
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[:n] or "x"
