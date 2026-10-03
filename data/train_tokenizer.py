"""Train G-Dev's tokenizer: 32k byte-level BPE for code and English, digits split.

Two decisions carry over from the earlier models. Every digit is its own token
(G-Mini's lesson: multi-digit tokens make a model copy numbers badly). The
pre-split keeps a newline together with the indentation that follows it, so a
nested block costs one token for its whitespace instead of one per level.

The chat and tool tokens are reserved here, before any model sees them, because
adding a token later means resizing the embedding of a trained model.

Usage:
    python data/train_tokenizer.py corpus_html.txt corpus_js.txt ... --out data/tokenizer.json
"""

import argparse
import random
import sys
from pathlib import Path

from tokenizers import Regex, Tokenizer, decoders, models, pre_tokenizers, processors, trainers

DOC_SEP = "<|doc|>"
VOCAB = 32768

SPECIAL_TOKENS = [
    "<|pad|>", "<|endoftext|>",
    "<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>",
    "<|file|>",
    "<|system|>", "<|user|>", "<|assistant|>", "<|end|>",
    "<|tool_call|>", "<|tool_result|>",
] + [f"<|reserved_{i}|>" for i in range(8)]

SPLIT = (r"""(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}|"""
         r""" ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+[ \t]*|\s+(?!\S)|\s+""")


def iter_docs(path: Path):
    buf = []
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.rstrip("\n") == DOC_SEP:
                doc = "".join(buf)
                buf.clear()
                if doc.strip():
                    yield doc
            else:
                buf.append(line)


def sample(paths, budget_per_file, seed=0):
    rng = random.Random(seed)
    for path in paths:
        used = 0
        keep = 0.35
        for doc in iter_docs(path):
            if rng.random() > keep:
                continue
            if doc.startswith("<|file|>"):
                doc = doc.split("\n", 1)[-1]
            yield doc[:20000]
            used += min(len(doc), 20000)
            if used >= budget_per_file:
                break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/tokenizer.json"))
    ap.add_argument("--chars-per-file", type=float, default=250e6)
    a = ap.parse_args()

    tok = Tokenizer(models.BPE(byte_fallback=False))
    tok.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Split(Regex(SPLIT), behavior="isolated"),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
    ])
    tok.decoder = decoders.ByteLevel()
    tok.post_processor = processors.ByteLevel(trim_offsets=False)
    trainer = trainers.BpeTrainer(
        vocab_size=VOCAB, special_tokens=SPECIAL_TOKENS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(), min_frequency=2, show_progress=False)
    tok.train_from_iterator(sample(a.corpus, a.chars_per_file), trainer)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tok.save(str(a.out))

    import re
    multi = [t for t in tok.get_vocab() if re.fullmatch(r"\s?\d{2,}", t)]
    print(f"vocab {tok.get_vocab_size()}, multi-digit tokens {len(multi)} (must be 0)")
    assert not multi, multi[:10]
    tests = ["const ball = { x: 10, y: 20 };\n    if (ball.x > 1998) {\n        ball.x = 0;\n    }",
             ".card:hover { transform: translateY(-4px) scale(1.02); transition: .2s ease; }",
             "def update(dt):\n    self.pos += self.vel * dt",
             "<|user|>make the button bounce<|end|><|assistant|><|tool_call|>"]
    for s in tests:
        ids = tok.encode(s).ids
        assert tok.decode(ids, skip_special_tokens=False) == s, f"roundtrip failed: {s!r}"
        print(f"{len(ids):3d} tok / {len(s):3d} ch  {s[:50]!r}")
    for t in SPECIAL_TOKENS:
        assert tok.token_to_id(t) is not None


if __name__ == "__main__":
    sys.exit(main())
