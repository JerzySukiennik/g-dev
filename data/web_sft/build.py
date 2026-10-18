"""Turn verified pages and conversations into G-Dev's SFT files.

Each line holds the chat text and the character spans of every assistant answer,
so training scores the pages (and their closing <|end|>) and nothing the user said.
A conversation is dropped if any of its pages failed verification or it does not fit
the context window.

Usage:
    python data/web_sft/build.py DIR TOKENIZER OUT_PREFIX [--val 0.03]
    (DIR holds pages.jsonl, verified.jsonl and convs.jsonl from gen.py and verify.mjs)
"""

import argparse
import json
import random
import statistics
from pathlib import Path

from tokenizers import Tokenizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("tokenizer")
    ap.add_argument("out_prefix")
    ap.add_argument("--val", type=float, default=0.03)
    ap.add_argument("--max-tokens", type=int, default=2047)
    a = ap.parse_args()

    tok = Tokenizer.from_file(a.tokenizer)
    ok = {}
    for line in open(a.dir / "verified.jsonl", encoding="utf-8"):
        r = json.loads(line)
        ok[r["id"]] = r["response"] if r["ok"] else None
    kept, dropped, lens, kinds = [], {"failed": 0, "long": 0}, [], {}
    for line in open(a.dir / "convs.jsonl", encoding="utf-8"):
        c = json.loads(line)
        if any(ok.get(t["page"]) is None for t in c["turns"]):
            dropped["failed"] += 1
            continue
        text, spans = "", []
        for t in c["turns"]:
            text += f"<|user|>{t['prompt']}<|end|><|assistant|>"
            start = len(text)
            text += ok[t["page"]] + "<|end|>"
            spans.append([start, len(text)])
        n = len(tok.encode(text).ids)
        if n > a.max_tokens:
            dropped["long"] += 1
            continue
        lens.append(n)
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        kept.append({"id": c["id"], "kind": c["kind"], "pattern": c["pattern"], "text": text, "spans": spans})
    random.Random(0).shuffle(kept)
    nval = int(len(kept) * a.val)
    for name, part in (("val", kept[:nval]), ("train", kept[nval:])):
        with open(f"{a.out_prefix}_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"kept {len(kept)} {kinds}, dropped {dropped}, train {len(kept)-nval} val {nval}")
    print(f"tokens/conversation: mean {statistics.mean(lens):.0f} max {max(lens)} total {sum(lens)/1e6:.2f}M")


if __name__ == "__main__":
    main()
