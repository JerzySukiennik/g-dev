"""G-Dev local panel server: streams pages as the model writes them.

Endpoints
  GET  /                 the panel
  GET  /api/status       model info
  GET  /api/files        pages written so far, newest first
  GET  /pages/<name>     a written page
  POST /api/generate     {"prompt": "...", "base": "file.html"?} -> server-sent events

All model work is in engine.py, shared with the online bridge. One generation at a time,
closing the request stops it, and the server exits after 30 idle minutes so the model does
not sit in memory; the G-Dev app starts it again.

    python app/server.py [port]
"""

import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import engine

APP = Path(__file__).resolve().parent
PAGES = APP / "pages"
VERSIONS = PAGES / ".versions"
IDLE_EXIT = 30 * 60
LAST = [time.time()]
LOCK = threading.Lock()
VERSIONS.mkdir(parents=True, exist_ok=True)

STOP = {"a", "an", "the", "make", "me", "create", "build", "write", "generate", "give", "please", "can", "you", "i", "need",
        "design", "with", "that", "and", "on", "in", "it", "of", "to", "page", "which", "when", "is", "nice", "simple"}


def slug_for(prompt):
    core = [w for w in re.findall(r"[a-z0-9]+", prompt.lower()) if w not in STOP][:4] or ["page"]
    base = "-".join(core)[:40]
    name, n = f"{base}.html", 2
    while (PAGES / name).exists():
        name, n = f"{base}-{n}.html", n + 1
    return name


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
        self.path = self.path.split("?")[0] if not self.path.startswith("/pages/") else self.path
        if self.path in ("/", "/index.html"):
            return self.send(200, (APP / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.send(200, json.dumps(engine.info()))
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
        old = (PAGES / base).read_text(encoding="utf-8") if base and (PAGES / base).exists() else None
        origin = read_meta(base).get("prompt") if old else None
        name = None
        for ev in engine.write_page(prompt, old, origin):
            if ev["t"] == "start":
                self.event({"t": "start", "note": ev["note"], "unknown": ev["unknown"]})
                if not old or ev["note"]:
                    old = None
            elif ev["t"] == "kind":
                name = base if ev["edit"] else slug_for(prompt)
                self.event({"t": "file", "file": name, "edit": ev["edit"]})
            elif ev["t"] == "delta":
                self.event(ev)
            elif ev["t"] == "done":
                if ev["edit"]:
                    (VERSIONS / f"{Path(name).stem}.{int(time.time())}.html").write_text(old, encoding="utf-8")
                LAST[0] = time.time()
                (PAGES / name).write_text(ev["text"], encoding="utf-8")
                (PAGES / name).with_suffix(".json").write_text(json.dumps({"prompt": origin if ev["edit"] else prompt}))
                self.event({"t": "done", "file": name, "edit": ev["edit"], "tokens": ev["tokens"], "secs": ev["secs"],
                            "lines": ev["text"].count("\n") + 1, "complete": ev["complete"]})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8615
    engine.ensure_loaded()
    print(f"G-Dev panel on http://localhost:{port}", flush=True)

    def reaper():
        while True:
            time.sleep(60)
            if time.time() - LAST[0] > IDLE_EXIT and not LOCK.locked():
                print("idle, exiting", flush=True)
                os._exit(0)

    threading.Thread(target=reaper, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
