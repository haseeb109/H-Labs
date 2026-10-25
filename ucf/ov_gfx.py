"""Overruled skin - graphics. Every overlay is an HTML snippet rendered to a transparent 1920x1080 PNG with
Playwright/Chromium (so type, slanted slabs and gradients look exactly like the approved storyboard).
PNGs are cached by content hash, so re-runs and repeated cards are free."""
import atexit
import hashlib
import re
import html as H
from pathlib import Path

from PIL import Image, ImageDraw

FONTS = Path(__file__).resolve().parent.parent / "hf" / "fonts"   # overridden by set_fonts() with the style pack's hf/fonts

_CSS_T = """
@font-face{font-family:Arch;font-weight:800;src:url(file://__F__/archivo-latin-800-normal.woff2)}
@font-face{font-family:Arch;font-weight:900;src:url(file://__F__/archivo-latin-900-normal.woff2)}
@font-face{font-family:Serif;font-weight:700;src:url(file://__F__/playfair-display-latin-700-normal.woff2)}
@font-face{font-family:Serif;font-weight:900;src:url(file://__F__/playfair-display-latin-900-normal.woff2)}
@font-face{font-family:Sans;font-weight:700;src:url(file://__F__/montserrat-latin-700-normal.woff2)}
@font-face{font-family:Sans;font-weight:800;src:url(file://__F__/montserrat-latin-800-normal.woff2)}
:root{--navy:#0E1A2B;--navy2:#16273E;--navy3:#1E3452;--cream:#F4EDE0;--gold:#E3B45A;--red:#D1222F;--mute:#A9B7CC}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:Sans,sans-serif;color:var(--cream)}
.abs{position:absolute}
.seal{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border:3px solid var(--gold);border-radius:50%;font-family:Serif;font-weight:900;font-size:28px;color:var(--gold)}
.brand{position:absolute;display:flex;align-items:center;gap:12px;font-family:Arch;font-weight:900;font-size:30px;letter-spacing:3px;background:rgba(10,19,34,.85);padding:8px 18px 8px 10px;border-left:5px solid var(--red)}
.lt{position:absolute;left:40px;top:786px;width:1280px}
.lt .k{display:inline-block;background:var(--red);font-family:Arch;font-weight:900;font-size:27px;letter-spacing:4px;padding:8px 26px 8px 22px;clip-path:polygon(0 0,100%% 0,calc(100%% - 18px) 100%%,0 100%%)}
.lt .n{background:var(--cream);color:#0E1A2B;font-family:Arch;font-weight:900;font-size:68px;padding:8px 30px;line-height:1.05;clip-path:polygon(0 0,100%% 0,calc(100%% - 26px) 100%%,0 100%%);width:1180px;white-space:nowrap}
.lt .s{background:var(--navy3);font-weight:700;font-size:29px;padding:12px 30px;color:var(--cream);border-left:8px solid var(--gold);width:1120px;white-space:nowrap;overflow:hidden}
.paper{position:absolute;background:var(--cream);color:#0E1A2B;padding:20px 26px;border-top:8px solid var(--red)}
.paper h4{font-family:Arch;font-weight:900;font-size:26px;letter-spacing:4px;color:var(--red);margin-bottom:6px}
.paper dt{font-weight:800;font-size:19px;letter-spacing:3px;color:#5d6b82;margin-top:12px}
.paper dd{font-family:Arch;font-weight:800;font-size:29px;line-height:1.15;margin-top:2px}
.take{position:absolute;left:40px;top:790px;width:1280px;background:var(--navy3);border-left:10px solid var(--gold);padding:18px 30px 20px}
.take .k{display:inline-block;background:var(--red);font-family:Arch;font-weight:900;font-size:22px;letter-spacing:4px;padding:5px 16px}
.take .t{font-family:Serif;font-weight:700;font-size:43px;line-height:1.22;margin-top:10px}
.sub{position:absolute;display:inline-flex;align-items:center;gap:14px;background:var(--red);color:#fff;font-family:Arch;font-weight:900;letter-spacing:2px;border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.45)}
.sub svg{width:1.05em;height:1.05em}
"""


LOGO = None


def set_logo(path):
    """Transparent channel logo (PNG). Replaces the CSS gold seal everywhere a seal is drawn."""
    global LOGO
    LOGO = Path(path).resolve() if path and Path(path).exists() else None


def _use_logo(inner):
    if not LOGO:
        return inner

    def rep(m):
        st = m.group(1) or ""
        w = re.search(r"width:(\d+)px", st)
        w = int(w.group(1)) if w else 44
        return (f'<img src="file://{LOGO}" style="width:{w + 12}px;height:{w + 12}px;object-fit:contain;'
                f'margin:-6px 4px -6px -4px;display:inline-block;vertical-align:middle">')
    return re.sub(r'<span class="seal"(?: style="([^"]*)")?>O</span>', rep, inner)


def set_fonts(d):
    global FONTS
    FONTS = Path(d)


def css():
    return _CSS_T.replace("__F__", str(FONTS)).replace("%%", "%")

BELL = ('<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 2a2 2 0 0 0-2 2v.3C7.2 5.1 6 7.4 6 10v4l-2 3v1h16v-1l-2-3v-4c0-2.6-1.2-4.9-4-5.7V4a2 2 0 0 0-2-2zm0 20a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 12 22z"/></svg>')

_pw = {"p": None, "b": None}


def _browser():
    if _pw["b"] is None:
        from playwright.sync_api import sync_playwright
        _pw["p"] = sync_playwright().start()
        _pw["b"] = _pw["p"].chromium.launch()
        atexit.register(close)
    return _pw["b"]


def close():
    try:
        if _pw["b"]:
            _pw["b"].close()
        if _pw["p"]:
            _pw["p"].stop()
    except Exception:
        pass
    _pw["b"] = _pw["p"] = None


def render(inner, out, size=(1920, 1080), body_style="", transparent=True):
    """Render an HTML snippet to PNG (cached by content hash next to `out`)."""
    out = Path(out)
    inner = _use_logo(inner)
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head>'
           f'<body style="width:{size[0]}px;height:{size[1]}px;position:relative;overflow:hidden;{body_style}">{inner}</body></html>')
    key = hashlib.md5(doc.encode()).hexdigest()[:12]
    p = out.with_name(f"{out.stem}_{key}.png")
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    page = _browser().new_page(viewport={"width": size[0], "height": size[1]})
    try:
        hp = p.with_suffix(".html")
        hp.write_text(doc, encoding="utf-8")
        page.goto("file://" + str(hp.resolve()))
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(250)          # let the embedded fonts settle
        page.screenshot(path=str(p), omit_background=transparent)
    finally:
        page.close()
    return p


def esc(t):
    return H.escape(str(t or ""), quote=False)


# --------------------------------------------------------------------------------------- building blocks
def background(out):
    inner = ('<div class="abs" style="inset:0;background:linear-gradient(115deg,#0A1322 0%,#12233A 55%,#0E1A2B 100%)"></div>'
             '<div class="abs" style="right:-300px;top:-200px;width:900px;height:1600px;background:linear-gradient(180deg,rgba(227,180,90,.10),rgba(227,180,90,0));transform:rotate(18deg)"></div>'
             '<div class="abs" style="left:0;right:0;bottom:0;height:9px;background:rgba(244,237,224,.15)"></div>')
    return render(inner, out, transparent=False)


def ticker(label, text, out):
    return render(f'<div class="abs" style="left:40px;top:1006px;width:1280px;height:48px;display:flex;align-items:center;background:rgba(10,19,34,.9);border-left:8px solid var(--red)">'
                  f'<span style="font-family:Arch;font-weight:900;font-size:24px;letter-spacing:3px;color:var(--gold);padding:0 18px;white-space:nowrap">{esc(label)}</span>'
                  f'<span style="font-weight:700;font-size:24px;color:var(--cream);white-space:nowrap;overflow:hidden">{esc(text)}</span></div>', out)


def brand(out):
    if LOGO:        # the logo already carries the word OVERRULED: show it alone, big enough to read
        return render(f'<img src="file://{LOGO}" style="position:absolute;left:46px;top:28px;width:104px;height:104px;object-fit:contain;filter:drop-shadow(0 4px 10px rgba(0,0,0,.55))">', out)
    return render('<div class="brand" style="left:60px;top:58px"><span class="seal">O</span>OVERRULED</div>', out)


def lower_third(kicker, name, sub, out):
    n = len(name)
    fs = 68 if n <= 30 else 58 if n <= 38 else 48
    return render(f'<div class="lt"><span class="k">{esc(kicker)}</span><div class="n" style="font-size:{fs}px">{esc(name)}</div>'
                  f'<div class="s">{esc(sub)}</div></div>', out)


def brief(case_label, rows, geom, out, title="THE BRIEF"):
    """rows = [(label, text)], geom = (x, y, w, h)."""
    x, y, w, h = geom
    dl = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in rows)
    return render(f'<div class="paper" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><h4>{esc(title)} · {esc(case_label)}</h4><dl>{dl}</dl></div>', out)


def quote_card(label, quote, who, geom, out):
    x, y, w, h = geom
    return render(f'<div class="paper" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><h4>{esc(label)}</h4>'
                  f'<div style="font-family:Serif;font-weight:900;font-size:46px;line-height:1.15;font-style:italic;margin-top:22px">{esc(quote)}</div>'
                  f'<div style="font-weight:800;font-size:21px;letter-spacing:3px;color:#5d6b82;margin-top:24px">{esc(who)}</div></div>', out)


def take(text, out):
    n = len(text.split())
    fs = 43 if n <= 24 else 38
    return render(f'<div class="take"><span class="k">OUR TAKE</span><div class="t" style="font-size:{fs}px">{esc(text)}</div></div>', out)


def exchange(ts, who_q, q, who_a, a, out):
    return render(
        '<div class="abs" style="left:40px;top:790px;width:1840px;display:flex;background:var(--navy3);border-left:10px solid var(--gold)">'
        f'<div style="padding:20px 30px;width:280px"><span style="background:var(--red);font-family:Arch;font-weight:900;font-size:22px;letter-spacing:4px;padding:5px 14px">THE EXCHANGE</span>'
        f'<div style="color:var(--mute);font-weight:700;font-size:22px;margin-top:12px">{esc(ts)}</div></div>'
        f'<div style="padding:18px 20px;flex:1"><div style="font-weight:800;font-size:22px;color:var(--gold);letter-spacing:3px">{esc(who_q)}</div>'
        f'<div style="font-family:Serif;font-weight:700;font-style:italic;font-size:42px;line-height:1.15">{esc(q)}</div></div>'
        f'<div style="padding:18px 28px;flex:1"><div style="font-weight:800;font-size:22px;color:var(--gold);letter-spacing:3px">{esc(who_a)}</div>'
        f'<div style="font-family:Serif;font-weight:700;font-style:italic;font-size:42px;line-height:1.15">{esc(a)}</div></div></div>', out)


def pill(out):
    return render(f'<div class="sub" style="left:1000px;top:58px;font-size:28px;padding:12px 24px">{BELL}SUBSCRIBE NOW</div>', out)


def corner_button(out):
    return render(f'<div class="abs" style="right:40px;bottom:140px;font-weight:700;font-size:24px;color:var(--mute);background:rgba(10,19,34,.8);padding:4px 12px">New hearings explained</div>'
                  f'<div class="sub" style="right:40px;bottom:60px;font-size:34px;padding:18px 30px">{BELL}SUBSCRIBE</div>', out)


def banner(out):
    return render(
        '<div class="abs" style="left:40px;top:790px;width:1840px;height:200px;background:var(--red);display:flex;align-items:center;padding:0 50px;gap:40px;'
        'clip-path:polygon(0 0,100% 0,calc(100% - 30px) 100%,0 100%)">'
        f'<div style="width:96px;height:96px">{BELL}</div>'
        '<div><div style="font-family:Arch;font-weight:900;font-size:74px;letter-spacing:2px;line-height:1">SUBSCRIBE NOW</div>'
        '<div style="font-weight:700;font-size:34px;margin-top:6px">Real courtroom hearings, explained. Tap the bell so you never miss one.</div></div></div>', out)


def hook_tag(out):
    return render('<div class="abs" style="left:40px;top:40px;background:var(--red);font-family:Arch;font-weight:900;font-size:30px;letter-spacing:5px;padding:10px 28px 10px 24px;'
                  'clip-path:polygon(0 0,100% 0,calc(100% - 18px) 100%,0 100%)">COMING UP</div>', out)


def hook_headline(text, out):
    n = len(text)
    fs = 72 if n <= 34 else 60 if n <= 48 else 50
    return render(f'<div class="lt"><div class="n" style="font-size:{fs}px;width:1250px;line-height:1.08;padding:14px 34px;white-space:normal">{esc(text)}</div></div>', out)


def overview(text, case_label, foot, out):
    w = len(text.split())
    fs = 58 if w <= 22 else 50 if w <= 32 else 44
    return render(
        '<div class="abs" style="left:140px;top:140px;width:1640px;background:var(--cream);color:#0E1A2B;padding:40px 60px 34px;border-top:12px solid var(--red)">'
        f'<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:Arch;font-weight:900;font-size:30px;letter-spacing:5px;color:var(--red)">THE OVERVIEW · {esc(case_label)}</span>'
        '<span class="brand" style="position:static;background:#0E1A2B;font-size:24px"><span class="seal" style="width:34px;height:34px;font-size:22px;border-width:2px">O</span>OVERRULED</span></div>'
        f'<div style="font-family:Serif;font-weight:700;font-size:{fs}px;line-height:1.25;margin-top:20px">{esc(text)}</div>'
        '<div style="display:flex;align-items:center;gap:26px;margin-top:30px;border-top:2px solid #cfc6b4;padding-top:24px">'
        f'<div class="sub" style="position:static;font-size:30px;padding:14px 26px">{BELL}SUBSCRIBE NOW</div>'
        f'<div style="font-weight:700;font-size:28px;color:#4a566b">{esc(foot)}</div></div></div>', out)


def docket(rows, question, options, out):
    """rows = [(case_label, name, outcome)]"""
    rws = "".join(
        f'<div style="display:flex;align-items:center;padding:20px 0;border-bottom:2px solid #2d4670"><div style="width:170px;background:var(--red);font-family:Arch;font-weight:900;font-size:26px;letter-spacing:4px;padding:8px 0;text-align:center">{esc(a)}</div>'
        f'<div style="flex:1;font-family:Arch;font-weight:800;font-size:50px;margin-left:30px">{esc(b)}</div><div style="font-weight:800;font-size:31px;color:var(--gold)">{esc(c)}</div></div>'
        for a, b, c in rows)
    opts = " &nbsp;&nbsp; ".join(f"{k} · {esc(v)}" for k, v in (options or {}).items())
    inner = (
        '<div class="abs" style="inset:0;background:linear-gradient(115deg,#0A1322 0%,#12233A 55%,#0E1A2B 100%)"></div>'
        '<div class="abs" style="left:110px;top:70px;width:1700px"><div style="display:flex;align-items:center;gap:22px"><span class="seal" style="width:76px;height:76px;font-size:50px">O</span>'
        '<div style="font-family:Arch;font-weight:900;font-size:88px;letter-spacing:2px">TODAY’S DOCKET</div></div>'
        '<div style="height:4px;background:linear-gradient(90deg,var(--gold),var(--red));margin:22px 0 10px"></div>' + rws +
        '<div style="display:flex;gap:36px;margin-top:36px"><div style="flex:1.25;background:var(--cream);color:#0E1A2B;padding:28px 38px;border-top:8px solid var(--red)">'
        '<div style="font-family:Arch;font-weight:900;font-size:26px;letter-spacing:4px;color:var(--red)">YOUR VERDICT</div>'
        f'<div style="font-family:Serif;font-weight:700;font-size:44px;line-height:1.18;margin-top:10px">{esc(question)}</div>'
        f'<div style="font-weight:700;font-size:26px;margin-top:12px;color:#4a566b">{opts or "Tell us in the comments."}</div></div>'
        f'<div style="flex:1;background:var(--red);padding:30px 38px;display:flex;flex-direction:column;justify-content:center;gap:12px;border-radius:6px">'
        f'<div style="display:flex;align-items:center;gap:18px"><div style="width:84px;height:84px">{BELL}</div>'
        '<div style="font-family:Arch;font-weight:900;font-size:68px;line-height:1">SUBSCRIBE<br>NOW</div></div>'
        '<div style="font-weight:700;font-size:28px">Watch the verdict. Tap the bell.</div></div></div></div>')
    return render(inner, out, transparent=False)


def sting_layers(out_dir):
    out_dir = Path(out_dir)
    panel = render('<div class="abs" style="left:-140px;top:0;width:520px;height:1080px;background:var(--red);transform:skewX(-12deg)"></div>'
                   '<div class="abs" style="left:330px;top:0;width:30px;height:1080px;background:var(--gold);transform:skewX(-12deg)"></div>', out_dir / "sting_panel")
    lock = render('<div class="abs" style="left:520px;top:300px"><div style="display:flex;align-items:center;gap:36px"><span class="seal" style="width:150px;height:150px;font-size:100px;border-width:5px">O</span>'
                  '<div style="font-family:Arch;font-weight:900;font-size:128px;letter-spacing:5px;line-height:1">OVERRULED</div></div>'
                  '<div style="height:4px;background:var(--gold);width:1000px;margin:26px 0 22px 186px"></div>'
                  '<div style="font-family:Serif;font-style:italic;font-weight:700;font-size:56px;color:var(--cream);margin-left:186px">Real courtrooms, explained.</div></div>', out_dir / "sting_lock")
    return panel, lock


def thumbnail(frame_png, text, gold_word, out):
    words = text.upper().split()
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(" ".join(cur)) >= 11:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    g = (gold_word or "").upper()
    body = "<br>".join(" ".join(f'<span style="background:var(--gold);color:#0E1A2B;padding:0 14px">{esc(w)}</span>' if w.strip(".,!?") == g else esc(w) for w in ln) for ln in lines)
    fs = 112 if len(lines) <= 3 else 92
    inner = (f'<img src="file://{Path(frame_png).resolve()}" style="position:absolute;left:0;top:0;width:1280px;height:720px;object-fit:cover">'
             '<div class="abs" style="inset:0;background:linear-gradient(90deg,rgba(10,19,34,.95) 0%,rgba(10,19,34,.6) 48%,rgba(10,19,34,0) 100%)"></div>'
             '<div class="abs" style="left:0;top:44px;background:var(--red);font-family:Arch;font-weight:900;font-size:34px;letter-spacing:5px;padding:10px 40px 10px 48px;clip-path:polygon(0 0,100% 0,calc(100% - 18px) 100%,0 100%)">COURT HEARING</div>'
             f'<div class="abs" style="left:48px;top:140px;width:900px;font-family:Arch;font-weight:900;font-size:{fs}px;line-height:1.0;text-shadow:0 5px 14px rgba(0,0,0,.6)">{body}</div>'
             '<div class="brand" style="left:48px;bottom:36px;background:none;border:none"><span class="seal">O</span>OVERRULED</div>')
    p = render(inner, out, size=(1280, 720), transparent=False)
    im = Image.open(p).convert("RGB")
    jp = Path(out).with_suffix(".jpg")
    im.save(jp, quality=93)
    return jp


# --------------------------------------------------------------------------------------- PIL: tile frames
def tile_frames(rects_small, rect_big, out):
    """Thin borders on the small tiles + gold corner brackets on the active (big) tile. rects are canvas coords."""
    out = Path(out)
    if out.exists():
        return out
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x, y, w, h in rects_small:
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(45, 70, 112, 255), width=2)
    if rect_big:
        x, y, w, h = rect_big
        g = (227, 180, 90, 255)
        L, T = 46, 5
        for cx, cy, sx, sy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            d.rectangle([min(cx, cx + sx * L), min(cy, cy + sy * T), max(cx, cx + sx * L) - (1 if sx > 0 else 0), max(cy, cy + sy * T) - (1 if sy > 0 else 0)], fill=g)
            d.rectangle([min(cx, cx + sx * T), min(cy, cy + sy * L), max(cx, cx + sx * T) - (1 if sx > 0 else 0), max(cy, cy + sy * L) - (1 if sy > 0 else 0)], fill=g)
    im.save(out)
    return out


def progress_bar(out):
    out = Path(out)
    if out.exists():
        return out
    w, h = 1920, 9
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for x in range(w):
        t = x / (w - 1)
        c = (int(227 + (209 - 227) * t), int(180 + (34 - 180) * t), int(90 + (47 - 90) * t), 255)
        for y in range(h):
            px[x, y] = c
    im.save(out)
    return out
