"""Shared Zoom-gallery helpers for v10. Wraps the Overruled detector (ov_layout) so both looks and the
boundary engine share one implementation. Never breaks Overruled: ov_layout stays the source of truth."""
from . import ov_layout


def classify(rgb):
    return ov_layout.classify(rgb)


def sample(path, a, b, cache=None):
    return ov_layout.sample(path, a, b, cache=cache)


def runs(samples, d):
    return ov_layout.runs(samples, d)


def tile_count_events(path, a, b):
    """[(tc, from_count, to_count)] inside [a, b] - layout changes collapsed to tile counts."""
    samples = sample(path, a, b)
    if not samples:
        return []
    d = b - a
    ev, prev = [], None
    for t0, t1, layout, _active in runs(samples, d):
        n = int(layout[0]) if str(layout)[0].isdigit() else 1
        if prev is not None and n != prev[1] and a <= t0 <= b:
            ev.append((round(t0, 1), prev[1], n))
        prev = (t0, n)
    return ev
