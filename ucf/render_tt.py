"""Trial Tales LOCKED editing style (reverse-engineered from youtu.be/kDtxYp0YiMY).

Every output video is built exactly like this:

  1. HOOK       10-15 s teaser cut from the lead case. Dark fleur-de-lis canvas, NO logo, wide footage strip,
                orange "In This Case" label (top-left) + white bottom headline caption.
  2. INTRO      your own 7.5 s gavel animation (assets/channel_intro.mp4) full-frame.
  3. CASE 1     canvas + TrialTales logo permanently top-left, footage strip, lime "CASE STARTED" label.
  4. RECAP      blurred footage strip, deep AI voice (ai33), ONE clip <= 18 s, logo stays.
  5. CASE n     red-bar white-box "2nd Case" / "3rd Case" label on the first seconds.
  ...
  N. CLOSING    blurred strip + AI voice, split into clips <= 18 s each, fade to black.

Canvas is 1920x1080. The stream's two-up gallery (1280x360 band of a 1280x720 frame) is cropped and scaled 1.5x
into a 1920x540 strip at y=270; top/bottom 270 px bands carry the fleur pattern, logo and labels.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from . import cards, hf, tts
from . import timeline as TL
from .render import AENC, AUDIO_NORM, NORM, TS, Renderer, court_audio, probe_dur, run, venc
from .timeutil import fmt_dur, fmt_tc, parse_tc

ASSETS = Path(__file__).resolve().parent.parent / "styles" / "trial_tales" / "assets"   # module default; TTRenderer uses the active style pack
STRIP_Y = 270
LABEL_DELAY = 0.35
LABEL_LEN = 4.2


def _ensure_assets(style_assets):
    if not (style_assets / "bg_logo.png").exists():
        env = {**os.environ, "HL_STYLE_DIR": str(style_assets.parent)}
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "tools" / "make_canvas.py")],
                       check=True, env=env)


OVERLAY_Y = 860          # top of the in-case overlay card (tt look; safe band is y 840-1040)

# ---------------------------------------------------------------- Zoom layouts
# Measured on Boyd streams (2026-10-25) at 64x36 grey: 2up | full3 | grid4 | solo, see classify_layout().
#   2up    court | judge band in the middle, black bars above and below
#   full3  court | judge on top, ONE participant tile centred below (the original 3-tile grid)
#   grid4  2x2: court | judge on top, two participant tiles below (e.g. two lawyers on Zoom)
#   solo   one camera full screen (court room, no judge tile)
LAYOUTS = ("2up", "full3", "grid4", "solo")
_STRIP_FIT = "scale=1920:-2:flags=lanczos,pad=1920:540:0:(540-ih)/2:color=0x121212"
LAYOUT_CHAIN = {
    "2up": "crop=iw:ih/2:0:ih/4,scale=1920:540:flags=lanczos",
    # court | judge (the 3/4 of its tile around her) | the participant tile, side by side to fill the strip
    "full3": ("split=3[{t}a][{t}b][{t}c];[{t}a]crop=iw/2:ih/2:0:0[{t}C];[{t}b]crop=iw*3/8:ih/2:iw*9/16:0[{t}J];"
              "[{t}c]crop=iw/2:ih/2:iw/4:ih/2[{t}W];[{t}C][{t}J][{t}W]hstack=3," + _STRIP_FIT),
    # court | judge | the middle third of each lower tile (where the participant's camera picture sits)
    "grid4": ("split=4[{t}a][{t}b][{t}c][{t}d];[{t}a]crop=iw/2:ih/2:0:0[{t}C];[{t}b]crop=iw*3/8:ih/2:iw*9/16:0[{t}J];"
              "[{t}c]crop=iw/6:ih/2:iw/6:ih/2[{t}P];[{t}d]crop=iw/6:ih/2:iw*2/3:ih/2[{t}Q];"
              "[{t}C][{t}J][{t}P][{t}Q]hstack=4," + _STRIP_FIT),
    "solo": "scale=-2:540:flags=lanczos,pad=1920:540:(1920-iw)/2:0:color=0x121212",
}
# where the judge sits in each layout (crop for the thumbnail): (w, h, x, y) as fractions of the frame
THUMB_CROP = {"2up": "iw/2:ih/2:iw/2:ih/4", "full3": "iw/2:ih/2:iw/2:0", "grid4": "iw/2:ih/2:iw/2:0",
              "solo": "iw:ih:0:0"}
# the court camera tile in each layout (thumbnail face search)
COURT_CROP = {"2up": "iw/2:ih/2:0:ih/4", "full3": "iw/2:ih/2:0:0", "grid4": "iw/2:ih/2:0:0", "solo": "iw:ih:0:0"}


def _gray_frames(args):
    """ffmpeg input args -> (pts list, frames uint8 [n, 36, 64]) of tiny grey frames for layout measurement."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-hide_banner", *args, "-an", "-vf", "scale=64:36,format=gray,showinfo",
                        "-fps_mode", "vfr", "-f", "rawvideo", "-"], capture_output=True)
    pts = [float(x) for x in re.findall(rb"pts_time:([\d.]+)", r.stderr)]
    frames = np.frombuffer(r.stdout, np.uint8)
    frames = frames[: len(frames) // (36 * 64) * 36 * 64].reshape(-1, 36, 64)
    return pts[: len(frames)], frames


def classify_layout(f):
    """One 64x36 grey frame -> layout. Thresholds from 03p3ATnv6dY, N8HQ0Yrk80Q and the Rendon fixtures:
    top band  : 2up has a black bar above the band (mean 0), every grid/solo frame is bright (>150)
    outer cols: full3 has black on both sides of the centred lower tile (0); grid4 / solo show picture (40-80)
    lower mid : grid4 has the black gap between its two lower tiles (0-6); solo shows the room (30+)"""
    top = f[0:7, 3:61].mean()
    if top <= 24:
        return "2up"
    side_l, side_r = f[20:30, 5:15].mean(), f[20:30, 49:59].mean()
    if max(side_l, side_r) < 15:
        return "full3"
    return "grid4" if f[20:30, 29:35].mean() < 12 else "solo"


class TTRenderer(Renderer):
    def __init__(self, cfg, sources, root):
        super().__init__(cfg, sources, root)
        from .config import style_path
        sdir = style_path(cfg)
        sassets = sdir / "assets"
        _ensure_assets(sassets)
        self.bg_logo = sassets / "bg_logo.png"
        self.bg_plain = sassets / "bg_plain.png"
        self.use_hf = bool(cfg.get("use_hyperframes", True)) and hf.available()
        self._layout = {}
        self.overlay_cache = {}

    # ---------- source geometry ----------
    def locate(self, sname, a, b):
        """-> (file, a', b'). A source may be one big file, or a set of pre-cut clips (sources.json "clips")."""
        s = self.src(sname)
        clips = s.get("clips")
        if not clips:
            return s["path"], a, b
        for c in clips:
            if c["in"] - 0.01 <= a and b <= c["out"] + 0.01:
                return c["path"], a - c["in"], b - c["in"]
        raise RuntimeError(f"{sname}: no pre-cut clip covers {a:.1f}-{b:.1f}s - re-run the clip extraction")

    def layout_runs(self, path, a, b):
        """Zoom gallery layouts switch while the hearing runs. Returns [(t0, t1, layout)] in seconds from `a`,
        layout = one of LAYOUTS (see classify_layout). Keyframes only, read as 64x36 grey thumbnails."""
        key = (path, round(a, 1), round(b, 1))
        if key in self._layout:
            return self._layout[key]
        d = b - a
        pts, frames = _gray_frames(["-skip_frame", "nokey", "-ss", f"{a:.2f}", "-t", f"{d:.2f}", "-i", str(path)])
        samples = [(t, classify_layout(f)) for t, f in zip(pts, frames)]
        if not samples:                       # no keyframe inside a short cut: classify the frame at `a` itself
            samples = [(0.0, self.layout_at(path, a))]
        if len(samples) == 1:
            runs = [(0.0, d, samples[0][1])]
        else:
            runs = []
            for k, (t, cl) in enumerate(samples):
                t0 = 0.0 if k == 0 else t
                t1 = d if k == len(samples) - 1 else samples[k + 1][0]
                if runs and runs[-1][2] == cl:
                    runs[-1] = (runs[-1][0], t1, cl)
                else:
                    runs.append((t0, t1, cl))
            changed = True
            while changed and len(runs) > 1:                      # swallow runs shorter than 4 s
                changed = False
                for k, (t0, t1, cl) in enumerate(runs):
                    if t1 - t0 < 4.0 and len(runs) > 1:
                        nb = k - 1 if k > 0 else k + 1
                        lo, hi = min(k, nb), max(k, nb)
                        runs[lo:hi + 1] = [(runs[lo][0], runs[hi][1], runs[nb][2])]
                        changed = True
                        break
        self._layout[key] = runs
        return runs

    def layout_at(self, path, t):
        """Layout of the single frame at t (accurate seek) - for short cuts and thumbnails."""
        _pts, frames = _gray_frames(["-ss", f"{max(0.0, t):.2f}", "-i", str(path), "-frames:v", "1"])
        return classify_layout(frames[0]) if len(frames) else "2up"

    def strip_chain(self, src_label, out_label, runs, tag="st"):
        """filter fragment: [src] -> 1920x540 strip [out]. The 2-up crop is the base; every other layout found in
        `runs` is built on its own branch and overlaid only while that layout is on screen. All crops are fractions
        of the frame, so 360p and 720p downloads give the same picture."""
        base = LAYOUT_CHAIN["2up"]
        others = [cl for cl in LAYOUTS if cl != "2up" and any(r[2] == cl for r in runs)]
        if not others:
            return f"[{src_label}]{base},setsar=1,fps=30[{out_label}]"
        n = len(others) + 1
        parts = [f"[{src_label}]split={n}" + "".join(f"[{tag}s{i}]" for i in range(n)),
                 f"[{tag}s0]{base},setsar=1,fps=30[{tag}L0]"]
        prev = f"{tag}L0"
        for i, cl in enumerate(others, start=1):
            en = "+".join(f"between(t,{t0:.2f},{t1:.2f})" for t0, t1, c in runs if c == cl)
            parts.append(f"[{tag}s{i}]{LAYOUT_CHAIN[cl].format(t=f'{tag}{i}')},setsar=1,fps=30[{tag}L{i}]")
            nxt = out_label if i == len(others) else f"{tag}M{i}"
            parts.append(f"[{prev}][{tag}L{i}]overlay=0:0:enable='{en}'[{nxt}]")
            prev = nxt
        return ";".join(parts)

    # ---------- overlays (HyperFrames -> transparent webm, else static PNG) ----------
    def overlay(self, kind, text, dur, work):
        key = (kind, text, round(dur, 2))
        if key in self.overlay_cache:
            return self.overlay_cache[key]
        res = None
        if self.use_hf:
            try:
                res = hf.render_overlay(kind, text, dur, Path(work) / f"ov_{kind}_{abs(hash(key)) % 10**7}.webm", work, cfg=self.cfg)
            except Exception:
                res = None
            if res is None:
                self.use_hf = False                       # do not retry a broken HyperFrames install every time
        if res is None:
            res = self._static_overlay(kind, text, Path(work) / f"ov_{kind}_{abs(hash(key)) % 10**7}.png")
        self.overlay_cache[key] = res
        return res

    def _static_overlay(self, kind, text, out):
        im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        def box(x, y, h, label, fs, bar_col, bar_w=36, gap=18):
            f = cards.font(fs, True)
            tw = int(d.textlength(label, font=f))
            d.rectangle([x, y, x + bar_w, y + h], fill=bar_col)
            d.rectangle([x + bar_w + gap - 18, y, x + bar_w + gap + tw + 60, y + h], fill="white")
            d.text((x + bar_w + gap + 12, y + h // 2), label, font=f, fill=(10, 10, 10), anchor="lm")

        if kind == "hook":
            box(54, 99, 132, "In This Case", 70, (226, 118, 27))
            box(54, 855, 123, text, 80, (226, 118, 27))
        elif kind == "case_started":
            d.text((375, 130), "CASE STARTED", font=cards.font(124, True), fill=(217, 242, 28), anchor="lm")
        else:
            box(549, 57, 150, text, 96, (179, 32, 42), bar_w=48)
        im.save(out)
        return out

    @staticmethod
    def _ov_input(ov, dur, delay=0.0):
        ov = str(ov)
        off = ["-itsoffset", f"{delay:.2f}"] if delay else []
        if ov.endswith(".webm"):
            return off + ["-c:v", "libvpx-vp9", "-i", ov]
        return off + ["-loop", "1", "-framerate", "30", "-t", f"{dur + delay:.3f}", "-i", ov]

    # ---------- segments ----------
    def tt_cut(self, sname, a, b, out, bg, ov=None, ov_delay=0.0):
        path, a, b = self.locate(sname, a, b)
        d = b - a
        if d <= 0.05:
            raise RuntimeError(f"empty cut {a}-{b}")
        runs = self.layout_runs(path, a, b)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{d:.3f}", "-i", bg,
               "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", path]
        chain = self.strip_chain("1:v", "f", runs) + f";[0:v][f]overlay=0:{STRIP_Y}:eof_action=pass[b]"
        last = "b"
        if ov:
            cmd += self._ov_input(ov, d, ov_delay)
            chain += f";[{last}][2:v]overlay=0:0:eof_action=pass:format=auto[b2]"
            last = "b2"
        chain += f";[{last}]format=yuv420p[vout]"
        cmd += ["-filter_complex", chain, "-map", "[vout]", "-map", "1:a:0?", "-af", court_audio(self.cfg), "-t", f"{d:.3f}",
                *venc(self.enc), *AENC, *TS, out]
        run(cmd)
        return out

    def tt_recap(self, sname, blur_in, dur, wav, lead, out, fade_out=False):
        """Blurred footage strip + AI voice. Original audio is muted so the narrator is clean."""
        path, blur_in, _ = self.locate(sname, max(0.0, blur_in), max(0.0, blur_in) + dur)
        runs = self.layout_runs(path, blur_in, blur_in + dur)
        lead_ms = int(lead * 1000)
        vf_tail = f",fade=t=out:st={dur - 0.9:.2f}:d=0.9" if fade_out else ""
        af_tail = f",afade=t=out:st={dur - 0.9:.2f}:d=0.9" if fade_out else ""
        fc = (self.strip_chain("1:v", "raw", runs) + ";[raw]scale=480:135,gblur=sigma=2.4,scale=1920:540:flags=bicubic[f];"
              f"[0:v][f]overlay=0:{STRIP_Y}:eof_action=pass[b];[b]format=yuv420p{vf_tail}[v];"
              f"[2:a]adelay={lead_ms}|{lead_ms},apad,{AUDIO_NORM}{af_tail}[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", self.bg_logo,
             "-ss", f"{blur_in:.3f}", "-t", f"{dur:.3f}", "-i", path, "-i", wav,
             "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *venc(self.enc), *AENC, *TS, out])
        return out

    def tt_intro(self, out, workdir):
        from .config import rel
        f = rel(self.cfg, "channel_intro_file")
        if not f.is_absolute():
            f = Path(__file__).resolve().parent.parent / f
        if f.exists():
            has_a = "audio" in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)],
                                              capture_output=True, text=True).stdout
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", f]
            if not has_a:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            cmd += ["-filter_complex", f"[0:v]{NORM}[v]", "-map", "[v]", "-map", "0:a:0" if has_a else "1:a:0",
                    "-af", AUDIO_NORM, "-shortest", *venc(self.enc), *AENC, *TS, out]
            run(cmd)
            return out
        return self.channel_intro(7.0, out, workdir)

    # ---------- one video ----------
    def _overlay_card_png(self, kind, text, out_png):
        """v10 in-case value-add card: orange kicker + bar + white box + black text, inside the safe zone."""
        from . import overlay_sched as OS
        from . import cards as C
        look = self.cfg.get("_look") or "tt"
        rect = OS.card_rect(look, text)
        OS.assert_safe(look, rect)
        zx0, zy0, zx1, zy1 = OS.safe_zone(look)
        max_w = zx1 - zx0 - 8
        max_h = zy1 - OVERLAY_Y                    # the card is placed at y=OVERLAY_Y inside the safe band
        measure = ImageDraw.Draw(Image.new("RGBA", (8, 8)))

        def wrap(px, width):
            f = C.font(px)
            lines, cur = [], ""
            for w in text.split():
                t = (cur + " " + w).strip()
                if cur and measure.textlength(t, font=f) > width - 80:
                    lines.append(cur)
                    cur = w
                else:
                    cur = t
            lines.append(cur)
            return f, lines

        # Fit ALL the text in <= 2 lines inside the band: widen first, then shrink the font. (Before, the box
        # was sized from a char-count guess: descenders were cut and a third line was silently dropped.)
        W = rect[2] - rect[0]
        for px in (54, 48, 42, 36):
            for width in (W, max_w):
                f_t, lines = wrap(px, width)
                H = 52 + int(px * 1.25) * len(lines) + 16
                if len(lines) <= 2 and H <= max_h:
                    break
            else:
                continue
            break
        W = min(max_w, max(W, int(max(measure.textlength(ln, font=f_t) for ln in lines)) + 90))
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W - 1, H - 1], fill=(255, 255, 255, 235))
        d.rectangle([0, 0, 36, H - 1], fill=(226, 118, 27, 255))          # orange bar #e2761b
        kicker = OS.KIND_KICKER.get(kind, "FACT").upper()
        d.text((56, 10), kicker, font=C.font(30), fill=(226, 118, 27, 255))
        y = 52
        for ln in lines[:2]:
            d.text((56, y), ln, font=f_t, fill=(15, 15, 18, 255))
            y += int(px * 1.25)
        im.save(out_png)
        return out_png

    def _burn_overlays(self, final, scheduled, workdir, ui=print):
        """Composite scheduled overlay cards onto the joined video (one ffmpeg pass, fades included)."""
        if not scheduled:
            return final
        pngs = []
        for i, (s, e, o) in enumerate(scheduled):
            p = Path(workdir) / f"ov_card_{i:02d}.png"
            self._overlay_card_png(o.get("kind", "fact"), o.get("text", ""), p)
            pngs.append((p, s, e))
        out = final.with_name(final.stem + "_ov.mp4")
        # -loop 1: a PNG input is ONE frame at t=0; the fade-in then never starts and ffmpeg repeats that fully
        # transparent frame, so every card was invisible (found on 03p3ATnv6dY, 2026-10-25).
        inp = ["-i", str(final)] + sum([["-loop", "1", "-t", f"{e + 1:.2f}", "-i", str(p)] for p, _s, e in pngs], [])
        fc, prev = [], "0:v"
        for i, (p, s, e) in enumerate(pngs):
            k = i + 1
            fc.append(f"[{k}:v]format=rgba,fade=in:st={s:.2f}:d=0.5:alpha=1,fade=out:st={max(s, e - 0.5):.2f}:d=0.5:alpha=1[ov{i}]")
            fc.append(f"[{prev}][ov{i}]overlay=x=54:y={OVERLAY_Y}:enable='between(t,{s:.2f},{e:.2f})'[v{i}]")
            prev = f"v{i}"
        run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-filter_complex", ";".join(fc),
             "-map", f"[{prev}]", "-map", "0:a?", *venc(self.enc), *AENC, "-movflags", "+faststart", out])
        if out.exists() and out.stat().st_size > 1000:
            final.unlink(missing_ok=True)
            out.rename(final)
            ui(f"  overlays burned: {len(pngs)}")
        return final

    def render_video(self, plan, video, outdir, tts_cache, ui=print):
        by_id = {c["id"]: c for c in plan["cases"]}
        outdir = Path(outdir)
        work = outdir / "_work"
        work.mkdir(parents=True, exist_ok=True)
        cfg = self.cfg
        ids = video["case_ids"]
        default_src = plan["source_file"]
        lead, tail = cfg["vo_lead"], cfg["vo_tail"]
        srcname = lambda c: c.get("source_file") or default_src      # noqa: E731

        # ----- AI voice clips (every clip <= 18 s) -----
        ui("  voiceover (clips <= 18 s)...")
        bridges = {b["after_case_id"]: b for b in video.get("bridges", [])}
        recap_clips = {}
        for i in range(len(ids) - 1):
            recap_clips[ids[i]] = tts.synth_clips(bridges[ids[i]]["text"], tts_cache, cfg, ui)
        final_clips = tts.synth_clips(video["vo_final"]["text"], tts_cache, cfg, ui)
        for cl in list(recap_clips.values()) + [final_clips]:
            for w in cl:
                assert probe_dur(w) <= cfg.get("vo_clip_max", 18.0) + 0.05, f"AI clip over limit: {w}"

        segfiles = []

        def seg(kind, path, **meta):
            segfiles.append((kind, Path(path), meta))

        # ----- 1. hook -----
        lead_case = by_id[ids[0]]
        hk = video["hook"]
        ha, hb = parse_tc(hk["in"]), parse_tc(hk["out"])
        p = work / "00_hook.mp4"
        if not p.exists():
            ui("  hook overlay + cut...")
            ov = self.overlay("hook", hk["headline"], hb - ha, work)
            self.tt_cut(srcname(lead_case), ha, hb, p, self.bg_plain, ov, 0.15)
        seg("hook", p, src=srcname(lead_case), a=ha, b=hb)
        # ----- 2. channel intro -----
        p = work / "01_intro.mp4"
        if not p.exists():
            self.tt_intro(p, work)
        seg("intro", p)

        # ----- 3.. cases + recaps -----
        k = 2
        recap_durs = []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            sname = srcname(c)
            for j, (a, b) in enumerate(TL.case_parts(c, cfg["cut_pad_out"])):
                a2 = max(0.0, a - (cfg["cut_pad_in"] if j == 0 else 0))
                p = work / f"{k:02d}_case{cid}_{j}.mp4"
                if not p.exists():
                    ui(f"  case {cid} part {j + 1}: {fmt_dur(b - a2)}")
                    ov = None
                    if j == 0:
                        kind, text = ("case_started", "") if i == 0 else ("nth", f"{hf.ordinal(i + 1)} Case")
                        ov = self.overlay(kind, text, LABEL_LEN, work)
                    self.tt_cut(sname, a2, b, p, self.bg_logo, ov, LABEL_DELAY)
                seg("case", p, case_id=cid, src=sname, a=a2, b=b)
                k += 1
            if i < len(ids) - 1:
                clips = recap_clips[cid]
                ds = [probe_dur(w) + lead + tail for w in clips]
                recap_durs.append(sum(ds))
                start = max(TL.case_parts(c, cfg["cut_pad_out"])[-1][0], parse_tc(c["out"]) - sum(ds) - 2.0)
                off = 0.0
                for q, (w, dq) in enumerate(zip(clips, ds)):
                    p = work / f"{k:02d}_recap{i + 1}_{q}.mp4"
                    if not p.exists():
                        self.tt_recap(sname, start + off, dq, w, lead, p)
                    seg("recap", p, case_id=cid, src=sname, a=start + off, b=start + off + dq)
                    off += dq
                    k += 1

        # ----- N. closing recap (clips <= 18 s, fade to black) -----
        last = by_id[ids[-1]]
        ds = [probe_dur(w) + lead + tail for w in final_clips]
        fin_total = sum(ds)
        start = max(TL.case_parts(last, cfg["cut_pad_out"])[-1][0], parse_tc(last["out"]) - fin_total - 2.0)
        off = 0.0
        for q, (w, dq) in enumerate(zip(final_clips, ds)):
            p = work / f"{k:02d}_final_{q}.mp4"
            if not p.exists():
                self.tt_recap(srcname(last), start + off, dq, w, lead, p, fade_out=(q == len(final_clips) - 1))
            seg("vo_final", p, case_id=ids[-1], src=srcname(last), a=start + off, b=start + off + dq)
            off += dq
            k += 1

        # ----- real timeline -----
        t = 0.0
        rows = []
        for kind, path, meta in segfiles:
            d = probe_dur(path)
            rows.append({"kind": kind, "start": t, "dur": d, **meta})
            t += d

        ui("  joining + loudness...")
        lst = work / "concat.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for _, p, _ in segfiles), encoding="utf-8")
        final = outdir / "video.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy",
             "-af", f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11", *AENC, "-movflags", "+faststart", final])

        real = {"hook": rows[0]["dur"], "intro": rows[1]["dur"], "recap": recap_durs, "final": fin_total}
        tcfg = dict(TL.DEFAULTS)
        tcfg.update({"cut_pad_out": cfg["cut_pad_out"], "vo_lead": lead, "vo_tail": tail, "style": "tt",
                     "wps": cfg.get("wps", 2.6), "final_min_hold": cfg.get("final_min_hold", 12.0)})
        tl = TL.build(video, by_id, tcfg, real)
        # v10 overlays: schedule inside cases, burn before QC
        scheduled = []
        try:
            from . import overlay_sched as OS
            if (self.cfg.get("overlays") or {}).get("enabled", True):
                total = probe_dur(final)
                busy = [(r["start"] + 0.3, r["start"] + 4.7) for r in rows if r["kind"] == "case"][:1]
                for cid in video["case_ids"]:
                    c = by_id[cid]
                    scheduled += OS.schedule(c, lambda tc, cid=cid: TL.src_to_out(tl, cid, tc), total, busy,
                                             self.cfg, look=self.cfg.get("_look") or "tt")
                if scheduled:
                    ui(f"  overlays scheduled: {len(scheduled)}")
                    final = self._burn_overlays(final, scheduled, outdir / "_work", ui)
                    rows.append({"kind": "overlay", "start": scheduled[0][0], "dur": scheduled[0][1] - scheduled[0][0],
                                 "a": 0, "b": 0, "src": "", "label": "overlays"})
                    video["_overlays_scheduled"] = [[round(s, 2), round(e, 2), o.get("kind"), o.get("text")]
                                                    for s, e, o in scheduled]
        except Exception as ex:  # noqa
            ui("  overlays skipped:", ex)
        # word-by-word captions in the band under the strip; never over the hook/intro or an overlay card
        try:
            from . import captions as CAP
            blocks = [(r["start"], r["start"] + r["dur"]) for r in rows if r["kind"] in ("hook", "intro")]
            blocks += [(s - 0.3, e + 0.3) for s, e, _o in scheduled]
            final = CAP.burn(final, blocks, work, self.cfg, venc(self.enc), ui)
        except Exception as ex:  # noqa - captions are a bonus layer, never a reason to lose the video
            ui("  captions skipped:", ex)
        for r in rows:
            s = self.sources.get(r.get("src", default_src)) or {}
            url = s.get("url", "")
            self.log.append({"video": video["n"], "segment": r["kind"], "case_id": r.get("case_id", ""),
                             "source_file": r.get("src", ""), "source_url": (url + ("&" if "?" in url else "?") + f"t={int(r['a'])}s") if url and "a" in r else url,
                             "src_in": fmt_tc(r["a"]) if "a" in r else "", "src_out": fmt_tc(r["b"]) if "b" in r else "",
                             "out_start": fmt_tc(r["start"]), "out_dur": f"{r['dur']:.1f}"})
        return {"final": final, "timeline": tl, "rows": rows, "durs": real, "measured_total": probe_dur(final),
                "work": work, "ai_clips": [round(probe_dur(w), 1) for cl in list(recap_clips.values()) + [final_clips] for w in cl]}


def _thumb(self, plan, video, outdir):
    from .timeutil import fmt_tc as _f
    by_id = {c["id"]: c for c in plan["cases"]}
    th = video["thumbnail"]
    wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
    cid = TL.find_case_for_tc(video, by_id, (wa + wb) / 2) or video["case_ids"][0]
    sname = by_id[cid].get("source_file") or plan["source_file"]
    cdir = Path(outdir) / "thumbnail_candidates"
    cdir.mkdir(parents=True, exist_ok=True)
    from . import faces as FC
    from PIL import Image
    min_face = int(self.cfg.get("thumb_min_face_px", 90))     # smaller court-camera faces upscale into mush
    cands = []                                                # (score, path, faces)

    def add(p):
        fs = FC.detect(p)
        # a big, confident face lifts a candidate; no face at all halves it (sharpness alone picked blank walls)
        fw = min(1.0, fs[0]["h"] * 2.2) * fs[0]["score"] if fs else 0.0
        cands.append((cards.sharpness(p) * (0.5 + fw), p, fs))

    n = 6
    for i in range(n):
        t = wa + (wb - wa) * i / max(1, n - 1)
        path, t0, _ = self.locate(sname, t, t + 0.1)
        stamp = _f(t).replace(':', '-')
        layout = self.layout_at(path, t0)
        # 1) the judge's tile; where it sits depends on the Zoom layout of that very frame
        p = cdir / f"cand_{i + 1}_{stamp}.jpg"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", path, "-frames:v", "1",
             "-vf", f"crop={THUMB_CROP[layout]},scale=1280:720:flags=lanczos", "-q:v", "2", p])
        add(p)
        # 2) the court camera, cropped onto the biggest face (usually the defendant) when it is big enough
        if FC.available():
            tile = cdir / f"court_{i + 1}_{stamp}.png"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", path, "-frames:v", "1",
                 "-vf", f"crop={COURT_CROP[layout]}", tile])
            fs = FC.detect(tile)
            if fs:
                im = Image.open(tile)
                if fs[0]["h"] * im.height >= min_face:
                    x0, y0, w, h = FC.face_crop_box(fs[0], im.width, im.height)
                    q = cdir / f"cand_{i + 1}_{stamp}_face.jpg"
                    im.crop((x0, y0, x0 + w, y0 + h)).convert("RGB").resize((1280, 720), Image.LANCZOS).save(q, quality=92)
                    add(q)
            tile.unlink(missing_ok=True)
    _score, best, best_faces = max(cands, key=lambda c: c[0])
    out = Path(outdir) / "thumbnail.jpg"
    cards.thumbnail(best, th["text"], th["gold_word"], FC.text_placement(best_faces, th["placement"]), out)
    for _s, p, fs in cands:
        cards.thumbnail(p, th["text"], th["gold_word"], FC.text_placement(fs, th["placement"]),
                        p.with_name(p.stem + "_text.jpg"))
    return out


TTRenderer.thumbnail = _thumb
