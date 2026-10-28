"""Per-stream signal extraction for the boundary engine -> work/<id>/evidence.json.
Transcript-level signals are computed once here (cheap). Video-level signals (tile counts, label sets)
are computed lazily, inside windows only, by ucf/boundary.py (speed rule, spec 7.2)."""
import json
import re
from pathlib import Path

from . import zoom

WRAP_UP = [r"you'?re free to go", r"that'?ll be all", r"good luck", r"anything further", r"we'?re adjourned",
           r"you'?re excused", r"sign the paperwork", r"right to appeal", r"taken into custody", r"see you on",
           r"thank you,? counsel"]
RULING = [r"I sentence you", r"sentenced? to", r"I find you guilty", r"finds you guilty", r"probation is revoked",
          r"I'?m going to give you", r"the court finds", r"\bdismissed\b", r"reset to", r"we'?ll see you on",
          r"find you", r"sentence you to", r"probation is (?:granted|continued|reinstated)", r"adjudication is withheld",
          r"imposition of sentence", r"court will find you", r"grants? you deferred"]


def _find(segs, patterns):
    out = []
    for s in segs:
        low = s["text"].lower()
        for p in patterns:
            m = re.search(p, low, re.I)
            if m:
                out.append({"tc": round(s["start"], 1), "end": round(max(s["end"], s["start"]), 1),
                            "phrase": m.group(0).lower()})
                break
    return sorted(out, key=lambda x: x["tc"])


def _silence(segs, min_gap=8.0):
    out, prev = [], None
    for s in segs:
        if prev is not None and s["start"] - prev >= min_gap:
            out.append({"tc": round(prev, 1), "gap": round(s["start"] - prev, 1)})
        prev = max(prev or 0, s["end"])
    return out


def build(video_path, segs, scan_rep, cfg, work):
    call_outs = []
    for c in scan_rep.get("clusters", []):
        call_outs.append({"tc": round(c["t"], 1), "phrase": "; ".join(sorted(set(c["phrases"])))[:60]})
    ev = {
        "call_outs": call_outs,
        "wrap_up": _find(segs, WRAP_UP),
        "ruling": _find(segs, RULING),
        "silence": _silence(segs),
        "video_available": bool(video_path and Path(video_path).exists()),
        "ocr_engine": None,
        "tile_events": [],           # filled lazily by boundary.refine_case (windowed)
        "label_events": [],
        "windows_done": [],
    }
    if cfg.get("boundary", {}).get("ocr"):
        from . import tile_ocr
        ev["ocr_engine"] = tile_ocr.pick_engine(cfg["boundary"].get("ocr", "auto"))
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    out = work / "evidence.json"
    out.write_text(json.dumps(ev, indent=1), encoding="utf-8")
    ev["path"] = out
    return ev
