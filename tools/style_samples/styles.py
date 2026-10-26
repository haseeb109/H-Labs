"""The 8 Test Styles for the 60-second style samples.

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

LEGAL = ["probation", "report", "revoke", "custody", "assault", "sentence", "guilty", "recommendation"]

STYLES = {}

# --------------------------------------------------------------------------- 1. Confidential File
STYLES["test_style_1"] = dict(
    name="Test Style - 1", look="Confidential File",
    footage=dict(mode="band", x=0, y=250, w=1920, h=540, grade="eq=contrast=1.05:saturation=0.85"),
    captions=dict(mode="key", max_words=4),
    emph=["scared", "afraid", "revoke", "report"],
    css="""
:root{--paper:#D9C19A;--paper2:#E8D6B0;--ink:#1C1A17;--red:#B3261E;--blue:#2F4A6B}
.tw{font-family:'Special Elite',monospace}
.osw{font-family:'Oswald',sans-serif;font-weight:700}
.stamp{border:6px solid var(--red);color:var(--red);font-family:'Oswald';font-weight:700;letter-spacing:6px;padding:6px 26px;transform:rotate(-7deg);background:rgba(217,193,154,.25)}
.cap{left:50%;transform:translateX(-50%);top:850px;background:#F5EBDD;color:var(--ink);font-family:'Special Elite';font-size:56px;padding:8px 26px;box-shadow:6px 6px 0 rgba(0,0,0,.25);white-space:nowrap}
.cap em{font-style:normal;color:var(--red);text-decoration:underline}
""",
    bg="""<div class="a" style="inset:0;background:radial-gradient(circle at 20% 10%,#E6D2AA,#D3B98E 60%,#C7AB7E);"></div>
<div class="a" style="inset:0;background:repeating-linear-gradient(0deg,rgba(60,40,10,.035) 0 2px,transparent 2px 6px)"></div>
<div class="a" style="left:0;top:0;width:520px;height:70px;background:#C9AE80;clip-path:polygon(0 0,92% 0,100% 100%,0 100%)"></div>
<div class="a tw" style="right:60px;top:200px;font-size:26px;color:#5b4a2c">FILE No. 2020-CR-12086 · DEPT. 187</div>
<div class="a" style="left:0;right:0;top:236px;height:3px;background:#1C1A17;opacity:.6"></div>
<div class="a" style="left:0;right:0;top:803px;height:3px;background:#1C1A17;opacity:.6"></div>""",
    intro="""<div class="a" style="inset:0;background:#1C1A17"></div>
<div class="a tw" style="left:0;right:0;top:470px;text-align:center;color:#D9C19A;font-size:64px">[ CHANNEL INTRO ]</div>
<div class="a tw" style="left:0;right:0;top:560px;text-align:center;color:#8d7a58;font-size:30px">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a stamp" style="left:70px;top:95px;font-size:44px">CLASSIFIED · PREVIEW</div>',
        hook_head='<div class="a tw" style="left:640px;top:105px;width:1210px;font-size:38px;color:#1C1A17;background:#F5EBDD;padding:12px 24px;box-shadow:6px 6px 0 rgba(0,0,0,.25)">He skipped 26 months of check-ins. Today he tells the judge why.</div>',
        case_label='<div class="a osw" style="left:0;top:155px;background:#1C1A17;color:#F5EBDD;font-size:46px;letter-spacing:4px;padding:12px 40px 12px 70px;clip-path:polygon(0 0,95% 0,100% 100%,0 100%)">EXHIBIT A · FRANK CORONA</div>',
        counter='<div class="a tw" style="right:60px;top:95px;font-size:34px;color:#1C1A17">FILE 1 OF 4 &nbsp;<span style="color:#B3261E">■</span>□□□</div>',
        mid='''<div class="a" style="left:70px;top:845px;display:flex;gap:28px">
<div class="tw" style="background:#F5EBDD;padding:16px 24px;font-size:30px;color:#1C1A17;box-shadow:6px 6px 0 rgba(0,0,0,.25);border-left:10px solid #2F4A6B">EVIDENCE TAG<br><b style="font-size:38px">Probation violation</b><br>lawn mower theft case</div>
<div class="tw" style="background:#F5EBDD;padding:16px 24px;font-size:30px;color:#1C1A17;box-shadow:6px 6px 0 rgba(0,0,0,.25);border-left:10px solid #B3261E">FACING<br><b style="font-size:38px">Up to 2 years</b><br>state jail</div></div>''',
        mid2='<div class="a tw" style="right:70px;top:845px;background:#F5EBDD;padding:14px 22px;font-size:32px;color:#1C1A17;transform:rotate(2deg);box-shadow:6px 6px 0 rgba(0,0,0,.25)">MOTIVE: <span style="color:#B3261E">“I was scared.”</span></div>',
        sub='<div class="a stamp" style="right:80px;top:840px;font-size:50px;transform:rotate(-5deg)">▶ SUBSCRIBE</div><div class="a tw" style="right:90px;top:935px;font-size:26px;color:#1C1A17">open the next file</div>',
        ruling='<div class="a stamp" style="left:50%;top:380px;margin-left:-330px;font-size:120px;padding:10px 50px;background:rgba(245,235,221,.85)">REVOKED</div>',
        recap='''<div class="a" style="left:260px;top:170px;width:1400px;background:#F5EBDD;padding:46px 60px;box-shadow:12px 12px 0 rgba(0,0,0,.35);border-top:14px solid #1C1A17">
<div class="osw" style="font-size:30px;letter-spacing:6px;color:#B3261E">CASE SUMMARY · EXHIBIT A</div>
<div class="tw" style="font-size:44px;line-height:1.45;color:#1C1A17;margin-top:20px">At 17 he took a deal for stealing a lawn mower. Then he stopped reporting for 26 months. His reason: <span style="color:#B3261E">he was scared</span>. The State asked for 18 months.</div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(28,26,23,.88)"></div>
<div class="a stamp" style="left:120px;top:150px;font-size:80px;color:#E8D6B0;border-color:#E8D6B0;background:none">CASE CLOSED</div>
<div class="a" style="left:120px;top:400px;width:760px;height:428px;border:4px dashed #D9C19A;display:flex;align-items:center;justify-content:center" ><span class="tw" style="color:#D9C19A;font-size:40px">NEXT FILE ▶</span></div>
<div class="a" style="left:1010px;top:470px;background:#B3261E;color:#fff;font-family:Oswald;font-weight:700;font-size:64px;letter-spacing:5px;padding:24px 60px">SUBSCRIBE</div>
<div class="a tw" style="left:1010px;top:640px;color:#D9C19A;font-size:34px;width:780px">New case files every week.</div>'''),
)

# --------------------------------------------------------------------------- 2. Breaking News
STYLES["test_style_2"] = dict(
    name="Test Style - 2", look="Breaking News",
    footage=dict(mode="band", x=0, y=190, w=1920, h=540),
    captions=dict(mode="full", max_words=7),
    emph=[],
    css="""
:root{--navy:#0A2A6B;--navy2:#061A45;--red:#E10600;--steel:#9AA7B8}
.bc{font-family:'Barlow Condensed',sans-serif;font-weight:800;text-transform:uppercase}
.cap{left:50%;transform:translateX(-50%);top:640px;background:rgba(0,0,0,.82);color:#fff;font-family:'Roboto',sans-serif;font-weight:500;font-size:40px;padding:6px 18px;white-space:nowrap}
""",
    bg="""<div class="a" style="inset:0;background:linear-gradient(180deg,#0B2E74,#061A45)"></div>
<div class="a" style="inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.035) 0 1px,transparent 1px 80px),repeating-linear-gradient(0deg,rgba(255,255,255,.035) 0 1px,transparent 1px 80px)"></div>
<div class="a" style="left:0;right:0;top:1000px;height:80px;background:#fff"></div>
<div class="a bc" style="left:0;top:1000px;height:80px;width:300px;background:#E10600;color:#fff;font-size:44px;display:flex;align-items:center;justify-content:center;z-index:2">COURT UPDATE</div>""",
    intro="""<div class="a" style="inset:0;background:linear-gradient(180deg,#0B2E74,#061A45)"></div>
<div class="a bc" style="left:0;right:0;top:470px;text-align:center;color:#fff;font-size:80px">[ CHANNEL INTRO ]</div>
<div class="a" style="left:0;right:0;top:580px;text-align:center;color:#9AA7B8;font:500 30px Roboto">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a bc" style="left:60px;top:760px;background:#E10600;color:#fff;font-size:50px;padding:6px 26px">COMING UP</div>',
        hook_head='<div class="a" style="left:60px;top:830px;width:1800px;background:#fff;color:#0A2A6B;padding:10px 26px"><span class="bc" style="font-size:66px">Man who skipped probation for 2 years faces the judge</span></div>',
        case_label='''<div class="a" style="left:60px;top:760px;width:1500px">
<div class="bc" style="display:inline-block;background:#E10600;color:#fff;font-size:44px;padding:4px 22px">BREAKING</div>
<div style="background:#fff;color:#0A2A6B;padding:8px 22px"><span class="bc" style="font-size:62px">Frank Corona · Probation hearing</span></div>
<div class="bc" style="background:#0A2A6B;color:#fff;font-size:34px;padding:6px 22px;border:1px solid #9AA7B8">Cause 2020 CR12086 · Facing up to 2 years</div></div>''',
        ticker='<div class="a bc" style="left:330px;top:1000px;height:80px;display:flex;align-items:center;color:#0A2A6B;font-size:42px;white-space:nowrap">CASE 1 OF 4 &nbsp;●&nbsp; CHARGE: PROBATION VIOLATION &nbsp;●&nbsp; STATE ASKING 18 MONTHS &nbsp;●&nbsp; COMING UP: THE JUDGE RULES &nbsp;●&nbsp; <span style="color:#E10600">SUBSCRIBE FOR EVERY VERDICT</span> &nbsp;●&nbsp; CASE 1 OF 4 &nbsp;●&nbsp; STATE ASKING 18 MONTHS &nbsp;●&nbsp; COMING UP: THE JUDGE RULES</div>',
        counter='''<div class="a bc" style="left:0;top:1000px;height:80px;width:300px;background:#E10600;color:#fff;font-size:44px;display:flex;align-items:center;justify-content:center">COURT UPDATE</div>
<div class="a bc" style="right:60px;top:56px;display:flex;gap:0;font-size:40px"><span style="background:#E10600;color:#fff;padding:4px 18px">● LIVE</span><span style="background:#fff;color:#0A2A6B;padding:4px 18px">2:07 PM</span></div>''',
        mid='''<div class="a" style="right:60px;top:760px;width:420px;background:#061A45;border:2px solid #9AA7B8;padding:14px 22px">
<div class="bc" style="color:#E10600;font-size:34px;letter-spacing:2px">VERDICT WATCH</div>
<div class="bc" style="color:#fff;font-size:76px;line-height:1">0:24</div><div style="color:#9AA7B8;font:500 24px Roboto">until the ruling</div></div>''',
        mid2='''<div class="a" style="left:60px;top:760px;width:1100px;background:#fff;border-left:14px solid #E10600;padding:14px 26px">
<div class="bc" style="color:#E10600;font-size:30px">THE JUDGE</div>
<div style="color:#0A2A6B;font:700 46px Roboto">“There’s no need to be afraid of me.”</div></div>''',
        sub='<div class="a bc" style="right:60px;top:120px;background:#E10600;color:#fff;font-size:40px;padding:8px 24px;border:3px solid #fff">▶ SUBSCRIBE FOR VERDICTS</div>',
        ruling='''<div class="a" style="left:0;right:0;top:760px;background:#E10600;padding:10px 60px"><span class="bc" style="color:#fff;font-size:92px">BREAKING: PROBATION REVOKED</span></div>''',
        recap='''<div class="a" style="left:160px;top:180px;width:1600px;background:#061A45;border:2px solid #9AA7B8">
<div class="bc" style="background:#E10600;color:#fff;font-size:40px;padding:8px 30px">DEVELOPING · THE RECAP</div>
<div style="color:#fff;font:500 46px/1.4 Roboto;padding:30px 40px">Frank Corona missed 26 months of probation check-ins. He told the court he was scared. The State asked for 18 months. The judge revoked his probation.</div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(6,26,69,.92)"></div>
<div class="a bc" style="left:120px;top:120px;color:#fff;font-size:80px">NEXT BROADCAST</div>
<div class="a" style="left:120px;top:260px;width:900px;height:506px;border:4px solid #9AA7B8;display:flex;align-items:center;justify-content:center"><span class="bc" style="color:#9AA7B8;font-size:44px">NEXT VIDEO ▶</span></div>
<div class="a bc" style="left:1110px;top:420px;background:#E10600;color:#fff;font-size:72px;padding:20px 50px">SUBSCRIBE</div>
<div class="a" style="left:1110px;top:580px;color:#fff;font:500 34px Roboto;width:700px">New verdicts every week.</div>'''),
)

# --------------------------------------------------------------------------- 3. Viral / Gen-Z
STYLES["test_style_3"] = dict(
    name="Test Style - 3", look="Viral Gen-Z",
    footage=dict(mode="band", x=0, y=200, w=1920, h=600, grade="eq=contrast=1.12:saturation=1.2"),
    punch=0.78,
    captions=dict(mode="full", max_words=3, word_pop=True),
    emph=[],
    css="""
:root{--blk:#0B0B0B;--yel:#FFE600;--pink:#FF2E88;--cyan:#22D3EE}
.an{font-family:'Anton',sans-serif;text-transform:uppercase}
.stk{font-family:'Anton';text-transform:uppercase;border:6px solid #000;box-shadow:8px 8px 0 #000;padding:10px 30px}
.cap{left:50%;transform:translateX(-50%);top:840px;font-family:'Anton';font-size:110px;color:#fff;text-transform:uppercase;white-space:nowrap;-webkit-text-stroke:6px #000;paint-order:stroke fill;letter-spacing:1px}
.cap em{font-style:normal;color:var(--yel)}
""",
    bg="""<div class="a" style="inset:0;background:#0B0B0B"></div>
<div class="a" style="inset:0;background:radial-gradient(circle at 15% 15%,rgba(255,46,136,.35),transparent 35%),radial-gradient(circle at 85% 85%,rgba(34,211,238,.30),transparent 35%)"></div>
<div class="a" style="inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.04) 0 2px,transparent 2px 60px)"></div>""",
    intro="""<div class="a" style="inset:0;background:#FFE600"></div>
<div class="a an" style="left:0;right:0;top:420px;text-align:center;color:#0B0B0B;font-size:150px">[ INTRO ]</div>
<div class="a" style="left:0;right:0;top:620px;text-align:center;color:#0B0B0B;font:700 34px Archivo">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a stk" style="left:70px;top:60px;background:#FF2E88;color:#fff;font-size:64px;transform:rotate(-4deg)">WAIT FOR IT</div>',
        hook_head='<div class="a an" style="right:70px;top:60px;width:1100px;text-align:right;color:#FFE600;font-size:76px;line-height:1.05;-webkit-text-stroke:4px #000;paint-order:stroke fill">HE SKIPPED PROBATION FOR 2 YEARS</div>',
        case_label='<div class="a stk" style="left:250px;top:50px;background:#22D3EE;color:#0B0B0B;font-size:60px;transform:rotate(3deg)">CASE 1/4 · FRANK</div>',
        counter='<div class="a" style="left:0;right:0;top:0;height:14px;background:#222"><div style="width:35%;height:100%;background:linear-gradient(90deg,#FF2E88,#FFE600)"></div></div>',
        mid='''<div class="a stk" style="right:70px;top:50px;background:#FFE600;color:#0B0B0B;font-size:44px;line-height:1.15;transform:rotate(2deg)">GUESS THE SENTENCE<br><span style="font-size:36px">A) 6 MONTHS &nbsp; B) 18 MONTHS &nbsp; C) 2 YEARS</span></div>''',
        mid2='<div class="a stk" style="right:120px;top:70px;background:#FF2E88;color:#fff;font-size:90px;transform:rotate(-6deg)">NO WAY</div>',
        sub='<div class="a stk" style="right:70px;top:50px;background:#FF2E88;color:#fff;font-size:52px;border-radius:999px;transform:rotate(-3deg)">▶ SUBSCRIBE IF YOU GUESSED RIGHT</div>',
        ruling='<div class="a stk" style="left:50%;top:330px;margin-left:-420px;background:#FFE600;color:#0B0B0B;font-size:170px;transform:rotate(-5deg)">REVOKED</div>',
        recap='''<div class="a stk" style="left:200px;top:160px;width:1520px;background:#0B0B0B;color:#fff;border-color:#FFE600;box-shadow:12px 12px 0 #FF2E88;padding:40px 50px">
<div style="color:#FFE600;font-size:60px">QUICK RECAP</div>
<div style="font-family:Archivo;font-weight:900;text-transform:none;font-size:52px;line-height:1.3;margin-top:16px">Stole a lawn mower at 17. Skipped probation for 26 months. Said he was scared. <span style="color:#22D3EE">Judge: revoked.</span></div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(11,11,11,.9)"></div>
<div class="a an" style="left:120px;top:110px;color:#FFE600;font-size:110px">WATCH NEXT</div>
<div class="a" style="left:120px;top:280px;width:900px;height:506px;border:8px solid #22D3EE;display:flex;align-items:center;justify-content:center"><span class="an" style="color:#22D3EE;font-size:60px">NEXT VIDEO ▶</span></div>
<div class="a stk" style="left:1120px;top:430px;background:#FF2E88;color:#fff;font-size:90px;border-radius:999px">SUBSCRIBE</div>'''),
)

# --------------------------------------------------------------------------- 4. Cinematic Documentary
STYLES["test_style_4"] = dict(
    name="Test Style - 4", look="Cinematic Documentary",
    footage=dict(mode="cine", x=0, y=138, w=1920, h=804, grade="eq=contrast=1.08:saturation=0.75:gamma=0.95,vignette=PI/5"),
    captions=dict(mode="hook", max_words=6),
    emph=["scared", "afraid"],
    css="""
:root{--blk:#0A0A0A;--bone:#EDE6D6;--amber:#C8963E;--ash:#5A5A5A}
.cg{font-family:'Cormorant Garamond',serif}
.it{font-family:'Inter Tight',sans-serif}
.cap{left:50%;transform:translateX(-50%);top:968px;font-family:'Cormorant Garamond';font-style:italic;font-weight:500;font-size:54px;color:#EDE6D6;white-space:nowrap}
.cap em{color:var(--amber)}
""",
    bg="""<div class="a" style="inset:0;background:#0A0A0A"></div>""",
    intro="""<div class="a" style="inset:0;background:#0A0A0A"></div>
<div class="a cg" style="left:0;right:0;top:470px;text-align:center;color:#EDE6D6;font-size:80px;font-style:italic">[ channel intro ]</div>
<div class="a it" style="left:0;right:0;top:590px;text-align:center;color:#5A5A5A;font-size:26px;letter-spacing:8px">YOUR INTRO.MP4 PLAYS HERE</div>""",
    el=dict(
        hook_label='<div class="a it" style="left:80px;top:52px;color:#C8963E;font-size:26px;letter-spacing:10px;font-weight:600">A COURTROOM STORY</div>',
        hook_head='<div class="a" style="inset:0;background:radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,.55))"></div>',
        case_label='''<div class="a" style="inset:0;background:rgba(10,10,10,.55)"></div>
<div class="a it" style="left:0;right:0;top:430px;text-align:center;color:#C8963E;font-size:30px;letter-spacing:14px;font-weight:600">CHAPTER ONE</div>
<div class="a cg" style="left:0;right:0;top:480px;text-align:center;color:#EDE6D6;font-size:110px;font-weight:600">The Missing Years</div>''',
        counter='<div class="a it" style="right:80px;top:52px;color:#EDE6D6;font-size:24px;letter-spacing:8px;opacity:.8">CH. 1 / 4 &nbsp;·&nbsp; 2:07 PM</div>',
        mid='<div class="a cg" style="left:80px;top:962px;color:#EDE6D6;font-size:52px;font-style:italic">The State asks for eighteen months.</div>',
        mid2='<div class="a cg" style="right:80px;top:962px;color:#C8963E;font-size:52px;font-style:italic">“There’s no need to be afraid of me.”</div>',
        sub='<div class="a it" style="left:80px;top:964px;display:flex;align-items:center;gap:16px;color:#C8963E;font-size:28px;letter-spacing:8px;font-weight:600"><span style="border:2px solid #C8963E;padding:6px 18px">SUBSCRIBE</span><span style="color:#EDE6D6;letter-spacing:4px;font-weight:400">for the next story</span></div>',
        ruling='<div class="a cg" style="left:0;right:0;top:956px;text-align:center;color:#C8963E;font-size:60px;font-weight:600">“The court is going to revoke.”</div>',
        recap='''<div class="a it" style="left:0;right:0;top:300px;text-align:center;color:#C8963E;font-size:30px;letter-spacing:14px;font-weight:600">EPILOGUE</div>
<div class="a cg" style="left:300px;width:1320px;top:370px;text-align:center;color:#EDE6D6;font-size:58px;line-height:1.35;font-style:italic">He was seventeen when he made the deal. Two years of silence later, fear was his only answer. The judge revoked his probation.</div>''',
        end='''<div class="a" style="inset:0;background:#0A0A0A"></div>
<div class="a cg" style="left:140px;top:150px;color:#EDE6D6;font-size:84px;font-weight:600">The next story</div>
<div class="a" style="left:140px;top:300px;width:900px;height:506px;border:2px solid #5A5A5A;display:flex;align-items:center;justify-content:center"><span class="it" style="color:#5A5A5A;font-size:28px;letter-spacing:10px">NEXT VIDEO</span></div>
<div class="a it" style="left:1140px;top:480px;border:3px solid #C8963E;color:#C8963E;font-size:48px;letter-spacing:12px;font-weight:600;padding:22px 50px">SUBSCRIBE</div>'''),
)

# --------------------------------------------------------------------------- 5. Legal Explainer
STYLES["test_style_5"] = dict(
    name="Test Style - 5", look="Legal Explainer",
    footage=dict(mode="full", x=50, y=150, w=1280, h=720),
    captions=dict(mode="full", max_words=6),
    emph=LEGAL,
    css="""
:root{--board:#24352E;--chalk:#F4F1E8;--yel:#F2D16B;--coral:#E07A5F}
.k{font-family:'Kalam',cursive;font-weight:700}
.ss{font-family:'Source Sans 3',sans-serif}
.cap{left:690px;transform:translateX(-50%);top:905px;font-family:'Source Sans 3';font-weight:700;font-size:50px;color:#F4F1E8;white-space:nowrap}
.cap em{font-style:normal;color:#24352E;background:var(--yel);padding:0 8px;border-radius:4px}
""",
    bg="""<div class="a" style="inset:0;background:radial-gradient(circle at 30% 20%,#2F463B,#1C2A24 75%)"></div>
<div class="a" style="inset:0;background:radial-gradient(circle at 70% 60%,rgba(255,255,255,.05),transparent 30%),radial-gradient(circle at 20% 80%,rgba(255,255,255,.04),transparent 25%)"></div>
<div class="a" style="left:40px;top:140px;width:1300px;height:740px;border:4px dashed rgba(244,241,232,.7);border-radius:10px"></div>
<div class="a" style="left:1380px;top:150px;width:3px;height:720px;background:rgba(244,241,232,.25)"></div>""",
    intro="""<div class="a" style="inset:0;background:#24352E"></div>
<div class="a k" style="left:0;right:0;top:450px;text-align:center;color:#F4F1E8;font-size:90px">[ channel intro ]</div>
<div class="a k" style="left:0;right:0;top:580px;text-align:center;color:#F2D16B;font-size:36px">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a k" style="left:1420px;top:170px;color:#F2D16B;font-size:44px;width:460px">TODAY’S QUESTION</div>',
        hook_head='<div class="a k" style="left:1420px;top:240px;color:#F4F1E8;font-size:52px;line-height:1.2;width:460px">Can a judge send you to jail for missing probation meetings?</div>',
        case_label='<div class="a k" style="left:230px;top:40px;color:#F4F1E8;font-size:56px">Case 1 · <span style="color:#F2D16B">Probation Revocation Hearing</span></div>',
        counter='''<div class="a k" style="left:1420px;top:160px;width:470px;font-size:32px;color:rgba(244,241,232,.55);line-height:1.6;white-space:nowrap">
<div>① Arraignment ✓</div><div>② Plea deal ✓</div><div style="color:#F2D16B;font-size:38px">③ Revocation hearing ◀</div><div>④ Sentence ?</div></div>''',
        mid='''<div class="a" style="left:1410px;top:420px;width:420px;background:#F2D16B;color:#24352E;padding:20px 24px;border-radius:6px;transform:rotate(-1.5deg)">
<div class="k" style="font-size:30px">LEGAL TERM</div><div class="k" style="font-size:52px;line-height:1">Revocation</div>
<div class="ss" style="font-size:28px;font-weight:600;margin-top:8px">The judge cancels probation and the original punishment can come back.</div></div>''',
        mid2='''<div class="a" style="left:1410px;top:420px;width:420px;background:#E07A5F;color:#fff;padding:20px 24px;border-radius:6px;transform:rotate(1.5deg)">
<div class="k" style="font-size:30px">RULE BROKEN</div><div class="k" style="font-size:44px;line-height:1.1">Stopped reporting to probation</div>
<div class="ss" style="font-size:28px;font-weight:600;margin-top:8px">26 months with no check-in.</div></div>''',
        sub='<div class="a k" style="left:1410px;top:780px;width:470px;border:4px solid #F4F1E8;border-radius:10px;padding:12px 20px;color:#F4F1E8;font-size:40px;text-align:center">▶ <span style="color:#F2D16B">Subscribe</span> &amp; learn</div>',
        ruling='''<div class="a" style="left:1410px;top:420px;width:420px;background:#F4F1E8;color:#24352E;padding:20px 24px;border-radius:6px">
<div class="k" style="font-size:30px;color:#E07A5F">THE ANSWER</div><div class="k" style="font-size:52px;line-height:1.05">Yes. Probation revoked.</div></div>''',
        recap='''<div class="a" style="left:220px;top:160px;width:1480px;background:#24352E;border:6px dashed #F4F1E8;border-radius:16px;padding:40px 54px">
<div class="k" style="color:#F2D16B;font-size:56px">Today you learned</div>
<div class="ss" style="color:#F4F1E8;font-size:44px;font-weight:600;line-height:1.5;margin-top:10px">1. Missing probation check-ins is a violation.<br>2. The State can ask for jail time (here: 18 months).<br>3. The judge can <span style="color:#F2D16B">revoke</span> probation, even for a first offence.</div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(28,42,36,.94)"></div>
<div class="a k" style="left:120px;top:110px;color:#F4F1E8;font-size:90px">Next lesson</div>
<div class="a" style="left:120px;top:270px;width:900px;height:506px;border:5px dashed #F4F1E8;border-radius:12px;display:flex;align-items:center;justify-content:center"><span class="k" style="color:#F2D16B;font-size:50px">NEXT VIDEO ▶</span></div>
<div class="a k" style="left:1120px;top:440px;background:#F2D16B;color:#24352E;font-size:76px;padding:16px 50px;border-radius:12px">Subscribe</div>'''),
)

# --------------------------------------------------------------------------- 6. Human Story
STYLES["test_style_6"] = dict(
    name="Test Style - 6", look="Human Story",
    footage=dict(mode="band", x=80, y=250, w=1760, h=495, grade="eq=saturation=0.9:gamma=1.04,colorbalance=rs=.04:bs=-.03"),
    captions=dict(mode="key", max_words=5),
    emph=["scared", "afraid", "help", "revoke"],
    css="""
:root{--plum:#3B2440;--peach:#F6C9A8;--sage:#9DB49A;--cream:#FFF8F1;--rose:#C2577A}
.fr{font-family:'Fraunces',serif}
.nu{font-family:'Nunito',sans-serif}
.card{background:var(--cream);color:var(--plum);border-radius:18px;box-shadow:0 18px 40px rgba(0,0,0,.35)}
.cap{left:50%;transform:translateX(-50%);top:800px;font-family:'Fraunces';font-style:italic;font-weight:500;font-size:62px;color:#FFF8F1;white-space:nowrap;text-shadow:0 4px 18px rgba(0,0,0,.5)}
.cap em{color:var(--peach)}
""",
    bg="""<div class="a" style="inset:0;background:radial-gradient(circle at 50% 35%,#5A3762,#3B2440 70%,#2A1830)"></div>
<div class="a" style="left:120px;top:80px;width:260px;height:260px;border-radius:50%;background:rgba(246,201,168,.10);filter:blur(30px)"></div>
<div class="a" style="right:160px;bottom:60px;width:340px;height:340px;border-radius:50%;background:rgba(157,180,154,.12);filter:blur(40px)"></div>
<div class="a" style="left:76px;top:246px;width:1768px;height:503px;border-radius:22px;box-shadow:0 20px 60px rgba(0,0,0,.45)"></div>""",
    intro="""<div class="a" style="inset:0;background:radial-gradient(circle at 50% 40%,#5A3762,#3B2440 70%)"></div>
<div class="a fr" style="left:0;right:0;top:450px;text-align:center;color:#FFF8F1;font-size:84px;font-style:italic">[ channel intro ]</div>
<div class="a nu" style="left:0;right:0;top:580px;text-align:center;color:#F6C9A8;font-size:32px">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a nu" style="left:90px;top:100px;background:#9DB49A;color:#3B2440;font-size:30px;font-weight:800;letter-spacing:4px;padding:8px 22px;border-radius:999px">IN THEIR WORDS</div>',
        hook_head='<div class="a fr" style="left:90px;top:150px;color:#FFF8F1;font-size:64px;font-weight:700">He was 17. Now he has to explain two lost years.</div>',
        case_label='''<div class="a card" style="left:90px;top:790px;padding:18px 34px"><div class="fr" style="font-size:54px;font-weight:700">Frank Corona</div>
<div class="nu" style="font-size:30px;font-weight:700;color:#7a5a7f">Probation hearing · Story 1 of 4</div></div>''',
        counter='<div class="a nu" style="right:90px;top:110px;color:#F6C9A8;font-size:30px;font-weight:700;letter-spacing:3px">STORY 1 OF 4 &nbsp;● ○ ○ ○</div>',
        mid='''<div class="a card" style="left:90px;top:790px;padding:18px 34px;max-width:1300px"><div class="nu" style="font-size:28px;font-weight:800;letter-spacing:3px;color:#C2577A">WHAT HE IS FACING</div>
<div class="fr" style="font-size:48px;font-weight:700">Up to 2 years in state jail. The State asks for 18 months.</div></div>''',
        mid2='''<div class="a card" style="left:90px;top:140px;padding:12px 30px"><span class="fr" style="font-size:56px;font-style:italic">“I was scared.”</span><span class="nu" style="font-size:28px;font-weight:700;color:#7a5a7f"> &nbsp;— Frank Corona</span></div>''',
        sub='<div class="a nu" style="right:90px;top:90px;background:#C2577A;color:#fff;font-size:36px;font-weight:800;padding:14px 34px;border-radius:999px;box-shadow:0 10px 30px rgba(0,0,0,.35)">♡ Subscribe for more stories</div>',
        ruling='''<div class="a card" style="left:90px;top:140px;padding:12px 30px"><span class="nu" style="font-size:28px;font-weight:800;letter-spacing:3px;color:#C2577A">THE JUDGE’S DECISION &nbsp;</span><span class="fr" style="font-size:54px;font-weight:700">Probation revoked.</span></div>''',
        recap='''<div class="a card" style="left:260px;top:180px;width:1400px;padding:46px 60px">
<div class="nu" style="font-size:30px;font-weight:800;letter-spacing:4px;color:#C2577A">WHAT HAPPENS NEXT</div>
<div class="fr" style="font-size:50px;line-height:1.4;margin-top:16px">A teenager’s mistake became two years of hiding. Fear kept him away. Now the judge has revoked his probation, and he faces state jail.</div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(42,24,48,.92)"></div>
<div class="a fr" style="left:120px;top:120px;color:#FFF8F1;font-size:80px;font-weight:700">Another story</div>
<div class="a" style="left:120px;top:270px;width:900px;height:506px;border:3px solid #F6C9A8;border-radius:22px;display:flex;align-items:center;justify-content:center"><span class="nu" style="color:#F6C9A8;font-size:40px;font-weight:700">NEXT VIDEO ▶</span></div>
<div class="a nu" style="left:1120px;top:440px;background:#C2577A;color:#fff;font-size:64px;font-weight:800;padding:20px 54px;border-radius:999px">♡ Subscribe</div>'''),
)

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

# --------------------------------------------------------------------------- 8. Courtroom Sketch
STYLES["test_style_8"] = dict(
    name="Test Style - 8", look="Courtroom Sketch",
    footage=dict(mode="band", x=110, y=270, w=1700, h=478, grade="eq=saturation=0.55:contrast=1.05,colorbalance=rm=.06:gm=.03:bm=-.05"),
    captions=dict(mode="hook", max_words=5),
    emph=["scared", "afraid"],
    css="""
:root{--paper:#EFE8DA;--graphite:#3A3A3A;--wash:#5B7DB1;--sepia:#A0522D}
.gl{font-family:'Gloock',serif}
.ka{font-family:'Kalam',cursive;font-weight:700}
.wash{background:radial-gradient(ellipse at 30% 40%,rgba(91,125,177,.95),rgba(91,125,177,.75) 60%,rgba(91,125,177,.0) 75%);color:#fff}
.cap{left:50%;transform:translateX(-50%);top:800px;font-family:'Kalam';font-weight:700;font-size:62px;color:#3A3A3A;white-space:nowrap}
.cap em{font-style:normal;color:var(--wash)}
""",
    bg="""<div class="a" style="inset:0;background:#EFE8DA"></div>
<div class="a" style="inset:0;background:repeating-linear-gradient(35deg,rgba(58,58,58,.035) 0 2px,transparent 2px 9px)"></div>
<div class="a" style="left:0;top:0;width:700px;height:500px;background:radial-gradient(circle,rgba(91,125,177,.14),transparent 65%)"></div>
<div class="a" style="right:0;bottom:0;width:800px;height:500px;background:radial-gradient(circle,rgba(160,82,45,.12),transparent 65%)"></div>
<svg class="a" style="left:0;top:0" width="1920" height="1080"><g fill="none" stroke="#3A3A3A" stroke-linecap="round">
<path d="M98 262 L1824 258 L1822 760 L96 758 Z" stroke-width="4"/><path d="M104 268 L1817 266 L1815 752 L103 753 Z" stroke-width="2" opacity=".6"/>
<path d="M90 250 L140 300 M1830 250 L1780 300 M90 770 L140 720 M1830 770 L1780 720" stroke-width="2" opacity=".5"/></g></svg>""",
    intro="""<div class="a" style="inset:0;background:#EFE8DA"></div>
<div class="a gl" style="left:0;right:0;top:450px;text-align:center;color:#3A3A3A;font-size:84px">[ channel intro ]</div>
<div class="a ka" style="left:0;right:0;top:580px;text-align:center;color:#A0522D;font-size:36px">your intro.mp4 plays here</div>""",
    el=dict(
        hook_label='<div class="a ka" style="left:110px;top:110px;color:#A0522D;font-size:46px">Drawn in court ✎</div>',
        hook_head='<div class="a gl" style="left:110px;top:170px;color:#3A3A3A;font-size:62px">The quiet defendant who had to explain two years</div>',
        case_label='''<div class="a" style="left:110px;top:790px;width:900px;padding:20px 36px" ><div class="a" style="inset:0;background:radial-gradient(ellipse at 40% 50%,rgba(91,125,177,.9),rgba(91,125,177,.6) 55%,transparent 72%)"></div>
<div style="position:relative" class="ka"><div style="font-size:30px;color:#EFE8DA">THE DEFENDANT</div><div class="gl" style="font-size:64px;color:#fff">Frank Corona</div><div style="font-size:30px;color:#EFE8DA">Probation violation · Sketch 1 of 4</div></div></div>''',
        counter='<div class="a ka" style="right:110px;top:120px;color:#3A3A3A;font-size:38px">Sketch 1 of 4</div>',
        mid='''<div class="a ka" style="left:110px;top:800px;color:#3A3A3A;font-size:52px;transform:rotate(-1deg)">The State asks for <span style="color:#A0522D;border-bottom:4px solid #A0522D">18 months</span>.</div>''',
        mid2='''<div class="a ka" style="left:110px;top:800px;color:#5B7DB1;font-size:58px;transform:rotate(-1deg)">“Well, there’s no need to be afraid of me.” <span style="color:#3A3A3A;font-size:36px">— the judge</span></div>''',
        sub='''<div class="a ka" style="right:110px;top:100px;color:#3A3A3A;font-size:44px;padding:10px 34px;border:4px solid #3A3A3A;border-radius:40px 14px 36px 12px;transform:rotate(1.5deg);background:rgba(239,232,218,.8)">▶ Subscribe</div>''',
        ruling='''<div class="a" style="left:110px;top:790px;width:900px;padding:20px 36px"><div class="a" style="inset:0;background:radial-gradient(ellipse at 40% 50%,rgba(160,82,45,.92),rgba(160,82,45,.6) 55%,transparent 72%)"></div>
<div class="gl" style="position:relative;font-size:80px;color:#fff">Revoked.</div></div>''',
        recap='''<div class="a" style="left:260px;top:170px;width:1400px;background:#EFE8DA;border:4px solid #3A3A3A;border-radius:8px 30px 10px 24px;padding:40px 56px;box-shadow:10px 12px 0 rgba(58,58,58,.25)">
<div class="ka" style="font-size:44px;color:#A0522D">Sketch of the day</div>
<div class="gl" style="font-size:50px;line-height:1.4;color:#3A3A3A;margin-top:12px">A boy who took a deal at seventeen, a fear that kept him away for two years, and a judge who said the door was always open.</div></div>''',
        end='''<div class="a" style="inset:0;background:rgba(239,232,218,.95)"></div>
<div class="a gl" style="left:120px;top:110px;color:#3A3A3A;font-size:84px">The next sketch</div>
<div class="a" style="left:120px;top:270px;width:900px;height:506px;border:4px solid #3A3A3A;border-radius:10px 40px 14px 30px;display:flex;align-items:center;justify-content:center"><span class="ka" style="color:#5B7DB1;font-size:50px">next video ▶</span></div>
<div class="a ka" style="left:1120px;top:440px;color:#fff;background:#A0522D;font-size:72px;padding:14px 54px;border-radius:40px 14px 36px 12px">Subscribe</div>'''),
)
