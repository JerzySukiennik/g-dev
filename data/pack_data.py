"""Tokenise G-Dev's corpora into flat uint16 binaries for memory-mapped training.

Code documents (those starting with <|file|>) are rewritten into
fill-in-the-middle order half the time, so the model can complete a gap and not
only the end of a file. Prose and Markdown are never rewritten. Training samples
random windows, so the order in which corpora are appended does not matter.

Documents go wholly to train or wholly to val (every 200th document), so no
file leaks across the split. With --delete each corpus text file is removed
once packed, which keeps a Kaggle session inside its 20 GB of disk.

Usage:
    python data/pack_data.py corpus_html.txt corpus_js.txt ... --out-prefix /kaggle/working/dev --delete
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_tokenizer import iter_docs  # noqa: E402

BATCH_DOCS = 1000
FIM_RATE = 0.5
FIM_MAX_CHARS = 30_000
VAL_EVERY = 200


def fim(doc: str, rng: random.Random) -> str:
    header, body = doc.split("\n", 1) if "\n" in doc else (doc, "")
    if len(body) < 50 or len(body) > FIM_MAX_CHARS:
        return doc
    a, b = sorted(rng.sample(range(len(body) + 1), 2))
    return (f"<|fim_prefix|>{header}\n{body[:a]}<|fim_suffix|>{body[b:]}"
            f"<|fim_middle|>{body[a:b]}")


def pack(paths, tok_path: Path, prefix: Path, delete: bool):
    tok = Tokenizer.from_file(str(tok_path))
    assert tok.get_vocab_size() <= 65535, "vocab too large for uint16"
    eot = tok.token_to_id("<|endoftext|>")
    rng = random.Random(1)
    tf, vf = open(f"{prefix}_train.bin", "wb"), open(f"{prefix}_val.bin", "wb")
    counts = {"docs": 0, "train": 0, "val": 0, "fim": 0, "per_source": {}}

    def flush(batch, name):
        for enc in tok.encode_batch(batch):
            ids = np.fromiter(enc.ids, dtype=np.uint16, count=len(enc.ids))
            ids = np.append(ids, np.uint16(eot))
            if counts["docs"] % VAL_EVERY == 0:
                ids.tofile(vf); counts["val"] += len(ids)
            else:
                ids.tofile(tf); counts["train"] += len(ids)
            counts["per_source"][name] = counts["per_source"].get(name, 0) + len(ids)
            counts["docs"] += 1
        batch.clear()

    for path in paths:
        name = path.stem.replace("corpus_", "")
        print(f"packing {name} ...", flush=True)
        batch = []
        for doc in iter_docs(path):
            if doc.startswith("<|file|>") and rng.random() < FIM_RATE:
                doc = fim(doc, rng)
                counts["fim"] += 1
            batch.append(doc)
            if len(batch) >= BATCH_DOCS:
                flush(batch, name)
                if counts["docs"] % 100_000 < BATCH_DOCS:
                    print(f"  {counts['docs']:,} docs  {counts['train']/1e6:.0f}M train tokens", flush=True)
        flush(batch, name)
        if delete:
            path.unlink()
    tf.close(); vf.close()
    print(json.dumps(counts, indent=1))
    Path(f"{prefix}_counts.json").write_text(json.dumps(counts))


def verify(prefix: Path, tok_path: Path):
    tok = Tokenizer.from_file(str(tok_path))
    arr = np.memmap(f"{prefix}_train.bin", dtype=np.uint16, mode="r")
    print(f"train tokens {len(arr):,}  max id {int(arr.max())}  vocab {tok.get_vocab_size()}")
    assert int(arr.max()) < tok.get_vocab_size()
    eot = tok.token_to_id("<|endoftext|>")
    assert int((arr[:3_000_000] == eot).sum()) > 0, "no document separators"
    for frac in (0.1, 0.5, 0.9):
        s = int(len(arr) * frac)
        print(f"--- sample at {frac:.0%} ---")
        print(tok.decode([int(t) for t in arr[s:s + 120]], skip_special_tokens=False)[:500])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", nargs="+", type=Path)
    ap.add_argument("--tokenizer", type=Path, default=Path("data/tokenizer.json"))
    ap.add_argument("--out-prefix", type=Path, default=Path("data/dev"))
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()
    pack(a.corpus, a.tokenizer, a.out_prefix, a.delete)
    verify(a.out_prefix, a.tokenizer)
