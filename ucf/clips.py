"""Clips-only output (menu mode 4): for every verified case >= 8:00 -> ONE clean clip for the editor + an editing guide.

clip.mp4   = hook (10-20 s, from inside the case) + the whole case, dead air cut out. Native resolution, frame-accurate cuts,
             encoded ONCE as H.264 (opens in every editor). No overlays, no AI voice, no graphics, no watermark.
EDITOR_GUIDE.txt = everything the full render would have added, as instructions with CLIP timestamps: hook text, text overlays
             (where + what), subscribe CTAs, the closing voice-over script (ready to paste into any TTS), titles, thumbnail,
             description, chapters, tags - and the list of cuts (source times) in case the editor wants something back.
The brain runs exactly as in mode "all" (Pass A cases + Pass B packaging), so the guide holds the same texts the full video would.

config: clips_crf (14) | clips_dead_air_s (10: a silence this long inside a case is cut) | clips_dead_air_pad (0.7 s kept each side)
        clips_dead_air_max_share (0.35: never cut more 'silence' than this share of a case - protects against transcript holes)
        clips_hook_min / clips_hook_max (10 / 20 s)
"""
import json
import subprocess
from pathlib import Path

from . import timeline as TL
from . import vo as V
from .timeutil import fmt_tc, parse_tc

PILL_EVERY = 360.0          # same rhythm as the full styles: small subscribe reminder every 6 min


def mmss(t):
    t = max(0, int(round(t)))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def hook_span(video, case, cfg):
    """(a, b) source seconds of the hook, held to 10-20 s and inside the case."""
    lo, hi = float(cfg.get("clips_hook_min", 10)), float(cfg.get("clips_hook_max", 20))
    ca, cb = parse_tc(case["in"]), parse_tc(case["out"])
    hk = video.get("hook") or {}
    try:
        a, b = parse_tc(hk["in"]), parse_tc(hk["out"])
    except Exception:
        a, b = ca + (cb - ca) * 0.6, ca + (cb - ca) * 0.6 + 15
    a = min(max(a, ca), cb - lo)
    b = min(max(b, a + lo), a + hi, cb)
    return a, b


def silent_gaps(segs, a, b, min_gap, pad):
    """Transcript gaps >= min_gap inside [a, b] -> removable spans (pad seconds kept on each side)."""
    sp = sorted((float(s["start"]), float(s["end"])) for s in segs if float(s["end"]) > a and float(s["start"]) < b)
    out, cur = [], a
    for s, e in sp + [(b, b)]:
        if s - cur >= min_gap:
            out.append((cur + pad, s - pad))
        cur = max(cur, e)
    return out


def case_spans(case, segs, cfg):
    """Kept (src_a, src_b) parts of a case: the brain's removes + dead air from the transcript, merged.
    Safety: a transcript with holes (captions that missed quiet speech) would look like 'dead air' - when the silences add up to
    more than clips_dead_air_max_share (35%) of the case, only gaps >= 30 s are cut, and if that is still too much, none."""
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    pad, share = float(cfg.get("clips_dead_air_pad", 0.7)), float(cfg.get("clips_dead_air_max_share", 0.35))
    gaps = []
    for min_gap in (float(cfg.get("clips_dead_air_s", 10)), 30.0):
        gaps = silent_gaps(segs or [], a, b, min_gap, pad)
        if sum(y - x for x, y in gaps) <= share * (b - a):
            break
    else:
        gaps = []
    cut = list(TL.removes(case)) + gaps
    cut = sorted((max(a, x), min(b, y)) for x, y in cut if y - x > 0.5)
    merged = []
    for x, y in cut:
        if merged and x <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y))
        else:
            merged.append((x, y))
    parts, cur = [], a
    for x, y in merged:
        if x - cur > 0.3:
            parts.append((cur, x))
        cur = max(cur, y)
    if b - cur > 0.3:
        parts.append((cur, b))
    return parts, merged


def build_map(hook, parts):
    """[(kind, src_a, src_b, out_start)] in clip order."""
    rows, t = [("hook", hook[0], hook[1], 0.0)], hook[1] - hook[0]
    for x, y in parts:
        rows.append(("case", x, y, t))
        t += y - x
    return rows, t


def src_to_clip(rows, src):
    """Clip time of a source moment inside the case (a moment that was cut lands on the next kept frame); None if outside."""
    for kind, a, b, o in rows:
        if kind == "case" and a <= src <= b:
            return o + (src - a)
    later = [(a, o) for kind, a, b, o in rows if kind == "case" and a > src]
    return later[0][1] if later else None


def encode_args(enc, cfg):
    from .render import venc, _X264
    if enc == "libx264":
        return ["-c:v", "libx264", "-preset", _X264["preset"], "-crf", str(cfg.get("clips_crf", 14)), "-profile:v", "high",
                "-pix_fmt", "yuv420p", "-g", "60", *(["-threads", _X264["threads"]] if _X264["threads"] != "0" else [])]
    return venc(enc)


def cut_clip(src, rows, out, enc, cfg, ui=print):
    """One ffmpeg pass: every span as its own accurately-seeked input -> concat -> one H.264 encode. Short audio fades at every
    join so the cuts do not click."""
    from .render import hwdec, run_progress
    cmd, fc, n = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"], [], 0
    total = 0.0
    for _k, a, b, _o in rows:
        d = b - a
        cmd += ["-ss", f"{a:.3f}", "-t", f"{d:.3f}", *hwdec(), "-i", str(src)]
        f = min(0.04, d / 4)
        fc.append(f"[{n}:v]setpts=PTS-STARTPTS,setsar=1[v{n}];"
                  f"[{n}:a]asetpts=PTS-STARTPTS,afade=t=in:d={f:.3f},afade=t=out:st={max(0, d - f):.3f}:d={f:.3f}[a{n}]")
        n += 1
        total += d
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", *encode_args(enc, cfg),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    if total > 60:
        run_progress(cmd, total, "    clip", ui=ui)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("clip cut failed:\n" + r.stderr[-1500:])
    return total


def frames(src, times, folder):
    """Still frames (thumbnail candidates) at source times -> [paths]."""
    out = []
    for i, t in enumerate(times, 1):
        p = Path(folder) / f"thumbnail_frame_{i}.jpg"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(p)],
                           capture_output=True)
        if r.returncode == 0 and p.exists():
            out.append(p)
    return out


def guide(plan, video, case, rows, total, cuts, cfg, source_url=""):
    """EDITOR_GUIDE.txt text."""
    wps = float(cfg.get("wps", 2.6))
    hk_len = rows[0][2] - rows[0][1]
    L = ["=" * 72, f"  EDITOR GUIDE  -  {case.get('name', '')}   ({cfg.get('channel_name') or cfg.get('style', '')})",
         "=" * 72, "",
         f"clip.mp4 = {mmss(total)}   |   hook 0:00-{mmss(hk_len)}, then the whole case (dead air already cut out)",
         *([f"Case: {' - '.join(x for x in (case.get('charge'), case.get('question')) if x)}"]
           if case.get("charge") or case.get("question") else []),
         f"Source: {source_url or plan.get('source_file', '')}   case {case.get('in')}-{case.get('out')}", "",
         "Every time below is a CLIP time (where it goes in clip.mp4).  Add: watermark (your own), music, graphics as usual.", ""]

    ev = []                                                                   # (clip time, line)
    hk = video.get("hook") or {}
    if hk.get("headline"):
        ev.append((0.0, f"TEXT OVERLAY  0:00-{mmss(hk_len)}   HOOK TITLE, big, top-centre:  \"{hk['headline']}\""))
    ev.append((hk_len, f"CUT / TRANSITION  {mmss(hk_len)}   hook ends -> case starts (channel intro / sting here if you use one)"))
    pos = {"fact": "bottom-left lower third", "coming_up": "top-left banner ('COMING UP')", "quote": "bottom-centre, quote style",
           "number": "bottom-left lower third", "context": "bottom-left lower third"}
    busy_until = hk_len + 2
    for o in sorted(case.get("overlays") or [], key=lambda o: parse_tc(o.get("tc", "0:00:00"))):
        try:
            t = src_to_clip(rows, parse_tc(o["tc"]))
        except Exception:
            t = None
        if t is None or t > total - 5:
            continue
        t = max(t, busy_until)                       # a moment that was cut lands on the next kept frame: never stack two cards
        d = float(o.get("dur") or 7)
        busy_until = t + d + 2
        ev.append((t, f"TEXT OVERLAY  {mmss(t)}-{mmss(t + d)}   {pos.get(o.get('kind'), 'bottom-left lower third')}  "
                      f"[{o.get('kind', 'fact')}]:  \"{o.get('text', '')}\""))
    cstart = hk_len
    ev.append((cstart + 12, f"SUBSCRIBE CTA  {mmss(cstart + 12)}-{mmss(cstart + 17)}   animated Subscribe button, bottom-right"))
    k = 1
    while cstart + PILL_EVERY * k < total - 45:
        t = cstart + PILL_EVERY * k
        ev.append((t, f"SUBSCRIBE CTA  {mmss(t)}-{mmss(t + 4)}   small 'Subscribe' pill, top-right"))
        k += 1
    fin = (video.get("vo_final") or {}).get("text", "").strip()
    if fin:
        nw = V.n_words(fin)
        ev.append((total, f"VOICE-OVER  after {mmss(total)} (end of the case)   closing narration over a result / end card, "
                          f"~{nw / wps:.0f} s ({nw} words)  -> script below (VO 1)"))
        ev.append((total + nw / wps, "SUBSCRIBE CTA  on the end card   big Subscribe + next video"))
    L += ["TIMELINE", "-" * 72] + [f"{mmss(t):>8}  {line}" for t, line in sorted(ev, key=lambda e: e[0])] + [""]

    L += ["VOICE-OVER SCRIPTS  (paste into TTS as they are)", "-" * 72]
    if fin:
        L += [f"VO 1 - closing narration  (after {mmss(total)}, ~{V.n_words(fin) / wps:.0f} s):", fin, ""]
    if (video.get("vo1") or {}).get("text"):
        L += [f"VO 0 - intro narration  (after the hook, at {mmss(hk_len)}):", video["vo1"]["text"], ""]
    q = video.get("quiz") or {}
    if q.get("question"):
        opts = "   ".join(f"{k}) {v}" for k, v in (q.get("options") or {}).items())
        L += ["QUIZ CARD (optional, before the ruling):", f"  {q['question']}   {opts}   answer: {q.get('answer', '')}", ""]

    L += ["TITLES  (* = upload with this one; swap to #2 at 48 h if CTR < 5%)", "-" * 72]
    for i, t in enumerate(video.get("titles") or [], 1):
        L.append(f"{'*' if t.get('primary') else ' '} {i}. [{t.get('style')}]  {t.get('text')}")
    th = video.get("thumbnail") or {}
    if th:
        L += ["", "THUMBNAIL", "-" * 72, f"text: {th.get('text', '')}    (gold / highlight word: {th.get('gold_word', '')})",
              f"frame: look for {th.get('look_for', 'the strongest reaction')} - candidates: thumbnail_frame_*.jpg in this folder"]
    d = video.get("description") or {}
    if d:
        L += ["", "DESCRIPTION", "-" * 72, d.get("first_line", ""), "", d.get("what_happens", ""), ""]
        if d.get("search_question"):
            L += [d["search_question"], d.get("answer", ""), ""]
        chs = []
        for ch in video.get("chapters") or []:
            try:
                t = 0.0 if not chs else src_to_clip(rows, parse_tc(ch["tc"]))
            except Exception:
                t = None
            if t is not None and (not chs or t > chs[-1][0] + 10):
                chs.append((t, ch.get("label", "")))
        if chs:
            L += ["Chapters:"] + [f"{mmss(t)} {lbl}" for t, lbl in chs] + [""]
        L += [d.get("related_question", ""), "", "Educational content. Not legal advice."]
    if video.get("tags"):
        L += ["", "TAGS", "-" * 72, ", ".join(video["tags"])]
    if video.get("pinned_comment"):
        L += ["", "PINNED COMMENT", "-" * 72, video["pinned_comment"]]

    L += ["", "CUTS MADE  (source times - in case you want something back)", "-" * 72,
          f"hook: source {fmt_tc(rows[0][1], False)}-{fmt_tc(rows[0][2], False)}"]
    L += [f"removed {fmt_tc(a, False)}-{fmt_tc(b, False)}  ({b - a:.0f} s dead air / break)" for a, b in cuts] or ["no dead air removed"]
    return "\n".join(L) + "\n"


def make(plan, video, case, segs, src, folder, cfg, enc, ui=print, source_url=""):
    """Render one clip + its guide into `folder`. -> dict(final, total, qc)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    hook = hook_span(video, case, cfg)
    parts, cuts = case_spans(case, segs, cfg)
    rows, total = build_map(hook, parts)
    removed = sum(b - a for a, b in cuts)
    ui(f"  clip: hook {hook[1] - hook[0]:.0f} s + case {mmss(total - (hook[1] - hook[0]))} "
       f"({len(cuts)} dead-air cut{'s' if len(cuts) != 1 else ''}, {mmss(removed)} removed)")
    final = folder / "clip.mp4"
    cut_clip(src, rows, final, enc, cfg, ui)
    (folder / "EDITOR_GUIDE.txt").write_text(guide(plan, video, case, rows, total, cuts, cfg, source_url), encoding="utf-8")
    th = video.get("thumbnail") or {}
    try:
        wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
    except Exception:
        wa = wb = hook[0] + 3
    frames(src, [wa, (wa + wb) / 2, wb, hook[0] + 2], folder)
    qc = {"ok": final.exists() and final.stat().st_size > 0, "length_s": round(total, 1), "dead_air_removed_s": round(removed, 1),
          "cuts": len(cuts), "kind": "clip"}
    (folder / "qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    return {"final": final, "total": total, "qc": qc}
