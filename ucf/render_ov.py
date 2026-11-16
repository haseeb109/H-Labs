"""OVERRULED skin renderer (same locked structure as Trial Tales, different look).

  1. HOOK      10-15 s teaser, "COMING UP" tag + serif headline slab (no brand bug)
  2. STING     5.5 s seal + wordmark (red/gold panel slides in)
  3. CASE n    Zoom gallery re-staged by tile count (1/2/3/4 tiles, active speaker big, gold corner brackets),
               brand bug, slanted lower-third (case label, "State v. ...", court line), "The Brief" card,
               "Our Take" commentary cards, "The Exchange" Q&A card, thin progress line
  4. OVERVIEW  blurred stage + cream "The Overview" card with the narrated text, AI voice (<=18 s per clip)
  ...
  N. DOCKET    "Today's Docket" results board + big Subscribe box under the closing narration (<=18 s clips), fade out
Subscribe prompts are scheduled automatically (see schedule_subs()).

OVRenderer is also the base of the style-pack looks (Justice Served, Court Beacon): render_video() is a chain of
named steps (_voice, _plan_pieces, stage_clip, _closing_segments, _finish_video, thumbnail) and a subclass overrides
only the graphics module (GFX), the per-run geometry / layer stack and its own overlay scheduling.
"""
import json
from PIL import Image
from pathlib import Path

from . import ov_gfx as G
from . import ov_layout as L
from . import timeline as TL
from .render import AENC, AUDIO_NORM, TS, court_audio, hwdec, probe_dur, run, run_progress, still, venc
from .render_tt import TTRenderer
from .timeutil import fmt_dur, fmt_tc, parse_tc

CASE_LABEL_AT, CASE_LABEL_LEN = 0.6, 7.0
TAKE_LEN, EXCH_LEN = 9.0, 9.0
PILL_EVERY, PILL_LEN, BANNER_LEN, BUTTON_LEN = 360.0, 4.0, 7.0, 5.0


def _short(t, n):
    t = (t or "").strip()
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _crop_png(png, cache={}):
    """-> (path, ox, oy): PNG trimmed to its non-transparent bbox (cuts overlay cost massively)."""
    png = Path(png)
    k = str(png)
    if k in cache:
        return cache[k]
    im = Image.open(png).convert("RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    if not bb:
        bb = (0, 0, 2, 2)
    bb = (bb[0] & ~1, bb[1] & ~1, min(im.width, (bb[2] + 1) & ~1), min(im.height, (bb[3] + 1) & ~1))
    out = png.with_name(png.stem + "_c.png")
    im.crop(bb).save(out)
    cache[k] = (out, bb[0], bb[1])
    return cache[k]


def _merge_static(pngs, out):
    base = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    for q in pngs:
        base = Image.alpha_composite(base, Image.open(q).convert("RGBA"))
    base.save(out)
    return out


class OVRenderer(TTRenderer):
    GFX = G                     # the look's graphics module (HTML -> PNG); a style pack swaps it
    GFX_DIR = "_ov_gfx"         # work_dir subfolder for the generated graphics

    def __init__(self, cfg, sources, root):
        # Renderer base only: the Overruled look has no fleur-de-lis canvas / gavel assets to build
        super(TTRenderer, self).__init__(cfg, sources, root)
        self.bg_logo = self.bg_plain = None
        self.use_hf = False
        self._layout = {}
        self.overlay_cache = {}
        self.gfx = self.GFX
        logo = self._asset("logo_file")
        # ov_gfx always gets the fonts + logo: the generated sting (no channel intro file) is drawn with it
        for mod in ([G] if self.gfx is G else [G, self.gfx]):
            try:
                from .config import style_path
                mod.set_fonts(style_path(cfg, "hf/fonts"))
            except ImportError:
                pass
            mod.set_logo(logo)
        self.gdir = self.root / cfg["work_dir"] / self.GFX_DIR
        self.gdir.mkdir(parents=True, exist_ok=True)
        self._build_canvas()
        self.lfile = self.gdir / "layout_cache.json"
        try:
            self.lcache = json.loads(self.lfile.read_text())
        except (OSError, ValueError):              # no / broken cache: the layouts are measured again
            self.lcache = {}

    def _build_canvas(self):
        """The fixed pictures of the look: background, brand bug, progress line."""
        self.bg = self.gfx.background(self.gdir / "bg")
        self.brand_png = self.gfx.brand(self.gdir / "brand")
        self.prog_png = self.gfx.progress_bar(self.gdir / "progress.png")

    # ------------------------------------------------------------------ layout analysis
    def analyse(self, path, a, b):
        samples = L.sample(path, a, b, self.lcache)
        try:
            self.lfile.write_text(json.dumps(self.lcache))
        except OSError as e:                       # cache only: the next run measures again
            print(f"  layout cache not saved ({e})", flush=True)
        return L.runs(samples, b - a)

    # ------------------------------------------------------------------ generic stage clip
    def stage_clip(self, sname, a, b, out, *, layers=(), blur=False, wav=None, lead=0.0, fade_out=False, prog=None, **opts):
        """Render [a, b) of source `sname` re-staged on the canvas, one encode per Zoom layout run.
        layers  : dicts {png, s, e, fin, fout, slide}   (times relative to a)
        prog    : (f0, f1) progress fractions across this clip
        opts    : look-specific extras, read by _geometry() / _run_layers() (Overruled: brief, brief_first, brand, ticker)"""
        path, a, b = self.locate(sname, a, b)
        d = b - a
        if d <= 0.05:
            raise RuntimeError(f"empty cut {a}-{b}")
        runs = self.analyse(path, a, b)
        outs = []
        for k, (t0, t1, lay, tpl, act) in enumerate(runs):
            dr = t1 - t0
            if dr < 0.1:
                continue
            geo = self._geometry(lay, tpl, act, path, a + t0, opts)
            ls = self._run_layers(geo, (lay, tpl, act), d, layers, blur, opts)
            pr = None
            if prog:
                pr = (prog[0] + (prog[1] - prog[0]) * t0 / d, prog[0] + (prog[1] - prog[0]) * t1 / d)
            f = out if len(runs) == 1 else Path(str(out).replace(".mp4", f"_r{k}.mp4"))
            if not f.exists():
                self._compose_run(path, a + t0, dr, geo, ls, t0, f, blur=blur, wav=wav, lead=lead, wav_t0=t0,
                                  fade_out=fade_out and k == len(runs) - 1, d_total=d, prog=pr)
            outs.append(f)
        if len(runs) > 1:
            lst = Path(str(out).replace(".mp4", "_list.txt"))
            lst.write_text("".join(f"file '{Path(x).resolve()}'\n" for x in outs), encoding="utf-8")
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
        return out

    def _geometry(self, lay, tpl, act, path, t, opts):
        """Where the Zoom tiles land on the canvas for one layout run (path / t: the run's source frame, for looks that probe it)."""
        return L.geometry(lay, tpl, act)

    def _run_layers(self, geo, run, d, layers, blur, opts):
        """The PNG stack of one layout run: frames, brand bug, ticker, the brief card, then the caller's layers."""
        lay, tpl, act = run
        ls = [dict(l) for l in layers]
        if not blur:
            fr = self.gfx.tile_frames(geo["small"], geo["big"], self.gdir / f"fr_{lay}_{act}_{tpl}.png")
            ls.insert(0, dict(png=fr, s=0, e=d))
            if opts.get("brand", True):
                ls.insert(1, dict(png=self.brand_png, s=0, e=d))
            if opts.get("ticker"):
                ls.insert(2, dict(png=opts["ticker"], s=0, e=d))
            self._brief_layer(ls, geo, d, opts)
        return ls

    @staticmethod
    def _brief_layer(ls, geo, d, opts):
        """The side-column card: always on, or (first part of a case) only for the first `brief_first` seconds."""
        brief = opts.get("brief")
        if not brief:
            return
        geom, mode = geo["brief"]
        if mode == "always":
            ls.append(dict(png=brief(geom), s=0, e=d, fin=0.0))
        elif mode == "first" and opts.get("brief_first"):
            ls.append(dict(png=brief(geom), s=0.6, e=opts["brief_first"], fin=0.5, fout=0.5))

    def _compose_run(self, path, a, dr, geo, layers, t0, out, *, blur, wav, lead, wav_t0, fade_out, d_total, prog):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", self.bg,
               "-ss", f"{a:.3f}", "-t", f"{dr:.3f}", *hwdec(), "-i", path]
        nxt = 2
        widx = None
        if wav:
            if wav_t0 > 0.01:
                cmd += ["-ss", f"{max(0.0, wav_t0 - lead):.3f}"]
            cmd += ["-i", wav]
            widx = nxt
            nxt += 1
        fc = [still(0, dr, "bg")]                 # background + layers: decoded and converted once (render.still)
        n = len(geo["tiles"])
        if n == 1:
            fc.append("[1:v]fps=30[t0]")
        else:
            fc.append(f"[1:v]fps=30,split={n}" + "".join(f"[t{i}]" for i in range(n)))
        cur = "bg"
        for i, (src, dst) in enumerate(geo["tiles"]):
            cx, cy, cw, ch = L.cover_crop(src, dst)
            # optional per-style clean-up of soft Zoom footage: footage_pre runs before the upscale (denoise),
            # footage_post after it (sharpen). Both default to "" so other styles render exactly as before.
            pre, post = self.cfg.get("footage_pre") or "", self.cfg.get("footage_post") or ""
            fc.append(f"[t{i}]crop=w='{cw:.2f}*iw/1280':h='{ch:.2f}*ih/720':x='{cx:.2f}*iw/1280':y='{cy:.2f}*ih/720',"
                      + (f"{pre}," if pre else "")
                      + f"scale={dst[2]}:{dst[3]}:flags=lanczos," + (f"{post}," if post else "") + f"setsar=1[c{i}]")
            fc.append(f"[{cur}][c{i}]overlay={dst[0]}:{dst[1]}:eof_action=pass[s{i}]")
            cur = f"s{i}"
        if blur:
            fc.append(f"[{cur}]scale=480:270,gblur=sigma=2.6,scale=1920:1080:flags=bicubic,colorchannelmixer=rr=.55:gg=.55:bb=.55[bl]")
            cur = "bl"
        j = nxt
        static, timed = [], []
        for ly in layers:
            s_, e_ = ly["s"] - t0, ly["e"] - t0
            if e_ <= 0.05 or s_ >= dr:
                continue
            if s_ <= 0.01 and e_ >= dr - 0.01 and not ly.get("slide") and not ly.get("fin") and not ly.get("fout"):
                static.append(ly["png"])
            else:
                timed.append(ly)
        if static:
            import hashlib
            hk = hashlib.md5("|".join(map(str, static)).encode()).hexdigest()[:10]
            mp = Path(self.gdir) / f"static_{hk}.png"
            if not mp.exists():
                _merge_static(static, mp)
            timed.insert(0, dict(s=t0 - 1, e=t0 + dr + 5, png=mp))
        for ly in timed:
            s, e = ly["s"] - t0, ly["e"] - t0
            fin = ly.get("fin", 0.0) if s > 0 else 0.0
            fout = ly.get("fout", 0.0) if ly["e"] <= t0 + dr + 1e-6 and ly["e"] < d_total - 1e-6 else 0.0
            s0, e0 = max(s, 0.0), min(e, dr)
            cp, ox, oy = _crop_png(ly["png"])
            cmd += ["-i", str(cp)]
            chain = still(j, dr, f"st{j}", "yuva420p") + f";[st{j}]null"
            if fin > 0:
                chain += f",fade=t=in:st={s0:.3f}:d={fin:.2f}:alpha=1"
            if fout > 0:
                chain += f",fade=t=out:st={max(s0, e0 - fout):.3f}:d={fout:.2f}:alpha=1"
            fc.append(chain + f"[l{j}]")
            xe = str(ox)
            if ly.get("slide"):
                xe = f"'{ox}-90*max(0,1-(t-{s0:.3f})/0.45)'"
            fc.append(f"[{cur}][l{j}]overlay=x={xe}:y={oy}:format=auto:enable='between(t,{s0:.3f},{e0:.3f})'[o{j}]")
            cur = f"o{j}"
            j += 1
        if prog:
            cmd += ["-i", str(self.prog_png)]
            f0, f1 = prog
            fc.append(still(j, dr, f"st{j}", "yuva420p"))
            fc.append(f"[{cur}][st{j}]overlay=x='-1920+1920*({f0:.5f}+({f1 - f0:.5f})*t/{dr:.3f})':y=1071:format=auto[o{j}]")
            cur = f"o{j}"
            j += 1
        vtail = f",fade=t=out:st={max(0, dr - 0.9):.2f}:d=0.9" if fade_out else ""
        fc.append(f"[{cur}]format=yuv420p{vtail}[vout]")
        if widx is not None:
            ms = int(lead * 1000) if wav_t0 <= 0.01 else 0
            atail = f",afade=t=out:st={max(0, dr - 0.9):.2f}:d=0.9" if fade_out else ""
            fc.append(f"[{widx}:a]adelay={ms}|{ms},apad,{AUDIO_NORM}{atail}[aout]")
            amap = ["-map", "[aout]"]
        else:
            amap = ["-map", "1:a:0?", "-af", court_audio(self.cfg) + (f",afade=t=out:st={max(0, dr - 0.9):.2f}:d=0.9" if fade_out else "")]
        cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", *amap, "-t", f"{dr:.3f}", *venc(self.enc), *AENC, *TS, out]
        if dr > 90:                       # long cut: show progress so it is never mistaken for a hang
            run_progress(cmd, dr, f"    rendering {Path(out).name}")
        else:
            run(cmd)

    # ------------------------------------------------------------------ fixed segments
    def _asset(self, key):
        v = self.cfg.get(key)
        if not v:
            return None
        p = Path(v).expanduser()
        p = p if p.is_absolute() else self.root / p
        return p if p.exists() else None

    def ov_sting(self, out, seconds=5.5):
        intro = self._asset("channel_intro_file")
        if intro:       # the owner's own animated intro (logo + gavel): re-encode to the canvas, keep its sound
            d = probe_dur(intro)
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(intro),
                 "-vf", f"fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
                        f"setsar=1,fade=t=out:st={d - 0.5:.2f}:d=0.5,format=yuv420p",
                 "-af", f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,{AUDIO_NORM},afade=t=out:st={d - 0.5:.2f}:d=0.5",
                 "-t", f"{d:.3f}", *venc(self.enc), *AENC, *TS, out])
            return out
        panel, lock = G.sting_layers(self.gdir)
        extra = self.cfg.get("sting_audio_file")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{seconds}", "-i", self.bg,
               "-loop", "1", "-framerate", "30", "-t", f"{seconds}", "-i", str(panel),
               "-loop", "1", "-framerate", "30", "-t", f"{seconds}", "-i", str(lock)]
        if extra and Path(extra).expanduser().exists():
            cmd += ["-i", str(Path(extra).expanduser())]
            a = "[3:a]atrim=0:%.2f,%s,afade=t=in:d=0.4,afade=t=out:st=%.2f:d=0.8[a]" % (seconds, AUDIO_NORM, seconds - 0.8)
        else:
            cmd += ["-f", "lavfi", "-t", f"{seconds}", "-i", "sine=frequency=165:sample_rate=48000"]
            a = "[3:a]volume=0.10,afade=t=in:d=1.2,afade=t=out:st=%.2f:d=1.6,%s[a]" % (seconds - 1.6, AUDIO_NORM)
        fc = ("[2:v]format=rgba,fade=t=in:st=0.9:d=0.8:alpha=1,fade=t=out:st=%.2f:d=0.6:alpha=1[lk];"
              "[1:v]format=rgba[pn];"
              "[0:v][pn]overlay=x='-700*max(0,1-t/0.7)':y=0:format=auto[b1];"
              "[b1][lk]overlay=0:0:format=auto,fade=t=out:st=%.2f:d=0.6,format=yuv420p[v];%s") % (seconds - 0.6, seconds - 0.6, a)
        run(cmd + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{seconds}", *venc(self.enc), *AENC, *TS, out])
        return out

    def ov_card_clip(self, png, wav, lead, out, fade_out=False):
        dur = probe_dur(wav) + lead + self.cfg["vo_tail"]
        ms = int(lead * 1000)
        vt = f",fade=t=out:st={dur - 0.9:.2f}:d=0.9" if fade_out else ""
        at = f",afade=t=out:st={dur - 0.9:.2f}:d=0.9" if fade_out else ""
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", str(png), "-i", wav,
             "-filter_complex", f"[0:v]scale=1920:1080,setsar=1,format=yuv420p{vt}[v];[1:a]adelay={ms}|{ms},apad,{AUDIO_NORM}{at}[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *venc(self.enc), *AENC, *TS, out])
        return out

    # ------------------------------------------------------------------ plan -> text
    def _case_info(self, plan, c, n):
        cfg = self.cfg
        name = c.get("headline_name") or f"State v. {c['name']}"
        kicker = f"CASE {n} · {(c.get('proceeding') or 'HEARING').upper()}"
        sub = c.get("sub_line") or cfg.get("court_line", "{court} · Bexar County, Texas").replace("{court}", cfg.get("court", "District Court"))
        rows = [("THE DEFENDANT", _short(c.get("defendant_line") or c["name"], 60)),
                ("THE CHARGE", _short(c.get("charge") or "", 70)),
                ("THE QUESTION", _short(c.get("question") or "", 70))]
        return name, kicker, sub, rows

    def schedule_subs(self, case_ranges, total_end, busy):
        """Subscribe prompts on the final timeline (global seconds). case_ranges=[(start,end)] per case; busy=[(s,e)] cards at the bottom."""
        ev = []
        for (cs, ce) in case_ranges:
            ev.append(("button", cs + 12.0, cs + 12.0 + BUTTON_LEN))
        c0, cend = case_ranges[0][0], case_ranges[-1][1]
        k = 1
        while c0 + PILL_EVERY * k < cend - 45:
            t = c0 + PILL_EVERY * k
            ev.append(("pill", t, t + PILL_LEN))
            k += 1
        mid = (c0 + cend) / 2.0
        best = None
        for off in range(-150, 151, 5):
            t = mid + off
            if t < c0 + 60 or t + BANNER_LEN > cend - 40:
                continue
            if not any(cs <= t and t + BANNER_LEN <= ce for cs, ce in case_ranges):
                continue
            if any(t < e + 3 and t + BANNER_LEN > s - 3 for s, e in busy):
                continue
            if any(kind == "pill" and t < e + 8 and t + BANNER_LEN > s - 8 for kind, s, e in ev):
                continue
            if best is None or abs(off) < abs(best - mid):
                best = t
        if best is not None:
            ev.append(("banner", best, best + BANNER_LEN))
        return ev

    # ------------------------------------------------------------------ shared steps of render_video
    def _clip_texts(self, text, n):
        """The narrated text split the same way the voice was (shown on the recap card), or repeated when the counts differ."""
        from . import vo as V
        parts = V.split_clips(text, self.cfg.get("vo_clip_target", 17.0), self.cfg.get("wps", 2.6))
        return parts if len(parts) == n else [text] * n

    def _intro_seconds(self, default):
        """Length of the channel intro: the owner's file when there is one, else the configured sting length."""
        intro = self._asset("channel_intro_file")
        return probe_dur(intro) if intro else float(self.cfg.get("intro_seconds_tt", default))

    def _plan_pieces(self, by_id, ids, gt, srcname, recap_clips):
        """Pre-pass: where every case part and recap lands on the finished timeline. The subscribe schedule and the
        in-case cards need global seconds before anything is rendered.
        -> pieces [dict(cid, i, j, a, b, g0, el, tot, src)], case_ranges [(start, end, case)], recap_plan [[clip seconds]], total_end"""
        cfg = self.cfg
        lead, tail = cfg["vo_lead"], cfg["vo_tail"]
        pieces, case_ranges, recap_plan = [], [], []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            cs = gt
            parts = TL.case_parts(c, cfg["cut_pad_out"])
            tot = sum(b - a for a, b in parts)
            el = 0.0
            for j, (a, b) in enumerate(parts):
                a2 = max(0.0, a - (cfg["cut_pad_in"] if j == 0 else 0))
                pieces.append(dict(cid=cid, i=i, j=j, a=a2, b=b, g0=gt, el=el, tot=tot, src=srcname(c)))
                gt += b - a2
                el += b - a2
            case_ranges.append((cs, gt, c))
            if i < len(ids) - 1:
                ds = [probe_dur(w) + lead + tail for w in recap_clips[cid]]
                recap_plan.append(ds)
                gt += sum(ds)
        return pieces, case_ranges, recap_plan, gt

    def _closing_segments(self, board, final_clips, work, k, seg, last, src):
        """The closing board under every clip of the final narration (the last one fades out). -> (seconds, next k)"""
        lead, tail = self.cfg["vo_lead"], self.cfg["vo_tail"]
        ds = [probe_dur(w) + lead + tail for w in final_clips]
        for q, (w, dq) in enumerate(zip(final_clips, ds)):
            p = work / f"{k:02d}_final_{q}.mp4"
            if not p.exists():
                self.ov_card_clip(board, w, lead, p, fade_out=(q == len(final_clips) - 1))
            seg("vo_final", p, case_id=last["id"], src=src, a=parse_tc(last["out"]), b=parse_tc(last["out"]))
            k += 1
        return sum(ds), k

    def _finish_video(self, plan, video, by_id, outdir, work, segfiles, recap_durs, fin_total, intro_d, recap_clips,
                      final_clips, subs, ui, extra=None):
        """Join the segments, rebuild the timeline from the measured durations, write the footage log -> result dict."""
        cfg = self.cfg
        rows_ = self._timeline_rows(segfiles)
        final = self._join(work, segfiles, outdir, ui)
        real = {"hook": rows_[0]["dur"], "intro": sum(r["dur"] for r in rows_ if r["kind"] == "intro"),
                "recap": recap_durs, "final": fin_total}
        tcfg = dict(TL.DEFAULTS)
        tcfg.update({"cut_pad_out": cfg["cut_pad_out"], "vo_lead": cfg["vo_lead"], "vo_tail": cfg["vo_tail"], "style": "tt",
                     "wps": cfg.get("wps", 2.6), "final_min_hold": cfg.get("final_min_hold", 12.0), "intro_seconds_tt": intro_d})
        tl = TL.build(video, by_id, tcfg, real)
        self._footage_log(video, rows_, plan["source_file"])
        res = {"final": final, "timeline": tl, "rows": rows_, "durs": real, "measured_total": probe_dur(final),
               "work": work, "ai_clips": [round(probe_dur(w), 1) for cl in list(recap_clips.values()) + [final_clips] for w in cl],
               "subscribe": [(kd, round(s, 1), round(e, 1)) for kd, s, e in subs]}
        res.update(extra or {})
        return res

    # ------------------------------------------------------------------ one video
    def render_video(self, plan, video, outdir, tts_cache, ui=print):
        by_id = {c["id"]: c for c in plan["cases"]}
        outdir = Path(outdir)
        work = outdir / "_work"
        work.mkdir(parents=True, exist_ok=True)
        cfg = self.cfg
        ids = video["case_ids"]
        default_src = plan["source_file"]
        lead = cfg["vo_lead"]
        srcname = lambda c: c.get("source_file") or default_src      # noqa: E731
        gf = lambda name: self.gdir / name                              # noqa: E731

        bridges, recap_clips, final_clips = self._voice(video, ids, tts_cache, ui)

        # ---- pre-pass: plan every segment so the subscribe schedule knows the global timeline
        sting_d = self._intro_seconds(5.5)
        hk = video["hook"]
        ha, hb = parse_tc(hk["in"]), parse_tc(hk["out"])
        lead_case = by_id[ids[0]]
        pieces, case_ranges, recap_plan, total_end = self._plan_pieces(by_id, ids, (hb - ha) + sting_d, srcname, recap_clips)
        case_ranges = [(cs, ce) for cs, ce, _ in case_ranges]

        takes = []
        for tk in video.get("takes", []):
            takes.append(("take", parse_tc(tk["tc"]), float(tk.get("dur", TAKE_LEN)), tk))
        for ex in video.get("exchanges", []):
            takes.append(("exchange", parse_tc(ex["tc"]), float(ex.get("dur", EXCH_LEN)), ex))

        def piece_local(tc):
            for pc in pieces:
                if pc["a"] <= tc < pc["b"]:
                    return pc, tc - pc["a"]
            return None, None

        busy = []
        for kind, tc, dur, _ in takes:
            pc, loc = piece_local(tc)
            if pc:
                busy.append((pc["g0"] + loc, pc["g0"] + loc + dur))
        for pc in pieces:
            if pc["j"] == 0:
                busy.append((pc["g0"] + CASE_LABEL_AT, pc["g0"] + CASE_LABEL_LEN))
        subs = self.schedule_subs(case_ranges, total_end, busy)
        self.sub_schedule = subs

        segfiles, seg = self._segments()

        # ----- 1. hook -----
        hp = work / "00_hook.mp4"
        if not hp.exists():
            ui("  hook...")
            lay = [dict(png=G.hook_tag(gf("hook_tag")), s=0.15, e=hb - ha, fin=0.5),
                   dict(png=G.hook_headline(hk["headline"], gf("hook_head")), s=0.35, e=hb - ha, fin=0.5, slide=True)]
            quote = hk.get("quote")
            brief_fn = (lambda geom: G.quote_card("IN THIS REPORT", quote, hk.get("quote_by", "ON THE RECORD"), geom, gf("hook_card"))) if quote else None
            self.stage_clip(srcname(lead_case), ha, hb, hp, layers=lay, brief=brief_fn, brand=False)
        seg("hook", hp, src=srcname(lead_case), a=ha, b=hb)
        # ----- 2. sting -----
        ip = work / "01_intro.mp4"
        if not ip.exists():
            self.ov_sting(ip, sting_d)
        seg("intro", ip)

        # ----- 3.. cases + overviews -----
        k = 2
        recap_durs = []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            sname = srcname(c)
            name, kicker, sub, rows = self._case_info(plan, c, i + 1)
            lt_png = G.lower_third(kicker, name, sub, gf(f"lt_{cid}"))
            tick_png = G.ticker(f"CASE {i + 1}", f"{name}  ·  187th District Court · Bexar County", gf(f"tick_{cid}"))
            brief_fn = lambda geom, rows=rows, i=i, cid=cid: G.brief(f"CASE {i + 1}", rows, geom, gf(f"brief_{cid}"))   # noqa: E731
            for pc in [p for p in pieces if p["cid"] == cid]:
                j = pc["j"]
                p = work / f"{k:02d}_case{cid}_{j}.mp4"
                d = pc["b"] - pc["a"]
                if not p.exists():
                    ui(f"  case {cid} part {j + 1}: {fmt_dur(d)}")
                    lay = []
                    if j == 0:
                        lay.append(dict(png=lt_png, s=CASE_LABEL_AT, e=CASE_LABEL_LEN, fin=0.4, fout=0.4, slide=True))
                    for kind, tc, dur, tk in takes:
                        if not (pc["a"] <= tc < pc["b"]):
                            continue
                        loc = tc - pc["a"]
                        if kind == "take":
                            png = G.take(tk["text"], gf(f"take_{int(tc)}"))
                        else:
                            png = G.exchange(tk.get("ts") or fmt_tc(tc), tk.get("who_q", "PROSECUTOR"), tk["q"], tk.get("who_a", "WITNESS"), tk["a"], gf(f"exch_{int(tc)}"))
                        lay.append(dict(png=png, s=loc, e=min(loc + dur, d), fin=0.5, fout=0.5))
                    for kind, s0, e0 in subs:
                        s, e = max(s0, pc["g0"]), min(e0, pc["g0"] + d)
                        if e - s < 1.0:
                            continue
                        png = {"pill": G.pill, "banner": G.banner, "button": G.corner_button}[kind](gf(f"sub_{kind}"))
                        lay.append(dict(png=png, s=s - pc["g0"], e=e - pc["g0"], fin=0.6, fout=0.6))
                    f0, f1 = pc["el"] / pc["tot"], (pc["el"] + d) / pc["tot"]
                    self.stage_clip(sname, pc["a"], pc["b"], p, layers=lay, brief=brief_fn, brief_first=10.5 if j == 0 else None, ticker=tick_png,
                                    prog=(f0, f1))
                seg("case", p, case_id=cid, src=sname, a=pc["a"], b=pc["b"])
                k += 1
            if i < len(ids) - 1:
                clips = recap_clips[cid]
                ds = recap_plan[i]
                recap_durs.append(sum(ds))
                texts = self._clip_texts(bridges[cid]["text"], len(clips))
                nxt = by_id[ids[i + 1]]
                start = self._vo_start(c, sum(ds))
                off = 0.0
                for q, (w, dq) in enumerate(zip(clips, ds)):
                    p = work / f"{k:02d}_recap{i + 1}_{q}.mp4"
                    if not p.exists():
                        card = G.overview(texts[q], f"CASE {i + 1}", f"Next: {_short(nxt.get('what_it_is') or nxt['name'], 70)}", gf(f"ov_{cid}_{q}"))
                        self.stage_clip(sname, start + off, start + off + dq, p, layers=[dict(png=card, s=0.15, e=dq, fin=0.6)],
                                        blur=True, brand=False, wav=w, lead=lead)
                    seg("recap", p, case_id=cid, src=sname, a=start + off, b=start + off + dq)
                    off += dq
                    k += 1

        # ----- N. closing: docket board + closing narration (<= 18 s clips) -----
        last = by_id[ids[-1]]
        rows = []
        for n_, cid in enumerate(ids, 1):
            c = by_id[cid]
            res = (c.get("result") or {}).get("sentence") or c.get("ends_on") or ""
            rows.append((f"CASE {n_}", f"State v. {c['name']}", _short(res, 38)))
        quiz = video.get("quiz") or {}
        dk = G.docket(rows, quiz.get("question", "Who do you believe?"), quiz.get("options"), gf("docket"))
        fin_total, k = self._closing_segments(dk, final_clips, work, k, seg, last, srcname(last))

        return self._finish_video(plan, video, by_id, outdir, work, segfiles, recap_durs, fin_total, sting_d, recap_clips,
                                  final_clips, subs, ui)

    # ------------------------------------------------------------------ thumbnail
    def _thumb_candidates(self, sname, wa, wb, cdir):
        """Six frames across the thumbnail window, each cropped to the active Zoom tile -> [(sharpness, png)]."""
        import numpy as np
        from . import cards
        cands = []
        n = 6
        for i in range(n):
            t = wa + (wb - wa) * i / max(1, n - 1)
            path, t0, _ = self.locate(sname, t, t + 0.1)
            raw = cdir / f"raw_{i + 1}.png"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", path, "-frames:v", "1",
                 "-vf", f"scale={L.W}:{L.H}", raw])
            rgb = np.asarray(Image.open(raw).convert("RGB"))
            lay, tpl, act, _ = L.classify(rgb)
            geo = L.geometry(lay, tpl, act if act not in (None, 0) or lay not in ("2", "3") else L.DEFAULT_ACTIVE.get(lay, 0))
            x, y, w, h = [int(v) for v in L.cover_crop(geo["tiles"][0][0], (0, 0, 1280, 720), bias=0.1)]
            p = cdir / f"cand_{i + 1}_{fmt_tc(t).replace(':', '-')}.png"
            Image.open(raw).crop((x, y, x + w, y + h)).resize((1280, 720), Image.LANCZOS).save(p)
            cands.append((cards.sharpness(p), p))
        return cands

    def thumbnail(self, plan, video, outdir):
        by_id = {c["id"]: c for c in plan["cases"]}
        th = video["thumbnail"]
        wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
        cid = TL.find_case_for_tc(video, by_id, (wa + wb) / 2) or video["case_ids"][0]
        sname = by_id[cid].get("source_file") or plan["source_file"]
        cdir = Path(outdir) / "thumbnail_candidates"
        cdir.mkdir(parents=True, exist_ok=True)
        best = max(self._thumb_candidates(sname, wa, wb, cdir))[1]
        out = Path(outdir) / "thumbnail.jpg"
        png = self.gfx.thumbnail(best, th.get("text", ""), th.get("gold_word", ""), Path(outdir) / "_work" / "thumb")
        Image.open(png).convert("RGB").save(out, quality=93)
        return out
