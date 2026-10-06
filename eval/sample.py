"""Sample from a G-Dev checkpoint on a fixed set of prompts, to read what it writes.

A base model after pretraining only continues text: it has no chat format yet, so
every prompt is the beginning of a file (the same `<|file|>name` header the
training data uses) or a fill-in-the-middle request.

Usage:
    python eval/sample.py CKPT TOKENIZER [--tokens 160] [--temp 0.4] [--out samples.md]
"""

import argparse
import pathlib
import sys
import time
from pathlib import Path

import torch
from tokenizers import Tokenizer

sys.modules.setdefault("pathlib._local", pathlib)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.gpt import GPT, GPTConfig  # noqa: E402

PROMPTS = [
    ("css animation", "<|file|>button.css\n.btn {\n  padding: 12px 24px;\n  border-radius: 8px;\n  transition: transform 0.2s ease;\n}\n\n.btn:hover {\n"),
    ("js canvas loop", "<|file|>game.js\nconst canvas = document.getElementById('game');\nconst ctx = canvas.getContext('2d');\nlet player = { x: 100, y: 100, vx: 0, vy: 0 };\n\nfunction update(dt) {\n"),
    ("html page", "<|file|>index.html\n<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n  <title>Bouncing ball</title>\n  <style>\n"),
    ("js function", "<|file|>utils.js\n// Returns the debounced version of fn that waits `delay` ms after the last call\nfunction debounce(fn, delay) {\n"),
    ("python function", "<|file|>fib.py\ndef fibonacci(n):\n    \"\"\"Return the first n Fibonacci numbers as a list.\"\"\"\n"),
    ("typescript", "<|file|>Vec2.ts\nexport class Vec2 {\n  constructor(public x: number, public y: number) {}\n\n  add(o: Vec2): Vec2 {\n"),
    ("fim js", "<|fim_prefix|><|file|>snake.js\nfunction moveSnake(snake, dir) {\n  const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };\n<|fim_suffix|>\n  return snake;\n}\n<|fim_middle|>"),
    ("prose", "The easiest way to make a web animation feel smooth is to"),
]


def load(ckpt_path, device):
    ck = torch.load(ckpt_path, map_location=device, weights_only=False)
    model = GPT(GPTConfig(**ck["config"])).to(device)
    model.load_state_dict(ck["model"])
    return model.eval(), ck["step"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("tokenizer")
    ap.add_argument("--tokens", type=int, default=160)
    ap.add_argument("--temp", type=float, default=0.4)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--out", default="samples.md")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2, help="CPU threads; low by default to keep the fans quiet")
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(a.threads)
    torch.manual_seed(a.seed)
    model, step = load(a.ckpt, device)
    tok = Tokenizer.from_file(a.tokenizer)
    stop = {tok.token_to_id("<|endoftext|>")}
    lines = [f"# G-Dev samples, step {step}, temp {a.temp}, top-k {a.top_k}\n"]
    for name, prompt in PROMPTS:
        ids = torch.tensor([tok.encode(prompt).ids], device=device)
        out, t0 = [], time.time()
        for tid, _ in model.generate(ids, a.tokens, temperature=a.temp, top_k=a.top_k,
                                     repetition_penalty=1.0):
            if tid in stop:
                break
            out.append(tid)
        text = tok.decode(out, skip_special_tokens=False)
        print(f"[{name}] {len(out)} tokens in {time.time()-t0:.0f}s", flush=True)
        lines.append(f"## {name}\n\n```\n{prompt}█{text}\n```\n")
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"written {a.out}")


if __name__ == "__main__":
    main()
