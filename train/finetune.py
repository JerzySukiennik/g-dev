"""Supervised fine-tuning: teach the pretrained G-Dev to answer a description with a page.

The base model only continues text. After `<|user|>description<|end|><|assistant|>`
it has to write the whole page and then stop with `<|end|>`. Three choices matter:

  Masked loss. Only the answer (the page and its closing `<|end|>`) is scored.
  Scoring the description too would train the model to write requests.

  Packing. Examples average ~400 tokens against a 2048 window, so several are
  packed into each sequence, never split across two, and the rest is padding that
  is not scored. Attention is not blocked between packed examples, the same as in
  pretraining.

  Gentle learning rate. Narrow data and a few hundred steps: a high rate would
  trade the model's general code knowledge for the 18 patterns it is shown.

Input files are produced by data/web_sft/build.py: one JSON per line with `text`
and `answer_from`, the character offset where the answer begins.

Run:
    python train/finetune.py --init run1/ckpt.pt --tokenizer tokenizer.json \
        --train data/web_sft/data/webpages_train.jsonl --val data/web_sft/data/webpages_val.jsonl --out sft
"""

import argparse
import json
import math
import random
import sys
import time
import pathlib
from pathlib import Path

import numpy as np
import torch
from tokenizers import Tokenizer

sys.modules.setdefault("pathlib._local", pathlib)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.gpt import GPT, GPTConfig  # noqa: E402
from train.train import lr_at, save_ckpt  # noqa: E402


def encode_examples(path, tok, block):
    """-> list of (ids, answer_mask) with the answer mask True where the token is scored."""
    out = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        enc = tok.encode(r["text"])
        ids = enc.ids
        if len(ids) > block:
            continue
        mask = [start >= r["answer_from"] for start, _ in enc.offsets]
        out.append((ids, mask))
    return out


class Packer:
    """Shuffles examples each epoch and packs them into fixed-size sequences."""

    def __init__(self, examples, block, pad_id, seed=0):
        self.examples, self.block, self.pad, self.rng = examples, block, pad_id, random.Random(seed)
        self.seqs = []
        self.cursor = 0
        self.epoch = 0
        self._repack()

    def _repack(self):
        order = list(range(len(self.examples)))
        self.rng.shuffle(order)
        seqs, cur_ids, cur_mask = [], [], []
        for i in order:
            ids, mask = self.examples[i]
            if len(cur_ids) + len(ids) > self.block + 1:
                seqs.append((cur_ids, cur_mask))
                cur_ids, cur_mask = [], []
            cur_ids += ids
            cur_mask += mask
        if cur_ids:
            seqs.append((cur_ids, cur_mask))
        self.seqs, self.cursor = seqs, 0
        self.epoch += 1

    def tokens_per_epoch(self):
        return sum(len(ids) for ids, _ in self.examples)

    def batch(self, n, device):
        T = self.block
        x = np.full((n, T), self.pad, dtype=np.int64)
        y = np.full((n, T), -1, dtype=np.int64)
        for b in range(n):
            if self.cursor >= len(self.seqs):
                self._repack()
            ids, mask = self.seqs[self.cursor]
            self.cursor += 1
            m = len(ids) - 1
            x[b, :m] = ids[:m]
            tgt = np.array(ids[1:], dtype=np.int64)
            y[b, :m] = np.where(np.array(mask[1:], dtype=bool), tgt, -1)
        xt, yt = torch.from_numpy(x), torch.from_numpy(y)
        return xt.to(device), yt.to(device)


@torch.no_grad()
def evaluate(model, examples, block, pad, batch, ctx, device):
    model.eval()
    p = Packer(examples, block, pad, seed=1)
    n_seq = len(p.seqs)
    total, count = 0.0, 0
    for _ in range(max(1, n_seq // batch)):
        x, y = p.batch(batch, device)
        with ctx:
            _, loss = model(x, targets=y, return_logits=False)
        total += loss.mean().item()
        count += 1
    model.train()
    return total / count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", type=Path, required=True)
    ap.add_argument("--tokenizer", type=str, required=True)
    ap.add_argument("--train", type=str, required=True)
    ap.add_argument("--val", type=str, required=True)
    ap.add_argument("--out", type=Path, default=Path("checkpoints/sft"))
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=0, help="override the epoch-based step count")
    ap.add_argument("--lr", type=float, default=6e-5)
    ap.add_argument("--min-lr", type=float, default=6e-6)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--eval-every", type=int, default=50)
    ap.add_argument("--log-every", type=int, default=10)
    ap.add_argument("--single-gpu", action="store_true")
    ap.add_argument("--threads", type=int, default=2, help="CPU threads when there is no GPU")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(args.threads)
    use_amp = device == "cuda"
    bf16 = use_amp and torch.cuda.get_device_capability()[0] >= 8
    ctx = (torch.autocast(device_type="cuda", dtype=torch.bfloat16 if bf16 else torch.float16)
           if use_amp else torch.autocast(device_type="cpu", enabled=False))
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp and not bf16)

    ck = torch.load(args.init, map_location=device, weights_only=False)
    cfg = GPTConfig(**ck["config"])
    model = GPT(cfg).to(device)
    model.load_state_dict(ck["model"])
    print(f"loaded {args.init}: pretrain step {ck['step']}")

    tok = Tokenizer.from_file(args.tokenizer)
    pad = tok.token_to_id("<|pad|>")
    train_ex = encode_examples(args.train, tok, cfg.block_size)
    val_ex = encode_examples(args.val, tok, cfg.block_size)
    train = Packer(train_ex, cfg.block_size, pad)
    scored = sum(sum(m) for _, m in train_ex)
    print(f"{len(train_ex)} train / {len(val_ex)} val examples, {train.tokens_per_epoch()/1e6:.2f}M tokens "
          f"per epoch, {scored/1e6:.2f}M of them scored, {len(train.seqs)} packed sequences")

    seqs_per_step = args.batch_size * args.grad_accum
    max_steps = args.max_steps or max(1, int(len(train.seqs) * args.epochs / seqs_per_step))
    print(f"{max_steps} steps of {seqs_per_step} sequences")

    decay = [p for _, p in model.named_parameters() if p.dim() >= 2]
    no_decay = [p for _, p in model.named_parameters() if p.dim() < 2]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": 0.0}, {"params": no_decay, "weight_decay": 0.0}],
                            lr=args.lr, betas=(0.9, 0.95), eps=1e-8, fused=(device == "cuda"))

    base = evaluate(model, val_ex, cfg.block_size, pad, args.batch_size, ctx, device)
    print(f"val loss before SFT: {base:.4f}", flush=True)

    if not args.single_gpu and device == "cuda" and torch.cuda.device_count() > 1:
        print(f"using {torch.cuda.device_count()} GPUs via DataParallel")
        model = torch.nn.DataParallel(model)

    args.out.mkdir(parents=True, exist_ok=True)
    log = args.out / "log.jsonl"
    best, step = float("inf"), 0
    model.train()
    t0 = time.time()
    while step < max_steps:
        lr = lr_at(step, args.warmup, max_steps, args.lr, args.min_lr)
        for g in opt.param_groups:
            g["lr"] = lr
        opt.zero_grad(set_to_none=True)
        for _ in range(args.grad_accum):
            x, y = train.batch(args.batch_size, device)
            with ctx:
                _, loss = model(x, targets=y, return_logits=False)
                loss = loss.mean() / args.grad_accum
            scaler.scale(loss).backward()
        if args.grad_clip > 0:
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        scaler.step(opt)
        scaler.update()
        step += 1

        if step % args.log_every == 0:
            tl = loss.item() * args.grad_accum
            print(f"step {step:>4}/{max_steps}  loss {tl:6.3f}  lr {lr:.2e}  epoch {train.epoch}  "
                  f"{(time.time()-t0)/args.log_every:.1f}s/step", flush=True)
            with log.open("a") as f:
                f.write(json.dumps({"step": step, "train_loss": tl, "lr": lr}) + "\n")
            t0 = time.time()
        if step % args.eval_every == 0 or step == max_steps:
            v = evaluate(model, val_ex, cfg.block_size, pad, args.batch_size, ctx, device)
            print(f"  -> val {v:.4f}", flush=True)
            with log.open("a") as f:
                f.write(json.dumps({"step": step, "val_loss": v}) + "\n")
            if v < best:
                best = v
                save_ckpt(args.out / "best.pt", model, opt, step, best, cfg, args)
            t0 = time.time()

    save_ckpt(args.out / "ckpt.pt", model, opt, step, best, cfg, args)
    print(f"done: {step} steps, val {base:.4f} -> best {best:.4f}")


if __name__ == "__main__":
    main()
