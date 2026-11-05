from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Coder_Buddy_Final_Presentation.pptx"
P = Presentation()
P.slide_width = Inches(13.333)
P.slide_height = Inches(7.5)
BLANK = P.slide_layouts[6]
C = {
    "navy": "111C30", "navy2": "1C2C47", "ink": "19263B", "muted": "68768C",
    "paper": "FAF6F8", "white": "FFFFFF", "purple": "AD4873", "pale": "F8EAF0", "green": "198A63",
    "mint": "65D6B2", "mintp": "E8F8F1", "amber": "D99838", "amberp": "FFF4E3",
    "blue": "4380D8", "bluep": "EAF2FF", "line": "E4E8EF", "red": "C6524C",
}

def rgb(hex_value):
    return RGBColor.from_string(C.get(hex_value, hex_value))

def bg(slide, color="paper"):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(color)

def text(slide, value, x, y, w, h, size=16, color="ink", bold=False, font="Aptos", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear(); tf.word_wrap = True
    tf.margin_left = Inches(margin); tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin); tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]; p.alignment = align
    p.text = value
    p.font.name = font; p.font.size = Pt(size); p.font.bold = bold; p.font.color.rgb = rgb(color)
    return shape

def box(slide, x, y, w, h, fill="white", line="line", radius=True):
    typ = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(typ, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    sh.line.color.rgb = rgb(line)
    if radius:
        sh.adjustments[0] = 0.12
    return sh

def line(slide, x1, y1, x2, y2, color="line", width=1.5, end=None):
    sh = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    sh.line.color.rgb = rgb(color); sh.line.width = Pt(width)
    if end is not None:
        sh.line.end_arrowhead = end
    return sh

def header(slide, section, title, sub=None, dark=False):
    text(slide, section.upper(), .62, .38, 6, .25, 9, "mint" if dark else "purple", True, "Aptos Mono")
    text(slide, title, .62, .76, 12, .62, 29, "white" if dark else "navy", True)
    if sub:
        text(slide, sub, .64, 1.48, 11.9, .42, 12, "D4DBE7" if dark else "muted")

def footer(slide, number, dark=False):
    col = "8996AA" if dark else "8B95A5"
    line(slide, .62, 7.08, 12.72, 7.08, "navy2" if dark else "line", 1)
    text(slide, "CODER BUDDY  ·  FINAL CAPSTONE REVIEW", .64, 7.16, 5, .18, 8, col, True, "Aptos Mono")
    text(slide, f"{number:02d} / 12", 11.7, 7.16, 1, .18, 8, col, False, "Aptos Mono", PP_ALIGN.RIGHT)

def new_slide(section, title, sub=None, dark=False):
    s = P.slides.add_slide(BLANK); bg(s, "navy" if dark else "paper"); header(s, section, title, sub, dark); footer(s, len(P.slides), dark); return s

def card(slide, x, y, w, h, title, body, accent="purple", fill="white", title_size=15, body_size=11):
    box(slide, x, y, w, h, fill, "line" if fill == "white" else fill)
    box(slide, x, y, .06, h, accent, accent, False)
    text(slide, title, x+.2, y+.18, w-.38, .32, title_size, "navy", True)
    text(slide, body, x+.2, y+.58, w-.4, h-.68, body_size, "muted")

# 1 — cover
s=P.slides.add_slide(BLANK); bg(s,"navy")
box(s,8.35,0,4.98,7.5,"navy2","navy2",False)
for i,(x,y,r,col) in enumerate([(9.25,1.1,1.1,"purple"),(10.7,2.1,.55,"mint"),(9.7,3.8,.34,"blue"),(11.3,4.2,.82,"purple"),(8.8,5.5,.45,"mint")]):
    sh=s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(r), Inches(r)); sh.fill.solid(); sh.fill.fore_color.rgb=rgb(col); sh.line.fill.background()
line(s,9.8,1.8,10.95,2.35,"mint",2); line(s,10.1,4.1,11.3,4.55,"blue",2); line(s,9.3,5.6,10.2,4.5,"purple",2)
text(s,"◈  CODERBUDDY-CAPSTONE",.74,.65,6,.36,13,"mint",True,"Aptos Mono")
text(s,"An AI\nsoftware\nengineer.",.72,1.62,7.2,2.3,47,"white",True)
text(s,"From a natural-language request to a tested,\npreviewable app in one inspectable studio.",.78,4.3,6.7,.8,17,"D4DBE7")
text(s,"CAPSTONE PROJECT  ·  FINAL REVIEW",.78,5.55,5,.25,10,"mint",True,"Aptos Mono")
text(s,"P. Vardhini  ·  R. Yashritha  ·  A. Harika\nV. Ajaykumar  ·  V. Sneha\nProject Guide: K. Balakrishna",.78,5.95,6.8,.8,11,"white")
text(s,"SR UNIVERSITY  /  COMPUTER SCIENCE",8.78,6.67,4,.22,9,"D4DBE7",True,"Aptos Mono")
footer(s,1,True)

# 2 — problem
s=new_slide("01 · Motivation","AI can write code. Who makes sure the app works?","The gap is not another code snippet — it is the delivery work around it.")
card(s,.7,2.15,3.85,2.2,"Fragmented workflow","Requirements, planning, coding, setup, testing, and debugging happen in separate manual steps.","purple")
card(s,4.75,2.15,3.85,2.2,"High entry barrier","People without development experience still have to manage files, run applications, and interpret errors.","blue")
card(s,8.8,2.15,3.85,2.2,"Snippet-only assistants","Generated code often leaves integration, verification, and refinement to the user.","mint")
box(s,.7,4.75,11.95,1.35,"navy","navy")
text(s,"PROJECT CHALLENGE",.98,5.02,2,.22,9,"mint",True,"Aptos Mono")
text(s,"Can an open, inspectable AI workflow turn a plain-language requirement into an application that is actually tested and ready to preview?",.98,5.36,11.1,.52,16,"white",True)

# 3 — objective and scope
s=new_slide("02 · Objectives","A complete build loop, with a clear boundary","In scope: a transparent local web-app generator. Future work: production deployment and broad language support.")
objectives=[("01","Understand","Extract intent, users, constraints, and expected features."),("02","Plan","Make the implementation tasks visible and auditable."),("03","Build & verify","Generate app files, execute behavior tests, and correct failures."),("04","Refine","Apply follow-up natural-language changes and revalidate.")]
for i,(num,title,body) in enumerate(objectives):
    x=.72+i*3.13
    box(s,x,2.1,2.88,1.78,"white","line")
    text(s,num,x+.2,2.28,.6,.3,11,"purple",True,"Aptos Mono")
    text(s,title,x+.2,2.68,2.4,.32,16,"navy",True)
    text(s,body,x+.2,3.12,2.45,.56,10,"muted")
box(s,.72,4.28,5.72,1.7,"mintp","mintp")
text(s,"IN SCOPE",.98,4.52,2,.22,9,"green",True,"Aptos Mono")
text(s,"Web UI · Python tests · Preview · ZIP export · Source-aware refinement · Persistent queue/history",.98,4.92,5.1,.7,13,"ink",True)
box(s,6.68,4.28,5.72,1.7,"bluep","bluep")
text(s,"FUTURE SCOPE",6.95,4.52,2,.22,9,"blue",True,"Aptos Mono")
text(s,"Database scaffolding · Cloud publishing · GitHub integration · Multi-language code · OS-level isolation",6.95,4.92,5.1,.7,13,"ink",True)

# 4 — workflow
s=new_slide("03 · Method","Reason → plan → act → observe → correct","Each transition is explicit; validation output is the feedback signal.",True)
steps=[("01","UNDERSTAND","Interpret prompt"),("02","PLAN","Order tasks"),("03","GENERATE","Create app"),("04","TEST","Run behavior"),("05","CORRECT","Retry / deliver")]
for i,(n,title,desc) in enumerate(steps):
    x=.7+i*2.52
    box(s,x,2.45,2.1,1.4,"navy2","3B4A63")
    text(s,n,x+.18,2.62,.45,.2,9,"mint",True,"Aptos Mono")
    text(s,title,x+.18,2.94,1.72,.24,12,"white",True)
    text(s,desc,x+.18,3.36,1.72,.26,9,"D4DBE7")
    if i<4: line(s,x+2.12,3.16,x+2.45,3.16,"mint",1.7)
box(s,2.1,4.68,9.1,1.05,"navy2","3B4A63")
text(s,"FAILURE FEEDBACK LOOP",2.38,4.91,2.7,.2,9,"mint",True,"Aptos Mono")
text(s,"Actual validation diagnostics → model repair (up to 2 attempts) → rerun checks",5.05,4.86,5.75,.34,12,"white",True)
text(s,"If the model still fails, the fallback is labeled as a starter — not misrepresented as a custom solution.",2.4,5.25,8.7,.25,10,"D4DBE7")

# 5 — architecture
s=new_slide("04 · Architecture","Inspectable layers; replaceable components","LangGraph coordinates the loop. LangChain tools own bounded filesystem and test actions.")
rows=[("PRESENTATION","FastAPI + responsive engineering studio","Queue · projects · source · preview · export","purple"),("ORCHESTRATION","SQLite FIFO worker + LangGraph","Analyze → build → verify → repair · saved events","blue"),("MODEL","Azure Foundry / Ollama (configurable)","Server-side configuration · disclosed fallback","mint"),("TOOLS & WORKSPACE","LangChain tools + independent build folders","File writer · pytest · Node syntax checks","amber"),("QUALITY & DELIVERY","Persistent versions · preview · ZIP export","Behavior tests · bounded retries · source inspection","purple")]
for i,(tag,title,body,accent) in enumerate(rows):
    y=2.05+i*.88
    box(s,.8,y,11.7,.68,"white","line")
    box(s,.8,y,.075,.68,accent,accent,False)
    text(s,tag,1.02,y+.12,2.0,.22,9,accent,True,"Aptos Mono")
    text(s,title,3.0,y+.1,4.15,.25,12,"navy",True)
    text(s,body,7.28,y+.12,4.9,.27,10,"muted")

# 6 — artifacts
s=new_slide("05 · Generation","A prompt becomes a complete project bundle","The configured model returns interpretation, plan, code, business logic and tests as structured JSON.")
box(s,.76,2.05,3.1,3.95,"navy","navy")
text(s,"PROMPT",1.02,2.34,1.2,.22,9,"mint",True,"Aptos Mono")
text(s,"“Build a daily task app. Let me add tasks, mark them done, remove them, and see an empty state.”",1.02,2.82,2.52,1.5,17,"white",True)
text(s,"User request → configured model",1.02,5.42,2.5,.28,10,"D4DBE7")
files=[("index.html","Accessible app layout"),("styles.css","Responsive styling"),("app.js","Working browser behavior"),("app_logic.py","Business rules"),("test_app.py","Behavior + edge tests"),("README.md","Run/test instructions")]
for i,(name,desc) in enumerate(files):
    col=i%2; row=i//2; x=4.25+col*4.05; y=2.12+row*1.22
    box(s,x,y,3.75,.96,"white","line")
    text(s,"▣",x+.17,y+.2,.32,.3,15,"purple",True)
    text(s,name,x+.58,y+.16,2.95,.23,12,"navy",True,"Aptos Mono")
    text(s,desc,x+.58,y+.5,2.95,.22,9,"muted")
line(s,3.88,4.0,4.15,4.0,"purple",2)
text(s,"Project output is saved per run, can be inspected, previewed, and downloaded as a ZIP.",4.25,5.92,7.8,.3,11,"muted")

# 7 — tool execution
s=new_slide("06 · Tool execution","The model does not get a free-form shell","LangChain tool calls are narrow, auditable, and bound to the current run workspace.")
card(s,.78,2.18,3.75,2.15,"write_project_file","Accepts a relative path and text; path resolution must stay inside workspace/<run-id>.","purple")
card(s,4.8,2.18,3.75,2.15,"run_generated_tests","Runs the fixed Python pytest command with shell disabled, time limit, minimal environment, and import restrictions.","blue")
card(s,8.82,2.18,3.75,2.15,"serve_preview / export","Static assets are allow-listed; preview runs in a sandboxed iframe; ZIP contains only generated project files.","mint")
box(s,.8,4.78,11.77,1.08,"amberp","amberp")
text(s,"SECURITY NOTE",1.04,5.02,1.55,.2,9,"amber",True,"Aptos Mono")
text(s,"This capstone is designed for local, trusted prompts. Static checks and process limits reduce risk; they are not an OS/container sandbox. Do not expose it as a public code-execution service.",2.86,4.95,9.2,.5,11,"ink",True)

# 8 — dashboard
s=new_slide("07 · Product","A build studio, not a black box","The user can inspect progress, app behavior, source, agent decisions, and the test gate in one place.")
# create a stylized product frame
box(s,.82,2.02,8.1,4.2,"white","line")
box(s,.82,2.02,8.1,.42,"navy","navy",False)
for i,col in enumerate(("red","amber","mint")):
    sh=s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.02+i*.18), Inches(2.17), Inches(.08), Inches(.08));sh.fill.solid();sh.fill.fore_color.rgb=rgb(col);sh.line.fill.background()
text(s,"WORKSPACE LAYOUT  /  ILLUSTRATION",1.82,2.14,4,.18,8,"white",False,"Aptos Mono")
box(s,1.1,2.72,4.95,2.96,"paper","line")
text(s,"LIVE APP PREVIEW",1.32,2.91,2.4,.18,8,"purple",True,"Aptos Mono")
text(s,"Your daily list",1.33,3.35,3.8,.35,22,"navy",True)
box(s,1.35,3.92,4.42,.48,"white","line")
text(s,"Add a task…",1.58,4.06,2.3,.16,9,"muted")
for j,label in enumerate(("Plan the day","Review class notes","Submit project")):
    y=4.65+j*.28
    text(s,"✓" if j==0 else "○",1.42,y,.2,.17,9,"green" if j==0 else "muted",True)
    text(s,label,1.75,y,3.2,.17,9,"ink")
box(s,6.28,2.72,2.34,2.96,"navy","navy")
text(s,"QUALITY GATE",6.48,2.95,1.8,.18,8,"mint",True,"Aptos Mono")
text(s,"pytest",6.48,3.35,1.2,.25,15,"white",True)
text(s,"Actual output",6.48,3.88,1.8,.25,14,"mint",True)
text(s,"Scope shown explicitly",6.48,4.27,1.7,.38,9,"D4DBE7")
text(s,"Source files",6.48,4.9,1.4,.2,9,"D4DBE7")
text(s,"Download ZIP  ↓",6.48,5.26,1.65,.2,9,"mint",True)
card(s,9.28,2.15,3.25,1.16,"Live plan","See the agent stages and their status.","purple",title_size=13,body_size=9)
card(s,9.28,3.55,3.25,1.16,"Activity trace","Understand which tools ran and why.","blue",title_size=13,body_size=9)
card(s,9.28,4.95,3.25,1.16,"Natural-language iteration","Request changes; rebuild and retest.","mint",title_size=13,body_size=9)

# 9 — verification
s=new_slide("08 · Verification","A green syntax check is not enough","Generated behavior tests execute the app's business rules and edge cases; failures feed the correction loop.")
steps=[("GENERATE","app_logic.py + test_app.py"),("EXECUTE","pytest -q in run folder"),("OBSERVE","assertion + traceback"),("CORRECT","model gets exact failure"),("RE-RUN","up to 2 bounded retries")]
for i,(title,body) in enumerate(steps):
    x=.75+i*2.52
    box(s,x,2.32,2.12,1.55,"white","line")
    text(s,f"0{i+1}",x+.18,2.52,.42,.18,9,"purple",True,"Aptos Mono")
    text(s,title,x+.18,2.88,1.75,.27,12,"navy",True)
    text(s,body,x+.18,3.32,1.73,.34,9,"muted")
    if i<4: line(s,x+2.14,3.1,x+2.4,3.1,"purple",1.5)
box(s,.78,4.55,5.78,1.32,"mintp","mintp")
text(s,"CORE TEST SUITE",1.04,4.8,2.5,.2,9,"green",True,"Aptos Mono")
text(s,"FIFO · restart recovery · cancellation · idempotency · versioned refinement · API/safety tests",1.04,5.19,5.1,.38,12,"ink",True)
box(s,6.78,4.55,5.78,1.32,"bluep","bluep")
text(s,"DELIVERY EVIDENCE",7.04,4.8,2.5,.2,9,"blue",True,"Aptos Mono")
text(s,"Test output · source bundle · isolated app preview · visible fallback status",7.04,5.19,5.1,.38,12,"ink",True)

# 10 — stack
s=new_slide("09 · Technology","Open components, configurable inference","The model is configurable; the orchestration and tool contracts stay modular.")
stack=[("UI","HTML · CSS · JavaScript","Explorer · queue · projects · preview","purple"),("API","FastAPI · Pydantic · SQLite","Durable FIFO worker · version history","blue"),("AGENTS","LangGraph · modular Python agents","Stateful analyze/build/repair graph","mint"),("TOOLS","LangChain Core StructuredTools","Confined file writes · fixed test runner","amber"),("MODEL","Azure Foundry / Ollama","Configurable provider · keys server-side","purple"),("TESTS","pytest · Node syntax checks","Behavior-focused verification","blue")]
for i,(tag,title,body,acc) in enumerate(stack):
    x=.75+(i%3)*4.08;y=2.15+(i//3)*1.75
    box(s,x,y,3.78,1.42,"white","line");box(s,x,y,.06,1.42,acc,acc,False)
    text(s,tag,x+.24,y+.19,3,.2,9,acc,True,"Aptos Mono")
    text(s,title,x+.24,y+.55,3.28,.27,13,"navy",True)
    text(s,body,x+.24,y+.97,3.23,.25,9,"muted")
box(s,.78,5.95,11.75,.53,"navy","navy")
text(s,"BRIEF: GPT-OSS + GROQ  ·  IMPLEMENTED: AZURE FOUNDRY / GPT-4.1-MINI AND LOCAL OLLAMA",1.02,6.11,11.2,.18,9,"white",True,"Aptos Mono",PP_ALIGN.CENTER)

# 11 — demo and roadmap
s=new_slide("10 · Demonstration","Show the loop. Then show the app.","A short, repeatable final-review walkthrough.",True)
script=[("01","Queue requests","Submit a calculator, a quiz, and a third request; cancel the waiting third."),("02","Explain plan","Show one active request, FIFO order, actual plan and events."),("03","Inspect output","Open preview, exercise behavior, select source and inspect checks."),("04","Refine & retain","Apply a change; compare separate build versions in Projects."),("05","Reload & export","Reopen saved history after reload, then export the source ZIP.")]
for i,(n,t,b) in enumerate(script):
    y=2.05+i*.77
    text(s,n,.86,y,.46,.25,10,"mint",True,"Aptos Mono")
    text(s,t,1.5,y,2.0,.25,13,"white",True)
    text(s,b,3.68,y,8.7,.36,11,"D4DBE7")
box(s,.85,6.03,11.6,.55,"navy2","3B4A63")
text(s,"FALLBACK READY",1.05,6.2,1.65,.18,9,"mint",True,"Aptos Mono")
text(s,"If the configured provider is offline, disclose fallback; never claim it fulfilled arbitrary requirements.",3.0,6.16,8.95,.22,10,"white")

# 12 — close
s=P.slides.add_slide(BLANK);bg(s,"navy")
text(s,"◈  CODER BUDDY",.8,.62,4,.32,12,"mint",True,"Aptos Mono")
text(s,"A working app is\nonly the beginning.",.8,1.65,8.7,1.65,39,"white",True)
text(s,"Plan it. Build it. Test it. Learn from failure.\nRefine it — with every step visible.",.86,3.74,7.9,.95,18,"D4DBE7")
box(s,.86,5.36,5.5,.7,"navy2","3B4A63")
text(s,"Thank you  ·  Questions?",1.14,5.58,4.9,.28,15,"mint",True)
for i,(x,y,r,col) in enumerate([(9.5,1.35,1.15,"purple"),(10.8,3.0,.6,"mint"),(9.45,4.6,.9,"blue")]):
    sh=s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(r), Inches(r));sh.fill.solid();sh.fill.fore_color.rgb=rgb(col);sh.line.fill.background()
line(s,10.25,2.1,11.0,3.15,"mint",2);line(s,10.0,4.8,10.98,3.4,"purple",2)
footer(s,12,True)

P.core_properties.title = "CoderBuddy-CaPStone — An AI Software Engineer"
P.core_properties.subject = "Final capstone project presentation"
P.core_properties.author = "Coder Buddy Capstone Team"
P.core_properties.keywords = "agentic AI, LangGraph, LangChain, Ollama, software engineering"
P.save(OUTPUT)
print(f"Wrote {OUTPUT} ({len(P.slides)} slides)")
