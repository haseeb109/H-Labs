"""The approved Test Style 7 (Sports Scoreboard) for the 60-second style samples.

Each style is a dict:
  name, look         shown in the file name and the console
  footage            where the court footage sits: mode "band" (Zoom 2-up band, 32:9), "full" (whole 16:9 frame)
                     or "cine" (2.39:1 letterbox); x, y, w, h on the 1920x1080 canvas; optional ffmpeg "grade"
  punch              crop factor for a punch-in zoom on the ruling segment (1.0 = none)
  captions           mode "full" | "key" | "hook", word_pop (True = active word highlighted), max_words
  css                one CSS block for every element of this style
  bg / intro         full-screen HTML (opaque)
  el                 element name -> HTML (absolute positioned, transparent page). Missing element = not used.
  emph               words that get the highlight colour in captions

Text comes from the sample case (Frank Corona, Judge Boyd stream HKURkJmb-K8, 2:07:09-2:08:07).
No channel names anywhere: the logo slot shows the style's assets/logo.png, or a dotted LOGO box.
"""

CASE = {
    "name": "Frank Corona",
    "cause": "2020 CR12086",
    "charge": "Probation violation · lawn mower theft",
    "facing": "Up to 2 years state jail",
    "ask": "18 months",
}

STYLES = {}

# --------------------------------------------------------------------------- 7. Sports Scoreboard
STYLES["test_style_7"] = dict(
    name="Test Style - 7", look="Sports Scoreboard",
    footage=dict(mode="band", x=0, y=240, w=1920, h=540, grade="eq=contrast=1.1:saturation=1.05"),
    captions=dict(mode="key", max_words=4),
    emph=["scared", "afraid", "revoke", "report"],
    css="""
:root{--pit:#121417;--amber:#FFB000;--turf:#1F8A4C;--white:#F5F5F5}
.bs{font-family:'Big Shoulders Display',sans-serif;font-weight:800;text-transform:uppercase}
.mono{font-family:'DM Mono',monospace}
.cap{left:50%;transform:translateX(-50%);top:815px;font-family:'Big Shoulders Display';font-weight:800;font-size:84px;color:#F5F5F5;text-transform:uppercase;white-space:nowrap;letter-spacing:2px}
.cap em{font-style:normal;color:var(--amber)}
""",
    bg="""<div class="a" style="inset:0;background:linear-gradient(180deg,#1C2026,#0D0F12)"></div>
<div class="a" style="inset:0;background:conic-gradient(from 200deg at 10% -10%,transparent 0 20deg,rgba(255,255,255,.06) 25deg,transparent 32deg),conic-gradient(from 130deg at 90% -10%,transparent 0 20deg,rgba(255,255,255,.06) 25deg,transparent 32deg)"></div>
<div class="a" style="left:0;right:0;top:232px;height:8px;background:#1F8A4C"></div><div class="a" style="left:0;right:0;top:780px;height:8px;background:#1F8A4C"></div>""",
    intro="""<div class="a" style="inset:0;background:#121417"></div>
<div class="a bs" style="left:0;right:0;top:430px;text-align:center;color:#FFB000;font-size:130px">[ INTRO ]</div>
<div class="a mono" style="left:0;right:0;top:600px;text-align:center;color:#F5F5F5;font-size:30px">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a bs" style="left:0;right:0;top:40px;text-align:center;color:#FFB000;font-size:44px;letter-spacing:8px">TONIGHT’S MATCHUP</div>',
        hook_head='<div class="a bs" style="left:0;right:0;top:95px;text-align:center;color:#F5F5F5;font-size:110px;line-height:1">STATE <span style="color:#FFB000">vs</span> FRANK CORONA</div>',
        case_label='<div class="a bs" style="left:60px;top:820px;background:#FFB000;color:#121417;font-size:66px;padding:6px 30px">ROUND 1 · PROBATION HEARING</div>',
        counter='''<div class="a" style="left:50%;top:50px;margin-left:-520px;width:1040px;display:flex;background:#000;border:4px solid #333">
<div class="bs" style="flex:1;color:#F5F5F5;font-size:46px;padding:10px 20px">PROSECUTION <span style="color:#FFB000;font-family:'DM Mono';font-size:54px">1</span></div>
<div class="bs" style="background:#1F8A4C;color:#fff;font-size:40px;padding:14px 22px">RD 1</div>
<div class="bs" style="flex:1;text-align:right;color:#F5F5F5;font-size:46px;padding:10px 20px"><span style="color:#FFB000;font-family:'DM Mono';font-size:54px">0</span> DEFENSE</div></div>''',
        mid='''<div class="a" style="left:60px;top:820px;width:1100px;background:#000;border:3px solid #333;padding:14px 24px">
<div class="bs" style="color:#FFB000;font-size:40px;letter-spacing:4px">SENTENCE METER</div>
<div style="position:relative;height:40px;background:#222;margin-top:8px"><div style="width:75%;height:100%;background:linear-gradient(90deg,#1F8A4C,#FFB000)"></div></div>
<div class="mono" style="display:flex;justify-content:space-between;color:#F5F5F5;font-size:26px;margin-top:6px"><span>0</span><span style="color:#FFB000">STATE ASKS 18 MO</span><span>MAX 24 MO</span></div></div>''',
        mid2='<div class="a bs" style="right:60px;top:160px;background:#1F8A4C;color:#fff;font-size:44px;padding:10px 26px">PLAY OF THE GAME: “I WAS SCARED.”</div>',
        sub='<div class="a bs" style="right:60px;top:160px;background:#FFB000;color:#121417;font-size:44px;padding:10px 26px">▶ SUBSCRIBE · FINAL SCORE NEXT</div>',
        ruling='''<div class="a" style="left:50%;top:400px;margin-left:-600px;width:1200px;background:#000;border:8px solid #FFB000;text-align:center;padding:20px">
<div class="bs" style="color:#FFB000;font-size:50px;letter-spacing:10px">FINAL</div><div class="bs" style="color:#F5F5F5;font-size:120px;line-height:1">PROBATION REVOKED</div></div>''',
        recap='''<div class="a" style="left:240px;top:170px;width:1440px;background:#000;border:4px solid #FFB000;padding:36px 50px">
<div class="bs" style="color:#FFB000;font-size:56px;letter-spacing:6px">POST-GAME STATS</div>
<div class="mono" style="color:#F5F5F5;font-size:40px;line-height:1.7;margin-top:10px">MISSED CHECK-INS ...... 26 MONTHS<br>STATE ASKED ........... 18 MONTHS<br>MAX POSSIBLE .......... 24 MONTHS<br>RESULT ................ <span style="color:#FFB000">REVOKED</span></div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(13,15,18,.94)"></div>
<div class="a bs" style="left:120px;top:110px;color:#FFB000;font-size:100px">NEXT MATCH</div>
<div class="a" style="left:120px;top:270px;width:900px;height:506px;border:6px solid #1F8A4C;display:flex;align-items:center;justify-content:center"><span class="bs" style="color:#1F8A4C;font-size:56px">NEXT VIDEO ▶</span></div>
<div class="a bs" style="left:1120px;top:440px;background:#FFB000;color:#121417;font-size:84px;padding:14px 50px">SUBSCRIBE</div>'''),
)

