"""G-Dev panel server: loads the fine-tuned model once and streams pages as it writes them.

Endpoints
  GET  /                 the panel
  GET  /api/status       model info
  GET  /api/files        pages written so far, newest first
  GET  /pages/<name>     a written page
  POST /api/generate     {"prompt": "..."} -> server-sent events: start, delta, done, error

One generation runs at a time; closing the request stops it. The server exits after
30 idle minutes so the ~700 MB model does not sit in memory; the G-Dev app starts it again.
 Inference is CPU only,
at low priority and on four threads, so the Mac stays quiet and usable.

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
SFT_CKPT = ROOT / "Niepotrzebne/sft-final/sft/ckpt.pt"
WEIGHTS = ROOT / "Niepotrzebne/gdev-sft-weights.pt"
TOKENIZER = ROOT / "Niepotrzebne/sft-final/sft/tokenizer.json"
MAX_TOKENS = 1400
THREADS = 4
IDLE_EXIT = 30 * 60
LAST = [time.time()]

PAGES.mkdir(exist_ok=True)
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
            meta = []
            for p in files:
                side = p.with_suffix(".json")
                info = json.loads(side.read_text()) if side.exists() else {}
                meta.append({"name": p.name, "prompt": info.get("prompt", ""), "time": p.stat().st_mtime})
            return self.send(200, json.dumps(meta))
        if self.path.startswith("/pages/"):
            p = PAGES / Path(self.path[7:]).name
            if p.exists() and p.suffix == ".html":
                return self.send(200, p.read_bytes(), "text/html; charset=utf-8")
        self.send(404, '{"error":"not found"}')

    def do_POST(self):
        LAST[0] = time.time()
        if self.path != "/api/generate":
            return self.send(404, '{"error":"not found"}')
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        prompt = " ".join(str(body.get("prompt", "")).split())[:600]
        if not prompt:
            return self.send(400, '{"error":"empty prompt"}')
        if not LOCK.acquire(blocking=False):
            return self.send(409, '{"error":"busy"}')
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.stream(prompt)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            LOCK.release()

    def event(self, obj):
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
        self.wfile.flush()

    def stream(self, prompt):
        name = slug_for(prompt)
        self.event({"t": "start", "file": name})
        ids = torch.tensor([TOK.encode(f"<|user|>{prompt}<|end|><|assistant|>").ids])
        out, sent, t0 = [], "", time.time()
        finished = False
        with torch.no_grad():
            for tid, _ in MODEL.generate(ids, MAX_TOKENS, temperature=0.05, top_k=40, repetition_penalty=1.0):
                if tid in END:
                    finished = True
                    break
                out.append(tid)
                text = TOK.decode(out, skip_special_tokens=True)
                if len(out) % 3 == 0 and not text.endswith("�"):
                    self.event({"t": "delta", "text": text[len(sent):]})
                    sent = text
        text = TOK.decode(out, skip_special_tokens=True)
        if text[len(sent):]:
            self.event({"t": "delta", "text": text[len(sent):]})
        LAST[0] = time.time()
        (PAGES / name).write_text(text, encoding="utf-8")
        (PAGES / name).with_suffix(".json").write_text(json.dumps({"prompt": prompt}))
        secs = time.time() - t0
        self.event({"t": "done", "file": name, "tokens": len(out), "secs": round(secs, 1),
                    "lines": text.count("\n") + 1, "complete": finished})


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
