"""Your own downloaded video (+ its transcript, when you have one) instead of a YouTube download.

resolve(path) takes a video file OR a folder:
  * folder -> the biggest video file inside (mp4 / mkv / webm / mov / m4v / ts) and, when present, a transcript next to it
    (json / json3 / vtt / srt; one named like the video wins). No transcript -> the run makes one with whisper.
  * file   -> that video, plus a transcript beside it with the same name (video.mp4 + video.en.vtt / video.json ...).
stream_id(path) -> a safe work-folder id: the YouTube id when the name carries one ("Title [abc123XYZ_-].mp4", yt-dlp style),
else the file name made safe (letters, digits, - and _).
The file itself is never moved, changed or deleted (cleanup only touches work/<id>/source.*)."""
import re
from pathlib import Path

VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".ts")
TRANSCRIPT_EXT = (".json", ".json3", ".vtt", ".srt")
# files the tool writes itself next to a video: never a transcript
_NOT_TRANSCRIPT = re.compile(r"^(meta|plan.*|video_plan|qc|upload_status|sources|scan|evidence.*|brain_reply.*|segs)\.json$", re.I)


def _transcripts(folder):
    return [p for p in Path(folder).iterdir()
            if p.is_file() and p.suffix.lower() in TRANSCRIPT_EXT and not _NOT_TRANSCRIPT.match(p.name)]


def _match(video, cands):
    """The transcript that belongs to this video: same name first (video.en.vtt, video.json), else the only one."""
    stem = video.stem.lower()
    same = [c for c in cands if c.name.lower().startswith(stem + ".") or c.stem.lower() == stem]
    if same:
        return sorted(same, key=lambda c: (c.suffix.lower() not in (".json3", ".vtt", ".srt"), len(c.name)))[0]
    return cands[0] if len(cands) == 1 else None


def resolve(path):
    """-> (video Path, transcript Path or None). Raises ValueError with a plain message when nothing usable is there."""
    p = Path(str(path).strip().strip('"').strip("'")).expanduser()
    if not p.exists():
        raise ValueError(f"not found: {p}")
    if p.is_dir():
        vids = [x for x in p.iterdir() if x.is_file() and x.suffix.lower() in VIDEO_EXT and not x.name.endswith(".part")]
        if not vids:
            raise ValueError(f"no video file (.mp4 / .mkv / .webm / .mov) in {p}")
        video = max(vids, key=lambda x: x.stat().st_size)
        return video, _match(video, _transcripts(p))
    if p.suffix.lower() not in VIDEO_EXT:
        raise ValueError(f"{p.name} is not a video file ({' / '.join(VIDEO_EXT)})")
    same = [c for c in _transcripts(p.parent) if c.name.lower().startswith(p.stem.lower() + ".") or c.stem.lower() == p.stem.lower()]
    return p, (_match(p, same) if same else None)


def stream_id(video):
    name = Path(video).stem
    m = re.search(r"\[([A-Za-z0-9_-]{11})\]", name) or re.fullmatch(r"([A-Za-z0-9_-]{11})", name)
    if m:
        return m.group(1)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:40]
    return "local_" + (safe or "video")
