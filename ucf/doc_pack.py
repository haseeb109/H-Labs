"""Documentary styles: make ONE case's packaging reply safe to render, whatever the brain left out (2026-11-24).

The documentary renderer (ucf/render_doc.py) falls back for every "doc" field, but the rest of the run reads the classic
video fields: the voice-over counter, the thumbnail, the edit sheet and metadata.txt (title, description, quiz, pinned
comment, publish slot). A cheap brain often leaves some of them out - before this, that cost the whole case (validator) or
failed a finished video at the metadata step. sanitize() repairs the reply IN PLACE from the case's own (validated) fields
and returns what it changed, so the plan report can say so. minimal() is the reply when the brain gave no JSON at all.
"""
import re

from .timeutil import fmt_tc, parse_tc
from .validate import _doc_fill_vo, names_other, _clean_name


def _tc(x):
    try:
        return parse_tc(x)
    except (TypeError, ValueError, KeyError, AttributeError):
        return None


def _text(x):
    if isinstance(x, dict):
        x = x.get("text", "")
    return re.sub(r"\s+", " ", str(x or "")).strip()


def _sentence(t, n=200):
    t = _text(t)
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


def _hook_window(case):
    """A 12 s window in the back half of the case: the ruling if known, else the moment, else 70% in."""
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    ph = {p.get("phase"): p for p in (case.get("phases") or []) if isinstance(p, dict)}
    for t in (_tc((ph.get("ruling") or {}).get("tc")), _tc(case.get("ruling_tc")), _tc(case.get("moment_tc"))):
        if t is not None and a + 0.4 * (b - a) <= t <= b - 3:
            s = max(a + 0.4 * (b - a), t - 3)
            return s, min(b, s + 12)
    s = a + 0.7 * (b - a)
    return s, min(b, s + 12)


def _strs(x):
    """'a' | ['a', {"text": 'b'}] -> ['a', 'b'] (empty items dropped)."""
    if isinstance(x, (str, dict)):
        x = [x]
    return [t for t in (_text(i) for i in (x if isinstance(x, list) else [])) if t]


def _dicts(x, text_key="text"):
    """list of dicts; a bare string becomes {text_key: string}; anything else is dropped."""
    if isinstance(x, (str, dict)):
        x = [x]
    out = []
    for i in x if isinstance(x, list) else []:
        if isinstance(i, str) and i.strip():
            out.append({text_key: i.strip()})
        elif isinstance(i, dict):
            out.append(i)
    return out


def doc_shapes(d):
    """The documentary fields in the shapes the renderer reads (a cheap brain mixes strings, dicts and lists).
    -> number of fields reshaped."""
    n = 0

    def put(k, v):
        nonlocal n
        if d.get(k) != v:
            d[k] = v
            n += 1
    for k in ("profile", "questions", "answers", "bridges", "earlier_bridges"):
        if k in d:
            put(k, _strs(d[k]))
    for k in ("backstory", "cold_open", "rulings", "turns", "replays"):
        if k in d:
            put(k, _dicts(d[k]))
    if "chapters" in d:
        chs = []
        for c in _dicts(d["chapters"], "title"):
            c = dict(c)
            if "at" not in c and c.get("tc"):
                c["at"] = c["tc"]
            if not c.get("title") and c.get("label"):
                c["title"] = c["label"]
            chs.append(c)
        put("chapters", chs)
    for b in d.get("backstory") or []:
        if "tags" in b:
            b["tags"] = _strs(b["tags"])
        if "pills" in b:
            b["pills"] = _strs(b["pills"])
    if "impact_quote" in d and not isinstance(d["impact_quote"], dict):
        put("impact_quote", {"text": _text(d["impact_quote"])} if _text(d["impact_quote"]) else {})
    for k in ("tease", "stamp", "tagline", "verdict_big", "episode_title", "episode_summary", "cliffhanger", "date",
              "charge_level", "backstory_text"):
        if k in d and not isinstance(d[k], str):
            put(k, _text(d[k]) if isinstance(d[k], (dict, str)) else " ".join(_strs(d[k])))
    if "board" in d:
        bd = d["board"] if isinstance(d["board"], dict) else {}
        items = [i for i in _dicts(bd.get("items"), "label") if _text(i.get("label"))]
        for k, it in enumerate(items):
            it.setdefault("id", f"i{k}")
            it["id"], it["label"] = str(it["id"]), _text(it["label"])
        ids = {it["id"] for it in items}
        links = []
        for ln in bd.get("links") or []:
            if isinstance(ln, dict):
                ln = [ln.get("from") or ln.get("a"), ln.get("to") or ln.get("b"), ln.get("label") or ln.get("why") or ""]
            if isinstance(ln, list) and len(ln) >= 2 and str(ln[0]) in ids and str(ln[1]) in ids:
                links.append([str(ln[0]), str(ln[1]), _text(ln[2]) if len(ln) > 2 else ""])
        put("board", {"items": items, "links": links} if items else {})
    for r in d.get("replays") or []:
        marks = []
        for m in r.get("marks") or [] if isinstance(r.get("marks"), list) else []:
            try:
                if isinstance(m, dict) and 0 <= float(m.get("x")) <= 1 and 0 <= float(m.get("y")) <= 1:
                    marks.append(m)
            except (TypeError, ValueError):
                continue
        r["marks"] = marks
    return n


def minimal(case):
    """The reply when the brain gave nothing usable: every field from the case itself."""
    return {"case_ids": [case["id"]], "doc": {}, "_auto": True}


def sanitize(v, case, all_cases, segs=None, cfg=None):
    """Repair one documentary video object in place. -> [notes] (what was filled or dropped)."""
    notes = []
    cfg = cfg or {}
    a, b = parse_tc(case["in"]), parse_tc(case["out"])
    name = case.get("name") or "the defendant"
    charge = case.get("charge") or case.get("what_it_is") or "the charge"
    res = case.get("result") if isinstance(case.get("result"), dict) else {}
    v["case_ids"] = [case["id"]]
    v["bridges"] = []
    if not isinstance(v.get("doc"), dict):
        v["doc"] = {}
    if doc_shapes(v["doc"]):
        notes.append("documentary fields reshaped (strings / lists the renderer could not read)")
    for k in ("vo1", "vo_final"):
        if isinstance(v.get(k), str):
            v[k] = {"text": v[k]}
    # ---- hook: must be real footage of THIS case (the cold open falls back to it)
    hk = v.get("hook") if isinstance(v.get("hook"), dict) else {"headline": _text(v.get("hook"))}
    ha, hb = _tc(hk.get("in")), _tc(hk.get("out"))
    if ha is None or hb is None or not (a <= ha < hb <= b + 1) or not (4 <= hb - ha <= 25):
        ha, hb = _hook_window(case)
        hk.update({"in": fmt_tc(ha, False), "out": fmt_tc(hb, False)})
        notes.append("hook window set from the ruling / case moment")
    hk.setdefault("headline", _sentence(case.get("moment") or charge, 60))
    v["hook"] = hk
    v.setdefault("intro_seconds", 6)
    # ---- voice-over: never another defendant's name, never empty
    mine = set(_clean_name(name).split())
    others = [c for c in all_cases if c.get("id") != case["id"] and c.get("name")]
    for k in ("vo1", "vo_final"):
        t = _text(v.get(k)).lower()
        if t and any(names_other(t, c["name"], mine) for c in others):
            v[k] = {"text": ""}
            notes.append(f"{k} named another defendant - rewritten from the case")
    d = v["doc"]
    for k in ("tease",):
        if d.get(k) and any(names_other(_text(d[k]).lower(), c["name"], mine) for c in others):
            d.pop(k)
            notes.append(f"doc.{k} named another defendant - left out")
    if isinstance(d.get("backstory"), list):
        keep = [x for x in d["backstory"] if isinstance(x, dict) and _text(x)
                and not any(names_other(_text(x).lower(), c["name"], mine) for c in others)]
        if len(keep) != len(d["backstory"]):
            notes.append(f"{len(d['backstory']) - len(keep)} backstory beat(s) left out (empty / another defendant)")
        d["backstory"] = keep
    before = {k: _text(v.get(k)) for k in ("vo1", "vo_final")}
    _doc_fill_vo(v, [case])
    for k in ("vo1", "vo_final"):
        if not _text(v.get(k)):
            v[k] = {"text": _sentence(" ".join(x for x in (case.get("story"), case.get("ends_on")) if x)
                                      or f"This is the hearing of {name}.", 400), "auto": True}
        if _text(v.get(k)) != before[k]:
            notes.append(f"{k} filled from the case document")
    # ---- overlays (optional retention beats): keep only ones that are inside the case and, if they quote, true
    ctext = " ".join(s.get("text", "") for s in (segs or []) if a - 1 <= float(s.get("start", 0)) <= b + 1).lower()
    ovs = v.get("overlays") if isinstance(v.get("overlays"), list) else []
    good = []
    for o in ovs:
        t = _tc(o.get("tc")) if isinstance(o, dict) else None
        ev = re.sub(r"\s+", " ", str((o or {}).get("evidence") or "")).strip().lower() if isinstance(o, dict) else ""
        if t is None or not (a <= t <= b) or not _text(o.get("text")) or (ev and ctext and ev[:60] not in ctext):
            continue
        good.append(o)
    if len(good) != len(ovs):
        notes.append(f"{len(ovs) - len(good)} overlay(s) left out (outside the case / quote not in the transcript)")
    v["overlays"] = good
    # ---- metadata fields (metadata.txt / edit sheet / thumbnail read them)
    ts = [t for t in (v.get("titles") or []) if isinstance(t, dict) and _text(t.get("text"))]
    if not ts:
        ttl = _sentence(f"{name.upper()} - {charge}", 95)
        if _text(v.get("title")):
            ttl = _text(v["title"])
        ts = [{"text": ttl, "style": "auto", "primary": True}]
        notes.append("title made from the case (brain gave none) - check it before upload")
    if not any(t.get("primary") for t in ts):
        ts[0]["primary"] = True
    v["titles"] = ts
    v["title"] = next(_text(t["text"]) for t in ts if t.get("primary"))
    v["backup_title"] = next((_text(t["text"]) for t in ts if not t.get("primary")), v["title"])
    q = _text(case.get("question")) or f"What happened to {name}?"
    desc = v.get("description") if isinstance(v.get("description"), dict) else {}
    defaults = {"first_line": q, "what_happens": _sentence(case.get("story") or f"{name} stands before the judge on {charge}.", 400),
                "search_question": q, "answer": _sentence(" ".join(x for x in (case.get("story"), case.get("ends_on")) if x), 700),
                "related_question": f"What does {charge.lower()} carry in Texas?"}
    filled = [k for k, dv in defaults.items() if not _text(desc.get(k))]
    for k in filled:
        desc[k] = defaults[k]
    if filled and not v.get("_auto"):
        notes.append("description filled from the case: " + ", ".join(filled))
    v["description"] = desc
    if not isinstance(v.get("tags"), list) or not v["tags"]:
        v["tags"] = [t for t in {name.lower(), charge.lower(), "court case", "judge", "sentencing", "court hearing"} if t]
    for k in ("pinned_comment", "community_post"):
        if not _text(v.get(k)):
            v[k] = f"{q} Tell us what you think in the comments."
        elif isinstance(v.get(k), dict):
            v[k] = _text(v[k])
    qz = v.get("quiz") if isinstance(v.get("quiz"), dict) else {}
    opts = qz.get("options") if isinstance(qz.get("options"), dict) else {}
    if not _text(qz.get("question")) or not all(_text(opts.get(x)) for x in "ABC"):
        qz = {"question": f"What would you have given {name}?",
              "options": {"A": "A second chance", "B": "What the judge gave", "C": "More time"},
              "answer": "left open - answer in the comments"}
    v["quiz"] = qz
    if not isinstance(v.get("publish"), dict) or not v["publish"].get("slot"):
        v["publish"] = {"slot": "1pm ET"}
    if not isinstance(v.get("chapters"), list):
        v["chapters"] = []
    th = v.get("thumbnail") if isinstance(v.get("thumbnail"), dict) else {}
    wa, wb = _tc(th.get("window_in")), _tc(th.get("window_out"))
    if wa is None or wb is None or not (a <= wa < wb <= b):
        th["window_in"], th["window_out"] = fmt_tc(parse_tc(hk["in"]) + 1, False), fmt_tc(parse_tc(hk["in"]) + 4, False)
    words = _text(th.get("text")) or _sentence(d.get("verdict_big") or res.get("sentence") or charge, 30)
    th["text"] = " ".join(words.split()[:5]).upper()
    th.setdefault("gold_word", th["text"].split()[-1] if th["text"] else "")
    th.setdefault("look_for", "expression")
    th.setdefault("placement", "top")
    v["thumbnail"] = th
    if notes:
        v["_pack_notes"] = list(dict.fromkeys((v.get("_pack_notes") or []) + notes))
    return notes


def tts_chars(v):
    """Characters the documentary renderer may voice for this video (the narration fields + vo1 / vo_final)."""
    d = v.get("doc") or {}
    n = len(_text(v.get("vo1"))) + len(_text(v.get("vo_final"))) + len(_text(d.get("tease")))
    n += sum(len(_text(x)) for x in d.get("backstory") or [] if isinstance(x, dict))
    n += sum(len(_text(x)) for x in (d.get("bridges") or []) + (d.get("earlier_bridges") or []))
    n += sum(len(_text((r or {}).get("analysis"))) for r in d.get("replays") or [] if isinstance(r, dict))
    n += len(_text(d.get("episode_summary"))) + 60          # "This is the full story of ..." / "Previously ..."
    return n
