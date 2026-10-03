# G-Dev

An English coding model trained from scratch, aimed at behaving like a small
coding agent: you talk to it, it writes code, calls tools in a fixed format and
reads their results. Eighth member of the G family.

Status: scaffold. Model code is inherited from G-Mini (RoPE, RMSNorm, SwiGLU,
KV cache); data pipeline, tokenizer and kernels come next.

## Honest scope

A ~200M model trained on ~4B tokens is a small autocomplete-and-chat assistant
for code, not a Claude Code replacement. Qwen2.5-Coder-0.5B reaches ~28% on
HumanEval after ~5.5T tokens; this model sees roughly a thousand times fewer.
Expect single-digit to low-teens pass@1 and a model that follows a simple
tool-call format, not one that fixes real repositories alone.

## Plan

1. Tokenizer: 32k BPE on code and English, every digit split, tool-call tokens reserved.
2. Pretraining mix, permissive licenses only: The Stack v2 (permissive subset),
   FineWeb-Edu for English, plus docs and Q&A. Fill-in-the-middle on part of the code.
3. SFT: chat and instruction data, then tool-use traces in one fixed text format.
4. Eval: HumanEval and MBPP pass@1, plus execution of generated tool calls.

## Layout

| path | what |
|---|---|
| `model/` | transformer, inherited from G-Mini |
| `train/` | pretraining loop with `--max-hours` self-termination |
| `data/` | corpus download, filtering, tokenizer, packing |
| `kaggle/` | kernels that run it on free Kaggle GPUs |
| `tools/` | session chain that resumes training automatically |
| `bench/` | throughput probe for choosing the final size |
| `eval/` | HumanEval, MBPP, tool-call checks |

MIT licensed.
