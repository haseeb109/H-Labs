"""Case documents for the documentary styles. Every video gets one (mandatory); a real record is optional.

1. CASE SUMMARY (always): a paper card built from facts the brain read out of the hearing. Every fact must quote its
   evidence from the transcript; a fact whose evidence is not in the transcript, or whose value is not in its evidence,
   is DROPPED (never shown). When the brain gave nothing usable, the summary is built from the plan's own case fields
   (name / charge / result), so the document always exists.
   The card is clearly our summary: "CASE SUMMARY · from the public court hearing" + a footnote "not an official court
   record". No seal, no signature, no "OFFICIAL" - it must never pass for a real court document.

2. COURT RECORD (optional): a real public PDF the owner drops in (input/records/<anything>.pdf or the case folder).
   The page is shown on the legal background with a highlighter on the exact phrases and black bars over personal data
   (phone, date of birth, SSN, street address, e-mail) - found automatically and ALWAYS applied, plus any extra phrases.

Plan field the brain fills (Pass B, per case):
    "case_doc": {"defendant": {"value": "Summer Diaz", "evidence": "Summer Diaz, you are charged with"}, ...}
"""
import re
from pathlib import Path

from . import paper

FIELDS = [  # key, label, how it is shown
    ("defendant", "DEFENDANT"), ("age", "AGE"), ("cause_no", "CAUSE NO."), ("court", "COURT"),
    ("charges", "CHARGE"), ("offense_date", "OFFENSE DATE"), ("hearing_date", "HEARING"), ("bond", "BOND"),
    ("plea", "PLEA"), ("state_asked", "STATE ASKED"), ("defense_asked", "DEFENSE ASKED"), ("result", "RESULT"),
    ("sentence", "SENTENCE"), ("conditions", "CONDITIONS"), ("next_date", "NEXT DATE"),
]
LABEL = dict(FIELDS)
HIGHLIGHT = ("result", "sentence")                       # the lines the highlighter wipes over on the last step
DISCLAIMER = "Prepared from the public court hearing recording. Not an official court record."


def _norm(t):
    t = str(t or "").lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9$%.' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens_ok(value, evidence):
    """Every number and every capitalised word of the value must be in the evidence quote."""
    ev = _norm(evidence)
    for tok in re.findall(r"\$?\d[\d,.]*|[A-Z][a-zA-Z'-]+", str(value)):
        n = _norm(tok).replace(",", "")
        if n and n not in ev.replace(",", ""):
            return False
    return True


def verify(case_doc, transcript_text):
    """-> (facts {key: value}, dropped [(key, reason)]). Values are kept only with evidence found in the transcript."""
    tx = _norm(transcript_text)
    facts, dropped = {}, []
    for key, item in (case_doc or {}).items():
        if key not in LABEL:
            dropped.append((key, "unknown field"))
            continue
        if not isinstance(item, dict):
            dropped.append((key, "no evidence given"))
            continue
        val, ev = item.get("value"), item.get("evidence") or ""
        if val in (None, "", []):
            continue
        if len(_norm(ev)) < 8 or _norm(ev) not in tx:
            dropped.append((key, "evidence quote not found in the transcript"))
            continue
        vals = val if isinstance(val, list) else [val]
        if not all(_tokens_ok(v, ev) for v in vals):
            dropped.append((key, "value is not in its evidence quote"))
            continue
        facts[key] = "; ".join(str(v) for v in vals)
    return facts, dropped


def from_case(case):
    """Fallback facts from the plan's own case fields (already validated by the plan validator)."""
    out = {}
    for src, dst in (("name", "defendant"), ("defendant", "defendant"), ("charge", "charges"), ("result", "result"),
                     ("court", "court"), ("hearing_date", "hearing_date"), ("date", "hearing_date"), ("facing", "sentence")):
        v = case.get(src)
        if v and dst not in out:
            out[dst] = str(v)
    return out


def build_facts(case, transcript_text, meta=None):
    """Facts for the summary card: verified brain facts, topped up by the plan's case fields and the stream info
    (court line / date). -> (facts, dropped). Never empty: at least the defendant line is there."""
    facts, dropped = verify(case.get("case_doc"), transcript_text)
    for k, v in from_case(case).items():
        facts.setdefault(k, v)
    meta = meta or {}
    if meta.get("court"):
        facts.setdefault("court", meta["court"])
    if meta.get("date"):
        facts.setdefault("hearing_date", meta["date"])
    facts.setdefault("defendant", case.get("name") or case.get("id") or "THE DEFENDANT")
    return facts, dropped


def summary_card(facts, out, palette=None, title="CASE SUMMARY"):
    """-> list of PNGs: one per row appearing, then the final one with the highlighter on result / sentence.
    Full-frame (legal background), for 4-8 s with paper-rustle + pop SFX per row."""
    p = paper._pal(palette)
    rows = [(k, facts[k]) for k, _ in FIELDS if facts.get(k)]

    def card(n, hl):
        trs = ""
        for i, (k, v) in enumerate(rows):
            vis = "visible" if i < n else "hidden"
            val = paper.esc(v)
            if hl and k in HIGHLIGHT:
                val = f'<span class="hl">{val}</span>'
            trs += (f'<tr style="visibility:{vis}"><td style="width:300px;color:{p["muted"]};font-size:22px;letter-spacing:2px;'
                    f'padding:9px 0;vertical-align:top">{LABEL[k]}</td><td style="font-size:30px;font-weight:700;padding:7px 0;'
                    f'text-transform:uppercase">{val}</td></tr>')
        return (paper._legal_bg() +
                f'<div class="paper" style="left:300px;top:110px;width:1320px;transform:rotate(-0.8deg)">'
                f'<div style="display:flex;justify-content:space-between"><span class="k">{paper.esc(title)} · from the public court hearing</span>'
                f'<span class="k">{paper.esc(facts.get("cause_no", ""))}</span></div>'
                f'<div style="border-top:3px solid {p["ink"]};margin:14px 0 8px"></div><table style="border-collapse:collapse;width:100%">{trs}</table>'
                f'<div style="margin-top:16px;font-size:16px;color:{p["muted"]}">{DISCLAIMER}</div></div>')
    outs = [paper.render(card(n, False), Path(out).with_name(f"{Path(out).stem}_{n}"), p, transparent=False)
            for n in range(1, len(rows) + 1)]
    if any(k in facts for k in HIGHLIGHT):
        outs.append(paper.render(card(len(rows), True), Path(out).with_name(f"{Path(out).stem}_hl"), p, transparent=False))
    return outs


def mini_doc(facts, out, palette=None, keys=("charges", "bond", "result")):
    """Small corner card (transparent) for court blocks: 2-3 key facts, used by the engagement scheduler."""
    p = paper._pal(palette)
    lines = "".join(f'<div style="font-size:19px;margin-top:4px"><span style="color:{p["muted"]}">{LABEL[k]}:</span> '
                    f'<b>{paper.esc(facts[k])}</b></div>' for k in keys if facts.get(k))
    inner = (f'<div class="a" style="right:50px;top:110px;width:520px;background:{p["paper"]};color:{p["ink"]};padding:16px 20px;'
             f'font-family:{p["mono"]};transform:rotate(1.2deg);box-shadow:0 14px 30px rgba(0,0,0,.4)">'
             f'<div style="font-size:15px;letter-spacing:3px;color:{p["muted"]}">CASE SUMMARY</div>{lines}</div>')
    return paper.render(inner, out, p)


# ------------------------------------------------------------------ real court record (PDF)
PII = [
    re.compile(r"\(?\b\d{3}\)?[-. ]?\d{3}[-. ]\d{4}\b"),                                   # phone
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                                   # SSN
    re.compile(r"\b(?:DOB|D\.O\.B\.|date of birth)\W{0,3}\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.I),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),                                              # e-mail
    re.compile(r"\b\d{2,6} (?:[A-Z][a-z]+ ){1,3}(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Ln|Lane|Blvd|Ct|Court|Way|Cir|Circle)\b\.?"),
]


def pii_phrases(text):
    out = []
    for rx in PII:
        out += [m.group(0) for m in rx.finditer(text or "")]
    return list(dict.fromkeys(out))


def pdf_page_text(pdf, page=0):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    try:
        return doc[page].get_textpage().get_text_range()
    finally:
        doc.close()


def _boxes(tp, phrase, scale, height):
    """Pixel boxes (x0, y0, x1, y1) of every hit of `phrase` on the page image."""
    out = []
    s = tp.search(phrase, match_case=False, match_whole_word=False)
    while True:
        hit = s.get_next()
        if not hit:
            break
        idx, cnt = hit
        for i in range(tp.count_rects(idx, cnt)):
            l, b, r, t = tp.get_rect(i)
            out.append((l * scale, height - t * scale, r * scale, height - b * scale))
    return out


def record_card(pdf, out, page=0, highlights=(), redact=(), palette=None, auto_redact=True):
    """Real court record page -> (before_png, after_png, report). Personal data found on the page is ALWAYS blacked out
    (both PNGs); highlights appear only on the after PNG. A highlight phrase not on the page is reported, not drawn."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw
    p = paper._pal(palette)
    out = Path(out)
    doc = pdfium.PdfDocument(str(pdf))
    report = []
    try:
        pg = doc[page]
        w, h = pg.get_size()
        scale = 900 / h                                            # page image 900 px tall
        img = pg.render(scale=scale).to_pil().convert("RGB")
        tp = pg.get_textpage()
        text = tp.get_text_range()
        bars = list(redact) + (pii_phrases(text) if auto_redact else [])
        hl_boxes = []
        for ph in highlights:
            bx = _boxes(tp, ph, scale, img.height)
            if not bx:
                report.append(f"highlight not on page {page + 1}: {ph[:50]}")
            hl_boxes += bx
        red_boxes = []
        for ph in bars:
            red_boxes += _boxes(tp, ph, scale, img.height)
        report.append(f"{len(red_boxes)} redaction bar(s), {len(hl_boxes)} highlight box(es)")
    finally:
        doc.close()

    def comp(with_hl):
        im = img.copy()
        if with_hl and hl_boxes:
            lay = Image.new("RGB", im.size, (255, 255, 255))
            dl = ImageDraw.Draw(lay)
            col = tuple(int(p["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            for x0, y0, x1, y1 in hl_boxes:
                dl.rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill=col)
            from PIL import ImageChops
            im = ImageChops.multiply(im, lay)
        d = ImageDraw.Draw(im)
        for x0, y0, x1, y1 in red_boxes:
            d.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=(0, 0, 0))
        canvas = Image.new("RGB", (1920, 1080), tuple(int(p["bg"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)))
        canvas.paste(im, ((1920 - im.width) // 2, 90))
        return canvas
    a, b = out.with_name(out.stem + "_rec_a.png"), out.with_name(out.stem + "_rec_b.png")
    a.parent.mkdir(parents=True, exist_ok=True)
    comp(False).save(a)
    comp(True).save(b)
    return a, b, report


def find_records(*folders):
    """PDFs the owner dropped for this case (input/records/, the case folder)."""
    out = []
    for f in folders:
        d = Path(f)
        if d.is_dir():
            out += sorted(d.glob("*.pdf"))
    return out
