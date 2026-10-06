"""Render what G-Dev writes: sample several pages per prompt and show each one live
in a sandboxed iframe next to its code, in a single HTML gallery.

Every prompt is the start of a real page whose visible parts are already in place
(a button, a spinner, a canvas), so the model's job is the CSS or script that
makes them look and move. Output is shown exactly as generated; the browser's
error recovery decides what renders, the way it would for anyone's page.

Usage:
    python eval/gallery.py CKPT TOKENIZER --out gallery.html [--per 3] [--threads 2]
"""

import argparse
import html
import json
import pathlib
import sys
from pathlib import Path

import torch
from tokenizers import Tokenizer

sys.modules.setdefault("pathlib._local", pathlib)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.gpt import GPT, GPTConfig  # noqa: E402

HEAD = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>{t}</title>\n<style>body{{margin:0;display:grid;place-items:center;min-height:100vh;font-family:system-ui,sans-serif;background:#fafafa}}</style>\n</head>\n<body>\n'

PROMPTS = [
    ("Hover button", HEAD.format(t="Button") + '<button class="btn">Hover me</button>\n<style>\n.btn {\n  background: #4f46e5;\n  color: white;\n  padding: 14px 28px;\n  border: none;\n  border-radius: 10px;\n  font-size: 16px;\n  cursor: pointer;\n  transition: transform 0.2s ease, box-shadow 0.2s ease;\n}\n.btn:hover {\n'),
    ("Loading spinner", HEAD.format(t="Spinner") + '<div class="spinner"></div>\n<style>\n.spinner {\n  width: 48px;\n  height: 48px;\n  border: 5px solid #ddd;\n  border-top-color: #4f46e5;\n  border-radius: 50%;\n  animation: '),
    ("Card", HEAD.format(t="Card") + '<div class="card">\n  <h2>Rocket launch</h2>\n  <p>Liftoff is scheduled for Saturday morning.</p>\n</div>\n<style>\n.card {\n'),
    ("Bouncing ball", HEAD.format(t="Bouncing ball") + '<canvas id="c" width="400" height="300" style="background:#111"></canvas>\n<script>\nconst c = document.getElementById("c");\nconst ctx = c.getContext("2d");\nlet x = 50, y = 50, vx = 3, vy = 2;\nfunction loop() {\n'),
    ("Pulsing dots", HEAD.format(t="Dots") + '<div class="dots"><span></span><span></span><span></span></div>\n<style>\n.dots span {\n  display: inline-block;\n  width: 16px;\n  height: 16px;\n  margin: 6px;\n  border-radius: 50%;\n  background: #4f46e5;\n  animation: pulse 1s infinite;\n}\n.dots span:nth-child(2) { animation-delay: 0.2s; }\n.dots span:nth-child(3) { animation-delay: 0.4s; }\n@keyframes pulse {\n'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("tokenizer")
    ap.add_argument("--out", default="gallery.html")
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--tokens", type=int, default=320)
    ap.add_argument("--temp", type=float, default=0.55)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(a.threads)
    ck = torch.load(a.ckpt, map_location=device, weights_only=False)
    model = GPT(GPTConfig(**ck["config"])).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    tok = Tokenizer.from_file(a.tokenizer)
    eot = tok.token_to_id("<|endoftext|>")

    sections = []
    for name, prompt in PROMPTS:
        cards = []
        for i in range(a.per):
            torch.manual_seed(100 + i)
            ids = torch.tensor([tok.encode("<|file|>index.html\n" + prompt).ids], device=device)
            out = []
            for tid, _ in model.generate(ids, a.tokens, temperature=a.temp, top_k=40, repetition_penalty=1.1):
                if tid == eot:
                    break
                out.append(tid)
            gen = tok.decode(out, skip_special_tokens=True)
            print(f"[{name} #{i+1}] {len(out)} tokens", flush=True)
            cards.append((prompt, gen))
        sections.append((name, cards))

    parts = []
    for name, cards in sections:
        items = []
        for n, (prompt, gen) in enumerate(cards, 1):
            doc = prompt + gen
            items.append(
                f'<figure><iframe sandbox="allow-scripts" srcdoc="{html.escape(doc, quote=True)}"></iframe>'
                f'<figcaption>#{n}</figcaption>'
                f'<details><summary>code</summary><pre><span class="p">{html.escape(prompt.split("<body>", 1)[-1].lstrip())}</span>'
                f'<span class="g">{html.escape(gen)}</span></pre></details></figure>')
        parts.append(f'<section><h2>{html.escape(name)}</h2><div class="row">{"".join(items)}</div></section>')

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G-Dev gallery</title>
<style>
:root{{--bg:#0f1115;--fg:#e8e8ec;--mut:#8b8f99;--line:#252932;--acc:#8b93ff}}
@media (prefers-color-scheme:light){{:root{{--bg:#f6f6f8;--fg:#15171c;--mut:#6a6e78;--line:#dcdde3;--acc:#4f46e5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:32px 16px 64px}}
main{{max-width:1180px;margin:0 auto}}h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);margin:0 0 32px}}
h2{{font-size:15px;font-weight:600;margin:32px 0 12px;color:var(--acc)}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
figure{{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--bg)}}
iframe{{width:100%;height:240px;border:0;display:block;background:#fff}}
figcaption{{padding:8px 12px;color:var(--mut);font-size:12px;border-top:1px solid var(--line)}}
details{{border-top:1px solid var(--line)}}summary{{cursor:pointer;padding:8px 12px;color:var(--mut);font-size:12px}}
pre{{margin:0;padding:12px;overflow:auto;max-height:260px;font:12px/1.45 ui-monospace,monospace;white-space:pre-wrap}}
.p{{color:var(--mut)}}.g{{color:var(--fg)}}
</style></head><body><main>
<h1>G-Dev, step {ck['step']}</h1>
<p class="sub">Each page starts with a real button, spinner, card, canvas or dots; the grey code is my prompt, the bright code is what the model wrote. Rendered live, unedited.</p>
{''.join(parts)}
</main></body></html>"""
    Path(a.out).write_text(page, encoding="utf-8")
    print("written", a.out)


if __name__ == "__main__":
    main()
