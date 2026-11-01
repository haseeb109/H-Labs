"""Keep the PC usable while H Labs works: lower process priority + a CPU thread cap.

* priority: the run (and every ffmpeg / whisper it starts - child processes inherit it) runs at "below normal", so Windows gives
  the mouse, browser and other apps the CPU first. The work is just as fast when the PC is otherwise idle.
* threads: libx264 (CPU encoder - used when no GPU encoder works), ffmpeg filters and whisper use `cpu_threads` threads instead
  of every core: 75% of the logical cores by default (12-thread i7 -> 9), so the CPU no longer sits at 100%.
config: "process_priority": "below_normal" | "normal" | "idle"     "cpu_threads": 0 (= auto, 75%) | a number | "all"
The GPU takes the encode whenever NVENC / VideoToolbox works (see the setup check): then the CPU only decodes and filters."""
import os


def cpu_threads(cfg):
    n = os.cpu_count() or 4
    v = (cfg or {}).get("cpu_threads", 0)
    if str(v).lower() == "all":
        return n
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = 0
    return max(1, min(n, v)) if v > 0 else max(2, int(n * 0.75))


def lower_priority(cfg):
    """Lower this process's priority (inherited by the ffmpeg / whisper children). -> label, or '' when unchanged."""
    want = str((cfg or {}).get("process_priority", "below_normal")).lower()
    if want == "normal":
        return ""
    try:
        if os.name == "nt":
            import ctypes
            cls = {"idle": 0x40, "below_normal": 0x4000}.get(want, 0x4000)
            k32 = ctypes.windll.kernel32
            if k32.SetPriorityClass(k32.GetCurrentProcess(), cls):
                return want
            return ""
        os.nice(19 if want == "idle" else 10)
        return want
    except Exception:
        return ""
