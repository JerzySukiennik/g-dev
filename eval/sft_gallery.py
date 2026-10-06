"""Ask a fine-tuned G-Dev for pages and show them live in one HTML gallery.

Prompts come in two groups: ones the training grammar covers, and ones it does not,
so the gallery shows both what was learned and where it stops.

Usage:
    python eval/sft_gallery.py CKPT TOKENIZER --out gallery.html [--per 2] [--threads 8]
"""

import argparse
import html
import pathlib
import sys
from pathlib import Path

import torch
from tokenizers import Tokenizer

sys.modules.setdefault("pathlib._local", pathlib)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.gpt import GPT, GPTConfig  # noqa: E402

IN_GRAMMAR = [
    "Make a green button \"Play\" that grows slightly on hover.",
    "Create a card titled \"Weekly report\" saying \"Everything went according to plan this week.\" that lifts up on hover, dark theme.",
    "Build a ring spinner loader in orange, fast.",
    "Make a Snake game with a teal snake and red food, controlled with the arrow keys, showing the score above the board.",
    "Create 6 rainbow-colored balls bouncing around inside a canvas.",
    "Write a click counter with a big purple number and a plus and a minus button.",
    "Build a tab switcher with the tabs Overview, Features and Pricing, the active tab highlighted in blue, each tab showing its own text.",
    "Make a toggle switch labeled \"Dark mode\" that turns pink when it is on.",
]
OUTSIDE = [
    "Make a pink button \"Buy tickets\" that shakes when you hover over it.",
    "Create a clock that shows the current time and updates every second.",
    "Build a login form with an email field, a password field and a blue Sign in button.",
    "Write a Tic-tac-toe game for two players.",
]
SYS = "<|user|>{}<|end|><|assistant|>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("tokenizer")
    ap.add_argument("--out", default="sft_gallery.html")
    ap.add_argument("--per", type=int, default=2)
    ap.add_argument("--tokens", type=int, default=1100)
    ap.add_argument("--temp", type=float, default=0.3)
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(a.threads)
    ck = torch.load(a.ckpt, map_location=device, weights_only=False)
    model = GPT(GPTConfig(**ck["config"])).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    tok = Tokenizer.from_file(a.tokenizer)
    end = tok.token_to_id("<|end|>")
    eot = tok.token_to_id("<|endoftext|>")

    groups = []
    for title, prompts in (("Covered by the training data", IN_GRAMMAR), ("Not in the training data", OUTSIDE)):
        cards = []
        for prompt in prompts:
            variants = []
            for i in range(a.per):
                torch.manual_seed(7 + i)
                ids = torch.tensor([tok.encode(SYS.format(prompt)).ids], device=device)
                out = []
                for tid, _ in model.generate(ids, a.tokens, temperature=a.temp if i else 0.05, top_k=40, repetition_penalty=1.0):
                    if tid in (end, eot):
                        break
                    out.append(tid)
                variants.append(tok.decode(out, skip_special_tokens=True))
                print(f"[{prompt[:40]}] #{i+1}: {len(out)} tokens", flush=True)
            cards.append((prompt, variants))
        groups.append((title, cards))

    parts = []
    for title, cards in groups:
        rows = []
        for prompt, variants in cards:
            figs = "".join(
                f'<figure><iframe sandbox="allow-scripts" srcdoc="{html.escape(v, quote=True)}"></iframe>'
                f'<details><summary>code</summary><pre>{html.escape(v)}</pre></details></figure>' for v in variants)
            rows.append(f'<div class="item"><p class="ask">{html.escape(prompt)}</p><div class="row">{figs}</div></div>')
        parts.append(f"<section><h2>{html.escape(title)}</h2>{''.join(rows)}</section>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G-Dev after SFT</title><style>
:root{{--bg:#0f1115;--fg:#e8e8ec;--mut:#8b8f99;--line:#252932;--acc:#8b93ff}}
@media (prefers-color-scheme:light){{:root{{--bg:#f6f6f8;--fg:#15171c;--mut:#6a6e78;--line:#dcdde3;--acc:#4f46e5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:32px 16px 64px}}
main{{max-width:1100px;margin:0 auto}}h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);margin:0 0 24px}}
h2{{font-size:15px;color:var(--acc);margin:36px 0 12px}}.item{{margin-bottom:22px}}.ask{{margin:0 0 8px;color:var(--fg);font-weight:600}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
figure{{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden}}iframe{{width:100%;height:300px;border:0;background:#fff;display:block}}
summary{{cursor:pointer;padding:8px 12px;color:var(--mut);font-size:12px;border-top:1px solid var(--line)}}
pre{{margin:0;padding:12px;max-height:260px;overflow:auto;font:12px/1.45 ui-monospace,monospace;white-space:pre-wrap}}
</style></head><body><main><h1>G-Dev after SFT (pretrain step {ck['step']})</h1>
<p class="sub">Each answer is the page the model wrote for the request above it, rendered live and unedited. The first variant is greedy, the second sampled.</p>
{''.join(parts)}</main></body></html>"""
    Path(a.out).write_text(page, encoding="utf-8")
    print("written", a.out)


if __name__ == "__main__":
    main()
