"""JUSTICE SERVED renderer (lives in the style pack: styles/justice_served/engine/) - "sports scoreboard" look.

Same locked case structure as every H Labs style EXCEPT one owner decision: there is NO channel intro.
  1. HOOK      10-15 s teaser from the lead case ("TODAY'S MATCHUP" tag + big headline slab, no logo)
  2. CASE 1    starts straight after the hook (no intro animation). Zoom gallery re-staged by tile count, turf-green frame
               + amber corner ticks on the active speaker, lower third "ROUND n · PROCEEDING / STATE vs NAME / court line",
               THE MATCHUP card, bottom ticker, progress line, in-case cards (KEY STAT, PLAY BY PLAY, WATCH THIS, YOUR CALL,
               COMING UP, THE CALL, ON THE RECORD)
  3. RECAP     blurred footage + "POST-GAME REPORT" card, AI voice (<= 18 s clips)
  N. CLOSING   "FINAL SCORE" board + YOUR CALL quiz + big SUBSCRIBE box under the closing narration, fade out
Branding: the logo (assets/logo_transparent.png) sits small in the bottom-right corner of every frame after the hook.
Subscribe CTA in every video: corner button (first one after ~2.5 min, so viewers are not asked before they care), SUBSCRIBE
pill every ~6 min, one full-width banner mid-video, SUBSCRIBE box on every recap card and on the closing board, and the
spoken line in vo_final.
"""
import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image

from ucf import ov_layout as L
from ucf import timeline as TL
from ucf import tts
from ucf.render import probe_dur, run
from ucf.render_ov import BUTTON_LEN, OVRenderer, _short
from ucf.render_tt import TTRenderer
from ucf.timeutil import fmt_dur, fmt_tc, parse_tc


def _sibling(name):
    key = f"justice_served_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


JG = _sibling("js_gfx")

LABEL_AT, LABEL_LEN = 0.6, 7.0
ITEM_GAP = 20.0
HEAD_SKIP, TAIL_SKIP = 40.0, 30.0           # overlay cards: not in the first 40 s / last 30 s of a case
CARD_HEAD, CARD_TAIL = 15.0, 10.0           # takes / exchanges
FIRST_CTA_AT = 150.0                        # first corner SUBSCRIBE button, seconds into the first case
KINDS = ("fact", "so_far", "watch", "verdict_q", "coming_up")


class JSRenderer(OVRenderer):
    def __init__(self, cfg, sources, root):
        super(TTRenderer, self).__init__(cfg, sources, root)       # renderer base only (no canvas / gavel assets)
        self.bg_logo = self.bg_plain = None
        self.use_hf = False
        self._layout = {}
        self.overlay_cache = {}
        try:
            from ucf.config import style_path
            JG.set_fonts(style_path(cfg, "hf/fonts"))
        except ImportError:
            pass
        JG.set_logo(self._asset("logo_file"))
        self.gdir = self.root / cfg["work_dir"] / "_js_gfx"
        self.gdir.mkdir(parents=True, exist_ok=True)
        self.bg = JG.background(self.gdir / "bg")
        self.brand_png = JG.brand(self.gdir / "brand")
        self.prog_png = JG.progress_bar(self.gdir / "progress.png")
        self.lfile = self.gdir / "layout_cache.json"
        try:
            self.lcache = json.loads(self.lfile.read_text())
        except Exception:
            self.lcache = {}

    # ------------------------------------------------------------------ staging
    def stage_clip(self, sname, a, b, out, *, layers=(), brief=None, brief_first=None, brand=True, ticker=None, blur=False,
                   wav=None, lead=0.0, fade_out=False, prog=None):
        """Render [a, b) of `sname` on the Justice Served canvas. layers: {png, s, e, fin, fout, slide} relative to a."""
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
            geo = L.geometry(lay, tpl, act)
            ls = [dict(l) for l in layers]
            if not blur:
                fr = JG.tile_frames(geo["small"], geo["big"], self.gdir / f"fr_{lay}_{act}_{tpl}.png")
                ls.insert(0, dict(png=fr, s=0, e=d))
                if ticker:
                    ls.insert(1, dict(png=ticker, s=0, e=d))
                if brief:
                    geom, mode = geo["brief"]
                    if mode == "always":
                        ls.append(dict(png=brief(geom), s=0, e=d, fin=0.0))
                    elif mode == "first" and brief_first:
                        ls.append(dict(png=brief(geom), s=0.6, e=brief_first, fin=0.5, fout=0.5))
            if brand:                        # the corner logo, on every frame except the hook
                ls.insert(1, dict(png=self.brand_png, s=0, e=d))
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

    def ov_card_clip(self, png, wav, lead, out, fade_out=False):
        return super().ov_card_clip(png, wav, lead, out, fade_out)

    # ------------------------------------------------------------------ text
    def _case_info(self, plan, c, n):
        name = c.get("headline_name") or f"State v. {c['name']}"
        kicker = f"ROUND {n} · {(c.get('proceeding') or 'HEARING').upper()}"
        sub = c.get("sub_line") or self.cfg.get("court_line", "187th District Court · Judge Stephanie Boyd · Bexar County, Texas")
        charge = c.get("charge") or ""
        if c.get("facing"):
            charge = f"{charge} · facing {c['facing']}" if charge else f"Facing {c['facing']}"
        rows = [("DEFENDANT", _short(c.get("defendant_line") or c["name"], 60)),
                ("CHARGE", _short(charge, 80)),
                ("THE QUESTION", _short(c.get("question") or "", 80))]
        return name, kicker, sub, rows

    def schedule_subs(self, case_ranges, total_end, busy):
        """OV schedule, but the first corner button waits until the viewer is invested (FIRST_CTA_AT s into case 1)."""
        ev = super().schedule_subs(case_ranges, total_end, busy)
        out = []
        for kind, s, e in ev:
            if kind == "button":
                for i, (cs, ce) in enumerate(case_ranges):
                    if abs(s - (cs + 12.0)) < 0.01:
                        off = min(FIRST_CTA_AT, max(20.0, (ce - cs) * 0.4)) if i == 0 else 30.0
                        s, e = cs + off, cs + off + BUTTON_LEN
                        break
            out.append((kind, s, e))
        return out

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

        # ---- pre-pass: global timeline (no intro: case 1 starts the second the hook ends)
        hk = video["hook"]
        ha, hb = parse_tc(hk["in"]), parse_tc(hk["out"])
        lead_case = by_id[ids[0]]
        gt = hb - ha
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
        total_end = gt

        def piece_of(tc):
            for pc in pieces:
                if pc["a"] <= tc < pc["b"]:
                    return pc
            return None

        # ---- in-case cards: overlays (fact / so_far / watch / verdict_q / coming_up), takes, exchanges
        items = []        # (g_start, g_end, kind, payload)
        exch = list(video.get("exchanges") or [])
        takes = list(video.get("takes") or [])
        for cs, ce, c in case_ranges:
            cand = []
            for o in c.get("overlays") or []:
                if o.get("kind") in KINDS and o.get("text"):
                    try:
                        cand.append((parse_tc(o["tc"]), float(o.get("dur") or 7.0), o["kind"], o, HEAD_SKIP, TAIL_SKIP))
                    except Exception:
                        pass
            for tk in takes:
                try:
                    cand.append((parse_tc(tk["tc"]), float(tk.get("dur") or 8.0), "take", tk, CARD_HEAD, CARD_TAIL))
                except Exception:
                    pass
            for ex in exch:
                try:
                    cand.append((parse_tc(ex["tc"]), float(ex.get("dur") or 9.0), "record", ex, CARD_HEAD, CARD_TAIL))
                except Exception:
                    pass
            for tc, dur, kind, o, hs, ts_ in sorted(cand, key=lambda x: x[0]):
                if not (parse_tc(c["in"]) <= tc < parse_tc(c["out"])):
                    continue
                pc = piece_of(tc)
                if not pc:
                    continue
                g = pc["g0"] + (tc - pc["a"])
                if g < cs + hs or g + dur > ce - ts_:
                    continue
                if kind != "watch" and any(not (g + dur + ITEM_GAP <= s or g >= e + ITEM_GAP) for s, e, k2, _ in items if k2 != "watch"):
                    continue
                items.append((g, g + dur, kind, o))
        busy = [(s, e) for s, e, k, _ in items if k != "watch"] + [(cs + LABEL_AT, cs + LABEL_LEN) for cs, _, _ in case_ranges]
        subs = self.schedule_subs([(cs, ce) for cs, ce, _ in case_ranges], total_end, busy)
        self.sub_schedule = subs

        segfiles = []

        def seg(kind, path, **meta):
            segfiles.append((kind, Path(path), meta))

        # ----- 1. hook (no logo)
        hp = work / "00_hook.mp4"
        if not hp.exists():
            ui("  hook...")
            lay = [dict(png=JG.hook_tag(gf("hook_tag")), s=0.15, e=hb - ha, fin=0.5),
                   dict(png=JG.hook_headline(hk.get("headline") or "", gf("hook_head")), s=0.35, e=hb - ha, fin=0.5, slide=True)]
            quote = hk.get("quote")
            brief_fn = (lambda geom: JG.quote_card("ON THE RECORD", quote, hk.get("quote_by", "IN COURT"), geom, gf("hook_card"))) if quote else None
            self.stage_clip(srcname(lead_case), ha, hb, hp, layers=lay, brief=brief_fn, brand=False)
        seg("hook", hp, src=srcname(lead_case), a=ha, b=hb)

        # ----- 2.. cases (straight after the hook) + recaps
        k = 1
        recap_durs = []
        for i, cid in enumerate(ids):
            c = by_id[cid]
            sname = srcname(c)
            name, kicker, sub, rows = self._case_info(plan, c, i + 1)
            lt_png = JG.lower_third(kicker, name, sub, gf(f"lt_{cid}"))
            tick_png = JG.ticker(f"ROUND {i + 1}", f"{name}  ·  187th District Court · Bexar County", gf(f"tick_{cid}"))
            brief_fn = lambda geom, rows=rows, i=i, cid=cid: JG.brief(f"ROUND {i + 1}", rows, geom, gf(f"brief_{cid}"))   # noqa: E731
            for pc in [p for p in pieces if p["cid"] == cid]:
                j = pc["j"]
                p = work / f"{k:02d}_case{cid}_{j}.mp4"
                d = pc["b"] - pc["a"]
                if not p.exists():
                    ui(f"  case {cid} part {j + 1}: {fmt_dur(d)}")
                    lay = []
                    if j == 0:
                        lay.append(dict(png=lt_png, s=LABEL_AT, e=LABEL_LEN, fin=0.4, fout=0.4, slide=True))
                    for s0, e0, kind, o in items:
                        s, e = max(s0, pc["g0"]), min(e0, pc["g0"] + d)
                        if e - s < 1.5:
                            continue
                        if kind == "record":
                            png = JG.exchange(o.get("ts") or fmt_tc(parse_tc(o["tc"])), o.get("who_q", "PROSECUTOR"), o["q"], o.get("who_a", "WITNESS"), o["a"],
                                              gf(f"exch_{int(s0)}"))
                        else:
                            png = JG.strip_card(kind, o["text"], gf(f"card_{kind}_{int(s0)}"))
                        lay.append(dict(png=png, s=s - pc["g0"], e=e - pc["g0"], fin=0.5, fout=0.5))
                    for kind, s0, e0 in subs:
                        s, e = max(s0, pc["g0"]), min(e0, pc["g0"] + d)
                        if e - s < 1.0:
                            continue
                        png = {"pill": JG.pill, "banner": JG.banner, "button": JG.corner_button}[kind](gf(f"sub_{kind}"))
                        lay.append(dict(png=png, s=s - pc["g0"], e=e - pc["g0"], fin=0.6, fout=0.6))
                    f0, f1 = pc["el"] / pc["tot"], (pc["el"] + d) / pc["tot"]
                    self.stage_clip(sname, pc["a"], pc["b"], p, layers=lay, brief=brief_fn, brief_first=10.5 if j == 0 else None,
                                    ticker=tick_png, prog=(f0, f1))
                seg("case", p, case_id=cid, src=sname, a=pc["a"], b=pc["b"])
                k += 1
            if i < len(ids) - 1:
                clips = recap_clips[cid]
                ds = recap_plan[i]
                recap_durs.append(sum(ds))
                texts = clip_texts(bridges[cid]["text"], len(clips))
                nxt = by_id[ids[i + 1]]
                start = max(TL.case_parts(c, cfg["cut_pad_out"])[-1][0], parse_tc(c["out"]) - sum(ds) - 2.0)
                off = 0.0
                for q, (w, dq) in enumerate(zip(clips, ds)):
                    p = work / f"{k:02d}_recap{i + 1}_{q}.mp4"
                    if not p.exists():
                        card = JG.overview(texts[q], f"ROUND {i + 1}", f"Next up: {_short(nxt.get('what_it_is') or nxt['name'], 70)}", gf(f"ov_{cid}_{q}"))
                        self.stage_clip(sname, start + off, start + off + dq, p, layers=[dict(png=card, s=0.15, e=dq, fin=0.6)],
                                        blur=True, brand=True, wav=w, lead=lead)
                    seg("recap", p, case_id=cid, src=sname, a=start + off, b=start + off + dq)
                    off += dq
                    k += 1

        # ----- N. closing: FINAL SCORE board + closing narration (<= 18 s clips)
        last = by_id[ids[-1]]
        rows = []
        for n_, cid in enumerate(ids, 1):
            c = by_id[cid]
            res = (c.get("result") or {}).get("sentence") or c.get("ends_on") or ""
            rows.append((f"ROUND {n_}", f"State v. {c['name']}", _short(res, 38)))
        quiz = video.get("quiz") or {}
        dk = JG.docket(rows, quiz.get("question", "What would you have ruled?"), quiz.get("options"), gf("docket"))
        ds = [probe_dur(w) + lead + tail for w in final_clips]
        fin_total = sum(ds)
        for q, (w, dq) in enumerate(zip(final_clips, ds)):
            p = work / f"{k:02d}_final_{q}.mp4"
            if not p.exists():
                self.ov_card_clip(dk, w, lead, p, fade_out=(q == len(final_clips) - 1))
            seg("vo_final", p, case_id=ids[-1], src=srcname(last), a=parse_tc(last["out"]), b=parse_tc(last["out"]))
            k += 1

        # ----- real timeline + join
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
        from ucf.render import AENC
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy",
             "-af", f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11", *AENC, "-movflags", "+faststart", final])
        real = {"hook": rows_[0]["dur"], "intro": 0.0, "recap": recap_durs, "final": fin_total}
        tcfg = dict(TL.DEFAULTS)
        tcfg.update({"cut_pad_out": cfg["cut_pad_out"], "vo_lead": lead, "vo_tail": tail, "style": "tt",
                     "wps": cfg.get("wps", 2.6), "final_min_hold": cfg.get("final_min_hold", 12.0), "intro_seconds_tt": 0.0})
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
                "overlays": [(kind, round(s, 1), round(e, 1)) for s, e, kind, _ in items]}

    # ------------------------------------------------------------------ thumbnail
    def thumbnail(self, plan, video, outdir):
        import numpy as np
        from ucf import cards
        by_id = {c["id"]: c for c in plan["cases"]}
        th = video["thumbnail"]
        wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
        cid = TL.find_case_for_tc(video, by_id, (wa + wb) / 2) or video["case_ids"][0]
        sname = by_id[cid].get("source_file") or plan["source_file"]
        cdir = Path(outdir) / "thumbnail_candidates"
        cdir.mkdir(parents=True, exist_ok=True)
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
        best = max(cands)[1]
        out = Path(outdir) / "thumbnail.jpg"
        jp = JG.thumbnail(best, th["text"], th["gold_word"], Path(outdir) / "_work" / "thumb")
        Image.open(jp).save(out, quality=93)
        return out
