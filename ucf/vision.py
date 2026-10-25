"""Optional Claude-vision tie-break for low-confidence case boundaries (spec 7.6).
Off by default (boundary.vision_check). Sends an 8-frame strip; returns the tc where the defendant's
tile last appears. Uses the Anthropic key file; skipped with a warning when unavailable."""
import base64
import subprocess
import tempfile
from pathlib import Path


def _frames(video_path, best, n=8, span=16):
    td = tempfile.mkdtemp(prefix="hlabs_vision_")
    out = []
    for k in range(n):
        t = best - span + (2 * span) * k / (n - 1)
        p = Path(td) / f"f{k:02d}.jpg"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, t):.2f}", "-i", str(video_path),
                            "-frames:v", "1", "-vf", "scale=640:-1", "-q:v", "5", str(p)], capture_output=True)
        if r.returncode == 0 and p.exists():
            out.append((t, p))
    return out


def tie_break(video_path, best, case, cfg):
    """-> (tc, reason) or (None, reason). Conservative: any failure returns None."""
    from . import brain as B
    key = __import__("os").environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, "no anthropic key for vision"
    frames = _frames(video_path, best)
    if len(frames) < 4:
        return None, "could not build frame strip"
    content = [{"type": "text",
                "text": (f"These frames are from a Zoom court hearing, times labelled. The case of "
                         f"{case.get('name', 'the defendant')} ends somewhere here. Return JSON "
                         '{"last_frame_with_same_defendant": "<tc>", "next_person_appears": "<tc|null>", '
                         '"reason": "<=20 words"}. Frame times: '
                         + ", ".join(f"f{k}={t:.0f}s" for k, (t, _p) in enumerate(frames)))}]
    for _t, p in frames:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.b64encode(p.read_bytes()).decode()}})
    import json as _json
    import urllib.request
    body = _json.dumps({"model": (cfg.get("boundary") or {}).get("vision_model", "claude-sonnet-5-5"),
                        "max_tokens": 300,
                        "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            reply = _json.loads(r.read())["content"][0]["text"]
        from .brain import extract_json
        ans = extract_json(reply)
        tc = float(str(ans.get("last_frame_with_same_defendant", "0")).replace(":", "").lstrip("0") or 0) \
            if ":" not in str(ans.get("last_frame_with_same_defendant", "")) else None
        if tc is None:
            parts = [float(x) for x in str(ans["last_frame_with_same_defendant"]).split(":")]
            tc = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
        return tc, ans.get("reason", "")[:60]
    except Exception as e:
        return None, f"vision failed: {e}"
