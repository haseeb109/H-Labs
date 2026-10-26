"""COURT BEACON TV look renderer (lives in the style pack: styles/court_beacon/engine/) - "cinema + evidence board" (approved style v2, Oct 2026).

Same locked structure as every H Labs style:
  1. HOOK        10-15 s teaser from the lead case: cinema letterbox, "FROM THE COURT RECORD", typed headline
  2. INTRO       the owner's 10 s Court Beacon animation (styles/court_beacon/assets/channel_intro.mp4), its own sound
  3. CASE n      first 4 s: EVIDENCE BOARD insert - the live footage keeps playing inside a taped polaroid, case data
                 and an OPEN stamp. Then the CINEMA layout: active Zoom tile full width (y 64-928), top bar with logo,
                 case label and hearing steps (CALLED > PLEA > TESTIMONY > RULING > CLOSED, driven by case.phases),
                 other Zoom tiles as small monitors in the bottom strip, and every text overlay ONLY in the bottom strip:
                   KEY FACT (big orange number), SO FAR (3 beats), YOUR VERDICT, ON THE RECORD (video.exchanges, Q then A),
                   WATCH (orange corner brackets + tag).  "Coming up" teasers are NOT used in this look (owner decision).
  4. BRIEFING    bundle modes only: blurred footage + three polaroids + narrated text (AI voice, <= 18 s clips)
  N. CASE FILES  polaroid wall of every case with its outcome stamp + YOUR VERDICT quiz + Subscribe, under vo_final
Subscribe: corner button at each case start + 12 s, SUBSCRIBE NOW pill in the top bar every ~6 min, one full-strip
bell banner mid-video, button on every Briefing card, the spoken line in vo_final, the big box on the closing board.
"""
import json
import re
from pathlib import Path

import importlib.util
import sys

import numpy as np
from PIL import Image

from ucf import ov_layout as L
from ucf import timeline as TL
from ucf import tts
from ucf.render import probe_dur, run
from ucf.render_ov import OVRenderer, _short
from ucf.timeutil import fmt_dur, fmt_tc, parse_tc


def _sibling(name):
    """Load a module that lives next to this file (the style pack ships its own engine; no ucf/ changes)."""
    key = f"court_beacon_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


CG = _sibling("cb_gfx")

OPEN_LEN = 4.0                      # evidence-board insert at the start of every case
ITEM_GAP = 20.0                     # seconds kept free between two strip items
HEAD_SKIP, TAIL_SKIP = 40.0, 30.0   # no overlays in the first 40 s / last 30 s of a case
FACT_LEN, EXCH_LEN = 7.0, 9.0
KINDS = ("fact", "so_far", "watch", "verdict_q")       # "coming_up" is never drawn in this look
STEP_BY_PHASE = CG.PHASE_STEP


def _face_crop(src, dst, face):
    """Largest sub-rect of src (1280-space) with dst's aspect, centred on the face (x) with the eyes ~35% from the top."""
    x, y, w, h = src
    aw = dst[2] / dst[3]
    if w / h > aw:
        cw, ch = h * aw, h
    else:
        cw, ch = w, w / aw
    if face:
        fx, fy = x + face[1] * w, y + face[2] * h
        cx = min(max(x, fx - cw / 2), x + w - cw)
        cy = min(max(y, fy - ch * 0.35), y + h - ch)
    else:
        cx, cy = x + (w - cw) / 2, y + (h - ch) * 0.2
    return (cx, cy, cw, ch)


def cb_geometry(layout, template, active, mode="case", finfo=None):
    """-> dict(tiles=[(src_rect_1280, dst_rect)], big, small, labels, side).  mode: case | hook | open.
    finfo: per tile (face_score, cx, cy) from analyse() or None.
    CASE layouts:  TWO-SHOT when a second person is on screen (the judge tile, or any other tile with a face):
                   main person 1268x864 left, judge 640x480 top right, courtroom 640x372 below it (or brand panel).
                   FULL otherwise: main person full width, other tiles as small monitors in the strip."""
    rects = [(x + 6, y + 6, w - 12, h - 12) for x, y, w, h in L.TEMPLATES[template]]    # inside Zoom's green ring
    n = len(rects)
    act = active if active is not None and active < n else L.DEFAULT_ACTIVE.get(layout, 0)
    face = lambda i: (finfo[i] if finfo and i < len(finfo) and finfo[i] and finfo[i][0] > 0 else None)  # noqa: E731
    if mode == "hook":
        return dict(tiles=[(_face_crop(rects[act], CG.HOOK_RECT, face(act)), CG.HOOK_RECT)], big=CG.HOOK_RECT, small=[], labels=[], side=None)
    if mode == "open":
        return dict(tiles=[(_face_crop(rects[act], CG.POLAROID_HOLE, face(act)), CG.POLAROID_HOLE)], big=CG.POLAROID_HOLE, small=[], labels=[], side=None)
    others = [i for i in range(n) if i != act]
    judge = 1 if template in ("3", "3w") and act != 1 else None
    people = [i for i in others if face(i)]
    top = judge if judge is not None else (max(people, key=lambda i: face(i)[0]) if people else None)
    if top is not None:
        rest = [i for i in others if i != top]
        bot = rest[0] if rest else None
        tiles = [(_face_crop(rects[act], CG.MAIN2, face(act)), CG.MAIN2), (_face_crop(rects[top], CG.SIDE_TOP, face(top)), CG.SIDE_TOP)]
        if bot is not None:
            tiles.append((_face_crop(rects[bot], CG.SIDE_BOT, face(bot)), CG.SIDE_BOT))
        side = [_tile_label(template, top), _tile_label(template, bot) if bot is not None else None]
        return dict(tiles=tiles, big=CG.MAIN2, small=[], labels=[], side=side)
    others = others[:2]
    small = CG.thumb_rects(len(others))
    tiles = [(_face_crop(rects[act], CG.CINEMA, face(act)), CG.CINEMA)] + [(_face_crop(rects[i], r, face(i)), r) for i, r in zip(others, small)]
    return dict(tiles=tiles, big=CG.CINEMA, small=small, labels=[_tile_label(template, i) for i in others], side=None)


def _tile_label(template, i):
    if template in ("3", "3w"):
        return ["COURT", "JUDGE", "ON THE STAND"][i]
    if template == "2":
        return ["COURT", "ON THE STAND"][i]
    return f"VIEW {i + 1}"


class CBRenderer(OVRenderer):
    def __init__(self, cfg, sources, root):
        super().__init__(cfg, sources, root)          # Overruled plumbing: compose engine, intro file, layout cache
        try:
            from ucf.config import style_path
            CG.set_fonts(style_path(cfg, "hf/fonts"))
        except ImportError:
            pass
        CG.set_logo(self._asset("logo_file"))
        self.gdir = self.root / cfg["work_dir"] / "_cb_gfx"
        self.gdir.mkdir(parents=True, exist_ok=True)
        self.bg = CG.background(self.gdir / "bg")
        self.lfile = self.gdir / "layout_cache.json"
        try:
            self.lcache = json.loads(self.lfile.read_text())
        except Exception:
            self.lcache = {}

    # ------------------------------------------------------------------ staging
    def stage_clip(self, sname, a, b, out, *, layers=(), mode="case", static=(), blur=False, wav=None, lead=0.0,
                   fade_out=False, **_ignored):
        """Render [a, b) of `sname` on the Court Beacon canvas. layers: {png, s, e, fin, fout, slide} (times relative to a);
        static: PNGs shown for the whole clip (top bar ...). Zoom layout changes inside the clip are handled per run."""
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
            geo = cb_geometry(lay, tpl, act, mode, self._finfo.get((path, round(a + t0, 1))))
            ls = []
            if not blur:
                if mode == "case" and geo.get("side"):
                    ls.append(dict(png=CG.frame_two(geo["side"], self.gdir / f"frame2_{'_'.join(str(x) for x in geo['side'])}"), s=0, e=d))
                elif mode == "case":
                    ls.append(dict(png=CG.frame(len(geo["small"]), geo["labels"], self.gdir / f"frame_{len(geo['small'])}_{'_'.join(geo['labels'])}"), s=0, e=d))
                for sp in static:
                    ls.append(dict(png=sp, s=0, e=d))
            for l in layers:
                l = dict(l)
                if "watch" in l:          # brackets follow the main picture of this layout run
                    l["png"] = CG.watch(l.pop("watch"), self.gdir / "watch", rect=geo["big"])
                ls.append(l)
            f = out if len(runs) == 1 else Path(str(out).replace(".mp4", f"_r{k}.mp4"))
            if not f.exists():
                self._compose_run(path, a + t0, dr, geo, ls, t0, f, blur=blur, wav=wav, lead=lead, wav_t0=t0,
                                  fade_out=fade_out and k == len(runs) - 1, d_total=d, prog=None)
            outs.append(f)
        if len(outs) > 1:
            lst = Path(str(out).replace(".mp4", "_list.txt"))
            lst.write_text("".join(f"file '{Path(x).resolve()}'\n" for x in outs), encoding="utf-8")
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
        return out

    # ------------------------------------------------------------------ who is big: the tile with the person in it
    def _person_scores(self, im, tpl):
        """Face size x confidence per tile of a 1280x720 PIL frame (MediaPipe via ucf.faces). [] if unavailable.
        Zoom's green ring and 'tile 0 = court wide shot' guess wrong on in-person hearings (the defendant stands in
        the court tile while the witness tile shows an empty chair), so the face decides when it can."""
        return [f[0] for f in self._face_info(im, tpl)]

    def _face_info(self, im, tpl):
        """-> [(score, cx, cy)] per tile (cx/cy = biggest face centre as fractions of the tile), [] if unavailable."""
        try:
            from ucf import faces as FC
            if not FC.available():
                return []
        except Exception:
            return []
        out = []
        for i, (x, y, w, h) in enumerate(L.TEMPLATES[tpl]):
            p = self.gdir / f"_face_probe_{i}.png"
            ix, iy, iw, ih = x + 4, y + 4, w - 8, h - 38
            im.crop((ix, iy, ix + iw, iy + ih)).save(p)
            fs = FC.detect(p)
            if not fs:
                out.append((0.0, 0.5, 0.4))
                continue
            f = fs[0]
            v = f["w"] * f["h"] * f["score"]
            if tpl in ("3", "3w") and i == 1:
                v *= 0.3          # the judge's own tile: the witness / defendant is the story, the judge is the side picture
            cx = (4 + (f["x"] + f["w"] / 2) * iw) / w
            cy = (4 + (f["y"] + f["h"] / 2) * ih) / h
            out.append((v, cx, cy))
        return out

    def analyse(self, path, a, b):
        """Zoom layout runs (shared detector) + per run: who is big (faces) and where each face sits (for the crops)."""
        runs = super().analyse(path, a, b)
        out = []
        self._finfo = getattr(self, "_finfo", {})
        for (t0, t1, lay, tpl, act) in runs:
            finfo = None
            if lay in ("1", "2", "3", "4"):
                key = f"cbface2|{path}|{a + t0:.1f}|{a + t1:.1f}"
                if key not in self.lcache:
                    rec = None
                    try:
                        probe = self.gdir / "_probe.png"
                        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a + (t0 + t1) / 2:.2f}", "-i", str(path),
                             "-frames:v", "1", "-vf", f"scale={L.W}:{L.H}", probe])
                        fi = self._face_info(Image.open(probe).convert("RGB"), tpl)
                        if fi:
                            best = int(np.argmax([f[0] for f in fi])) if max(f[0] for f in fi) > 0 else None
                            rec = {"act": best, "faces": fi}
                    except Exception:
                        rec = None
                    self.lcache[key] = rec
                    try:
                        self.lfile.write_text(json.dumps(self.lcache))
                    except Exception:
                        pass
                rec = self.lcache[key]
                if rec:
                    if rec.get("act") is not None and len(L.TEMPLATES[tpl]) > 1:
                        act = rec["act"]
                    finfo = rec.get("faces")
            self._finfo[(path, round(a + t0, 1))] = finfo
            out.append((t0, t1, lay, tpl, act))
        return out

    # ------------------------------------------------------------------ frames from the source (polaroids, thumbnail)
    def grab(self, sname, t, out):
        path, t0, _ = self.locate(sname, t, t + 0.1)
        out = Path(out)
        if not out.exists():
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", path, "-frames:v", "1",
                 "-vf", f"scale={L.W}:{L.H}", out])
        return out

    def tile_crops(self, raw, prefix, aspect=(16, 9)):
        """Crop every Zoom tile of a raw 1280x720 frame -> [(png, role)] active first."""
        im = Image.open(raw).convert("RGB")
        lay, tpl, act, _ = L.classify(np.asarray(im))
        rects = L.TEMPLATES[tpl]
        act = act if act is not None and act < len(rects) else L.DEFAULT_ACTIVE.get(lay, 0)
        sc = self._person_scores(im, tpl) if len(rects) > 1 else []
        if sc and max(sc) > 0:
            act = int(np.argmax(sc))
        order = [act] + [i for i in range(len(rects)) if i != act]
        out = []
        for i in order:
            x, y, w, h = rects[i]
            ix, iy, iw, ih = x + 4, y + 4, w - 8, h - 38            # inside the green ring, above the Zoom name label
            cw, ch = (iw, int(iw * aspect[1] / aspect[0])) if iw * aspect[1] / aspect[0] <= ih else (int(ih * aspect[0] / aspect[1]), ih)
            cx = ix + (iw - cw) // 2
            cy = iy + int((ih - ch) * 0.2)
            p = Path(f"{prefix}_{i}.png")
            im.crop((cx, cy, cx + cw, cy + ch)).resize((800, 450), Image.LANCZOS).save(p)
            out.append((p, _tile_label(tpl, i)))
        return out

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _steps(c):
        """[(stream_tc, step_index)] from case.phases, sorted; [] when the plan has no phases."""
        out = []
        for ph in c.get("phases") or []:
            st = STEP_BY_PHASE.get(ph.get("phase"))
            try:
                out.append((parse_tc(ph["tc"]), st))
            except Exception:
                continue
        return sorted([x for x in out if x[1] is not None])

    def _case_rows(self, c):
        return [("CHARGE", _short(c.get("charge") or "", 46)), ("FACING", _short(c.get("facing") or "", 46)),
                ("HEARING", _short((c.get("proceeding") or c.get("what_it_is") or "").capitalize(), 46)),
                ("COURT", "187th District, Judge Boyd")]

    # ------------------------------------------------------------------ one video
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
        gf = lambda name: self.gdir / name                              # noqa: E731

        ui("  voiceover (clips <= 18 s)...")
        bridges = {b["after_case_id"]: b for b in video.get("bridges", [])}
        recap_clips = {}
        for i in range(len(ids) - 1):
            recap_clips[ids[i]] = tts.synth_clips(bridges[ids[i]]["text"], tts_cache, cfg, ui)
        final_clips = tts.synth_clips(video["vo_final"]["text"], tts_cache, cfg, ui)
        for cl in list(recap_clips.values()) + [final_clips]:
            for w in cl:
                assert probe_dur(w) <= cfg.get("vo_clip_max", 18.0) + 0.05, f"AI clip over limit: {w}"
        from ucf import vo as V

        def clip_texts(text, n):
            parts = V.split_clips(text, cfg.get("vo_clip_target", 17.0), cfg.get("wps", 2.6))
            return parts if len(parts) == n else [text] * n

        # ---- pre-pass: global timeline (subscribe schedule needs it)
        intro_file = self._asset("channel_intro_file")
        intro_d = probe_dur(intro_file) if intro_file else float(cfg.get("intro_seconds_tt", 10.0))
        hk = video["hook"]
        ha, hb = parse_tc(hk["in"]), parse_tc(hk["out"])
        lead_case = by_id[ids[0]]
        gt = (hb - ha) + intro_d
        pieces, case_ranges, recap_plan = [], [], []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            cs = gt
            parts = TL.case_parts(c, cfg["cut_pad_out"])
            for j, (a, b) in enumerate(parts):
                a2 = max(0.0, a - (cfg["cut_pad_in"] if j == 0 else 0))
                pieces.append(dict(cid=cid, i=i, j=j, a=a2, b=b, g0=gt, src=srcname(c)))
                gt += b - a2
            case_ranges.append((cs, gt, c))
            if i < len(ids) - 1:
                ds = [probe_dur(w) + lead + tail for w in recap_clips[cid]]
                recap_plan.append(ds)
                gt += sum(ds)
        total_end = gt

        def piece_of(tc):
            for pc in pieces:
                if pc["a"] <= tc < pc["b"]:
                    return pc
            return None

        # ---- strip items per case: overlays (fact/so_far/verdict_q/watch) + exchanges (ON THE RECORD)
        items = []        # (global_start, global_end, kind, payload, pc)
        exch = list(video.get("exchanges") or [])
        for cs, ce, c in case_ranges:
            cand = []
            for o in c.get("overlays") or []:
                if o.get("kind") not in KINDS or not o.get("text"):
                    continue
                try:
                    cand.append((parse_tc(o["tc"]), float(o.get("dur") or FACT_LEN), o["kind"], o))
                except Exception:
                    continue
            for ex in exch:
                try:
                    tc = parse_tc(ex["tc"])
                except Exception:
                    continue
                if parse_tc(c["in"]) <= tc < parse_tc(c["out"]):
                    cand.append((tc, float(ex.get("dur") or EXCH_LEN), "record", ex))
            for tc, dur, kind, o in sorted(cand, key=lambda x: x[0]):
                pc = piece_of(tc)
                if not pc:
                    continue
                g = pc["g0"] + (tc - pc["a"])
                if g < cs + HEAD_SKIP or g + dur > ce - TAIL_SKIP:
                    continue
                if kind != "watch" and any(not (g + dur + ITEM_GAP <= s or g >= e + ITEM_GAP) for s, e, k2, _, _ in items if k2 != "watch"):
                    continue
                items.append((g, g + dur, kind, o, pc))
        busy = [(s, e) for s, e, k, _, _ in items if k != "watch"] + [(cs, cs + OPEN_LEN + 1) for cs, _, _ in case_ranges]
        subs = self.schedule_subs([(cs, ce) for cs, ce, _ in case_ranges], total_end, busy)
        self.sub_schedule = subs

        segfiles = []

        def seg(kind, path, **meta):
            segfiles.append((kind, Path(path), meta))

        # ----- 1. hook
        hp = work / "00_hook.mp4"
        if not hp.exists():
            ui("  hook...")
            meta = f"BEXAR COUNTY, TEXAS · {fmt_tc(ha)}"
            hl = CG.hook(hk.get("headline") or "", "FROM THE COURT RECORD", meta, f"THE FULL HEARING · IN 0:{int(hb - ha):02d}", gf("hook"))
            self.stage_clip(srcname(lead_case), ha, hb, hp, mode="hook", layers=[dict(png=hl, s=0.2, e=hb - ha, fin=0.5)])
        seg("hook", hp, src=srcname(lead_case), a=ha, b=hb)
        # ----- 2. intro (owner's animation via channel_intro_file; generated sting only if the file is missing)
        ip = work / "01_intro.mp4"
        if not ip.exists():
            self.ov_sting(ip, intro_d)
        seg("intro", ip)

        # ----- 3.. cases + briefings
        k = 2
        recap_durs = []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            sname = srcname(c)
            title = f"State v. {c['name']}"
            label = f"CASE FILE {i + 1:02d} · {title.upper()}"
            steps = self._steps(c)
            for pc in [p for p in pieces if p["cid"] == cid]:
                j = pc["j"]
                d_all = pc["b"] - pc["a"]
                cuts = [(pc["a"], pc["b"], "case")]
                if j == 0 and d_all > OPEN_LEN + 6:
                    cuts = [(pc["a"], pc["a"] + OPEN_LEN, "open"), (pc["a"] + OPEN_LEN, pc["b"], "case")]
                for q, (a, b, mode) in enumerate(cuts):
                    p = work / f"{k:02d}_case{cid}_{j}_{q}.mp4"
                    d = b - a
                    g0 = pc["g0"] + (a - pc["a"])
                    if not p.exists():
                        ui(f"  case {cid} part {j + 1}{'/open' if mode == 'open' else ''}: {fmt_dur(d)}")
                        lay = []
                        # top bar, switching with the hearing steps
                        if steps:
                            bounds = [a] + [t for t, _ in steps if a < t < b] + [b]
                            for s0, s1 in zip(bounds[:-1], bounds[1:]):
                                st = max([x for t, x in steps if t <= s0 + 0.01] or [steps[0][1] if mode == "open" else 0])
                                lay.append(dict(png=CG.topbar(label, st, gf(f"top_{cid}_{st}")), s=s0 - a, e=s1 - a))
                        else:
                            lay.append(dict(png=CG.topbar(label, None, gf(f"top_{cid}_x")), s=0, e=d))
                        if mode == "open":
                            rows = self._case_rows(c)
                            card = CG.case_open(f"{i + 1:02d}", title, rows, fmt_tc(parse_tc(c["in"])), gf(f"open_{cid}"))
                            lay.append(dict(png=card, s=0.2, e=d, fin=0.4))
                        else:
                            for s, e, kind, o, ipc in items:
                                if ipc is not pc or not (g0 <= s < g0 + d):
                                    continue
                                ls_, le_ = s - g0, min(e - g0, d)
                                if kind == "record":
                                    png = CG.on_record(o.get("ts") or fmt_tc(parse_tc(o["tc"])), o.get("who_q", "PROSECUTOR"), o["q"],
                                                       o.get("who_a", "WITNESS"), o["a"], gf(f"rec_{cid}_{int(s)}"))
                                elif kind == "fact":
                                    png = CG.key_fact(o["text"], gf(f"fact_{cid}_{int(s)}"))
                                elif kind == "so_far":
                                    png = CG.so_far(o["text"], gf(f"sofar_{cid}_{int(s)}"))
                                elif kind == "verdict_q":
                                    png = CG.verdict_q(o["text"], gf(f"vq_{cid}_{int(s)}"))
                                else:
                                    lay.append(dict(watch=_short(o["text"], 40), s=ls_, e=le_, fin=0.5, fout=0.5))
                                    continue
                                lay.append(dict(png=png, s=ls_, e=le_, fin=0.5, fout=0.5, slide=kind in ("fact", "so_far")))
                            for kind, s0, e0 in subs:
                                s, e = max(s0, g0), min(e0, g0 + d)
                                if e - s < 1.0:
                                    continue
                                png = {"pill": CG.sub_pill, "banner": CG.sub_banner, "button": CG.sub_button}[kind](gf(f"sub_{kind}"))
                                lay.append(dict(png=png, s=s - g0, e=e - g0, fin=0.6, fout=0.6))
                        self.stage_clip(sname, a, b, p, mode=mode, layers=lay)
                    seg("case", p, case_id=cid, src=sname, a=a, b=b)
                    k += 1
            if i < len(ids) - 1:
                clips = recap_clips[cid]
                ds = recap_plan[i]
                recap_durs.append(sum(ds))
                texts = clip_texts(bridges[cid]["text"], len(clips))
                mid = (parse_tc(c["in"]) + parse_tc(c["out"])) / 2
                try:
                    pol = self.tile_crops(self.grab(sname, parse_tc(c.get("moment_tc") or "") if c.get("moment_tc") else mid,
                                                    work / f"pol_{cid}.png"), work / f"pol_{cid}")
                except Exception:
                    pol = []
                status = "VERDICT PENDING" if c.get("ruling_deferred") or "PENDING" in (c.get("ends_on") or "").upper() else "CASE CLOSED"
                start = max(TL.case_parts(c, cfg["cut_pad_out"])[-1][0], parse_tc(c["out"]) - sum(ds) - 2.0)
                off = 0.0
                for q, (w, dq) in enumerate(zip(clips, ds)):
                    p = work / f"{k:02d}_brief{i + 1}_{q}.mp4"
                    if not p.exists():
                        card = CG.briefing(texts[q], f"CASE {i + 1:02d} OF {len(ids)}", pol[:3], status, gf(f"brief_{cid}_{q}"))
                        self.stage_clip(sname, start + off, start + off + dq, p, mode="hook", blur=True,
                                        layers=[dict(png=card, s=0.15, e=dq, fin=0.6)], wav=w, lead=lead)
                    seg("recap", p, case_id=cid, src=sname, a=start + off, b=start + off + dq)
                    off += dq
                    k += 1

        # ----- N. closing: case files wall + vo_final
        last = by_id[ids[-1]]
        rows = []
        for cid in ids:
            c = by_id[cid]
            res = _short((c.get("result") or {}).get("sentence") or c.get("ends_on") or "", 24).upper()
            if c.get("ruling_deferred") or "PENDING" in res:
                res = "VERDICT PENDING"
            t = parse_tc(c.get("moment_tc")) if c.get("moment_tc") else (parse_tc(c["in"]) + parse_tc(c["out"])) / 2
            try:
                img = self.tile_crops(self.grab(srcname(c), t, work / f"wall_{cid}.png"), work / f"wall_{cid}")[0][0]
            except Exception:
                img = self.grab(srcname(c), t, work / f"wall_{cid}.png")
            rows.append((img, f"State v. {c['name']}", res or "CASE CLOSED"))
        quiz = video.get("quiz") or {}
        board = CG.case_files(rows, quiz.get("question", "What would your verdict be?"), quiz.get("options"), gf("casefiles"))
        ds = [probe_dur(w) + lead + tail for w in final_clips]
        fin_total = sum(ds)
        for q, (w, dq) in enumerate(zip(final_clips, ds)):
            p = work / f"{k:02d}_final_{q}.mp4"
            if not p.exists():
                self.ov_card_clip(board, w, lead, p, fade_out=(q == len(final_clips) - 1))
            seg("vo_final", p, case_id=ids[-1], src=srcname(last), a=parse_tc(last["out"]), b=parse_tc(last["out"]))
            k += 1

        # ----- real timeline + join (shared with Overruled)
        return self._finish(plan, video, by_id, outdir, work, segfiles, recap_durs, fin_total, intro_d, recap_clips,
                            final_clips, subs, ui, items)

    def _finish(self, plan, video, by_id, outdir, work, segfiles, recap_durs, fin_total, intro_d, recap_clips,
                final_clips, subs, ui, items):
        from ucf.render import AENC
        cfg = self.cfg
        default_src = plan["source_file"]
        t = 0.0
        rows_ = []
        for kind, path, meta in segfiles:
            d = probe_dur(path)
            rows_.append({"kind": kind, "start": t, "dur": d, **meta})
            t += d
        ui("  joining + loudness...")
        lst = work / "concat.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for _, p, _ in segfiles), encoding="utf-8")
        final = outdir / "video.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy",
             "-af", f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11", *AENC, "-movflags", "+faststart", final])
        real = {"hook": rows_[0]["dur"], "intro": rows_[1]["dur"], "recap": recap_durs, "final": fin_total}
        tcfg = dict(TL.DEFAULTS)
        tcfg.update({"cut_pad_out": cfg["cut_pad_out"], "vo_lead": cfg["vo_lead"], "vo_tail": cfg["vo_tail"], "style": "tt",
                     "wps": cfg.get("wps", 2.6), "final_min_hold": cfg.get("final_min_hold", 12.0), "intro_seconds_tt": intro_d})
        tl = TL.build(video, by_id, tcfg, real)
        for r in rows_:
            s = self.sources.get(r.get("src", default_src)) or {}
            url = s.get("url", "")
            self.log.append({"video": video["n"], "segment": r["kind"], "case_id": r.get("case_id", ""),
                             "source_file": r.get("src", ""), "source_url": (url + ("&" if "?" in url else "?") + f"t={int(r['a'])}s") if url and "a" in r else url,
                             "src_in": fmt_tc(r["a"]) if "a" in r else "", "src_out": fmt_tc(r["b"]) if "b" in r else "",
                             "out_start": fmt_tc(r["start"]), "out_dur": f"{r['dur']:.1f}"})
        return {"final": final, "timeline": tl, "rows": rows_, "durs": real, "measured_total": probe_dur(final),
                "work": work, "ai_clips": [round(probe_dur(w), 1) for cl in list(recap_clips.values()) + [final_clips] for w in cl],
                "subscribe": [(kd, round(s, 1), round(e, 1)) for kd, s, e in subs],
                "overlays": [(kind, round(s, 1), round(e, 1)) for s, e, kind, _, _ in items]}

    # ------------------------------------------------------------------ thumbnail
    def thumbnail(self, plan, video, outdir):
        from ucf import cards
        by_id = {c["id"]: c for c in plan["cases"]}
        th = video["thumbnail"]
        wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
        cid = TL.find_case_for_tc(video, by_id, (wa + wb) / 2) or video["case_ids"][0]
        sname = by_id[cid].get("source_file") or plan["source_file"]
        cdir = Path(outdir) / "thumbnail_candidates"
        cdir.mkdir(parents=True, exist_ok=True)
        cands = []
        for i in range(6):
            t = wa + (wb - wa) * i / 5
            raw = self.grab(sname, t, cdir / f"raw_{i + 1}.png")
            p = self.tile_crops(raw, cdir / f"cand_{i + 1}")[0][0]
            cands.append((cards.sharpness(p), p))
        best = max(cands)[1]
        out = Path(outdir) / "thumbnail.jpg"
        png = CG.thumbnail(best, th.get("text", ""), th.get("gold_word", ""), Path(outdir) / "_work" / "thumb")
        Image.open(png).convert("RGB").save(out, quality=93)
        return out
