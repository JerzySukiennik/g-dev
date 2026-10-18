"""Generate description -> single-file HTML pairs for G-Dev's supervised fine-tuning.

Every page is assembled from a pattern (button, card, spinner, snake, ...) with
parameters drawn at random. A parameter that changes the page is always stated in
the description, and a description never states something the page does not do,
so the model learns "say it, get it" instead of guessing. Pages are checked in a
real browser by verify.mjs before they are kept.

Besides single requests it writes two-turn conversations: an edit ("make it red"),
where the second page is the first one regenerated with exactly one parameter
changed, and a switch, where the second request is an unrelated new page. The
model has to tell the two apart from the conversation alone.

Usage:
    python data/web_sft/gen.py --out DIR      # writes DIR/pages.jsonl and DIR/convs.jsonl
"""

import argparse
import json
import random
from pathlib import Path

COLORS = {
    "indigo": ("#4f46e5", "#4338ca", "#ffffff"),
    "blue": ("#2563eb", "#1d4ed8", "#ffffff"),
    "green": ("#16a34a", "#15803d", "#ffffff"),
    "red": ("#dc2626", "#b91c1c", "#ffffff"),
    "orange": ("#ea580c", "#c2410c", "#ffffff"),
    "pink": ("#db2777", "#be185d", "#ffffff"),
    "purple": ("#9333ea", "#7e22ce", "#ffffff"),
    "teal": ("#0d9488", "#0f766e", "#ffffff"),
    "yellow": ("#eab308", "#ca8a04", "#1f2937"),
    "gray": ("#4b5563", "#374151", "#ffffff"),
}
LABELS = ["Click me", "Play", "Start", "Submit", "Buy now", "Sign up", "Download", "Get started",
          "Launch", "Subscribe", "Send", "Continue", "Learn more", "Try it"]
HEADINGS = ["Welcome", "Hello there", "Coming soon", "Let's go", "Good morning", "Happy birthday",
            "Hello world", "Rocket launch", "Summer sale", "New arrivals"]
CARDS = [("Rocket launch", "Liftoff is scheduled for Saturday morning."),
         ("Weekly report", "Everything went according to plan this week."),
         ("New message", "You have three unread messages waiting."),
         ("Piano lessons", "Practice for twenty minutes every day."),
         ("Garden tips", "Water the plants early in the morning."),
         ("Travel notes", "The train to the coast leaves at noon."),
         ("Recipe of the day", "Tomato soup with fresh basil and bread."),
         ("Project update", "The new design is ready for review.")]
NAVS = [["Home", "About", "Blog", "Contact"], ["Home", "Shop", "Pricing", "Support"],
        ["Work", "Studio", "News", "Hire us"], ["Games", "Music", "Videos", "Profile"]]
FAQS = [("What is this?", "A small demo page."), ("How much does it cost?", "It is completely free."),
        ("Can I change it?", "Yes, everything is editable."), ("Who made it?", "A tiny language model."),
        ("Does it work offline?", "Yes, it is a single file."), ("Is it fast?", "It loads instantly.")]
TABS = [["Overview", "Features", "Pricing"], ["Info", "Photos", "Reviews"], ["Today", "Week", "Month"]]
MODALS = [("Open modal", "Hello!", "This is a modal window."), ("Show details", "Details", "Here is some more information."),
          ("Open", "Notice", "Your changes have been saved.")]
TOGGLES = ["Dark mode", "Notifications", "Wi-Fi", "Sound", "Airplane mode", "Auto save"]

LEADS = ["Make", "Create", "Build", "Write", "Generate", "I need", "Give me", "Can you make", "Please create", "Design"]


def tpl(s, **kw):
    for k, v in kw.items():
        s = s.replace(f"<<{k}>>", str(v))
    return s


def say(rng, templates, **slots):
    s = rng.choice(templates)
    for k, v in slots.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def finish(rng, core, dark):
    core = core.strip()
    if dark:
        core += rng.choice([" on a dark background", ", dark theme", " with a dark theme", " on a dark page"])
    lead = rng.choice(LEADS)
    text = f"{lead} {core}"
    if rng.random() < 0.5:
        text += "."
    return text


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><<title>></title>
<style>
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  font-family: system-ui, sans-serif;
  background: <<bg>>;
  color: <<fg>>;
}
<<css>>
</style>
</head>
<body>
<<body>>
</body>
</html>
"""


def page(title, css, body, dark, script="", bg=None):
    bg = bg or ("#111827" if dark else "#f5f5f7")
    fg = "#f9fafb" if dark else "#1f2937"
    out = tpl(PAGE, title=title, css=css.strip("\n"), body=body.strip("\n"), bg=bg, fg=fg)
    if script:
        out = out.replace("</body>", "<script>\n" + script.strip("\n") + "\n</script>\n</body>")
    return out


def surface(dark):
    return "#1f2937" if dark else "#ffffff"


def pick_color(rng, exclude=()):
    name = rng.choice([c for c in COLORS if c not in exclude])
    return name, COLORS[name]


class Params:
    """Records every parameter a pattern draws, or replays given values.

    Regenerating a page with all of its recorded parameters and one of them changed
    gives exactly the edited page, which is what the edit conversations need.
    """

    def __init__(self, given=None):
        self.given = dict(given or {})
        self.vals = {}

    def __call__(self, name, draw):
        v = self.given[name] if name in self.given else draw()
        self.vals[name] = v
        return v


# ---------------------------------------------------------------- UI patterns

def button_hover(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    shape = P("shape", lambda: rng.choice(["rounded", "pill", "square"]))
    radius = {"rounded": "10px", "pill": "999px", "square": "0"}[shape]
    label = P("label", lambda: rng.choice(LABELS))
    effect = P("effect", lambda: rng.choice(["grow", "lift", "glow", "darken", "outline"]))
    hover = {
        "grow": "transform: scale(1.1);",
        "lift": "transform: translateY(-4px);\n  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.25);",
        "glow": f"box-shadow: 0 0 22px {hx};",
        "darken": f"background: {hd};\n  border-color: {hd};",
        "outline": f"background: transparent;\n  color: {hx};",
    }[effect]
    ephrase = {
        "grow": ["grows slightly on hover", "scales up when you hover over it", "gets bigger on hover"],
        "lift": ["lifts up with a shadow on hover", "floats upward when hovered", "moves up and gets a shadow on hover"],
        "glow": ["glows on hover", "gets a glowing shadow when you hover over it"],
        "darken": ["gets darker on hover", "turns a darker shade when hovered"],
        "outline": ["turns into an outline on hover", "becomes an outlined button when you hover over it"],
    }[effect]
    shape_word = {"rounded": rng.choice(["rounded ", ""]), "pill": rng.choice(["pill-shaped ", "pill "]), "square": "square "}[shape]
    core = say(rng, ["a {s}{c} button that says \"{l}\" and {e}", "a page with a {s}{c} button labeled \"{l}\" that {e}",
                     "a {c} {s}button \"{l}\" which {e}"], s=shape_word, c=cname, l=label, e=rng.choice(ephrase))
    css = f""".btn {{
  padding: 14px 28px;
  border: 2px solid {hx};
  border-radius: {radius};
  background: {hx};
  color: {tx};
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}}
.btn:hover {{
  {hover}
}}"""
    body = f'<button class="btn">{label}</button>'
    return finish(rng, core, dark), page("Button", css, body, dark), {"hover": ".btn", "wait": 350}


def card_hover(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    title, text = P("card", lambda: rng.choice(CARDS))
    effect = P("effect", lambda: rng.choice(["lift", "tilt", "grow"]))
    hover = {"lift": "transform: translateY(-8px);\n  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.25);",
             "tilt": "transform: rotate(-2deg);\n  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.25);",
             "grow": "transform: scale(1.05);\n  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.25);"}[effect]
    ephrase = {"lift": ["lifts up on hover", "floats up when hovered"], "tilt": ["tilts slightly on hover", "rotates a little when you hover over it"],
               "grow": ["grows on hover", "scales up when hovered"]}[effect]
    core = say(rng, ["a card with a {c} top border, the title \"{t}\" and the text \"{x}\" that {e}",
                     "a {c} card titled \"{t}\" saying \"{x}\", it {e}"], c=cname, t=title, x=text, e=rng.choice(ephrase))
    css = f""".card {{
  width: 280px;
  padding: 24px;
  border-radius: 14px;
  border-top: 4px solid {hx};
  background: {surface(dark)};
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}}
.card:hover {{
  {hover}
}}
.card h2 {{
  margin: 0 0 8px;
  font-size: 20px;
}}
.card p {{
  margin: 0;
  opacity: 0.8;
}}"""
    body = f'<div class="card">\n  <h2>{title}</h2>\n  <p>{text}</p>\n</div>'
    return finish(rng, core, dark), page("Card", css, body, dark), {"hover": ".card", "wait": 400}


def spinner(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    kind = P("kind", lambda: rng.choice(["ring", "dots", "bars", "pulse"]))
    speed = P("speed", lambda: rng.choice(["slow", "normal", "normal", "fast"]))
    track = "#374151" if dark else "#d1d5db"
    d = {"ring": {"slow": "1.6s", "normal": "0.9s", "fast": "0.45s"}, "dots": {"slow": "1.8s", "normal": "1s", "fast": "0.5s"},
         "bars": {"slow": "1.6s", "normal": "1s", "fast": "0.5s"}, "pulse": {"slow": "2s", "normal": "1.2s", "fast": "0.6s"}}[kind][speed]
    if kind == "ring":
        css = f""".spinner {{
  width: 48px;
  height: 48px;
  border: 5px solid {track};
  border-top-color: {hx};
  border-radius: 50%;
  animation: spin {d} linear infinite;
}}
@keyframes spin {{
  to {{
    transform: rotate(360deg);
  }}
}}"""
        body = '<div class="spinner"></div>'
    elif kind == "dots":
        css = f""".dots span {{
  display: inline-block;
  width: 16px;
  height: 16px;
  margin: 6px;
  border-radius: 50%;
  background: {hx};
  animation: pulse {d} infinite ease-in-out;
}}
.dots span:nth-child(2) {{
  animation-delay: 0.2s;
}}
.dots span:nth-child(3) {{
  animation-delay: 0.4s;
}}
@keyframes pulse {{
  0%, 80%, 100% {{
    transform: scale(0.4);
    opacity: 0.4;
  }}
  40% {{
    transform: scale(1);
    opacity: 1;
  }}
}}"""
        body = '<div class="dots"><span></span><span></span><span></span></div>'
    elif kind == "bars":
        css = f""".bars {{
  display: flex;
  align-items: center;
  gap: 6px;
  height: 50px;
}}
.bars span {{
  width: 8px;
  height: 100%;
  background: {hx};
  animation: stretch {d} infinite ease-in-out;
}}
.bars span:nth-child(2) {{ animation-delay: 0.1s; }}
.bars span:nth-child(3) {{ animation-delay: 0.2s; }}
.bars span:nth-child(4) {{ animation-delay: 0.3s; }}
.bars span:nth-child(5) {{ animation-delay: 0.4s; }}
@keyframes stretch {{
  0%, 100% {{
    transform: scaleY(0.3);
  }}
  50% {{
    transform: scaleY(1);
  }}
}}"""
        body = '<div class="bars"><span></span><span></span><span></span><span></span><span></span></div>'
    else:
        css = f""".pulse {{
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: {hx};
  animation: beat {d} infinite ease-in-out;
}}
@keyframes beat {{
  0% {{
    transform: scale(0.5);
    opacity: 1;
  }}
  100% {{
    transform: scale(1.4);
    opacity: 0;
  }}
}}"""
        body = '<div class="pulse"></div>'
    kname = {"ring": ["a spinning ring loader", "a ring spinner"], "dots": ["a loader with three pulsing dots", "three bouncing dots loader"],
             "bars": ["a loader made of five stretching bars", "an equalizer-style bar loader"], "pulse": ["a pulsing circle loader", "a circle that pulses and fades"]}[kind]
    core = f"{rng.choice(kname)} in {cname}"
    if speed != "normal":
        core += f", {speed}"
    return finish(rng, core, dark), page("Loader", css, body, dark), {"animated": True}


def progress(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    d = {"slow": "4s", "normal": "2s", "fast": "1s"}[speed]
    shape = P("shape", lambda: rng.choice(["rounded", "square"]))
    r = "999px" if shape == "rounded" else "0"
    track = "#374151" if dark else "#e5e7eb"
    css = f""".bar {{
  width: 300px;
  height: 16px;
  border-radius: {r};
  background: {track};
  overflow: hidden;
}}
.fill {{
  height: 100%;
  width: 0;
  background: {hx};
  animation: load {d} ease-in-out infinite;
}}
@keyframes load {{
  0% {{
    width: 0;
  }}
  100% {{
    width: 100%;
  }}
}}"""
    body = '<div class="bar"><div class="fill"></div></div>'
    core = say(rng, ["a {s}{c} progress bar that keeps filling up", "a {c} loading bar that fills from left to right, {s2}"],
               s=("" if speed == "normal" else speed + " "), c=cname, s2=("at a normal speed" if speed == "normal" else speed))
    if shape == "square":
        core += rng.choice([" with square corners", ", square ends"])
    return finish(rng, core, dark), page("Progress", css, body, dark), {"animated": True}


def toggle(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    label = P("label", lambda: rng.choice(TOGGLES))
    off = "#4b5563" if dark else "#cbd5e1"
    css = f""".row {{
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 18px;
}}
.switch {{
  position: relative;
  width: 52px;
  height: 30px;
}}
.switch input {{
  opacity: 0;
  width: 0;
  height: 0;
}}
.slider {{
  position: absolute;
  inset: 0;
  border-radius: 30px;
  background: {off};
  cursor: pointer;
  transition: background 0.25s;
}}
.slider::before {{
  content: "";
  position: absolute;
  left: 3px;
  top: 3px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #ffffff;
  transition: transform 0.25s;
}}
input:checked + .slider {{
  background: {hx};
}}
input:checked + .slider::before {{
  transform: translateX(22px);
}}"""
    body = f'<div class="row">\n  <label class="switch"><input type="checkbox"><span class="slider"></span></label>\n  <span>{label}</span>\n</div>'
    core = say(rng, ["a toggle switch labeled \"{l}\" that turns {c} when it is on", "a {c} on/off switch next to the text \"{l}\"",
                     "a \"{l}\" switch that becomes {c} when you turn it on"], l=label, c=cname)
    return finish(rng, core, dark), page("Toggle", css, body, dark), {"click": ".slider", "wait": 400}


def text_fade(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    text = P("text", lambda: rng.choice(HEADINGS))
    direction = P("direction", lambda: rng.choice(["bottom", "left", "top", "fade"]))
    start = {"bottom": "transform: translateY(40px);", "left": "transform: translateX(-60px);", "top": "transform: translateY(-40px);", "fade": ""}[direction]
    end = {"fade": ""}.get(direction, "transform: none;")
    css = f"""h1 {{
  margin: 0;
  font-size: 56px;
  color: {hx};
  animation: appear 1.2s ease-out;
}}
@keyframes appear {{
  from {{
    opacity: 0;
    {start}
  }}
  to {{
    opacity: 1;
    {end}
  }}
}}""".replace("\n    \n", "\n")
    body = f"<h1>{text}</h1>"
    how = {"bottom": ["slides up from below while fading in", "rises from the bottom and fades in"], "left": ["slides in from the left while fading in", "comes in from the left and fades in"],
           "top": ["drops down from the top while fading in", "slides down from above and fades in"], "fade": ["fades in", "slowly fades in"]}[direction]
    core = f"a big {cname} heading \"{text}\" that {rng.choice(how)} when the page loads"
    return finish(rng, core, dark), page("Heading", css, body, dark), {"animated": True, "delay": 60}


def gradient_bg(rng, dark, P):
    names = P("colors", lambda: rng.sample(list(COLORS), 3))
    cols = [COLORS[n][0] for n in names]
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    d = {"slow": "14s", "normal": "8s", "fast": "3s"}[speed]
    text = P("text", lambda: rng.choice(HEADINGS))
    css = f"""body {{
  background: linear-gradient(-45deg, {cols[0]}, {cols[1]}, {cols[2]});
  background-size: 400% 400%;
  animation: shift {d} ease infinite;
}}
h1 {{
  margin: 0;
  font-size: 52px;
  color: #ffffff;
}}
@keyframes shift {{
  0% {{
    background-position: 0% 50%;
  }}
  50% {{
    background-position: 100% 50%;
  }}
  100% {{
    background-position: 0% 50%;
  }}
}}"""
    body = f"<h1>{text}</h1>"
    core = f"a page with an animated gradient background that moves between {names[0]}, {names[1]} and {names[2]}, {'' if speed == 'normal' else speed + ', '}with the white heading \"{text}\" in the middle"
    return finish(rng, core, False), page("Gradient", css, body, False), {"animated": True, "delay": 100}


def navbar(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    items = P("items", lambda: rng.choice(NAVS))
    css = f""".nav {{
  display: flex;
  gap: 28px;
}}
.nav a {{
  position: relative;
  padding: 6px 0;
  color: inherit;
  text-decoration: none;
  font-size: 18px;
}}
.nav a::after {{
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  width: 0;
  height: 3px;
  background: {hx};
  transition: width 0.3s ease;
}}
.nav a:hover::after {{
  width: 100%;
}}"""
    body = '<nav class="nav">\n' + "\n".join(f'  <a href="#">{i}</a>' for i in items) + "\n</nav>"
    core = say(rng, ["a navigation bar with the links {l} where a {c} underline slides in under a link on hover",
                     "a simple menu with {l} that gets an animated {c} underline when you hover over an item"], l=", ".join(items[:-1]) + " and " + items[-1], c=cname)
    return finish(rng, core, dark), page("Navbar", css, body, dark), {"hover": ".nav a", "wait": 450}


def modal(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    label, title, text = P("modal", lambda: rng.choice(MODALS))
    css = f""".btn {{
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  background: {hx};
  color: {tx};
  font-size: 16px;
  cursor: pointer;
}}
.overlay {{
  position: fixed;
  inset: 0;
  display: none;
  place-items: center;
  background: rgba(0, 0, 0, 0.5);
}}
.overlay.show {{
  display: grid;
}}
.modal {{
  width: 280px;
  padding: 24px;
  border-radius: 14px;
  background: {surface(dark)};
  text-align: center;
}}
.modal h2 {{
  margin: 0 0 8px;
}}"""
    body = f'<button class="btn" id="open">{label}</button>\n<div class="overlay" id="overlay">\n  <div class="modal">\n    <h2>{title}</h2>\n    <p>{text}</p>\n    <button class="btn" id="close">Close</button>\n  </div>\n</div>'
    script = """const overlay = document.getElementById("overlay");
document.getElementById("open").addEventListener("click", () => overlay.classList.add("show"));
document.getElementById("close").addEventListener("click", () => overlay.classList.remove("show"));"""
    core = say(rng, ["a {c} button \"{l}\" that opens a modal window titled \"{t}\" with the text \"{x}\" and a Close button",
                     "a page with a button \"{l}\" in {c}; clicking it opens a popup saying \"{t}\" and \"{x}\", with a Close button"], c=cname, l=label, t=title, x=text)
    return finish(rng, core, dark), page("Modal", css, body, dark, script), {"click": "#open", "wait": 150}


def tabs(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    names = P("tabs", lambda: rng.choice(TABS))
    css = f""".tabs {{
  width: 320px;
}}
.tab-row {{
  display: flex;
  border-bottom: 2px solid {"#374151" if dark else "#e5e7eb"};
}}
.tab {{
  flex: 1;
  padding: 10px;
  border: none;
  border-bottom: 3px solid transparent;
  background: none;
  color: inherit;
  font-size: 16px;
  cursor: pointer;
}}
.tab.active {{
  border-bottom-color: {hx};
  color: {hx};
  font-weight: 600;
}}
.panel {{
  display: none;
  padding: 18px 4px;
}}
.panel.active {{
  display: block;
}}"""
    btns = "\n".join(f'    <button class="tab{" active" if i == 0 else ""}" data-i="{i}">{n}</button>' for i, n in enumerate(names))
    panels = "\n".join(f'  <div class="panel{" active" if i == 0 else ""}">This is the {n.lower()} tab.</div>' for i, n in enumerate(names))
    body = f'<div class="tabs">\n  <div class="tab-row">\n{btns}\n  </div>\n{panels}\n</div>'
    script = """const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    panels.forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    panels[tab.dataset.i].classList.add("active");
  });
});"""
    core = f"a tab switcher with the tabs {', '.join(names[:-1])} and {names[-1]}, the active tab highlighted in {cname}, each tab showing its own text"
    return finish(rng, core, dark), page("Tabs", css, body, dark, script), {"click": ".tab:nth-child(2)", "wait": 150}


def accordion(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    faqs = P("faqs", lambda: rng.sample(FAQS, 3))
    css = f""".faq {{
  width: 320px;
}}
details {{
  padding: 14px 16px;
  margin-bottom: 8px;
  border-radius: 10px;
  border-left: 4px solid {hx};
  background: {surface(dark)};
}}
summary {{
  font-weight: 600;
  cursor: pointer;
}}
details p {{
  margin: 10px 0 0;
  opacity: 0.8;
}}"""
    body = '<div class="faq">\n' + "\n".join(f"  <details>\n    <summary>{q}</summary>\n    <p>{a}</p>\n  </details>" for q, a in faqs) + "\n</div>"
    core = f"an FAQ accordion with three questions (\"{faqs[0][0]}\", \"{faqs[1][0]}\" and \"{faqs[2][0]}\") that expand to show an answer, with a {cname} left border"
    return finish(rng, core, dark), page("FAQ", css, body, dark), {"click": "summary", "wait": 150}


def counter(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    minus = P("minus", lambda: rng.random() < 0.5)
    css = f""".counter {{
  text-align: center;
}}
#value {{
  font-size: 72px;
  font-weight: 700;
  color: {hx};
}}
.btn {{
  width: 52px;
  height: 52px;
  margin: 0 6px;
  border: none;
  border-radius: 50%;
  background: {hx};
  color: {tx};
  font-size: 26px;
  cursor: pointer;
}}"""
    mbtn = '\n  <button class="btn" id="dec">-</button>' if minus else ""
    body = f'<div class="counter">\n  <div id="value">0</div>{mbtn}\n  <button class="btn" id="inc">+</button>\n</div>'
    script = 'let count = 0;\nconst value = document.getElementById("value");\n' \
             'document.getElementById("inc").addEventListener("click", () => {\n  count++;\n  value.textContent = count;\n});\n'
    if minus:
        script += 'document.getElementById("dec").addEventListener("click", () => {\n  count--;\n  value.textContent = count;\n});\n'
    core = f"a click counter with a big {cname} number and {'a plus and a minus button' if minus else 'a plus button'}"
    return finish(rng, core, dark), page("Counter", css, body, dark, script), {"click": "#inc", "wait": 100}


def theme_toggle(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    css = f"""body {{
  transition: background 0.3s, color 0.3s;
}}
body.dark {{
  background: #111827;
  color: #f9fafb;
}}
.box {{
  text-align: center;
}}
h1 {{
  margin: 0 0 16px;
}}
.btn {{
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  background: {hx};
  color: {tx};
  font-size: 16px;
  cursor: pointer;
}}"""
    body = '<div class="box">\n  <h1>Theme demo</h1>\n  <button class="btn" id="toggle">Toggle theme</button>\n</div>'
    script = 'document.getElementById("toggle").addEventListener("click", () => {\n  document.body.classList.toggle("dark");\n});'
    core = f"a light page with a {cname} \"Toggle theme\" button that switches the whole page between light and dark mode"
    return finish(rng, core, False), page("Theme", css, body, False, script), {"click": "#toggle", "wait": 450}


# ------------------------------------------------------------- canvas patterns

def bouncing_balls(rng, dark, P):
    multi = P("multi", lambda: rng.random() < 0.5)
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    rainbow = P("rainbow", lambda: multi and rng.random() < 0.5)
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    v = {"slow": 1.5, "normal": 3, "fast": 6}[speed]
    n = 6 if multi else 1
    fill = '`hsl(${i * 60}, 80%, 55%)`' if rainbow else f'"{hx}"'
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const balls = [];
for (let i = 0; i < {n}; i++) {{
  balls.push({{
    x: 40 + Math.random() * 320,
    y: 40 + Math.random() * 220,
    vx: ({v} + Math.random()) * (Math.random() < 0.5 ? -1 : 1),
    vy: ({v} + Math.random()) * (Math.random() < 0.5 ? -1 : 1),
    r: 16,
    color: {fill},
  }});
}}
function loop() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const b of balls) {{
    b.x += b.vx;
    b.y += b.vy;
    if (b.x < b.r || b.x > canvas.width - b.r) b.vx *= -1;
    if (b.y < b.r || b.y > canvas.height - b.r) b.vy *= -1;
    ctx.beginPath();
    ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
    ctx.fillStyle = b.color;
    ctx.fill();
  }}
  requestAnimationFrame(loop);
}}
loop();"""
    css = f"canvas {{\n  background: {'#0b1020' if dark else '#ffffff'};\n  border-radius: 8px;\n}}"
    body = '<canvas id="c" width="400" height="300"></canvas>'
    if n == 1:
        core = f"a {cname} ball bouncing around inside a canvas"
    else:
        core = f"{n} {'rainbow-colored' if rainbow else cname} balls bouncing around inside a canvas"
    if speed != "normal":
        core += f", {speed}"
    return finish(rng, core, dark), page("Bouncing balls", css, body, dark, script), {"animated": True, "delay": 50, "canvas": "#c"}


def particles(rng, dark, P):
    kind = P("kind", lambda: rng.choice(["snow", "bubbles", "stars"]))
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    count = P("count", lambda: rng.choice([60, 150]))
    bg = {"snow": "#0b1e3a", "bubbles": "#0e4a6b", "stars": "#05060f"}[kind]
    if kind == "snow":
        color = "#ffffff"
    elif kind == "bubbles":
        color = "rgba(255, 255, 255, 0.6)"
    else:
        color = hx
    if kind == "snow":
        init = "x: Math.random() * W, y: Math.random() * H, r: 1 + Math.random() * 3, s: 0.5 + Math.random() * 1.5"
        step = "p.y += p.s;\n    p.x += Math.sin(p.y / 30) * 0.4;\n    if (p.y > H) { p.y = -5; p.x = Math.random() * W; }"
        draw = "ctx.beginPath();\n    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);\n    ctx.fillStyle = COLOR;\n    ctx.fill();"
    elif kind == "bubbles":
        init = "x: Math.random() * W, y: Math.random() * H, r: 4 + Math.random() * 14, s: 0.3 + Math.random() * 1"
        step = "p.y -= p.s;\n    if (p.y < -p.r) { p.y = H + p.r; p.x = Math.random() * W; }"
        draw = "ctx.beginPath();\n    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);\n    ctx.strokeStyle = COLOR;\n    ctx.lineWidth = 2;\n    ctx.stroke();"
    else:
        init = "x: Math.random() * W, y: Math.random() * H, r: 0.5 + Math.random() * 2, t: Math.random() * 6.28"
        step = "p.t += 0.05;"
        draw = "ctx.globalAlpha = 0.5 + 0.5 * Math.sin(p.t);\n    ctx.beginPath();\n    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);\n    ctx.fillStyle = COLOR;\n    ctx.fill();\n    ctx.globalAlpha = 1;"
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
const particles = [];
for (let i = 0; i < {count}; i++) {{
  particles.push({{ {init} }});
}}
function loop() {{
  ctx.clearRect(0, 0, W, H);
  for (const p of particles) {{
    {step}
    {draw.replace("COLOR", repr(color).replace("'", '"'))}
  }}
  requestAnimationFrame(loop);
}}
loop();"""
    css = f"canvas {{\n  background: {bg};\n  border-radius: 8px;\n}}"
    body = '<canvas id="c" width="400" height="300"></canvas>'
    word = {"snow": "falling white snow", "bubbles": "light bubbles rising", "stars": f"{cname} twinkling stars"}[kind]
    core = f"an animation of {word} on a canvas, {'a lot of them' if count > 100 else 'not too many'}"
    return finish(rng, core, False), page("Particles", css, body, False, script, bg="#f5f5f7"), {"animated": True, "delay": 50, "canvas": "#c"}


def pong(rng, dark, P):
    c1 = P("c1", lambda: pick_color(rng)[0])
    h1 = COLORS[c1][0]
    c2 = P("c2", lambda: pick_color(rng, exclude=(c1,))[0])
    h2 = COLORS[c2][0]
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
const player = {{ y: H / 2 - 30, h: 60 }};
const ai = {{ y: H / 2 - 30, h: 60 }};
const ball = {{ x: W / 2, y: H / 2, vx: 4, vy: 3, r: 8 }};
let score = 0;
let up = false;
let down = false;
document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowUp") up = true;
  if (e.key === "ArrowDown") down = true;
}});
document.addEventListener("keyup", (e) => {{
  if (e.key === "ArrowUp") up = false;
  if (e.key === "ArrowDown") down = false;
}});
function reset() {{
  ball.x = W / 2;
  ball.y = H / 2;
  ball.vx = 4 * (Math.random() < 0.5 ? -1 : 1);
  ball.vy = 3;
}}
function loop() {{
  if (up) player.y -= 5;
  if (down) player.y += 5;
  player.y = Math.max(0, Math.min(H - player.h, player.y));
  ai.y += (ball.y - (ai.y + ai.h / 2)) * 0.06;
  ball.x += ball.vx;
  ball.y += ball.vy;
  if (ball.y < ball.r || ball.y > H - ball.r) ball.vy *= -1;
  if (ball.x < 24 && ball.y > player.y && ball.y < player.y + player.h && ball.vx < 0) {{
    ball.vx *= -1.05;
    score++;
  }}
  if (ball.x > W - 24 && ball.y > ai.y && ball.y < ai.y + ai.h && ball.vx > 0) ball.vx *= -1;
  if (ball.x < 0) {{
    score = 0;
    reset();
  }}
  if (ball.x > W) reset();
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "{h1}";
  ctx.fillRect(10, player.y, 8, player.h);
  ctx.fillStyle = "{h2}";
  ctx.fillRect(W - 18, ai.y, 8, ai.h);
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2);
  ctx.fill();
  ctx.font = "20px system-ui";
  ctx.fillText(score, W / 2 - 6, 28);
  requestAnimationFrame(loop);
}}
loop();"""
    css = "canvas {\n  border-radius: 8px;\n}"
    body = '<canvas id="c" width="480" height="320"></canvas>'
    core = f"a Pong game where I move the {c1} paddle on the left with the arrow keys, the computer plays the {c2} paddle, and the score counts my hits"
    return finish(rng, core, dark), page("Pong", css, body, dark, script), {"animated": True, "delay": 60, "keys": ["ArrowUp"], "canvas": "#c"}


def snake(rng, dark, P):
    c1 = P("c1", lambda: pick_color(rng)[0])
    h1 = COLORS[c1][0]
    c2 = P("c2", lambda: pick_color(rng, exclude=(c1,))[0])
    h2 = COLORS[c2][0]
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    ms = {"slow": 150, "normal": 100, "fast": 60}[speed]
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const size = 20;
const cells = canvas.width / size;
let snake;
let dir;
let food;
let score;
function start() {{
  snake = [{{ x: 10, y: 10 }}, {{ x: 9, y: 10 }}, {{ x: 8, y: 10 }}];
  dir = {{ x: 1, y: 0 }};
  score = 0;
  placeFood();
}}
function placeFood() {{
  food = {{ x: Math.floor(Math.random() * cells), y: Math.floor(Math.random() * cells) }};
}}
document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowUp" && dir.y === 0) dir = {{ x: 0, y: -1 }};
  if (e.key === "ArrowDown" && dir.y === 0) dir = {{ x: 0, y: 1 }};
  if (e.key === "ArrowLeft" && dir.x === 0) dir = {{ x: -1, y: 0 }};
  if (e.key === "ArrowRight" && dir.x === 0) dir = {{ x: 1, y: 0 }};
}});
function step() {{
  const head = {{ x: snake[0].x + dir.x, y: snake[0].y + dir.y }};
  const hitWall = head.x < 0 || head.y < 0 || head.x >= cells || head.y >= cells;
  const hitSelf = snake.some((s) => s.x === head.x && s.y === head.y);
  if (hitWall || hitSelf) {{
    start();
    return;
  }}
  snake.unshift(head);
  if (head.x === food.x && head.y === food.y) {{
    score++;
    document.getElementById("score").textContent = "Score: " + score;
    placeFood();
  }} else {{
    snake.pop();
  }}
}}
function draw() {{
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "{h2}";
  ctx.fillRect(food.x * size, food.y * size, size - 2, size - 2);
  ctx.fillStyle = "{h1}";
  for (const s of snake) ctx.fillRect(s.x * size, s.y * size, size - 2, size - 2);
}}
start();
setInterval(() => {{
  step();
  draw();
}}, {ms});"""
    css = "#score {\n  margin-bottom: 10px;\n  text-align: center;\n  font-size: 20px;\n}\ncanvas {\n  border-radius: 8px;\n}"
    body = '<div>\n  <div id="score">Score: 0</div>\n  <canvas id="c" width="400" height="400"></canvas>\n</div>'
    core = f"a Snake game with a {c1} snake and {c2} food, controlled with the arrow keys, showing the score above the board{'' if speed == 'normal' else ', ' + speed}"
    return finish(rng, core, dark), page("Snake", css, body, dark, script), {"animated": True, "delay": 120, "keys": ["ArrowDown"], "canvas": "#c"}


def click_target(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    size = P("size", lambda: rng.choice(["small", "normal", "big"]))
    px = {"small": 36, "normal": 56, "big": 84}[size]
    css = f"""#score {{
  margin-bottom: 12px;
  text-align: center;
  font-size: 22px;
}}
#area {{
  position: relative;
  width: 400px;
  height: 300px;
  border-radius: 10px;
  background: {surface(dark)};
}}
#target {{
  position: absolute;
  left: 50px;
  top: 50px;
  width: {px}px;
  height: {px}px;
  border: none;
  border-radius: 50%;
  background: {hx};
  cursor: pointer;
}}"""
    body = '<div>\n  <div id="score">Score: 0</div>\n  <div id="area">\n    <button id="target"></button>\n  </div>\n</div>'
    script = f"""const area = document.getElementById("area");
const target = document.getElementById("target");
const scoreEl = document.getElementById("score");
let score = 0;
target.addEventListener("click", () => {{
  score++;
  scoreEl.textContent = "Score: " + score;
  target.style.left = Math.random() * (area.clientWidth - {px}) + "px";
  target.style.top = Math.random() * (area.clientHeight - {px}) + "px";
}});"""
    core = f"a click game with a {size + ' ' if size != 'normal' else ''}{cname} circle that jumps to a random spot every time I click it, and a score counter"
    return finish(rng, core, dark), page("Click game", css, body, dark, script), {"click": "#target", "wait": 100}


PATTERNS = [
    (button_hover, 1.0), (card_hover, 0.8), (spinner, 1.0), (progress, 0.6), (toggle, 0.7), (text_fade, 0.7),
    (gradient_bg, 0.6), (navbar, 0.6), (modal, 0.7), (tabs, 0.7), (accordion, 0.6), (counter, 0.7), (theme_toggle, 0.5),
    (bouncing_balls, 0.9), (particles, 0.8), (pong, 0.6), (snake, 0.8), (click_target, 0.7),
]
BY_NAME = {f.__name__: f for f, _ in PATTERNS}

# ------------------------------------------------------------------ edits
#
# An edit changes exactly one recorded parameter, and its instruction names the new
# value, so "make it faster" only appears where it has one meaning (from normal).

BTN_EFFECT = {"grow": ["grow on hover", "scale up on hover"], "lift": ["lift up with a shadow on hover", "float up on hover"],
              "glow": ["glow on hover"], "darken": ["get darker on hover"], "outline": ["turn into an outline on hover"]}
CARD_EFFECT = {"lift": ["lift up on hover"], "tilt": ["tilt slightly on hover"], "grow": ["grow on hover"]}
SPIN_KIND = {"ring": "a spinning ring", "dots": "three pulsing dots", "bars": "stretching bars", "pulse": "a pulsing circle"}
NO_THEME = {"gradient_bg", "theme_toggle", "particles"}


def other(rng, options, cur):
    return rng.choice([o for o in options if o != cur])


def edit_color(rng, vals, key="color", who=None, avoid=()):
    new = other(rng, [c for c in COLORS if c not in avoid], vals[key])
    if who:
        text = rng.choice([f"make {who} {new}", f"change {who} to {new}", f"I want {who} to be {new}"])
    else:
        text = rng.choice([f"make it {new}", f"change the color to {new}", f"use {new} instead", f"can you make it {new}?",
                           f"switch the color to {new}", f"{new} please"])
    return text, {key: new}


def edit_speed(rng, vals, noun="it"):
    cur = vals["speed"]
    new = other(rng, ["slow", "normal", "fast"], cur)
    if cur == "normal":
        text = rng.choice([f"make {noun} {'faster' if new == 'fast' else 'slower'}", f"make {noun} {new}"])
    elif new == "normal":
        text = rng.choice([f"make {noun} normal speed", f"set {noun} to a normal speed"])
    else:
        text = f"make {noun} {new}"
    return text, {"speed": new}


def edits_for(rng, name, vals, dark):
    """All edits that apply to this page, each as (instruction, changed params, new dark)."""
    out = []
    if "color" in vals:
        out.append((*edit_color(rng, vals), dark))
    if name not in NO_THEME:
        if dark:
            out.append((rng.choice(["use a light background", "switch to a light theme", "make the background light"]), {}, False))
        else:
            out.append((rng.choice(["use a dark background", "switch to a dark theme", "make the background dark"]), {}, True))
    if name == "button_hover":
        new = other(rng, LABELS, vals["label"])
        out.append((rng.choice([f'change the text to "{new}"', f'make it say "{new}"', f'rename the button to "{new}"']), {"label": new}, dark))
        new = other(rng, list(BTN_EFFECT), vals["effect"])
        e = rng.choice(BTN_EFFECT[new])
        out.append((rng.choice([f"make it {e} instead", f"I want it to {e}", f"can it {e} instead?"]), {"effect": new}, dark))
        new = other(rng, ["rounded", "pill", "square"], vals["shape"])
        w = {"rounded": "rounded", "pill": "pill-shaped", "square": "square"}[new]
        out.append((rng.choice([f"make it {w}", f"make the button {w}"]), {"shape": new}, dark))
    if name == "card_hover":
        new = other(rng, list(CARD_EFFECT), vals["effect"])
        e = rng.choice(CARD_EFFECT[new])
        out.append((rng.choice([f"make it {e} instead", f"I want the card to {e}"]), {"effect": new}, dark))
    if name == "toggle":
        new = other(rng, TOGGLES, vals["label"])
        out.append((rng.choice([f'change the label to "{new}"', f'make it say "{new}"']), {"label": new}, dark))
    if name == "spinner":
        out.append((*edit_speed(rng, vals), dark))
        new = other(rng, list(SPIN_KIND), vals["kind"])
        out.append((rng.choice([f"make it {SPIN_KIND[new]} instead", f"use {SPIN_KIND[new]} instead"]), {"kind": new}, dark))
    if name == "progress":
        out.append((*edit_speed(rng, vals), dark))
        new = "square" if vals["shape"] == "rounded" else "rounded"
        out.append((rng.choice(["give it square corners", "make the ends square"] if new == "square" else ["make it rounded", "round the corners"]), {"shape": new}, dark))
    if name in ("text_fade", "gradient_bg"):
        new = other(rng, HEADINGS, vals["text"])
        out.append((rng.choice([f'change the heading to "{new}"', f'make it say "{new}"', f'change the text to "{new}"']), {"text": new}, dark))
    if name == "gradient_bg":
        out.append((*edit_speed(rng, vals, "the gradient"), dark))
    if name == "text_fade":
        new = other(rng, ["bottom", "left", "top", "fade"], vals["direction"])
        how = {"bottom": "slide up from below", "left": "slide in from the left", "top": "drop down from the top", "fade": "only fade in, without moving"}[new]
        out.append((f"make it {how} instead", {"direction": new}, dark))
    if name == "counter":
        out.append(("remove the minus button" if vals["minus"] else "add a minus button", {"minus": not vals["minus"]}, dark))
    if name == "click_target":
        new = other(rng, ["small", "normal", "big"], vals["size"])
        out.append((f"make the circle {'normal-sized' if new == 'normal' else new}", {"size": new}, dark))
    if name == "bouncing_balls":
        out.append((*edit_speed(rng, vals), dark))
        if not vals["multi"]:
            out.append((rng.choice(["make it 6 balls", "add more balls, 6 in total"]), {"multi": True, "rainbow": False}, dark))
        elif not vals["rainbow"]:
            out.append(("make the balls rainbow-colored", {"rainbow": True}, dark))
    if name == "snake":
        out.append((*edit_color(rng, vals, "c1", "the snake", avoid=(vals["c2"],)), dark))
        out.append((*edit_color(rng, vals, "c2", "the food", avoid=(vals["c1"],)), dark))
        out.append((*edit_speed(rng, vals, "the snake"), dark))
    if name == "pong":
        out.append((*edit_color(rng, vals, "c1", "my paddle", avoid=(vals["c2"],)), dark))
        out.append((*edit_color(rng, vals, "c2", "the computer's paddle", avoid=(vals["c1"],)), dark))
    return out


def make(fn, rng, dark, given=None):
    P = Params(given)
    desc, html, checks = fn(rng, dark, P)
    return desc, html, checks, P.vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--singles", type=int, default=6500)
    ap.add_argument("--edits", type=int, default=4500)
    ap.add_argument("--switches", type=int, default=1200, help="second request is a new page, not an edit")
    ap.add_argument("--out", type=Path, default=Path("."))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    funcs, weights = zip(*PATTERNS)
    pages, page_ids, convs = [], {}, []

    def add_page(name, html, checks):
        if html not in page_ids:
            page_ids[html] = len(pages)
            pages.append({"id": len(pages), "pattern": name, "response": html, "checks": checks})
        return page_ids[html]

    def fresh():
        fn = rng.choices(funcs, weights)[0]
        dark = rng.random() < 0.3
        desc, html, checks, vals = make(fn, rng, dark)
        return fn, dark, desc, add_page(fn.__name__, html, checks), vals

    seen = set()
    while sum(1 for c in convs if len(c["turns"]) == 1) < a.singles:
        fn, dark, desc, pid, _ = fresh()
        if (desc, pid) in seen:
            continue
        seen.add((desc, pid))
        convs.append({"kind": "single", "pattern": fn.__name__, "turns": [{"prompt": desc, "page": pid}]})
    n = 0
    while n < a.edits:
        fn, dark, desc, pid, vals = fresh()
        options = edits_for(rng, fn.__name__, vals, dark)
        if not options:
            continue
        text, change, dark2 = rng.choice(options)
        _, html2, checks2, _ = make(fn, random.Random(0), dark2, {**vals, **change})
        pid2 = add_page(fn.__name__, html2, checks2)
        if pid2 == pid:
            continue
        if rng.random() < 0.3:
            text = text[0].upper() + text[1:]
        if rng.random() < 0.4 and not text.endswith("?"):
            text += "."
        convs.append({"kind": "edit", "pattern": fn.__name__, "turns": [{"prompt": desc, "page": pid}, {"prompt": text, "page": pid2}]})
        n += 1
    for _ in range(a.switches):
        fn, dark, desc, pid, _ = fresh()
        fn2, dark2, desc2, pid2, _ = fresh()
        convs.append({"kind": "switch", "pattern": fn2.__name__, "turns": [{"prompt": desc, "page": pid}, {"prompt": desc2, "page": pid2}]})

    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "pages.jsonl").open("w", encoding="utf-8") as f:
        for p in pages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with (a.out / "convs.jsonl").open("w", encoding="utf-8") as f:
        for i, c in enumerate(convs):
            f.write(json.dumps({"id": i, **c}, ensure_ascii=False) + "\n")
    kinds = {}
    for c in convs:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"{len(pages)} unique pages, {len(convs)} conversations {kinds}")


if __name__ == "__main__":
    main()
