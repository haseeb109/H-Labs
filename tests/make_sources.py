#!/usr/bin/env python3
"""Build state/sources.json for the Rendon fixture: map the pre-cut clips in tests/fixtures/rv_clips
to their stream-clock ranges so the renderer can cut the 28:37 test video without the full stream.

Each clip was cut with a symmetric ~2 s handle around its piece, so the handle is recovered from the
probed duration: handle = (clip_duration - piece_duration) / 2, clip_in = piece_in - handle.
Every range the renderer will request (hook, pieces + 0.5 s pad, recap windows) is verified to sit
inside a clip; the script exits non-zero on any gap.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ucf.timeutil import parse_tc, fmt_tc  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "rv_clips"
PLAN = json.loads((ROOT / "tests" / "rendon_2025-05-09_plan.json").read_text(encoding="utf-8"))
SNAME = "lVQ79x0Hd_w.mp4"
URL = "https://youtu.be/lVQ79x0Hd_w"


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def pieces():
    """[(name, in_s, out_s)] in play order: 9 Rendon pieces, the hook window, then Maldonado."""
    c1 = next(c for c in PLAN["cases"] if c["id"] == 1)
    c2 = next(c for c in PLAN["cases"] if c["id"] == 2)
    raw, cur = [], parse_tc(c1["in"])
    for rm in c1["removes"]:
        raw.append((cur, parse_tc(rm["in"])))
        cur = parse_tc(rm["out"])
    raw.append((cur, parse_tc(c1["out"])))
    named = [(f"r{i + 1}", a, b) for i, (a, b) in enumerate(raw)]
    h = PLAN["videos"][0]["hook"]
    named.append(("hook", parse_tc(h["in"]), parse_tc(h["out"])))
    named.append(("m1", parse_tc(c2["in"]), parse_tc(c2["out"])))
    return named


def main():
    clips = []
    for name, a, b in pieces():
        f = FIX / f"{name}.mp4"
        if not f.exists():
            sys.exit(f"missing fixture clip: {f}")
        dur = probe_dur(f)
        handle = (dur - (b - a)) / 2.0
        if not 0.0 < handle < 15.0:
            sys.exit(f"{name}: probed {dur:.1f}s vs piece {b - a:.1f}s -> handle {handle:.1f}s looks wrong")
        cin, cout = round(a - handle, 2), round(b + handle, 2)
        if abs((cout - cin) - dur) > 0.35:
            sys.exit(f"{name}: handle fit off by {abs((cout - cin) - dur):.2f}s")
        clips.append({"in": cin, "out": cout, "path": str(f), "piece": name})
        print(f"  {name:>4}: {fmt_tc(cin, False)} - {fmt_tc(cout, False)}  ({dur:6.1f}s, handle {handle:.1f}s)")
    clips.sort(key=lambda c: c["in"])
    state = ROOT / "state"
    state.mkdir(exist_ok=True)
    sp = state / "sources.json"
    src = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    src[SNAME] = {"path": str(FIX / "r1.mp4"), "url": URL, "clips": clips}
    sp.write_text(json.dumps(src, indent=2), encoding="utf-8")
    print(f"wrote {sp} ({len(clips)} clips)")

    # verify every range the renderer may request is covered by exactly one clip
    c1 = next(c for c in PLAN["cases"] if c["id"] == 1)
    c2 = next(c for c in PLAN["cases"] if c["id"] == 2)
    need = [("hook", parse_tc(PLAN["videos"][0]["hook"]["in"]), parse_tc(PLAN["videos"][0]["hook"]["out"])),
            ("thumb", parse_tc(PLAN["videos"][0]["thumbnail"]["window_in"]),
             parse_tc(PLAN["videos"][0]["thumbnail"]["window_out"])),
            ("case2", parse_tc(c2["in"]), parse_tc(c2["out"]) + 0.5)]
    cur = parse_tc(c1["in"])
    for rm in c1["removes"]:
        need.append(("piece", cur, parse_tc(rm["in"]) + 0.5))
        cur = parse_tc(rm["out"])
    need.append(("piece", cur, parse_tc(c1["out"]) + 0.5))
    for tag, a, b in need:
        hits = [c["piece"] for c in clips if c["in"] - 0.01 <= a and b <= c["out"] + 0.01]
        if not hits:
            sys.exit(f"GAP: {tag} {fmt_tc(a, False)}-{fmt_tc(b, False)} not covered by any clip")
    print(f"coverage OK: {len(need)} requested ranges covered (locate uses the first match, chronological order)")


if __name__ == "__main__":
    main()
