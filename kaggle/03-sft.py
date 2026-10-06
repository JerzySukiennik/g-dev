"""Kaggle notebook cell: fine-tune G-Dev on the verified web pages (about 15 minutes on T4 x2).

Attach as notebook inputs, from your own work: gdev-prep (for tokenizer.json) and
the latest training session (for ckpt.pt). Do not attach the gdev-ckpt dataset:
it is the old step-5518 checkpoint and would be picked first.

Paste into a notebook cell, then Save Version, Save & Run All. The fine-tuned
checkpoint lands in /kaggle/working/sft.
"""

import glob
import subprocess
import sys

subprocess.run("rm -rf /kaggle/working/g-dev && git clone --depth 1 https://github.com/JerzySukiennik/g-dev.git /kaggle/working/g-dev", shell=True, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers"], check=True)


def find(pattern):
    hits = sorted(glob.glob(f"/kaggle/input/**/{pattern}", recursive=True))
    return hits[0] if hits else None


ckpt, tok = find("ckpt.pt"), find("tokenizer.json")
assert ckpt and tok, "attach gdev-prep (tokenizer.json) and the last gdev-sN (ckpt.pt)"
print("checkpoint:", ckpt)
print("tokenizer :", tok)
data = "/kaggle/working/g-dev/data/web_sft/data"
subprocess.run([sys.executable, "train/finetune.py", "--init", ckpt, "--tokenizer", tok,
                "--train", f"{data}/webpages_train.jsonl", "--val", f"{data}/webpages_val.jsonl",
                "--out", "/kaggle/working/sft"], cwd="/kaggle/working/g-dev", check=True)
subprocess.run(["cp", tok, "/kaggle/working/sft/tokenizer.json"], check=True)
