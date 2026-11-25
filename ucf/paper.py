"""Documentary graphics kit (shared by the new editing styles): paper cards, stamps, pills, statute highlight,
calendar / timeline, sentence card, comparison boxes, chapter cards, profile card, jargon pill, ruling lower-third,
top bar. NO channel name, logo or watermark anywhere - the owner adds branding in the editor.

Every card is HTML rendered to a 1920x1080 PNG with Playwright (cached by content hash). Colours and fonts come from a
`palette` dict that each style pack passes in (see PALETTE for the keys); fonts are the free ones in shared/fonts.
Cards meant to animate come back as two PNGs (before / after) so the renderer can wipe or cross-fade between them
(e.g. the statute line without and with the highlighter).
"""
import hashlib
import html as H
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "shared" / "fonts"

PALETTE = {"accent": "#F5C518", "accent_ink": "#111111", "danger": "#D7263D", "paper": "#F4F1EA", "ink": "#1B1B1B",
           "muted": "#6B6B6B", "bg": "#2A2A2E", "bg_text": "rgba(0,0,0,.10)", "card": "rgba(14,14,16,.82)",
           "white": "#FFFFFF", "mono": "Mono", "head": "Head", "serif": "Serif", "sans": "Sans", "radius": "4px"}

LEGAL_BG_TEXT = ("the court finds the defendant has violated the conditions of community supervision as alleged in the "
                 "motion to adjudicate guilt and the state of texas by and through its assistant district attorney "
                 "moves the court to proceed with an adjudication of guilt on the original charge pursuant to article ")


def _css(p):
    f = FONT_DIR.resolve().as_uri()
    return f"""
@font-face{{font-family:Mono;font-weight:500;src:url({f}/ibm-plex-mono-latin-500-normal.woff2)}}
@font-face{{font-family:Mono;font-weight:700;src:url({f}/ibm-plex-mono-latin-600-normal.woff2)}}
@font-face{{font-family:Head;font-weight:600;src:url({f}/oswald-latin-600-normal.woff2)}}
@font-face{{font-family:Head;font-weight:700;src:url({f}/oswald-latin-700-normal.woff2)}}
@font-face{{font-family:Serif;font-weight:700;src:url({f}/source-serif-4-latin-700-normal.woff2)}}
@font-face{{font-family:Sans;font-weight:600;src:url({f}/inter-latin-600-normal.woff2)}}
@font-face{{font-family:Sans;font-weight:800;src:url({f}/inter-latin-800-normal.woff2)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent;font-family:{p['sans']},sans-serif;color:{p['white']}}}
.a{{position:absolute}}
.pill{{display:inline-block;background:{p['accent']};color:{p['accent_ink']};font-family:{p['mono']};font-weight:700;
  font-size:30px;letter-spacing:2px;text-transform:uppercase;padding:8px 18px;border-radius:{p['radius']};
  box-shadow:0 6px 18px rgba(0,0,0,.35);margin-bottom:12px;max-width:1100px}}
.pill.w{{background:{p['white']};color:{p['ink']}}} .pill.r{{background:{p['danger']};color:{p['white']}}}
.pill.d{{background:{p['card']};color:{p['white']}}}
.stamp{{display:inline-block;font-family:{p['head']};font-weight:700;font-size:78px;letter-spacing:3px;color:{p['danger']};
  border:8px solid {p['danger']};border-radius:10px;padding:4px 26px;text-transform:uppercase;opacity:.92;
  mix-blend-mode:multiply;filter:url(#rough)}}
.legal{{position:absolute;inset:-40px;background:{p['bg']};color:{p['bg_text']};font-family:{p['serif']};font-size:44px;
  line-height:1.35;padding:30px;filter:blur(1.2px);overflow:hidden;text-transform:uppercase}}
.paper{{position:absolute;background:{p['paper']};color:{p['ink']};font-family:{p['mono']};padding:42px 54px;
  box-shadow:0 30px 60px rgba(0,0,0,.45);border-radius:3px}}
.paper .k{{font-size:20px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:{p['muted']}}}
.paper .t{{font-size:40px;font-weight:700;margin:14px 0 10px;text-transform:uppercase}}
.paper li{{font-size:30px;margin:8px 0 0 34px}}
.hl{{background:linear-gradient(transparent 12%,{p['accent']} 12%,{p['accent']} 88%,transparent 88%);padding:0 4px}}
.strike{{text-decoration:line-through;text-decoration-color:{p['danger']};text-decoration-thickness:4px}}
.card{{position:absolute;background:{p['card']};border-radius:8px;padding:34px 46px;backdrop-filter:blur(6px)}}
.big{{font-family:{p['head']};font-weight:700;line-height:1;text-transform:uppercase}}
"""


_SVG = ('<svg width="0" height="0" style="position:absolute"><filter id="rough"><feTurbulence type="fractalNoise" '
        'baseFrequency="0.9" numOctaves="2" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="5"/>'
        '</filter></svg>')


def esc(t):
    return H.escape(str(t if t is not None else ""), quote=False)


def _pal(palette):
    return dict(PALETTE, **(palette or {}))


def render(inner, out, palette=None, transparent=True, size=(1920, 1080)):
    """HTML snippet -> PNG next to `out` (name gets a content hash, so identical cards are rendered once)."""
    from ucf import ov_gfx
    p = _pal(palette)
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{_css(p)}</style></head><body style="width:'
           f'{size[0]}px;height:{size[1]}px;position:relative;overflow:hidden">{_SVG}{inner}</body></html>')
    out = Path(out)
    png = out.with_name(f"{out.stem}_{hashlib.md5(doc.encode()).hexdigest()[:12]}.png")
    if png.exists():
        return png
    png.parent.mkdir(parents=True, exist_ok=True)
    page = ov_gfx._browser().new_page(viewport={"width": size[0], "height": size[1]})
    try:
        hp = png.with_suffix(".html")
        hp.write_text(doc, encoding="utf-8")
        page.goto(hp.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(200)
        page.screenshot(path=str(png), omit_background=transparent)
        hp.unlink(missing_ok=True)
    finally:
        page.close()
    return png


def _legal_bg():
    return f'<div class="legal">{esc(LEGAL_BG_TEXT * 6)}</div>'


# ---------------------------------------------------------------- overlays (transparent, go on top of footage)
def pill_stack(lines, out, palette=None, x=60, y=120, kinds=None):
    """1-3 stacked pills, top-left by default. kinds per line: '' (accent) | 'w' white | 'r' danger | 'd' dark.
    Returns one PNG per step (pill 1, pills 1-2, pills 1-3) so they can appear one by one with the narrator."""
    kinds = kinds or [""] * len(lines)
    outs = []
    for n in range(1, len(lines) + 1):
        inner = f'<div class="a" style="left:{x}px;top:{y}px">' + "<br>".join(
            f'<span class="pill {kinds[i]}">{esc(t)}</span>' for i, t in enumerate(lines[:n])) + "</div>"
        outs.append(render(inner, Path(out).with_name(f"{Path(out).stem}_{n}"), palette))
    return outs


def stamp(text, out, palette=None, x=1180, y=640, rot=-8):
    inner = f'<div class="a" style="left:{x}px;top:{y}px;transform:rotate({rot}deg)"><span class="stamp">{esc(text)}</span></div>'
    return render(inner, out, palette)


def top_bar(date, out, palette=None, tag="", badges=("REAL COURT FOOTAGE",)):
    """Date pill (+ optional hearing tag) top-left, small badges top-right. No channel name."""
    p = _pal(palette)
    d = esc(date) + (f" · {esc(tag)}" if tag else "")
    right = "".join(f'<span class="pill r" style="font-size:20px;padding:5px 12px;margin-left:10px">● {esc(b)}</span>'
                    for b in badges)
    inner = (f'<div class="a" style="left:40px;top:26px"><span class="pill" style="font-size:22px;padding:5px 12px">{d}</span></div>'
             f'<div class="a" style="right:40px;top:26px">{right}</div>')
    return render(inner, out, p)


def jargon_pill(term, definition, out, palette=None):
    p = _pal(palette)
    inner = (f'<div class="card a" style="right:50px;top:110px;width:640px;padding:22px 28px">'
             f'<div style="font-family:{p["mono"]};font-weight:700;font-size:26px;color:{p["accent"]};text-transform:uppercase">{esc(term)}</div>'
             f'<div style="font-family:{p["sans"]};font-weight:600;font-size:25px;margin-top:8px;line-height:1.3">{esc(definition)}</div></div>')
    return render(inner, out, p)


def ruling_lower_third(items, out, palette=None):
    """items = [("Asked", "$20,000"), ("Set", "$150,000 + full GPS")] -> one bar bottom-left."""
    p = _pal(palette)
    body = " &nbsp;•&nbsp; ".join(f'<span style="color:{p["muted"]}">{esc(k)}:</span> <b>{esc(v)}</b>' for k, v in items)
    inner = (f'<div class="a" style="left:60px;bottom:150px;background:{p["accent"]};color:{p["accent_ink"]};'
             f'font-family:{p["mono"]};font-size:32px;padding:12px 24px;border-radius:{p["radius"]};'
             f'box-shadow:0 8px 22px rgba(0,0,0,.4)">{body}</div>')
    return render(inner, out, p)


def name_tag(name, sub, out, palette=None, x=60, y=820):
    p = _pal(palette)
    inner = (f'<div class="a" style="left:{x}px;top:{y}px;background:{p["paper"]};color:{p["ink"]};padding:8px 16px;'
             f'font-family:{p["mono"]};border-radius:2px"><div style="font-size:22px;font-weight:700;text-transform:uppercase">'
             f'{esc(name)}</div><div style="font-size:15px;color:{p["muted"]};text-transform:uppercase">{esc(sub)}</div></div>')
    return render(inner, out, p)


def counter(label, n, out, palette=None, x=1560, y=40):
    """Running counter badge, e.g. LIE #3 / LAW 2/5."""
    p = _pal(palette)
    inner = (f'<div class="a" style="left:{x}px;top:{y}px;background:{p["danger"]};color:{p["white"]};padding:10px 22px;'
             f'font-family:{p["head"]};font-weight:700;font-size:46px;border-radius:{p["radius"]}">{esc(label)} {esc(n)}</div>')
    return render(inner, out, p)


def meter(label, value, out, palette=None):
    """0..1 meter bar (attitude / tension meter) top-right."""
    p = _pal(palette)
    v = max(0.0, min(1.0, float(value)))
    inner = (f'<div class="card a" style="right:50px;top:110px;width:420px;padding:18px 22px">'
             f'<div style="font-family:{p["mono"]};font-weight:700;font-size:22px;text-transform:uppercase">{esc(label)}</div>'
             f'<div style="margin-top:10px;height:22px;background:rgba(255,255,255,.15);border-radius:11px;overflow:hidden">'
             f'<div style="width:{v * 100:.0f}%;height:100%;background:linear-gradient(90deg,{p["accent"]},{p["danger"]})"></div>'
             f'</div></div>')
    return render(inner, out, p)


def poll(question, options, out, palette=None, reveal=None):
    """'You be the judge' card. reveal = index of the real answer (None = the question frame)."""
    p = _pal(palette)
    opts = ""
    for i, o in enumerate(options):
        on = reveal is not None and i == reveal
        bg = p["accent"] if on else "rgba(255,255,255,.10)"
        col = p["accent_ink"] if on else p["white"]
        opts += (f'<div style="margin-top:18px;background:{bg};color:{col};font-family:{p["head"]};font-weight:600;'
                 f'font-size:46px;padding:14px 26px;border-radius:{p["radius"]}">{"ABCD"[i]}) {esc(o)}</div>')
    inner = (f'<div class="card a" style="left:360px;top:200px;width:1200px">'
             f'<div class="big" style="font-size:64px;color:{p["accent"]}">{esc(question)}</div>{opts}</div>')
    return render(inner, out, p)


# ---------------------------------------------------------------- full-frame cards (opaque)
def paper_card(kicker, title, bullets, out, palette=None, stamp_text=None, corner=""):
    p = _pal(palette)
    lis = "".join(f"<li>{esc(b)}</li>" for b in bullets)
    st = (f'<div class="a" style="right:60px;bottom:40px;transform:rotate(-7deg)"><span class="stamp" '
          f'style="font-size:56px">{esc(stamp_text)}</span></div>') if stamp_text else ""
    inner = (_legal_bg() + f'<div class="paper" style="left:330px;top:250px;width:1260px;min-height:420px;transform:rotate(-1.5deg)">'
             f'<div style="display:flex;justify-content:space-between"><span class="k">{esc(kicker)}</span>'
             f'<span class="k">{esc(corner)}</span></div><div class="t">{esc(title)}</div><ul>{lis}</ul>{st}</div>')
    return render(inner, out, p, transparent=False)


def timeline_card(label, date, note, out, palette=None, stamp_text=None):
    return paper_card(label, date, [note] if note else [], out, palette, stamp_text)


def calendar_grid(title, months, out, palette=None):
    """months = [("MAR 2023", True=missed/crossed), ...] - e.g. reports to probation."""
    p = _pal(palette)
    cells = "".join(
        f'<div style="border:2px solid {p["ink"]};height:86px;display:flex;align-items:center;justify-content:center;'
        f'font-weight:700;font-size:22px;position:relative">{esc(m)}'
        + (f'<span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:'
           f'{p["danger"]};font-size:80px;font-family:{p["head"]}">✕</span>' if x else "") + "</div>"
        for m, x in months)
    inner = (_legal_bg() + f'<div class="paper" style="left:240px;top:300px;width:1440px;transform:rotate(1deg)">'
             f'<div class="k">{esc(title)}</div><div style="display:grid;grid-template-columns:repeat(12,1fr);gap:8px;'
             f'margin-top:20px">{cells}</div></div>')
    return render(inner, out, p, transparent=False)


def statute_card(cite, text, highlight, out, palette=None, plain="", penalty=""):
    """Statute text on paper; -> (before_png, after_png): the same card without / with the highlighted phrase, the
    plain-English pill and the penalty box (the renderer wipes from one to the other). The highlight must be an exact
    substring of `text` (the text comes from the statute library, never from the brain)."""
    p = _pal(palette)
    t = esc(text)
    h = esc(highlight)
    if highlight and h not in t:
        raise ValueError(f"highlight '{highlight[:40]}' is not in the statute text of {cite}")

    def card(on):
        body = t.replace(h, f'<span class="hl">{h}</span>', 1) if (on and h) else t
        extra = ""
        if on and plain:
            extra += f'<div class="a" style="left:300px;top:150px"><span class="pill" style="font-size:40px">{esc(plain)}</span></div>'
        if on and penalty:
            extra += (f'<div class="a" style="right:240px;bottom:130px;background:{p["danger"]};color:{p["white"]};'
                      f'font-family:{p["head"]};font-weight:700;font-size:84px;padding:10px 40px;border:6px solid '
                      f'{p["white"]};transform:rotate(-3deg)">{esc(penalty)}</div>')
        return (_legal_bg() + f'<div class="paper" style="left:300px;top:260px;width:1320px;font-family:{p["serif"]}">'
                f'<div class="k" style="font-family:{p["mono"]}">§ {esc(cite)}</div>'
                f'<div style="font-size:38px;line-height:1.45;margin-top:16px">{body}</div></div>{extra}')
    return (render(card(False), Path(out).with_name(Path(out).stem + "_a"), p, transparent=False),
            render(card(True), Path(out).with_name(Path(out).stem + "_b"), p, transparent=False))


def sentence_card(big, label, lines, out, palette=None, struck=""):
    p = _pal(palette)
    rows = "".join(f'<div style="font-size:30px;margin-top:8px">{esc(x)}</div>' for x in lines)
    if struck:
        rows += f'<div style="font-size:30px;margin-top:8px" class="strike">{esc(struck)}</div>'
    inner = (_legal_bg() + f'<div class="paper" style="left:380px;top:330px;width:1160px;transform:rotate(-1deg);display:flex;gap:40px;align-items:center">'
             f'<div class="big" style="font-size:150px;color:{p["danger"]}">{esc(big)}</div>'
             f'<div><div class="k">{esc(label)}</div>{rows}</div></div>')
    return render(inner, out, p, transparent=False)


def comparison(left, right, out, palette=None):
    """left / right = (label, value). Left = danger side (e.g. the State asks), right = neutral (the defence asks)."""
    p = _pal(palette)

    def box(lab, val, bg, fg, x):
        return (f'<div class="a" style="left:{x}px;top:360px;width:700px;background:{bg};color:{fg};padding:40px;'
                f'border-radius:{p["radius"]};box-shadow:0 20px 50px rgba(0,0,0,.4)"><div style="font-family:{p["mono"]};'
                f'font-weight:700;font-size:28px;letter-spacing:2px;text-transform:uppercase">{esc(lab)}</div>'
                f'<div class="big" style="font-size:92px;margin-top:14px">{esc(val)}</div></div>')
    inner = _legal_bg() + box(*left, p["danger"], p["white"], 220) + box(*right, p["paper"], p["ink"], 1000)
    return render(inner, out, p, transparent=False)


def chapter_card(kicker, date, keyword, out, palette=None, variant="card"):
    """HEARING 6 / JANUARY 28, 2025 / [THE BOND] - transparent; the renderer puts it on blurred footage.
    variant: card (dark box + pill) | minimal (Emotional Cut: serif words between two thin lines, no box) |
    episode (Docu-Series: left-aligned, big title, accent bar, like a streaming episode card)."""
    p = _pal(palette)
    if variant == "minimal":
        inner = (f'<div class="a" style="left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;color:#EDE6D6">'
                 f'<div style="width:220px;height:2px;background:{p["accent"]};margin:0 auto 26px"></div>'
                 f'<div style="font-family:{p["serif"]};font-weight:700;font-size:30px;letter-spacing:10px;opacity:.75;text-transform:uppercase">{esc(kicker)}</div>'
                 f'<div style="font-family:{p["serif"]};font-weight:700;font-size:92px;margin:14px 0 8px;text-transform:uppercase">{esc(keyword)}</div>'
                 f'<div style="font-family:{p["serif"]};font-weight:700;font-size:28px;letter-spacing:6px;opacity:.7">{esc(date)}</div>'
                 f'<div style="width:220px;height:2px;background:{p["accent"]};margin:26px auto 0"></div></div>')
        return render(inner, out, p)
    if variant == "episode":
        inner = (f'<div class="a" style="left:150px;top:50%;transform:translateY(-50%);border-left:12px solid {p["accent"]};padding-left:44px">'
                 f'<div style="font-family:{p["mono"]};font-size:28px;letter-spacing:8px;color:{p["accent"]};text-transform:uppercase">{esc(kicker)}</div>'
                 f'<div class="big" style="font-size:130px;margin:10px 0 6px;color:#fff;text-shadow:0 10px 40px rgba(0,0,0,.6)">{esc(keyword)}</div>'
                 f'<div style="font-family:{p["mono"]};font-size:30px;letter-spacing:4px;color:#d8f3f0">{esc(date)}</div></div>')
        return render(inner, out, p)
    inner = (f'<div class="card a" style="left:50%;top:50%;transform:translate(-50%,-50%);text-align:center;min-width:900px;padding:50px 80px">'
             f'<div style="font-family:{p["mono"]};font-size:30px;letter-spacing:8px;color:{p["muted"]};text-transform:uppercase">{esc(kicker)}</div>'
             f'<div class="big" style="font-size:96px;margin:14px 0 22px">{esc(date)}</div>'
             f'<span class="pill" style="font-size:42px">{esc(keyword)}</span></div>')
    return render(inner, out, p)


def big_text(text, out, palette=None, sub="", colour=None):
    """Kinetic / time-jump title (THREE YEARS LATER..., 45 YEARS) - transparent, centred."""
    p = _pal(palette)
    inner = (f'<div class="a" style="left:0;right:0;top:50%;transform:translateY(-50%);text-align:center">'
             f'<div class="big" style="font-size:150px;color:{colour or p["white"]};text-shadow:0 10px 40px rgba(0,0,0,.6)">{esc(text)}</div>'
             + (f'<div style="font-family:{p["mono"]};font-size:34px;letter-spacing:6px;margin-top:20px;text-transform:uppercase">{esc(sub)}</div>' if sub else "")
             + "</div>")
    return render(inner, out, p)


def profile_card(photo, pills, out, palette=None, caption="", stamp_text=""):
    """Polaroid-style photo left + stacked fact pills right. -> one PNG per pill step."""
    p = _pal(palette)
    ph = Path(photo).resolve().as_uri() if photo else ""
    pol = (f'<div class="a" style="left:300px;top:250px;background:#fff;padding:22px 22px 70px;transform:rotate(-4deg);'
           f'box-shadow:0 30px 60px rgba(0,0,0,.5)"><div style="width:460px;height:520px;background:#333 url({ph}) center/cover"></div>'
           f'<div style="color:#222;font-family:{p["mono"]};font-weight:700;font-size:30px;text-align:center;margin-top:14px;'
           f'text-transform:uppercase">{esc(caption)}</div></div>')
    outs = []
    for n in range(0, len(pills) + 1):
        stack = "<br>".join(f'<span class="pill" style="font-size:40px">{esc(t)}</span>' for t in pills[:n])
        inner = (f'<div class="a" style="inset:0;background:radial-gradient(circle at 30% 40%,#8a7f72,#3e3a35)"></div>'
                 + pol + f'<div class="a" style="left:960px;top:300px">{stack}</div>'
                 + (f'<div class="a" style="left:560px;top:640px;transform:rotate(-9deg)"><span class="stamp" '
                    f'style="font-size:96px">{esc(stamp_text)}</span></div>' if stamp_text else ""))
        outs.append(render(inner, Path(out).with_name(f"{Path(out).stem}_{n}"), p, transparent=False))
    return outs


# ---------------------------------------------------------------- style extras (2026-11-23)
def board(items, links, out, palette=None, reveal=None, master=None, stamp_text=None):
    """Evidence board: cork background, pinned cards, red strings. items = [{"id","label","sub"}] (max 8),
    links = [[id_a, id_b, "label"]]. reveal = how many items are pinned yet (None = all); strings only between pinned
    items. master = facts dict -> the case summary pinned in the middle. Full frame."""
    p = _pal(palette)
    n = len(items) if reveal is None else max(0, min(reveal, len(items)))
    slots = [(180, 150), (760, 120), (1340, 170), (160, 640), (1380, 660), (560, 760), (1000, 780), (1500, 420)]
    pos = {it["id"]: slots[i % len(slots)] for i, it in enumerate(items[:8])}
    shown = {it["id"] for it in items[:n]}
    lines = ""
    for a, b, *lab in links:
        if a in shown and b in shown:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            x1, y1, x2, y2 = x1 + 150, y1 + 40, x2 + 150, y2 + 40
            lines += (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{p["danger"]}" stroke-width="5"/>'
                      + (f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 10}" fill="#fff" font-family="Mono" font-size="22" '
                         f'text-anchor="middle" style="paint-order:stroke;stroke:#000;stroke-width:5px">{esc(lab[0])}</text>' if lab and lab[0] else ""))
    cards_ = ""
    for i, it in enumerate(items[:n]):
        x, y = pos[it["id"]]
        rot = (-3, 2, -1.5, 3, -2, 1.5, -2.5, 2)[i % 8]
        cards_ += (f'<div class="a" style="left:{x}px;top:{y}px;width:300px;background:{p["paper"]};color:{p["ink"]};padding:16px 18px;'
                   f'transform:rotate({rot}deg);box-shadow:0 12px 24px rgba(0,0,0,.5);font-family:{p["mono"]}">'
                   f'<div style="position:absolute;left:138px;top:-12px;width:24px;height:24px;border-radius:50%;background:{p["danger"]};'
                   f'box-shadow:0 3px 6px rgba(0,0,0,.5)"></div><div style="font-size:28px;font-weight:700;text-transform:uppercase">{esc(it["label"])}</div>'
                   f'<div style="font-size:19px;color:{p["muted"]};margin-top:6px">{esc(it.get("sub", ""))}</div></div>')
    mid = ""
    if master:
        rows = "".join(f'<div style="font-size:19px;margin-top:4px">{esc(k.upper())}: <b>{esc(v)}</b></div>'
                       for k, v in list(master.items())[:5])
        mid = (f'<div class="a" style="left:700px;top:380px;width:520px;background:{p["paper"]};color:{p["ink"]};padding:20px 24px;'
               f'font-family:{p["mono"]};box-shadow:0 18px 36px rgba(0,0,0,.55);transform:rotate(-1deg)">'
               f'<div style="font-size:16px;letter-spacing:3px;color:{p["muted"]}">CASE SUMMARY · MASTER FILE</div>{rows}</div>')
    st = (f'<div class="a" style="left:1200px;top:860px;transform:rotate(-8deg)"><span class="stamp">{esc(stamp_text)}</span></div>'
          if stamp_text else "")
    inner = (f'<div class="a" style="inset:0;background:radial-gradient(circle at 40% 40%,#8a6440,#4a3220 75%)"></div>'
             f'<svg class="a" style="inset:0" width="1920" height="1080">{lines}</svg>{mid}{cards_}{st}')
    return render(inner, out, p, transparent=False)


def telestrator(marks, out, palette=None, label=""):
    """Replay drawing layer (transparent): marks = [{"kind": "circle"|"arrow"|"underline", "x": 0-1, "y": 0-1, "r": 0-1}]
    in frame fractions. label = small caption next to the first mark (e.g. EYES DOWN)."""
    p = _pal(palette)
    col = p["accent"]
    svg = ""
    for m in marks[:4]:
        x, y = float(m.get("x", .5)) * 1920, float(m.get("y", .45)) * 1080
        r = float(m.get("r", .09)) * 1080
        k = m.get("kind", "circle")
        if k == "arrow":
            svg += (f'<line x1="{x + 260}" y1="{y - 200}" x2="{x + 30}" y2="{y - 20}" stroke="{col}" stroke-width="12" stroke-linecap="round"/>'
                    f'<polygon points="{x + 10},{y} {x + 70},{y - 20} {x + 30},{y - 70}" fill="{col}"/>')
        elif k == "underline":
            svg += f'<path d="M{x - r} {y} Q {x} {y + 18} {x + r} {y - 4}" stroke="{col}" stroke-width="10" fill="none" stroke-linecap="round"/>'
        else:
            svg += f'<ellipse cx="{x}" cy="{y}" rx="{r * 1.1}" ry="{r}" stroke="{col}" stroke-width="10" fill="none"/>'
    lab = ""
    if label and marks:
        x, y = float(marks[0].get("x", .5)) * 1920, float(marks[0].get("y", .45)) * 1080
        lab = (f'<div class="a" style="left:{min(1500, x + 140)}px;top:{max(40, y - 260)}px"><span class="pill" '
               f'style="font-size:36px">{esc(label)}</span></div>')
    inner = f'<svg class="a" style="inset:0" width="1920" height="1080">{svg}</svg>{lab}'
    return render(inner, out, p)


def title_card(kicker, title, lines, out, palette=None):
    """Case title card: THE STATE OF TEXAS v. NAME / charge / court. Full frame, legal background."""
    p = _pal(palette)
    rows = "".join(f'<div style="font-family:{p["mono"]};font-size:30px;margin-top:10px;color:{p["muted"]};text-transform:uppercase">{esc(x)}</div>'
                   for x in lines if x)
    inner = (_legal_bg() + f'<div class="card a" style="left:50%;top:50%;transform:translate(-50%,-50%);width:1400px;text-align:center;'
             f'background:rgba(10,10,12,.88)"><div style="font-family:{p["mono"]};font-size:24px;letter-spacing:6px;color:{p["accent"]}">{esc(kicker)}</div>'
             f'<div class="big" style="font-size:84px;margin:16px 0 6px">{esc(title)}</div>{rows}</div>')
    return render(inner, out, p, transparent=False)


def episode_card(n, title, out, palette=None, sub=""):
    p = _pal(palette)
    inner = (f'<div class="a" style="inset:0;background:#0b0b0d"></div><div class="a" style="left:0;right:0;top:50%;transform:translateY(-50%);text-align:center">'
             f'<div style="font-family:{p["mono"]};font-size:34px;letter-spacing:10px;color:{p["accent"]}">EPISODE {esc(n)}</div>'
             f'<div class="big" style="font-size:130px;margin-top:10px">{esc(title)}</div>'
             + (f'<div style="font-family:{p["mono"]};font-size:28px;margin-top:16px;color:{p["muted"]};text-transform:uppercase">{esc(sub)}</div>' if sub else "")
             + "</div>")
    return render(inner, out, p, transparent=False)


def black_text(text, out, palette=None, sub="", colour=None):
    """Kinetic line on black (full frame)."""
    p = _pal(palette)
    inner = (f'<div class="a" style="inset:0;background:#000"></div>'
             f'<div class="a" style="left:120px;right:120px;top:50%;transform:translateY(-50%);text-align:center">'
             f'<div class="big" style="font-size:110px;color:{colour or p["white"]}">{esc(text)}</div>'
             + (f'<div style="font-family:{p["mono"]};font-size:30px;letter-spacing:6px;margin-top:24px;color:{p["muted"]};text-transform:uppercase">{esc(sub)}</div>' if sub else "")
             + "</div>")
    return render(inner, out, p, transparent=False)


# Texas punishment ranges by offense level (Penal Code ch. 12) - fixed table, the brain only names the level.
PENALTY = {"capital": "LIFE OR DEATH", "F1": "5 TO 99 YEARS OR LIFE", "F2": "2 TO 20 YEARS", "F3": "2 TO 10 YEARS",
           "SJF": "180 DAYS TO 2 YEARS", "MA": "UP TO 1 YEAR", "MB": "UP TO 180 DAYS", "MC": "FINE UP TO $500"}
PENALTY_NAME = {"capital": "CAPITAL FELONY", "F1": "FIRST-DEGREE FELONY", "F2": "SECOND-DEGREE FELONY",
                "F3": "THIRD-DEGREE FELONY", "SJF": "STATE JAIL FELONY", "MA": "CLASS A MISDEMEANOR",
                "MB": "CLASS B MISDEMEANOR", "MC": "CLASS C MISDEMEANOR"}


def penalty_card(charge, level, out, palette=None):
    """Charge + its punishment range (Texas Penal Code 12.xx). None when the level is unknown."""
    if level not in PENALTY:
        return None
    p = _pal(palette)
    inner = (_legal_bg() + f'<div class="paper" style="left:360px;top:300px;width:1200px;transform:rotate(-1deg)">'
             f'<div class="k">THE CHARGE · Texas Penal Code ch. 12</div><div class="t">{esc(charge)}</div>'
             f'<div style="font-size:30px">{PENALTY_NAME[level]}</div></div>'
             f'<div class="a" style="right:300px;bottom:180px;background:{p["danger"]};color:{p["white"]};font-family:{p["head"]};'
             f'font-weight:700;font-size:80px;padding:10px 40px;border:6px solid {p["white"]};transform:rotate(-3deg)">{PENALTY[level]}</div>')
    return render(inner, out, p, transparent=False)


# ---------------------------------------------------------------- court frames per style (2026-11-25: the 6 documentary
# styles looked the same for 80% of the video - the court footage had one frame for all)
def scorebug(left, mid, right, out, palette=None, sub=""):
    """Instant Replay: sports-broadcast bug top-left (replaces the date pill): [COURT][STATE v. REED][● LIVE] + a line."""
    p = _pal(palette)
    inner = (f'<div class="a" style="left:40px;top:28px;font-family:{p["sans"]};font-weight:800;text-transform:uppercase;'
             f'filter:drop-shadow(0 8px 18px rgba(0,0,0,.45))"><div style="display:flex;align-items:stretch">'
             f'<div style="background:{p["accent"]};color:{p["accent_ink"]};padding:8px 16px;font-size:25px;letter-spacing:1px">{esc(left)}</div>'
             f'<div style="background:rgba(8,12,20,.93);color:#fff;padding:8px 18px;font-size:25px">{esc(mid)}</div>'
             + (f'<div style="background:{p["danger"]};color:#fff;padding:8px 14px;font-size:21px;display:flex;align-items:center">'
                f'● {esc(right)}</div>' if right else "")
             + "</div>"
             + (f'<div style="display:inline-block;background:rgba(8,12,20,.80);color:{p["accent"]};padding:5px 16px;font-size:19px;'
                f'letter-spacing:2px;margin-top:3px">{esc(sub)}</div>' if sub else "")
             + "</div>")
    return render(inner, out, p)


def corner_chip(kicker, text, out, palette=None):
    """Verdict First: the outcome stays on screen for the whole video (top-right, under the footage badge)."""
    p = _pal(palette)
    inner = (f'<div class="a" style="right:40px;top:84px;background:rgba(10,10,12,.88);border-right:9px solid {p["danger"]};'
             f'padding:10px 20px 12px;box-shadow:0 8px 22px rgba(0,0,0,.45);text-align:right">'
             f'<div style="font-family:{p["mono"]};font-size:17px;letter-spacing:4px;color:#bdbdbd;text-transform:uppercase">{esc(kicker)}</div>'
             f'<div class="big" style="font-family:{p["head"]};font-size:46px;color:#fff;margin-top:2px">{esc(text)}</div></div>')
    return render(inner, out, p)


def cork(out, palette=None):
    """Evidence Board: the cork board behind the court footage."""
    p = _pal(palette)
    inner = ('<div class="a" style="inset:0;background:radial-gradient(circle at 40% 40%,#8a6440,#4a3220 75%)"></div>'
             '<div class="a" style="inset:0;opacity:.18;background-image:radial-gradient(#000 1px,transparent 1.6px);'
             'background-size:7px 7px"></div>')
    return render(inner, out, p, transparent=False)


def pinned_overlay(box, out, palette=None, note="EXHIBIT · COURT RECORDING"):
    """Evidence Board court frame: push pins + tape on the photo of the footage, a small paper note. box = (x, y, w, h)."""
    p = _pal(palette)
    x, y, w, h = box
    pin = (f'width:30px;height:30px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#ff6b6b,{p["danger"]} 60%,#5a0d14);'
           f'box-shadow:0 5px 8px rgba(0,0,0,.55)')
    tape = 'width:170px;height:44px;background:rgba(240,230,200,.72);box-shadow:0 2px 4px rgba(0,0,0,.25)'
    inner = (f'<div class="a" style="left:{x + 70}px;top:{y - 16}px;{pin}"></div>'
             f'<div class="a" style="left:{x + w - 100}px;top:{y - 16}px;{pin}"></div>'
             f'<div class="a" style="left:{x - 60}px;top:{y + h - 34}px;transform:rotate(-38deg);{tape}"></div>'
             f'<div class="a" style="left:{x + w - 110}px;top:{y + h - 30}px;transform:rotate(36deg);{tape}"></div>'
             f'<div class="a" style="left:{x + w - 330}px;top:{y + h + 8}px;background:{p["paper"]};color:{p["ink"]};'
             f'font-family:{p["mono"]};font-weight:700;font-size:20px;letter-spacing:2px;padding:6px 14px;transform:rotate(-2deg);'
             f'box-shadow:0 6px 12px rgba(0,0,0,.45)">{esc(note)}</div>')
    return render(inner, out, p)


def look_layer(kind, out, palette=None):
    """The style's grade as ONE transparent PNG on top of the footage (2026-11-25: the vignette / noise filters made a
    render 2.5x slower): cinema = film letterbox + warm tint + vignette; episode = teal tint + vignette. None otherwise."""
    p = _pal(palette)
    vig = '<div class="a" style="inset:0;background:radial-gradient(ellipse at center,rgba(0,0,0,0) 52%,rgba(0,0,0,.55) 100%)"></div>'
    if kind == "cinema":
        inner = ('<div class="a" style="inset:0;background:rgba(120,80,30,.10)"></div>' + vig +
                 '<div class="a" style="left:0;right:0;top:0;height:118px;background:#000"></div>'
                 '<div class="a" style="left:0;right:0;bottom:0;height:118px;background:#000"></div>')
    elif kind == "episode":
        inner = '<div class="a" style="inset:0;background:rgba(20,120,125,.09)"></div>' + vig
    else:
        return None
    return render(inner, out, p)
