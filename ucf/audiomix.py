"""Music bed + SFX layer with ducking (shared by the documentary-type editing styles).

Rules (from the reverse-engineered documentary engine):
  * music sits under narration / B-roll / graphics, and DUCKS hard (default -22 dB, or to silence) the moment court
    audio starts; it comes back on the narrator's first word
  * SFX only on narrated / graphic beats - an SFX cue that falls inside a court window is dropped, never mixed over court
  * every file comes from the owner's library:  <library>/music/<mood>/*  and  <library>/sfx/<kind>/*
    (folder name = mood / kind; any audio format ffmpeg reads)

Use:
    plan = MixPlan(duration=312.0, court=[(20.0, 140.0)],
                   music=[MusicCue(0, 20, "drone_tense"), MusicCue(140, 312, "investigative_bed")],
                   sfx=[SfxCue(19.2, "stamp_thud"), SfxCue(141.0, "whoosh")])
    mix_onto(video_in, video_out, plan, library="D:/HLabsLibrary")   # video stream copied, audio re-mixed once
"""
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}

MUSIC_MOODS = ("drone_tense", "investigative_bed", "intro_theme", "ominous_bass", "ending_swell", "emotional_piano",
               "upbeat_light", "suspense_pulse")
SFX_KINDS = ("stamp_thud", "whoosh", "riser", "paper_rustle", "pop_click", "ui_click", "typewriter", "bass_drop",
             "brass_hit", "clock_tick", "camera_shutter", "glitch", "heartbeat", "buzzer_wrong", "ding_right",
             "freeze_hit", "tape_rewind", "boom")

DEFAULTS = {"music_db": -18.0,       # music level under narration (relative to full scale of the file)
            "duck_db": -22.0,        # extra drop inside court windows; <= -60 means silence
            "duck_ramp": 0.35,       # seconds to fade into / out of a duck
            "sfx_db": -6.0,
            "music_fade": 1.2}


@dataclass
class MusicCue:
    start: float
    end: float
    mood: str
    db: float = None          # None = DEFAULTS["music_db"]


@dataclass
class SfxCue:
    t: float
    kind: str
    db: float = None


@dataclass
class MixPlan:
    duration: float
    court: list = field(default_factory=list)      # [(start, end)] seconds where raw court audio plays
    music: list = field(default_factory=list)
    sfx: list = field(default_factory=list)


def library_files(library, sub, name):
    d = Path(library) / sub / name
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT and p.stat().st_size > 0)


def pick(library, sub, name, seed=0):
    files = library_files(library, sub, name)
    if not files:
        return None
    return random.Random(f"{name}:{seed}").choice(files)


def in_court(t, court, pad=0.15):
    return any(a - pad <= t <= b + pad for a, b in court)


def duck_expr(court, duck_db, ramp):
    """ffmpeg volume expression (t = output time): 1.0 outside court windows, duck gain inside, linear ramps."""
    if not court:
        return "1"
    g = 0.0 if duck_db <= -60 else 10 ** (duck_db / 20.0)
    parts = []
    for a, b in sorted(court):
        # depth 0..1 of the duck at time t for this window (trapezoid)
        parts.append(f"clip(min((t-{a - ramp:.3f})/{ramp:.3f},({b + ramp:.3f}-t)/{ramp:.3f}),0,1)")
    depth = parts[0] if len(parts) == 1 else "max(" + ",".join(parts[:2]) + ")"
    for p in parts[2:]:
        depth = f"max({depth},{p})"
    return f"1-({1 - g:.5f})*{depth}"


def build(plan, library, cfg=None, first_input=1, seed=0):
    """-> (extra_inputs: list[list[str]], filter_lines: list[str], out_label or None, report: list[str]).
    Inputs are numbered from `first_input` (input 0 = the video / voice track). The output label is the mixed
    music+sfx bus, to be amixed with the main audio by the caller (see mix_onto)."""
    c = dict(DEFAULTS, **(cfg or {}))
    inputs, lines, buses, report = [], [], [], []
    idx = first_input
    duck = duck_expr(plan.court, float(c["duck_db"]), float(c["duck_ramp"]))
    for k, m in enumerate(plan.music):
        if m.end - m.start < 0.5:
            continue
        f = pick(library, "music", m.mood, seed + k)
        if not f:
            report.append(f"music '{m.mood}' missing: put files in {Path(library) / 'music' / m.mood} (cue skipped)")
            continue
        dur = m.end - m.start
        fade = min(float(c["music_fade"]), dur / 3)
        db = c["music_db"] if m.db is None else m.db
        inputs.append(["-stream_loop", "-1", "-i", str(f)])
        lab = f"mu{k}"
        lines.append(f"[{idx}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
                     f"afade=t=in:d={fade:.2f},afade=t=out:st={dur - fade:.3f}:d={fade:.2f},volume={db}dB,"
                     f"adelay={int(m.start * 1000)}:all=1[{lab}]")
        buses.append(lab)
        idx += 1
    for k, s in enumerate(plan.sfx):
        if in_court(s.t, plan.court):
            report.append(f"sfx '{s.kind}' at {s.t:.1f}s dropped: inside court audio")
            continue
        f = pick(library, "sfx", s.kind, seed + k)
        if not f:
            report.append(f"sfx '{s.kind}' missing: put files in {Path(library) / 'sfx' / s.kind} (cue skipped)")
            continue
        db = c["sfx_db"] if s.db is None else s.db
        inputs.append(["-i", str(f)])
        lab = f"fx{k}"
        lines.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={db}dB,"
                     f"adelay={int(s.t * 1000)}:all=1[{lab}]")
        buses.append(lab)
        idx += 1
    if not buses:
        return inputs, lines, None, report
    mus = [b for b in buses if b.startswith("mu")]
    fx = [b for b in buses if b.startswith("fx")]
    out = []
    if mus:
        lines.append("".join(f"[{b}]" for b in mus) + f"amix=inputs={len(mus)}:normalize=0:duration=longest,"
                     f"volume='{duck}':eval=frame[mbus]")
        out.append("mbus")
    out += fx
    lines.append("".join(f"[{b}]" for b in out) + f"amix=inputs={len(out)}:normalize=0:duration=longest,"
                 f"atrim=0:{plan.duration:.3f}[bed]")
    return inputs, lines, "bed", report


def mix_onto(video_in, video_out, plan, library, cfg=None, ui=print, seed=0):
    """Re-mix the audio of a finished/segment file with the music+SFX bed. Video is stream-copied (no re-encode).
    -> list of report lines (missing files, dropped cues). With nothing to add, the file is copied as it is."""
    inputs, lines, out, report = build(plan, library, cfg, seed=seed)
    for r in report:
        ui("  audio: " + r)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video_in)]
    for i in inputs:
        cmd += i
    if out is None:
        cmd += ["-map", "0", "-c", "copy", str(video_out)]
    else:
        fc = ";".join(lines + [f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[main]",
                               f"[main][{out}]amix=inputs=2:normalize=0:duration=first[aout]"])
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(video_out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"audio mix failed (ucf/audiomix.py mix_onto): {r.stderr.strip()[-300:]}")
    return report


def library_status(library):
    """-> {"music": {mood: n_files}, "sfx": {kind: n_files}} for the setup check / Studio."""
    return {"music": {m: len(library_files(library, "music", m)) for m in MUSIC_MOODS},
            "sfx": {k: len(library_files(library, "sfx", k)) for k in SFX_KINDS}}
