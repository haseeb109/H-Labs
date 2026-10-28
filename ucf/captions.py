"""Word-by-word captions: mlx-whisper (Apple-silicon Whisper) word timestamps on the finished video -> an ASS
subtitle file with the spoken word highlighted -> burned in with libass.

Placement (tt look): the band under the 1920x540 footage strip (y 840-1040). No captions during the hook and the
gavel intro (the hook has its own headline) or while an overlay card is on screen (same band).

Needs: `pip install mlx-whisper` (Apple silicon) and an ffmpeg built with libass (`brew install ffmpeg-full`).
Anything missing -> captions are skipped with a message, the video still renders.
"""
import hashlib
import sys
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

GOLD = "&H0032B4F0&"      # ASS colours are &HBBGGRR - this is #F0B432, the Trial Tales gold
WHITE = "&H00FFFFFF&"
FFMPEG_LIBASS_CANDIDATES = ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg")


def libass_ffmpeg(cfg=None):
    """Path of an ffmpeg that has the `subtitles` (libass) filter, or None."""
    want = (cfg or {}).get("ffmpeg_libass")
    for c in ([want] if want else []) + list(FFMPEG_LIBASS_CANDIDATES) + [shutil.which("ffmpeg")]:
        if not c or not os.path.exists(c):
            continue
        r = subprocess.run([c, "-hide_banner", "-filters"], capture_output=True, text=True)
        if re.search(r"\bsubtitles\b", r.stdout):
            return c
    return None


def transcribe_words(media, cfg, cache=None):
    """-> [(start, end, word)] for the whole file. Cached in `cache` (json) - transcription is the slow part."""
    if cache and Path(cache).exists():
        return [tuple(w) for w in json.loads(Path(cache).read_text(encoding="utf-8"))]
    import mlx_whisper
    res = mlx_whisper.transcribe(str(media), path_or_hf_repo=cfg.get("caption_model", "mlx-community/whisper-large-v3-turbo"),
                                 word_timestamps=True, condition_on_previous_text=False, language="en",
                                 no_speech_threshold=0.5, verbose=None)
    words = []
    for seg in res.get("segments", []):
        if seg.get("no_speech_prob", 0) > 0.8:          # whisper invents text in silence - drop those segments
            continue
        for w in seg.get("words", []):
            t = (w.get("word") or "").strip()
            if t and w.get("end", 0) > w.get("start", 0):
                words.append((round(float(w["start"]), 3), round(float(w["end"]), 3), t))
    if cache:
        Path(cache).write_text(json.dumps(words), encoding="utf-8")
    return words


def chunk_words(words, max_words=4, max_gap=0.6, max_dur=2.6):
    """Group words into short on-screen lines: break on a pause, end of sentence, length or duration."""
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w[0] - cur[-1][1] > max_gap or w[1] - cur[0][0] > max_dur
                    or re.search(r"[.?!]$", cur[-1][2])):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def _ts(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def _blocked(a, b, blocks):
    return any(a < y and b > x for x, y in blocks)


def build_ass(words, blocks, out, cfg=None):
    """Write the ASS file. One event per spoken word: the whole chunk on screen, that word in gold.
    `blocks` = [(start, end)] where no caption may show. -> number of events written."""
    cfg = cfg or {}
    size = int(cfg.get("caption_font_size", 66))
    margin_v = int(cfg.get("caption_margin_v", 70))       # from the bottom: text sits in the y 900-1010 band
    font = cfg.get("caption_font", "Arial")
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n"
            "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,{font},{size},{WHITE},{WHITE},&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,5,1,2,"
            f"120,120,{margin_v},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
            "Effect, Text\n")
    lines = []
    chunks = chunk_words(words, int(cfg.get("caption_max_words", 4)))
    prev_end = 0.0
    for k, ch in enumerate(chunks):
        # a line never outlives the start of the next one, and never starts before the previous one ended
        # (whisper's word times sometimes overlap - two lines would stack on screen)
        limit = chunks[k + 1][0][0] if k + 1 < len(chunks) else float("inf")
        for i, (s, e, _w) in enumerate(ch):
            nxt = ch[i + 1][0] if i + 1 < len(ch) else max(e, ch[0][0] + 0.7)
            a = max(s, prev_end)
            b = min(max(nxt, a + 0.08), limit)
            if b - a < 0.04:
                continue
            prev_end = b
            if _blocked(a, b, blocks):
                continue
            txt = " ".join((f"{{\\c{GOLD}}}{_esc(x[2]).upper()}{{\\c{WHITE}}}" if j == i else _esc(x[2]).upper())
                           for j, x in enumerate(ch))
            lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{txt}")
    Path(out).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def default_font_dir():
    """Where the OS keeps its fonts (libass needs a font folder for the caption text)."""
    if sys.platform == "darwin":
        return "/System/Library/Fonts/Supplemental"
    if os.name == "nt":
        return "C:/Windows/Fonts"
    return "/usr/share/fonts"


def _flt_path(p):
    """ffmpeg filter-option escaping: forward slashes, and the drive colon of a Windows path escaped (C\\:/dir/file)."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def subtitles_filter(ass, font_dir=None):
    return f"subtitles=filename='{_flt_path(ass)}':fontsdir='{_flt_path(font_dir or default_font_dir())}'"


def burn(final, blocks, work, cfg, venc_args, ui=print):
    """Transcribe `final`, build captions and burn them in (video re-encoded, audio copied). Returns the path of
    the captioned video (same name), or `final` untouched when captions are off or a tool is missing."""
    if not cfg.get("burn_captions", False):      # off by default (owner, 2026-10-25); "captions" is the transcript source
        return final
    ff = libass_ffmpeg(cfg)
    if not ff:
        ui("  captions skipped: no ffmpeg with libass (brew install ffmpeg-full)")
        return final
    try:
        import mlx_whisper  # noqa: F401
    except Exception:
        ui("  captions skipped: mlx-whisper not installed (.venv/bin/pip install mlx-whisper)")
        return final
    work = Path(work)
    key = hashlib.md5(((work / "concat.txt").read_text(encoding="utf-8") if (work / "concat.txt").exists()
                       else str(final)).encode()).hexdigest()[:10]
    cache = work / f"caption_words_{key}.json"
    ui("  captions: word timings from cache" if cache.exists() else "  captions: transcribing words (mlx-whisper)...")
    words = transcribe_words(final, cfg, cache=cache)
    ass = work / "captions.ass"
    n = build_ass(words, blocks, ass, cfg)
    if not n:
        ui("  captions skipped: no words")
        return final
    out = Path(final).with_name(Path(final).stem + "_cap.mp4")
    vf = subtitles_filter(ass, cfg.get("caption_font_dir"))
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(final), "-vf", vf, *venc_args, "-c:a", "copy",
                    "-movflags", "+faststart", str(out)], check=True)
    if out.exists() and out.stat().st_size > 1000:
        Path(final).unlink(missing_ok=True)
        out.rename(final)
        ui(f"  captions burned: {n} word events")
    return final
