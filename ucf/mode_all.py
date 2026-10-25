"""v10 mode "all" orchestration: two-pass brain (Pass A inventory -> script -> Pass B per-case packaging),
virality ranking, and the plan assembly that run_stream.py renders.
Everything the brain writes is distrusted where it matters: totals, ranks, and title/backup_title are
script-computed here (spec 5.2 / 10)."""
import json
from pathlib import Path

from . import validate as VAL
from . import validate_v10 as V10
from .config import style_path
from .timeutil import parse_tc, fmt_tc
from . import vo as V

ROOT = Path(__file__).resolve().parent.parent


def _slice_text(segs, a, b):
    return " ".join(s["text"] for s in segs if a - 1 <= s["start"] <= b + 1)


def finalize_cases(plan, cfg):
    """Script step between Pass A and Pass B: lengths, statuses, interrupted segment pick,
    virality totals + penalties + tie-break ranking. Mutates plan["cases"], returns the used list."""
    mc = float(cfg.get("min_case_minutes", 8.0)) * 60
    used = []
    for c in plan.get("cases", []):
        if c.get("status") == "skipped":
            continue
        a, b = parse_tc(c["in"]), parse_tc(c["out"])
        removes = sum(parse_tc(r["out"]) - parse_tc(r["in"]) for r in
                      (list(c.get("removes") or []) + ([c["remove"]] if c.get("remove") else []))
                      if r.get("in") and r.get("out"))
        kept = (b - a) - removes
        if c.get("interrupted") and c.get("segments"):
            segs = sorted(((parse_tc(s["in"]), parse_tc(s["out"])) for s in c["segments"]), key=lambda x: x[0] - x[1])
            a, b = segs[0]
            c["in"], c["out"] = fmt_tc(a, False), fmt_tc(b, False)
            kept = b - a
            if kept < mc:
                c["status"] = "skipped"
                c["reject_reason"] = "interrupted, longest segment under 8:00"
        if c.get("status") != "rejected":
            if kept >= mc:
                # the script owns the threshold (spec 5.1): an over-cautious brain skip is corrected here
                c["status"] = "used"
                c["_dur"] = kept
                c.pop("reject_reason", None)
                used.append(c)
            elif c.get("status") == "used":
                c["status"] = "skipped"
                c["reject_reason"] = f"under {cfg.get('min_case_minutes', 8):.0f}:00"
    return used


def rank_used(used):
    """Assign virality totals + ranks. LIMITED monetisation can never sit in the top 3."""
    for c in used:
        c.setdefault("virality", {})
        c["virality"]["total"] = V10.virality_total(c)
    ranked = sorted(used, key=lambda c: (-c["virality"]["total"],) + tuple(-x for x in _tb(c)))
    limited = [c for c in ranked if (c.get("monetisation") or "").upper() == "LIMITED"]
    top = [c for c in ranked if c not in limited]
    order = top[:3] + limited + top[3:]          # LIMITED pushed to rank 4+, original order kept after
    for i, c in enumerate(order, 1):
        c["rank"] = i
    return order


def _tb(c):
    f = (c.get("virality") or {}).get("factors") or {}
    return (f.get("surprise_ruling", 0) + f.get("judge_confrontation", 0), c.get("_dur", 0), -parse_tc(c["in"]))


def case_prompt(case, cfg, judge):
    """Pass B prompt: packaging system + titles + overlays + the style's extras + THIS case + transcript slice."""
    # video_schema.md: without the exact field shapes the model invented its own (tc_in, list options, string
    # vo_final) and every case failed validation on 03p3ATnv6dY (2026-10-25)
    parts = [_shared("packaging.md", cfg), _shared("video_schema.md", cfg), _shared("titles_core.md", cfg)]
    from .brain import examples_on
    if examples_on(cfg):
        parts.insert(2, _shared("example_pass_b.md", cfg))
    tr = cfg.get("_title_rules")
    if tr:
        parts.append(style_path(cfg, tr).read_text(encoding="utf-8"))
    parts.append(_shared("overlays.md", cfg))
    if cfg.get("_prompt_extra"):
        parts.append(style_path(cfg, cfg["_prompt_extra"]).read_text(encoding="utf-8"))
    fill = {"{JUDGE_NAME}": judge, "{CHANNEL}": cfg.get("channel_name", ""),
            "{MIN_CASE}": fmt_tc(float(cfg.get("min_case_minutes", 8.0)) * 60, False)}
    txt = "\n\n".join(p for p in parts if p)
    for k, v in fill.items():
        txt = txt.replace(k, v)
    case_json = json.dumps({k: v for k, v in case.items() if not k.startswith("_")}, indent=1, ensure_ascii=False)
    txt += ("\n\n" + "═" * 64 + "\n THE CASE (JSON)\n" + "═" * 64 + "\n" + case_json
            + "\n\nNow output the single {\"video\": {...}} JSON object.")
    return txt


def _shared(name, cfg):
    p = ROOT / "prompts" / "shared" / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def case_slice_lines(lines, a, b):
    """Transcript compact lines inside [a - 20 s, b + 10 s] for a Pass B prompt."""
    out = []
    for ln in lines:
        m = None
        try:
            m = parse_tc(ln.split("]", 1)[0].strip("[] ") or "0:00:00")
        except Exception:
            m = None
        if m is not None and a - 20 <= m <= b + 10:
            out.append(ln)
    return out


def _provider_cfg(cfg, provider):
    """cfg copy pointed at one provider (brain + its own model + max_tokens). mock/manual keep cfg as is."""
    from . import brain as B
    if provider in B.PROVIDERS:
        return B.cfg_for(cfg, provider)
    return dict(cfg, brain=provider)


def _fallback_for(cfg, used):
    """The provider to retry with, or None (no fallback set, same provider, or offline mock run)."""
    fb = cfg.get("brain_fallback") or ""
    return fb if fb and fb != used and used != "mock" else None


def _pass_a_loop(cfg_a, prompt_a, stream_len, segs, ui, work, tag=""):
    """Pass A with validator repair rounds on ONE provider. -> (plan, errs). A reply that cannot be repaired
    (BrainStop: empty / cut off / refused) or an API error ends this provider's attempt; the caller decides
    whether a fallback provider takes over (no fallback -> BrainStop goes up and stops the run)."""
    from . import brain as B
    msgs_a = [{"role": "user", "content": prompt_a}]
    plan, errs = None, []
    for rnd in range(int(cfg_a["max_repair_rounds"]) + 1):
        ui(f"  PASS A (inventory) {cfg_a.get('brain')} round {rnd + 1}...")
        cfg_a["_usage_label"] = f"pass A {tag}r{rnd + 1}"
        try:
            txt = B.stream_and_save(msgs_a, cfg_a,
                                    Path(work) / f"brain_reply_A_{tag}{rnd + 1}.txt" if work else None,
                                    on_text=lambda n: n % 400 == 0 and ui(f"    ...{n} chunks"))
        except (B.BrainStop, RuntimeError) as e:
            if not tag and not _fallback_for(cfg_a, cfg_a.get("brain")):
                raise                                   # no fallback configured: stop the run (old behaviour)
            return None, [f"{cfg_a.get('brain')}: {e}"]
        try:
            plan = B.extract_json(txt)
        except Exception as e:
            plan, errs = None, [f"Pass A: not valid JSON ({e})"]
            msgs_a += [{"role": "assistant", "content": txt}, {"role": "user", "content": errs[0]}]
            continue
        errs, _w = VAL.validate(plan, stream_len, segs, cfg_a)
        if not errs:
            break
        ui(f"  validator: {len(errs)} problem(s) -> sending back")
        msgs_a += [{"role": "assistant", "content": txt},
                   {"role": "user", "content": "The validator rejected this plan. Fix EVERY item and return the "
                    "COMPLETE corrected JSON (same schema):\n- " + "\n- ".join(errs[:40])}]
    return plan, errs


def _pass_b_loop(c, pb, prompt_b, plan, judge, stream_len, segs, cfg, ui, work, tag=""):
    """Pass B for one case on ONE provider with validator repair rounds. -> (video object, errs)."""
    from . import brain as B
    msgs_b = [{"role": "user", "content": prompt_b}]
    vobj, berrs = None, []
    for rnd in range(int(cfg["max_repair_rounds"]) + 1):
        pb["_usage_label"] = f"pass B {c.get('name', '')[:10]} {tag}r{rnd + 1}"
        try:
            txt = B.stream_and_save(msgs_b, pb,
                                    Path(work) / f"brain_reply_B_{c['id']}_{tag}{rnd + 1}.txt" if work else None,
                                    on_text=lambda n: n % 400 == 0 and ui(f"    ...{n} chunks"))
        except (B.BrainStop, RuntimeError) as e:
            if not tag and not _fallback_for(cfg, pb.get("brain")):
                raise                                   # no fallback configured: stop the run (old behaviour)
            return None, [f"{pb.get('brain')}: {e}"]
        try:
            vobj = B.extract_json(txt).get("video", {})
        except Exception as e:
            vobj, berrs = None, [f"Pass B: not valid JSON ({e})"]
            msgs_b += [{"role": "assistant", "content": txt}, {"role": "user", "content": berrs[0]}]
            continue
        probe = {"n": c["rank"], "schema": "v10", **vobj, "case_ids": [c["id"]], "bridges": vobj.get("bridges", [])}
        try:
            berrs, _w = VAL.validate({"schema": "v10", "mode": "all", "cases": plan["cases"], "videos": [probe],
                                      "judge_name": judge, "gaps": plan.get("gaps", [])},
                                     stream_len, segs, dict(cfg, **{"_single_video": c["id"]}))
        except Exception as ex:  # noqa: shape surprises become repairable, never crashes
            berrs = [f"validator could not read this video object ({ex}) - check field shapes against the schema"]
        if not berrs:
            break
        ui(f"  validator: {len(berrs)} problem(s) -> sending back (first: {berrs[0][:110]})")
        msgs_b += [{"role": "assistant", "content": txt},
                   {"role": "user", "content": "The validator rejected this video. Fix EVERY item and return the "
                    "COMPLETE corrected {\"video\": {...}} JSON:\n- " + "\n- ".join(berrs[:40])}]
    return vobj, berrs


def build_plan(segs, lines, scan_text, stream_len, cfg, ui=print, work=None, scan_rep=None, video_path=None):
    """Two-pass brain for mode "all". Returns (plan, errs). Uses brain._stream_any + the validator
    repair loop per pass. Saves every reply into work/ when given."""
    from . import brain as B
    from . import evidence as EV
    judge = cfg.get("judge_name", "Judge Boyd")
    # ---------- evidence (transcript signals now; the Pass A prompt cites them) ----------
    ev = None
    if (cfg.get("boundary") or {}).get("enabled", True) and video_path and Path(video_path).exists():
        try:
            ev = EV.build(video_path, segs, scan_rep or {"clusters": []}, cfg, work)
            cfg["_boundary_evidence"] = (
                "call-outs: " + "; ".join(f"{c['tc']}" for c in ev["call_outs"][:40]) + "\n" +
                "wrap-ups: " + "; ".join(f"{w['tc']} '{w['phrase']}'" for w in ev["wrap_up"][:40]) + "\n" +
                "rulings: " + "; ".join(f"{r['tc']} '{r['phrase']}'" for r in ev["ruling"][:40]))
        except Exception as e:  # noqa
            ui("evidence skipped:", e)
    # ---------- Pass A: inventory ----------
    # mock_passA_replies set -> Pass A replays a saved brain reply (resume) while Pass B stays live.
    # Hybrid: brain_pass_a (cheap) runs the inventory; brain_fallback takes over when it fails.
    pass_a_brain = ("mock" if cfg.get("mock_passA_replies")
                    else cfg.get("brain_pass_a") or cfg.get("brain", "anthropic"))
    cfg_a = dict(_provider_cfg(cfg, pass_a_brain), _cases_only=True,
                 _mock_queue=list(cfg.get("mock_passA_replies") or []))
    prompt_a = B.build_prompt(
        {"source_file": cfg["_source_file"], "stream_length": fmt_tc(stream_len, False),
         "channel_name": cfg.get("channel_name", ""), "judge_name": judge}, scan_text, lines, [], cfg_a)
    if work:
        (Path(work) / "prompt_A.txt").write_text(prompt_a, encoding="utf-8")
    plan, errs = _pass_a_loop(cfg_a, prompt_a, stream_len, segs, ui, work)
    fb = _fallback_for(cfg, pass_a_brain)
    if (plan is None or errs) and fb:
        ui(f"  Pass A on {pass_a_brain} failed ({(errs or ['no plan'])[0][:100]}) -> falling back to {fb}")
        cfg_a2 = dict(_provider_cfg(cfg, fb), _cases_only=True, _mock_queue=[])
        plan, errs = _pass_a_loop(cfg_a2, prompt_a, stream_len, segs, ui, work, tag="fb_")
        pass_a_brain = fb
    if plan is None or errs:
        return plan, errs or ["Pass A failed"]
    plan["pass_a_brain"] = pass_a_brain

    judge = plan.get("judge_name") or judge          # the brain confirms/corrects the judge from the transcript
    for c in plan.get("cases", []):                  # overlays are a PASS B deliverable in mode all
        c.pop("overlays", None)

    # ---------- boundary refinement (video signals may move OUT inside the window) ----------
    if ev:
        try:
            from . import boundary as BD
            BD.refine_plan(plan, ev, video_path, cfg, work, ui)
        except Exception as e:  # noqa
            ui("boundary refinement skipped:", e)

    # ---------- script step ----------
    used = rank_used(finalize_cases(plan, cfg))
    plan["cases"] = sorted(plan.get("cases", []), key=lambda c: parse_tc(c["in"]))
    if not used:
        return plan, ["no case reached the minimum length for its own video"]

    # ---------- Pass B: one packaging call per used case ----------
    # one shared reply queue in rank order: case A pops reply 1, case B pops reply 2, ...
    cfg["_mock_queue"] = list(cfg.get("mock_passB_replies") or [])
    videos = []
    for c in used:
        ui(f"  PASS B (packaging) #{c['rank']} {c['name']}...")
        pass_b_brain = cfg.get("brain_pass_b") or cfg.get("brain", "anthropic")
        pb = _provider_cfg(cfg, pass_b_brain)
        a, b = parse_tc(c["in"]), parse_tc(c["out"])
        prompt_b = case_prompt(c, pb, judge) + "\n\n" + "═" * 64 + \
            "\n TRANSCRIPT SLICE (this case only)\n" + "═" * 64 + "\n" + "\n".join(case_slice_lines(lines, a, b))
        vobj, berrs = _pass_b_loop(c, pb, prompt_b, plan, judge, stream_len, segs, cfg, ui, work)
        fb = _fallback_for(cfg, pass_b_brain)
        if (vobj is None or berrs) and fb:
            ui(f"  {c['name']}: {pass_b_brain} could not pass the validator -> retrying this case on {fb}")
            vobj, berrs = _pass_b_loop(c, _provider_cfg(cfg, fb), prompt_b, plan, judge, stream_len, segs, cfg,
                                       ui, work, tag="fb_")
            pass_b_brain = fb
        c["packaged_by"] = pass_b_brain
        if vobj is None or berrs:
            ui(f"  ! {c['name']} stays unrendered (needs_review) - see brain_reply_B_{c['id']}_*.txt")
            c["needs_review"] = True
            c["status"] = "skipped"
            c["reject_reason"] = "packaging failed validation - needs review"
            continue
        c["overlays"] = vobj.get("overlays") or []      # Pass B owns the final overlay list
        vobj.setdefault("case_ids", [c["id"]])
        vobj["n"] = c["rank"]
        vobj["rank"] = c["rank"]
        vobj["bridges"] = []
        vobj["title"] = next((t.get("text") for t in vobj.get("titles", []) if t.get("primary")), "")
        vobj["backup_title"] = next((t.get("text") for t in sorted(vobj.get("titles", []),
                                                                  key=lambda t: t.get("ctr_rank", 9))
                                     if not t.get("primary")), "")
        videos.append(vobj)
    plan["schema"] = "v10"
    plan["mode"] = "all"
    plan["judge_name"] = judge
    plan["videos"] = sorted(videos, key=lambda v: v["rank"])
    return plan, []


def write_ranking(plan, outroot, cfg, sid):
    """ranking.md + ranking.csv for every mode (rank = video order in bundle modes)."""
    by_id = {c["id"]: c for c in plan.get("cases", [])}
    vids = plan.get("videos", [])
    md = [f"# Ranking — {sid} — style: {cfg.get('style')} — mode: {cfg.get('mode')}"]
    rows = ["rank,folder,name,cause_no,in,out,length,score,why,confidence,title_karma,title_quote,"
            "title_number,title_twist,title_human,primary_style,thumbnail_text,publish_slot,status"]
    for v in vids:
        c = by_id[v["case_ids"][0]]
        titles = {t.get("style"): t.get("text") for t in v.get("titles", [])}
        prim = next((t for t in v.get("titles", []) if t.get("primary")), {})
        vir = (c.get("virality") or {})
        bd = (c.get("boundary") or {})
        folder = f"{v.get('rank', v.get('n', 0)):02d}_{c['name'].replace(' ', '_')}" \
            if cfg.get("mode") == "all" else f"Video_{v['n']:02d}_{c['name'].replace(' ', '_')}"
        md += ["", f"## #{v.get('rank', v.get('n'))}  {c['name']}  ({fmt_tc(c.get('_dur', 0), False)})  —  "
                   f"score {vir.get('total', 0)}/100",
               f"Why: {vir.get('why', '-')}", f"Folder: {folder}/",
               "Factors: " + " · ".join(f"{k} {vir.get('factors', {}).get(k, 0)}"
                                        for k in ("judge_confrontation", "emotion", "surprise_ruling", "numbers",
                                                  "topic_click", "completeness", "av_quality")),
               f"Boundary: IN {c['in']}  OUT {c['out']}  (confidence {bd.get('confidence', '-')})",
               f"Brain: cases by {plan.get('pass_a_brain', '-')} · packaging by {c.get('packaged_by', '-')}",
               "Titles:"]
        for i, t in enumerate(v.get("titles", [])):
            md.append(f"  {i + 1}. [{t.get('style')}]  {t.get('text')}"
                      + ("  ★ primary — " + t.get("primary_why", "") if t.get("primary") else ""))
        md.append(f"Thumbnail text: {(v.get('thumbnail') or {}).get('text', '-')}   |   "
                  f"Publish slot: {(v.get('publish') or {}).get('slot', '-')}")
        rows.append(",".join([
            str(v.get("rank", v.get("n", ""))), folder, c.get("name", ""), c.get("cause_no", ""),
            c.get("in", ""), c.get("out", ""), fmt_tc(c.get("_dur", 0), False), str(vir.get("total", 0)),
            (vir.get("why", "") or "").replace(",", ";"), str(bd.get("confidence", "")),
            titles.get("karma", ""), titles.get("quote", ""), titles.get("number", ""),
            titles.get("twist", ""), titles.get("human", ""), prim.get("style", ""),
            ((v.get("thumbnail") or {}).get("text", "") or "").replace(",", ";"),
            (v.get("publish") or {}).get("slot", ""), c.get("status", "used")]))
    skipped = [c for c in plan.get("cases", []) if c.get("status") == "skipped"]
    rejected = [c for c in plan.get("cases", []) if c.get("status") == "rejected"]
    if skipped:
        md += ["", "## Skipped (under the minimum)"] + [f"- {c['name']} {fmt_tc(c.get('_dur', 0), False)} "
                                                       f"({c['in']}-{c['out']})" for c in skipped]
    if rejected:
        md += ["", "## Rejected (pure procedure)"] + [f"- {c['name']} ({c['in']}-{c['out']})" for c in rejected]
    review = [c for c in plan.get("cases", []) if c.get("needs_review")]
    if review:
        md += ["", "## Needs review (packaging failed validation - NOT rendered)"] + \
              [f"- {c['name']} (see brain_reply_B_{c['id']}_*.txt)" for c in review]
    outroot.mkdir(parents=True, exist_ok=True)
    (outroot / "ranking.md").write_text("\n".join(md), encoding="utf-8")
    (outroot / "ranking.csv").write_text("\ufeff" + "\n".join(rows), encoding="utf-8")
