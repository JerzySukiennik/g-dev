"""G-Dev bridge: answers page requests that arrive through Firebase while the Mac is awake.

The website writes a job into a Realtime Database and listens for the answer; this
process listens for jobs, asks the model (engine.py) and writes the page back as it is
produced. Both sides only make outgoing connections, so nothing at home is exposed.

Each browser gets its own space under a random 128-bit client id, so nobody can read
another visitor's pages, and only this Mac (an anonymous account whose uid the database
rules name) can list the tree or write answers. Every answer write carries the whole text
so far rather than a delta: a dropped or reordered write can never leave half a page.

The model loads on the first request and is dropped after ten idle minutes, so waiting
for visitors costs a few dozen MB.

    python app/bridge.py [--print-uid]
"""

import argparse
import json
import os
import signal
import threading
import time
from pathlib import Path

import requests

import engine

DB = "https://gzowo-g-dev-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyBa5pOiEofJPmNbpoJjjeGZHhSrYH7PIn8"
IDENTITY = Path.home() / ".g-dev" / "identity.json"
HEARTBEAT = 20
IDLE_UNLOAD = 10 * 60
FLUSH_EVERY = 0.7
STALE_JOB = 15 * 60
MAX_QUEUE = 6
STREAM_SILENCE = 90


class Identity:
    def __init__(self):
        self.data = {}
        self.expires = 0

    def load_or_create(self):
        if IDENTITY.exists():
            self.data = json.loads(IDENTITY.read_text())
            self._refresh()
        else:
            r = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}",
                              json={"returnSecureToken": True}, timeout=20)
            r.raise_for_status()
            d = r.json()
            self.data = {"uid": d["localId"], "refresh": d["refreshToken"], "token": d["idToken"]}
            self.expires = time.time() + int(d["expiresIn"]) - 120
            IDENTITY.parent.mkdir(parents=True, exist_ok=True)
            IDENTITY.write_text(json.dumps(self.data))
            IDENTITY.chmod(0o600)
        return self.data["uid"]

    def _refresh(self):
        r = requests.post(f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
                          data={"grant_type": "refresh_token", "refresh_token": self.data["refresh"]}, timeout=20)
        r.raise_for_status()
        d = r.json()
        self.data.update(token=d["id_token"], refresh=d["refresh_token"])
        self.expires = time.time() + int(d["expires_in"]) - 120
        IDENTITY.write_text(json.dumps(self.data))

    def token(self):
        if time.time() > self.expires:
            self._refresh()
        return self.data["token"]

    @property
    def uid(self):
        return self.data["uid"]


class Bridge:
    def __init__(self, identity):
        self.id = identity
        self.jobs = []
        self.running = set()
        self.cancelled = set()
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stopping = threading.Event()

    def put(self, path, data):
        try:
            r = requests.put(f"{DB}/{path}.json?auth={self.id.token()}", json=data, timeout=20)
            if r.status_code >= 400:
                print(f"[bridge] write rejected {r.status_code} ({path}): {r.text[:160]}", flush=True)
        except requests.RequestException as e:
            print(f"[bridge] write failed ({path}): {e}", flush=True)

    def delete(self, path):
        try:
            requests.delete(f"{DB}/{path}.json?auth={self.id.token()}", timeout=20)
        except requests.RequestException:
            pass

    def announce(self, online):
        loaded = engine._state["model"] is not None
        self.put("status/mac", {"online": online, "at": int(time.time() * 1000), "loaded": loaded})

    def heartbeat(self):
        while not self.stopping.wait(HEARTBEAT):
            self.announce(True)

    def listen(self):
        headers = {"Accept": "text/event-stream"}
        while not self.stopping.is_set():
            try:
                r = requests.get(f"{DB}/open.json?auth={self.id.token()}", headers=headers, stream=True,
                                 timeout=(10, STREAM_SILENCE))
                event = None
                while not self.stopping.is_set():
                    line = r.raw.readline()
                    if not line:
                        break
                    line = line.decode("utf-8", "replace").strip()
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:") and event in ("put", "patch"):
                        self.on_event(json.loads(line[5:]))
                r.close()
            except (requests.RequestException, ValueError, OSError) as e:
                print(f"[bridge] stream lost: {e}", flush=True)
            time.sleep(3)

    def on_event(self, msg):
        parts = [p for p in msg.get("path", "/").split("/") if p]
        data = msg.get("data")
        if data is None:
            if len(parts) >= 3 and parts[1] == "jobs":
                with self.lock:
                    self.cancelled.add(parts[2])
                self.wake.set()
            return
        if not parts:
            for client, sub in (data or {}).items():
                for jid, job in ((sub or {}).get("jobs") or {}).items():
                    self.queue(client, jid, job)
        elif len(parts) == 1 and isinstance(data, dict):
            for jid, job in (data.get("jobs") or {}).items():
                self.queue(parts[0], jid, job)
        elif len(parts) == 2 and parts[1] == "jobs" and isinstance(data, dict):
            for jid, job in data.items():
                self.queue(parts[0], jid, job)
        elif len(parts) == 3 and parts[1] == "jobs" and isinstance(data, dict):
            self.queue(parts[0], parts[2], data)
        elif len(parts) == 4 and parts[1] == "jobs" and parts[3] == "cancel" and data:
            with self.lock:
                self.cancelled.add(parts[2])
            self.wake.set()

    def queue(self, client, jid, job):
        if not isinstance(job, dict) or "prompt" not in job:
            return
        with self.lock:
            if jid in self.running or any(j[1] == jid for j in self.jobs):
                return
            self.jobs.append((client, jid, job))
        self.wake.set()

    def handle(self, client, jid, job):
        out = f"open/{client}/out/{jid}"
        with self.lock:
            if jid in self.cancelled:
                self.cancelled.discard(jid)
                self.delete(f"open/{client}/jobs/{jid}")
                return
            self.running.add(jid)
        age = time.time() * 1000 - job.get("at", 0)
        if age > STALE_JOB * 1000:
            self.put(out, {"text": "", "error": "This request waited too long while the Mac was away. Send it again.", "done": True})
        else:
            print(f"[bridge] {client[:6]}/{jid[:8]}: {str(job['prompt'])[:70]!r}", flush=True)
            state, last = {"text": "", "started": False, "unknown": [], "note": None}, [0.0]

            def flush(force=False, **extra):
                if force or time.monotonic() - last[0] >= FLUSH_EVERY:
                    last[0] = time.monotonic()
                    self.put(out, {**state, **extra})

            try:
                prompt = " ".join(str(job["prompt"]).split())[:600]
                base = str(job.get("base") or "")[:24000] or None
                origin = str(job.get("origin") or "")[:600] or None
                for ev in engine.write_page(prompt, base, origin, should_stop=lambda: jid in self.cancelled):
                    if ev["t"] == "start":
                        state["unknown"], state["note"], state["started"] = ev["unknown"], ev["note"], True
                        flush(True)
                    elif ev["t"] == "kind":
                        state["edit"] = ev["edit"]
                        flush(True)
                    elif ev["t"] == "delta":
                        state["text"] += ev["text"]
                        flush()
                    elif ev["t"] == "done":
                        self.put(out, {**state, "text": ev["text"], "done": True, "tokens": ev["tokens"], "secs": ev["secs"],
                                       "complete": ev["complete"], "edit": ev["edit"]})
                if jid in self.cancelled:
                    self.put(out, {**state, "done": True, "stopped": True})
            except Exception as e:
                self.put(out, {**state, "error": f"Something went wrong on the Mac: {e}", "done": True})
        self.delete(f"open/{client}/jobs/{jid}")
        with self.lock:
            self.running.discard(jid)
            self.cancelled.discard(jid)

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: self.stopping.set() or self.wake.set())
        print(f"[bridge] Mac uid: {self.id.uid}", flush=True)
        self.announce(True)
        threading.Thread(target=self.heartbeat, daemon=True).start()
        threading.Thread(target=self.listen, daemon=True).start()
        while not self.stopping.is_set():
            self.wake.wait(30)
            self.wake.clear()
            while True:
                with self.lock:
                    self.jobs = self.jobs[-MAX_QUEUE:]
                    job = self.jobs.pop(0) if self.jobs else None
                if not job:
                    break
                self.handle(*job)
            if engine._state["model"] is not None and engine.idle_seconds() > IDLE_UNLOAD and not self.running:
                print("[bridge] idle, unloading the model", flush=True)
                engine.unload()
        self.announce(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-uid", action="store_true")
    args = ap.parse_args()
    identity = Identity()
    uid = identity.load_or_create()
    if args.print_uid:
        print(uid)
        return
    Bridge(identity).run()


if __name__ == "__main__":
    main()
