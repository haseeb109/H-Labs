"""One builder for the run_stream.py command line.

The launcher menu (1, 2, bulk queue) and H Labs Studio start the very same pipeline, but each used to build the argument list
by hand - and the two lists drifted apart once already (--min-case, --confirm-tts, --keep-source, --no-watermark, --queued,
--only, --local). Both now call build_run_command, so a new switch is added in ONE place (owner priority #13, 2026-11-16).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def is_link(u):
    """True for a YouTube (web) link, False for your own file / folder on this PC (a Windows path like C:\\videos\\x.mp4)."""
    return str(u).strip().lower().startswith(("http://", "https://"))


def build_run_command(python, url_or_path, style, mode, options=None, script=None):
    """-> the full command list for one run.

    options (the keys H Labs Studio already stores per job; all optional):
      brain "hive"/"manual"   --brain (left out when empty)
      min_case 5 / 8          --min-case, only in mode all / clips
      voice True              --confirm-tts (the owner's yes to > 5,000 TTS characters); clips make no voice, so never there
      watermark True          False -> --no-watermark
      cleanup True            False -> --keep-source (keeps the downloaded stream)
      queued False            True -> --queued (bulk queue / Studio: one report at the end, no pop-ups per stream)
      only [1, 3]             --only 1,3
      transcript_file "..."   --transcript-file (your own transcript for a local video)
    """
    o = dict(options or {})
    if mode == "download":                     # download only (tools/download_only.py): no style, brain or render options
        return ([str(python), str(ROOT / "tools" / "download_only.py"), str(url_or_path)] + (["--queued"] if o.get("queued") else [])
                + (["--max-height", str(int(o["max_height"]))] if str(o.get("max_height", "")).isdigit() else []))
    cmd = [str(python), str(script or (ROOT / "run_stream.py"))]
    cmd += [str(url_or_path)] if is_link(url_or_path) else ["--local", str(url_or_path)]
    if o.get("brain"):
        cmd += ["--brain", str(o["brain"])]
    cmd += ["--style", str(style), "--mode", str(mode)]
    if o.get("queued"):
        cmd.append("--queued")
    if mode in ("all", "clips") and str(o.get("min_case", "")) in ("5", "8"):
        cmd += ["--min-case", str(o["min_case"])]
    if o.get("transcript_file"):
        cmd += ["--transcript-file", str(o["transcript_file"])]
    if o.get("voice", True) and mode != "clips":
        cmd.append("--confirm-tts")
    if not o.get("watermark", True):
        cmd.append("--no-watermark")
    if not o.get("cleanup", True):
        cmd.append("--keep-source")
    if o.get("only"):
        cmd += ["--only", ",".join(str(n) for n in o["only"])]
    return cmd
