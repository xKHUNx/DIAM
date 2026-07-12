# AR Baseline: Fine-tuned Qwen3-8B — Design / Experiment Plan

**Date:** 2026-07-11
**Author:** Goh Kun Shun
**Status:** Approved for implementation

## 1. Motivation

Reviewer comment on the DIAM paper:

> "The addressee recognition experiment could benefit from more (and better) models
> and a better analysis. Even training a smaller LLM could be interesting and a nice
> comparison."

The reviewer's firm asks are (a) **more/better models** and (b) **better analysis**.
Fine-tuning a smaller open LLM is the reviewer's explicit *suggestion* ("even
training… could be interesting"). This spec covers that suggested item: a
**fine-tuned Qwen3-8B** addressee-recognition (AR) baseline that is directly
comparable to the existing prompted `gpt-5.2` baseline.

(The broader "more prompted models + naïve floor + better analysis" package is
tracked separately as follow-up; this spec is scoped to the fine-tuned model.)

## 2. Task recap

For every Elementary Unit (EDU) in a session, predict its addressee set, chosen
from a per-session candidate pool. Evaluation (unchanged, `evaluate_ar_baseline.py`):
set-based **Exact Match** and **F1** per EDU, broken down by scenario
(everyone / single / multi) and by candidate-pool size.

Data (per `data/{train,dev,test}.json`):

| Split | Sessions | EDUs |
|---|---|---|
| train | 28 | 6,792 |
| dev   | 6  | 1,535 |
| test  | 6  | 1,465 |

Label mix (all splits): single 81%, everyone 14%, multi 4.5%, none 0%.
Candidate pool ≈ 11 names/session (max 19). Content is English + Malay.

## 3. Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Base model | **Qwen3-8B** (non-thinking) | Recent, strong ~8B open model; Llama-3.1-8B reads as dated. Thinking disabled to keep it a clean supervised classifier (no `<think>` traces to parse or pay for). |
| Task framing | **Per-EDU, 20-EDU left window** (Design C) | Whole-session-at-once = only 28 training examples. Per-EDU gives ~6,792 examples. K=20 reuses the project's existing window convention (`--context_size 20`). Addressee is locally resolvable, so a 20-EDU window loses little signal. |
| `max_seq_len` | **2048** | Measured 20-EDU windows: median 745, p99 1,244, **max 1,431** tokens (~chars/4). Plus instructions (~250) + output (~40) + tokenizer slack (~1.2×) ≈ 2,100 worst case. 1024 would truncate ~11% of windows. |
| FT method | **bf16 LoRA** (QLoRA fallback) | Windows are short (~600–2,000 tok), so a 32 GB RTX 5090 fits bf16 8B + LoRA easily — faster and higher-fidelity than 4-bit. `--load_in_4bit` flag retained for smaller GPUs. |
| Framework | **Unsloth + TRL** | Fastest, lowest-VRAM, single-script; good RunPod ergonomics. |
| Epochs / LR | 3 epochs, 2e-4, linear, warmup 0.03 | Standard LoRA SFT recipe. |

## 4. Comparability contract

The fine-tuned model **must** stay comparable to the prompted GPT baseline:

- **Same candidate pool** logic: `["everyone"] + sorted(unique speakers)`.
- **Same output space**: predicted addressees are exact pool strings.
- **Same evaluator**: predictions are reconstructed into
  `[{"dialogue_id": <id>, "addressees": [[...], [...], ...]}]`, one inner list per
  EDU aligned by index, and scored by the **existing** `evaluate_ar_baseline.py`
  against `data/test.json`. No change to the metric.

Difference from GPT (a legitimate, reportable advantage): we predict **one EDU at
a time**, so the positional-alignment drift that the GPT baseline patches by
padding/truncating a 242-entry list cannot occur.

## 5. Pipeline / components

Each unit is a standalone script under `baseline_ar/qwen3_sft/`:

1. **`build_ar_sft_data.py`** — data prep.
   - Input: `data/{split}.json`. Output: JSONL.
   - Training rows (`train.jsonl`, `dev.jsonl`): chat `messages`
     `[system, user(prompt), assistant(gold JSON)]`.
   - Inference rows (`test_prompts.jsonl`, `dev_prompts.jsonl`):
     `{dialogue_id, edu_index, messages:[system, user]}` (no gold leaked).
   - Prompt = task instructions + candidate pool + 20-EDU window ending on the
     target `[eduN]`; asks for `{"addressees": [...]}`.

2. **`train_qwen3_ar.py`** — Unsloth LoRA SFT.
   - Loads `unsloth/Qwen3-8B`, applies chat template with `enable_thinking=False`,
     trains on assistant responses only (`train_on_responses_only`), saves adapter.

3. **`predict_qwen3_ar.py`** — inference + reconstruction.
   - Loads base + adapter, greedy-decodes each prompt, robustly parses the JSON
     addressee set (fallback: substring match against the pool), keeps only pool
     members, reconstructs per-session index-aligned lists → `predictions.json`.

4. **`evaluate_ar_baseline.py`** — reused unchanged.

5. **`run_runpod.sh`** — one-shot orchestration for a RunPod pod
   (install → build data → train → predict → evaluate).

## 6. Error handling

- Empty/malformed model output → empty addressee set `[]` for that EDU (counts as a
  miss unless gold is also empty; never crashes the run).
- Predicted names not in the pool → dropped (mirrors the "exact pool string"
  contract).
- Missing EDU indices at reconstruction → padded with `[]` so per-session list
  length matches the session's EDU count.

## 7. Expected cost (RTX 5090, RunPod)

~1,000 real tokens/example × 6,792 ≈ 6.8M tokens/epoch. At bf16 LoRA throughput,
~20–30 min/epoch → **~60–90 min for 3 epochs**; end-to-end incl. install + 16 GB
model download + inference ≈ **~1.5 h, ~$1–1.5**.

## 8. Out of scope (follow-up)

- Additional prompted baselines (Qwen3-8B / Llama-3.1-8B zero-shot).
- Naïve non-LLM floor (e.g. "most-recently-addressed speaker").
- Extended error analysis (everyone↔single confusion, chair-vs-member).
- Window-size ablation (K = 10/20/40).
