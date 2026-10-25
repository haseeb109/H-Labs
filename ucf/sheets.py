"""BLOCK 1 (EDIT SHEET) and BLOCK 2 (METADATA) text, generated from the plan + the real timeline."""
import textwrap

from . import timeline as TL
from . import vo as V
from .timeutil import parse_tc, fmt_tc, fmt_dur, fmt_chapter

PKT = {"9am ET": "6pm PKT summer / 7pm winter", "1pm ET": "10pm PKT summer / 11pm winter",
       "6pm ET": "3am PKT next day summer / 4am winter"}


def midrolls(video, by_id, tl):
    seams = list(tl["seams"])
    total = tl["total"]
    pts = []
    if seams:
        # at most 3, spread
        if len(seams) > 3:
            step = len(seams) / 3.0
            seams = [seams[int(i * step)] for i in range(3)]
        pts = seams
    else:
        c = by_id[video["case_ids"][0]]
        rul = None
        if c.get("ruling_tc"):
            rul = TL.src_to_out(tl, c["id"], parse_tc(c["ruling_tc"]))
        t = 8 * 60.0
        while t < total - 120 and len(pts) < 4:
            if rul is not None and abs(t - rul) < 45:
                t = rul + 60
            pts.append(t)
            t += 8 * 60.0
    return pts


def chapters(video, by_id, tl):
    out = []
    for ch in video["chapters"]:
        cid = TL.find_case_for_tc(video, by_id, parse_tc(ch["tc"]))
        o = TL.src_to_out(tl, cid, parse_tc(ch["tc"])) if cid else None
        if o is not None:
            out.append((o, ch["label"]))
    if out:
        out[0] = (0.0, out[0][1])        # chapter list must start at 00:00 (hook+intro sit in the first chapter)
    # YouTube needs >=10 s between chapters
    clean = []
    for o, l in out:
        if clean and o - clean[-1][0] < 10:
            continue
        clean.append((o, l))
    return clean


def _card_lines(case, n, total, kind):
    if kind == "intro":
        L = [f"CASE {n} OF {total}", case["name"].upper()]
        if case.get("cause_no"):
            L.append(f"Cause No. {case['cause_no']}")
        L += [f"CHARGE        {case['charge']}", f"FACING        {case['facing']}", f"THE QUESTION  {case['question']}"]
    else:
        r = case["result"]
        L = [f"CASE {n} — THE RULING", case["name"].upper(), f"SENTENCE    {r['sentence']}",
             f"CONDITIONS  {r['conditions']}"]
    return ["     " + x for x in L]


def _case_box(c):
    rows = [("WHAT IT IS", c.get("what_it_is", "")), ("CHARGE", c.get("charge", "")), ("THE STORY", c.get("story", "")),
            ("ROOT AGAINST", c.get("root_against", "")),
            ("THE MOMENT", f"{c.get('moment', '')} ({c.get('moment_tc', '')})"),
            ("ENDS ON", c.get("ends_on", ""))]
    out = ["┌─ CASE " + str(c["id"]) + " ─" + "─" * 52,
           f"│ {c['name']}   Cause No. {c.get('cause_no', '')}"]
    for k, v in rows:
        wrapped = textwrap.wrap(v, 62) or [""]
        out.append(f"│ {k:<13}{wrapped[0]}")
        for w in wrapped[1:]:
            out.append("│ " + " " * 13 + w)
    out.append("└" + "─" * 62)
    return "\n".join(out)


def edit_sheet_tt(plan, video, tl, durs):
    """Edit sheet for the locked Trial Tales structure."""
    by_id = {c["id"]: c for c in plan["cases"]}
    ids = video["case_ids"]
    L = ["╔" + "═" * 62 + "╗", "║  EDIT SHEET — TRIAL TALES LOCKED STYLE",
         f"║  VIDEO {video['n']} · {fmt_dur(tl['total'])} · source: {plan['source_file']}", "╚" + "═" * 62 + "╝\n"]
    hk = video["hook"]
    L.append(f"▶️ HOOK — source {hk['in']}–{hk['out']} ({parse_tc(hk['out']) - parse_tc(hk['in']):.0f} s), no logo, label 'In This Case'")
    L.append(f"   Bottom headline: \"{hk.get('headline', '')}\"")
    L.append(f"   Spoken: \"{hk.get('spoken_actual') or hk.get('spoken', '')}\"\n")
    L.append(f"▶️ CHANNEL INTRO — your gavel animation ({durs.get('intro', 7.47):.1f} s)\n")
    brs = {b["after_case_id"]: b for b in video.get("bridges", [])}
    for i, cid in enumerate(ids):
        c = by_id[cid]
        L.append(_case_box(c))
        a, b = parse_tc(c["in"]), parse_tc(c["out"])
        lab = "CASE STARTED (lime)" if i == 0 else f"'{['1st','2nd','3rd'][i] if i < 3 else str(i + 1) + 'th'} Case' (red bar)"
        L.append(f"▶️ CASE {i + 1} — play {c['in']} to {c['out']}  ({fmt_dur(b - a)})   label: {lab}")
        for rr in TL.removes(c):
            L.append(f"   REMOVE: {fmt_tc(rr[0])} to {fmt_tc(rr[1])}")
        if i < len(ids) - 1:
            br = brs[cid]
            L.append(f"▶️ AI RECAP (blurred strip, ≤18 s clips) after case {i + 1}:")
            L.append(f"   \"{br['text']}\"   ({V.n_words(br['text'])} words)")
        L.append("")
    L.append("▶️ CLOSING RECAP (blurred strip, split into ≤18 s clips, fade to black):")
    L.append(f"   \"{video['vo_final']['text']}\"   ({V.n_words(video['vo_final']['text'])} words)\n")
    mr = midrolls(video, by_id, tl)
    L.append("▶️ MID-ROLLS — " + " · ".join(fmt_tc(t, False) for t in mr) + "  (on the seams between cases)\n")
    th = video["thumbnail"]
    L.append(f"▶️ THUMBNAIL — screenshot inside {th['window_in']}–{th['window_out']}: \"{th['text']}\" (gold: {th['gold_word']}, {th['placement']} third)")
    L.append(f"QUIZ (pinned comment): {video['quiz'].get('question', '')}")
    L.append(f"\nRUNTIME: {fmt_dur(tl['total'])}")
    return "\n".join(L)


def edit_sheet(plan, video, tl, durs):
    if not any(s["kind"] == "vo1" for s in tl["segments"]):
        return edit_sheet_tt(plan, video, tl, durs)
    by_id = {c["id"]: c for c in plan["cases"]}
    ids = video["case_ids"]
    n_cases = len(ids)
    L = []
    L.append("╔" + "═" * 62 + "╗")
    L.append(f"║  BLOCK 1 — EDIT SHEET")
    L.append(f"║  VIDEO {video['n']} · {fmt_dur(tl['total'])} · source: {plan['source_file']}")
    L.append("╚" + "═" * 62 + "╝\n")
    hk = video["hook"]
    hd = parse_tc(hk["out"]) - parse_tc(hk["in"])
    L.append(f"▶️ HOOK — play {hk['in']} to {hk['out']}   ({hd:.0f} sec)")
    L.append(f"   Spoken: \"{hk.get('spoken_actual') or hk.get('spoken', '')}\"")
    L.append("   No voiceover.\n")
    L.append(f"▶️ CHANNEL INTRO ANIMATION — {durs.get('intro', video.get('intro_seconds', 6)):.0f} sec")
    L.append("   No voiceover.\n")
    c1 = by_id[ids[0]]
    L.append(f"▶️ VO-1 — read over the opening of Case 1:")
    L.append(f"   \"{video['vo1']['text']}\"   ({V.n_words(video['vo1']['text'])} words)")
    L.append(f"   CARD: INTRO · blur footage from {c1['in']}–{fmt_tc(parse_tc(c1['in']) + durs.get('vo1', 12))} of this case")
    L += _card_lines(c1, 1, n_cases, "intro")
    L.append("")
    brs = {b["after_case_id"]: b for b in video.get("bridges", [])}
    for i, cid in enumerate(ids):
        c = by_id[cid]
        L.append(_case_box(c))
        L.append("")
        a, b = parse_tc(c["in"]), parse_tc(c["out"])
        L.append(f"▶️ CASE {i + 1} — play {c['in']} to {c['out']}   ({c['out']} − {c['in']} = {fmt_dur(b - a)})")
        for rr in TL.removes(c):
            L.append(f"   REMOVE: {fmt_tc(rr[0])} to {fmt_tc(rr[1])}")
        L.append("")
        if i < n_cases - 1:
            br = brs[cid]
            nxt = by_id[ids[i + 1]]
            L.append(f"▶️ VO-BRIDGE — read between Case {i + 1} and Case {i + 2}:")
            L.append(f"   \"{br['text']}\"   ({V.n_words(br['text'])} words)")
            L.append(f"   CARD 1: RESULT · blur footage from the end of Case {i + 1}")
            L += _card_lines(c, i + 1, n_cases, "result")
            L.append(f"   CARD 2: INTRO · blur footage from the start of Case {i + 2}")
            L += _card_lines(nxt, i + 2, n_cases, "intro")
            L.append("")
    last = by_id[ids[-1]]
    L.append("▶️ VO-FINAL — read over the closing frames:")
    L.append(f"   \"{video['vo_final']['text']}\"   ({V.n_words(video['vo_final']['text'])} words)")
    L.append(f"   CARD: RESULT · blur footage from the end of the last case")
    L += _card_lines(last, n_cases, n_cases, "result")
    L.append("")
    fin = tl["segments"][-1]["dur"]
    L.append(f"▶️ QUIZ CARD — on screen for the last {fin:.0f} sec. Text in Block 2.\n")
    mr = midrolls(video, by_id, tl)
    L.append("▶️ MID-ROLLS — " + " · ".join(fmt_tc(t, False) for t in mr))
    L.append("   Place on the seams between cases. Never inside a ruling.\n")
    th = video["thumbnail"]
    L.append(f"▶️ THUMBNAIL — screenshot anywhere in {th['window_in']}–{th['window_out']}")
    L.append(f"   Look for: {th.get('look_for', '')}. Reject any neutral face.")
    L.append(f"   TEXT ON THUMB:  \"{th['text']}\"")
    L.append(f"   GOLD WORD:      {th['gold_word']}")
    L.append(f"   PLACEMENT:      {th['placement']} third\n")
    cases_total = sum(TL.case_len(by_id[i]) for i in ids)
    L.append(f"RUNTIME: hook {hd:.0f} sec + intro {durs.get('intro', 6):.0f} sec + cases {fmt_dur(cases_total)} "
             f"+ VO/cards = {fmt_dur(tl['total'])}")
    return "\n".join(L)


def metadata(plan, video, tl, cfg, source_url=""):
    by_id = {c["id"]: c for c in plan["cases"]}
    d = video["description"]
    chs = chapters(video, by_id, tl)
    L = []
    L.append("╔" + "═" * 62 + "╗")
    L.append("║  BLOCK 2 — METADATA")
    L.append(f"║  VIDEO {video['n']}")
    L.append("╚" + "═" * 62 + "╝\n")
    titles = video.get("titles") or []
    if titles:
        L.append("TITLES  (\u2605 = upload with this one; swap to #2 at 48 h if CTR < 5%)")
        for i, t in enumerate(titles, 1):
            star = "\u2605" if t.get("primary") else " "
            L.append(f"{star} {i}. [{t.get('style')}]  {t.get('text')}")
        L.append("")
    L.append("TITLE\n" + video["title"] + "\n")
    L.append("BACKUP TITLE  (swap at 48h if CTR under 5%)\n" + video["backup_title"] + "\n")
    desc = [d["first_line"], "", d["what_happens"], ""]
    if d.get("pending_note"):
        desc += [d["pending_note"], ""]
    desc += [d["search_question"], d["answer"], "", "Chapters:"]
    desc += [f"{fmt_chapter(o)} {l}" for o, l in chs]
    desc += ["", d["related_question"], "", "Educational content. Not legal advice."]
    credit = cfg.get("source_credit", "").replace("{source_url}", source_url)
    if credit:
        desc += ["", credit]
    L.append("DESCRIPTION\n" + "\n".join(desc) + "\n")
    tags, seen = [], set()
    for t in cfg["base_tags"] + video.get("tags", []):
        k = t.strip().lower()
        if k and k not in seen:
            seen.add(k)
            tags.append(k)
    line = ""
    for t in tags:
        nxt = (line + ", " + t) if line else t
        if len(nxt) > 480:
            break
        line = nxt
    L.append("TAGS  (paste as one line)\n" + line + "\n")
    L.append("PINNED COMMENT\n" + video["pinned_comment"] + "\n")
    L.append("COMMUNITY POST  (T+2h)\n" + video["community_post"] + "\n")
    q = video["quiz"]
    L.append("QUIZ  (on screen at the end)\n" + q["question"])
    for k in "ABC":
        L.append(f"  {k}) {q['options'][k]}")
    L.append(f"Answer: {q.get('answer') or 'left open — answer in the comments'}\n")
    slot = video["publish"]["slot"]
    L.append(f"PUBLISH\n{slot}  =  {PKT.get(slot, '')}\nSchedule it — do not publish live.")
    fu = video.get("followup_owed")
    if isinstance(fu, str):
        fu = {"case": fu}
    if fu:
        L.append(f"\nFOLLOW-UP OWED\n{fu.get('case', '')} · ruling expected {fu.get('ruling_expected', '')}")
    return "\n".join(L), chs
