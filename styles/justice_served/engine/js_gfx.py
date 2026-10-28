"""JUSTICE SERVED graphics - "sports scoreboard" look (charcoal, amber, turf green). Every overlay is an HTML snippet
rendered to a transparent 1920x1080 PNG with Playwright/Chromium and cached by content hash (re-runs are free).
The channel logo (assets/logo_transparent.png) is the only brand mark: small, in the bottom-right corner."""
import atexit
import hashlib
import html as H
from pathlib import Path

from PIL import Image, ImageDraw

FONTS = Path(__file__).resolve().parent.parent / "hf" / "fonts"      # overridden by set_fonts()
LOGO = None

_CSS_T = """
@font-face{font-family:Bsd;font-weight:800;src:url(__F__/big-shoulders-display-latin-800-normal.woff2)}
@font-face{font-family:Bsd;font-weight:900;src:url(__F__/big-shoulders-display-latin-900-normal.woff2)}
@font-face{font-family:Mono;font-weight:500;src:url(__F__/dm-mono-latin-500-normal.woff2)}
@font-face{font-family:Inter;font-weight:600;src:url(__F__/inter-latin-600-normal.woff2)}
@font-face{font-family:Inter;font-weight:800;src:url(__F__/inter-latin-800-normal.woff2)}
:root{--pit:#121417;--pit2:#1C2026;--pit3:#262B33;--amber:#FFB000;--turf:#1F8A4C;--white:#F5F5F5;--mute:#9AA3AF;--line:#343A44}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:Inter,sans-serif;color:var(--white)}
.abs{position:absolute}
.bsd{font-family:Bsd,sans-serif;font-weight:900;text-transform:uppercase}
.mono{font-family:Mono,monospace;font-weight:500}
.amb{background:var(--amber);color:var(--pit)}
.lt{position:absolute;left:40px;top:786px;width:1280px}
.lt .k{display:inline-block;background:var(--amber);color:var(--pit);font-family:Bsd;font-weight:900;font-size:40px;letter-spacing:3px;text-transform:uppercase;padding:2px 30px 2px 22px;clip-path:polygon(0 0,100% 0,calc(100% - 18px) 100%,0 100%)}
.lt .n{background:#000;border-left:10px solid var(--amber);font-family:Bsd;font-weight:900;text-transform:uppercase;color:var(--white);padding:0 30px;line-height:1.08;width:1230px;white-space:nowrap;overflow:hidden}
.lt .s{background:var(--turf);font-family:Mono;font-weight:500;font-size:26px;padding:9px 30px;color:#fff;width:1130px;white-space:nowrap;overflow:hidden}
.panel{position:absolute;background:#000;border:3px solid var(--line);border-top:8px solid var(--amber);padding:18px 24px}
.panel h4{font-family:Bsd;font-weight:900;font-size:34px;letter-spacing:3px;color:var(--amber);text-transform:uppercase;margin-bottom:6px}
.panel dt{font-family:Mono;font-weight:500;font-size:19px;letter-spacing:2px;color:var(--amber);margin-top:14px;text-transform:uppercase}
.panel{overflow:hidden}
.panel dd{font-family:Bsd;font-weight:800;font-size:34px;line-height:1.08;text-transform:uppercase;margin-top:2px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.strip{position:absolute;left:40px;top:792px;width:1280px;background:#000;border:3px solid var(--line);border-left:12px solid var(--amber);padding:14px 28px 18px}
.strip .k{display:inline-block;background:var(--amber);color:var(--pit);font-family:Bsd;font-weight:900;font-size:28px;letter-spacing:3px;padding:1px 16px;text-transform:uppercase}
.strip .t{font-family:Inter;font-weight:800;font-size:44px;line-height:1.16;margin-top:8px}
.sub{position:absolute;display:inline-flex;align-items:center;gap:14px;background:var(--amber);color:var(--pit);font-family:Bsd;font-weight:900;text-transform:uppercase;letter-spacing:2px;border:4px solid #000;box-shadow:6px 6px 0 rgba(0,0,0,.55)}
.sub svg{width:1.05em;height:1.05em}
"""

BELL = ('<svg viewBox="0 0 24 24" fill="#121417"><path d="M12 2a2 2 0 0 0-2 2v.3C7.2 5.1 6 7.4 6 10v4l-2 3v1h16v-1l-2-3v-4c0-2.6-1.2-4.9-4-5.7V4a2 2 0 0 0-2-2zm0 20a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 12 22z"/></svg>')

_pw = {"p": None, "b": None}


def set_logo(path):
    global LOGO
    LOGO = Path(path).resolve() if path and Path(path).exists() else None


def set_fonts(d):
    global FONTS
    FONTS = Path(d)


def css():
    return _CSS_T.replace("__F__", Path(FONTS).resolve().as_uri())


def _browser():
    if _pw["b"] is None:
        from playwright.sync_api import sync_playwright
        _pw["p"] = sync_playwright().start()
        import os
        _pw["b"] = _pw["p"].chromium.launch(executable_path=os.environ.get("HL_CHROMIUM") or None)   # HL_CHROMIUM: optional Chromium binary
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
    out = Path(out)
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
        page.goto(hp.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(250)
        page.screenshot(path=str(p), omit_background=transparent)
    finally:
        page.close()
    return p


def esc(t):
    return H.escape(str(t or ""), quote=False)


def _emph(text):
    """*word* -> amber block (headline emphasis); stray asterisks removed."""
    out, parts = [], str(text or "").split("*")
    for i, seg in enumerate(parts):
        if not seg:
            continue
        out.append(f'<span style="background:var(--amber);color:var(--pit);padding:0 12px">{esc(seg)}</span>' if i % 2 else esc(seg))
    return "".join(out)


def _logo_tag(size, extra=""):
    if not LOGO:
        return ""
    return (f'<img src="{Path(LOGO).as_uri()}" style="position:absolute;right:30px;bottom:24px;height:{size}px;width:auto;object-fit:contain;'
            f'filter:drop-shadow(0 4px 10px rgba(0,0,0,.6));{extra}">')


# --------------------------------------------------------------------------------------- permanent elements
def background(out):
    inner = ('<div class="abs" style="inset:0;background:linear-gradient(180deg,#1C2026,#0D0F12)"></div>'
             '<div class="abs" style="inset:0;background:conic-gradient(from 200deg at 8% -10%,transparent 0 20deg,rgba(255,255,255,.05) 25deg,transparent 33deg),'
             'conic-gradient(from 128deg at 92% -10%,transparent 0 20deg,rgba(255,255,255,.05) 25deg,transparent 33deg)"></div>'
             '<div class="abs" style="left:0;right:0;bottom:0;height:9px;background:#262B33"></div>')
    return render(inner, out, transparent=False)


def brand(out):
    """The logo, small, bottom-right corner (shown on every case / recap / closing frame, never on the hook)."""
    return render(_logo_tag(104) or '<div class="abs bsd" style="right:34px;bottom:30px;font-size:34px;color:var(--amber)">JUSTICE SERVED</div>', out)


def ticker(label, text, out):
    return render('<div class="abs" style="left:40px;top:1006px;width:1280px;height:48px;display:flex;align-items:center;background:#000;border-left:8px solid var(--turf)">'
                  f'<span class="bsd" style="font-size:30px;letter-spacing:3px;color:var(--amber);padding:0 18px;white-space:nowrap">{esc(label)}</span>'
                  f'<span class="mono" style="font-size:23px;color:var(--white);white-space:nowrap;overflow:hidden">{esc(text)}</span></div>', out)


def lower_third(kicker, name, sub, out):
    """name = 'State v. X' - the 'v.' becomes an amber VS."""
    nm = esc(name.upper())
    for sep in (" V. ", " VS. ", " VS "):
        if sep in f" {nm} ":
            a, b = f" {nm} ".split(sep, 1)
            nm = f'{a.strip()} <span style="color:var(--amber)">VS</span> {b.strip()}'
            break
    n = len(name)
    fs = 96 if n <= 24 else 80 if n <= 32 else 64
    return render(f'<div class="lt"><span class="k">{esc(kicker)}</span><div class="n" style="font-size:{fs}px">{nm}</div>'
                  f'<div class="s">{esc(sub)}</div></div>', out)


def brief(case_label, rows, geom, out, title="THE MATCHUP"):
    x, y, w, h = geom
    dl = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in rows)
    return render(f'<div class="panel" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><h4>{esc(title)} · {esc(case_label)}</h4><dl>{dl}</dl></div>', out)


def quote_card(label, quote, who, geom, out):
    x, y, w, h = geom
    return render(f'<div class="panel" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><h4>{esc(label)}</h4>'
                  f'<div style="font-family:Inter;font-weight:800;font-size:44px;line-height:1.18;margin-top:22px">“{esc(quote)}”</div>'
                  f'<div class="mono" style="font-size:21px;letter-spacing:2px;color:var(--amber);margin-top:24px;text-transform:uppercase">{esc(who)}</div></div>', out)


def strip_card(kind, text, out):
    """In-case cards in the bottom band: fact | so_far | watch | verdict_q | take."""
    kick = {"fact": "KEY STAT", "so_far": "PLAY BY PLAY", "watch": "WATCH THIS", "verdict_q": "YOUR CALL", "take": "THE CALL", "coming_up": "COMING UP"}.get(kind, "KEY STAT")
    n = len(text.split())
    fs = 46 if n <= 14 else 40 if n <= 24 else 34
    body = esc(text)
    if kind == "fact":                       # a leading number is shown big
        import re
        m = re.match(r"^\s*([$]?[\d][\d,\.]*[%]?\+?(?:\s?(?:years?|months?|days?|times|minutes|statements?|counts?))?)\s*(.*)$", text, re.I)
        if m and m.group(2):
            body = (f'<span class="bsd" style="color:var(--amber);font-size:{fs + 34}px;vertical-align:-6px;margin-right:16px">{esc(m.group(1))}</span>{esc(m.group(2))}')
    return render(f'<div class="strip"><span class="k">{kick}</span><div class="t" style="font-size:{fs}px">{body}</div></div>', out)


def exchange(ts, who_q, q, who_a, a, out):
    return render(
        '<div class="abs" style="left:40px;top:792px;width:1840px;display:flex;background:#000;border:3px solid var(--line);border-left:12px solid var(--amber)">'
        f'<div style="padding:18px 26px;width:380px"><span class="bsd amb" style="font-size:28px;letter-spacing:3px;padding:1px 14px;white-space:nowrap">ON THE RECORD</span>'
        f'<div class="mono" style="color:var(--mute);font-size:22px;margin-top:12px">{esc(ts)}</div></div>'
        f'<div style="padding:16px 20px;flex:1"><div class="mono" style="font-size:20px;color:var(--amber);letter-spacing:2px;text-transform:uppercase">{esc(who_q)}</div>'
        f'<div style="font-family:Inter;font-weight:800;font-size:38px;line-height:1.16">{esc(q)}</div></div>'
        f'<div style="padding:16px 28px;flex:1;border-left:3px solid var(--line)"><div class="mono" style="font-size:20px;color:var(--amber);letter-spacing:2px;text-transform:uppercase">{esc(who_a)}</div>'
        f'<div style="font-family:Inter;font-weight:800;font-size:38px;line-height:1.16">{esc(a)}</div></div></div>', out)


# --------------------------------------------------------------------------------------- subscribe CTAs
def pill(out):
    return render(f'<div class="sub" style="left:1000px;top:58px;font-size:40px;padding:4px 24px">{BELL}SUBSCRIBE</div>', out)


def corner_button(out):
    return render('<div class="abs mono" style="right:40px;bottom:250px;font-size:22px;color:var(--white);background:#000;padding:4px 12px;border:2px solid var(--line)">New rounds every week</div>'
                  f'<div class="sub" style="right:40px;bottom:160px;font-size:50px;padding:6px 30px">{BELL}SUBSCRIBE</div>', out)


def banner(out):
    return render(
        '<div class="abs" style="left:40px;top:790px;width:1840px;height:160px;background:var(--amber);color:var(--pit);display:flex;align-items:center;padding:0 50px;gap:36px;border:4px solid #000;'
        'clip-path:polygon(0 0,100% 0,calc(100% - 30px) 100%,0 100%)">'
        f'<div style="width:86px;height:86px">{BELL}</div>'
        '<div><div class="bsd" style="font-size:84px;letter-spacing:2px;line-height:.95">SUBSCRIBE · FINAL SCORE NEXT</div>'
        '<div style="font-family:Inter;font-weight:800;font-size:30px;margin-top:6px">Real courtroom hearings, every round. Tap the bell.</div></div></div>', out)


# --------------------------------------------------------------------------------------- hook
def hook_tag(out):
    return render('<div class="abs bsd amb" style="left:40px;top:40px;font-size:44px;letter-spacing:5px;padding:2px 34px 2px 26px;'
                  'clip-path:polygon(0 0,100% 0,calc(100% - 20px) 100%,0 100%)">TODAY’S MATCHUP</div>', out)


def hook_headline(text, out):
    plain = str(text or "").replace("*", "")
    n = len(plain)
    fs = 104 if n <= 26 else 88 if n <= 40 else 70
    return render(f'<div class="lt"><div class="n" style="font-size:{fs}px;width:1250px;line-height:1.04;padding:8px 34px;white-space:normal;border-left:14px solid var(--amber)">{_emph(text)}</div></div>', out)


# --------------------------------------------------------------------------------------- recap + closing
def overview(text, case_label, foot, out):
    w = len(text.split())
    fs = 54 if w <= 22 else 46 if w <= 32 else 40
    return render(
        '<div class="abs" style="left:140px;top:140px;width:1640px;background:#000;border:4px solid var(--line);border-top:12px solid var(--amber);padding:36px 56px 32px">'
        f'<div class="bsd" style="font-size:44px;letter-spacing:5px;color:var(--amber)">POST-GAME REPORT · {esc(case_label)}</div>'
        f'<div style="font-family:Inter;font-weight:800;font-size:{fs}px;line-height:1.26;margin-top:18px">{esc(text)}</div>'
        '<div style="display:flex;align-items:center;gap:26px;margin-top:28px;border-top:3px solid var(--line);padding-top:22px">'
        f'<div class="sub" style="position:static;font-size:40px;padding:4px 24px">{BELL}SUBSCRIBE</div>'
        f'<div class="mono" style="font-size:26px;color:var(--mute)">{esc(foot)}</div></div></div>', out)


def docket(rows, question, options, out):
    """Closing board. rows = [(round_label, name, outcome)]"""
    rws = "".join(
        '<div style="display:flex;align-items:center;padding:16px 0;border-bottom:3px solid var(--line)">'
        f'<div class="bsd amb" style="width:210px;font-size:36px;letter-spacing:3px;padding:4px 0;text-align:center">{esc(a)}</div>'
        f'<div class="bsd" style="flex:1;font-size:60px;margin-left:30px">{esc(b)}</div>'
        f'<div class="mono" style="font-size:30px;color:var(--amber);text-align:right;max-width:620px">{esc(c)}</div></div>' for a, b, c in rows)
    opts = " &nbsp;&nbsp; ".join(f"{k} · {esc(v)}" for k, v in (options or {}).items())
    inner = (
        '<div class="abs" style="inset:0;background:linear-gradient(180deg,#1C2026,#0D0F12)"></div>'
        '<div class="abs" style="left:110px;top:60px;width:1700px">'
        '<div class="bsd" style="font-size:120px;letter-spacing:4px;line-height:1">FINAL SCORE</div>'
        '<div style="height:6px;background:linear-gradient(90deg,var(--amber),var(--turf));margin:18px 0 8px"></div>' + rws +
        '<div style="display:flex;gap:34px;margin-top:34px"><div style="flex:1.3;background:#000;border:3px solid var(--line);border-top:8px solid var(--amber);padding:26px 36px">'
        '<div class="bsd" style="font-size:40px;letter-spacing:4px;color:var(--amber)">YOUR CALL</div>'
        f'<div style="font-family:Inter;font-weight:800;font-size:44px;line-height:1.18;margin-top:8px">{esc(question)}</div>'
        f'<div class="mono" style="font-size:25px;margin-top:12px;color:var(--mute)">{opts or "Tell us in the comments."}</div></div>'
        '<div style="flex:1;background:var(--amber);color:var(--pit);padding:26px 36px;display:flex;flex-direction:column;justify-content:center;gap:10px;border:4px solid #000">'
        f'<div style="display:flex;align-items:center;gap:18px"><div style="width:84px;height:84px">{BELL}</div>'
        '<div class="bsd" style="font-size:84px;line-height:.92">SUBSCRIBE<br>NOW</div></div>'
        '<div style="font-family:Inter;font-weight:800;font-size:28px">Next round is coming. Tap the bell.</div></div></div></div>'
        + _logo_tag(104))
    return render(inner, out, transparent=False)


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
    body = "<br>".join(" ".join(f'<span style="background:var(--amber);color:var(--pit);padding:0 14px">{esc(w)}</span>' if w.strip(".,!?") == g else esc(w) for w in ln) for ln in lines)
    fs = 128 if len(lines) <= 3 else 104
    inner = (f'<img src="{Path(frame_png).resolve().as_uri()}" style="position:absolute;left:0;top:0;width:1280px;height:720px;object-fit:cover">'
             '<div class="abs" style="inset:0;background:linear-gradient(90deg,rgba(13,15,18,.96) 0%,rgba(13,15,18,.62) 50%,rgba(13,15,18,0) 100%)"></div>'
             '<div class="abs bsd amb" style="left:0;top:44px;font-size:44px;letter-spacing:5px;padding:2px 44px 2px 48px;clip-path:polygon(0 0,100% 0,calc(100% - 20px) 100%,0 100%)">COURT HEARING</div>'
             f'<div class="abs bsd" style="left:48px;top:130px;width:900px;font-size:{fs}px;line-height:.98;text-shadow:0 5px 14px rgba(0,0,0,.7)">{body}</div>'
             + (f'<img src="{Path(LOGO).as_uri()}" style="position:absolute;right:26px;bottom:22px;height:104px;object-fit:contain">' if LOGO else ""))
    p = render(inner, out, size=(1280, 720), transparent=False)
    jp = Path(out).with_suffix(".jpg")
    Image.open(p).convert("RGB").save(jp, quality=93)
    return jp


# --------------------------------------------------------------------------------------- PIL pieces
def tile_frames(rects_small, rect_big, out):
    """Thin frames on the small tiles + a turf-green frame with amber corner ticks on the active (big) tile."""
    out = Path(out)
    if out.exists():
        return out
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x, y, w, h in rects_small:
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(52, 58, 68, 255), width=2)
    if rect_big:
        x, y, w, h = rect_big
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(31, 138, 76, 255), width=4)
        a = (255, 176, 0, 255)
        for cx, cy, sx, sy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            d.rectangle([min(cx, cx + sx * 54), min(cy, cy + sy * 8), max(cx, cx + sx * 54) - (1 if sx > 0 else 0), max(cy, cy + sy * 8) - (1 if sy > 0 else 0)], fill=a)
            d.rectangle([min(cx, cx + sx * 8), min(cy, cy + sy * 54), max(cx, cx + sx * 8) - (1 if sx > 0 else 0), max(cy, cy + sy * 54) - (1 if sy > 0 else 0)], fill=a)
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
        c = (int(255 + (31 - 255) * t), int(176 + (138 - 176) * t), int(0 + (76 - 0) * t), 255)
        for y in range(h):
            px[x, y] = c
    im.save(out)
    return out
