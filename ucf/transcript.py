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


GPU_MIN_FREE_MB = 2000          # a small model needs ~1-2 GB of GPU memory; below this the CPU is the safer choice
GPU_OPT_IN = ROOT / "runtime" / "whisper_gpu.txt"      # "on" / "off", written by tools/win/setup.ps1 (the CUDA libraries are an extra download)
LAST = {"device": None, "x_realtime": None, "why": ""}  # what the last whisper_safe call used (smoke test, the run's events)


def gpu_opted_in():
    """The owner chose 'whisper on the GPU' in setup (HL_WHISPER_DEVICE=cuda / cpu overrides it). Default off."""
    import os
    env = os.environ.get("HL_WHISPER_DEVICE", "").strip().lower()
    if env in ("cpu", "cuda"):
        return env == "cuda"
    try:
        return GPU_OPT_IN.read_text(encoding="utf-8").strip().lower().startswith("on")
    except OSError:
        return False


def gpu_free_mb():
    """Free memory (MB) of the NVIDIA GPU with the most room, from nvidia-smi; None when there is no NVIDIA GPU / driver."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    vals = [int(x) for x in (r.stdout or "").split() if x.isdigit()]
    return max(vals) if vals else None


def choose_device(min_free_mb=GPU_MIN_FREE_MB):
    """-> ('cuda' | 'cpu', reason). Cheap and safe: nothing is imported here, only nvidia-smi is asked. The libraries themselves
    are checked in the child process (cuda_ready), so a broken CUDA install degrades to the CPU instead of crashing the run."""
    if not gpu_opted_in():
        return "cpu", "GPU whisper is off - Setup.bat asks once"
    free = gpu_free_mb()
    if free is None:
        return "cpu", "no NVIDIA GPU found (nvidia-smi missing)"
    if free < min_free_mb:
        return "cpu", f"only {free} MB of GPU memory free (needs {min_free_mb})"
    return "cuda", f"{free} MB of GPU memory free"


def _cuda_dll_dirs():
    """Folders of the pip nvidia-cublas / nvidia-cudnn wheels (site-packages/nvidia/<lib>/bin on Windows, .../lib on Linux)."""
    import os
    import sys
    out = []
    for base in sys.path:
        root = Path(base) / "nvidia"
        if root.is_dir():
            for sub in ("bin", "lib"):
                out += [str(d) for d in sorted(root.glob(f"*/{sub}")) if d.is_dir()]
    if os.name == "nt":                      # Python 3.8+ ignores PATH for DLL loading: register the folders
        for d in out:
            try:
                os.add_dll_directory(d)
            except (OSError, AttributeError):
                pass
    if out:
        os.environ["PATH"] = os.pathsep.join(out + [os.environ.get("PATH", "")])
    return out


def cuda_ready():
    """Run in the CHILD process before the model loads: a GPU is there and the CUDA libraries really load. Raises RuntimeError
    with a one-line reason (the parent prints it and goes on with the CPU)."""
    import ctypes
    import os
    _cuda_dll_dirs()
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
    except Exception as e:  # noqa - any import / driver failure just means 'no GPU whisper here'
        raise RuntimeError(f"CUDA not usable: {type(e).__name__}: {str(e)[:120]}")
    if n < 1:
        raise RuntimeError("CUDA not usable: the driver reports no GPU for whisper")
    for nm in (("cublas64_12.dll", "cudnn64_9.dll") if os.name == "nt" else ("libcublas.so.12", "libcudnn.so.9")):
        try:
            ctypes.CDLL(nm)
        except OSError:
            raise RuntimeError(f"CUDA libraries missing ({nm} does not load) - run Setup.bat and say yes to 'whisper on the GPU'")


def _media_seconds(media):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(media)],
                           capture_output=True, text=True, timeout=30)
        return float((r.stdout or "").strip() or 0) or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def whisper_transcribe(media, model="base.en", device="cpu", threads=None, compute_type="int8", vad=True):
    """Fallback ASR with faster-whisper. cpu_threads matters: defaults leave the M1 at ~1.3x realtime,
    8 threads gives ~6x. int8 + beam_size=1 stays well ahead of the 18 s caption quality bar.
    A bundled model dir (models/<name>) wins over a Hub download, so an offline machine just works."""
    import os
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")     # Windows without developer mode: harmless warning
    if device == "cuda":
        cuda_ready()                           # raises one clear RuntimeError when the CUDA libraries are not usable
    from faster_whisper import WhisperModel  # lazy import
    local = ROOT / "models" / model
    if local.exists():
        model = str(local)
    m = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=threads or os.cpu_count() or 4)
    seg_iter, _ = m.transcribe(str(media), vad_filter=bool(vad), beam_size=1, language="en")
    segs = [{"start": s.start, "end": s.end, "text": _clean(s.text)} for s in seg_iter if _clean(s.text)]
    return normalise(segs)


def msvc_runtime_version():
    """Version of the Microsoft C++ runtime (System32\\msvcp140.dll) on Windows, e.g. (14, 44, 35211, 0); None if missing/not Windows."""
    import os
    import sys
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "msvcp140.dll")
        if not os.path.exists(path):
            return None
        ver = ctypes.WinDLL("version")
        n = ver.GetFileVersionInfoSizeW(path, None)
        buf = ctypes.create_string_buffer(n)
        ver.GetFileVersionInfoW(path, 0, n, buf)
        p, ln = ctypes.c_void_p(), wintypes.UINT()
        ver.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(ln))
        ms, ls = ctypes.cast(p, ctypes.POINTER(wintypes.DWORD * 4)).contents[2:4]
        return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)
    except (OSError, AttributeError, ValueError, IndexError):   # no version API / odd DLL: "unknown" (the caller only warns)
        return None


# CPU tries, in order. The voice-activity filter (VAD) runs on onnxruntime; when that crashes, whisper still works without it.
WHISPER_TRIES = (("int8", None, True), ("int8", None, False), ("float32", 2, False))
GPU_TRY = ("float16", None, True)       # tried FIRST when a CUDA GPU with enough free memory is there; any failure -> WHISPER_TRIES


def whisper_safe(media, model="base.en", threads=None, ui=print):
    """whisper_transcribe in a CHILD process. On some Windows PCs the native engines crash the whole process
    (0xC0000005 = access violation; 2026-11-15: an old Microsoft C++ runtime, msvcp140.dll < 14.40, under the new
    onnxruntime / ctranslate2 builds - Setup.bat now installs the current runtime). A crash is reported with its exit code
    and retried without the onnxruntime voice filter, then with float32 / 2 threads; the run never dies silently.
    With a CUDA GPU (opt-in in Setup.bat, enough free memory) the first try is float16 on the GPU; a GPU problem of any kind
    costs one line and the CPU chain takes over, so the GPU can never fail a transcript the CPU could make."""
    import os
    import sys
    import tempfile
    import time
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); from ucf import transcript as T; "
            "s = T.whisper_transcribe(sys.argv[2], sys.argv[3], threads=int(sys.argv[4]) or None, compute_type=sys.argv[5], "
            "vad=sys.argv[7] == '1', device=sys.argv[8]); json.dump(s, open(sys.argv[6], 'w', encoding='utf-8'))")
    env = dict(os.environ, HF_HUB_DISABLE_SYMLINKS_WARNING="1", KMP_DUPLICATE_LIB_OK="TRUE")
    device, why_cpu = choose_device()
    LAST.update(device=None, x_realtime=None, why=why_cpu)
    tries = [("cuda",) + GPU_TRY] if device == "cuda" else []
    tries += [("cpu",) + t for t in WHISPER_TRIES]
    audio_s = _media_seconds(media) if os.path.exists(str(media)) else None
    last, crashed = "", False
    for n, (dev, ctype, th, vad) in enumerate(tries):
        th = (threads or 0) if th is None else th
        with tempfile.TemporaryDirectory(prefix="whisper_") as t:
            out = os.path.join(t, "segs.json")
            t0 = time.time()
            r = subprocess.run([sys.executable, "-c", code, str(ROOT), str(media), model, str(th), ctype, out, "1" if vad else "0", dev],
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env)
            if r.returncode == 0 and os.path.exists(out):
                with open(out, encoding="utf-8") as f:
                    segs = json.load(f)
                x = round(audio_s / max(time.time() - t0, 0.01), 1) if audio_s else None
                LAST.update(device=dev, x_realtime=x)
                if dev == "cpu" and n > (1 if device == "cuda" else 0):
                    ui(f"  whisper OK with the safer settings ({ctype}{'' if vad else ', no voice filter'})")
                ui(f"transcript: whisper on the {'GPU' if dev == 'cuda' else 'CPU'}" + (f" ({x}x realtime)" if x else "")
                   + ("" if dev == "cuda" or device == "cuda" else f"  [{why_cpu}]"))
                return segs
            code_hex = f"0x{r.returncode & 0xFFFFFFFF:08X}"
            tail = "\n".join((r.stderr or "").strip().splitlines()[-6:])
            why = (tail.splitlines() or [""])[-1][:160]
            if dev == "cuda":                    # not a CPU crash: say it once, go on with the CPU chain
                LAST["why"] = why or f"exit code {r.returncode} ({code_hex})"
                ui(f"  whisper on the GPU did not work ({LAST['why']}) - using the CPU")
                continue
            crashed = crashed or code_hex == "0xC0000005"
            last = f"exit code {r.returncode} ({code_hex})" + (f":\n{tail}" if tail else "")
            more = n + 1 < len(tries)
            ui(f"  whisper failed ({ctype}{'' if vad else ', no voice filter'}): exit code {r.returncode} ({code_hex}) {why}"
               + (" - trying again with safer settings..." if more else ""))
    hint = ""
    if crashed:
        v = msvc_runtime_version()
        hint = ("\n  0xC0000005 = the Microsoft C++ runtime on this PC is " +
                ("missing" if v is None else "version " + ".".join(map(str, v))) +
                " (whisper needs 14.40 or newer). Run Setup.bat again - it installs the current one (click Yes when Windows asks).")
    raise RuntimeError("whisper (transcript) does not run on this PC - " + last + hint +
                       "\n  Or give a transcript with --transcript-file. The download is kept: the next run starts at the transcript.")


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
