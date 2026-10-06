#!/usr/bin/env python3
"""Prowadzi trening G-Dev bez udzialu czlowieka: kolejne sesje pretrainingu, a po
ostatniej SFT i galeria.

Petla jest bezstanowa. Za kazdym obrotem pyta Kaggle, co istnieje, i z tego wylicza,
co robic dalej, wiec restart Maca albo uslugi niczego nie gubi. Jedyny zapis to
tools/state.json (zmierzony wspolczynnik quoty, dlugosc wyniku, pamiec sft).

  - sesja trwa  -> czekaj
  - nic nie trwa, trening nie skonczony -> odpal nastepna sesje z ostatniej COMPLETE
  - trening doszedl do MAX_STEPS -> SFT (gdev-sft), potem pobierz wynik i zrob galerie
  - kilka bledow startu pod rząd -> poczekaj do odnowienia quoty i probuj od nowa

Sesje konczone przez platforme (CANCELLED) nie nadaja sie na zrodlo kolejnej, wiec
dlugosc sesji jest dobierana tak, by trening sam sie zakonczyl (--max-hours) przed
limitem quoty. Quote liczy sie ze wspolczynnikiem zmierzonym z poprzednich sesji
(start 2.0 = ostroznie), bo raz obserwowalismy 2x, raz 1x.

Uruchomienie: LaunchAgent fun.gzowo.g-dev.chain albo .venv/bin/python tools/chain.py
Zatrzymanie: dotknij tools/STOP.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "Downloads/Claude/Projects/AIe/G-Dev"
KAGGLE = [str(Path.home() / "Downloads/Claude/Projects/AIe/G-Images/.venv/bin/python"), "-m", "kaggle"]
TORCH_PY = str(Path.home() / "Downloads/Claude/Projects/AIe/G-Micro/.venv/bin/python")
CFG = Path.home() / ".kaggle-gdev"
USER = (CFG / "username").read_text().strip()
KAGGLE_ENV = {**os.environ, "KAGGLE_API_TOKEN": str(CFG / "access_token")}

PREFIX, PREP, SEED, SFT = "gdev-s", "gdev-prep", "gdev-ckpt", "gdev-sft"
FIRST = 2
MAX_SESSION = 60
MAX_STEPS = 55800
STATE = REPO / "tools/state.json"
STOP_FILE = REPO / "tools/STOP"
DONE_FILE = REPO / "tools/DONE"
TMP = REPO / "Niepotrzebne/chain-tmp"

POLL = 900
QUOTA_WAIT = 3600
RETRY_WAIT = 1800
MAX_FAILS = 4
SESSION_CAP = 10.5
SETUP_MARGIN = 0.7
MIN_USEFUL = 1.5


def log(msg):
    print(f"[{datetime.now():%F %H:%M}] {msg}", flush=True)


def notify(msg):
    log(f"POWIADOMIENIE: {msg}")
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "G-Dev"'], capture_output=True)


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"factor": 2.0}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1))


def kaggle(*args, timeout=300):
    try:
        r = subprocess.run(KAGGLE + list(args), capture_output=True, text=True, timeout=timeout, env=KAGGLE_ENV)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def status(name):
    m = re.search(r"KernelWorkerStatus\.(\w+)", kaggle("kernels", "status", f"{USER}/{name}"))
    return m.group(1) if m else "NONE"


def quota():
    """(godziny GPU zuzyte, pozostale, UTC odnowienia) albo None."""
    m = re.search(r"^GPU\s+([\d.]+)h\s+([\d.]+)h\s+[\d.]+h\s+(\S+)", kaggle("quota"), re.M)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), datetime.fromisoformat(m.group(3)).replace(tzinfo=timezone.utc)


def scan(upto):
    return {n: status(f"{PREFIX}{n}") for n in range(1, upto + 1)}


def session_hours(factor):
    q = quota()
    if q is None:
        log("nie umiem odczytac quoty — biore ostrozne 3 h")
        return 3.0
    h = min((q[1] - SETUP_MARGIN) / factor, SESSION_CAP)
    return 0.0 if h < MIN_USEFUL else round(h, 1)


def push_kernel(name, code_file, sources, datasets, replace):
    d = REPO / f"Niepotrzebne/kernel-{name}"
    d.mkdir(parents=True, exist_ok=True)
    code = (REPO / code_file).read_text(encoding="utf-8")
    for pat, val in replace.items():
        code = re.sub(pat, val, code, count=1, flags=re.M)
    (d / "train_kernel.py").write_text(code, encoding="utf-8")
    (d / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USER}/{name}", "title": name, "code_file": "train_kernel.py",
        "language": "python", "kernel_type": "script", "is_private": "true",
        "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": datasets, "competition_sources": [],
        "kernel_sources": sources, "model_sources": [],
    }, indent=2), encoding="utf-8")
    out = kaggle("kernels", "push", "-p", str(d), timeout=900)
    log(f"push {name}: {out.strip().splitlines()[-1] if out.strip() else '(brak wyjscia)'}")
    if "Maximum batch GPU session count" in out:
        return 3
    if "not valid kernel sources" in out:
        log(f"STOP: Kaggle odrzucil zrodlo dla {name}")
        return 1
    return 0 if "successfully pushed" in out else 1


def launch_session(prev, nxt, st):
    hours = session_hours(st["factor"])
    if hours == 0.0:
        log(f"quota prawie wyczerpana — nie odpalam {nxt}")
        return 2
    q = quota()
    rc = push_kernel(nxt, "kaggle/02-train.py",
                     [f"{USER}/{PREP}"] + ([f"{USER}/{prev}"] if prev else []),
                     [] if prev else [f"{USER}/{SEED}"],
                     {r"^SESSION_HOURS = .*$": f"SESSION_HOURS = {hours}", r"^EXPECT_RESUME = .*$": "EXPECT_RESUME = True"})
    if rc == 0:
        log(f"{nxt} dostaje limit {hours} h (wspolczynnik quoty {st['factor']:.2f})")
        st["launch"] = {"name": nxt, "hours": hours, "used": q[0] if q else None, "ts": time.time(), "measured": False}
        save_state(st)
    return rc


def calibrate(st, sess):
    """Po zakonczeniu sesji porownaj zuzyta quote z zegarem i popraw wspolczynnik."""
    ln = st.get("launch")
    if not ln or ln.get("measured") or ln.get("used") is None:
        return
    n = int(ln["name"].replace(PREFIX, ""))
    if sess.get(n) != "COMPLETE":
        return
    q = quota()
    if q is None:
        return
    measured = (q[0] - ln["used"]) / (ln["hours"] + 0.25)
    st["factor"] = round(min(2.0, max(1.0, measured * 1.05)), 2)
    ln["measured"] = True
    log(f"{ln['name']}: quota zuzyta {q[0]-ln['used']:.2f} h przy {ln['hours']} h sesji -> wspolczynnik {st['factor']}")
    save_state(st)


def last_step(name, st):
    steps = st.setdefault("steps", {})
    if name in steps:
        return steps[name]
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    kaggle("kernels", "output", f"{USER}/{name}", "-p", str(d), "--file-pattern", r"log\.jsonl$", timeout=600)
    path = next(d.rglob("log.jsonl"), None)
    if not path:
        return None
    step = 0
    for line in path.read_text().splitlines():
        try:
            step = max(step, json.loads(line).get("step", 0))
        except ValueError:
            pass
    steps[name] = step
    save_state(st)
    log(f"{name} skonczyl na kroku {step}/{MAX_STEPS}")
    return step


def sft_phase(last_ok, st):
    log(f"trening doszedl do konca ({last_ok}) — faza SFT")
    fails = 0
    while True:
        if STOP_FILE.exists():
            return
        s = status(SFT)
        if s in ("RUNNING", "QUEUED"):
            time.sleep(POLL)
        elif s == "COMPLETE" and st.get("sft_for") == last_ok:
            break
        elif fails >= MAX_FAILS:
            notify("SFT nie startuje po kilku probach, wymagana decyzja")
            STOP_FILE.touch()
            return
        else:
            q = quota()
            if q and q[1] < 1.0:
                wait = max(600, (q[2] - datetime.now(timezone.utc)).total_seconds() + 600)
                log(f"za malo quoty na SFT, czekam {wait/3600:.1f} h do odnowienia")
                time.sleep(min(wait, 6 * 3600))
                continue
            rc = push_kernel(SFT, "kaggle/03-sft.py", [f"{USER}/{PREP}", f"{USER}/{last_ok}"], [], {})
            if rc == 0:
                st["sft_for"] = last_ok
                save_state(st)
                time.sleep(180)
            else:
                fails += 1
                time.sleep(RETRY_WAIT)
    out = REPO / "Niepotrzebne/sft-final"
    out.mkdir(parents=True, exist_ok=True)
    log("pobieram wynik SFT")
    kaggle("kernels", "output", f"{USER}/{SFT}", "-p", str(out), "--file-pattern", r"(ckpt\.pt|tokenizer\.json)$", timeout=3600)
    ckpt, tok = next(out.rglob("ckpt.pt"), None), next(out.rglob("tokenizer.json"), None)
    if not ckpt or not tok or ckpt.stat().st_size < 1_000_000:
        notify("SFT sie skonczylo, ale nie udalo sie pobrac wyniku")
        STOP_FILE.touch()
        return
    gal = REPO / "Niepotrzebne/sft-gallery.html"
    r = subprocess.run([TORCH_PY, str(REPO / "eval/sft_gallery.py"), str(ckpt), str(tok), "--out", str(gal)],
                       capture_output=True, text=True)
    log(r.stdout[-400:] + r.stderr[-400:])
    DONE_FILE.write_text(f"checkpoint: {ckpt}\ngallery: {gal}\n")
    notify("SFT gotowe, galeria czeka w G-Dev/Niepotrzebne/sft-gallery.html")


def main():
    st = load_state()
    log("lancuch wystartowal")
    ignore = st.get("ignore", 0)
    while True:
        if STOP_FILE.exists():
            log("znaleziono STOP — koncze")
            return 0
        top = max([FIRST + 3, st.get("top", 0) + 3])
        sess = scan(min(top, MAX_SESSION))
        existing = [n for n, s in sess.items() if s != "NONE"]
        st["top"] = max(existing, default=0)
        calibrate(st, sess)
        if any(s in ("RUNNING", "QUEUED") for s in sess.values()):
            time.sleep(POLL)
            continue

        done = [n for n, s in sess.items() if s == "COMPLETE"]
        last_ok = f"{PREFIX}{max(done)}" if done else None
        if last_ok and (last_step(last_ok, st) or 0) >= MAX_STEPS:
            sft_phase(last_ok, st)
            return 0

        base = max(done, default=0)
        fails = sum(1 for n, s in sess.items() if n > max(base, ignore) and s in ("ERROR", "CANCEL", "CANCELACKNOWLEDGED"))
        if fails >= MAX_FAILS:
            q = quota()
            wait = QUOTA_WAIT * 6
            if q:
                wait = max(900, (q[2] - datetime.now(timezone.utc)).total_seconds() + 600)
            notify(f"{fails} bledy startu z rzedu, ponawiam po odnowieniu quoty (za {wait/3600:.1f} h)")
            ignore = st["ignore"] = st["top"]
            save_state(st)
            time.sleep(min(wait, 7 * 24 * 3600))
            continue
        if fails:
            ln = st.get("launch", {})
            left = RETRY_WAIT - (time.time() - ln.get("ts", 0))
            if left > 0:
                time.sleep(left)

        nxt_n = max(existing, default=FIRST - 1) + 1
        rc = launch_session(last_ok, f"{PREFIX}{nxt_n}", st)
        if rc == 0:
            time.sleep(180)
        elif rc == 2:
            q = quota()
            wait = QUOTA_WAIT
            if q and q[1] < MIN_USEFUL + SETUP_MARGIN:
                wait = min(max(900, (q[2] - datetime.now(timezone.utc)).total_seconds() + 600), 6 * 3600)
            time.sleep(wait)
        elif rc == 3:
            time.sleep(600)
        else:
            time.sleep(RETRY_WAIT)


if __name__ == "__main__":
    sys.exit(main())
