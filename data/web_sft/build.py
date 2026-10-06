"""Turn verified pages into G-Dev's SFT file: chat-formatted text plus the character
offset where the answer starts, so training can mask the loss to the answer only.

Usage:
    python data/web_sft/build.py verified.jsonl TOKENIZER out_prefix [--val 0.03]
"""

import argparse
import json
import random
import statistics
from pathlib import Path

from tokenizers import Tokenizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verified")
    ap.add_argument("tokenizer")
    ap.add_argument("out_prefix")
    ap.add_argument("--val", type=float, default=0.03)
    ap.add_argument("--max-tokens", type=int, default=2047)
    a = ap.parse_args()

    tok = Tokenizer.from_file(a.tokenizer)
    rows = [json.loads(l) for l in open(a.verified, encoding="utf-8")]
    kept, dropped, lens, per = [], 0, [], {}
    for r in rows:
        if not r["ok"]:
            dropped += 1
            continue
        head = f"<|user|>{r['prompt']}<|end|><|assistant|>"
        text = head + r["response"] + "<|end|>"
        n = len(tok.encode(text).ids)
        if n > a.max_tokens:
            dropped += 1
            continue
        lens.append(n)
        per.setdefault(r["pattern"], []).append(n)
        kept.append({"id": r["id"], "pattern": r["pattern"], "text": text, "answer_from": len(head)})
    random.Random(0).shuffle(kept)
    nval = int(len(kept) * a.val)
    for name, part in (("val", kept[:nval]), ("train", kept[nval:])):
        with open(f"{a.out_prefix}_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"kept {len(kept)} dropped {dropped}  train {len(kept)-nval} val {nval}")
    print(f"tokens/example: mean {statistics.mean(lens):.0f} median {statistics.median(lens):.0f} max {max(lens)}  total {sum(lens)/1e6:.2f}M")
    for p, v in sorted(per.items(), key=lambda x: -statistics.mean(x[1])):
        print(f"  {p:16s} n={len(v):4d} mean {statistics.mean(v):5.0f} max {max(v)}")


if __name__ == "__main__":
    main()
