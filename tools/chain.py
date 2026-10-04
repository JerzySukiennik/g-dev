#!/usr/bin/env python3
"""Odpala kolejne sesje treningu G-Dev bez udzialu czlowieka.

Dlaczego Python, skoro to samo robil wczesniej skrypt basha: LaunchAgent NIE
MOZE czytac ~/Downloads bashem. Zmierzone, nie zalozone — usluga probna dala:

    [ -r plik ]            OK      (access(2) nie jest bramkowany)
    faktyczny odczyt       BLOKADA
    bash skrypt-z-repo     BLOKADA  ("Operation not permitted")
    listing katalogu       BLOKADA
    python z venv          OK       (czyta, listuje, wykonuje pliki .py)

Most G-Micro dziala pod LaunchAgentem od tygodnia wlasnie dlatego, ze jest
Pythonem. Ten plik istnieje, zeby lancuch mial te sama odpornosc.

Dziala tylko dlatego, ze trening zatrzymuje sie sam przed limitem Kaggle
(--max-hours w train/train.py). Run sciety przez platforme konczy sie jako
CANCEL_ACKNOWLEDGED, a takiego Kaggle NIE przyjmuje jako zrodla dla nastepnego
kernela — sprawdzone dwa razy. Tylko run COMPLETE mozna podpiac, i na tym stoi
caly ten skrypt.

Uruchomienie: przez LaunchAgent fun.gzowo.g-dev.chain, albo recznie:
    .venv/bin/python tools/chain.py [gdev-sN]
Zatrzymanie: dotknij pliku tools/STOP.
Bez argumentu i bez zadnej sesji startuje gdev-s2 z datasetu gdev-ckpt (checkpoint sesji 1).
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path.home() / "Downloads/Claude/Projects/AIe/G-Dev"
KAGGLE = [str(Path.home() / "Downloads/Claude/Projects/AIe/G-Images/.venv/bin/python"),
          "-m", "kaggle"]
CFG = Path.home() / ".kaggle-gdev"          # token konta treningowego G-Dev, osobno od ~/.kaggle
USER = (CFG / "username").read_text().strip()
KAGGLE_ENV = {**os.environ, "KAGGLE_API_TOKEN": str(CFG / "access_token")}
PREFIX = "gdev-s"
PREP = "gdev-prep"
SEED = "gdev-ckpt"           # dataset z checkpointem sesji 1 (zrobionej na innym koncie)
FIRST = 2                    # pierwsza sesja tego konta wznawia sesje 1, wiec numeracja idzie dalej
STOP_FILE = REPO / "tools/STOP"

POLL_SECONDS = 900          # sesja trwa ~10 h, czesciej nie ma sensu
QUOTA_WAIT = 3600           # gdy brak quoty — sprawdzaj raz na godzine
MAX_SESSION = 12
SESSION_CAP = 10.5          # gorny limit sesji Kaggle
SETUP_MARGIN = 0.7          # klonowanie repo, montowanie, zapis 2 GB
MIN_USEFUL = 1.5            # ponizej tego nie warto zaczynac


def log(msg):
    print(f"[{datetime.now():%F %H:%M}] {msg}", flush=True)


def kaggle(*args, timeout=300):
    """Kaggle CLI pisze czesc komunikatow na stderr, wiec laczymy strumienie."""
    try:
        r = subprocess.run(KAGGLE + list(args), capture_output=True, text=True,
                           timeout=timeout, env=KAGGLE_ENV)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def status_of(name):
    return kaggle("kernels", "status", f"{USER}/{name}").strip().splitlines()[-1:] or [""]


def remaining_hours():
    """Godziny GPU, ktore zostaly w tym tygodniu. None, gdy nie da sie odczytac."""
    out = kaggle("quota")
    m = re.search(r"^GPU\s+\S+\s+([\d.]+)h", out, re.M)
    return float(m.group(1)) if m else None


def other_gpu_running(own):
    """Ile innych kerneli GPU konta chodzi teraz. Quota to czas zegarowy i liczy
    sie za kazdy kernel osobno, wiec dwa rownolegle zjadaja ja dwa razy szybciej."""
    out = kaggle("kernels", "list", "--mine", "--sort-by", "dateRun", "--page-size", "6")
    n = 0
    for line in out.splitlines()[2:]:
        ref = line.split()[0] if line.split() else ""
        name = ref.split("/")[-1]
        if not name or name in (own, PREP) or name.startswith("gdev-s") or "prep" in name:
            continue
        if "RUNNING" in " ".join(status_of(name)):
            n += 1
    return n


def session_hours(own="", slots=1):
    """Ile ma trwac nastepna sesja.

    Run sciety przez WYCZERPANA QUOTE konczy sie tak samo jak sciety przez
    platforme — jako CANCELLED — czyli jego checkpoint jest nie do wznowienia.
    Dlatego sesja nigdy nie jest dluzsza niz to, co realnie zostalo,
    a gdy obok chodzi inny kernel GPU (G-Weird), quota dzieli sie przez `slots`.
    """
    rem = remaining_hours()
    if rem is None:
        log("nie umiem odczytac quoty — biore ostrozne 8 h")
        return 8.0
    h = min((rem - SETUP_MARGIN) / slots, SESSION_CAP)
    return 0.0 if h < MIN_USEFUL else round(h, 1)


def detect_current():
    """Ostatnia istniejaca sesja. Usluga wstaje po restarcie bez pamieci."""
    found = None
    for i in range(1, MAX_SESSION + 1):
        if "KernelWorkerStatus" in " ".join(status_of(f"{PREFIX}{i}")):
            found = f"{PREFIX}{i}"
    return found


def launch_next(prev, nxt):
    """0 = odpalone, 1 = blad wymagajacy czlowieka, 2 = brak quoty, 3 = brak wolnego slotu GPU."""
    hours = session_hours(nxt, 1 + other_gpu_running(nxt))
    if hours == 0.0:
        log(f"quota prawie wyczerpana — czekam, nie odpalam {nxt}")
        return 2

    d = REPO / f"Niepotrzebne/kernel-{nxt}"
    d.mkdir(parents=True, exist_ok=True)
    code = (REPO / "kaggle/02-train.py").read_text(encoding="utf-8")
    code = re.sub(r"^SESSION_HOURS = .*$", f"SESSION_HOURS = {hours}",
                  code, count=1, flags=re.M)
    code = re.sub(r"^EXPECT_RESUME = .*$", "EXPECT_RESUME = True",
                  code, count=1, flags=re.M)
    (d / "train_kernel.py").write_text(code, encoding="utf-8")
    (d / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USER}/{nxt}", "title": nxt, "code_file": "train_kernel.py",
        "language": "python", "kernel_type": "script", "is_private": "true",
        "enable_gpu": "true", "enable_internet": "true",
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [] if prev else [f"{USER}/{SEED}"], "competition_sources": [],
        "kernel_sources": [f"{USER}/{PREP}"] + ([f"{USER}/{prev}"] if prev else []),
        "model_sources": [],
    }, indent=2), encoding="utf-8")

    log(f"{nxt} dostaje limit {hours} h")
    out = kaggle("kernels", "push", "-p", str(d), timeout=900)
    log(f"push {nxt}: {out.strip().splitlines()[-1] if out.strip() else '(brak wyjscia)'}")

    # Kaggle potrafi ODRZUCIC zrodlo i mimo to wystartowac run — wtedy trening
    # leci od zera i cicho marnuje quote. To trzeba zlapac tutaj.
    if "Maximum batch GPU session count" in out:
        return 3
    if "not valid kernel sources" in out:
        log(f"STOP: Kaggle odrzucil {prev} jako zrodlo — {nxt} trenowalby od zera.")
        return 1
    return 0 if "successfully pushed" in out else 1


def main():
    current = sys.argv[1] if len(sys.argv) > 1 else None
    if not current:
        current = detect_current()
    if not current:
        log("zadnej sesji nie ma — startuje pierwsza (z checkpointu SEED)")
        while True:
            if STOP_FILE.exists():
                return 0
            rc = launch_next(None, f"{PREFIX}{FIRST}")
            if rc == 0:
                current = f"{PREFIX}{FIRST}"
                break
            if rc == 1:
                STOP_FILE.touch()
                log("wymagana decyzja czlowieka — zapisalem STOP")
                return 0
            time.sleep(600 if rc == 3 else QUOTA_WAIT)
        time.sleep(120)
    n = int(re.sub(r"\D", "", current))
    log(f"lancuch wystartowal, obserwuje {current}")

    while True:
        if STOP_FILE.exists():
            log("znaleziono STOP — koncze")
            return 0

        s = " ".join(status_of(current))
        if "COMPLETE" in s:
            log(f"{current} zakonczony")
            if n >= MAX_SESSION:
                log(f"osiagnieto MAX_SESSION={MAX_SESSION} — koncze")
                return 0
            nxt = f"{PREFIX}{n + 1}"
            rc = launch_next(current, nxt)
            if rc == 0:
                current, n = nxt, n + 1
                log(f"przechodze na {current}")
                time.sleep(120)
            elif rc == 2:
                time.sleep(QUOTA_WAIT)
            elif rc == 3:
                time.sleep(600)
            else:
                # Zero, nie blad: KeepAlive restartuje tylko po niezerowym
                # wyjsciu, wiec blad wymagajacy czlowieka konczymy czysto,
                # zeby usluga nie probowala w kolko tego samego.
                STOP_FILE.touch()
                log("wymagana decyzja czlowieka — zapisalem STOP")
                return 0
        elif "ERROR" in s or "CANCEL" in s:
            log(f"{current} w stanie koncowym: {s} — koncze")
            STOP_FILE.touch()
            return 0

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
