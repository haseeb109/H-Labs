"""Dossier: several hearings of ONE defendant (different streams, months or years apart) in one documentary video.

    python tools/dossier.py --name "Summer Diaz" URL1 URL2 URL3 [--style case_file_doc]

1. every link is downloaded + transcribed by the normal pipeline (run_stream --stage transcript)
2. in each transcript the defendant's part is found by name (the biggest cluster of mentions; widened to the call-out
   before it and the wrap-up after it) and that part is cut into state/dossier/<name>/  (stream copy: no quality loss)
   with its own transcript slice and its date (the stream's upload date)
3. the NEWEST hearing runs through the full pipeline with --dossier <name>: the brain sees the earlier hearings
   (date + what was said) to write the backstory / bridges, and the documentary renderer puts the earlier hearings in
   front of it as dated chapters (HEARING 1 / MAY 15, 2023 ...), in time order.

A hearing where the name is not found is skipped with a reason (wrong link / different spelling: use --alias).
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_PART = 15 * 60          # one earlier hearing is cut to at most 15 minutes
CLUSTER_GAP = 240           # mentions further apart than this are different parts of the stream


def key_of(name):
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_") or "defendant"


def folder(name, state_dir=None):
    return Path(state_dir or ROOT / "state") / "dossier" / key_of(name)


def _patterns(name, aliases=()):
    words = [w for w in re.findall(r"[a-z']+", (name or "").lower()) if len(w) > 2]
    pats = set()
    if words:
        pats.add(words[-1])                       # last name: what the court says most ("Ms. Diaz")
        pats.add(" ".join(words))
    for a in aliases:
        a = a.strip().lower()
        if a:
            pats.add(a)
    return [re.compile(r"\b" + re.escape(p) + r"\b") for p in pats]


def find_window(segs, name, aliases=(), pad_before=20.0, pad_after=75.0):
    """-> (start, end, mentions) of the defendant's part of a transcript, or None. The biggest cluster of mentions wins."""
    pats = _patterns(name, aliases)
    hits = [float(s["start"]) for s in segs if any(p.search(s.get("text", "").lower()) for p in pats)]
    if not hits:
        return None
    clusters, cur = [], [hits[0]]
    for t in hits[1:]:
        if t - cur[-1] > CLUSTER_GAP:
            clusters.append(cur)
            cur = []
        cur.append(t)
    clusters.append(cur)
    best = max(clusters, key=lambda c: (len(c), c[-1] - c[0]))
    a = max(0.0, best[0] - pad_before)
    b = best[-1] + pad_after
    # end at the next case being called, when that comes before the padded end
    for s in segs:
        t = float(s["start"])
        if best[-1] + 10 < t < b and re.search(r"\b(calling|call(ing)? the case of|next case|cause number)\b", s.get("text", "").lower()):
            b = t - 2
            break
    end_of_stream = max((float(s.get("end", s["start"])) for s in segs), default=b)
    b = min(b, end_of_stream, a + MAX_PART)
    return (a, b, len(best)) if b - a >= 20 else None


def nice_date(upload):
    """'20230515' -> 'MAY 15, 2023' ('' stays '')."""
    import datetime
    try:
        return datetime.datetime.strptime(str(upload)[:8], "%Y%m%d").strftime("%b %d, %Y").upper()
    except ValueError:
        return ""


def cut(src, a, b, out):
    """Stream-copy cut (no re-encode: same quality as the download). Starts on the keyframe before a."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-i", str(src), "-t", f"{b - a:.2f}",
                        "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-avoid_negative_ts", "make_zero", str(out)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"cutting the hearing failed (ucf/dossier.py cut): {r.stderr.strip()[-200:]}")
    return out


def add_hearing(name, src, segs, upload, url="", title="", aliases=(), state_dir=None):
    """Find + cut the defendant's part of one stream into the dossier. -> hearing dict, or raises ValueError(why)."""
    w = find_window(segs, name, aliases)
    if not w:
        raise ValueError(f"'{name}' is not named in this stream's transcript ({title or url}) - wrong link, or add --alias")
    a, b, n = w
    d = folder(name, state_dir)
    tag = re.sub(r"[^0-9A-Za-z]+", "", str(upload) or "x")[:8] or "x"
    vid = re.sub(r"[^0-9A-Za-z_-]+", "", Path(src).stem)[:20]
    clip = cut(src, a, b, d / f"h_{tag}_{vid}.mp4")
    local = [dict(s, start=float(s["start"]) - a, end=float(s.get("end", s["start"])) - a) for s in segs
             if a <= float(s["start"]) < b]
    h = {"date": nice_date(upload), "upload": str(upload), "url": url, "title": title, "file": clip.name,
         "src_in": round(a, 2), "src_out": round(b, 2), "mentions": n, "segs": local}
    man = load(name, state_dir)
    man["hearings"] = [x for x in man["hearings"] if x["file"] != h["file"]] + [h]
    man["hearings"].sort(key=lambda x: x.get("upload", ""))
    save(name, man, state_dir)
    return h


def load(name, state_dir=None):
    p = folder(name, state_dir) / "manifest.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"name": name, "hearings": []}


def save(name, man, state_dir=None):
    d = folder(name, state_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")


def earlier(name, before_upload, state_dir=None):
    """Hearings older than the one being made now, oldest first, with absolute clip paths."""
    man = load(name, state_dir)
    d = folder(name, state_dir)
    out = []
    for h in man["hearings"]:
        if before_upload and h.get("upload", "") >= str(before_upload):
            continue
        p = d / h["file"]
        if p.exists():
            out.append(dict(h, path=str(p)))
    return out


def prompt_block(hearings, max_chars=1800):
    """Text for the brain (Pass B): what happened at each earlier hearing, so backstory / bridges can tell the arc."""
    if not hearings:
        return ""
    parts = ["\n" + "═" * 64, " EARLIER HEARINGS OF THIS DEFENDANT (oldest first) - the video shows them BEFORE this one",
             "═" * 64,
             "Use them for the backstory and the bridges (what changed between hearings, how long it took). Facts from these "
             "hearings may go into case_doc only with evidence quoted from THIS text. Do not put their timecodes in any field."]
    for i, h in enumerate(hearings, 1):
        txt = " ".join(s.get("text", "") for s in h.get("segs", []))
        parts.append(f"\nHEARING {i} - {h.get('date') or 'date unknown'} ({h.get('title', '')[:80]}):\n{txt[:max_chars]}")
    return "\n".join(parts) + "\n"
