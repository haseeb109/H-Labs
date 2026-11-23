"""UMF Case Factory - livestream URL -> N re-edited case videos."""
from pathlib import Path as _P

def _read_version():
    """VERSION file at the repo root (date-based, e.g. 2026.11.15); bumped with every release so every laptop can say which
    build it runs (launcher banner, Studio, run log, run report)."""
    try:
        return (_P(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


__version__ = _read_version()


def _no_console_input():
    """ffmpeg / ffprobe / yt-dlp never read the console (2026-11-23). They inherited the console's input: a key pressed while
    the setup or a run was working (Enter, 'c', '?') put ffmpeg into its interactive "Enter command:" mode, where it waits for
    input forever - the smoke test's whisper and download checks then timed out. Every tool started by H Labs now gets an empty
    input instead (same as `-nostdin`), unless the caller passes stdin= itself. Python children (run_stream, whisper) keep the
    console, so nothing that asks a question is affected."""
    import os
    import subprocess

    if getattr(subprocess.Popen, "_hl_nostdin", False):
        return
    tools = {"ffmpeg", "ffprobe", "ffplay", "yt-dlp", "yt_dlp", "git", "node", "npx", "nvidia-smi"}
    orig = subprocess.Popen.__init__

    def init(self, args, *a, **kw):
        if "stdin" not in kw and len(a) < 3:
            try:
                argv = [args] if isinstance(args, (str, bytes, os.PathLike)) else list(args)
                first = os.path.basename(str(argv[0]).split()[0] if isinstance(args, str) else str(argv[0])).lower()
                stem = first.rsplit(".", 1)[0] if first.endswith(".exe") else first
                if stem in tools or ("-m" in argv and "yt_dlp" in argv):
                    kw["stdin"] = subprocess.DEVNULL
            except (IndexError, TypeError):
                pass
        orig(self, args, *a, **kw)

    subprocess.Popen.__init__ = init
    subprocess.Popen._hl_nostdin = True


_no_console_input()
