"""v10 overlay scheduler + safe-zone geometry (spec 8). Faces are never covered: every overlay rect is
asserted inside the style's safe zone and outside all footage rects - by geometry, not by hope."""
from .timeutil import parse_tc

# 1920x1080 canvas, per look
SAFE_ZONES = {
    "tt": (54, 840, 1866, 1040),          # bottom band below the 1920x540 strip (strip = y 270-810)
    "ov": (40, 790, 1320, 995),           # bottom band left of the side column, above the ticker
}
FOOTAGE = {
    "tt": [(0, 270, 1920, 810)],
    "ov": [(40, 40, 1320, 760), (1340, 40, 540, 760)],    # big tile + side column (pre re-staging bounds)
}
KIND_KICKER = {"fact": "FACT", "coming_up": "COMING UP", "so_far": "SO FAR", "watch": "WATCH THIS",
               "verdict_q": "YOUR VERDICT", "take": "OUR TAKE"}


def safe_zone(look):
    return SAFE_ZONES.get(look, SAFE_ZONES["tt"])


def footage_rects(look, layout=None):
    return list(FOOTAGE.get(look, FOOTAGE["tt"]))


def _rect_inside(inner, outer):
    return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _rect_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def card_rect(look, text, font_px=54):
    """The rect an overlay card will occupy: width from ~0.52 px/char at font size, max 2 lines.
    Always clamped inside the safe zone."""
    look = look or "tt"
    x0, y0, x1, y1 = safe_zone(look)
    lines = max(1, min(2, -(-len(text) // 60)))
    w = min(x1 - x0 - 8, int(len(text) * font_px * 0.52 / lines) + 150)
    h = min(y1 - y0 - 4, int(font_px * 1.25 * lines) + 40)       # kicker strip + padding, zone-clamped
    return (x0, y0, x0 + w, y0 + h)


def assert_safe(look, rect):
    sz = safe_zone(look)
    if not _rect_inside(rect, sz):
        raise ValueError(f"overlay rect {rect} escapes the {look} safe zone {sz}")
    for fr in footage_rects(look):
        if _rect_overlap(rect, fr):
            raise ValueError(f"overlay rect {rect} covers footage {fr}")


def schedule(case, src_to_out, total, busy, cfg, look="tt"):
    """Map a case's overlays to output time and resolve conflicts.

    case        the case dict (in/out + overlays[])
    src_to_out  fn(stream_tc) -> output seconds (or None when inside a removed span)
    total       measured video length in seconds
    busy        [(start, end)] output-time intervals already used (labels, cards, subscribe items)
    """
    ocfg = cfg.get("overlays") or {}
    if not ocfg.get("enabled", True):
        return []
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    head, tail = float(ocfg.get("skip_head_s", 40)), float(ocfg.get("skip_tail_s", 30))
    dur = float(ocfg.get("dur_s", 7.0))
    min_gap = float(ocfg.get("min_gap_s", 180))
    out = []
    for o in sorted(case.get("overlays") or [], key=lambda x: parse_tc(x.get("tc", "0:00:00"))):
        t = src_to_out(parse_tc(o.get("tc", "0:00:00")))
        if t is None:
            continue
        t0, t1 = t + 0.2, t + 0.2 + dur
        if t0 < head or t1 > total - tail:
            continue
        ref = o.get("ref_tc")
        if ref:
            try:
                rt = src_to_out(parse_tc(ref))
                if rt is not None and not (t1 + 45 <= rt <= total):
                    continue
            except Exception:
                continue
        # conflict resolution: shift +-20 s inside free space, else drop
        placed = None
        for shift in (0, 5, -5, 10, -10, 15, -15, 20, -20):
            s, e = t0 + shift, t1 + shift
            if s < head or e > total - tail:
                continue
            if any(not (e <= bs or s >= be) for bs, be in busy):
                continue
            if out and s - (out[-1][1]) < min_gap:
                continue
            placed = (s, e)
            break
        if placed:
            out.append((placed[0], placed[1], o))
    out.sort(key=lambda x: x[0])
    return out
