"""Builds the output timeline of one video (estimated or from real VO durations).
Used by the validator (estimates), the sheet writer, and the renderer (real numbers)."""
from . import vo as V
from .timeutil import parse_tc

DEFAULTS = {"cut_pad_out": 0.5, "final_min_hold": 20.0, "final_max_hold": 30.0, "style": "",
            "vo_lead": 0.35, "vo_tail": 0.6, "wps": 2.6}


def removes(case):
    """Removed spans of a case, sorted: supports `remove` (one span) and `removes` (list, e.g. a jury-trial highlight cut)."""
    rs = list(case.get("removes") or [])
    if case.get("remove"):
        rs.append(case["remove"])
    return sorted(((parse_tc(r["in"]), parse_tc(r["out"])) for r in rs))


def case_len(case, pad_out=0.0):
    return sum(b - a for a, b in case_parts(case, pad_out))


def case_parts(case, pad_out=0.0):
    """list of (src_in, src_out) in play order (one, or two when `remove` is used)."""
    a, b = parse_tc(case["in"]), parse_tc(case["out"]) + pad_out
    parts, cur = [], a
    for ra, rb in removes(case):
        parts.append((cur, ra))
        cur = rb
    parts.append((cur, b))
    return parts


def build(video, cases_by_id, cfg=None, durs=None):
    """Return dict(segments=[...], total=sec, seams=[...]).
    durs (optional real durations): {'hook','intro','vo1','bridge':[(a,b),...],'final'}"""
    c = dict(DEFAULTS)
    c.update(cfg or {})
    durs = durs or {}
    segs = []
    t = 0.0

    def add(kind, dur, **kw):
        nonlocal t
        segs.append(dict(kind=kind, start=t, dur=dur, **kw))
        t += dur

    hk = video["hook"]
    add("hook", durs.get("hook", parse_tc(hk["out"]) - parse_tc(hk["in"])))
    add("intro", durs.get("intro", float(c.get("intro_seconds_tt", 7.47)) if c.get("_renderer", "tt") == "tt" else float(video.get("intro_seconds", 6))))
    ids = video["case_ids"]
    if c.get("_renderer", "tt") == "tt":
        return _build_tt(video, cases_by_id, c, durs, segs, add, lambda: t)
    add("vo1", durs.get("vo1", V.est_seconds(video["vo1"]["text"], c["wps"]) + c["vo_lead"] + c["vo_tail"] - 0.5),
        case_id=ids[0], card="intro")
    bridges = {b["after_case_id"]: b for b in video.get("bridges", [])}
    seams = []
    for i, cid in enumerate(ids):
        cs = cases_by_id[cid]
        parts = case_parts(cs, c["cut_pad_out"])
        add("case", sum(b - a for a, b in parts), case_id=cid, parts=parts)
        if i < len(ids) - 1:
            br = bridges.get(cid)
            seams.append(t)
            if br:
                A, B = V.split_bridge(br["text"], br.get("split_after_sentence"))
                da, db = (durs["bridge"][i] if durs.get("bridge") and i < len(durs["bridge"]) else
                          (V.est_seconds(A, c["wps"]) + c["vo_lead"], V.est_seconds(B, c["wps"]) + c["vo_tail"]))
                add("bridge_result", da, case_id=cid, card="result")
                add("bridge_intro", db, case_id=ids[i + 1], card="intro")
    fin_est = V.est_seconds(video["vo_final"]["text"], c["wps"]) + c["vo_lead"] + c["vo_tail"]
    fin = durs.get("final", min(max(fin_est, c["final_min_hold"]), max(c["final_max_hold"], fin_est)))
    add("vo_final", fin, case_id=ids[-1], card="result")
    return {"segments": segs, "total": t, "seams": seams}


def est_clips_dur(text, c):
    """Estimated total seconds of the AI clips for `text` (each <=18 s), incl. lead/tail."""
    clips = V.split_clips(text, c.get("vo_clip_target", V.CLIP_TARGET), c["wps"])
    return sum(V.est_seconds(x, c["wps"]) + c["vo_lead"] + c["vo_tail"] - 0.5 for x in clips)


def _build_tt(video, cases_by_id, c, durs, segs, add, now):
    """Trial Tales locked structure: hook -> intro -> case, recap, case, recap ... case -> closing recap clips."""
    ids = video["case_ids"]
    bridges = {b["after_case_id"]: b for b in video.get("bridges", [])}
    seams = []
    for i, cid in enumerate(ids):
        cs = cases_by_id[cid]
        parts = case_parts(cs, c["cut_pad_out"])
        add("case", sum(b - a for a, b in parts), case_id=cid, parts=parts, n=i + 1)
        if i < len(ids) - 1:
            seams.append(now())
            br = bridges.get(cid)
            if br:
                d = durs["recap"][i] if durs.get("recap") and i < len(durs["recap"]) else est_clips_dur(br["text"], c)
                add("recap", d, case_id=cid)
    fin = durs.get("final")
    if fin is None:
        fin = max(est_clips_dur(video["vo_final"]["text"], c), c.get("final_min_hold", 10.0))
    add("vo_final", fin, case_id=ids[-1])
    t = now()
    return {"segments": segs, "total": t, "seams": seams}


def src_to_out(tl, case_id, tc):
    """Stream timecode (sec) inside a case -> output-video seconds, or None if it falls in a removed span."""
    for s in tl["segments"]:
        if s["kind"] != "case" or s["case_id"] != case_id:
            continue
        off = s["start"]
        for a, b in s["parts"]:
            if a <= tc <= b:
                return off + (tc - a)
            off += b - a
    return None


def find_case_for_tc(video, cases_by_id, tc):
    for cid in video["case_ids"]:
        cs = cases_by_id[cid]
        if parse_tc(cs["in"]) - 0.01 <= tc <= parse_tc(cs["out"]) + 0.01:
            return cid
    return None
