"""G-Dev panel server: loads the fine-tuned model once and streams pages as it writes them.

Endpoints
  GET  /                 the panel
  GET  /api/status       model info
  GET  /api/files        pages written so far, newest first
  GET  /pages/<name>     a written page
  POST /api/generate     {"prompt": "...", "base": "file.html"?} -> server-sent events

With a base file the model sees the conversation that produced it (the original request
and the current page) followed by the new request, the format it was fine-tuned on. If
the answer has the same <title> as the base it is an edit and overwrites the file (the
previous version is kept in pages/.versions); otherwise it is a new page.

Events: start, file {file, edit}, delta {text}, done {...}. `sure` in done is the share of
tokens the model chose with at least 90% probability (measured without temperature): near 1.0
on the kinds of pages it was trained on, clearly lower when it is guessing. One generation at a time,
closing the request stops it, and the server exits after 30 idle minutes so the model
does not sit in memory; the G-Dev app starts it again.

    python app/server.py [port]
"""

import json
import os
import pathlib
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from tokenizers import Tokenizer

sys.modules.setdefault("pathlib._local", pathlib)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.gpt import GPT, GPTConfig  # noqa: E402

APP = Path(__file__).resolve().parent
PAGES = APP / "pages"
VERSIONS = PAGES / ".versions"
SFT_CKPT = ROOT / "Niepotrzebne/sft2-final/sft/ckpt.pt"
WEIGHTS = ROOT / "Niepotrzebne/gdev-sft2-weights.pt"
TOKENIZER = ROOT / "Niepotrzebne/sft2-final/sft/tokenizer.json"
MAX_TOKENS = 1400
ANSWER_ROOM = 900
THREADS = 4
IDLE_EXIT = 30 * 60
LAST = [time.time()]

VERSIONS.mkdir(parents=True, exist_ok=True)
os.nice(10)
torch.set_num_threads(THREADS)


def load_model():
    if not WEIGHTS.exists():
        ck = torch.load(SFT_CKPT, map_location="cpu", weights_only=False)
        torch.save({"config": ck["config"], "model": ck["model"], "sft_steps": ck["step"]}, WEIGHTS)
    ck = torch.load(WEIGHTS, map_location="cpu", weights_only=False)
    m = GPT(GPTConfig(**ck["config"]))
    m.load_state_dict(ck["model"])
    m.eval()
    return m, ck


t0 = time.time()
MODEL, META = load_model()
TOK = Tokenizer.from_file(str(TOKENIZER))
END = {TOK.token_to_id("<|end|>"), TOK.token_to_id("<|endoftext|>")}
PARAMS = sum(p.numel() for p in MODEL.parameters())
LOCK = threading.Lock()
print(f"model ready in {time.time()-t0:.0f}s, {PARAMS/1e6:.0f}M params, {THREADS} threads", flush=True)


def slug_for(prompt):
    words = re.findall(r"[a-z0-9]+", prompt.lower())
    stop = {"a", "an", "the", "make", "create", "build", "write", "generate", "give", "me", "please", "can", "you",
            "i", "need", "design", "with", "that", "and", "on", "in", "it", "of", "to", "page", "which", "when", "is"}
    core = [w for w in words if w not in stop][:4] or ["page"]
    base = "-".join(core)[:40]
    name, n = f"{base}.html", 2
    while (PAGES / name).exists():
        name, n = f"{base}-{n}.html", n + 1
    return name


def title_of(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return m.group(1).strip() if m else None


def read_meta(name):
    side = (PAGES / name).with_suffix(".json")
    return json.loads(side.read_text()) if side.exists() else {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        LAST[0] = time.time()
        if self.path in ("/", "/index.html"):
            return self.send(200, (APP / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.send(200, json.dumps({"params": PARAMS, "threads": THREADS, "sft_steps": META.get("sft_steps"),
                                              "context": MODEL.config.block_size}))
        if self.path == "/api/files":
            files = sorted(PAGES.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
            return self.send(200, json.dumps([{"name": p.name, "prompt": read_meta(p.name).get("prompt", ""),
                                               "time": p.stat().st_mtime} for p in files]))
        if self.path.startswith("/pages/"):
            p = PAGES / Path(self.path[7:].split("?")[0]).name
            if p.exists() and p.suffix == ".html":
                return self.send(200, p.read_bytes(), "text/html; charset=utf-8")
        self.send(404, '{"error":"not found"}')

    def do_POST(self):
        LAST[0] = time.time()
        if self.path != "/api/generate":
            return self.send(404, '{"error":"not found"}')
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        prompt = " ".join(str(body.get("prompt", "")).split())[:600]
        base = Path(str(body.get("base") or "")).name
        if not prompt:
            return self.send(400, '{"error":"empty prompt"}')
        if not LOCK.acquire(blocking=False):
            return self.send(409, '{"error":"busy"}')
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.stream(prompt, base)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            LOCK.release()

    def event(self, obj):
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
        self.wfile.flush()

    def stream(self, prompt, base):
        context, old, origin = "", None, prompt
        if base and (PAGES / base).exists():
            old = (PAGES / base).read_text(encoding="utf-8")
            origin = read_meta(base).get("prompt") or prompt
            context = f"<|user|>{origin}<|end|><|assistant|>{old}<|end|>"
        full = context + f"<|user|>{prompt}<|end|><|assistant|>"
        ids = TOK.encode(full).ids
        note = None
        if context and len(ids) + ANSWER_ROOM > MODEL.config.block_size:
            note = "the previous page is too long to fit next to the request, so this starts a new page"
            context, old, origin = "", None, prompt
            ids = TOK.encode(f"<|user|>{prompt}<|end|><|assistant|>").ids
        self.event({"t": "start", "context": bool(context), "note": note})
        decided = None if old else (slug_for(prompt), False)
        if decided:
            self.event({"t": "file", "file": decided[0], "edit": False})
        out, sent, t0, finished, logp = [], "", time.time(), False, []
        with torch.no_grad():
            for tid, probs in MODEL.generate(torch.tensor([ids]), MAX_TOKENS, greedy=True):
                logp.append(float(torch.log(probs[tid].clamp_min(1e-9))))
                if tid in END:
                    finished = True
                    break
                out.append(tid)
                text = TOK.decode(out, skip_special_tokens=True)
                if not decided and ("</title>" in text or len(out) > 60):
                    same = title_of(text) is not None and title_of(text) == title_of(old)
                    decided = (base, True) if same else (slug_for(prompt), False)
                    self.event({"t": "file", "file": decided[0], "edit": decided[1]})
                if decided and len(out) % 3 == 0 and not text.endswith("�"):
                    self.event({"t": "delta", "text": text[len(sent):]})
                    sent = text
        text = TOK.decode(out, skip_special_tokens=True)
        if not decided:
            decided = (slug_for(prompt), False)
            self.event({"t": "file", "file": decided[0], "edit": False})
        if text[len(sent):]:
            self.event({"t": "delta", "text": text[len(sent):]})
        name, edit = decided
        if edit:
            (VERSIONS / f"{Path(name).stem}.{int(time.time())}.html").write_text(old, encoding="utf-8")
        LAST[0] = time.time()
        (PAGES / name).write_text(text, encoding="utf-8")
        (PAGES / name).with_suffix(".json").write_text(json.dumps({"prompt": origin if edit else prompt}))
        secs = time.time() - t0
        sure = sum(1 for x in logp if x > -0.105) / max(1, len(logp))
        self.event({"t": "done", "file": name, "edit": edit, "tokens": len(out), "secs": round(secs, 1),
                    "lines": text.count("\n") + 1, "complete": finished, "sure": round(sure, 4)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8615
    print(f"G-Dev panel on http://localhost:{port}", flush=True)

    def reaper():
        while True:
            time.sleep(60)
            if time.time() - LAST[0] > IDLE_EXIT and not LOCK.locked():
                print("idle, exiting", flush=True)
                os._exit(0)

    threading.Thread(target=reaper, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
