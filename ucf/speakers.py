"""Speaker-labelled captions for court footage:  JUDGE: Excuse me. Stand up over there...

Who speaks is decided in this order:
  1. turns from the plan (the brain marks them in Pass B: [{"from": s, "to": s, "who": "JUDGE"}]) - most reliable
  2. a text heuristic (phrases only a judge / a defendant / a lawyer says)
  3. the previous line's speaker (short replies stay with the person who was talking)
Unknown stays unlabelled - a wrong name is worse than no name.

Captions are a dark box with a monospace line and the speaker name in its own colour (documentary look). Colours and
font come from the style pack, never hard-coded channel branding.
"""
import re
from pathlib import Path

JUDGE_PAT = re.compile(r"\b(i('m| am) (going to|gonna) (find|sentence|set|revoke|grant|deny)|the court (finds|will|is)|"
                       r"i find you|you are (hereby )?sentenced|bond (is|will be) set|have a seat|"
                       r"do you understand|how do you plead|is that (your|correct)|state,? (are you|what)|"
                       r"counsel|approach|be seated|remanded|i'?ll allow|overruled|sustained|"
                       r"do (y'?all|you) need help)\b", re.I)
DEFENDANT_PAT = re.compile(r"\b(yes,? ma'?am|no,? ma'?am|yes,? sir|no,? sir|your honor,? i|i('m| am) sorry|"
                           r"i didn'?t|i don'?t know|i only|i swear|i was just|guilty|not guilty)\b", re.I)
LAWYER_PAT = re.compile(r"\b(your honou?r,? (my client|the state|we|defense)|my client|the state (asks|requests|would)|"
                        r"we('d| would) ask|move to|objection|pass the witness|nothing further)\b", re.I)


def guess(text):
    t = text or ""
    if LAWYER_PAT.search(t):
        return "LAWYER"
    if JUDGE_PAT.search(t):
        return "JUDGE"
    if DEFENDANT_PAT.search(t):
        return "DEFENDANT"
    return None


def label(lines, turns=None, names=None, carry_max_gap=1.2):
    """lines = [(start, end, text)] -> [(start, end, who|None, text)].
    turns = [{"from", "to", "who"}] from the plan; names = {"DEFENDANT": "SUMMER", "LAWYER": "DEFENSE"} renames roles."""
    names = names or {}
    turns = sorted(turns or [], key=lambda x: float(x["from"]))
    out, prev, prev_end = [], None, -99.0
    for s, e, txt in lines:
        mid = (s + e) / 2
        who = next((str(tu["who"]).upper() for tu in turns if float(tu["from"]) <= mid <= float(tu["to"])), None)
        if not who:
            who = guess(txt)
        if not who and prev and s - prev_end <= carry_max_gap and len(txt.split()) <= 6:
            who = prev
        out.append((s, e, names.get(who, who) if who else None, txt))
        prev, prev_end = who or prev, e
    return out


def _ts(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _esc(t):
    return str(t).replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _ass_colour(hexrgb, alpha=0):
    h = hexrgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&".upper()


def build_ass(labelled, out, look=None, blocks=None):
    """Write an ASS file with boxed, speaker-prefixed caption lines. look keys (all optional, from the style pack):
    font, size, text, box, box_alpha (0-255, 0 = solid), speaker_colours {ROLE: "#hex"}, default_speaker, margin_v,
    margin_l, align (1 = bottom-left, 2 = bottom-centre). blocks = [(s, e)] where no caption may show. -> lines written."""
    lk = {"font": "Courier New", "size": 34, "text": "#F2F2F2", "box": "#0B0B0B", "box_alpha": 40, "margin_v": 60,
          "margin_l": 120, "align": 2, "default_speaker": "#F5C518",
          "speaker_colours": {"JUDGE": "#F5C518", "DEFENDANT": "#7FD3FF", "LAWYER": "#FF8A80"}}
    lk.update(look or {})
    blocks = blocks or []
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Spk,{lk['font']},{lk['size']},{_ass_colour(lk['text'])},{_ass_colour(lk['text'])},"
            f"{_ass_colour(lk['box'], int(lk['box_alpha']))},{_ass_colour(lk['box'], int(lk['box_alpha']))},0,0,0,0,"
            f"100,100,0,0,3,12,0,{int(lk['align'])},{int(lk['margin_l'])},{int(lk['margin_l'])},{int(lk['margin_v'])},1"
            "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    rows = []
    for s, e, who, txt in labelled:
        if e - s < 0.05 or any(s < b and e > a for a, b in blocks):
            continue
        body = _esc(txt.strip())
        if who:
            col = _ass_colour(lk["speaker_colours"].get(who, lk["default_speaker"]))
            body = f"{{\\b1\\c{col}}}{_esc(who)}:{{\\b0\\c{_ass_colour(lk['text'])}}} " + body
        rows.append(f"Dialogue: 0,{_ts(s)},{_ts(e)},Spk,,0,0,0,,{body}")
    Path(out).write_text(head + "\n".join(rows) + "\n", encoding="utf-8")
    return len(rows)


def lines_from_words(words, max_chars=78, max_gap=0.7, max_dur=5.0):
    """whisper words [(s, e, w)] -> sentence-ish caption lines [(s, e, text)] (breaks on . ? ! / pauses / length)."""
    out, cur = [], []
    for s, e, w in words:
        if cur and (s - cur[-1][1] > max_gap or e - cur[0][0] > max_dur
                    or len(" ".join(x[2] for x in cur)) + len(w) > max_chars):
            out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur)))
            cur = []
        cur.append((s, e, w))
        if w.rstrip().endswith((".", "?", "!")) and len(cur) >= 3:
            out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur)))
            cur = []
    if cur:
        out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur)))
    return out
