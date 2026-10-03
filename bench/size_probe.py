"""Choose G-Dev's size by measuring throughput on the real T4, at both context lengths.

G-Mini found the T4's memory wall between 204M and 282M parameters at a 1024
context. G-Dev wants 2048 (agent traces and whole HTML files are long), and
attention memory grows with context, so the wall moves. Interpolating this
hardware has been wrong by ~2x twice, so this measures instead: each candidate
shape at each context, backing off the micro-batch until it fits.

G-Micro 110M runs as an anchor. At 1024 it must come back near 16,800 tok/s;
if it does not, distrust every other line.

Run on Kaggle with a T4 x2 accelerator (kaggle/00-probe.py runs both contexts):

    PROBE_BLOCK=2048 python bench/size_probe.py
"""

import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.gpt import GPT, GPTConfig  # noqa: E402

# (label, n_layer, n_head, n_embd, vocab_size). head_dim stays 64 throughout.
# Vocabulary is per-candidate on purpose: a 48k softmax is real compute, so
# measuring G-Micro with G-Mini's vocabulary would compare it against a number it
# never produced and quietly break the anchor.
CANDIDATES = [
    ("G-Micro 110M (anchor)", 12, 12, 768, 32000),
    ("16x768", 16, 12, 768, 32768),
    ("20x768", 20, 12, 768, 32768),
    ("24x768", 24, 12, 768, 32768),
    ("18x896", 18, 14, 896, 32768),
    ("20x896", 20, 14, 896, 32768),
]
BLOCK = int(__import__("os").environ.get("PROBE_BLOCK", 1024))
STEPS = 3          # optimiser steps timed (each is ACCUM micro-batches)
WARMUP = 1
# Real training accumulates gradients to a ~65k-token step (train/train.py:
# batch 8 x grad_accum 8 x block 1024) so the optimiser runs once per eight
# micro-batches. A first version of this probe stepped the optimiser after
# every micro-batch and came out roughly 2x pessimistic — it predicted 21h for
# G-Micro's 2B tokens where the real run took about 10. Matching the real step
# size is the difference between a usable estimate and a misleading one.
TOKENS_PER_STEP = 65536


def ffn_hidden(n_embd):
    """G-Micro's ratio: ~8/3 x n_embd, rounded to a multiple of 128."""
    return int(round(n_embd * 8 / 3 / 128) * 128)


def try_config(label, n_layer, n_head, n_embd, vocab_size, micro_batch):
    cfg = GPTConfig(n_layer=n_layer, n_head=n_head, n_embd=n_embd,
                    ffn_hidden=ffn_hidden(n_embd), block_size=BLOCK,
                    vocab_size=vocab_size)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    model = GPT(cfg).to(device)
    n_params = model.num_params()

    # Same precision policy as train/train.py: fp16 on Turing, where bf16 has
    # no tensor cores and runs at roughly half speed.
    bf16 = device == "cuda" and torch.cuda.get_device_capability()[0] >= 8
    amp_dtype = torch.bfloat16 if bf16 else torch.float16
    scaler = torch.cuda.amp.GradScaler(enabled=(device == "cuda" and not bf16))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, betas=(0.9, 0.95))

    x = torch.randint(0, cfg.vocab_size, (micro_batch, BLOCK), device=device)
    y = torch.randint(0, cfg.vocab_size, (micro_batch, BLOCK), device=device)

    accum = max(1, TOKENS_PER_STEP // (micro_batch * BLOCK))
    t0 = None
    for step in range(STEPS):
        for _ in range(accum):
            with torch.autocast(device_type="cuda", dtype=amp_dtype, enabled=device == "cuda"):
                _, loss = model(x, targets=y, return_logits=False)
            scaler.scale(loss / accum).backward()
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)
        if step == WARMUP - 1:
            torch.cuda.synchronize()
            t0 = time.time()
    torch.cuda.synchronize()

    elapsed = time.time() - t0
    measured_steps = STEPS - WARMUP
    tok_per_s = micro_batch * BLOCK * accum * measured_steps / elapsed
    peak_gb = torch.cuda.max_memory_allocated() / 1e9

    del model, opt, x, y
    torch.cuda.empty_cache()
    return n_params, tok_per_s, peak_gb, accum


def main():
    if not torch.cuda.is_available():
        raise SystemExit("no GPU — this probe only means anything on the real hardware")
    name = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"block_size={BLOCK}")
    print(f"GPU: {name}  ({total:.1f} GB, {torch.cuda.device_count()} visible)")
    print(f"capability {torch.cuda.get_device_capability()}  "
          f"-> {'bf16' if torch.cuda.get_device_capability()[0] >= 8 else 'fp16'}\n")

    results = []
    for label, L, H, E, V in CANDIDATES:
        # Back off until it fits rather than reporting a flat failure:
        # "trains at micro-batch 4" is a usable answer, "OOM" is not.
        for micro_batch in (8, 4, 2, 1):
            try:
                n, tps, peak, accum = try_config(label, L, H, E, V, micro_batch)
                print(f"{label:<22} {n/1e6:>6.0f}M  micro_batch={micro_batch}x{accum}  "
                      f"{tps:>8,.0f} tok/s  peak {peak:>5.1f} GB")
                results.append((label, n, tps, micro_batch, peak))
                break
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                print(f"{label:<22} micro_batch={micro_batch}: OOM, zmniejszam")
        else:
            print(f"{label:<22} nie mieści się nawet przy micro_batch=1")

    # Single-GPU numbers above; training runs DataParallel across both cards,
    # which measured ~1.7x on G-Micro rather than 2x.
    DP = 1.7
    print(f"\nprzewidywany czas treningu (DataParallel x{DP}, obie karty):")
    print(f"{'model':<26}{'tok/param':>10}{'tokenów':>10}{'godzin':>9}{'tygodni quoty':>15}")
    for label, n, tps, _, _ in results:
        for tok_per_param in (8, 20):
            d = tok_per_param * n
            hours = d / (tps * DP) / 3600
            print(f"{label:<22}{tok_per_param:>10}{d/1e9:>9.1f}B{hours:>8.0f}h{hours/30:>14.1f}")


if __name__ == "__main__":
    main()
