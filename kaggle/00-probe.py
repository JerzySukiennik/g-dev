"""Kaggle kernel: measure G-Dev's throughput at 1024 and 2048 context. T4 x2, a few minutes.

Paste or push this file; it clones the repo and calls bench/size_probe.py, which
cannot be pasted on its own because it locates the repo through __file__.
"""

import os
import subprocess
import sys

REPO = "https://github.com/JerzySukiennik/g-dev.git"
WORK = "/kaggle/working"

if os.path.exists(f"{WORK}/g-dev"):
    subprocess.run(["git", "-C", f"{WORK}/g-dev", "pull", "--ff-only"], check=True)
else:
    subprocess.run(["git", "clone", "--depth", "1", REPO, f"{WORK}/g-dev"], check=True)
os.chdir(f"{WORK}/g-dev")

for block in ("1024", "2048"):
    print(f"\n######## context {block} ########", flush=True)
    subprocess.run([sys.executable, "bench/size_probe.py"], check=True,
                   env={**os.environ, "PROBE_BLOCK": block})
