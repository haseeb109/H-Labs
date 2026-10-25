"""Voiceover synthesis with fallbacks. Output: 48 kHz stereo WAV. Cached by text hash.
Hard rule (UMF): more than `tts_confirm_chars` characters in one run needs an explicit yes first."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import vo as V


def _to_wav(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "48000", "-ac", "2", str(dst)], check=True)


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def _ai33(text, out_wav, cfg, tmp):
    script = Path(os.path.expanduser(cfg["ai33_script"]))
    if not script.is_absolute():
        script = Path(__file__).resolve().parent.parent / script
    if not script.exists():
        raise RuntimeError(f"ai33_tts.py not found at {script}")
    txt = tmp / "vo.txt"
    txt.write_text(text, encoding="utf-8")
    mp3 = tmp / "vo.mp3"
    subprocess.run([sys.executable, str(script), "tts", "--voice", cfg["ai33_voice"], "--text-file", str(txt),
                    "--out", str(mp3)], check=True, timeout=300)
    _to_wav(mp3, out_wav)


def _voicestudio(text, out_wav, cfg, tmp):
    body = json.dumps({"model": "tts-1", "input": text, "voice": cfg["voicestudio_voice"],
                       "response_format": "mp3"}).encode()
    req = urllib.request.Request(cfg["voicestudio_url"], data=body, headers={"Content-Type": "application/json"})
    mp3 = tmp / "vo.mp3"
    with urllib.request.urlopen(req, timeout=300) as r:
        mp3.write_bytes(r.read())
    _to_wav(mp3, out_wav)


def _say(text, out_wav, cfg, tmp):
    if not shutil.which("say"):
        raise RuntimeError("`say` not available (macOS only)")
    aiff = tmp / "vo.aiff"
    subprocess.run(["say", "-v", cfg["say_voice"], "-o", str(aiff), text], check=True)
    _to_wav(aiff, out_wav)


def _dummy(text, out_wav, cfg, tmp):
    """Test provider: a quiet tone as long as the line would take to read."""
    d = V.est_seconds(text)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=220:d={d:.2f}:r=48000",
                    "-af", "volume=0.05", "-ac", "2", str(out_wav)], check=True)


PROVIDERS = {"ai33": _ai33, "voicestudio": _voicestudio, "say": _say, "dummy": _dummy}


def synth(text, cache_dir, cfg):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    order = cfg.get("tts_order", ["ai33", "voicestudio", "say"])
    key = hashlib.sha1((order[0] + cfg.get("ai33_voice", "") + text).encode()).hexdigest()[:16]
    wav = cache_dir / f"{key}.wav"
    if wav.exists() and wav.stat().st_size > 1000:
        return wav
    tmp = cache_dir / f"tmp_{key}"
    tmp.mkdir(exist_ok=True)
    errs = []
    for name in order:
        try:
            PROVIDERS[name](text, wav, cfg, tmp)
            if wav.exists() and wav.stat().st_size > 1000:
                shutil.rmtree(tmp, ignore_errors=True)
                return wav
        except Exception as e:  # noqa
            errs.append(f"{name}: {e}")
    raise RuntimeError("all TTS providers failed -> " + " | ".join(errs))


def _atempo(src, dst, factor):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter:a", f"atempo={factor:.4f}",
                    "-ar", "48000", "-ac", "2", str(dst)], check=True)


def synth_clips(text, cache_dir, cfg, warn=print):
    """Synthesize `text` as one or more AI-voice clips, EVERY clip <= cfg['vo_clip_max'] seconds (default 18).
    Strategy: split at sentence boundaries first (~16.5 s each), then measure the real audio; a clip that is
    still too long is sped up slightly (<= 12 %) or split again. Returns list of WAV paths."""
    cmax = float(cfg.get("vo_clip_max", V.CLIP_MAX))
    out = []

    def fit(t, depth=0):
        wav = synth(t, cache_dir, cfg)
        d = dur(wav)
        if d <= cmax:
            out.append(wav)
            return
        sents = V.sentences(t)
        if len(sents) >= 2 and depth < 4:
            mid = V.split_clips(t, max_s=max(6.0, d / 2 + 1), wps=V.n_words(t) / max(d, 1) )
            if len(mid) < 2:
                half = len(sents) // 2
                mid = [" ".join(sents[:half]), " ".join(sents[half:])]
            for m in mid:
                fit(m, depth + 1)
            return
        factor = d / (cmax - 0.2)
        if factor > 1.25:
            warn(f"    ! one sentence reads {d:.1f}s - shorten the VO text (clip limit {cmax:.0f}s)")
        fast = wav.with_name(wav.stem + "_fit.wav")
        _atempo(wav, fast, min(factor, 1.25))
        out.append(fast)

    for part in V.split_clips(text, float(cfg.get("vo_clip_target", V.CLIP_TARGET)), float(cfg.get("wps", 2.6))):
        fit(part)
    return out


def chars_needed(plan, only=None, tt=False):
    n = 0
    for v in plan.get("videos", []):
        if only and v["n"] not in only:
            continue
        n += len(v["vo_final"]["text"]) + sum(len(b["text"]) for b in v.get("bridges", []))
        if not tt:
            n += len(v["vo1"]["text"])
    return n
