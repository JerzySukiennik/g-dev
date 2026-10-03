"""Kaggle kernel: pretrain G-Dev, resuming across sessions.

Run over and over by tools/chain.py. Each session picks up the previous
session's checkpoint (weights, optimiser moments, step, RNG), trains until its
own time limit and leaves a checkpoint for the next one.

Inputs, attached by the chain as kernel sources (no datasets to publish):
  - gdev-prep   dev_train.bin, dev_val.bin, tokenizer.json
  - gdev-sN     the previous session's run1/ckpt.pt (absent on session 1)

Traps carried over from G-Micro and G-Mini:

  Mount depth is not fixed (`/kaggle/input/<slug>/` and
  `/kaggle/input/datasets/<owner>/<slug>/` both occur), so every lookup is a
  recursive glob.

  Kaggle can reject a kernel source and still start the run, which then trains
  from random weights and silently burns quota. The chain sets EXPECT_RESUME
  for every session after the first, and a missing checkpoint then aborts here
  instead of restarting from step 0.

  Resumed sessions keep the default learning rate. G-Mini lowered it on resume
  because its warm start needed a gentle peak; G-Dev starts from scratch, and
  changing the peak mid-run would distort the cosine schedule.
"""

import glob
import os
import shutil
import subprocess
import sys

REPO = "https://github.com/JerzySukiennik/g-dev.git"
WORK = "/kaggle/working"
OUT = f"{WORK}/run1"

SESSION_HOURS = 10.5
EXPECT_RESUME = False

if os.path.exists(f"{WORK}/g-dev"):
    subprocess.run(["git", "-C", f"{WORK}/g-dev", "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "--depth", "1", REPO, f"{WORK}/g-dev"], check=True)
os.chdir(f"{WORK}/g-dev")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers"], check=True)


def find(pattern):
    hits = sorted(glob.glob(f"/kaggle/input/**/{pattern}", recursive=True))
    return hits[0] if hits else None


data_train = find("dev_train.bin")
assert data_train, "dev_train.bin not found: attach gdev-prep as a kernel source"
data_prefix = data_train[: -len("_train.bin")]
print(f"data: {data_prefix}")

os.makedirs(OUT, exist_ok=True)
tok = find("tokenizer.json")
if tok:
    shutil.copy(tok, f"{OUT}/tokenizer.json")

resume = find("ckpt.pt")
if EXPECT_RESUME and not resume:
    raise SystemExit("EXPECT_RESUME is set but no ckpt.pt was mounted: refusing to restart from step 0")

cmd = [sys.executable, "train/train.py", "--data", data_prefix, "--out", OUT,
       "--max-hours", str(SESSION_HOURS)]
if resume:
    subprocess.run(["cp", resume, f"{OUT}/ckpt.pt"], check=True)
    print(f"resuming from {resume}")
    cmd += ["--resume"]
else:
    print("session 1: training from scratch")

subprocess.run(cmd, check=True)
print(f"\ncheckpoint in {OUT}")
