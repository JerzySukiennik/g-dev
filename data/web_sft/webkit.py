"""Shared pieces for the web-page SFT generator: palette, word lists, page shell,
description helpers and the Params recorder."""


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
