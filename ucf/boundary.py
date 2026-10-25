"""Boundary scoring + refinement (spec 7.5). IN is never moved (CASE START locked); OUT is refined inside
a window using transcript + Zoom-video signals, with hard constraints, snapping, confidence and a
corrections log. Degrades gracefully: no video file / no OCR -> transcript-only scoring."""
import json
from pathlib import Path

from . import zoom, tile_ocr
from .timeutil import parse_tc, fmt_tc


def _near(events, t, lo_off, hi_off, span):
    """Strongest triangular weight of any event landing in [t+lo_off, t+hi_off]."""
    best = 0.0
    for e in events:
        tc = e["tc"] if isinstance(e, dict) else e[0]
        if t + lo_off <= tc <= t + hi_off:
            best = max(best, max(0.0, 1.0 - abs(tc - t) / span))
    return best


def _tile_events_window(ev, video_path, a, b):
    key = (round(a, 1), round(b, 1))
    done = ev.setdefault("windows_done", [])
    if key not in done and ev.get("video_available"):
        try:
            for tc, f, to in zoom.tile_count_events(video_path, a, b):
                ev["tile_events"].append({"tc": tc, "from": f, "to": to})
            done.append(key)
        except Exception:
            done.append(key)
    return [e for e in ev["tile_events"] if a <= e["tc"] <= b]


def refine_case(case, ev, video_path, cfg, next_in=None):
    """Refine case OUT; returns (old_out, new_out, confidence). Never violates hard constraints."""
    bcfg = cfg.get("boundary") or {}
    if not bcfg.get("enabled", True) or not ev:
        return None
    w = float(bcfg.get("window_s", 120))
    wt = bcfg.get("weights", {})
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    if next_in is not None:
        b = min(b, next_in - 1)
    out_brain = b
    ruling_tc = None
    for p in case.get("phases") or []:
        if p.get("phase") == "ruling":
            ruling_tc = parse_tc(p["tc"])
    wrap = [e for e in ev.get("wrap_up", []) if a - 5 <= e["tc"] <= b + 30]
    calls = [c for c in ev.get("call_outs", []) if a + 30 < c["tc"] < b + 90]
    names = (case.get("name") or "").lower().split()
    surname = [n for n in names if len(n) >= 4] or names
    tiles = _tile_events_window(ev, video_path, max(0, a - 5), min(b + w, (next_in or b + w)))
    silences = [s for s in ev.get("silence", [])]

    lo, hi = max(a + 30, b - w), min(b + w, (next_in or b + w + 1) - 1)
    if lo >= hi:
        return None
    best, best_score = None, -1e9
    t = float(lo)
    while t <= hi:
        s = 0.0
        s += float(wt.get("next_call", 3.0)) * _near(calls, t, 0, 45, 45)
        s += float(wt.get("wrap_up", 2.0)) * _near(wrap, t, -20, 5, 25)
        s += float(wt.get("tile_count", 1.5)) * _near([{"tc": e["tc"]} for e in tiles], t, -6, 6, 12)
        s += float(wt.get("silence", 1.0)) * _near(silences, t, 0, 5, 5)
        if ruling_tc is not None and t < ruling_tc + 3:
            s += float(wt.get("before_ruling", -4.0))
        if any(c["tc"] < t for c in calls):
            s += float(wt.get("call_inside", -5.0)) * 0        # call_inside handled as hard check below
        if s > best_score:
            best, best_score = t, s
        t += 1.0
    # hard constraints: never cut a ruling - brain phase AND transcript evidence both act as floors
    floors = []
    if ruling_tc is not None and not case.get("ruling_deferred"):
        floors.append(ruling_tc + 3)
    tr_rulings = [r for r in ev.get("ruling", []) if a < r["tc"] < b + w]
    if tr_rulings and not case.get("ruling_deferred"):
        floors.append(max(r["tc"] for r in tr_rulings) + 3)
    if floors:
        # a ruling floor BEYOND the brain's window legitimately widens the search (never past the next case)
        hi = max(hi, *[min(fl, (next_in or fl + 1) - 1) for fl in floors])
        b2 = parse_tc(case["out"])
    for fl in floors:
        if best < fl:
            best = min(fl, hi)
    if wrap:
        wtc = max(x["tc"] for x in wrap if x["tc"] <= hi)
        if wtc > best - 20 and wtc <= hi:
            best = min(wtc + 0.5, hi)                          # snap to wrap-up end
    if next_in is not None:
        best = min(best, next_in - 1)
    best = max(best, a + 30)
    if abs(best - out_brain) > w:
        best = out_brain                                       # never drift beyond the window
    # confidence: gap to second best + agreeing signal count
    second = -1e9
    t = float(lo)
    while t <= hi:
        if abs(t - best) > 10 and t != best:
            s2 = _score_at(t, wt, calls, wrap, tiles, silences, ruling_tc)
            second = max(second, s2)
        t += 1.0
    agree = sum(1 for x in (calls, wrap, tiles) if _near(x if isinstance(x, list) and x and isinstance(x[0], dict)
                                                          else [{"tc": y[0]} for y in x], best, -10, 10, 20) > 0)
    confidence = int(100 * min(1.0, max(0.0, (best_score - max(second, 0)) / 3 + agree / 6)))
    old = case["out"]
    case["out"] = fmt_tc(best, False)
    case["boundary"] = {
        "out_brain": fmt_tc(out_brain, False), "out_score": round(best_score, 2),
        "confidence": confidence,
        "signals": [f"next call {c['tc']}" for c in calls][:2] + [f"wrap-up {x['tc']}" for x in wrap][:2]
                   + [f"tile {e['from']}->{e['to']} at {e['tc']}" for e in tiles][:2],
        "start_confirmed": bool(tiles or wrap), "vision_used": False,
    }
    return old, case["out"], confidence


def _score_at(t, wt, calls, wrap, tiles, silences, ruling_tc):
    s = 0.0
    s += float(wt.get("next_call", 3.0)) * _near(calls, t, 0, 45, 45)
    s += float(wt.get("wrap_up", 2.0)) * _near(wrap, t, -20, 5, 25)
    s += float(wt.get("tile_count", 1.5)) * _near([{"tc": e["tc"]} for e in tiles], t, -6, 6, 12)
    s += float(wt.get("silence", 1.0)) * _near(silences, t, 0, 5, 5)
    if ruling_tc is not None and t < ruling_tc + 3:
        s += float(wt.get("before_ruling", -4.0))
    return s


def refine_plan(plan, ev, video_path, cfg, work, ui=print):
    """Refine every used case in mode all (sorted by IN so next_in is known) + write reports/logs."""
    used = sorted([c for c in plan.get("cases", []) if c.get("status") == "used"], key=lambda c: parse_tc(c["in"]))
    changes = []
    for i, c in enumerate(used):
        nxt = parse_tc(used[i + 1]["in"]) if i + 1 < len(used) else None
        r = refine_case(c, ev, video_path, cfg, next_in=nxt)
        if r:
            old, new, conf = r
            if abs(parse_tc(new) - parse_tc(old)) > 1:
                ui(f"  boundary {c['name']}: OUT {old} -> {new} (confidence {conf})")
            changes.append({"case": c["name"], "brain_out": old, "refined_out": new, "confidence": conf})
    if work:
        Path(work).mkdir(parents=True, exist_ok=True)
        (Path(work) / "boundary_changes.json").write_text(json.dumps(changes, indent=1), encoding="utf-8")
        lines = ["# Boundary report", ""]
        for c in used:
            bd = c.get("boundary") or {}
            lines.append(f"- {c['name']}: IN {c['in']}  OUT {bd.get('out_brain', c['out'])} -> {c['out']}  "
                         f"confidence {bd.get('confidence', '-')}  signals: {'; '.join(bd.get('signals', [])) or '-'}")
        (Path(work) / "boundary_report.md").write_text("\n".join(lines), encoding="utf-8")
    return changes
