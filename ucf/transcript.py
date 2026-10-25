"""Transcript loading/normalising. Segment = {"start": s, "end": s, "text": str}."""
import json
import re
import subprocess
from pathlib import Path

from .timeutil import fmt_tc

ROOT = Path(__file__).resolve().parent.parent


def _clean(t):
    t = t.replace("​", "").replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip()


def load_nexlev(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = d["transcript"] if isinstance(d, dict) else d
    segs = []
    for r in rows:
        txt = _clean(r.get("text", ""))
        if not txt:
            continue
        s = float(r["startMs"]) / 1000.0
        e = float(r.get("endMs", r["startMs"])) / 1000.0
        segs.append({"start": s, "end": max(e, s), "text": txt})
    return normalise(segs)


def load_json3(path):
    """yt-dlp --write-auto-subs --sub-format json3 output."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    segs = []
    for ev in d.get("events", []):
        if "segs" not in ev:
            continue
        txt = _clean("".join(s.get("utf8", "") for s in ev["segs"]))
        if not txt:
            continue
        s = ev.get("tStartMs", 0) / 1000.0
        e = s + ev.get("dDurationMs", 0) / 1000.0
        segs.append({"start": s, "end": e, "text": txt})
    return normalise(segs)


def load_vtt(path):
    segs = []
    cur = None
    ts = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d+) --> (\d+):(\d\d):(\d\d)[.,](\d+)")
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = ts.search(line)
        if m:
            g = list(map(float, m.groups()))
            s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            cur = {"start": s, "end": e, "text": ""}
            segs.append(cur)
        elif cur is not None and line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:")):
            cur["text"] = (cur["text"] + " " + re.sub(r"<[^>]+>", "", line)).strip()
    return normalise([s for s in segs if s["text"]])


def normalise(segs):
    """Sort by start, drop exact consecutive duplicates (rolling captions)."""
    segs = sorted(segs, key=lambda x: (x["start"], x["end"]))
    out = []
    for s in segs:
        if out and s["text"] == out[-1]["text"] and s["start"] - out[-1]["start"] < 6:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
            continue
        # rolling "A" then "A B" style: if new text starts with previous text, replace
        if out and s["text"].startswith(out[-1]["text"]) and s["start"] - out[-1]["start"] < 6 \
                and len(out[-1]["text"]) > 8:
            out[-1]["text"] = s["text"]
            out[-1]["end"] = max(out[-1]["end"], s["end"])
            continue
        out.append(dict(s))
    return out


def whisper_transcribe(media, model="base.en", device="cpu"):
    """Fallback ASR with faster-whisper. cpu_threads matters: defaults leave the M1 at ~1.3x realtime,
    8 threads gives ~6x. int8 + beam_size=1 stays well ahead of the 18 s caption quality bar.
    A bundled model dir (models/<name>) wins over a Hub download, so an offline machine just works."""
    import os
    from faster_whisper import WhisperModel  # lazy import
    local = ROOT / "models" / model
    if local.exists():
        model = str(local)
    m = WhisperModel(model, device=device, compute_type="int8", cpu_threads=os.cpu_count() or 4)
    seg_iter, _ = m.transcribe(str(media), vad_filter=True, beam_size=1, language="en")
    segs = [{"start": s.start, "end": s.end, "text": _clean(s.text)} for s in seg_iter if _clean(s.text)]
    return normalise(segs)


def load_any(path):
    p = Path(path)
    if p.suffix in (".json", ".json3"):
        txt = p.read_text(encoding="utf-8")[:2000]
        if '"events"' in txt:
            return load_json3(p)
        if '"startMs"' in txt or '"transcript"' in txt:
            return load_nexlev(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, list) and d and "start" in d[0]:
            return d
        raise ValueError("unknown transcript json format")
    if p.suffix in (".vtt", ".srt"):
        return load_vtt(p)
    raise ValueError(f"unsupported transcript file {p}")


def save(segs, path):
    Path(path).write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")


def compact_lines(segs, max_chars=170, max_span=9.0):
    """Merge into '[H:MM:SS] text' lines so the model sees real, citable timecodes."""
    lines, buf, t0, tl = [], [], None, None
    for s in segs:
        if buf and (len(" ".join(buf)) + len(s["text"]) > max_chars or s["start"] - t0 > max_span
                    or s["text"].startswith(">>")):
            lines.append(f"[{fmt_tc(t0)}] {' '.join(buf)}")
            buf, t0 = [], None
        if t0 is None:
            t0 = s["start"]
        buf.append(s["text"])
    if buf:
        lines.append(f"[{fmt_tc(t0)}] {' '.join(buf)}")
    return lines


def words_in(segs, a, b):
    return sum(len(s["text"].split()) for s in segs if a <= s["start"] < b)


def text_in(segs, a, b, limit=None):
    t = " ".join(s["text"] for s in segs if a <= s["start"] < b)
    return t if not limit else t[:limit]
