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


def chapter_card(kicker, date, keyword, out, palette=None):
    """HEARING 6 / JANUARY 28, 2025 / [THE BOND] - transparent; the renderer puts it on blurred footage."""
    p = _pal(palette)
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


def profile_card(photo, pills, out, palette=None, caption=""):
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
                 + pol + f'<div class="a" style="left:960px;top:300px">{stack}</div>')
        outs.append(render(inner, Path(out).with_name(f"{Path(out).stem}_{n}"), p, transparent=False))
    return outs
