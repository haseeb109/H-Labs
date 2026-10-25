"""Cause cards, quiz panel, intro title card, thumbnail text (Pillow). Style = Rule 8:
gold #D4A017 labels, white values, one thin gold rule, no boxes/shadows/icons, left aligned, 10% margins."""
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

GOLD = (212, 160, 23, 255)
WHITE = (255, 255, 255, 255)
GREY = (170, 170, 170, 255)
W, H = 1920, 1080
MX = int(W * 0.10)
MY = int(H * 0.10)

_FONT_BOLD = ["assets/fonts/bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_FONT_REG = ["assets/fonts/regular.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
             "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
             "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
             "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
_cache = {}


def font(size, bold=True, override=None):
    key = (size, bold, override)
    if key in _cache:
        return _cache[key]
    for p in ([override] if override else []) + (_FONT_BOLD if bold else _FONT_REG):
        if p and os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _cache[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _cache[key] = f
    return f


def _tw(d, text, f):
    return d.textlength(text, font=f)


def _spaced(d, xy, text, f, fill, spacing=4):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += _tw(d, ch, f) + spacing
    return x


def _spaced_w(d, text, f, spacing=4):
    return sum(_tw(d, c, f) + spacing for c in text)


def _wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tw(d, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _canvas():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def intro_card(case, n, total, out):
    """CASE n OF total / NAME / Cause No / rule / CHARGE / FACING / THE QUESTION"""
    im, d = _canvas()
    f_tag, f_name, f_cause = font(34), font(92), font(32, bold=False)
    f_lab, f_val = font(30), font(40, bold=False)
    rows = [("CHARGE", case.get("charge", "")), ("FACING", case.get("facing", "")),
            ("THE QUESTION", case.get("question", ""))]
    label_w = 330
    val_w = int(W * 0.62) - label_w
    laid = []
    for lab, val in rows:
        lines = _wrap(d, val, f_val, val_w)
        laid.append((lab, lines))
    # name may wrap
    name_lines = _wrap(d, case.get("name", "").upper(), f_name, W - 2 * MX)
    h = 44 + len(name_lines) * 104 + 12
    if case.get("cause_no"):
        h += 46
    h += 22 + 8 + 30
    for _, lines in laid:
        h += len(lines) * 54 + 14
    y = (H - MY) - h
    y = max(int(H * 0.30), y)
    _spaced(d, (MX, y), f"CASE {n} OF {total}", f_tag, GOLD, 5)
    y += 50
    for ln in name_lines:
        d.text((MX, y), ln, font=f_name, fill=WHITE)
        y += 104
    y += 14
    d.rectangle([MX, y, MX + min(760, W - 2 * MX), y + 3], fill=GOLD)
    y += 16
    if case.get("cause_no"):
        d.text((MX, y), f"Cause No. {case['cause_no']}", font=f_cause, fill=GREY)
        y += 46
    y += 14
    for lab, lines in laid:
        _spaced(d, (MX, y + 8), lab, f_lab, GOLD, 3)
        for ln in lines:
            d.text((MX + label_w, y), ln, font=f_val, fill=WHITE)
            y += 54
        y += 14
    im.save(out)
    return out


def result_card(case, n, out):
    im, d = _canvas()
    f_tag, f_name = font(34), font(92)
    f_lab, f_val = font(30), font(40, bold=False)
    res = case.get("result") or {}
    rows = [("SENTENCE", res.get("sentence", "")), ("CONDITIONS", res.get("conditions", ""))]
    label_w = 330
    val_w = int(W * 0.62) - label_w
    laid = [(lab, _wrap(d, val, f_val, val_w)) for lab, val in rows]
    name_lines = _wrap(d, case.get("name", "").upper(), f_name, W - 2 * MX)
    h = 44 + len(name_lines) * 104 + 12 + 22 + 8 + 30
    for _, lines in laid:
        h += len(lines) * 54 + 14
    y = max(int(H * 0.30), (H - MY) - h)
    _spaced(d, (MX, y), f"CASE {n} \u2014 THE RULING", f_tag, GOLD, 5)
    y += 50
    for ln in name_lines:
        d.text((MX, y), ln, font=f_name, fill=WHITE)
        y += 104
    y += 14
    d.rectangle([MX, y, MX + min(760, W - 2 * MX), y + 3], fill=GOLD)
    y += 30
    for lab, lines in laid:
        _spaced(d, (MX, y + 8), lab, f_lab, GOLD, 3)
        for ln in lines:
            d.text((MX + label_w, y), ln, font=f_val, fill=WHITE)
            y += 54
        y += 14
    im.save(out)
    return out


def with_quiz(card_png, quiz, out):
    """Composite the quiz panel (upper right) over an existing card PNG."""
    base = Image.open(card_png).convert("RGBA")
    d = ImageDraw.Draw(base)
    f_tag, f_q, f_o = font(30), font(38), font(34, bold=False)
    pw = 700
    x = W - MX - pw
    y = MY
    _spaced(d, (x, y), "QUICK QUIZ", f_tag, GOLD, 5)
    y += 48
    for ln in _wrap(d, quiz.get("question", ""), f_q, pw):
        d.text((x, y), ln, font=f_q, fill=WHITE)
        y += 48
    d.rectangle([x, y + 4, x + 420, y + 7], fill=GOLD)
    y += 24
    for k in "ABC":
        t = (quiz.get("options") or {}).get(k, "")
        d.text((x, y), f"{k})", font=f_tag, fill=GOLD)
        for ln in _wrap(d, t, f_o, pw - 60):
            d.text((x + 60, y), ln, font=f_o, fill=WHITE)
            y += 44
        y += 12
    base.save(out)
    return out


def _rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    im = im.convert("RGBA")
    im.putalpha(mask)
    return im


def logo_badge(logo_path, size, out, opacity=1.0, radius_ratio=0.16):
    """Logo -> rounded RGBA PNG at `size` px wide (square logos keep their navy tile look)."""
    im = Image.open(logo_path).convert("RGBA")
    r = size / max(im.size)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    im = _rounded(im, int(min(im.size) * radius_ratio))
    if opacity < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * opacity))
        im.putalpha(a)
    im.save(out)
    return out


def logo_bg_colour(logo_path, default=(8, 8, 10)):
    try:
        im = Image.open(logo_path).convert("RGB")
        return im.getpixel((3, 3))
    except Exception:
        return default


def title_card(channel, out, sub="", logo_path=None):
    """Generated channel intro still: big logo centred (background = logo's own colour) + channel name."""
    bg = logo_bg_colour(logo_path) if logo_path else (8, 8, 10)
    im = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(im)
    f, f2 = font(96), font(40, bold=False)
    y = H // 2 - 60
    if logo_path and os.path.exists(str(logo_path)):
        lg = Image.open(logo_path).convert("RGBA")
        size = 640
        r = size / max(lg.size)
        lg = _rounded(lg.resize((int(lg.width * r), int(lg.height * r)), Image.LANCZOS), 30)
        im.alpha_composite(lg, ((W - lg.width) // 2, (H - lg.height) // 2 - 10))
        y = H
        lines = []        # the logo already carries the channel name
    else:
        lines = _wrap(d, channel.upper(), f, W - 2 * MX)
        y = H // 2 - len(lines) * 70
    for ln in lines:
        d.text(((W - _tw(d, ln, f)) / 2, y), ln, font=f, fill=WHITE)
        y += 140
    if not (logo_path and os.path.exists(str(logo_path))):
        d.rectangle([W // 2 - 220, y, W // 2 + 220, y + 4], fill=GOLD)
    if sub:
        d.text(((W - _tw(d, sub, f2)) / 2, y + 26), sub, font=f2, fill=GREY)
    im.convert("RGB").save(out)
    return out


def coming_up_tag(out):
    """Small gold 'COMING UP' label for the hook teaser (lower-left, inside the safe margin)."""
    im, d = _canvas()
    f = font(34)
    _spaced(d, (MX, H - MY - 40), "COMING UP", f, GOLD, 6)
    d.rectangle([MX, H - MY - 40 + 46, MX + 230, H - MY - 40 + 49], fill=GOLD)
    im.save(out)
    return out


def thumbnail(frame_path, text, gold_word, placement, out, size=(1280, 720)):
    im = Image.open(frame_path).convert("RGB")
    tw, th = size
    r = max(tw / im.width, th / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    left, top = (im.width - tw) // 2, (im.height - th) // 2
    im = im.crop((left, top, left + tw, top + th)).convert("RGBA")
    quoted = text.strip().startswith(('"', "\u201c"))
    txt = text.strip() if quoted else text.strip().upper()
    words = txt.split()
    gold = (gold_word or "").strip().strip('.,!?"\u201c\u201d').lower()
    d = ImageDraw.Draw(im)
    size_px = 150
    while size_px > 40:
        f = font(size_px)
        lines, cur = [], []
        for w in words:
            t = " ".join(cur + [w])
            if _tw(d, t, f) <= tw * 0.92 or not cur:
                cur.append(w)
            else:
                lines.append(cur)
                cur = [w]
        if cur:
            lines.append(cur)
        block_h = len(lines) * int(size_px * 1.12)
        if len(lines) <= 2 and block_h <= th * 0.32 and all(_tw(d, " ".join(l), f) <= tw * 0.92 for l in lines):
            break
        size_px -= 6
    f = font(size_px)
    lh = int(size_px * 1.12)
    block_h = len(lines) * lh
    y = 36 if placement == "top" else th - block_h - 44
    stroke = 10
    for line in lines:
        total = _tw(d, " ".join(line), f)
        x = (tw - total) / 2
        for i, w in enumerate(line):
            col = GOLD if w.strip('.,!?"\u201c\u201d').lower() == gold else WHITE
            d.text((x, y), w, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += _tw(d, w + " ", f)
        y += lh
    im.convert("RGB").save(out, quality=92)
    return out


def sharpness(path):
    """Variance of a Laplacian-ish filter - used to pick the least blurry candidate frame."""
    import numpy as np
    g = np.asarray(Image.open(path).convert("L").resize((480, 270)), dtype="float32")
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def contact_sheet(images, labels, out, cols=4, tw=480):
    th = int(tw * 9 / 16)
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    f = font(22, bold=False)
    for i, (p, lab) in enumerate(zip(images, labels)):
        r, c = divmod(i, cols)
        try:
            im = Image.open(p).convert("RGB").resize((tw, th))
            sheet.paste(im, (c * tw, r * (th + 34)))
        except Exception:
            pass
        d.text((c * tw + 8, r * (th + 34) + th + 5), lab[:48], font=f, fill=(230, 230, 230))
    sheet.save(out, quality=88)
    return out
