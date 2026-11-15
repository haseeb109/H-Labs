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


def whisper_transcribe(media, model="base.en", device="cpu", threads=None, compute_type="int8"):
    """Fallback ASR with faster-whisper. cpu_threads matters: defaults leave the M1 at ~1.3x realtime,
    8 threads gives ~6x. int8 + beam_size=1 stays well ahead of the 18 s caption quality bar.
    A bundled model dir (models/<name>) wins over a Hub download, so an offline machine just works."""
    import os
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")     # Windows without developer mode: harmless warning
    from faster_whisper import WhisperModel  # lazy import
    local = ROOT / "models" / model
    if local.exists():
        model = str(local)
    m = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=threads or os.cpu_count() or 4)
    seg_iter, _ = m.transcribe(str(media), vad_filter=True, beam_size=1, language="en")
    segs = [{"start": s.start, "end": s.end, "text": _clean(s.text)} for s in seg_iter if _clean(s.text)]
    return normalise(segs)


def whisper_safe(media, model="base.en", threads=None, ui=print):
    """whisper_transcribe in a CHILD process. On some Windows PCs the native whisper engine (ctranslate2) crashes the whole
    process with no message (a new PC, 2026-11-15: the run just ended after the model download). A crash here is reported
    with its exit code and retried once with safer settings (float32, 2 threads); the run never dies silently."""
    import os
    import subprocess
    import sys
    import tempfile
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); from ucf import transcript as T; "
            "s = T.whisper_transcribe(sys.argv[2], sys.argv[3], threads=int(sys.argv[4]) or None, compute_type=sys.argv[5]); "
            "json.dump(s, open(sys.argv[6], 'w', encoding='utf-8'))")
    env = dict(os.environ, HF_HUB_DISABLE_SYMLINKS_WARNING="1", KMP_DUPLICATE_LIB_OK="TRUE")
    last = ""
    for ctype, th in (("int8", threads or 0), ("float32", 2)):
        with tempfile.TemporaryDirectory(prefix="whisper_") as t:
            out = os.path.join(t, "segs.json")
            r = subprocess.run([sys.executable, "-c", code, str(ROOT), str(media), model, str(th), ctype, out],
                               stderr=subprocess.PIPE, text=True, env=env)
            if r.returncode == 0 and os.path.exists(out):
                with open(out, encoding="utf-8") as f:
                    return json.load(f)
            tail = "\n".join((r.stderr or "").strip().splitlines()[-6:])
            last = f"exit code {r.returncode} (0x{r.returncode & 0xFFFFFFFF:08X})" + (f":\n{tail}" if tail else "")
            why = (tail.splitlines() or [""])[-1][:160]
            ui(f"  whisper failed ({ctype}): exit code {r.returncode} (0x{r.returncode & 0xFFFFFFFF:08X}) {why}"
               + (" - trying again with safer settings..." if ctype == "int8" else ""))
    raise RuntimeError("whisper (transcript) does not run on this PC - " + last +
                       "\n  Ideas: update Windows + the Microsoft Visual C++ Redistributable (x64), run Setup.bat again, "
                       "or give a transcript with --transcript-file. Send work\\<id>\\run_log.txt to the owner.")


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
