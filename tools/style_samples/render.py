"""Render 60-second style samples for the approved Test Style 7 (Sports Scoreboard), all on the same court clip.

    .venv/bin/python3 tools/style_samples/render.py                    # Test Style 7, downloads the clip with yt-dlp
    .venv/bin/python3 tools/style_samples/render.py --styles 7         # same, explicit
    .venv/bin/python3 tools/style_samples/render.py --source clip.mp4  # use a clip you already have

Clip: Judge Boyd stream HKURkJmb-K8, 2:07:05-2:08:10 (Frank Corona probation hearing). Captions come from
the NexLev transcript in tests/ (no Whisper needed). Output: output/style_samples/Test_Style_N.mp4

Every sample has the same 60 s timeline so the looks are easy to compare:
  0-12 hook (captions on in every mode) | 12-15 intro slot | 15-41 case, part 1 | 41-50 case, ruling
  50-56 recap (blurred footage + card)  | 56-60 end screen with subscribe box
Needs: ffmpeg, yt-dlp (only for the download), `pip install playwright pillow` + `playwright install chromium`.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from styles import STYLES  # noqa: E402

VIDEO_ID = "HKURkJmb-K8"
SRC0 = 7625            # stream second of the first frame of the clip (2:07:05)
SRC1 = 7690            # 2:08:10
FPS = 30
W, H = 1920, 1080

# (kind, stream start, stream end, timeline start)
SEGMENTS = [
    ("hook", 7647, 7651, 0.0),    # "You tell why you didn't report?" "I was scared."
    ("hook", 7662, 7670, 4.0),    # "Let me know if there's an issue. I'm here. But nobody can help anybody..."
    ("intro", None, None, 12.0),
    ("case", 7629, 7655, 15.0),   # new number one, assault, deceased, why didn't you report, scared
    ("ruling", 7672, 7681, 41.0), # probation, recommendation, "The court is going to revoke."
    ("recap", 7681, 7687, 50.0),
    ("end", None, None, 56.0),
]
SEG_LEN = {"intro": 3.0, "end": 4.0}
TOTAL = 60.0

# element -> (start, end, animation)
SCHEDULE = {
    "hook_label": (0.3, 12.0, "slide"),
    "hook_head": (0.6, 12.0, "fade"),
    "case_label": (15.3, 19.5, "slide"),
    "counter": (15.0, 50.0, "fade"),
    "ticker": (15.0, 50.0, "scroll"),
    "mid": (21.0, 28.5, "slide"),
    "sub": (30.0, 36.0, "drop"),        # first subscribe CTA (in a real video: after the first big moment, ~2-3 min)
    "mid2": (36.5, 42.0, "slide"),
    "ruling": (45.8, 50.0, "drop"),
    "recap": (50.3, 55.8, "fade"),
    "end": (56.0, 60.0, "fade"),
}
KEY_WINDOWS = [(0.0, 12.0), (33.0, 41.0), (44.0, 50.0)]   # "key moments" caption mode
HOOK_WINDOWS = [(0.0, 12.0)]

FONTS = ("https://fonts.googleapis.com/css2?family=Special+Elite&family=Oswald:wght@700&family=Barlow+Condensed:wght@800"
         "&family=Roboto:wght@500;700&family=Anton&family=Archivo:wght@700;900&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500"
         "&family=Inter+Tight:wght@400;600&family=Kalam:wght@700&family=Source+Sans+3:wght@600;700&family=Fraunces:ital,wght@0,700;1,500"
         "&family=Nunito:wght@700;800&family=Big+Shoulders+Display:wght@800&family=DM+Mono&family=Gloock&display=block")


def run(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(" ".join(map(str, cmd))[:600])
        print(r.stderr[-3000:])
        raise SystemExit("ffmpeg failed")
    return r


# ----------------------------------------------------------------------------------------------- source clip
def get_source(args, cache: Path) -> Path:
    if args.source:
        return Path(args.source)
    clip = cache / f"{VIDEO_ID}_{SRC0}_{SRC1}.mp4"
    if clip.exists():
        return clip
    ytdlp = shutil.which("yt-dlp") or str(ROOT / ".venv/bin/yt-dlp")
    print("downloading the sample clip (65 s) with yt-dlp ...")
    cmd = [ytdlp, "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]", "--merge-output-format", "mp4",
           "--download-sections", f"*{SRC0}-{SRC1}", "--force-keyframes-at-cuts", "-o", str(clip),
           f"https://www.youtube.com/watch?v={VIDEO_ID}"]
    if (ROOT / "cookies.txt").exists():
        cmd[1:1] = ["--cookies", str(ROOT / "cookies.txt")]
    r = subprocess.run(cmd)
    if r.returncode != 0 or not clip.exists():
        raise SystemExit("download failed - pass a local clip with --source (stream 2:07:05-2:08:10)")
    return clip


# ----------------------------------------------------------------------------------------------- captions
def load_words(path: Path):
    """NexLev transcript lines -> [(stream_sec, word)], words spread evenly inside each line."""
    lines = json.load(open(path))["transcript"]
    out = []
    for i, ln in enumerate(lines):
        a = int(ln["startMs"]) / 1000
        if a < SRC0 - 5 or a > SRC1 + 5:
            continue
        b = int(lines[i + 1]["startMs"]) / 1000 if i + 1 < len(lines) else int(ln["endMs"]) / 1000
        b = min(b, int(ln["endMs"]) / 1000)
        words = re.sub(r">>", "", ln["text"]).split()
        if not words:
            continue
        step = max(0.12, (b - a) / len(words))
        for k, w in enumerate(words):
            out.append((a + k * step, w))
    return out


def caption_chunks(words, max_words):
    """Map words onto the timeline and group them. -> [(start, end, [words])]"""
    placed = []
    for kind, s0, s1, t0 in SEGMENTS:
        if kind not in ("hook", "case", "ruling"):
            continue
        for ts, w in words:
            if s0 <= ts < s1 - 0.15:
                placed.append((t0 + ts - s0, w))
    placed.sort()
    chunks, cur = [], []
    for i, (t, w) in enumerate(placed):
        if cur and (len(cur) >= max_words or t - cur[-1][0] > 0.8 or seg_of(t) != seg_of(cur[0][0])):
            chunks.append(cur)
            cur = []
        cur.append((t, w))
        if re.search(r"[.?!]$", w):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    res = []
    for i, c in enumerate(chunks):
        start = c[0][0]
        nxt = chunks[i + 1][0][0] if i + 1 < len(chunks) else start + 2
        end = min(nxt, c[-1][0] + 0.9, seg_end(start))
        res.append((start, max(end, start + 0.35), c))
    return res


def seg_of(t):
    for i, (kind, s0, s1, t0) in enumerate(SEGMENTS):
        if t0 <= t < seg_start_next(i):
            return i
    return -1


def seg_start_next(i):
    return SEGMENTS[i + 1][3] if i + 1 < len(SEGMENTS) else TOTAL


def seg_end(t):
    return seg_start_next(seg_of(t))


def in_windows(t, wins):
    return any(a <= t < b for a, b in wins)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cap_html(words, emph, active=None):
    out = []
    for i, w in enumerate(words):
        bare = re.sub(r"[^a-z']", "", w.lower())
        hot = (i == active) if active is not None else any(bare.startswith(e) for e in emph)
        out.append(f"<em>{esc(w)}</em>" if hot else esc(w))
    return " ".join(out)


# ----------------------------------------------------------------------------------------------- HTML -> PNG
class Painter:
    def __init__(self, chromium=None):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        kw = {"executable_path": chromium} if chromium else {}
        self.browser = self.pw.chromium.launch(**kw)
        self.page = self.browser.new_page(viewport={"width": W, "height": H})

    def png(self, css, body, out: Path, opaque=False, crop=True, width=W):
        """width > 1920 is for the news ticker, which scrolls in from beyond the right edge."""
        self.page.set_viewport_size({"width": width, "height": H})
        html = (f'<html><head><link rel="stylesheet" href="{FONTS}"><style>html,body{{margin:0;width:{width}px;height:{H}px;'
                f'background:transparent;overflow:hidden}}.a{{position:absolute}}{css}</style></head><body>{body}</body></html>')
        self.page.set_content(html, wait_until="networkidle")
        self.page.evaluate("document.fonts.ready")
        self.page.screenshot(path=str(out), omit_background=not opaque)
        if not crop:
            return 0, 0
        from PIL import Image
        im = Image.open(out)
        if im.mode != "RGBA":          # fully opaque element: keep the whole frame
            return 0, 0
        box = im.getchannel("A").getbbox()
        if not box:
            return None
        x0, y0 = max(0, box[0] - 2) & ~1, max(0, box[1] - 2) & ~1
        x1, y1 = min(im.width, box[2] + 2), min(H, box[3] + 2)
        x1 -= (x1 - x0) % 2
        y1 -= (y1 - y0) % 2
        im.crop((x0, y0, x1, y1)).save(out)
        return x0, y0

    def close(self):
        self.browser.close()
        self.pw.stop()


def logo_html(style_dir: Path, color):
    logo = style_dir / "assets" / "logo.png"
    if logo.exists():           # inline as data URI: the page cannot load file:// images
        import base64
        b64 = base64.b64encode(logo.read_bytes()).decode()
        return f'<img class="a" src="data:image/png;base64,{b64}" style="left:60px;top:40px;height:110px">'
    return (f'<div class="a" style="left:60px;top:40px;border:3px dashed {color};color:{color};font:700 28px Archivo,sans-serif;'
            f'letter-spacing:6px;padding:16px 26px;opacity:.85">LOGO</div>')


# ----------------------------------------------------------------------------------------------- video
def footage_filter(fg, punch=1.0):
    mode = fg["mode"]
    if mode == "band":        # middle 32:9 band of a 16:9 Zoom frame (2-up grid)
        crop = "crop=iw:ih/2:0:ih/4"
    elif mode == "cine":
        crop = "crop=iw:iw/2.39:0:(ih-iw/2.39)/2"
    else:
        crop = "null"
    f = f"{crop},scale={fg['w']}:{fg['h']}"
    if punch != 1.0:
        f = (f"{crop},crop=iw*{punch}:ih*{punch}:(iw-iw*{punch})/2:(ih-ih*{punch})/2,"
             f"scale={fg['w']}:{fg['h']}")
    if fg.get("grade"):
        f += "," + fg["grade"]
    return f + ",setsar=1,fps=30"


def render_segment(i, seg, style, src, bg, intro, work):
    kind, s0, s1, t0 = seg
    dur = (seg_start_next(i) - t0)
    out = work / f"seg{i}.mp4"
    fg = style["footage"]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out)]
    silent = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    if kind in ("intro", "end"):
        img = intro if kind == "intro" else bg
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(img), *silent,
             "-filter_complex", "[0:v]format=yuv420p[v]", "-map", "[v]", "-map", "1:a", *enc])
        return out
    ss = s0 - SRC0
    if kind == "recap":
        vf = (f"[1:v]crop=iw:ih/2:0:ih/4,scale=-2:{H},crop={W}:{H},gblur=sigma=28,"
              f"eq=brightness=-0.18:saturation=0.6,setsar=1,fps=30[f];[0:v][f]overlay=0:0[v];[1:a]volume=0.25[a]")
    else:
        punch = style.get("punch", 1.0) if kind == "ruling" else 1.0
        vf = (f"[1:v]{footage_filter(fg, punch)}[f];[0:v][f]overlay={fg['x']}:{fg['y']}:shortest=1[v];"
              f"[1:a]volume=1.0[a]")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(bg),
         "-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-filter_complex", vf, "-map", "[v]", "-map", "[a]", *enc])
    return out


def anim_xy(kind, x, y, s):
    if kind == "scroll":           # news ticker: moves left 75 px per second
        return f"{x}-75*(t-{s})", str(y)
    if kind == "slide":
        return f"if(lt(t\\,{s}+0.35)\\,{x - 80}+80*(t-{s})/0.35\\,{x})", str(y)
    if kind == "drop":
        return str(x), f"if(lt(t\\,{s}+0.25)\\,{y - 50}+50*(t-{s})/0.25\\,{y})"
    return str(x), str(y)


def render_style(sid, style, src, words, painter, outdir: Path, keep=False):
    style_dir = ROOT / "styles" / sid
    work = Path(tempfile.mkdtemp(prefix=f"{sid}_"))
    css = style["css"]
    print(f"\n== {style['name']} ({style['look']})")

    bg = work / "bg.png"
    painter.png(css, style["bg"], bg, opaque=True, crop=False)
    intro_mp4 = style_dir / "assets" / "channel_intro.mp4"
    intro = work / "intro.png"
    painter.png(css, style["intro"], intro, opaque=True, crop=False)

    # elements
    layers = []   # (png, x, y, start, end, anim)
    bugc = re.search(r"--(?:ink|steel|chalk|bone|peach|amber|graphite|yel)[^:]*:(#[0-9A-Fa-f]{6})", css)
    logo = logo_html(style_dir, bugc.group(1) if bugc else "#ffffff")
    p = work / "logo.png"
    xy = painter.png(css, logo, p)
    if xy:
        layers.append((p, *xy, 15.0, 50.0, "fade"))
    for name, html in style["el"].items():
        s, e, anim = SCHEDULE[name]
        p = work / f"el_{name}.png"
        xy = painter.png(css, html, p, width=8000 if name == "ticker" else W)
        if xy:
            layers.append((p, *xy, s, e, anim))

    # captions
    cfg = style["captions"]
    wins = {"full": [(0, 50)], "key": KEY_WINDOWS, "hook": HOOK_WINDOWS}[cfg["mode"]]
    busy = [(SCHEDULE[k][0], SCHEDULE[k][1]) for k in ("case_label", "mid", "mid2", "ruling")
            if k in style["el"] and cfg["mode"] != "full"]
    n = 0
    for (a, b, chunk) in caption_chunks(words, cfg["max_words"]):
        if not in_windows(a, wins):
            continue
        ws = [w for _, w in chunk]
        if cfg.get("word_pop"):
            for k, (tw, _) in enumerate(chunk):
                ta = tw if k else a
                tb = chunk[k + 1][0] if k + 1 < len(chunk) else b
                p = work / f"cap{n}.png"
                xy = painter.png(css, f'<div class="a cap">{cap_html(ws, [], k)}</div>', p)
                if xy:
                    layers.append((p, *xy, ta, tb, "cut"))
                n += 1
        else:
            if any(x <= a < y for x, y in busy) and not in_windows(a, HOOK_WINDOWS):
                continue
            p = work / f"cap{n}.png"
            xy = painter.png(css, f'<div class="a cap">{cap_html(ws, style.get("emph", []))}</div>', p)
            if xy:
                layers.append((p, *xy, a, b, "cut"))
            n += 1
    print(f"  {len(layers)} layers ({n} caption cards, mode {cfg['mode']})")

    # base timeline
    segs = []
    for i, seg in enumerate(SEGMENTS):
        if seg[0] == "intro" and intro_mp4.exists():
            out = work / f"seg{i}.mp4"
            run(["ffmpeg", "-y", "-i", str(intro_mp4), "-t", "3", "-vf", f"scale={W}:{H},setsar=1,fps=30", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)])
            segs.append(out)
            continue
        segs.append(render_segment(i, seg, style, src, bg, intro, work))
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])

    # overlays, in batches so the filter graph stays small
    cur = base
    for bi in range(0, len(layers), 40):
        batch = layers[bi:bi + 40]
        ins, fc, last = ["-i", str(cur)], [], "0:v"
        for k, (png, x, y, s, e, anim) in enumerate(batch, start=1):
            d = max(0.1, e - s)
            ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(png)]
            fade = "" if anim == "cut" else (f",fade=in:st=0:d=0.25:alpha=1,fade=out:st={max(0, d - 0.25):.3f}:d=0.25:alpha=1")
            fc.append(f"[{k}:v]format=rgba{fade},setpts=PTS-STARTPTS+{s:.3f}/TB[l{k}]")
            ox, oy = anim_xy(anim, x, y, s)
            fc.append(f"[{last}][l{k}]overlay=x='{ox}':y='{oy}':eof_action=pass[o{k}]")
            last = f"o{k}"
        nxt = work / f"ov{bi}.mp4"
        run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "0:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", str(nxt)])
        cur = nxt
    final = outdir / f"{style['name'].replace(' - ', '_').replace(' ', '_')}_{style['look'].replace(' ', '_')}.mp4"
    shutil.copy(cur, final)
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    print(f"  -> {final}")
    return final


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--styles", nargs="*", help="style numbers (7) or ids (default: all)")
    ap.add_argument("--source", help="local clip of stream HKURkJmb-K8 starting at 2:07:05 (else yt-dlp download)")
    ap.add_argument("--transcript", default=str(ROOT / "tests/sample_boyd_2026-10-19_nexlev.json"))
    ap.add_argument("--out", default=str(ROOT / "output/style_samples"))
    ap.add_argument("--chromium", default=os.environ.get("HL_CHROMIUM"), help="Chromium binary (optional)")
    ap.add_argument("--keep", action="store_true", help="keep the work folders")
    args = ap.parse_args()

    ids = list(STYLES)
    if args.styles:
        ids = [s if s in STYLES else f"test_style_{s}" for s in args.styles]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    src = get_source(args, outdir)
    words = load_words(Path(args.transcript))
    painter = Painter(args.chromium)
    try:
        for sid in ids:
            render_style(sid, STYLES[sid], src, words, painter, outdir, args.keep)
    finally:
        painter.close()
    print(f"\ndone: {outdir}")


if __name__ == "__main__":
    main()
