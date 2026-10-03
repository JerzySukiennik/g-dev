"""Kaggle kernel: build G-Dev's token binaries on CPU (Internet on, no GPU quota).

Four fetchers run in parallel because the bottleneck is network, not CPU. Their
text lands in /tmp so the saved output holds only dev_train.bin, dev_val.bin,
tokenizer.json and dev_counts.json. A failed source is skipped rather than
fatal: a training run on seven of eight sources beats a kernel that dies after
hours of downloading.

Budgets are characters, tuned for ~4B tokens at ~3.6 characters per token
(measured on a smoke test: HTML 3.6, Markdown 3.8; prose runs higher).
"""

import os
import subprocess
import sys

REPO = "https://github.com/JerzySukiennik/g-dev.git"
WORK = "/kaggle/working"
TMP = "/tmp/gdev"
os.makedirs(TMP, exist_ok=True)

if os.path.exists(f"{TMP}/g-dev"):
    subprocess.run(["git", "-C", f"{TMP}/g-dev", "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "--depth", "1", REPO, f"{TMP}/g-dev"], check=True)
os.chdir(f"{TMP}/g-dev")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "datasets", "tokenizers", "pyarrow"], check=True)

try:
    from kaggle_secrets import UserSecretsClient
    os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    pass

# name, fetcher args, character budget
JOBS = [
    ("html",   ["html"],  1.8e9),
    ("md",     ["md"],    0.6e9),
    ("prose",  ["prose"], 3.2e9),
]
# One process over github-code-clean feeds one file per language group.
CODE_GROUPS = "js:JavaScript:3.2e9;ts:TypeScript:2.2e9;css:CSS:1.1e9;py:Python:2.2e9"

procs = {}
for name, args, chars in JOBS:
    out = f"{TMP}/corpus_{name}.txt"
    log = open(f"{TMP}/{name}.log", "w")
    procs[name] = (subprocess.Popen([sys.executable, "data/fetch_corpus.py", *args, "--out", out,
                                     "--max-chars", str(chars)], stdout=log, stderr=subprocess.STDOUT), [out])
log = open(f"{TMP}/code.log", "w")
procs["code"] = (subprocess.Popen([sys.executable, "data/fetch_corpus.py", "code", "--out", f"{TMP}/code",
                                   "--groups", CODE_GROUPS], stdout=log, stderr=subprocess.STDOUT),
                 [f"{TMP}/corpus_{g.split(':')[0]}.txt" for g in CODE_GROUPS.split(";")])

corpora = []
for name, (p, outs) in procs.items():
    rc = p.wait()
    print(f"{name}: exit {rc}", flush=True)
    print(open(f"{TMP}/{name}.log").read()[-600:], flush=True)
    for out in outs:
        size = os.path.getsize(out) if os.path.exists(out) else 0
        print(f"  {os.path.basename(out)}: {size/1e9:.2f} GB", flush=True)
        if size > 50e6:
            corpora.append(out)

assert corpora, "no source produced data"

subprocess.run([sys.executable, "data/train_tokenizer.py", *corpora, "--out", f"{WORK}/tokenizer.json",
                "--chars-per-file", "150e6"], check=True)
subprocess.run([sys.executable, "data/pack_data.py", *corpora, "--tokenizer", f"{WORK}/tokenizer.json",
                "--out-prefix", f"{WORK}/dev", "--delete"], check=True)
print("done: dev_train.bin, dev_val.bin, tokenizer.json in", WORK)
