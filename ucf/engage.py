"""Retention scheduler: something useful on screen at least every few seconds, every beat carries information.

The rule (all new documentary styles):
  * court footage: never more than `max_gap_court` s (default 18) without a beat
  * narration / B-roll: never more than `max_gap_vo` s (default 7) without a beat
  * a beat is VALUE first: a case fact, a ruling, a legal term explained, a date, a quote callout, a question the video
    will answer ("coming up"), the mini case document, a counter. Only when the video has nothing left to say in that
    gap does it fall back to a visual-only beat (punch-in zoom on court, slow push / Ken Burns on B-roll), and the
    report says so - so the brain can be asked for more facts next time.
  * no two beats of the same kind back to back, beats never overlap each other or the style's own cards.

    beats, report = schedule(duration, segments, candidates, existing)
    segments   = [(start, end, "court" | "vo")]
    candidates = [{"t": preferred second, "kind": "fact", "text": "...", "dur": 4}]   (from candidates_from_plan)
    existing   = [(start, end)] already busy (chapter cards, stamps, polls...)
"""
import re

KINDS_VALUE = ("fact", "ruling", "jargon", "date", "quote", "question", "doc", "counter", "charge")
FALLBACK = {"court": "zoom", "vo": "push"}
DEFAULTS = {"max_gap_court": 18.0, "max_gap_vo": 7.0, "min_gap": 3.0, "beat_dur": 4.0, "window": 25.0}

# plain-English definitions shown when the term is said in court (fixed list: the brain never writes definitions)
JARGON = {
    "deferred adjudication": "Probation without a conviction - finish it and the case is dismissed.",
    "motion to adjudicate": "The State asks the judge to find the person guilty after breaking probation.",
    "motion to revoke": "The State asks the judge to end probation and send the person to jail or prison.",
    "nolo contendere": "No contest - not admitting guilt, but not fighting the charge.",
    "no contest": "Not admitting guilt, but not fighting the charge.",
    "plea bargain": "A deal: plead guilty for a lighter or agreed sentence.",
    "plea agreement": "A deal: plead guilty for a lighter or agreed sentence.",
    "discovery": "The evidence the State must share with the defense before a plea or trial.",
    "indictment": "A grand jury's formal decision that there is enough evidence to charge.",
    "true bill": "The grand jury agreed there is enough evidence for a trial.",
    "pr bond": "Personal recognizance bond - released on a promise to come back, no cash.",
    "personal recognizance": "Released on a promise to come back to court, no cash.",
    "surety bond": "A bail bond paid through a bondsman.",
    "bond conditions": "Rules the person must follow to stay out of jail before trial.",
    "community supervision": "Texas name for probation.",
    "probation": "Serving the sentence outside jail under strict rules.",
    "felony": "A serious crime - punishable by prison time.",
    "misdemeanor": "A lesser crime - punishable by jail time or a fine.",
    "state jail felony": "The lowest felony level in Texas - 180 days to 2 years in a state jail.",
    "enhancement": "A prior conviction that raises the punishment range.",
    "habitual offender": "Two prior felony prison trips - punishment can go up to life.",
    "credit for time served": "Days already spent in jail count toward the sentence.",
    "capias": "A warrant for the person's arrest issued by the court.",
    "bench warrant": "An arrest warrant issued by the judge, often for missing court.",
    "continuance": "Moving the hearing to a later date.",
    "pre-sentence investigation": "A report on the person's background before sentencing.",
    "psi": "Pre-sentence investigation - a background report before sentencing.",
    "ignition interlock": "A breath-test device that must be passed before the car starts.",
    "scram": "An ankle monitor that checks for alcohol through the skin.",
    "ua": "Urinalysis - a drug test.",
    "allocution": "The defendant's chance to speak before the sentence.",
    "victim impact statement": "The victim or family tells the court how the crime affected them.",
    "restitution": "Money the defendant must pay back to the victim.",
    "adjudicated": "Formally found guilty.",
    "revoked": "Probation is over - the original punishment can now be given.",
}


def find_jargon(lines):
    """lines = [(start, end, text)] -> candidates for every legal term said (first time only)."""
    seen, out = set(), []
    for s, e, txt in lines:
        low = " " + re.sub(r"[^a-z ]", " ", (txt or "").lower()) + " "
        for term, d in JARGON.items():
            if term in seen:
                continue
            if f" {term} " in low:
                seen.add(term)
                out.append({"t": s, "kind": "jargon", "text": f"{term.upper()}: {d}", "dur": 5.0, "term": term})
    return out


def candidates_from_plan(case, facts=None, lines=None):
    """Value beats for one case: overlays the brain wrote, case facts, rulings, charges, the jargon heard."""
    out = []
    for o in case.get("overlays") or []:
        t = o.get("t", o.get("tc_s"))
        if t is None or not o.get("text"):
            continue
        kind = {"coming_up": "question", "verdict_q": "question", "so_far": "fact", "watch": "quote"}.get(o.get("kind"), "fact")
        out.append({"t": float(t), "kind": kind, "text": o["text"], "dur": 4.0})
    for r in case.get("rulings") or []:
        if r.get("t") is not None and r.get("text"):
            out.append({"t": float(r["t"]), "kind": "ruling", "text": r["text"], "dur": 5.0})
    for q in case.get("quotes") or []:
        if q.get("t") is not None and q.get("text"):
            out.append({"t": float(q["t"]), "kind": "quote", "text": q["text"], "dur": 4.0})
    if facts:
        out.append({"t": None, "kind": "doc", "text": "CASE SUMMARY", "dur": 6.0})
        if facts.get("charges"):
            out.append({"t": None, "kind": "charge", "text": facts["charges"], "dur": 4.0})
    out += find_jargon(lines or [])
    return out


def _seg_at(t, segments):
    for a, b, k in segments:
        if a <= t < b:
            return k
    return "vo"


def _free(t, dur, busy, min_gap):
    return all(t + dur + min_gap <= a or t >= b + min_gap for a, b in busy)


def schedule(duration, segments, candidates, existing=None, cfg=None):
    """-> (beats [{"start","end","kind","text","value": bool}], report [str])."""
    c = dict(DEFAULTS, **(cfg or {}))
    busy = sorted((float(a), float(b)) for a, b in (existing or []))
    pool = [dict(x) for x in candidates]
    beats, report = [], []
    last_kind = None
    t = 0.0
    last_end = 0.0
    for a, b in busy:                               # style cards count as beats too
        if a <= 0.5:
            last_end = max(last_end, b)
    step = 0.5
    while t < duration:
        seg = _seg_at(t, segments)
        gap = c["max_gap_court"] if seg == "court" else c["max_gap_vo"]
        covered = max([last_end] + [b for a, b in busy if a <= t])
        if t - covered < gap:
            t += step
            continue
        # a beat is due at t: the best value candidate near t, a different kind than the last one
        dur = c["beat_dur"]
        best, score = None, None
        for x in pool:
            if x.get("used") or x["kind"] == last_kind:
                continue
            pt = x.get("t")
            d = abs(pt - t) if pt is not None else c["window"] * 0.6
            if pt is not None and (pt > t + 2 or d > c["window"]):
                continue                             # never show something before it is said
            if not _free(t, x.get("dur", dur), busy, c["min_gap"]):
                continue
            if score is None or d < score:
                best, score = x, d
        if best:
            best["used"] = True
            d = float(best.get("dur", dur))
            beats.append({"start": round(t, 2), "end": round(t + d, 2), "kind": best["kind"], "text": best["text"], "value": True})
            last_kind = best["kind"]
        else:
            d = 2.5
            k = FALLBACK.get(seg, "push")
            beats.append({"start": round(t, 2), "end": round(t + d, 2), "kind": k, "text": "", "value": False})
            report.append(f"{int(t // 60)}:{int(t % 60):02d} no fact left for this gap - {k} only")
            last_kind = k
        busy.append((t, t + d))
        busy.sort()
        last_end = t + d
        t = last_end
    unused = [x for x in pool if not x.get("used") and x["kind"] in ("ruling", "jargon")]
    for x in unused:                                 # rulings / terms are always worth showing when there is room
        if x.get("t") is not None and _free(x["t"], x.get("dur", 4), busy, c["min_gap"]):
            beats.append({"start": round(x["t"], 2), "end": round(x["t"] + x.get("dur", 4), 2), "kind": x["kind"],
                          "text": x["text"], "value": True})
            busy.append((x["t"], x["t"] + x.get("dur", 4)))
    beats.sort(key=lambda b: b["start"])
    return beats, report


def max_gap(beats, segments, duration, existing=None):
    """Longest stretch without a beat, per segment kind -> {"court": s, "vo": s} (validator rule E-01)."""
    spans = sorted([(b["start"], b["end"]) for b in beats] + [tuple(x) for x in (existing or [])])
    out = {"court": 0.0, "vo": 0.0}
    prev = 0.0
    for a, b in spans + [(duration, duration)]:
        if a > prev:
            k = _seg_at((prev + a) / 2, segments)
            out[k] = max(out[k], a - prev)
        prev = max(prev, b)
    return out


def value_share(beats):
    return sum(1 for b in beats if b["value"]) / len(beats) if beats else 1.0
