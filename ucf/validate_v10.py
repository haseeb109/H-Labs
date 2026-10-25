"""v10 validator groups: titles (T), overlays (O), case phases/virality (C), boundary (B).
Called from ucf/validate.py when title_system == "v10" / new plan fields are present.
Every error message carries its rule code (T-04, O-02, ...) so repair loops and reports are searchable."""
import re

from .timeutil import parse_tc, fmt_tc

ACRONYMS = {"DWI", "DUI", "DNA", "USA", "TV", "CPS", "ICE", "FBI", "DA", "AI", "MRI", "THC", "PTSD", "OMG",
            "HEB", "CR", "TX", "ER", "ID", "GPS", "AR", "CEO", "PSI", "BAC"}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
TITLE_STYLES = {"karma", "quote", "number", "twist", "human", "twist_fallback"}
_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
MULTI = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}


def _words(t):
    return [w for w in re.findall(r"[a-z']+", (t or "").lower()) if w]


def extract_numbers(text):
    """Canonical numeric values mentioned in `text`: digits (13, $30,000, 30K) and number words
    (thirteen, thirty thousand, two thousand nineteen). Returns a set of ints >= 1."""
    vals = set()
    t = (text or "").lower().replace(",", "")
    # digits + word multiplier ("30 thousand", "2.5 million") -> composed digits
    t = re.sub(r"(\d+(?:\.\d+)?)\s+(thousand|million|hundred)\b",
               lambda m: str(float(m.group(1)) * {"hundred": 100, "thousand": 1000, "million": 1_000_000}[m.group(2)]), t)
    for m in re.finditer(r"\$\s?(\d+(?:\.\d+)?)\s?([km])?\b|\b(\d+(?:\.\d+)?)\s?([km])?\b", t):
        v = float(m.group(3) or m.group(1))
        mul = (m.group(4) or m.group(2) or "").lower()
        if mul in ("k", "thousand"):
            v *= 1_000
        elif mul in ("m", "million"):
            v *= 1_000_000
        if v >= 1:
            vals.add(int(v))
    words = _words(t)
    i = 0
    while i < len(words):
        if words[i] in _ONES or words[i] in MULTI:
            acc, cur = 0, 0
            while i < len(words) and (words[i] in _ONES or words[i] in MULTI):
                w = words[i]
                if w in _ONES:
                    cur += _ONES[w]
                elif w == "hundred":
                    cur = (cur or 1) * 100
                else:
                    acc += (cur or 1) * MULTI[w]
                    cur = 0
                i += 1
            v = acc + cur
            if v >= 1:
                vals.add(int(v))
        else:
            i += 1
    return vals


def numbers_in_title_ok(title, case_text):
    """T-07: every number in the title must exist in the case transcript."""
    tvals = extract_numbers(title)
    if not tvals:
        return True, []
    cvals = extract_numbers(case_text)
    missing = [v for v in sorted(tvals) if v not in cvals]
    return not missing, missing


def _tokset(t):
    return {w for w in _words(t) if len(w) > 2}


def difflib_ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def quote_in_transcript(quote, case_text):
    """T-08 / O-06: a quoted span must fuzzy-match the transcript (token-set ratio >= 0.85)."""
    qtok = _tokset(quote)
    if not qtok:
        return True
    for line in re.split(r"[.!?]|\s+\|\s+", case_text or ""):
        ltok = _tokset(line)
        if not ltok:
            continue
        inter = len(qtok & ltok)
        if inter / max(len(qtok), 1) >= 0.85 or inter / max(len(ltok), 1) >= 0.85:
            return True
        if difflib_ratio(" ".join(sorted(qtok)), " ".join(sorted(ltok))) >= 0.85:
            return True
    return False


def _caps_words(t):
    """All-caps EMPHASIS PHRASES: consecutive caps tokens count as one bank verb ("SHUTS DOWN")."""
    out, run = [], []
    for w in re.findall(r"[A-Za-z][A-Za-z'’]+", t or ""):
        if len(w) >= 3 and w.isupper() and w not in ACRONYMS:
            run.append(w)
        elif run:
            out.append(" ".join(run))
            run = []
    if run:
        out.append(" ".join(run))
    return out


def _caps_in_template_ok(caps_word, style, banks):
    power = {w.upper() for w in banks.get("power", [])}
    emph = {w.upper() for w in banks.get("emphasis", [])}
    if style == "karma":
        return caps_word in power or any(caps_word.startswith(w) for w in power)
    return caps_word in power or caps_word in emph or any(caps_word.startswith(w) for w in list(power) + list(emph))


def parse_banks(title_rules_text):
    """Pull POWER-VERB BANK / EMPHASIS LIST / HOOK WORDS lists out of a style's title_rules.md (line-based)."""
    banks = {"power": [], "emphasis": [], "hook": []}
    cur = None
    for line in (title_rules_text or "").splitlines():
        s = line.strip()
        if s.startswith("POWER-VERB BANK"):
            cur = "power"
        elif s.startswith("EMPHASIS LIST"):
            cur = "emphasis"
        elif s.startswith("HOOK WORDS"):
            cur = "hook"
        elif cur and "·" in line:
            banks[cur] += [w.strip().lower() for w in line.split("·") if w.strip()]
        elif s and not s.startswith(("·", "-")):
            cur = None
    return banks


def check_titles_v10(video, case, case_text, judge, banks, E, W):
    """Group T — five titles, all hard rules. case_text = the case's transcript slice."""
    v = f"video {video.get('n', '?')}"
    titles = video.get("titles") or []
    styles = [t.get("style") for t in titles]
    base = [s for s in styles if s != "twist_fallback"]
    ok_set = len(styles) == 5 and set(styles) <= TITLE_STYLES and (
        set(base) == {"karma", "quote", "number", "twist", "human"}
        or (styles.count("twist_fallback") == 1 and "twist" not in styles
            and set(base) == {"karma", "quote", "number", "human"}))
    if not ok_set:
        allowed = " / ".join(sorted(TITLE_STYLES))
        E.append(f"{v}: T-01 need exactly 5 titles, one per style ({allowed}); got {styles}")
        return
    if sum(1 for t in titles if t.get("primary")) != 1:
        E.append(f"{v}: T-10 exactly one title must have primary: true")
    ranks = sorted(t.get("ctr_rank") for t in titles)
    if ranks != [1, 2, 3, 4, 5]:
        E.append(f"{v}: T-10 ctr_rank must be 1-5 and unique, got {ranks}")
    jlow = (judge or "").lower().strip()
    seen_first3, seen_sets = [], []
    for t in titles:
        st, tx = t.get("style"), (t.get("text") or "").strip()
        w = f"{v} [{st}]"
        if not tx:
            E.append(f"{w}: T-01 title text is empty")
            continue
        if st == "twist_fallback" and not t.get("reason"):
            E.append(f"{w}: T-01 twist_fallback needs a 'reason' (why this case has no real turn)")
        nch, nw = len(tx), len(_words(tx))
        if not (65 <= nch <= 95):
            E.append(f"{w}: T-02 is {nch} characters (65-95, hard max 100): {tx!r}")
        if not (8 <= nw <= 15):
            W.append(f"{w}: T-02 is {nw} words (aim 8-15)")
        hook40 = tx[:40].lower()
        banks_hook = any(h in hook40 for h in banks.get("hook", []))
        if not (re.search(r"\d", hook40) or '"' in tx[:40] or _caps_words(tx[:40]) or banks_hook):
            E.append(f"{w}: T-11 the first 40 characters carry no hook (bank word / number / quote / CAPS): {tx[:40]!r}")
        njudge = len(re.findall(re.escape(jlow), tx.lower())) if jlow else 0
        if njudge != 1:
            E.append(f"{w}: T-03 judge name {judge!r} must appear exactly once, found {njudge}: {tx!r}")
        caps = _caps_words(tx)
        if len(caps) != 1:
            E.append(f"{w}: T-04 exactly ONE all-caps emphasis word, found {caps}: {tx!r}")
        elif not _caps_in_template_ok(caps[0], "karma" if st in ("karma", "twist_fallback") else st, banks):
            E.append(f"{w}: T-04 CAPS word {caps[0]} is not in this style pack's banks")
        if tx.count(" — ") > 1 or tx.count(" | ") > 1 or ":" in tx or "?" in tx or EMOJI.search(tx):
            E.append(f"{w}: T-05 separators/punctuation (max one ' — ', max one ' | ', no colon/question/emoji): {tx!r}")
        if "*" in tx and not re.search(r"[A-Za-z]\*", tx):
            E.append(f"{w}: T-05 asterisk only to censor inside a word: {tx!r}")
        if re.search(r"\bgets? (?:probation|prison|\d+\s*years?)\b|\bfound guilty\b|\bsentenced\b"
                     r"|\bgoes? to (?:prison|jail)\b|\b\d+\s*years? (?:in|behind) (?:prison|jail)\b", tx.lower()):
            E.append(f"{w}: T-06 title reveals the verdict - tease it, never state it: {tx!r}")
        ok, missing = numbers_in_title_ok(tx, case_text)
        if not ok:
            E.append(f"{w}: T-07 numbers {missing} not found in this case's transcript")
        for q in re.findall(r'"([^"]{4,})"', tx):
            if not quote_in_transcript(q, case_text):
                E.append(f"{w}: T-08 quote {q!r} does not match this case's transcript")
        first3 = " ".join(_words(tx)[:3])
        if first3 in seen_first3:
            E.append(f"{w}: T-09 two titles start with the same three words ('{first3}')")
        seen_first3.append(first3)
        tset = _tokset(tx)
        for prev in seen_sets:
            inter = len(tset & prev)
            j = inter / max(len(tset | prev), 1)
            if j >= 0.6:
                E.append(f"{w}: T-09 two titles are too similar (Jaccard {j:.2f})")
        seen_sets.append(tset)
        if case.get("name"):
            surname = [x for x in re.split(r"\s+", case["name"].strip().lower()) if len(x) >= 4]
            if surname and surname[-1] in tx.lower():
                E.append(f"{w}: T-12 title contains the defendant's surname ('{surname[-1]}') - use roles/pronouns")
    th = video.get("thumbnail") or {}
    prim = next((t.get("text") for t in titles if t.get("primary")), "")
    ttx = (th.get("text") or "")
    if prim and ttx and ttx.lower() in prim.lower():
        E.append(f"{v}: T-13 thumbnail text repeats the primary title - it must ADD information")


def check_overlays(case, segs, cfg, E, W):
    """Group O — overlay timing/truth rules for one used case."""
    cid = case.get("id")
    ovs = case.get("overlays") or []
    if not ovs:
        return 0
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    case_len = b - a
    ocfg = cfg.get("overlays") or {}
    look = "ov" if cfg.get("_look") == "ov" else "tt"
    kinds = {"fact", "coming_up", "so_far", "watch", "verdict_q"} | ({"take"} if look == "ov" else set())
    ctext = " ".join(s["text"] for s in segs if a - 1 <= s["start"] <= b + 1) if segs else ""
    prev_kind, prev_tc = None, None
    for o in ovs:
        kind = o.get("kind")
        w = f"case {cid} overlay {o.get('tc')} ({kind})"
        if kind not in kinds:
            E.append(f"{w}: O-01 kind not allowed in this look")
            continue
        try:
            tc = parse_tc(o.get("tc"))
        except Exception:
            E.append(f"{w}: O-02 bad tc {o.get('tc')!r}")
            continue
        if not (a + 40 <= tc <= b - 30):
            E.append(f"{w}: O-02 tc must be >=40 s after IN and >=30 s before OUT ({fmt_tc(a)}-{fmt_tc(b)})")
        if o.get("ref_tc"):
            try:
                rt = parse_tc(o["ref_tc"])
                if kind == "coming_up" and not (tc + 45 <= rt <= b):
                    E.append(f"{w}: O-05 coming_up ref_tc must be >=45 s later, inside the same case")
            except Exception:
                E.append(f"{w}: O-05 bad ref_tc {o.get('ref_tc')!r}")
        maxw = 26 if kind == "take" else int(ocfg.get("max_words", 20))
        nww = len((o.get("text") or "").split())
        if nww > maxw:
            E.append(f"{w}: O-04 text is {nww} words (max {maxw})")
        txt = o.get("text") or ""
        if EMOJI.search(txt) or ("?" in txt and kind != "verdict_q"):
            E.append(f"{w}: O-04 emoji / question mark outside verdict_q")
        if prev_tc is not None and tc - prev_tc < float(ocfg.get("min_gap_s", 180)):
            E.append(f"{w}: O-03 overlays less than min_gap_s apart ({fmt_tc(prev_tc)} -> {fmt_tc(tc)})")
        if prev_kind == kind:
            E.append(f"{w}: O-07 two {kind} overlays in a row")
        ev = o.get("evidence") or ""
        if ev and ctext and not quote_in_transcript(ev, ctext):
            E.append(f"{w}: O-06 evidence quote not found in the case transcript")
        prev_kind, prev_tc = kind, tc
    exp = max(1, int(case_len // float(ocfg.get("every_s", 270)))) if case_len >= 240 else 0
    if abs(len(ovs) - exp) > 1:
        E.append(f"case {cid}: O-03 expected ~{exp} overlays for {fmt_tc(case_len)} of case, got {len(ovs)}")
    if case_len >= 480 and not any(o.get("kind") == "coming_up" for o in ovs):
        E.append(f"case {cid}: O-07 an 8:00+ case needs at least one coming_up overlay")
    return len(ovs)


def check_case_v10(case, cfg, E, W):
    """Group C additions for one case (phases, virality, interrupted). Call-inside C-04 needs segs -> caller."""
    cid = case.get("id")
    mode = cfg.get("mode")
    if case.get("status") not in ("used", "skipped"):
        return
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    phases = case.get("phases") or []
    if case.get("status") == "used":
        if not phases:
            E.append(f"case {cid}: C-02 phases missing (call/ruling/wrap_up with tc + evidence quotes)")
        else:
            last = -1.0
            for p in phases:
                try:
                    t = parse_tc(p.get("tc"))
                except Exception:
                    E.append(f"case {cid}: C-02 bad phase tc {p.get('tc')!r}")
                    continue
                if t < last:
                    E.append(f"case {cid}: C-02 phases must be monotonic ({p.get('phase')} at {p.get('tc')})")
                if not (a <= t <= b):
                    E.append(f"case {cid}: C-02 phase {p.get('phase')} at {p.get('tc')} sits outside the case range")
                if len((p.get("evidence") or "").split()) > 14:
                    W.append(f"case {cid}: C-02 phase evidence should be a <=12-word verbatim quote")
                last = t
            ruling = next((p for p in phases if p.get("phase") == "ruling"), None)
            if ruling and not case.get("ruling_deferred") and parse_tc(ruling["tc"]) > b - 3:
                E.append(f"case {cid}: C-03 ruling phase must be at least 3 s before OUT")
    if mode == "all" and case.get("status") == "used":
        vir = case.get("virality") or {}
        f = vir.get("factors") or {}
        ranges = {"judge_confrontation": (0, 20), "emotion": (0, 20), "surprise_ruling": (0, 20), "numbers": (0, 10),
                  "topic_click": (0, 15), "completeness": (0, 10), "av_quality": (0, 5)}
        for k, (lo, hi) in ranges.items():
            v = f.get(k)
            if not isinstance(v, (int, float)) or not (lo <= v <= hi):
                E.append(f"case {cid}: C-09 virality.{k} missing or outside {lo}-{hi}")
        if not (vir.get("why") or "").strip():
            E.append(f"case {cid}: C-09 virality.why missing")
    if case.get("interrupted"):
        segs_ = case.get("segments") or []
        if not segs_:
            E.append(f"case {cid}: C-08 interrupted:true needs segments[]")
        else:
            try:
                parsed = sorted((parse_tc(s["in"]), parse_tc(s["out"])) for s in segs_)
                for (s1a, s1b), (s2a, s2b) in zip(parsed, parsed[1:]):
                    if s2a < s1b:
                        E.append(f"case {cid}: C-08 segments overlap")
            except Exception:
                E.append(f"case {cid}: C-08 bad segment timecodes")


def virality_total(case):
    """Script-computed virality total (never trust a brain-written total). Penalties per spec 5.2."""
    f = (case.get("virality") or {}).get("factors") or {}
    total = sum(f.get(k, 0) for k in ("judge_confrontation", "emotion", "surprise_ruling", "numbers",
                                      "topic_click", "completeness", "av_quality"))
    if (case.get("monetisation") or "").upper() == "LIMITED":
        total -= 15
    if case.get("ruling_deferred") or case.get("verdict_pending"):
        total -= 10
    return total


def virality_tiebreak(case):
    f = (case.get("virality") or {}).get("factors") or {}
    return (f.get("surprise_ruling", 0) + f.get("judge_confrontation", 0),
            case.get("_dur", 0), -parse_tc(case["in"]))
