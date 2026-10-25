"""Programmatic version of the master prompt's FINAL LINE checklist.
validate(plan, stream_len, segs=None, cfg=None) -> (errors, warnings). Errors block the render."""
import json
import re

from . import timeline as TL
from . import validate_v10 as V10
from . import vo as V
from .config import style_path
from .timeutil import parse_tc, fmt_dur, fmt_tc

HOOK_BANNED = [r"cause number", r"\b20\d\d\s?cr\s?\d+", r"the court is calling", r"state versus", r"state vs",
               r"parties announce", r"for the record", r"\bdiscovery\b", r"wave the reading", r"any objection",
               r"off the record", r"may i approach", r"raise your right hand", r"do you solemnly swear",
               r"\bplea\b", r"\bpleas\b", r"\bplea cap", r"\bscheduling\b", r"\breset\b"]
ADJ_LABELS = {"monster", "cocky", "arrogant", "heartless", "shocking", "evil", "crazy", "rude", "brazen",
              "entitled", "angry", "insane", "disrespectful", "clueless", "cold", "ruthless", "dangerous",
              "vile", "disgusting", "unhinged", "delusional", "stubborn"}
APPEARANCE = ["tattoo", "hair", "weight", "overweight", "fat ", "skinny", "outfit", "clothes", "clothing", "dress"]
ACRONYMS = {"DWI", "DUI", "DNA", "USA", "TV", "CPS", "ICE", "FBI", "DA", "AI", "MRI", "THC", "PTSD", "OMG"}
STOP = set("a an the and or of to in on at for with from by is are was were be been it its this that his her their "
           "he she they him them as but not no so then than into over after before up down out off".split())
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
VAGUE_Q = [r"what will the judge", r"what happens", r"what does the judge", r"will the judge decide",
           r"what is the outcome", r"what will happen"]
RULE_LEAK = [r"RULES\s*\(do not print", r"never list the hook", r"5-8 chapters only", r"story beats",
             r"first at 00:00", r"one chapter minimum"]


def _tc(v, where, errs):
    try:
        return parse_tc(v)
    except Exception:
        errs.append(f"{where}: bad timecode {v!r}")
        return None


def _words_clean(t):
    return [w.strip(".,!?\"'()[]:;") for w in t.split() if re.search(r"[A-Za-z0-9]", w)]


def _title_halves(title):
    if " — " in title:
        a, b = title.split(" — ", 1)
        return a.strip(), b.strip()
    return title.strip(), ""


def _caps_words(t):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'’]+", t):
        if len(w) >= 3 and w.isupper() and w not in ACRONYMS:
            out.append(w)
    return out


def validate(plan, stream_len, segs=None, cfg=None):
    cfg = cfg or {}
    mode = cfg.get("mode")
    v10_titles = cfg.get("title_system", "v10") == "v10"
    E, W = [], []
    cases = plan.get("cases", [])
    videos = plan.get("videos", [])
    by_id = {}
    banks = V10.parse_banks(style_path(cfg, cfg["_title_rules"]).read_text(encoding="utf-8")
                            if cfg.get("_title_rules") else "")

    # ---------- cases ----------
    spans = []
    for c in cases:
        cid = c.get("id")
        w = f"case {cid} ({c.get('name')})"
        if cid in by_id:
            E.append(f"{w}: duplicate id")
        by_id[cid] = c
        a, b = _tc(c.get("in"), w + " in", E), _tc(c.get("out"), w + " out", E)
        if a is None or b is None:
            continue
        if not (0 <= a < b <= stream_len + 5):
            E.append(f"{w}: range {c['in']}-{c['out']} outside stream (0-{fmt_tc(stream_len)}) or reversed")
            continue
        c["_dur"] = b - a
        spans.append((a, b, cid))
        # LOCKED: a case starts where the judge CALLS it ("calling CR2469 ...") unless it is a jury-trial resume
        if segs is not None and c.get("status") == "used" and not c.get("resume"):
            near = " ".join(x["text"] for x in segs if a - 3 <= x["start"] <= a + 30)
            if not re.search(r"\bcalling\b|\bCR\s?\d{3,}|\bcause (no|number)", near, re.I):
                E.append(f"{w}: IN {c['in']} is not where the judge calls the case (no 'calling CR####' within 30 s) - "
                         "start at the call-out, or set \"resume\": true for a jury-trial continuation")
        if c.get("status") not in ("used", "carried", "rejected", "skipped"):
            E.append(f"{w}: status must be used|carried|rejected|skipped")
        if c.get("status") == "skipped" and mode != "all":
            E.append(f"{w}: status 'skipped' only exists in mode all (use rejected/carried)")
        if c["_dur"] < 120 and c.get("status") not in ("rejected", "skipped"):
            E.append(f"{w}: only {fmt_dur(c['_dur'])} of hearing - under 2:00 is not a case (reject it as 'under 2:00')")
        if mode == "all":
            mc = float(cfg.get("min_case_minutes", 8.0)) * 60
            kept = c["_dur"] - sum(parse_tc(r["out"]) - parse_tc(r["in"]) for r in (list(c.get("removes") or []) + ([c["remove"]] if c.get("remove") else []))
                                   if r.get("in") and r.get("out"))
            if c.get("status") == "used" and kept < mc:
                E.append(f"{w}: C-07 mode all keeps only cases with >= {cfg.get('min_case_minutes', 8):.0f} min of hearing "
                         f"(kept {fmt_dur(kept)}) - mark it skipped")
            if c.get("status") == "skipped" and kept >= mc:
                W.append(f"{w}: C-07 skipped but {fmt_dur(kept)} >= the {cfg.get('min_case_minutes', 8):.0f} min threshold")
            if c.get("status") == "used" and segs is not None:
                inside = " ".join(x["text"] for x in segs if a + 30 < x["start"] < b - 1)
                if re.search(r"\bcourt is calling\b|\bcause (no|number)\b|\bparties announce\b", inside, re.I):
                    E.append(f"{w}: C-04 a different CR call-out sits inside this case's range - split the ranges")
        # v10 case rules (phases, virality, interrupted) + overlays truth rules
        if v10_titles:
            V10.check_case_v10(c, cfg, E, W)
            if c.get("status") == "used" and not cfg.get("_cases_only"):
                V10.check_overlays(c, segs, cfg, E, W)   # overlays are a Pass B deliverable in mode all
        if c.get("status") == "rejected":
            rr = (c.get("reject_reason") or "").lower()
            if c["_dur"] >= 120 and not re.search(r"procedur|no hearing|scheduling|reset|bond paperwork|appearance", rr):
                E.append(f"{w}: rejected with {fmt_dur(c['_dur'])} - the ONLY reject reasons are pure procedure or under 2:00. "
                         f"A short case is a passenger, never a reject")
        rems = list(c.get("removes") or []) + ([c["remove"]] if c.get("remove") else [])
        last_rb = a
        for rem in sorted(rems, key=lambda r: parse_tc(r["in"]) if r.get("in") else 0):
            ra, rb = _tc(rem.get("in"), w + " remove.in", E), _tc(rem.get("out"), w + " remove.out", E)
            if ra is not None and rb is not None:
                if not (a < ra < rb < b):
                    E.append(f"{w}: REMOVE range must sit inside the case range")
                if ra < last_rb:
                    E.append(f"{w}: REMOVE ranges overlap")
                if rb - ra <= 120:
                    E.append(f"{w}: REMOVE must be a recess/dead stretch LONGER than 2:00 (got {fmt_dur(rb - ra)}); tighten IN/OUT instead")
                if ra - last_rb < 20:
                    E.append(f"{w}: kept piece before {rem.get('in')} is only {fmt_dur(ra - last_rb)} - keep pieces must be 20 s or longer")
                last_rb = rb
        if c.get("ruling_deferred"):
            pass
        elif c.get("status") in ("used", "carried"):
            r = _tc(c.get("ruling_tc"), w + " ruling_tc", E) if c.get("ruling_tc") else None
            if r is None:
                E.append(f"{w}: ruling_tc missing (or set ruling_deferred true)")
            elif not (a <= r <= b + 1):
                E.append(f"{w}: ruling_tc {c['ruling_tc']} is outside the case range")
        if c.get("status") == "used":
            for k in ("charge", "facing", "question"):
                if not (c.get(k) or "").strip():
                    E.append(f"{w}: '{k}' is empty (needed for the INTRO card)")
            res = c.get("result") or {}
            for k in ("sentence", "conditions"):
                if not str(res.get(k, "")).strip():
                    E.append(f"{w}: result.{k} is empty (needed for the RESULT card)")
            q = (c.get("question") or "").strip()
            if q:
                if not q.endswith("?"):
                    E.append(f"{w}: THE QUESTION must be a question ending in '?'")
                if any(re.search(p, q.lower()) for p in VAGUE_Q):
                    E.append(f"{w}: THE QUESTION is too vague ('{q}') - name the specific open loop")
                if len(q.split()) > 16:
                    W.append(f"{w}: THE QUESTION is long ({len(q.split())} words) - keep it one short line")
            if not (c.get("cause_no") or "").strip():
                W.append(f"{w}: cause_no empty - card will omit 'Cause No.'")
    spans.sort()
    for (a1, b1, i1), (a2, b2, i2) in zip(spans, spans[1:]):
        if a2 < b1 - 1:
            E.append(f"cases {i1} and {i2} overlap ({fmt_tc(a2)} < {fmt_tc(b1)})")

    # ---------- coverage proof ----------
    gaps = plan.get("gaps", [])
    gspans = []
    for g in gaps:
        ga, gb = _tc(g.get("in"), "gap in", E), _tc(g.get("out"), "gap out", E)
        if ga is not None and gb is not None and gb > ga:
            gspans.append((ga, gb))
    allsp = sorted([(a, b) for a, b, _ in spans] + gspans)
    merged = []
    for a, b in allsp:
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    covered = sum(b - a for a, b in merged)
    unmapped = stream_len - covered
    pts = [0.0] + [x for m in merged for x in m] + [stream_len]
    holes = [(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2) if pts[i + 1] - pts[i] > 1]
    for a, b in holes:
        if b - a > 180:
            E.append(f"coverage: {fmt_tc(a)}-{fmt_tc(b)} ({fmt_dur(b - a)}) is neither a case nor a classified GAP "
                     f"(Pass 2 requires every gap over 3:00 to be classified CASE or NON-CASE)")
    plan["_unmapped"] = max(0.0, unmapped)
    if unmapped > 0.10 * stream_len:
        W.append(f"coverage: {fmt_dur(unmapped)} of the stream is unmapped ({100 * unmapped / stream_len:.0f}%)")

    # ---------- Overruled look extras (style pack "overruled") ----------
    if cfg.get("_cases_only"):
        plan["_stats"] = {                                # Pass A (mode all): cases are all that exists yet
            "found": sum(c.get("_dur", 0) for c in cases),
            "used": sum(c.get("_dur", 0) for c in cases if c.get("status") == "used"),
            "carried": 0,
            "rejected": sum(c.get("_dur", 0) for c in cases if c.get("status") == "rejected"),
            "unmapped": plan.get("_unmapped", 0),
        }
        return E, W
    if cfg.get("_look") == "ov":
        from .timeutil import parse_tc as _ptc
        for v in videos:
            vw = f"video {v.get('id', v.get('n', '?'))}"
            tks = sorted(((_ptc(t["tc"]), t) for t in v.get("takes", []) if t.get("tc")), key=lambda x: x[0])
            for k, (tc, t) in enumerate(tks):
                if len((t.get("text") or "").split()) > 26:
                    E.append(f"{vw}: take at {t['tc']} is over 26 words")
                if k and tc - tks[k - 1][0] < 150:
                    E.append(f"{vw}: takes at {tks[k - 1][1]['tc']} and {t['tc']} are less than 2.5 min apart")
            for x in v.get("exchanges", []):
                if len((x.get("q") or "").split()) > 22 or len((x.get("a") or "").split()) > 18:
                    E.append(f"{vw}: exchange at {x.get('tc')} too long (q<=22, a<=18 words)")
            if "subscribe" not in ((v.get("vo_final") or {}).get("text", "")).lower():
                E.append(f"{vw}: vo_final must contain a subscribe line (Overruled)")
            if not v.get("quiz"):
                W.append(f"{vw}: no quiz for the closing docket board")
        for c in cases:
            if c.get("status") == "used" and not c.get("proceeding"):
                W.append(f"case {c.get('id')}: no 'proceeding' label (will default)")

    # ---------- videos ----------
    used_ids = {c["id"] for c in cases if c.get("status") == "used"}
    seen = {}
    pending = 0
    title_judge = 0
    for v in videos:
        n = v.get("n")
        w = f"video {n}"
        ids = v.get("case_ids") or []
        if not (1 <= len(ids) <= 5):
            E.append(f"{w}: needs 1-5 cases, has {len(ids)}")
        bad = [i for i in ids if i not in by_id or "_dur" not in by_id[i]]
        if bad:
            E.append(f"{w}: unknown/invalid case ids {bad}")
            continue
        for i in ids:
            if by_id[i].get("status") != "used":
                E.append(f"{w}: case {i} has status {by_id[i].get('status')!r}, only 'used' cases can be in a video")
            if i in seen:
                E.append(f"{w}: case {i} is already in video {seen[i]}")
            seen[i] = n
        # shape normalisation: the brain sometimes sends vo_final/vo1/hook as plain strings,
        # or community_post/pinned_comment as {"text": ...}
        for key in ("vo_final", "vo1"):
            if isinstance(v.get(key), str):
                v[key] = {"text": v[key]}
        for key in ("community_post", "pinned_comment"):
            if isinstance(v.get(key), dict):
                v[key] = v[key].get("text") or json.dumps(v[key], ensure_ascii=False)
        if isinstance(v.get("hook"), str):
            v["hook"] = {"in": v.get("hook_in", ""), "out": v.get("hook_out", ""), "headline": v["hook"]}
        vc = [by_id[i] for i in ids]
        lead = vc[0]
        total_cases = sum(TL.case_len(c) for c in vc)
        if mode == "all":
            if len(ids) != 1:
                E.append(f"{w}: V-01 mode all = exactly one case per video, got {len(ids)}")
            if v.get("bridges"):
                E.append(f"{w}: V-01 mode all has no bridges (bridges must be [])")
        hook_len = None
        # --- runtime
        hk = v.get("hook") or {}
        ha, hb = _tc(hk.get("in"), w + " hook.in", E), _tc(hk.get("out"), w + " hook.out", E)
        if ha is not None and hb is not None:
            hook_len = hb - ha
            hmin, hmax = cfg.get("hook_min", 10), cfg.get("hook_max", 15)
            if not (hmin - 0.4 <= hook_len <= hmax + 0.5):
                E.append(f"{w}: hook is {hook_len:.1f}s - must be {hmin:.0f}-{hmax:.0f} s")
            la, lb = parse_tc(lead["in"]), parse_tc(lead["out"])
            floor = la + 0.4 * (lb - la)
            if not (ha >= floor - 1 and hb <= lb + 1):
                E.append(f"{w}: hook {hk['in']}-{hk['out']} must be inside the BACK 60% of the lead case range "
                         f"({fmt_tc(floor)}-{lead['out']})")
            if segs is not None:
                real = " ".join(s["text"] for s in segs if ha - 0.5 <= s["start"] < hb).lower()
                hk["spoken_actual"] = real
                for p in HOOK_BANNED:
                    if re.search(p, real):
                        E.append(f"{w}: hook contains banned material /{p}/ - pick a hook with a real challenge/number/break")
                if len(real.split()) < 12:
                    W.append(f"{w}: hook clip has only {len(real.split())} words of speech")
            else:
                for p in HOOK_BANNED:
                    if re.search(p, (hk.get("spoken") or "").lower()):
                        E.append(f"{w}: hook text contains banned material /{p}/")
        intro = float(v.get("intro_seconds", 6))
        if cfg.get("_renderer") != "tt" and not (5 <= intro <= 8):
            E.append(f"{w}: channel intro must be 5-8 s, got {intro}")
        if cfg.get("_renderer") == "tt":
            hl = str(hk.get("headline", "")).strip()
            nhl = len(hl.split())
            if not (3 <= nhl <= 9):
                E.append(f"{w}: hook.headline (bottom caption of the teaser) must be 3-9 words, got {nhl}: {hl!r}")
            elif hl.endswith((".", ",")):
                E.append(f"{w}: hook.headline must not end with a period/comma")
        vo_est = 0.0
        if cfg.get("_renderer") == "tt":
            intro = float(cfg.get("intro_seconds_tt", 7.47))
            tcfg = dict(TL.DEFAULTS)
            tcfg.update({"wps": cfg.get("wps", 2.6), "_renderer": "tt"})
            vo_est = sum(TL.est_clips_dur(b.get("text", ""), tcfg) for b in v.get("bridges", [])) + \
                TL.est_clips_dur((v.get("vo_final") or {}).get("text", ""), tcfg)
        runtime = total_cases + (hook_len or 12) + intro + vo_est
        v["_cases_total"] = total_cases
        v["_runtime_rule"] = runtime
        rmin, rmax = cfg.get("runtime_min", 20 * 60), cfg.get("runtime_max", 40 * 60)
        if mode == "all":
            pass                                   # V-05: no runtime band in mode all - a case is one video, never chopped
        elif len(ids) == 1:
            if runtime < rmin:
                E.append(f"{w}: solo case is {fmt_dur(total_cases)} - runtime floor is {fmt_dur(rmin)}")
            elif total_cases < 25 * 60:
                W.append(f"{w}: solo case under 25:00 ({fmt_dur(total_cases)}) - only 25:00+ cases are normally solo")
            elif runtime > rmax + 5 and not cfg.get("allow_long_solo", True):
                E.append(f"{w}: single case runtime {fmt_dur(runtime)} is over {fmt_dur(rmax)}")
        else:
            if runtime < rmin:
                E.append(f"{w}: runtime {fmt_dur(runtime)} below the {fmt_dur(rmin)} floor - keep adding cases")
            if runtime > rmax + 5:
                E.append(f"{w}: bundle runtime {fmt_dur(runtime)} is over {fmt_dur(rmax)} - move a case to another video")
            if lead["_dur"] < 360:
                E.append(f"{w}: lead case {lead['name']} is only {fmt_dur(lead['_dur'])}; leads must be 6:00+ (short cases are passengers)")
        if lead.get("monetisation") == "LIMITED":
            W.append(f"{w}: flagship case is MONETISATION: LIMITED - avoid making it the thumbnail-facing lead")
        # --- voiceovers
        texts = {}
        if cfg.get("_renderer") != "tt" or (v.get("vo1") or {}).get("text"):
            texts["vo1"] = (v.get("vo1") or {}).get("text", "")
        brs = {b.get("after_case_id"): b for b in v.get("bridges", [])}
        for i in range(len(ids) - 1):
            b = brs.get(ids[i])
            if not b:
                E.append(f"{w}: missing VO-BRIDGE after case {ids[i]}")
            else:
                texts[f"bridge{i + 1}"] = b.get("text", "")
        extra = [k for k in brs if k not in ids[:-1]]
        if extra:
            E.append(f"{w}: bridges reference seams that do not exist: {extra}")
        texts["final"] = (v.get("vo_final") or {}).get("text", "")
        limits = {"vo1": (25, 35), "final": (45, 55)}
        if cfg.get("_renderer") == "tt":
            limits["final"] = (45, 70)          # read as 2 sentence-aligned clips, each <= 18 s
            limits["bridge"] = (35, 40)          # one recap clip, <= 18 s
        others = [c for c in cases if c["id"] not in ids]
        for k, t in texts.items():
            lo, hi = limits.get(k, limits["bridge"] if k.startswith("bridge") and "bridge" in limits else (35, 45))
            nw = V.n_words(t)
            if not t.strip():
                E.append(f"{w}: {k} is empty")
                continue
            if not (lo <= nw <= hi):
                E.append(f"{w}: {k} is {nw} words, must be {lo}-{hi} (real count)")
            low = t.lower()
            for ph in V.BANNED_VO:
                if ph in low:
                    E.append(f"{w}: {k} uses banned phrase '{ph}'")
            for c in others:
                nm = (c.get("name") or "").strip().lower()
                toks = [x for x in re.split(r"\s+", nm) if len(x) >= 4]
                if (nm and nm in low) or (toks and toks[-1] in low):
                    E.append(f"{w}: {k} names '{c['name']}' who is NOT in this video")
            if cfg.get("_renderer") == "tt":
                for sn in V.clip_issues(t, V.CLIP_TARGET, cfg.get("wps", 2.6)):
                    E.append(f"{w}: {k} has a sentence too long for one <=18 s AI clip: {sn[:60]!r}")
                if k.startswith("bridge") and V.est_seconds(t, cfg.get("wps", 2.6)) > V.CLIP_TARGET + 0.7:
                    E.append(f"{w}: {k} reads ~{V.est_seconds(t, cfg.get('wps', 2.6)):.1f}s - a recap clip must stay <= 18 s")
            if k.startswith("bridge") and (len(V.sentences(t)) < 2):
                E.append(f"{w}: {k} needs at least 2 sentences (close the last case, open the next)")
        # reuse between VOs
        keys = list(texts)
        for i, ka in enumerate(keys):
            for kb in keys[i + 1:]:
                sa = {V.norm_sentence(s) for s in V.sentences(texts[ka])}
                sb = {V.norm_sentence(s) for s in V.sentences(texts[kb])}
                if sa & sb:
                    E.append(f"{w}: {ka} and {kb} share an identical sentence - every VO must be NEW words")
                elif V.ngrams(texts[ka]) & V.ngrams(texts[kb]):
                    E.append(f"{w}: {ka} and {kb} share a 5-word run - reword")
        # comment ask / subscribe ask in final
        fl = texts["final"].lower()
        if "comment" not in fl and "which are you" not in fl and "side" not in fl and "?" not in fl:
            W.append(f"{w}: VO-FINAL has no visible comment ask")
        if not re.search(r"subscribe|follow|like", fl):
            (E if mode == "all" else W).append(f"{w}: V-03 VO-FINAL needs a like/subscribe ask"
                                               if mode == "all" else f"{w}: VO-FINAL has no like/subscribe ask")
        # --- quiz
        qz = v.get("quiz") or {}
        if not str(qz.get("question", "")).strip() or not all(str((qz.get("options") or {}).get(k, "")).strip() for k in "ABC"):
            E.append(f"{w}: quiz needs a question and options A, B, C")
        # --- title
        title, bt = v.get("title", ""), v.get("backup_title", "")
        if v10_titles:
            case_text = ""
            if segs is not None:
                sa, sb = parse_tc(vc[0]["in"]), max(parse_tc(c["out"]) for c in vc)
                case_text = " ".join(s["text"] for s in segs if parse_tc(vc[0]["in"]) - 1 <= s["start"] <= sb + 1)
            V10.check_titles_v10(v, lead, case_text, plan.get("judge_name") or cfg.get("judge_name", "Judge Boyd"),
                                 banks, E, W)
        for label, t in (("title", title), ("backup_title", bt)):
            if v10_titles:
                break                                        # v10 validates titles[] instead (group T)
            if not t:
                E.append(f"{w}: {label} missing")
                continue
            nch, nw = len(t), len(_words_clean(t.replace("—", " ")))
            if not (65 <= nch <= 90):
                E.append(f"{w}: {label} is {nch} characters (must be 65-90): {t!r}")
            if not (13 <= nw <= 17):
                E.append(f"{w}: {label} is {nw} words (must be 13-17): {t!r}")
            if t.count(" — ") != 1 or ":" in t or "|" in t:
                E.append(f"{w}: {label} must use exactly one ' — ' em dash and no colon/pipe: {t!r}")
            if "*" in t or EMOJI.search(t):
                E.append(f"{w}: {label} has asterisks or emoji")
            first = (re.findall(r"[A-Za-z]+", t) or [""])[0].lower()
            if first in ADJ_LABELS:
                E.append(f"{w}: {label} opens on an adjective label ('{first}') - never")
            setup, payoff = _title_halves(t)
            caps = _caps_words(t)
            if len(caps) != 1:
                E.append(f"{w}: {label} needs exactly ONE all-caps power word, found {caps}")
            elif caps[0] not in _caps_words(payoff):
                E.append(f"{w}: {label}: the ALL-CAPS word must be in the payoff half (after the em dash)")
            if any(a in t.lower() for a in APPEARANCE):
                W.append(f"{w}: {label} may be built on appearance - check")
            if not re.search(r"\d", t):
                W.append(f"{w}: {label} has no number - add one if the case gives one")
            if label == "title" and "judge boyd" in t.lower():
                title_judge += 1
        if title and bt and not v10_titles:
            s1, p1 = _title_halves(title)
            s2, p2 = _title_halves(bt)
            norm = lambda x: re.sub(r"[^a-z0-9 ]", "", x.lower()).strip()
            if norm(s1) == norm(s2) or norm(p1) == norm(p2):
                E.append(f"{w}: title and backup share a half - they must differ on BOTH halves")
            f1 = (norm(s1).split() or [""])[0]
            f2 = (norm(s2).split() or [""])[0]
            if f1 == f2:
                E.append(f"{w}: backup must use a DIFFERENT setup opener (both start with '{f1}')")
        # --- thumbnail
        th = v.get("thumbnail") or {}
        tx = (th.get("text") or "").strip()
        tw = _words_clean(tx)
        if not (2 <= len(tw) <= 5):
            E.append(f"{w}: thumbnail text must be 2-5 words, got {len(tw)}: {tx!r}")
        gold = (th.get("gold_word") or "").strip().strip(".,!?\"'").lower()
        if not gold or gold not in [x.lower() for x in tw]:
            E.append(f"{w}: gold_word must be exactly one word from the thumbnail text")
        if th.get("placement") not in ("top", "bottom"):
            E.append(f"{w}: thumbnail placement must be top|bottom")
        tset = {x.lower() for x in tw} - STOP
        hset = {x.lower() for x in _words_clean(title.replace("—", " "))} - STOP
        if tset and len(tset & hset) / len(tset) >= 0.5:
            E.append(f"{w}: thumbnail text {tx!r} repeats the title - it must ADD information")
        wa, wb = _tc(th.get("window_in"), w + " thumb.window_in", E), _tc(th.get("window_out"), w + " thumb.window_out", E)
        if wa is not None and wb is not None:
            if not (1.5 <= wb - wa <= 6):
                W.append(f"{w}: thumbnail window should be about 3 s")
            if not any(parse_tc(c["in"]) <= wa and wb <= parse_tc(c["out"]) + 1 for c in vc):
                E.append(f"{w}: thumbnail window must sit inside one of this video's case ranges")
        # --- description / metadata
        d = v.get("description") or {}
        for k in ("first_line", "what_happens", "search_question", "answer", "related_question"):
            if not str(d.get(k, "")).strip():
                E.append(f"{w}: description.{k} is empty")
        blob = " ".join(str(x) for x in d.values())
        for p in RULE_LEAK:
            if re.search(p, blob, re.I):
                E.append(f"{w}: chapter-rule text leaked into the description (/{p}/)")
        sq, ans = (d.get("search_question") or "").lower(), (d.get("answer") or "").lower()
        if sq and ans and ans[:len(sq)] == sq:
            E.append(f"{w}: description answer repeats the question as its first words")
        if d.get("answer") and not (70 <= V.n_words(d["answer"]) <= 140):
            W.append(f"{w}: description answer is {V.n_words(d['answer'])} words (aim ~100)")
        tags = v.get("tags") or []
        if not (10 <= len(tags) <= 18):
            W.append(f"{w}: expected 12-15 case-specific tags, got {len(tags)}")
        for k in ("pinned_comment", "community_post"):
            if not str(v.get(k, "")).strip():
                E.append(f"{w}: {k} missing")
        if v.get("community_post") and not (28 <= V.n_words(v["community_post"]) <= 55):
            W.append(f"{w}: community_post is {V.n_words(v['community_post'])} words (aim ~40)")
        if (v.get("publish") or {}).get("slot") not in ("9am ET", "1pm ET", "6pm ET"):
            E.append(f"{w}: publish.slot must be '9am ET' | '1pm ET' | '6pm ET'")
        if v.get("verdict_pending") or any(c.get("ruling_deferred") for c in vc):
            pending += 1
            if not v.get("followup_owed"):
                E.append(f"{w}: ruling is pending - followup_owed is required")
        # --- chapters (estimated timeline)
        try:
            tl = TL.build(v, by_id, cfg)
        except Exception as ex:  # noqa
            E.append(f"{w}: cannot build timeline: {ex}")
            continue
        chs = v.get("chapters") or []
        ch_lo = 4 if tl["total"] < 720 else 5                   # V-04: 4-8 under 12:00, else 5-8
        if not (ch_lo <= len(chs) <= 8):
            E.append(f"{w}: V-04 chapters must be {ch_lo}-8, got {len(chs)}")
        covered_cases = set()
        last_out = -1
        for ch in chs:
            ct = _tc(ch.get("tc"), w + " chapter tc", E)
            if ct is None:
                continue
            cid = TL.find_case_for_tc(v, by_id, ct)
            if cid is None:
                E.append(f"{w}: chapter {ch.get('tc')} is not inside any case range of this video")
                continue
            covered_cases.add(cid)
            o = TL.src_to_out(tl, cid, ct)
            if o is None:
                E.append(f"{w}: chapter {ch.get('tc')} falls inside the removed span")
                continue
            if o <= last_out:
                E.append(f"{w}: chapters must be in play order")
            last_out = o
            if o > tl["total"] - 60:
                E.append(f"{w}: chapter {ch.get('tc')} lands in the final 60 s of the video")
            lab = ch.get("label", "")
            if re.search(r"\bcase \d|\bhook\b|\bintro\b|\bvo\b|voice", lab, re.I) or not lab.strip():
                E.append(f"{w}: chapter label {lab!r} must be a story beat (not Case n / hook / intro / VO)")
        first = chs[0] if chs else None
        if first and _tc(first.get("tc"), "ch0", []) is not None and abs(parse_tc(first["tc"]) - parse_tc(lead["in"])) > 1.0:
            E.append(f"{w}: first chapter must be the first case's IN ({lead['in']})")
        if set(ids) - covered_cases:
            E.append(f"{w}: every case needs at least one chapter (missing {sorted(set(ids) - covered_cases)})")
        v["_est_total"] = tl["total"]

    # ---------- plan-level ----------
    if not cfg.get("_single_video"):
        for c in cases:
            if c.get("status") == "used" and c["id"] not in seen:
                E.append(f"case {c['id']} ({c['name']}) is 'used' but in no video")
    if pending > 1:
        W.append(f"{pending} verdict-pending videos in one plan (max 1 per week)")
    if videos and title_judge not in (0, len(videos)) and abs(title_judge / len(videos) - 0.5) > 0.5:
        pass
    usable = sum(c["_dur"] for c in cases if c.get("status") in ("used", "carried") and "_dur" in c)
    carried = sum(c["_dur"] for c in cases if c.get("status") == "carried" and "_dur" in c)
    rmin_ = cfg.get("runtime_min", 20 * 60)
    if usable >= rmin_ and not videos:
        E.append(f"YOU MUST BUILD: {fmt_dur(usable)} of usable hearings exist but no video was built")
    if carried >= rmin_ + 120:
        E.append(f"{fmt_dur(carried)} is carried forward - that is enough for another video; build it instead of carrying")
    for c in cases:
        if c.get("status") == "carried" and c.get("monetisation") != "LIMITED":
            pass
    plan["_stats"] = {
        "found": sum(c.get("_dur", 0) for c in cases),
        "used": sum(c.get("_dur", 0) for c in cases if c.get("status") == "used"),
        "carried": carried,
        "rejected": sum(c.get("_dur", 0) for c in cases if c.get("status") == "rejected"),
        "unmapped": plan["_unmapped"],
    }
    return E, W
