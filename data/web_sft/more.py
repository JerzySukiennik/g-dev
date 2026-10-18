"""More page patterns for G-Dev's SFT data: forms, widgets, number-driven animations,
cursor effects, composed landing pages and small games.

Same contract as gen.py: every parameter that changes the page goes through P and is
stated in the description. Decorative words people add ("nice", "simple", "modern")
appear in descriptions but never change the page, so the model learns to ignore them.
"""

from webkit import COLORS, page, surface, pick_color  # noqa: F401


def an(word):
    return ("an " if word[0] in "aeiou" else "a ") + word

FLUFF = ["", "", "", "nice ", "simple ", "clean ", "modern ", "cool ", "pretty ", "small "]
LEADS2 = ["Make", "Make me", "Create", "Build", "Can you make", "I want", "I'd like", "Give me", "Please make", "Generate",
          "Write", "Design", "Could you build", "Code"]
NUMW = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
        10: "ten", 11: "eleven", 12: "twelve", 15: "fifteen", 20: "twenty"}


def num(rng, n):
    return NUMW[n] if n in NUMW and rng.random() < 0.5 else str(n)


def color_phrase(rng, c):
    return rng.choice([f"in {c}", f"with a {c} theme", f"that will have a {c} theme", f"using {c}", f"with {c} accents", f"{c} themed"])


def done(rng, core, dark):
    core = core.strip()
    if dark:
        core += rng.choice([" on a dark background", ", dark theme", " with a dark background", " in dark mode"])
    text = f"{rng.choice(LEADS2)} {core}"
    if rng.random() < 0.5:
        text += "."
    return text


def card_css(dark, width=320):
    return f""".card {{
  width: {width}px;
  padding: 28px;
  border-radius: 16px;
  background: {surface(dark)};
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
}}
.card h2 {{
  margin: 0 0 18px;
  font-size: 22px;
}}"""


def btn_css(hx, tx, sel=".btn", full=False):
    return f"""{sel} {{
  {"width: 100%;" if full else "padding: 0 22px;"}
  height: 44px;
  border: none;
  border-radius: 10px;
  background: {hx};
  color: {tx};
  font-size: 16px;
  cursor: pointer;
}}
{sel}:hover {{
  filter: brightness(1.1);
}}"""


# ------------------------------------------------------------------ forms

FORMS = {
    "login": ("Welcome back", [("email", "Email", "email"), ("password", "Password", "password")], ["Sign in", "Log in"],
              ["a login form", "a sign in form", "a login page"]),
    "signup": ("Create your account", [("name", "Name", "text"), ("email", "Email", "email"), ("password", "Password", "password")],
               ["Sign up", "Create account", "Register"], ["a register form", "a sign up form", "a registration form", "a signup page"]),
    "contact": ("Contact us", [("name", "Name", "text"), ("email", "Email", "email"), ("message", "Message", "textarea")],
                ["Send", "Send message"], ["a contact form", "a contact us form"]),
    "newsletter": ("Join our newsletter", [("email", "Email", "email")], ["Subscribe", "Join"], ["a newsletter signup form", "a newsletter form"]),
}
THANKS = {"login": "Signed in!", "signup": "Account created!", "contact": "Thanks, we will reply soon!", "newsletter": "You are subscribed!"}


def form(rng, dark, P):
    kind = P("kind", lambda: rng.choice(list(FORMS)))
    title, fields, buttons, names = FORMS[kind]
    label = P("label", lambda: rng.choice(buttons))
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    inp = "#111827" if dark else "#f9fafb"
    line = "#374151" if dark else "#d1d5db"
    css = card_css(dark) + f"""
label {{
  display: block;
  margin-bottom: 14px;
  font-size: 14px;
}}
input, textarea {{
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 10px 12px;
  border: 1px solid {line};
  border-radius: 8px;
  background: {inp};
  color: inherit;
  font: inherit;
  box-sizing: border-box;
}}
input:focus, textarea:focus {{
  outline: 2px solid {hx};
  border-color: transparent;
}}
""" + btn_css(hx, tx, ".btn", full=True) + f"""
#done {{
  margin: 14px 0 0;
  color: {hx};
  text-align: center;
}}"""
    rows = []
    for fid, flabel, ftype in fields:
        if ftype == "textarea":
            rows.append(f'  <label>{flabel}<textarea id="{fid}" rows="4"></textarea></label>')
        else:
            rows.append(f'  <label>{flabel}<input id="{fid}" type="{ftype}"></label>')
    body = f'<form class="card" id="form">\n  <h2>{title}</h2>\n' + "\n".join(rows) + f'\n  <button class="btn" type="submit">{label}</button>\n  <p id="done"></p>\n</form>'
    script = f"""document.getElementById("form").addEventListener("submit", (e) => {{
  e.preventDefault();
  document.getElementById("done").textContent = "{THANKS[kind]}";
}});"""
    fl = [f[1].lower() + (" box" if f[2] == "textarea" else " field") for f in fields]
    flist = fl[0] if len(fl) == 1 else ", ".join(fl[:-1]) + " and " + fl[-1]
    art = "an" if flist[0] in "aeiou" else "a"
    rest = rng.choice(names).split(" ", 1)[1]
    fluff = rng.choice(FLUFF)
    lead = ("an " if (fluff or rest)[0] in "aeiou" else "a ") + fluff + rest
    core = rng.choice([
        f"{lead} with {art} {flist} and a \"{label}\" button, {color_phrase(rng, cname)}",
        f"{lead} {color_phrase(rng, cname)}, with {art} {flist} and a \"{label}\" button",
    ])
    return done(rng, core, dark), page(title, css, body, dark, script), {"click": ".btn", "wait": 150}


# ------------------------------------------------------------------ widgets

TODO_TITLES = ["My tasks", "To do", "Shopping list", "Today", "Homework"]
TODO_ITEMS = ["Buy milk", "Walk the dog", "Finish homework", "Call grandma", "Water the plants", "Practice piano"]


def todo(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    title = P("title", lambda: rng.choice(TODO_TITLES))
    n = P("items", lambda: rng.choice([0, 2, 3]))
    items = TODO_ITEMS[:n]
    line = "#374151" if dark else "#e5e7eb"
    css = card_css(dark, 340) + f"""
.row {{
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}}
#new {{
  flex: 1;
  padding: 10px 12px;
  border: 1px solid {line};
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
}}
""" + btn_css(hx, tx, "#add") + f"""
ul {{
  margin: 0;
  padding: 0;
  list-style: none;
}}
li {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid {line};
  cursor: pointer;
}}
li.done span {{
  text-decoration: line-through;
  opacity: 0.5;
}}
li button {{
  border: none;
  background: none;
  color: {hx};
  font-size: 18px;
  cursor: pointer;
}}"""
    body = f'<div class="card">\n  <h2>{title}</h2>\n  <div class="row">\n    <input id="new" placeholder="Add a task">\n    <button id="add">Add</button>\n  </div>\n  <ul id="list"></ul>\n</div>'
    script = f"""const list = document.getElementById("list");
const input = document.getElementById("new");
function addItem(text) {{
  const li = document.createElement("li");
  li.innerHTML = "<span></span><button>&times;</button>";
  li.querySelector("span").textContent = text;
  li.addEventListener("click", () => li.classList.toggle("done"));
  li.querySelector("button").addEventListener("click", (e) => {{
    e.stopPropagation();
    li.remove();
  }});
  list.appendChild(li);
}}
document.getElementById("add").addEventListener("click", () => {{
  if (input.value.trim()) addItem(input.value.trim());
  input.value = "";
}});
input.addEventListener("keydown", (e) => {{
  if (e.key === "Enter") document.getElementById("add").click();
}});
{json_list(items)}.forEach(addItem);"""
    start = "empty" if not n else "starting with " + " and ".join(f'"{x}"' for x in items)
    core = rng.choice([f"{rng.choice(FLUFF)}to-do list app titled \"{title}\" where I can add tasks, cross them off by clicking and delete them, {color_phrase(rng, cname)}, {start}",
                       f"{rng.choice(FLUFF)}todo list called \"{title}\" {color_phrase(rng, cname)}: add tasks with a button or Enter, click to mark done, x to delete, {start}"])
    return done(rng, "a " + core, dark), page(title, css, body, dark, script), {"fill": [["#new", "Test task"]], "click": "#add", "wait": 120}


def json_list(items):
    return "[" + ", ".join(f'"{x}"' for x in items) + "]"


def clock(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    h24 = P("h24", lambda: rng.random() < 0.5)
    date = P("date", lambda: rng.random() < 0.5)
    css = f""".clock {{
  text-align: center;
}}
#time {{
  font-size: 72px;
  font-weight: 700;
  color: {hx};
  font-variant-numeric: tabular-nums;
}}
#date {{
  margin-top: 6px;
  font-size: 18px;
  opacity: 0.7;
}}"""
    body = '<div class="clock">\n  <div id="time"></div>' + ('\n  <div id="date"></div>' if date else "") + "\n</div>"
    opts = '{ hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: ' + ("false" if h24 else "true") + " }"
    script = f"""function tick() {{
  const now = new Date();
  document.getElementById("time").textContent = now.toLocaleTimeString("en-US", {opts});""" + ("""
  document.getElementById("date").textContent = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });""" if date else "") + """
}
tick();
setInterval(tick, 1000);"""
    core = f"a {rng.choice(FLUFF)}digital clock {color_phrase(rng, cname)} that shows the current time with seconds in {'24-hour' if h24 else '12-hour'} format{' and the date below it' if date else ''}, updating every second"
    return done(rng, core, dark), page("Clock", css, body, dark, script), {"animated": True, "animWait": 1100}


def stopwatch(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    laps = P("laps", lambda: rng.random() < 0.4)
    css = f""".watch {{
  text-align: center;
}}
#display {{
  margin-bottom: 18px;
  font-size: 64px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}}
.btn {{
  margin: 0 4px;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: {hx};
  color: {tx};
  font-size: 16px;
  cursor: pointer;
}}
#laps {{
  margin-top: 14px;
  padding: 0;
  list-style: none;
  opacity: 0.8;
}}"""
    lbtn = '\n    <button class="btn" id="lap">Lap</button>' if laps else ""
    body = f'<div class="watch">\n  <div id="display">00:00.00</div>\n  <div>\n    <button class="btn" id="start">Start</button>\n    <button class="btn" id="stop">Stop</button>{lbtn}\n    <button class="btn" id="reset">Reset</button>\n  </div>' + ('\n  <ul id="laps"></ul>' if laps else "") + "\n</div>"
    script = """let elapsed = 0;
let started = 0;
let timer = null;
const display = document.getElementById("display");
function format(ms) {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const c = Math.floor((ms % 1000) / 10);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0") + "." + String(c).padStart(2, "0");
}
function now() {
  return elapsed + (timer ? Date.now() - started : 0);
}
document.getElementById("start").addEventListener("click", () => {
  if (timer) return;
  started = Date.now();
  timer = setInterval(() => (display.textContent = format(now())), 30);
});
document.getElementById("stop").addEventListener("click", () => {
  if (!timer) return;
  elapsed = now();
  clearInterval(timer);
  timer = null;
});
document.getElementById("reset").addEventListener("click", () => {
  clearInterval(timer);
  timer = null;
  elapsed = 0;
  display.textContent = format(0);""" + ("""
  document.getElementById("laps").innerHTML = "";""" if laps else "") + """
});""" + ("""
document.getElementById("lap").addEventListener("click", () => {
  const li = document.createElement("li");
  li.textContent = format(now());
  document.getElementById("laps").appendChild(li);
});""" if laps else "")
    core = f"a {rng.choice(FLUFF)}stopwatch with Start, Stop{', Lap' if laps else ''} and Reset buttons {color_phrase(rng, cname)}"
    return done(rng, core, dark), page("Stopwatch", css, body, dark, script), {"click": "#start", "wait": 300}


def calculator(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    key = "#374151" if dark else "#e5e7eb"
    css = f""".calc {{
  width: 280px;
  padding: 18px;
  border-radius: 18px;
  background: {surface(dark)};
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
}}
#screen {{
  height: 64px;
  margin-bottom: 14px;
  padding: 0 12px;
  border-radius: 10px;
  background: {"#111827" if dark else "#f3f4f6"};
  font-size: 32px;
  line-height: 64px;
  text-align: right;
  overflow: hidden;
}}
.keys {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}}
.keys button {{
  height: 52px;
  border: none;
  border-radius: 10px;
  background: {key};
  color: inherit;
  font-size: 20px;
  cursor: pointer;
}}
.keys .op {{
  background: {hx};
  color: {tx};
}}"""
    keys = ["C", "(", ")", "/", "7", "8", "9", "*", "4", "5", "6", "-", "1", "2", "3", "+", "0", ".", "⌫", "="]
    btns = "\n".join(f'    <button{" class=\"op\"" if k in "/*-+=" else ""}>{k}</button>' for k in keys)
    body = f'<div class="calc">\n  <div id="screen">0</div>\n  <div class="keys">\n{btns}\n  </div>\n</div>'
    script = """const screen = document.getElementById("screen");
let expr = "";
document.querySelectorAll(".keys button").forEach((b) => {
  b.addEventListener("click", () => {
    const k = b.textContent;
    if (k === "C") expr = "";
    else if (k === "⌫") expr = expr.slice(0, -1);
    else if (k === "=") {
      try {
        expr = String(Function("return (" + expr + ")")());
      } catch {
        expr = "Error";
      }
    } else {
      if (expr === "Error") expr = "";
      expr += k;
    }
    screen.textContent = expr || "0";
  });
});"""
    core = f"a {rng.choice(FLUFF)}calculator {color_phrase(rng, cname)} with buttons for digits, + - * /, brackets, clear and backspace"
    return done(rng, core, dark), page("Calculator", css, body, dark, script), {"click": ".keys button:nth-child(5)", "wait": 100}


def dice(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    n = P("count", lambda: rng.choice([1, 2, 3]))
    css = f""".box {{
  text-align: center;
}}
.dice {{
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 20px;
}}
.die {{
  width: 80px;
  height: 80px;
  border-radius: 16px;
  background: {hx};
  color: {tx};
  font-size: 44px;
  font-weight: 700;
  line-height: 80px;
}}
.die.roll {{
  animation: shake 0.4s;
}}
@keyframes shake {{
  25% {{ transform: rotate(-15deg); }}
  75% {{ transform: rotate(15deg); }}
}}
""" + btn_css(hx, tx)
    dies = "\n".join('    <div class="die">1</div>' for _ in range(n))
    body = f'<div class="box">\n  <div class="dice">\n{dies}\n  </div>\n  <button class="btn" id="roll">Roll</button>\n</div>'
    script = """document.getElementById("roll").addEventListener("click", () => {
  document.querySelectorAll(".die").forEach((d) => {
    d.classList.remove("roll");
    void d.offsetWidth;
    d.classList.add("roll");
    d.textContent = 1 + Math.floor(Math.random() * 6);
  });
});"""
    what = "a die" if n == 1 else f"{num(rng, n)} dice"
    core = f"a {rng.choice(FLUFF)}dice roller with {what} {color_phrase(rng, cname)} and a Roll button that shakes {'it' if n == 1 else 'them'} and shows random numbers from 1 to 6"
    return done(rng, core, dark), page("Dice", css, body, dark, script), {"click": "#roll", "wait": 200}


def rating(rng, dark, P):
    cname = P("color", lambda: rng.choice(["yellow", "orange", "red", "pink", "purple"]))
    hx = COLORS[cname][0]
    n = P("count", lambda: rng.choice([5, 5, 10]))
    off = "#4b5563" if dark else "#d1d5db"
    css = f""".rating {{
  text-align: center;
}}
.stars {{
  font-size: 42px;
  cursor: pointer;
}}
.stars span {{
  color: {off};
  transition: color 0.15s;
}}
.stars span.on {{
  color: {hx};
}}
#text {{
  margin-top: 8px;
  opacity: 0.8;
}}"""
    stars = "".join(f'<span data-v="{i + 1}">&#9733;</span>' for i in range(n))
    body = f'<div class="rating">\n  <div class="stars">{stars}</div>\n  <div id="text">Click a star to rate</div>\n</div>'
    script = f"""const stars = document.querySelectorAll(".stars span");
function paint(v) {{
  stars.forEach((s) => s.classList.toggle("on", Number(s.dataset.v) <= v));
}}
let rated = 0;
stars.forEach((s) => {{
  s.addEventListener("mouseenter", () => paint(Number(s.dataset.v)));
  s.addEventListener("mouseleave", () => paint(rated));
  s.addEventListener("click", () => {{
    rated = Number(s.dataset.v);
    paint(rated);
    document.getElementById("text").textContent = "You rated " + rated + " out of {n}";
  }});
}});"""
    core = f"a {rng.choice(FLUFF)}star rating with {num(rng, n)} {cname} stars that light up on hover and show \"You rated X out of {n}\" when clicked"
    return done(rng, core, dark), page("Rating", css, body, dark, script), {"click": ".stars span:nth-child(3)", "wait": 150}


def slider(rng, dark, P):
    names = P("colors", lambda: rng.sample(list(COLORS), rng.choice([3, 4, 5])))
    auto = P("auto", lambda: rng.random() < 0.5)
    n = len(names)
    css = """.slider {
  position: relative;
  width: 420px;
  height: 240px;
  overflow: hidden;
  border-radius: 16px;
}
.track {
  display: flex;
  height: 100%;
  transition: transform 0.5s ease;
}
.slide {
  flex: 0 0 100%;
  display: grid;
  place-items: center;
  color: #ffffff;
  font-size: 32px;
  font-weight: 700;
}
.nav {
  position: absolute;
  top: 50%;
  width: 40px;
  height: 40px;
  margin-top: -20px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  color: #ffffff;
  font-size: 20px;
  cursor: pointer;
}
#prev {
  left: 10px;
}
#next {
  right: 10px;
}
.dots {
  position: absolute;
  bottom: 12px;
  width: 100%;
  text-align: center;
}
.dots span {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin: 0 4px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.5);
}
.dots span.on {
  background: #ffffff;
}"""
    slides = "\n".join(f'    <div class="slide" style="background: {COLORS[c][0]}">Slide {i + 1}</div>' for i, c in enumerate(names))
    body = f'<div class="slider">\n  <div class="track" id="track">\n{slides}\n  </div>\n  <button class="nav" id="prev">&lsaquo;</button>\n  <button class="nav" id="next">&rsaquo;</button>\n  <div class="dots" id="dots"></div>\n</div>'
    script = f"""const track = document.getElementById("track");
const dots = document.getElementById("dots");
const count = {n};
let index = 0;
for (let i = 0; i < count; i++) dots.appendChild(document.createElement("span"));
function go(i) {{
  index = (i + count) % count;
  track.style.transform = "translateX(" + -index * 100 + "%)";
  dots.querySelectorAll("span").forEach((d, k) => d.classList.toggle("on", k === index));
}}
document.getElementById("prev").addEventListener("click", () => go(index - 1));
document.getElementById("next").addEventListener("click", () => go(index + 1));
go(0);""" + ("\nsetInterval(() => go(index + 1), 3000);" if auto else "")
    cl = ", ".join(names[:-1]) + " and " + names[-1]
    core = f"an {rng.choice(['', 'image ', ''])}slider with {num(rng, n)} slides colored {cl}, previous and next arrows and dots{', that also changes slides automatically every 3 seconds' if auto else ''}"
    core = core.replace("an image", "an image").replace("an slider", "a slider")
    return done(rng, core, False), page("Slider", css, body, False, script), {"click": "#next", "wait": 650}


def tooltip(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    label = P("label", lambda: rng.choice(["Hover me", "Info", "Help", "Details"]))
    tip = P("tip", lambda: rng.choice(["Hello!", "This is a tooltip", "More info here", "Saved automatically"]))
    side = P("side", lambda: rng.choice(["top", "bottom"]))
    pos = "bottom: 120%;" if side == "top" else "top: 120%;"
    css = f""".wrap {{
  position: relative;
  display: inline-block;
}}
""" + btn_css(hx, tx) + f"""
.tip {{
  position: absolute;
  left: 50%;
  {pos}
  padding: 8px 12px;
  border-radius: 8px;
  background: #111827;
  color: #ffffff;
  font-size: 14px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transform: translateX(-50%) translateY({"6px" if side == "top" else "-6px"});
  transition: opacity 0.2s, transform 0.2s;
}}
.wrap:hover .tip {{
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}}"""
    body = f'<div class="wrap">\n  <button class="btn">{label}</button>\n  <div class="tip">{tip}</div>\n</div>'
    core = f"{an(cname)} button \"{label}\" with a tooltip saying \"{tip}\" that fades in {'above' if side == 'top' else 'below'} it on hover"
    return done(rng, core, dark), page("Tooltip", css, body, dark), {"hover": ".btn", "wait": 300}


def dropdown(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    items = P("items", lambda: rng.choice([["Profile", "Settings", "Log out"], ["New file", "Open", "Save", "Export"], ["Small", "Medium", "Large"]]))
    label = P("label", lambda: rng.choice(["Menu", "Options", "Account"]))
    css = """.dd {
  position: relative;
  display: inline-block;
}
""" + btn_css(hx, tx) + f"""
.menu {{
  position: absolute;
  top: 110%;
  left: 0;
  min-width: 180px;
  margin: 0;
  padding: 6px;
  border-radius: 10px;
  background: {surface(dark)};
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  list-style: none;
  display: none;
}}
.menu.open {{
  display: block;
}}
.menu li {{
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
}}
.menu li:hover {{
  background: {hx};
  color: {tx};
}}"""
    lis = "\n".join(f"    <li>{i}</li>" for i in items)
    body = f'<div class="dd">\n  <button class="btn" id="toggle">{label} &#9662;</button>\n  <ul class="menu" id="menu">\n{lis}\n  </ul>\n</div>'
    script = """const menu = document.getElementById("menu");
document.getElementById("toggle").addEventListener("click", (e) => {
  e.stopPropagation();
  menu.classList.toggle("open");
});
document.addEventListener("click", () => menu.classList.remove("open"));"""
    il = ", ".join(items[:-1]) + " and " + items[-1]
    core = f"{an(cname)} \"{label}\" dropdown button that opens a menu with {il} when clicked and closes when clicking outside"
    return done(rng, core, dark), page("Dropdown", css, body, dark, script), {"click": "#toggle", "wait": 100}


WIDGETS = [(form, 1.4), (todo, 0.9), (clock, 0.6), (stopwatch, 0.6), (calculator, 0.6), (dice, 0.6), (rating, 0.6),
           (slider, 0.6), (tooltip, 0.6), (dropdown, 0.6)]


# ------------------------------------------------------------- animations

def dots_loader(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    n = P("count", lambda: rng.choice([3, 4, 5, 6, 7, 8, 9, 10, 12]))
    layout = P("layout", lambda: rng.choice(["row", "row", "circle"]))
    speed = P("speed", lambda: rng.choice(["slow", "normal", "normal", "fast"]))
    dur = {"slow": 1.8, "normal": 1.2, "fast": 0.6}[speed]
    step = round(dur / n, 3)
    if layout == "row":
        css = f""".loader {{
  display: flex;
  gap: 10px;
}}
.loader span {{
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: {hx};
  animation: pulse {dur}s ease-in-out infinite;
}}
@keyframes pulse {{
  0%, 80%, 100% {{
    transform: scale(0.4);
    opacity: 0.3;
  }}
  40% {{
    transform: scale(1);
    opacity: 1;
  }}
}}"""
    else:
        css = f""".loader {{
  position: relative;
  width: 90px;
  height: 90px;
}}
.loader span {{
  position: absolute;
  left: 38px;
  top: 38px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: {hx};
  animation: fade {dur}s linear infinite;
}}
@keyframes fade {{
  0% {{
    opacity: 1;
  }}
  100% {{
    opacity: 0.15;
  }}
}}"""
    spans = "\n".join(f'  <span style="animation-delay: {round(i * step, 3)}s{"" if layout == "row" else f"; transform: rotate({round(360 * i / n, 1)}deg) translateY(-36px)"}"></span>' for i in range(n))
    body = f'<div class="loader">\n{spans}\n</div>'
    shape = "in a row" if layout == "row" else "arranged in a circle"
    core = f"a {rng.choice(FLUFF)}loader made of {num(rng, n)} {cname} dots {shape} that pulse one after another"
    if speed != "normal":
        core += f", {speed}"
    return done(rng, core, dark), page("Loader", css, body, dark), {"animated": True}


def cursor_follow(rng, dark, P):
    n = P("count", lambda: rng.choice([5, 8, 10, 12, 15, 20]))
    rainbow = P("rainbow", lambda: rng.random() < 0.4)
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    ease = P("ease", lambda: rng.choice(["smooth", "snappy"]))
    k = 0.15 if ease == "smooth" else 0.4
    fill = '`hsl(${i * 360 / ' + str(n) + '}, 85%, 60%)`' if rainbow else f'"{hx}"'
    css = """.dot {
  position: fixed;
  left: 0;
  top: 0;
  border-radius: 50%;
  pointer-events: none;
}
p {
  opacity: 0.6;
}"""
    body = "<p>Move your mouse</p>"
    script = f"""const dots = [];
const count = {n};
let mx = innerWidth / 2;
let my = innerHeight / 2;
for (let i = 0; i < count; i++) {{
  const d = document.createElement("div");
  d.className = "dot";
  const size = 22 - i * (14 / count);
  d.style.width = d.style.height = size + "px";
  d.style.background = {fill};
  d.style.opacity = 1 - i / (count + 2);
  document.body.appendChild(d);
  dots.push({{ el: d, x: mx, y: my, size }});
}}
addEventListener("mousemove", (e) => {{
  mx = e.clientX;
  my = e.clientY;
}});
function loop() {{
  let x = mx;
  let y = my;
  for (const d of dots) {{
    d.x += (x - d.x) * {k};
    d.y += (y - d.y) * {k};
    d.el.style.transform = `translate(${{d.x - d.size / 2}}px, ${{d.y - d.size / 2}}px)`;
    x = d.x;
    y = d.y;
  }}
  requestAnimationFrame(loop);
}}
loop();"""
    col = "rainbow-colored" if rainbow else cname
    core = rng.choice([f"{num(rng, n)} {col} dots that follow the mouse cursor in a {ease} trail",
                       f"a {ease} trail of {num(rng, n)} {col} dots that follows the cursor",
                       f"a cursor trail effect: {num(rng, n)} {col} dots that go to the cursor, {ease}"])
    return done(rng, core, dark), page("Cursor trail", css, body, dark, script), {"mouse": [[100, 100], [400, 300]], "wait": 300}


TYPE_TEXTS = ["Hello, world!", "Welcome to my website", "Building the future", "Code. Create. Repeat.", "Have a great day",
              "Rocket launch in 3, 2, 1", "Learning something new"]


def typewriter(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    text = P("text", lambda: rng.choice(TYPE_TEXTS))
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    loop = P("loop", lambda: rng.random() < 0.5)
    ms = {"slow": 160, "normal": 90, "fast": 40}[speed]
    css = f"""h1 {{
  margin: 0;
  font-size: 44px;
  color: {hx};
}}
.caret {{
  display: inline-block;
  width: 3px;
  height: 1em;
  margin-left: 4px;
  background: {hx};
  vertical-align: -0.1em;
  animation: blink 0.8s step-end infinite;
}}
@keyframes blink {{
  50% {{
    opacity: 0;
  }}
}}"""
    body = '<h1><span id="text"></span><span class="caret"></span></h1>'
    script = f"""const full = {json_list([text])[1:-1]};
const el = document.getElementById("text");
let i = 0;
let deleting = false;
function step() {{
  el.textContent = full.slice(0, i);
  if (!deleting && i < full.length) i++;""" + (f"""
  else if (!deleting) {{
    deleting = true;
    return setTimeout(step, 1200);
  }} else if (i > 0) i--;
  else deleting = false;""" if loop else "") + f"""
  setTimeout(step, deleting ? {ms // 2} : {ms});
}}
step();"""
    core = f"a {rng.choice(FLUFF)}typewriter effect that types \"{text}\" letter by letter in {cname} with a blinking cursor{', then deletes it and starts again' if loop else ''}"
    if speed != "normal":
        core += f", {speed}"
    return done(rng, core, dark), page("Typewriter", css, body, dark, script), {"animated": True}


def wave_text(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    text = P("text", lambda: rng.choice(["WELCOME", "LOADING", "HELLO", "G-DEV", "PLAY", "SUMMER"]))
    css = f"""h1 {{
  margin: 0;
  font-size: 56px;
  color: {hx};
  letter-spacing: 4px;
}}
h1 span {{
  display: inline-block;
  animation: wave 1.2s ease-in-out infinite;
}}
@keyframes wave {{
  0%, 100% {{
    transform: translateY(0);
  }}
  30% {{
    transform: translateY(-18px);
  }}
}}"""
    spans = "".join(f'<span style="animation-delay: {round(i * 0.1, 1)}s">{c}</span>' for i, c in enumerate(text))
    body = f"<h1>{spans}</h1>"
    core = f"the word \"{text}\" in big {cname} letters that jump one after another in a wave"
    return done(rng, core, dark), page("Wave", css, body, dark), {"animated": True}


def confetti(rng, dark, P):
    n = P("count", lambda: rng.choice([40, 80, 150]))
    label = P("label", lambda: rng.choice(["Celebrate", "Click me", "Party!", "Surprise"]))
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    css = btn_css(hx, tx) + """
canvas {
  position: fixed;
  inset: 0;
  pointer-events: none;
}"""
    body = f'<button class="btn" id="go">{label}</button>\n<canvas id="c"></canvas>'
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
canvas.width = innerWidth;
canvas.height = innerHeight;
let bits = [];
document.getElementById("go").addEventListener("click", (e) => {{
  for (let i = 0; i < {n}; i++) {{
    bits.push({{
      x: e.clientX,
      y: e.clientY,
      vx: (Math.random() - 0.5) * 12,
      vy: -Math.random() * 12 - 4,
      s: 4 + Math.random() * 6,
      c: `hsl(${{Math.random() * 360}}, 90%, 60%)`,
      r: Math.random() * 6,
    }});
  }}
}});
function loop() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const b of bits) {{
    b.vy += 0.35;
    b.x += b.vx;
    b.y += b.vy;
    b.r += 0.1;
    ctx.save();
    ctx.translate(b.x, b.y);
    ctx.rotate(b.r);
    ctx.fillStyle = b.c;
    ctx.fillRect(-b.s / 2, -b.s / 2, b.s, b.s * 0.6);
    ctx.restore();
  }}
  bits = bits.filter((b) => b.y < canvas.height + 20);
  requestAnimationFrame(loop);
}}
loop();"""
    amount = {40: "a little", 80: "some", 150: "lots of"}[n]
    core = f"{an(cname)} \"{label}\" button that shoots {amount} colorful confetti from where you click"
    return done(rng, core, dark), page("Confetti", css, body, dark, script), {"click": "#go", "wait": 120}


def balls(rng, dark, P):
    n = P("count", lambda: rng.choice([1, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]))
    rainbow = P("rainbow", lambda: n > 1 and rng.random() < 0.5)
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    gravity = P("gravity", lambda: rng.random() < 0.3)
    v = {"slow": 1.5, "normal": 3, "fast": 6}[speed]
    fill = f'`hsl(${{i * {round(360 / n, 1)}}}, 80%, 55%)`' if rainbow else f'"{hx}"'
    grav = "\n    b.vy += 0.25;" if gravity else ""
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const balls = [];
for (let i = 0; i < {n}; i++) {{
  balls.push({{
    x: 40 + Math.random() * 320,
    y: 40 + Math.random() * 220,
    vx: ({v} + Math.random()) * (Math.random() < 0.5 ? -1 : 1),
    vy: ({v} + Math.random()) * (Math.random() < 0.5 ? -1 : 1),
    r: {16 if n < 8 else 10},
    color: {fill},
  }});
}}
function loop() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const b of balls) {{{grav}
    b.x += b.vx;
    b.y += b.vy;
    if (b.x < b.r || b.x > canvas.width - b.r) b.vx *= -1;
    if (b.y < b.r || b.y > canvas.height - b.r) {{
      b.vy *= -1;
      b.y = Math.max(b.r, Math.min(canvas.height - b.r, b.y));
    }}
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
    what = f"{an(cname)} ball" if n == 1 else f"{num(rng, n)} {'rainbow-colored' if rainbow else cname} balls"
    core = f"{what} bouncing around inside a canvas"
    if gravity:
        core += " with gravity"
    if speed != "normal":
        core += f", {speed}"
    return done(rng, core, dark), page("Bouncing balls", css, body, dark, script), {"animated": True, "delay": 50}


ANIMATIONS = [(dots_loader, 1.0), (cursor_follow, 0.8), (typewriter, 0.6), (wave_text, 0.5), (confetti, 0.6), (balls, 1.0)]


# ---------------------------------------------------------- landing pages

TOPICS = {
    "bakery": ("Sunny Bakery", "Fresh bread every morning", "Handmade pastries baked daily in the heart of town.",
               [("Fresh daily", "Everything is baked before sunrise."), ("Local flour", "Grain from farms nearby."),
                ("Cakes to order", "Birthday cakes on request."), ("Free coffee", "With every breakfast set.")],
               ("Anna", "The best croissants I have ever had.")),
    "coffee shop": ("Bean There", "Coffee worth waking up for", "Small batch roasts and a quiet place to work.",
                    [("Single origin", "Beans from one farm at a time."), ("Fast wifi", "Bring your laptop and stay."),
                     ("Oat milk", "Every drink, no extra charge."), ("Open late", "Until ten every evening.")],
                    ("Tom", "My favourite place to study.")),
    "gym": ("Iron Hall", "Get stronger every week", "Coaching, classes and open gym seven days a week.",
            [("Personal plans", "Training built around you."), ("Group classes", "Twenty classes every week."),
             ("Open 24/7", "Train whenever it suits you."), ("Free trial", "Your first week is on us.")],
            ("Marta", "I lifted my first 100 kilos here.")),
    "rocket club": ("Sky Rockets", "Build rockets that really fly", "A club for model rocket builders of every age.",
                    [("Launch days", "Every second Saturday."), ("Workshops", "Learn to build from scratch."),
                     ("Safe motors", "Certified motors only."), ("Team projects", "Build bigger rockets together.")],
                    ("Jurek", "My rocket went higher than the trees.")),
    "music school": ("Note by Note", "Learn the instrument you love", "Piano, guitar and drums lessons for all levels.",
                     [("Piano", "Classical and modern pieces."), ("Guitar", "Acoustic and electric."),
                      ("Drums", "Rhythm from day one."), ("Concerts", "Play on stage twice a year.")],
                     ("Ola", "I played my first concert after a year.")),
    "travel agency": ("Far Away", "Your next trip starts here", "Hand-picked trips to places worth the journey.",
                      [("Beach trips", "Sun, sand and clear water."), ("City breaks", "Weekends in great cities."),
                       ("Mountain hikes", "Guided trails and views."), ("Best prices", "We find the cheapest flights.")],
                      ("Piotr", "The trip of my life, perfectly planned.")),
    "task app": ("Taskly", "Get things done, calmly", "A simple app for your daily tasks and goals.",
                 [("Lists", "Organize tasks into lists."), ("Reminders", "Never miss a deadline."),
                  ("Sync", "On your phone and laptop."), ("Focus mode", "Hide everything but today.")],
                 ("Kasia", "Finally an app I actually use.")),
    "pizza place": ("Slice Club", "Pizza from a real stone oven", "Neapolitan pizza made with simple, fresh ingredients.",
                    [("Stone oven", "Baked at 450 degrees."), ("Fresh dough", "Rested for two days."),
                     ("Delivery", "Hot at your door in 30 minutes."), ("Vegan options", "Every pizza can be vegan.")],
                    ("Bartek", "Best pizza in the city, no question.")),
}
PLANS = [("Basic", "$9", ["1 user", "Email support"]), ("Pro", "$19", ["5 users", "Priority support"]),
         ("Team", "$49", ["Unlimited users", "Phone support"])]
CTAS = ["Get started", "Learn more", "Join now", "Book now", "Try it free", "Order now"]
SECTIONS = ["features", "pricing", "testimonial", "contact"]


def landing(rng, dark, P):
    topic = P("topic", lambda: rng.choice(list(TOPICS)))
    brand, title, sub, feats, (who, quote) = TOPICS[topic]
    cname = P("color", lambda: pick_color(rng)[0])
    hx, hd, tx = COLORS[cname]
    cta = P("cta", lambda: rng.choice(CTAS))
    nav = P("navbar", lambda: rng.random() < 0.7)
    foot = P("footer", lambda: rng.random() < 0.7)
    secs = P("sections", lambda: rng.sample(SECTIONS, rng.choice([1, 1, 2])))
    nf = P("features", lambda: rng.choice([2, 3, 3, 4]))
    np_ = P("plans", lambda: rng.choice([2, 3]))
    surf = surface(dark)
    line = "#374151" if dark else "#e5e7eb"
    css = f"""body {{
  display: block;
}}
.wrap {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
}}
section {{
  padding: 48px 0;
}}
h2 {{
  margin: 0 0 24px;
  font-size: 28px;
  text-align: center;
}}
.btn {{
  display: inline-block;
  padding: 12px 26px;
  border: none;
  border-radius: 10px;
  background: {hx};
  color: {tx};
  font-size: 16px;
  text-decoration: none;
  cursor: pointer;
}}
.btn:hover {{
  background: {hd};
}}
.hero {{
  padding: 80px 0;
  text-align: center;
}}
.hero h1 {{
  margin: 0 0 12px;
  font-size: 44px;
}}
.hero p {{
  margin: 0 auto 28px;
  max-width: 520px;
  font-size: 18px;
  opacity: 0.75;
}}"""
    parts = []
    if nav:
        css += f"""
nav {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
}}
.brand {{
  font-weight: 700;
  font-size: 20px;
  color: {hx};
}}
nav a {{
  margin-left: 20px;
  color: inherit;
  text-decoration: none;
}}"""
        links = "".join(f'<a href="#{s}">{s.capitalize()}</a>' for s in secs)
        parts.append(f'<nav class="wrap">\n  <span class="brand">{brand}</span>\n  <div>{links}</div>\n</nav>')
    parts.append(f'<header class="hero wrap">\n  <h1>{title}</h1>\n  <p>{sub}</p>\n  <a class="btn" href="#">{cta}</a>\n</header>')
    for s in secs:
        if s == "features":
            css += f"""
.grid {{
  display: grid;
  grid-template-columns: repeat({nf}, 1fr);
  gap: 18px;
}}
.feature {{
  padding: 22px;
  border-radius: 14px;
  background: {surf};
  border-top: 4px solid {hx};
}}
.feature h3 {{
  margin: 0 0 6px;
}}
.feature p {{
  margin: 0;
  opacity: 0.75;
}}"""
            cards = "\n".join(f'    <div class="feature">\n      <h3>{t}</h3>\n      <p>{d}</p>\n    </div>' for t, d in feats[:nf])
            parts.append(f'<section id="features" class="wrap">\n  <h2>Why {brand}</h2>\n  <div class="grid">\n{cards}\n  </div>\n</section>')
        elif s == "pricing":
            css += f"""
.plans {{
  display: grid;
  grid-template-columns: repeat({np_}, 1fr);
  gap: 18px;
}}
.plan {{
  padding: 26px;
  border-radius: 14px;
  background: {surf};
  border: 2px solid {line};
  text-align: center;
}}
.plan.best {{
  border-color: {hx};
}}
.price {{
  margin: 8px 0 14px;
  font-size: 34px;
  font-weight: 700;
}}
.plan ul {{
  margin: 0 0 18px;
  padding: 0;
  list-style: none;
  opacity: 0.8;
}}"""
            cards = "\n".join(f'    <div class="plan{" best" if i == 1 else ""}">\n      <h3>{n}</h3>\n      <div class="price">{p}</div>\n      <ul>' + "".join(f"<li>{x}</li>" for x in xs) + f'</ul>\n      <a class="btn" href="#">Choose</a>\n    </div>' for i, (n, p, xs) in enumerate(PLANS[:np_]))
            parts.append(f'<section id="pricing" class="wrap">\n  <h2>Pricing</h2>\n  <div class="plans">\n{cards}\n  </div>\n</section>')
        elif s == "testimonial":
            css += f"""
blockquote {{
  max-width: 560px;
  margin: 0 auto;
  padding: 26px 30px;
  border-left: 4px solid {hx};
  border-radius: 12px;
  background: {surf};
  font-size: 20px;
}}
cite {{
  display: block;
  margin-top: 10px;
  font-size: 15px;
  opacity: 0.7;
}}"""
            parts.append(f'<section id="testimonial" class="wrap">\n  <blockquote>"{quote}"<cite>{who}</cite></blockquote>\n</section>')
        elif s == "contact":
            css += f"""
form {{
  display: flex;
  gap: 10px;
  justify-content: center;
}}
form input {{
  width: 260px;
  padding: 12px;
  border: 1px solid {line};
  border-radius: 10px;
  background: {surf};
  color: inherit;
  font: inherit;
}}"""
            parts.append('<section id="contact" class="wrap">\n  <h2>Get in touch</h2>\n  <form onsubmit="event.preventDefault(); this.innerHTML = \'Thanks! We will write back soon.\'">\n    <input type="email" placeholder="Your email">\n    <button class="btn">Send</button>\n  </form>\n</section>')
    if foot:
        css += f"""
footer {{
  padding: 28px 0;
  border-top: 1px solid {line};
  text-align: center;
  opacity: 0.7;
}}"""
        parts.append(f"<footer>&copy; 2026 {brand}</footer>")
    desc_secs = []
    for s in secs:
        if s == "features":
            desc_secs.append(f"{num(rng, nf)} feature cards")
        elif s == "pricing":
            desc_secs.append(f"a pricing section with {num(rng, np_)} plans")
        elif s == "testimonial":
            desc_secs.append("a customer quote")
        else:
            desc_secs.append("a contact form with an email field")
    bits = (["a navbar"] if nav else []) + [f"a hero with {an(cname)} \"{cta}\" button"] + desc_secs + (["a footer"] if foot else [])
    what = ", ".join(bits[:-1]) + " and " + bits[-1]
    art = "an" if topic[0] in "aeiou" else "a"
    core = rng.choice([f"a {rng.choice(FLUFF)}landing page for {art} {topic} called \"{brand}\" with {what}",
                       f"a {rng.choice(FLUFF)}website for {art} {topic} named \"{brand}\": {what}"])
    return done(rng, core, dark), page(brand, css, "\n".join(parts), dark), {"hover": ".hero .btn", "wait": 250}


LANDINGS = [(landing, 2.5)]


# ------------------------------------------------------------------ games

def runner(rng, dark, P):
    c1 = P("c1", lambda: pick_color(rng)[0])
    c2 = P("c2", lambda: pick_color(rng, exclude=(c1,))[0])
    coins = P("coins", lambda: rng.random() < 0.6)
    speed = P("speed", lambda: rng.choice(["slow", "normal", "fast"]))
    v = {"slow": 3, "normal": 4.5, "fast": 6.5}[speed]
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
const lanes = [W / 6, W / 2, (W * 5) / 6];
let lane = 1;
let px = lanes[1];
let things = [];
let score = 0;
let best = 0;
let speed = {v};
let tick = 0;
document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowLeft" && lane > 0) lane--;
  if (e.key === "ArrowRight" && lane < 2) lane++;
}});
function reset() {{
  best = Math.max(best, score);
  score = 0;
  speed = {v};
  things = [];
}}
function spawn() {{
  const l = Math.floor(Math.random() * 3);
  const coin = {"Math.random() < 0.4" if coins else "false"};
  things.push({{ x: lanes[l], y: -40, coin }});
}}
function loop() {{
  tick++;
  if (tick % Math.max(18, Math.floor(60 - speed * 4)) === 0) spawn();
  px += (lanes[lane] - px) * 0.25;
  speed += 0.002;
  ctx.fillStyle = "#1f2937";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#374151";
  ctx.setLineDash([16, 16]);
  ctx.lineDashOffset = -tick * speed;
  for (const x of [W / 3, (W * 2) / 3]) {{
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }}
  ctx.setLineDash([]);
  for (const t of things) {{
    t.y += speed;
    if (t.coin) {{
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.arc(t.x, t.y, 10, 0, Math.PI * 2);
      ctx.fill();
    }} else {{
      ctx.fillStyle = "{COLORS[c2][0]}";
      ctx.fillRect(t.x - 28, t.y - 18, 56, 36);
    }}
    if (Math.abs(t.y - (H - 60)) < 28 && Math.abs(t.x - px) < 30) {{
      if (t.coin) {{
        score += 10;
        t.y = H + 100;
      }} else {{
        reset();
        return requestAnimationFrame(loop);
      }}
    }}
  }}
  things = things.filter((t) => t.y < H + 50);
  score += 0.1;
  ctx.fillStyle = "{COLORS[c1][0]}";
  ctx.fillRect(px - 18, H - 80, 36, 40);
  ctx.fillStyle = "#ffffff";
  ctx.font = "18px system-ui";
  ctx.fillText("Score: " + Math.floor(score) + "   Best: " + Math.floor(best), 12, 26);
  requestAnimationFrame(loop);
}}
loop();"""
    css = "canvas {\n  border-radius: 10px;\n}"
    body = '<canvas id="c" width="360" height="520"></canvas>'
    core = rng.choice([f"an endless runner game like Subway Surfers with three lanes, {an(c1)} player that switches lanes with the left and right arrow keys, {c2} obstacles{', yellow coins to collect' if coins else ''} and a score",
                       f"a 2D lane runner inspired by Subway Surfers: three lanes, I move the {c1} runner left and right with the arrow keys, dodge {c2} blocks{', grab yellow coins' if coins else ''}, score and best score",
                       f"a three-lane endless runner where the {c1} player dodges {c2} obstacles using the left and right arrows{', collecting yellow coins' if coins else ''}, with a score"])
    if speed != "normal":
        core += f", {speed}"
    return done(rng, core, dark), page("Runner", css, body, dark, script), {"animated": True, "keys": ["ArrowLeft"], "delay": 80}


def breakout(rng, dark, P):
    c1 = P("c1", lambda: pick_color(rng)[0])
    rows = P("rows", lambda: rng.choice([3, 4, 5]))
    rainbow = P("rainbow", lambda: rng.random() < 0.5)
    c2 = P("c2", lambda: pick_color(rng, exclude=(c1,))[0])
    brick = f'`hsl(${{r * {360 // rows}}}, 80%, 55%)`' if rainbow else f'"{COLORS[c2][0]}"'
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
const paddle = {{ x: W / 2 - 40, w: 80 }};
let ball;
let bricks;
let score = 0;
function reset() {{
  ball = {{ x: W / 2, y: H - 60, vx: 3, vy: -3 }};
  bricks = [];
  for (let r = 0; r < {rows}; r++) for (let c = 0; c < 8; c++) bricks.push({{ x: 10 + c * 58, y: 40 + r * 24, alive: true, color: {brick} }});
  score = 0;
}}
canvas.addEventListener("mousemove", (e) => {{
  paddle.x = e.offsetX - paddle.w / 2;
}});
document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowLeft") paddle.x -= 30;
  if (e.key === "ArrowRight") paddle.x += 30;
}});
function loop() {{
  ball.x += ball.vx;
  ball.y += ball.vy;
  if (ball.x < 8 || ball.x > W - 8) ball.vx *= -1;
  if (ball.y < 8) ball.vy *= -1;
  if (ball.y > H - 30 && ball.x > paddle.x && ball.x < paddle.x + paddle.w && ball.vy > 0) ball.vy *= -1;
  if (ball.y > H) reset();
  for (const b of bricks) {{
    if (b.alive && ball.x > b.x && ball.x < b.x + 52 && ball.y > b.y && ball.y < b.y + 18) {{
      b.alive = false;
      ball.vy *= -1;
      score++;
    }}
  }}
  if (bricks.every((b) => !b.alive)) reset();
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, W, H);
  for (const b of bricks) {{
    if (!b.alive) continue;
    ctx.fillStyle = b.color;
    ctx.fillRect(b.x, b.y, 52, 18);
  }}
  ctx.fillStyle = "{COLORS[c1][0]}";
  ctx.fillRect(paddle.x, H - 24, paddle.w, 10);
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(ball.x, ball.y, 7, 0, Math.PI * 2);
  ctx.fill();
  ctx.font = "16px system-ui";
  ctx.fillText("Score: " + score, 10, 22);
  requestAnimationFrame(loop);
}}
reset();
loop();"""
    css = "canvas {\n  border-radius: 10px;\n}"
    body = '<canvas id="c" width="480" height="400"></canvas>'
    bc = "rainbow" if rainbow else c2
    core = f"a Breakout game with {num(rng, rows)} rows of {bc} bricks, {an(c1)} paddle controlled with the mouse or arrow keys and a score"
    return done(rng, core, dark), page("Breakout", css, body, dark, script), {"animated": True, "delay": 60}


def flappy(rng, dark, P):
    c1 = P("c1", lambda: rng.choice(["yellow", "orange", "red", "pink"]))
    c2 = P("c2", lambda: rng.choice(["green", "teal", "gray", "blue"]))
    gap = P("gap", lambda: rng.choice(["easy", "normal", "hard"]))
    g = {"easy": 170, "normal": 140, "hard": 110}[gap]
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
let bird;
let pipes;
let score;
let frame;
function reset() {{
  bird = {{ y: H / 2, v: 0 }};
  pipes = [];
  score = 0;
  frame = 0;
}}
function flap() {{
  bird.v = -7;
}}
document.addEventListener("keydown", (e) => {{
  if (e.code === "Space") flap();
}});
canvas.addEventListener("click", flap);
function loop() {{
  frame++;
  if (frame % 90 === 30) pipes.push({{ x: W, top: 40 + Math.random() * (H - {g} - 80), passed: false }});
  bird.v += 0.4;
  bird.y += bird.v;
  ctx.fillStyle = "#7dd3fc";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "{COLORS[c2][0]}";
  for (const p of pipes) {{
    p.x -= 2.5;
    ctx.fillRect(p.x, 0, 52, p.top);
    ctx.fillRect(p.x, p.top + {g}, 52, H);
    const hit = 80 > p.x && 80 < p.x + 52 && (bird.y < p.top || bird.y > p.top + {g});
    if (hit) reset();
    if (!p.passed && p.x + 52 < 80) {{
      p.passed = true;
      score++;
    }}
  }}
  pipes = pipes.filter((p) => p.x > -60);
  if (bird.y > H || bird.y < 0) reset();
  ctx.fillStyle = "{COLORS[c1][0]}";
  ctx.beginPath();
  ctx.arc(80, bird.y, 14, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 28px system-ui";
  ctx.fillText(score, W / 2 - 8, 50);
  requestAnimationFrame(loop);
}}
reset();
loop();"""
    css = "canvas {\n  border-radius: 10px;\n}"
    body = '<canvas id="c" width="360" height="520"></canvas>'
    core = f"a Flappy Bird style game with {an(c1)} bird that flaps with space or a click, {c2} pipes with {'wide' if gap == 'easy' else 'narrow' if gap == 'hard' else 'normal'} gaps and a score"
    return done(rng, core, False), page("Flappy", css, body, False, script), {"animated": True, "delay": 60}


def catcher(rng, dark, P):
    c1 = P("c1", lambda: pick_color(rng)[0])
    thing = P("thing", lambda: rng.choice(["apples", "stars", "raindrops", "coins"]))
    color = {"apples": "#dc2626", "stars": "#facc15", "raindrops": "#38bdf8", "coins": "#eab308"}[thing]
    script = f"""const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const W = canvas.width;
const H = canvas.height;
const basket = {{ x: W / 2 - 40, w: 80 }};
let drops = [];
let score = 0;
let missed = 0;
let frame = 0;
canvas.addEventListener("mousemove", (e) => {{
  basket.x = e.offsetX - basket.w / 2;
}});
document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowLeft") basket.x -= 30;
  if (e.key === "ArrowRight") basket.x += 30;
}});
function loop() {{
  if (frame++ % 40 === 0) drops.push({{ x: 20 + Math.random() * (W - 40), y: -10, v: 2 + Math.random() * 2 }});
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "{color}";
  for (const d of drops) {{
    d.y += d.v;
    ctx.beginPath();
    ctx.arc(d.x, d.y, 10, 0, Math.PI * 2);
    ctx.fill();
    if (d.y > H - 30 && d.x > basket.x && d.x < basket.x + basket.w) {{
      d.y = H + 100;
      score++;
    }} else if (d.y > H && d.y < H + 50) {{
      d.y = H + 100;
      missed++;
    }}
  }}
  drops = drops.filter((d) => d.y < H + 60);
  ctx.fillStyle = "{COLORS[c1][0]}";
  ctx.fillRect(basket.x, H - 24, basket.w, 16);
  ctx.fillStyle = "#ffffff";
  ctx.font = "16px system-ui";
  ctx.fillText("Caught: " + score + "   Missed: " + missed, 10, 22);
  requestAnimationFrame(loop);
}}
loop();"""
    css = "canvas {\n  border-radius: 10px;\n}"
    body = '<canvas id="c" width="420" height="480"></canvas>'
    core = f"a game where I catch falling {thing} with {an(c1)} basket using the mouse or arrow keys, counting caught and missed"
    return done(rng, core, dark), page("Catch", css, body, dark, script), {"animated": True, "delay": 400}


def tictactoe(rng, dark, P):
    cx = P("c1", lambda: pick_color(rng)[0])
    co = P("c2", lambda: pick_color(rng, exclude=(cx,))[0])
    css = f""".game {{
  text-align: center;
}}
#status {{
  margin-bottom: 14px;
  font-size: 22px;
}}
.board {{
  display: grid;
  grid-template-columns: repeat(3, 100px);
  gap: 8px;
}}
.cell {{
  height: 100px;
  border: none;
  border-radius: 12px;
  background: {surface(dark)};
  font-size: 54px;
  font-weight: 700;
  cursor: pointer;
}}
.cell.x {{
  color: {COLORS[cx][0]};
}}
.cell.o {{
  color: {COLORS[co][0]};
}}
#reset {{
  margin-top: 16px;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: {COLORS[cx][0]};
  color: #ffffff;
  font-size: 16px;
  cursor: pointer;
}}"""
    cells = "\n".join('    <button class="cell"></button>' for _ in range(9))
    body = f'<div class="game">\n  <div id="status">X to move</div>\n  <div class="board">\n{cells}\n  </div>\n  <button id="reset">New game</button>\n</div>'
    script = """const cells = [...document.querySelectorAll(".cell")];
const status = document.getElementById("status");
const lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
let turn = "X";
let over = false;
function winner() {
  for (const [a, b, c] of lines) {
    const v = cells[a].textContent;
    if (v && v === cells[b].textContent && v === cells[c].textContent) return v;
  }
  return cells.every((c) => c.textContent) ? "draw" : null;
}
cells.forEach((cell) => {
  cell.addEventListener("click", () => {
    if (over || cell.textContent) return;
    cell.textContent = turn;
    cell.classList.add(turn.toLowerCase());
    const w = winner();
    if (w) {
      over = true;
      status.textContent = w === "draw" ? "It's a draw" : w + " wins!";
    } else {
      turn = turn === "X" ? "O" : "X";
      status.textContent = turn + " to move";
    }
  });
});
document.getElementById("reset").addEventListener("click", () => {
  cells.forEach((c) => {
    c.textContent = "";
    c.className = "cell";
  });
  turn = "X";
  over = false;
  status.textContent = "X to move";
});"""
    core = f"a Tic-tac-toe game for two players with {cx} X and {co} O, a status line saying whose turn it is or who won, and a New game button"
    return done(rng, core, dark), page("Tic-tac-toe", css, body, dark, script), {"click": ".cell", "wait": 100}


EMOJI = {"fruit": ["🍎", "🍌", "🍇", "🍓", "🍒", "🍍", "🥝", "🍑"], "animals": ["🐶", "🐱", "🐼", "🦊", "🐸", "🐵", "🐧", "🐙"],
         "space": ["🚀", "🌍", "🌙", "⭐", "🪐", "☄️", "🛸", "👨‍🚀"]}


def memory(rng, dark, P):
    theme = P("theme", lambda: rng.choice(list(EMOJI)))
    pairs = P("pairs", lambda: rng.choice([4, 6, 8]))
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    cols = 4
    css = f""".game {{
  text-align: center;
}}
#info {{
  margin-bottom: 12px;
  font-size: 18px;
}}
.board {{
  display: grid;
  grid-template-columns: repeat({cols}, 80px);
  gap: 10px;
}}
.card {{
  height: 80px;
  border-radius: 12px;
  background: {hx};
  font-size: 40px;
  line-height: 80px;
  cursor: pointer;
  user-select: none;
}}
.card.open, .card.found {{
  background: {surface(dark)};
}}
.card.found {{
  opacity: 0.5;
}}"""
    body = '<div class="game">\n  <div id="info">Moves: 0</div>\n  <div class="board" id="board"></div>\n</div>'
    script = f"""const symbols = {json_list(EMOJI[theme][:pairs])};
const deck = [...symbols, ...symbols].sort(() => Math.random() - 0.5);
const board = document.getElementById("board");
let open = [];
let moves = 0;
let found = 0;
deck.forEach((s) => {{
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.s = s;
  card.addEventListener("click", () => {{
    if (open.length === 2 || card.classList.contains("open") || card.classList.contains("found")) return;
    card.classList.add("open");
    card.textContent = s;
    open.push(card);
    if (open.length === 2) {{
      moves++;
      document.getElementById("info").textContent = "Moves: " + moves;
      const [a, b] = open;
      if (a.dataset.s === b.dataset.s) {{
        a.classList.add("found");
        b.classList.add("found");
        open = [];
        found++;
        if (found === symbols.length) document.getElementById("info").textContent = "You won in " + moves + " moves!";
      }} else {{
        setTimeout(() => {{
          a.classList.remove("open");
          b.classList.remove("open");
          a.textContent = "";
          b.textContent = "";
          open = [];
        }}, 700);
      }}
    }}
  }});
  board.appendChild(card);
}});"""
    core = f"a memory card game with {num(rng, pairs)} pairs of {theme} emoji on {cname} cards, a move counter and a win message"
    return done(rng, core, dark), page("Memory", css, body, dark, script), {"click": ".card", "wait": 100}


def whack(rng, dark, P):
    cname = P("color", lambda: pick_color(rng)[0])
    hx = COLORS[cname][0]
    holes = P("holes", lambda: rng.choice([6, 9]))
    secs = P("seconds", lambda: rng.choice([20, 30]))
    css = f""".game {{
  text-align: center;
}}
#info {{
  margin-bottom: 12px;
  font-size: 20px;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(3, 100px);
  gap: 12px;
}}
.hole {{
  position: relative;
  height: 100px;
  border-radius: 50%;
  background: {"#374151" if dark else "#d6d3d1"};
  overflow: hidden;
}}
.mole {{
  position: absolute;
  left: 15px;
  top: 100px;
  width: 70px;
  height: 70px;
  border: none;
  border-radius: 50%;
  background: {hx};
  cursor: pointer;
  transition: top 0.15s;
}}
.hole.up .mole {{
  top: 20px;
}}
#start {{
  margin-top: 16px;
  padding: 10px 22px;
  border: none;
  border-radius: 10px;
  background: {hx};
  color: #ffffff;
  font-size: 16px;
  cursor: pointer;
}}"""
    hs = "\n".join('    <div class="hole"><button class="mole"></button></div>' for _ in range(holes))
    body = f'<div class="game">\n  <div id="info">Score: 0 | Time: {secs}</div>\n  <div class="grid">\n{hs}\n  </div>\n  <button id="start">Start</button>\n</div>'
    script = f"""const holes = [...document.querySelectorAll(".hole")];
const info = document.getElementById("info");
let score = 0;
let time = {secs};
let timer = null;
let pop = null;
function show() {{
  holes.forEach((h) => h.classList.remove("up"));
  holes[Math.floor(Math.random() * holes.length)].classList.add("up");
}}
holes.forEach((h) => {{
  h.querySelector(".mole").addEventListener("click", () => {{
    if (!h.classList.contains("up")) return;
    h.classList.remove("up");
    score++;
    info.textContent = "Score: " + score + " | Time: " + time;
  }});
}});
document.getElementById("start").addEventListener("click", () => {{
  if (timer) return;
  score = 0;
  time = {secs};
  pop = setInterval(show, 800);
  timer = setInterval(() => {{
    time--;
    info.textContent = "Score: " + score + " | Time: " + time;
    if (time === 0) {{
      clearInterval(timer);
      clearInterval(pop);
      timer = null;
      holes.forEach((h) => h.classList.remove("up"));
      info.textContent = "Time's up! Score: " + score;
    }}
  }}, 1000);
}});"""
    core = f"a whack-a-mole game with {num(rng, holes)} holes and {cname} moles, a Start button, a score and a {secs} second timer"
    return done(rng, core, dark), page("Whack-a-mole", css, body, dark, script), {"click": "#start", "wait": 900}


GAMES = [(runner, 1.0), (breakout, 0.8), (flappy, 0.8), (catcher, 0.7), (tictactoe, 0.7), (memory, 0.7), (whack, 0.6)]
ALL = WIDGETS + ANIMATIONS + LANDINGS + GAMES


# ------------------------------------------------------------------ edits

NO_THEME_MORE = {"flappy", "slider"}
COUNTS = {"dots_loader": [3, 4, 5, 6, 7, 8, 9, 10, 12], "cursor_follow": [5, 8, 10, 12, 15, 20],
          "balls": [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20], "dice": [1, 2, 3], "rating": [5, 10], "memory": [4, 6, 8]}
NOUN = {"dots_loader": "dots", "cursor_follow": "dots", "balls": "balls", "dice": "dice", "rating": "stars", "memory": "pairs"}


def more_edits(rng, name, vals, dark, edit_color, edit_speed, other):
    out = []
    if name in COUNTS and "count" in vals or name == "memory":
        key = "pairs" if name == "memory" else "count"
        new = other(rng, COUNTS[name], vals[key])
        noun = NOUN[name] if new != 1 else NOUN[name][:-1].replace("dic", "die")
        change = {key: new}
        if name == "balls":
            change["rainbow"] = vals["rainbow"] and new > 1
        out.append((rng.choice([f"make it {num(rng, new)} {noun}", f"use {num(rng, new)} {noun} instead", f"I want {num(rng, new)} {noun}",
                                f"change it to {num(rng, new)} {noun}"]), change, dark))
    if name in ("dots_loader", "typewriter", "balls", "runner") and "speed" in vals:
        out.append((*edit_speed(rng, vals), dark))
    if name == "dots_loader":
        new = "circle" if vals["layout"] == "row" else "row"
        out.append(("arrange the dots in a circle" if new == "circle" else "put the dots in a row", {"layout": new}, dark))
    if name in ("cursor_follow", "balls") and vals.get("count", 1) > 1:
        if vals["rainbow"]:
            out.append((f"make all the {NOUN[name]} {vals['color']}", {"rainbow": False}, dark))
        else:
            out.append((f"make the {NOUN[name]} rainbow-colored", {"rainbow": True}, dark))
    if name == "balls":
        out.append(("add gravity" if not vals["gravity"] else "remove the gravity", {"gravity": not vals["gravity"]}, dark))
    if name in ("typewriter", "wave_text", "tooltip"):
        key = {"typewriter": "text", "wave_text": "text", "tooltip": "tip"}[name]
        pool = {"typewriter": TYPE_TEXTS, "wave_text": ["WELCOME", "LOADING", "HELLO", "G-DEV", "PLAY", "SUMMER"],
                "tooltip": ["Hello!", "This is a tooltip", "More info here", "Saved automatically"]}[name]
        new = other(rng, pool, vals[key])
        out.append((rng.choice([f'change the text to "{new}"', f'make it say "{new}"']), {key: new}, dark))
    if name in ("form", "confetti", "tooltip", "dropdown") and "label" in vals:
        pool = {"form": FORMS[vals.get("kind", "login")][2], "confetti": ["Celebrate", "Click me", "Party!", "Surprise"],
                "tooltip": ["Hover me", "Info", "Help", "Details"], "dropdown": ["Menu", "Options", "Account"]}[name]
        if len(pool) > 1:
            new = other(rng, pool, vals["label"])
            out.append((rng.choice([f'change the button text to "{new}"', f'rename the button to "{new}"']), {"label": new}, dark))
    if name == "todo":
        new = other(rng, TODO_TITLES, vals["title"])
        out.append((f'change the title to "{new}"', {"title": new}, dark))
    if name == "clock":
        out.append((f"use {'12' if vals['h24'] else '24'}-hour format", {"h24": not vals["h24"]}, dark))
        out.append(("remove the date" if vals["date"] else "show the date too", {"date": not vals["date"]}, dark))
    if name == "stopwatch":
        out.append(("remove the Lap button" if vals["laps"] else "add a Lap button", {"laps": not vals["laps"]}, dark))
    if name == "slider":
        out.append(("stop the automatic sliding" if vals["auto"] else "make it change slides automatically every 3 seconds", {"auto": not vals["auto"]}, dark))
    if name == "landing":
        new = other(rng, CTAS, vals["cta"])
        out.append((rng.choice([f'change the hero button to "{new}"', f'make the main button say "{new}"']), {"cta": new}, dark))
        out.append(("remove the footer" if vals["footer"] else "add a footer", {"footer": not vals["footer"]}, dark))
        out.append(("remove the navbar" if vals["navbar"] else "add a navbar", {"navbar": not vals["navbar"]}, dark))
        if "features" in vals["sections"]:
            new = other(rng, [2, 3, 4], vals["features"])
            out.append((f"make it {num(rng, new)} feature cards", {"features": new}, dark))
    if name in ("runner", "breakout", "catcher", "tictactoe"):
        who = {"runner": ("the player", "the obstacles"), "breakout": ("the paddle", "the bricks"),
               "catcher": ("the basket", None), "tictactoe": ("the X", "the O")}[name]
        out.append((*edit_color(rng, vals, "c1", who[0], avoid=(vals.get("c2"),)), dark))
        if who[1] and not (name == "breakout" and vals["rainbow"]):
            out.append((*edit_color(rng, vals, "c2", who[1], avoid=(vals["c1"],)), dark))
    if name == "runner":
        out.append(("remove the coins" if vals["coins"] else "add yellow coins to collect", {"coins": not vals["coins"]}, dark))
    if name == "flappy":
        new = other(rng, ["easy", "normal", "hard"], vals["gap"])
        out.append(({"easy": "make the gaps wider", "hard": "make the gaps narrower", "normal": "make the gaps normal size"}[new], {"gap": new}, dark))
    return out
