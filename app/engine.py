"""G-Dev's page writer, shared by the local panel server and the online bridge.

The model is loaded on first use and dropped by `unload()` when nobody has asked for a
while, so a bridge that waits all day for requests does not hold 700 MB. Both callers
use `write_page()`, a generator of events:

    {"t": "start", "unknown": [...], "note": str|None}   once, before any text
    {"t": "delta", "text": str}                          new text since the last delta
    {"t": "done", "edit": bool, "tokens": int, "secs": float, "complete": bool, "text": str}

A request with a base page is sent together with the conversation that produced it, the
format the model was fine-tuned on. If the answer has the same <title> as the base it is
an edit of that page; otherwise it is a new one.
"""

import json
import os
import pathlib
import re
import sys
import threading
import time
from pathlib import Path

sys.modules.setdefault("pathlib._local", pathlib)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAX_TOKENS = 1400
ANSWER_ROOM = 900
THREADS = int(os.environ.get("GDEV_THREADS", 4))
RUNS = [("sft3-final", "gdev-sft3-weights.pt"), ("sft2-final", "gdev-sft2-weights.pt")]
SFT_DATA = ROOT / "data/web_sft/data/webpages_train.jsonl"
COMMON = {"a", "an", "the", "me", "my", "i", "you", "it", "its", "it's", "that's", "i'm", "don't", "that", "this", "with",
          "and", "or", "of", "to", "in", "on", "for", "please", "can", "could", "would", "want", "need", "make", "create",
          "build", "write", "give", "generate", "design", "some", "is", "are", "be", "so", "but", "just", "like", "which",
          "when", "what", "there", "should", "not", "no", "yes", "do", "does", "have", "has", "from", "into", "at", "by",
          "as", "if", "then", "now", "also", "very", "really", "more", "less", "instead", "page", "website", "site",
          "html", "one", "meant", "nice", "simple", "clean", "modern", "cool", "pretty", "small", "like", "i'd", "code"}

_lock = threading.Lock()
_state = {"model": None, "tok": None, "meta": None, "known": None, "last": time.time()}


def _pick_run():
    for run, weights in RUNS:
        ck = ROOT / "Niepotrzebne" / run / "sft/ckpt.pt"
        tk = ROOT / "Niepotrzebne" / run / "sft/tokenizer.json"
        if tk.exists() and ((ROOT / "Niepotrzebne" / weights).exists() or (ck.exists() and ck.stat().st_size > 1e9)):
            return ck, ROOT / "Niepotrzebne" / weights, tk, run
    raise SystemExit("no fine-tuned G-Dev checkpoint found")


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


def _load():
    import torch
    from tokenizers import Tokenizer
    from model.gpt import GPT, GPTConfig

    os.nice(10)
    torch.set_num_threads(THREADS)
    ck_path, weights, tok_path, run = _pick_run()
    if not weights.exists():
        ck = torch.load(ck_path, map_location="cpu", weights_only=False)
        torch.save({"config": ck["config"], "model": ck["model"], "sft_steps": ck["step"]}, weights)
        del ck
    ck = torch.load(weights, map_location="cpu", weights_only=False)
    model = GPT(GPTConfig(**ck["config"]))
    model.load_state_dict(ck["model"])
    model.eval()
    known = set()
    for line in open(SFT_DATA, encoding="utf-8"):
        for turn in re.findall(r"<\|user\|>(.*?)<\|end\|>", json.loads(line)["text"]):
            known.update(words(turn))
    _state.update(model=model, tok=Tokenizer.from_file(str(tok_path)), meta={"run": run, "sft_steps": ck.get("sft_steps")},
                  known=known)


def ensure_loaded():
    with _lock:
        if _state["model"] is None:
            t0 = time.time()
            _load()
            print(f"[engine] model {_state['meta']['run']} ready in {time.time()-t0:.0f}s", flush=True)
        _state["last"] = time.time()


def unload():
    with _lock:
        _state.update(model=None, tok=None, known=None)
    import gc
    gc.collect()


def idle_seconds():
    return time.time() - _state["last"]


def info():
    ensure_loaded()
    m = _state["model"]
    return {"params": sum(p.numel() for p in m.parameters()), "threads": THREADS, "context": m.config.block_size,
            "sft_steps": _state["meta"].get("sft_steps"), "run": _state["meta"]["run"]}


def unknown_words(prompt):
    known = _state["known"]
    out = []
    for w in words(prompt):
        if w not in known and w not in COMMON and w.rstrip("s") not in known and w not in out:
            out.append(w)
    return out


def title_of(html):
    m = re.search(r"<title>(.*?)</title>", html or "", re.S)
    return m.group(1).strip() if m else None


def write_page(prompt, base_html=None, base_prompt=None, should_stop=lambda: False):
    import torch

    ensure_loaded()
    model, tok = _state["model"], _state["tok"]
    end = {tok.token_to_id("<|end|>"), tok.token_to_id("<|endoftext|>")}
    context = ""
    note = None
    if base_html:
        context = f"<|user|>{base_prompt or prompt}<|end|><|assistant|>{base_html}<|end|>"
    full = context + f"<|user|>{prompt}<|end|><|assistant|>"
    ids = tok.encode(full).ids
    if context and len(ids) + ANSWER_ROOM > model.config.block_size:
        note = "the previous page is too long to fit next to the request, so this starts a new page"
        base_html = None
        ids = tok.encode(f"<|user|>{prompt}<|end|><|assistant|>").ids
    yield {"t": "start", "unknown": unknown_words(prompt), "note": note}

    out, sent, t0, finished, edit = [], "", time.time(), False, None
    with torch.no_grad():
        for tid, _ in model.generate(torch.tensor([ids]), MAX_TOKENS, greedy=True):
            if should_stop():
                return
            if tid in end:
                finished = True
                break
            out.append(tid)
            text = tok.decode(out, skip_special_tokens=True)
            if edit is None and ("</title>" in text or len(out) > 60):
                edit = bool(base_html) and title_of(text) is not None and title_of(text) == title_of(base_html)
                yield {"t": "kind", "edit": edit}
            if edit is not None and len(out) % 3 == 0 and not text.endswith("�"):
                yield {"t": "delta", "text": text[len(sent):]}
                sent = text
    text = tok.decode(out, skip_special_tokens=True)
    if edit is None:
        edit = False
        yield {"t": "kind", "edit": False}
    if text[len(sent):]:
        yield {"t": "delta", "text": text[len(sent):]}
    _state["last"] = time.time()
    yield {"t": "done", "edit": edit, "tokens": len(out), "secs": round(time.time() - t0, 1), "complete": finished, "text": text}
