"""Court Beacon TV look - graphics ("cinema + evidence board", approved style v2, Oct 2026).

Every element is an HTML snippet rendered to a PNG with Playwright/Chromium (the same engine as the Overruled
look, see ov_gfx). PNGs are cached by content hash, so re-runs and repeated cards cost nothing.

Canvas map (1920x1080)
    top bar        y 0-64      logo, wordmark, case label, hearing steps, ON RECORD dot
    cinema         y 64-928    the active Zoom tile, full width (cropped 16:9 -> 2.22:1, biased upward)
    bottom strip   y 928-1080  ALL text overlays (left, x 56-1400) + the other Zoom tiles as small monitors (right)
Faces are never covered: text lives only in the top bar and the bottom strip (see overlay_sched SAFE_ZONES["cb"]).
"""
import hashlib
import html as H
import re
from pathlib import Path

from ucf import ov_gfx as _OV        # shared Chromium instance

FONTS = Path(__file__).resolve().parent.parent / "hf" / "fonts"      # styles/court_beacon/hf/fonts
LOGO = None

W, H_ = 1920, 1080
TOP_H = 64
CINEMA = (0, 64, 1920, 864)
STRIP_Y = 928
THUMB_W, THUMB_H, THUMB_Y, THUMB_GAP, THUMB_RIGHT = 228, 128, 938, 16, 40
HOOK_RECT = (0, 96, 1920, 888)
# TWO-SHOT (owner change, Oct 2026): the person on the stand AND the judge both big enough for a 40-60 audience
MAIN2 = (0, 64, 1268, 864)                    # witness / defendant
SIDE_TOP = (1280, 64, 640, 480)               # judge (4:3, the Zoom judge tile is 4:3 -> no crop, 1.33x)
SIDE_BOT = (1280, 556, 640, 372)              # courtroom wide shot (or the brand panel when there is none)
POLAROID_HOLE = (136, 186, 880, 495)          # footage keeps playing inside the evidence photo at case start
STEPS = ["CALLED", "PLEA", "TESTIMONY", "RULING", "CLOSED"]
PHASE_STEP = {"call": 0, "plea_or_admonish": 1, "evidence_or_argument": 2, "ruling": 3, "wrap_up": 4}

_CSS_T = """
@font-face{font-family:Osw;font-weight:600;src:url(__F__/oswald-latin-600-normal.woff2)}
@font-face{font-family:Osw;font-weight:700;src:url(__F__/oswald-latin-700-normal.woff2)}
@font-face{font-family:Mono;font-weight:500;src:url(__F__/ibm-plex-mono-latin-500-normal.woff2)}
@font-face{font-family:Mono;font-weight:600;src:url(__F__/ibm-plex-mono-latin-600-normal.woff2)}
@font-face{font-family:Ser;font-weight:600;font-style:italic;src:url(__F__/source-serif-4-latin-600-italic.woff2)}
@font-face{font-family:Ser;font-weight:700;src:url(__F__/source-serif-4-latin-700-normal.woff2)}
@font-face{font-family:Int;font-weight:600;src:url(__F__/inter-latin-600-normal.woff2)}
@font-face{font-family:Int;font-weight:800;src:url(__F__/inter-latin-800-normal.woff2)}
:root{--ink:#07080C;--bar:#06070A;--line:#2A2F3D;--paper:#EDE6D6;--orange:#F2792B;--purple:#5B2A86;--blue:#3CC8FF;
 --gold:#E6B14A;--red:#D63A2F;--text:#F1EEE8;--mute:#9095A6}
*{box-sizing:border-box;margin:0;padding:0}
body{color:var(--text);font-family:Int}
.abs{position:absolute}
.osw{font-family:Osw;font-weight:700}
.mono{font-family:Mono;font-weight:600}
.ser{font-family:Ser;font-weight:600;font-style:italic}
.kick{font-family:Mono;font-weight:600;font-size:20px;letter-spacing:4px;color:var(--blue)}
.tag{display:inline-flex;align-items:center;gap:12px;font-family:Mono;font-weight:600;font-size:22px;letter-spacing:4px;background:var(--orange);color:#140A02;padding:7px 16px}
.stamp{position:absolute;font-family:Osw;font-weight:700;letter-spacing:6px;color:var(--red);border:6px solid var(--red);padding:4px 22px;transform:rotate(-8deg)}
.sub{display:inline-flex;align-items:center;gap:14px;background:var(--red);color:#fff;font-family:Osw;font-weight:700;letter-spacing:3px;border-radius:10px}
.sub svg{width:1em;height:1em}
.pol{position:absolute;background:#F4F1EA;box-shadow:0 26px 60px rgba(0,0,0,.65)}
.pol .cap{position:absolute;left:18px;bottom:14px;font-family:Mono;font-weight:600;letter-spacing:2px;color:#2B2924}
.tape{position:absolute;width:150px;height:40px;background:rgba(230,215,170,.55)}
"""
BELL = _OV.BELL


def bell(px):
    return BELL.replace("<svg", f'<svg style="width:{px}px;height:{px}px"', 1)


def set_fonts(d):
    global FONTS
    FONTS = Path(d)


def set_logo(p):
    global LOGO
    LOGO = Path(p).resolve() if p and Path(p).exists() else None


def css():
    return _CSS_T.replace("__F__", Path(FONTS).resolve().as_uri())


def esc(t):
    return H.escape(str(t or ""), quote=False)


def render(inner, out, size=(W, H_), transparent=True, body_style=""):
    out = Path(out)
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head>'
           f'<body style="width:{size[0]}px;height:{size[1]}px;position:relative;overflow:hidden;{body_style}">{inner}</body></html>')
    key = hashlib.md5(doc.encode()).hexdigest()[:12]
    p = out.with_name(f"{out.stem}_{key}.png")
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    hp = p.with_suffix(".html")
    hp.write_text(doc, encoding="utf-8")
    page = _OV._browser().new_page(viewport={"width": size[0], "height": size[1]})
    try:
        page.goto(hp.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(200)
        page.screenshot(path=str(p), omit_background=transparent)
    finally:
        page.close()
    return p


def _logo(px):
    return f'<img src="{Path(LOGO).as_uri()}" style="width:{px}px;height:{px}px;object-fit:contain">' if LOGO else ""


def thumb_rects(n):
    n = max(0, min(2, n))          # max 2 monitors: the strip text (x 56-1400) must never touch them
    x = W - THUMB_RIGHT - THUMB_W * n - THUMB_GAP * (n - 1)
    return [(x + i * (THUMB_W + THUMB_GAP), THUMB_Y, THUMB_W, THUMB_H) for i in range(n)]


# ------------------------------------------------------------------------------------------- static canvas
def background(out):
    inner = ('<div class="abs" style="inset:0;background:radial-gradient(1200px 700px at 30% 35%, rgba(91,42,134,.28), transparent 70%),'
             'radial-gradient(900px 600px at 90% 100%, rgba(242,121,43,.14), transparent 70%),linear-gradient(180deg,#0A0B11,#06070A)"></div>'
             '<div class="abs" style="inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),'
             'linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:48px 48px"></div>'
             f'<div class="abs" style="left:0;top:0;width:{W}px;height:{TOP_H}px;background:var(--bar);border-bottom:1px solid #1E222E"></div>'
             f'<div class="abs" style="left:0;top:{STRIP_Y}px;width:{W}px;height:{H_ - STRIP_Y}px;background:var(--bar)"></div>')
    return render(inner, out, transparent=False)


def _chip(x, y, h, lab, fs=20):
    return (f'<div class="abs mono" style="left:{x + 10}px;top:{y + h - fs - 22}px;font-size:{fs}px;letter-spacing:3px;'
            f'background:rgba(6,7,10,.85);padding:4px 12px;border-left:4px solid var(--orange)">{esc(lab)}</div>')


def frame_two(side_labels, out):
    """Two-shot layer: fades, viewfinder corner on the main picture, borders + big labels on the side panels,
    brand panel when there is no second side picture."""
    mx, my, mw, mh = MAIN2
    s = (f'<div class="abs" style="left:0;top:{STRIP_Y - 90}px;width:{mw}px;height:90px;background:linear-gradient(0deg,#06070A,rgba(6,7,10,0))"></div>'
         '<div class="abs" style="left:28px;top:92px;width:54px;height:54px;border:solid rgba(255,255,255,.75);border-width:3px 0 0 3px"></div>')
    for rect, lab in zip((SIDE_TOP, SIDE_BOT), side_labels):
        x, y, w, h = rect
        if lab is None:
            s += (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:#0B0C12;border:1px solid #2A2F3D;'
                  'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px">'
                  f'{_logo(120)}<div class="osw" style="font-size:34px;letter-spacing:4px">COURT BEACON TV</div>'
                  '<div class="mono" style="font-size:18px;letter-spacing:3px;color:var(--mute)">LIVE FROM THE 187TH DISTRICT COURT</div></div>')
            continue
        s += f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border:2px solid #2A2F3D"></div>' + _chip(x, y, h, lab)
    return render(s, out)


def frame(n_thumbs, labels, out):
    """Static layer over the footage: bottom fade into the strip, viewfinder corners, monitor borders + labels."""
    s = (f'<div class="abs" style="left:0;top:{STRIP_Y - 120}px;width:{W}px;height:120px;background:linear-gradient(0deg,#06070A,rgba(6,7,10,0))"></div>'
         '<div class="abs" style="left:28px;top:92px;width:54px;height:54px;border:solid rgba(255,255,255,.75);border-width:3px 0 0 3px"></div>'
         '<div class="abs" style="left:1838px;top:92px;width:54px;height:54px;border:solid rgba(255,255,255,.75);border-width:3px 3px 0 0"></div>')
    for (x, y, w, h), lab in zip(thumb_rects(n_thumbs), labels):
        s += (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border:1px solid #3A3F4E"></div>'
              f'<div class="abs mono" style="left:{x + 6}px;top:{y + h - 26}px;font-size:14px;letter-spacing:2px;background:rgba(6,7,10,.82);padding:2px 7px">{esc(lab)}</div>')
    return render(s, out)


def topbar(case_label, step, out):
    """step: index into STEPS (None = no hearing steps shown)."""
    st = ""
    if step is not None:
        st = " &#9656; ".join(
            f'<span style="color:{"#C9CBD3" if i < step else ("var(--blue)" if i == step else "#4A4F5E")}">{n}</span>'
            for i, n in enumerate(STEPS))
    inner = (f'<div class="abs" style="left:0;top:0;width:{W}px;height:{TOP_H}px;display:flex;align-items:center;padding:0 40px;gap:20px">'
             f'{_logo(40)}<span class="osw" style="font-size:26px;letter-spacing:3px">COURT BEACON TV</span>'
             '<span style="width:1px;height:28px;background:#2A2F3D"></span>'
             f'<span class="mono" style="font-size:20px;letter-spacing:2px;color:#C9CBD3">{esc(case_label)}</span>'
             f'<span class="mono" style="margin-left:auto;font-size:16px;letter-spacing:2px">{st}</span>'
             '<span class="mono" style="font-size:20px;letter-spacing:2px;margin-left:26px"><b style="color:var(--red)">&#9679;</b> ON RECORD</span></div>')
    return render(inner, out)


# ------------------------------------------------------------------------------------------- hook
def hook(headline, kicker, meta, countdown, out):
    """Layers over the hook footage (footage at HOOK_RECT): letterbox bars, scrims, kicker, headline with one
    highlighted word (the last word, or the one wrapped in *stars*)."""
    words = headline.split()
    hi = next((i for i, w in enumerate(words) if w.startswith("*") and w.endswith("*")), len(words) - 1)
    parts = []
    for i, w in enumerate(words):
        w = esc(w.strip("*"))
        parts.append(f'<span style="display:inline-block;line-height:1;background:var(--orange);color:#0A0603;padding:4px 16px 6px">{w}</span>'
                     if i == hi else w)
    fs = 100 if len(headline) <= 34 else (84 if len(headline) <= 48 else 70)
    inner = (f'<div class="abs" style="left:0;top:96px;width:{W}px;height:888px;background:linear-gradient(90deg,rgba(6,7,10,.85) 0%,'
             'rgba(6,7,10,.2) 42%,transparent 65%),linear-gradient(0deg,rgba(6,7,10,.7),transparent 35%)"></div>'
             f'<div class="abs" style="left:0;top:0;width:{W}px;height:96px;background:#000"></div>'
             f'<div class="abs" style="left:0;top:984px;width:{W}px;height:96px;background:#000"></div>'
             f'<div class="abs mono" style="left:96px;top:136px;font-size:22px;letter-spacing:5px;color:var(--blue)">{esc(kicker)}</div>'
             f'<div class="abs mono" style="left:96px;top:172px;font-size:20px;letter-spacing:3px;color:var(--mute)">{esc(meta)}</div>'
             f'<div class="abs osw" style="left:96px;bottom:140px;font-size:{fs}px;line-height:1.12;text-transform:uppercase;width:1500px">{" ".join(parts)}</div>'
             f'<div class="abs mono" style="right:96px;top:1018px;font-size:20px;letter-spacing:4px;color:var(--mute)">{esc(countdown)}</div>')
    return render(inner, out)


# ------------------------------------------------------------------------------------------- case open (4 s insert)
def case_open(file_no, title, rows, live_tc, out):
    """Polaroid frame around POLAROID_HOLE (transparent centre -> the live footage shows through), tape, case data, OPEN stamp."""
    x, y, w, h = POLAROID_HOLE
    b, bot = 16, 58
    fs = 82 if len(title) <= 26 else (66 if len(title) <= 40 else 54)
    rws = "".join(f'<span style="color:var(--mute)">{esc(k):<8}</span> {esc(v)}<br>' for k, v in rows if v)
    inner = (f'<div class="abs" style="left:{x - b}px;top:{y - b}px;width:{w + 2 * b}px;height:{b}px;background:#F4F1EA"></div>'
             f'<div class="abs" style="left:{x - b}px;top:{y + h}px;width:{w + 2 * b}px;height:{bot}px;background:#F4F1EA;box-shadow:0 26px 60px rgba(0,0,0,.6)"></div>'
             f'<div class="abs" style="left:{x - b}px;top:{y}px;width:{b}px;height:{h}px;background:#F4F1EA"></div>'
             f'<div class="abs" style="left:{x + w}px;top:{y}px;width:{b}px;height:{h}px;background:#F4F1EA"></div>'
             f'<div class="abs mono" style="left:{x + 2}px;top:{y + h + 16}px;font-size:20px;letter-spacing:2px;color:#2B2924">EXHIBIT A &middot; LIVE {esc(live_tc)}</div>'
             f'<div class="tape" style="left:{x + 40}px;top:{y - 34}px;transform:rotate(-8deg)"></div>'
             f'<div class="tape" style="left:{x + w - 180}px;top:{y - 30}px;transform:rotate(6deg)"></div>'
             '<div class="abs" style="left:1110px;top:220px;width:740px">'
             f'<div class="mono" style="font-size:24px;letter-spacing:5px;color:var(--orange)">CASE FILE {esc(file_no)}</div>'
             f'<div class="osw" style="font-size:{fs}px;line-height:1.04;margin-top:12px;text-transform:uppercase">{esc(title)}</div>'
             f'<div style="margin-top:30px;font-family:Mono;font-weight:500;font-size:24px;line-height:1.8;color:#D8DAE0;white-space:pre">{rws}</div>'
             '<div class="stamp" style="left:420px;top:500px;font-size:60px">OPEN</div></div>')
    return render(inner, out)


# ------------------------------------------------------------------------------------------- in-case overlays (strip only)
_NUM = re.compile(r"^\s*(\$?\d[\d,.]*\s?(?:%|k|K|million)?)\s+(.*)$")


def _rule(width):
    return f'<div class="abs" style="left:56px;top:{STRIP_Y + 2}px;width:{width}px;height:3px;background:linear-gradient(90deg,var(--orange),rgba(242,121,43,0))"></div>'


def key_fact(text, out):
    m = _NUM.match(text or "")
    if m:
        num, rest = m.group(1), m.group(2)
        body = (f'<div class="osw" style="font-size:112px;line-height:.9;color:var(--orange)">{esc(num)}</div>'
                f'<div><div class="kick">KEY FACT &middot; FROM THE RECORD</div><div style="font-family:Int;font-weight:800;font-size:36px;line-height:1.15;margin-top:8px;width:1150px">{esc(rest)}</div></div>')
    else:
        body = (f'<div><div class="kick">KEY FACT &middot; FROM THE RECORD</div><div style="font-family:Int;font-weight:800;font-size:38px;line-height:1.15;margin-top:8px;width:1330px">{esc(text)}</div></div>')
    return render(_rule(900) + f'<div class="abs" style="left:56px;top:{STRIP_Y + 16}px;display:flex;align-items:center;gap:28px">{body}</div>', out)


def so_far(text, out):
    beats = [b.strip(" .") for b in re.split(r"\s*(?:;|·|•|\.\s)\s*", text or "") if b.strip(" .")][:3]
    if not beats:
        beats = [text]
    cols = "".join(f'<div><span class="mono" style="font-size:20px;color:var(--orange)">{i + 1:02d}</span><br>{esc(b)}</div>' for i, b in enumerate(beats))
    return render(_rule(700) + f'<div class="abs" style="left:56px;top:{STRIP_Y + 14}px;width:1340px"><div class="kick">SO FAR</div>'
                  f'<div style="display:grid;grid-template-columns:repeat({len(beats)},1fr);gap:26px;margin-top:8px;font-family:Int;font-weight:600;font-size:26px;line-height:1.22">{cols}</div></div>', out)


def verdict_q(text, out):
    return render(_rule(600) + f'<div class="abs" style="left:56px;top:{STRIP_Y + 18}px;width:1340px"><div class="kick" style="color:var(--orange)">YOUR VERDICT &middot; COMMENT BELOW</div>'
                  f'<div class="ser" style="font-size:42px;line-height:1.15;margin-top:8px">{esc(text)}</div></div>', out)


def watch(text, out, rect=None):
    """Orange brackets framing the main picture + WATCH tag (never on a face: corners only)."""
    rx, ry, rw, rh = rect or (240, 64, 1440, 864)
    L, x0, x1, y0, y1 = 70, rx + 60, rx + rw - 60, ry + 46, ry + rh - 28
    s = ""
    for x, y, bw in [(x0, y0, "5px 0 0 5px"), (x1 - L, y0, "5px 5px 0 0"), (x0, y1 - L, "0 0 5px 5px"), (x1 - L, y1 - L, "0 5px 5px 0")]:
        s += f'<div class="abs" style="left:{x}px;top:{y}px;width:{L}px;height:{L}px;border:solid var(--orange);border-width:{bw}"></div>'
    s += f'<div class="abs" style="left:{x0}px;top:{y0 - 36}px"><span class="tag" style="font-size:20px">WATCH &middot; {esc(text)}</span></div>'
    return render(s, out)


def on_record(ts, who_q, q, who_a, a, out):
    lab = 'display:inline-block;width:170px;font-size:16px;letter-spacing:3px;color:var(--mute)'
    fs = 38 if max(len(q or ""), len(a or "")) <= 70 else 32
    return render(f'<div class="abs" style="left:56px;top:{STRIP_Y + 14}px;width:1340px"><div class="kick">ON THE RECORD &middot; {esc(ts)}</div>'
                  f'<div style="margin-top:6px;line-height:1.18;white-space:nowrap;overflow:hidden"><span class="mono" style="{lab}">{esc(who_q)}</span><span class="ser" style="font-size:{fs}px">"{esc(q)}"</span></div>'
                  f'<div style="line-height:1.18;white-space:nowrap;overflow:hidden"><span class="mono" style="{lab}">{esc(who_a)}</span><span class="ser" style="font-size:{fs}px;color:var(--orange)">"{esc(a)}"</span></div></div>', out)


# ------------------------------------------------------------------------------------------- subscribe
def sub_button(out):
    return render(f'<div class="abs" style="left:1000px;top:88px"><span class="sub" style="font-size:26px;padding:10px 20px">{BELL}SUBSCRIBE</span></div>', out)


def sub_pill(out):
    return render(f'<div class="abs" style="right:34px;top:12px;height:40px;display:flex;align-items:center;background:var(--red);border-radius:20px;padding:0 20px;gap:10px">'
                  f'<span class="osw" style="font-size:22px;letter-spacing:3px;display:flex;align-items:center;gap:10px">{bell(20)}SUBSCRIBE NOW</span></div>', out)


def sub_banner(out):
    return render(f'<div class="abs" style="left:0;top:{STRIP_Y}px;width:{W}px;height:{H_ - STRIP_Y}px;background:var(--red);display:flex;align-items:center;gap:26px;padding:0 60px">'
                  f'<span style="width:64px;height:64px;display:inline-flex">{bell(64)}</span>'
                  '<div><div class="osw" style="font-size:52px;letter-spacing:3px;line-height:1">SUBSCRIBE &middot; TURN ON THE BEACON</div>'
                  '<div style="font-family:Int;font-weight:600;font-size:26px;margin-top:6px">Real court cases, every week. Tap the bell so you never miss a case file.</div></div></div>', out)


# ------------------------------------------------------------------------------------------- recap / closing / thumbnail
def briefing(text, label, frames, status, out):
    """Layer over the blurred stage: kicker, three polaroids (court / witness / judge), narrated text, stamp, Subscribe."""
    s = f'<div class="abs mono" style="left:0;width:{W}px;top:90px;text-align:center;font-size:24px;letter-spacing:8px;color:var(--blue)">THE BRIEFING &middot; {esc(label)}</div>'
    caps = ["THE COURTROOM", "ON THE STAND", "THE JUDGE"]
    xs = {1: [760], 2: [480, 1040], 3: [230, 760, 1290]}[max(1, min(3, len(frames)))]
    for i, (fp, x) in enumerate(zip(frames[:3], xs)):
        r = [-3, 1.5, -1.5][i]
        cap = fp[1] if isinstance(fp, tuple) else caps[i]
        img = fp[0] if isinstance(fp, tuple) else fp
        s += (f'<div class="pol" style="left:{x}px;top:170px;transform:rotate({r}deg);padding:12px 12px 46px">'
              f'<img src="{Path(img).resolve().as_uri()}" style="display:block;width:400px;height:225px;object-fit:cover">'
              f'<div class="cap" style="font-size:16px;bottom:12px">{esc(cap)}</div></div>')
    fs = 48 if len(text) <= 190 else 40
    s += (f'<div class="abs ser" style="left:260px;top:590px;width:1400px;text-align:center;font-style:normal;font-weight:700;font-size:{fs}px;line-height:1.3">{esc(text)}</div>'
          f'<div class="abs" style="left:0;width:{W}px;top:900px;text-align:center"><span class="sub" style="font-size:30px;padding:14px 28px">{BELL}SUBSCRIBE &middot; TURN ON THE BEACON</span></div>')
    if status:
        s += f'<div class="stamp" style="left:1460px;top:790px;font-size:40px">{esc(status)}</div>'
    return render(s, out)


def case_files(rows, question, options, out):
    """Closing board: polaroid wall (img, name, outcome) + YOUR VERDICT quiz + big Subscribe box. Opaque."""
    n = max(1, min(4, len(rows)))
    pw = {1: 640, 2: 560, 3: 456, 4: 380}[n]
    ph = int(pw * 9 / 16)
    gap = 60
    total = n * (pw + 24) + (n - 1) * gap
    x = (W - total) // 2
    s = (background_html() +
         f'<div class="abs" style="left:0;width:{W}px;top:70px;text-align:center"><div class="mono" style="font-size:22px;letter-spacing:8px;color:var(--blue)">187TH DISTRICT COURT &middot; BEXAR COUNTY</div>'
         '<div class="osw" style="font-size:86px;letter-spacing:3px;margin-top:6px">TODAY\'S CASE FILES</div></div>')
    for i, (img, name, res) in enumerate(rows[:n]):
        r = [-2, 1.5, -1, 1][i]
        s += (f'<div class="pol" style="left:{x}px;top:260px;transform:rotate({r}deg);padding:12px 12px 70px">'
              f'<img src="{Path(img).resolve().as_uri()}" style="display:block;width:{pw}px;height:{ph}px;object-fit:cover">'
              f'<div class="cap" style="font-family:Int;font-weight:800;font-size:24px;letter-spacing:0;bottom:22px">{esc(name)}</div></div>'
              f'<div class="stamp" style="left:{x + 60}px;top:{260 + ph - 70}px;font-size:28px;background:rgba(244,241,234,.7)">{esc(res)}</div>')
        x += pw + 24 + gap
    opts = options or {}
    if isinstance(opts, list):
        opts = {k: v for k, v in zip("ABC", opts)}
    ot = " &nbsp; ".join(f"{k} &middot; {esc(v)}" for k, v in opts.items())
    s += (f'<div class="abs" style="left:170px;top:720px;width:1000px;background:var(--paper);color:#1B1A17;padding:24px 32px">'
          '<div class="mono" style="font-size:20px;letter-spacing:4px;color:#B3471A">YOUR VERDICT</div>'
          f'<div class="ser" style="font-size:38px;line-height:1.2;margin-top:6px">{esc(question)}</div>'
          f'<div class="mono" style="font-size:24px;margin-top:12px">{ot}</div></div>'
          '<div class="abs" style="left:1230px;top:720px;width:520px;height:240px;background:var(--red);border-radius:14px;padding:26px 32px">'
          f'<div class="osw" style="font-size:60px;line-height:1;display:flex;align-items:center;gap:16px">{bell(54)}SUBSCRIBE</div>'
          '<div style="font-family:Int;font-weight:600;font-size:26px;margin-top:14px;line-height:1.3">Turn on the beacon. New case files every week.</div></div>')
    return render(s, out, transparent=False)


def background_html():
    return ('<div class="abs" style="inset:0;background:radial-gradient(1200px 700px at 30% 35%, rgba(91,42,134,.28), transparent 70%),'
            'radial-gradient(900px 600px at 90% 100%, rgba(242,121,43,.14), transparent 70%),linear-gradient(180deg,#0A0B11,#06070A)"></div>'
            '<div class="abs" style="inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),'
            'linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:48px 48px"></div>')


def thumbnail(frame_png, text, gold_word, out):
    """1280x720: black left, face right with blue/ember light, kicker, 2-3 line Oswald text, ONE word in an orange block."""
    words = (text or "").split()
    gw = (gold_word or "").strip().lower()
    out_words = []
    for w in words:
        if w.strip(".,!?'\"").lower() == gw and gw:
            out_words.append(f'<span style="display:inline-block;line-height:1;margin-top:10px;background:var(--orange);color:#0A0603;padding:6px 16px 10px;text-shadow:none">{esc(w)}</span>')
            gw = ""
        else:
            out_words.append(esc(w))
    n = len(words)
    lines = [out_words[i:i + 2] for i in range(0, n, 2)] if n > 2 else [out_words]
    fs = 130 if n <= 4 else 108
    inner = ('<div class="abs" style="inset:0;background:#06070A"></div>'
             f'<div class="abs" style="left:420px;top:0;width:860px;height:720px;overflow:hidden"><img src="{Path(frame_png).resolve().as_uri()}" style="width:1280px;height:720px;object-fit:cover;margin-left:-260px;filter:contrast(1.15) saturate(.9)"></div>'
             '<div class="abs" style="left:420px;top:0;width:860px;height:720px;background:linear-gradient(90deg,#06070A 0%,rgba(6,7,10,.2) 30%,transparent 55%),linear-gradient(200deg,rgba(60,200,255,.25),transparent 40%),linear-gradient(20deg,rgba(242,121,43,.35),transparent 45%)"></div>'
             '<div class="abs mono" style="left:44px;top:46px;font-size:24px;letter-spacing:6px;color:var(--blue)">FROM THE COURT RECORD</div>'
             f'<div class="abs osw" style="left:44px;top:104px;font-size:{fs}px;line-height:1.02;text-transform:uppercase;text-shadow:0 6px 30px rgba(0,0,0,.8)">{"<br>".join(" ".join(l) for l in lines)}</div>'
             + (f'<img class="abs" src="{Path(LOGO).as_uri()}" style="right:28px;bottom:24px;width:96px;height:96px">' if LOGO else ""))
    return render(inner, out, size=(1280, 720), transparent=False)
