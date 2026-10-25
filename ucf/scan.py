"""Deterministic Rule-0 helpers: Pass-1 marker scan + Pass-2 gap candidates + dead-air.
The LLM still judges; this makes sure the phrases/timecodes it sees are real."""
import re

from .timeutil import fmt_tc, fmt_dur

MARKERS = [
    r"court is calling", r"state versus", r"state vs", r"the state calls",
    r"can i have parties announce", r"parties announce", r"parties announced",
    r"we'?re on the record on", r"cause number", r"you may be seated",
    r"come forward", r"next case", r"call the next", r"are the parties ready",
    r"counsel,? announce",
]
MARK_RE = re.compile("|".join(MARKERS), re.I)
# "are you [NAME]" - name must be capitalised, so case-sensitive part
ARE_YOU = re.compile(r"\b[Aa]re you (?:Mr\.|Mrs\.|Ms\.|Miss|Dr\.)?\s*[A-Z][a-z]{2,}")


def _stream_text(segs):
    """Concatenate segments with a char->segment index so phrases spanning lines still match."""
    parts, idx, pos = [], [], 0
    for i, s in enumerate(segs):
        t = s["text"] + " "
        parts.append(t)
        idx.append(pos)
        pos += len(t)
    return "".join(parts), idx


def _seg_at(idx, pos):
    lo, hi = 0, len(idx) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if idx[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo


def pass1(segs):
    text, idx = _stream_text(segs)
    hits = []
    for rx in (MARK_RE, ARE_YOU):
        for m in rx.finditer(text):
            si = _seg_at(idx, m.start())
            hits.append({"t": segs[si]["start"], "phrase": m.group(0).strip().lower() if rx is MARK_RE
                         else m.group(0).strip()})
    hits.sort(key=lambda h: h["t"])
    # drop literal duplicates at same second
    out = []
    for h in hits:
        if out and abs(out[-1]["t"] - h["t"]) < 1.0 and out[-1]["phrase"] == h["phrase"]:
            continue
        out.append(h)
    return out


def cluster(hits, window=25.0):
    """Hits within `window` s are one candidate case start."""
    cl = []
    for h in hits:
        if cl and h["t"] - cl[-1]["t_last"] <= window:
            cl[-1]["t_last"] = h["t"]
            cl[-1]["phrases"].append(h["phrase"])
        else:
            cl.append({"t": h["t"], "t_last": h["t"], "phrases": [h["phrase"]]})
    return cl


def dead_air(segs, min_gap=90.0, stream_len=None):
    out, prev = [], 0.0
    for s in segs:
        if s["start"] - prev >= min_gap:
            out.append((prev, s["start"]))
        prev = max(prev, s["end"])
    if stream_len and stream_len - prev >= min_gap:
        out.append((prev, stream_len))
    return out


def pass2(clusters, stream_len, segs, min_gap=180.0):
    """Gaps between consecutive candidate starts (and edges) longer than min_gap, with speech density."""
    pts = [0.0] + [c["t"] for c in clusters] + [stream_len]
    gaps = []
    for a, b in zip(pts, pts[1:]):
        if b - a > min_gap:
            words = sum(len(s["text"].split()) for s in segs if a <= s["start"] < b)
            wpm = words / max((b - a) / 60.0, 0.01)
            gaps.append({"in": a, "out": b, "dur": b - a, "words": words, "wpm": wpm})
    return gaps


def report(segs, stream_len):
    hits = pass1(segs)
    cl = cluster(hits)
    g2 = pass2(cl, stream_len, segs)
    da = dead_air(segs, stream_len=stream_len)
    return {"hits": hits, "clusters": cl, "gaps": g2, "dead_air": da}


def report_text(rep):
    L = []
    L.append(f"SCRIPT PASS 1 - {len(rep['hits'])} marker hits in {len(rep['clusters'])} clusters (exact transcript timecodes):")
    for c in rep["clusters"]:
        ph = "; ".join(sorted(set(c["phrases"])))[:90]
        L.append(f"  {fmt_tc(c['t'])}  {ph}")
    L.append("")
    L.append("SCRIPT PASS 2 CANDIDATES - spans longer than 3:00 between consecutive hits "
             "(wpm = spoken words per minute; very low wpm usually means recess/silence):")
    for g in rep["gaps"]:
        L.append(f"  {fmt_tc(g['in'])} - {fmt_tc(g['out'])}  ({fmt_dur(g['dur'])})  {g['wpm']:.0f} wpm")
    L.append("")
    L.append("DEAD AIR - stretches with NO transcript text at all (90 s or more):")
    if rep["dead_air"]:
        for a, b in rep["dead_air"]:
            L.append(f"  {fmt_tc(a)} - {fmt_tc(b)}  ({fmt_dur(b - a)})")
    else:
        L.append("  none")
    return "\n".join(L)
