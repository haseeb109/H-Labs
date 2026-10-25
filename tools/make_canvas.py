"""Generates the Trial Tales canvas assets with headless Chrome:
   styles/<style>/assets/logo_gold.png (transparent), bg_plain.png, bg_logo.png   (1920x1080).
Target style: HL_STYLE_DIR env var (absolute or ROOT-relative), default styles/trial_tales."""
import base64, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STYLE = Path(os.environ.get("HL_STYLE_DIR", "styles/trial_tales"))
STYLE = STYLE if STYLE.is_absolute() else ROOT / STYLE
OUT = STYLE / "assets"
OUT.mkdir(parents=True, exist_ok=True)
FONT = (STYLE / "hf/fonts/playfair-display-latin-900-normal.woff2").read_bytes()
F64 = base64.b64encode(FONT).decode()
GOLD = "#f4c430"

FLEUR = """
<g id="fl">
 <path d="M0,-50 C15,-30 15,-8 0,12 C-15,-8 -15,-30 0,-50Z"/>
 <path d="M4,4 C20,-24 48,-26 48,-2 C38,-12 26,-8 24,8 C24,18 16,24 4,24Z"/>
 <path d="M-4,4 C-20,-24 -48,-26 -48,-2 C-38,-12 -26,-8 -24,8 C-24,18 -16,24 -4,24Z"/>
 <rect x="-24" y="20" width="48" height="8" rx="3"/>
 <path d="M-5,28 C-5,42 -15,48 -24,56 C-9,51 0,55 0,66 C0,55 9,51 24,56 C15,48 5,42 5,28Z"/>
</g>"""

def pattern_svg():
    cells = []
    sx, sy = 118, 112
    for r in range(-1, 11):
        for c in range(-1, 18):
            x = c * sx + (sx / 2 if r % 2 else 0) + 20
            y = r * sy + 70
            cells.append(f'<use href="#fl" transform="translate({x},{y}) scale(0.85)"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" style="position:absolute;left:0;top:0"><defs>{FLEUR}</defs><g fill="#1b1b1b">{"".join(cells)}</g></svg>'

GAVEL = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="104" viewBox="0 0 140 104" style="position:absolute;left:0;top:0">
 <g fill="{GOLD}">
  <rect x="6" y="94" width="76" height="8" rx="2"/>
  <rect x="16" y="86" width="56" height="8" rx="2"/>
  <g transform="rotate(-32 70 40)">
   <rect x="22" y="22" width="64" height="30" rx="6"/>
   <rect x="50" y="50" width="12" height="62" rx="4" transform="rotate(0)"/>
  </g>
 </g>
 <g transform="rotate(-32 70 40)" fill="#121212"><rect x="35" y="22" width="4" height="30"/><rect x="69" y="22" width="4" height="30"/></g>
</svg>"""

LOGO_HTML = f"""<html><head><style>
@font-face{{font-family:PF;font-weight:900;src:url(data:font/woff2;base64,{F64}) format('woff2');}}
html,body{{margin:0;background:transparent}}
#w{{position:relative;width:370px;height:190px}}
#t{{position:absolute;left:0;top:96px;font:900 70px/1 PF;color:{GOLD};letter-spacing:-1px;white-space:nowrap}}
</style></head><body><div id="w"><div style="position:absolute;left:34px;top:0">{GAVEL}</div><div id="t">TrialTales</div></div></body></html>"""

def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 370, "height": 190}, device_scale_factor=2)
        pg.set_content(LOGO_HTML)
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / "logo_gold_2x.png"), omit_background=True)
        pg2 = b.new_page(viewport={"width": 1920, "height": 1080})
        pg2.set_content(f'<html><body style="margin:0;background:#121212;width:1920px;height:1080px;position:relative;overflow:hidden">{pattern_svg()}</body></html>')
        pg2.wait_for_timeout(300)
        pg2.screenshot(path=str(OUT / "bg_plain.png"))
        b.close()
    from PIL import Image
    custom = OUT / "logo_custom.png"            # drop your own transparent PNG here to replace the drawn logo
    logo = Image.open(custom if custom.exists() else OUT / "logo_gold_2x.png").convert("RGBA")
    if custom.exists():
        logo.thumbnail((370, 190), Image.LANCZOS)
        canvas = Image.new("RGBA", (370, 190), (0, 0, 0, 0))
        canvas.alpha_composite(logo, (0, 190 - logo.height))
        logo = canvas
    else:
        logo = logo.resize((370, 190), Image.LANCZOS)
    logo.save(OUT / "logo_gold.png")
    bg = Image.open(OUT / "bg_plain.png").convert("RGB").convert("RGBA")
    bg.alpha_composite(logo, (24, 270 - 190 - 4))
    bg.convert("RGB").save(OUT / "bg_logo.png")
    print("ok")
main()
