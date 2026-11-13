"""Judge-neutral voice-over and on-screen text (owner rule 2026-11-13): the tool runs on dockets of different judges, so the
voice-over scripts and every text shown ON the video say "the judge", never the judge's name. Titles (and the YouTube
description / tags / pinned comment) keep the name - they are not changed here.

neutralize(plan, names) rewrites, in place, the spoken / on-screen fields of every video and case:
  video: hook.headline, hook.spoken, vo1.text, vo_final.text, bridges[].text, quiz (question / options / answer)
  case : overlays[].text, question, charge, facing, proceeding, what_it_is, moment, headline_name, sub_line, result.*
Transcript quotes and evidence stay verbatim (validators match them against the transcript).
"Judge Stephanie Boyd" / "Judge Boyd" / "Boyd" -> "the judge" ("The judge" at a sentence start, "THE JUDGE" in all-caps text,
"the judge's" for a possessive).
"""
import re

VIDEO_KEYS = (("hook", "headline"), ("hook", "spoken"), ("vo1", "text"), ("vo_final", "text"))
CASE_KEYS = ("question", "charge", "facing", "proceeding", "what_it_is", "moment", "headline_name", "sub_line")


def judge_names(*sources):
    """Name parts to remove, from judge_name values ("Judge Boyd") and a stream title ("... /JUDGE STEPHANIE BOYD/ ...")."""
    out = set()
    for s in sources:
        s = str(s or "")
        for m in re.finditer(r"\bjudge\s+((?:[a-z][a-z'\-]+\s+){0,2}[a-z][a-z'\-]+)", s, re.I):
            words = [w for w in m.group(1).split() if w.lower() not in ("the", "of", "court", "district", "and")]
            if words:
                out.add(" ".join(words))           # "Stephanie Boyd"
                out.add(words[-1])                 # "Boyd"
    return sorted(out, key=len, reverse=True)


def _pattern(names):
    alts = "|".join(re.escape(n).replace(r"\ ", r"\s+") for n in names)
    # optional "Judge " before the name, optional possessive after it
    return re.compile(rf"\b(judge\s+)?(?:{alts})\b('s|’s)?", re.I)


def neutral_text(text, names):
    if not text or not names or not isinstance(text, str):
        return text
    pat = _pattern(names)
    caps = text.upper() == text and any(c.isalpha() for c in text)

    def sub(m):
        before = text[:m.start()]
        word = "judge's" if m.group(2) else "judge"
        if re.search(r"\bthe\s+$", before, re.I):                   # "the Judge Boyd" -> "the judge"
            rep = word
        else:
            start = not before.strip() or re.search(r"[.!?:\"“(\-—]\s*$", before)
            rep = ("The " if start else "the ") + word
        return rep.upper() if caps else rep
    return pat.sub(sub, text)


def neutralize(plan, names):
    """Rewrite the plan's spoken / on-screen texts in place. -> number of fields changed."""
    if not names:
        return 0
    n = 0

    def fix(d, k):
        nonlocal n
        if isinstance(d, dict) and isinstance(d.get(k), str):
            new = neutral_text(d[k], names)
            if new != d[k]:
                d[k] = new
                n += 1

    for v in plan.get("videos", []) or []:
        for a, b in VIDEO_KEYS:
            fix(v.get(a) or {}, b)
        for br in v.get("bridges") or []:
            fix(br, "text")
        q = v.get("quiz") or {}
        fix(q, "question")
        fix(q, "answer")
        for k in list((q.get("options") or {}).keys()):
            fix(q["options"], k)
        for o in v.get("overlays") or []:
            fix(o, "text")
    for c in plan.get("cases", []) or []:
        for k in CASE_KEYS:
            fix(c, k)
        for k in list((c.get("result") or {}).keys()) if isinstance(c.get("result"), dict) else []:
            fix(c["result"], k)
        for o in c.get("overlays") or []:
            fix(o, "text")
    return n
