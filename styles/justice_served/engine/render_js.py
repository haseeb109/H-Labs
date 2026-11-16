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
import sys
from pathlib import Path

from ucf import ov_layout as L
from ucf.render_ov import BUTTON_LEN, OVRenderer, _short
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


def _ev(v):
    return int(round(v)) & ~1


def js_geometry(layout, template, active):
    """Footage on the canvas with the LEAST scaling (quality first - never the 2x zoom of a 640x360 Zoom tile):
    * 2 tiles  -> both tiles side by side as one 1920x540 strip (exactly 1.5x, same as the approved sample)
    * 1 / 3 / 4 tiles -> the whole original Zoom frame at 0.9x (a slight DOWN-scale: sharper than the source), matchup card at the right
    -> dict(tiles=[(src_rect_1280, dst_rect)], big=rect, small=[rects], brief=(rect, mode))"""
    rects = L.TEMPLATES[template]
    n = len(rects)
    act = active if active is not None and active < n else L.DEFAULT_ACTIVE.get(layout, 0)
    if layout == "2":
        dst = [(0, 120, 960, 540), (960, 120, 960, 540)]
        return dict(tiles=list(zip(rects, dst)), big=dst[act], small=[d for i, d in enumerate(dst) if i != act],
                    brief=((40, 676, 1840, 104), "always"))
    k, ox, oy = 0.9, 40, 118
    dst = [(ox + _ev(k * x), oy + _ev(k * y), _ev(k * w), _ev(k * h)) for x, y, w, h in rects]
    whole = (ox, oy, _ev(k * 1280), _ev(k * 720))
    return dict(tiles=list(zip(rects, dst)), big=whole, small=[], brief=((1224, 118, 656, 648), "always"))


class JSRenderer(OVRenderer):
    GFX = JG                    # the Justice Served graphics (js_gfx), same call shapes as ov_gfx
    GFX_DIR = "_js_gfx"

    # ------------------------------------------------------------------ staging: what differs from Overruled
    def _geometry(self, lay, tpl, act, path, t, opts):
        return js_geometry(lay, tpl, act)

    def _run_layers(self, geo, run, d, layers, blur, opts):
        """No tile frames (green box + amber corner ticks): they follow the detected layout, and when the footage is placed
        differently (e.g. the hook) the box sat off the picture (owner, 2026-11-02: remove it)."""
        ls = [dict(l) for l in layers]
        if not blur:
            if opts.get("ticker"):
                ls.insert(0, dict(png=opts["ticker"], s=0, e=d))
            if opts.get("header"):
                ls.insert(0, dict(png=opts["header"], s=0, e=d))       # same stacking as before: header, ticker, then the cards
            self._brief_layer(ls, geo, d, opts)
        if opts.get("brand", True):                        # the corner logo, on every frame except the hook
            ls.insert(1, dict(png=self.brand_png, s=0, e=d))
        return ls

    # ------------------------------------------------------------------ text
    def _case_info(self, plan, c, n):
        name = c.get("headline_name") or f"State v. {c['name']}"
        kicker = f"ROUND {n} · {(c.get('proceeding') or 'HEARING').upper()}"
        sub = c.get("sub_line") or self.cfg.get("court_line", "{court} · Bexar County, Texas").replace("{court}", self.cfg.get("court", "District Court"))
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
        ids = video["case_ids"]
        default_src = plan["source_file"]
        lead = self.cfg["vo_lead"]
        srcname = lambda c: c.get("source_file") or default_src      # noqa: E731
        gf = lambda name: self.gdir / name                              # noqa: E731

        bridges, recap_clips, final_clips = self._voice(video, ids, tts_cache, ui)

        # ---- pre-pass: global timeline (no intro: case 1 starts the second the hook ends)
        hk = video["hook"]
        ha, hb = parse_tc(hk["in"]), parse_tc(hk["out"])
        lead_case = by_id[ids[0]]
        pieces, case_ranges, recap_plan, total_end = self._plan_pieces(by_id, ids, hb - ha, srcname, recap_clips)

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

        segfiles, seg = self._segments()

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
            head_png = JG.scoreboard(kicker, c["name"], c.get("charge") or "", gf(f"head_{cid}"))
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
                                    ticker=tick_png, prog=(f0, f1), header=head_png)
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
        fin_total, k = self._closing_segments(dk, final_clips, work, k, seg, last, srcname(last))

        # ----- real timeline + join (shared; no intro segment -> 0.0 s of intro on the timeline)
        return self._finish_video(plan, video, by_id, outdir, work, segfiles, recap_durs, fin_total, 0.0, recap_clips,
                                  final_clips, subs, ui, extra={"overlays": [(kind, round(s, 1), round(e, 1)) for s, e, kind, _ in items]})
