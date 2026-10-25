"""Zoom gallery understanding for the Overruled skin.

* tile template detection  - the gallery is 1, 2, 3 or 4 tiles; the layout is matched against known Zoom templates in
  1280x720 reference coordinates (works for any source resolution, frames are scaled to 1280x720 first)
* active speaker           - Zoom outlines the speaking tile in green
* runs                     - (t0, t1, layout, active) with smoothing so the big tile never ping-pongs
* geometry                 - where each tile goes on the 1920x1080 Overruled canvas
"""
import json
import subprocess
from pathlib import Path

import numpy as np

W, H = 1280, 720
TEMPLATES = {
    "1":  [(0, 0, 1280, 720)],
    "2":  [(0, 180, 640, 360), (640, 180, 640, 360)],
    "3":  [(0, 0, 640, 360), (720, 0, 480, 360), (320, 360, 640, 360)],
    "3w": [(0, 0, 640, 360), (640, 0, 640, 360), (320, 360, 640, 360)],
    "4":  [(0, 0, 640, 360), (640, 0, 640, 360), (0, 360, 640, 360), (640, 360, 640, 360)],
}
DEFAULT_ACTIVE = {"1": 0, "2": 1, "3": 2, "4": 0}
SAMPLE_EVERY = 2.0          # seconds between probe frames
MIN_LAYOUT_RUN = 4.0
MIN_ACTIVE_RUN = 7.0        # the big tile never changes faster than this (calm for a 40-60 audience)


def classify(rgb):
    """rgb: HxWx3 uint8 at 1280x720 -> (layout, active_index|None, score)."""
    lum = rgb.mean(axis=2)
    lit = lum > 14
    best = None
    for name, rects in TEMPLATES.items():
        m = np.zeros(lit.shape, bool)
        fills = []
        for x, y, w, h in rects:
            m[y:y + h, x:x + w] = True
            fills.append(lit[y:y + h, x:x + w].mean())
        outside = lit[~m].mean() if (~m).any() else 0.0
        sc = float(np.mean(fills)) - 2.5 * outside
        if name == "1":
            sc -= 0.12              # a lone full-frame tile only wins when nothing else fits
        if best is None or sc > best[0]:
            best = (sc, name)
    sc, name = best
    layout = "3" if name == "3w" else name
    if sc < 0.70:
        layout, name = "1", "1"
    rects = TEMPLATES[name]
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    green = (g > 170) & (g - r > 60) & (g - b > 80)
    act, bestf = None, 0.30
    if len(rects) > 1:
        for i, (x, y, w, h) in enumerate(rects):
            ring = np.zeros(green.shape, bool)
            ring[y:y + 4, x:x + w] = True
            ring[y + h - 4:y + h, x:x + w] = True
            ring[y:y + h, x:x + 4] = True
            ring[y:y + h, x + w - 4:x + w] = True
            f = green[ring].mean()
            if f > bestf:
                act, bestf = i, f
    return layout, name, act, sc


def sample(path, a, b, cache=None):
    """Decode one frame every SAMPLE_EVERY s of [a, b) -> list of (t, layout, template, active)."""
    key = f"{path}|{a:.1f}|{b:.1f}"
    if cache is not None and key in cache:
        return [tuple(x) for x in cache[key]]
    d = b - a
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(path), "-an",
           "-vf", f"fps=1/{SAMPLE_EVERY},scale={W}:{H}:flags=fast_bilinear", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, n, size = [], 0, W * H * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        lay, name, act, _ = classify(rgb)
        out.append((n * SAMPLE_EVERY, lay, name, act))
        n += 1
    p.wait()
    if not out:
        out = [(0.0, "2", "2", None)]
    if cache is not None:
        cache[key] = out
    return out


def _mode(vals, default):
    vals = [v for v in vals if v is not None]
    if not vals:
        return default
    return max(set(vals), key=vals.count)


def runs(samples, d):
    """samples -> [(t0, t1, layout, template, active)] covering 0..d, smoothed."""
    S = sorted(samples)
    n = len(S)
    # layout run smoothing
    lay = [s[1] for s in S]
    tpl = [s[2] for s in S]
    i = 0
    seq = []
    for k in range(n):
        t0 = 0.0 if k == 0 else S[k][0]
        t1 = d if k == n - 1 else S[k + 1][0]
        if seq and seq[-1][2] == lay[k]:
            seq[-1][1] = t1
        else:
            seq.append([t0, t1, lay[k], tpl[k]])
    ch = True
    while ch and len(seq) > 1:
        ch = False
        for k, (t0, t1, l, tp) in enumerate(seq):
            if t1 - t0 < MIN_LAYOUT_RUN:
                nb = k - 1 if k > 0 else k + 1
                lo, hi = min(k, nb), max(k, nb)
                seq[lo:hi + 1] = [[seq[lo][0], seq[hi][1], seq[nb][2], seq[nb][3]]]
                ch = True
                break
    # active speaker inside each layout run
    out = []
    for t0, t1, l, tp in seq:
        idx = [k for k in range(n) if S[k][0] >= t0 - 1e-6 and S[k][0] < t1 - 1e-6 and S[k][1] == l]
        acts = [S[k][3] for k in idx]
        if l in ("2", "3"):       # the courtroom wide shot (tile 0) lights up whenever an attorney speaks: keep the witness/judge big
            acts = [None if a_ == 0 else a_ for a_ in acts]
        # carry forward unknowns, then majority over a ~10 s window
        carry, last = [], None
        for a_ in acts:
            last = a_ if a_ is not None else last
            carry.append(last)
        win = max(1, int(round(10 / SAMPLE_EVERY)) | 1)
        sm = []
        for k in range(len(carry)):
            lo, hi = max(0, k - win // 2), min(len(carry), k + win // 2 + 1)
            sm.append(_mode(carry[lo:hi], DEFAULT_ACTIVE.get(l, 0)))
        sub = []
        for k, a_ in enumerate(sm):
            s0 = t0 if k == 0 else S[idx[k]][0]
            s1 = t1 if k == len(sm) - 1 else S[idx[k + 1]][0]
            if sub and sub[-1][2] == a_:
                sub[-1][1] = s1
            else:
                sub.append([s0, s1, a_])
        if not sub:
            sub = [[t0, t1, DEFAULT_ACTIVE.get(l, 0)]]
        ch = True
        while ch and len(sub) > 1:
            ch = False
            for k, (s0, s1, a_) in enumerate(sub):
                if s1 - s0 < MIN_ACTIVE_RUN:
                    nb = k - 1 if k > 0 else k + 1
                    lo, hi = min(k, nb), max(k, nb)
                    sub[lo:hi + 1] = [[sub[lo][0], sub[hi][1], sub[nb][2]]]
                    ch = True
                    break
        for s0, s1, a_ in sub:
            out.append((s0, s1, l, tp, a_ if a_ is not None else DEFAULT_ACTIVE.get(l, 0)))
    # make runs contiguous
    fixed = []
    for k, r in enumerate(out):
        t0 = 0.0 if k == 0 else fixed[-1][1]
        t1 = d if k == len(out) - 1 else r[1]
        fixed.append((t0, t1, r[2], r[3], r[4]))
    return fixed


# ----------------------------------------------------------------------------------------------- geometry
BIG = (40, 40, 1280, 720)
BRIEF_LOW = (1340, 364, 540, 396)      # 1- and 2-tile layouts: card under / beside the small tile
BRIEF_FULL = (1340, 40, 540, 720)
BRIEF_COL4 = (1360, 40, 520, 720)


def geometry(layout, template, active):
    """-> dict(tiles=[(src_rect_1280, dst_rect)], big=rect|None, small=[rects], brief=(geom, mode))
    mode: 'always' (card stays) | 'first' (card shown for the first seconds only, covering the side column)."""
    rects = TEMPLATES[template]
    n = len(rects)
    act = active if active is not None and active < n else DEFAULT_ACTIVE.get(layout, 0)
    if layout == "1":
        return dict(tiles=[(rects[0], BIG)], big=BIG, small=[], brief=(BRIEF_FULL, "always"))
    if layout == "2":
        other = 1 - act
        small = (1340, 40, 540, 304)
        return dict(tiles=[(rects[act], BIG), (rects[other], small)], big=BIG, small=[small], brief=(BRIEF_LOW, "always"))
    if layout == "3":
        others = [i for i in range(n) if i != act]
        s1, s2 = (1340, 40, 540, 350), (1340, 410, 540, 350)
        return dict(tiles=[(rects[act], BIG), (rects[others[0]], s1), (rects[others[1]], s2)], big=BIG, small=[s1, s2],
                    brief=(BRIEF_FULL, "first"))
    # 4 tiles: 2x2 grid in template order, active outlined
    dst = [(40, 40, 640, 360), (700, 40, 640, 360), (40, 420, 640, 340), (700, 420, 640, 340)]
    return dict(tiles=[(rects[i], dst[i]) for i in range(4)], big=dst[act], small=[dst[i] for i in range(4) if i != act],
                brief=(BRIEF_COL4, "always"))


def cover_crop(src, dst, bias=0.18):
    """Largest sub-rect of `src` with the aspect of `dst`, biased upward (faces)."""
    x, y, w, h = src
    dw, dh = dst[2], dst[3]
    if w / h > dw / dh:
        nw = h * dw / dh
        return (x + (w - nw) / 2, y, nw, h)
    nh = w * dh / dw
    return (x, y + (h - nh) * bias, w, nh)
