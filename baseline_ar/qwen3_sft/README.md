# Fine-tuned Qwen3-8B — Addressee Recognition Baseline

A fine-tuned open-LLM AR baseline for DIAM, comparable to the prompted `gpt-5.2`
baseline in `baseline_ar/`. Fine-tunes **Qwen3-8B** (non-thinking) with **LoRA**
(Unsloth) on **per-EDU, 20-EDU-windowed** examples, then reconstructs predictions
into the exact format scored by `baseline_ar/evaluate_ar_baseline.py`.

See `docs/superpowers/specs/2026-07-11-ar-qwen3-sft-design.md` for the full design.

## Files

| File | Role |
|---|---|
| `build_ar_sft_data.py` | `data/*.json` → windowed per-EDU chat examples (JSONL) |
| `train_qwen3_ar.py`    | Unsloth LoRA SFT of Qwen3-8B (thinking disabled) |
| `predict_qwen3_ar.py`  | Inference + reconstruct index-aligned `predictions.json` |
| `run_runpod.sh`        | One-shot pod driver: install → data → train → predict → eval |

Evaluation reuses `../evaluate_ar_baseline.py` unchanged (same EM/F1 metric).

## Quick start (RunPod)

Pod: 1× RTX 5090 (32 GB) or any ≥24 GB GPU, PyTorch/CUDA 12.x image.

```bash
# upload the DIAM repo to the pod first (runpodctl send / scp / git clone)
cd DIAM/baseline_ar/qwen3_sft
chmod +x run_runpod.sh
./run_runpod.sh
```

Knobs via env vars, e.g. QLoRA on a smaller GPU or a quick 2-epoch run:

```bash
LOAD_IN_4BIT=1 ./run_runpod.sh          # 4-bit, fits 24GB
EPOCHS=2 BATCH=16 ./run_runpod.sh
```

Expected: **~60–90 min** training, **~1.5 h / ~$1–1.5** end-to-end on a 5090.

## Manual (step by step)

```bash
python build_ar_sft_data.py --data_dir ../../data --out_dir data_sft --window 20
python train_qwen3_ar.py    --train_file data_sft/train.jsonl --out_dir outputs/qwen3-ar-lora
python predict_qwen3_ar.py  --adapter outputs/qwen3-ar-lora \
                            --prompts_file data_sft/test_prompts.jsonl \
                            --data_file ../../data/test.json --out predictions_qwen3.json
python ../evaluate_ar_baseline.py --gt_file ../../data/test.json --pred_file predictions_qwen3.json
```

## Notes

- **Comparability:** same candidate pool (`["everyone"] + sorted(speakers)`),
  same exact-string output space, same evaluator as the GPT baseline.
- **Per-EDU prediction** avoids the positional-alignment drift the GPT baseline
  patches by padding/truncating a whole-session list.
- **Thinking disabled** (`enable_thinking=False`) at train and inference — the
  model emits only `{"addressees": [...]}`.
- Download `predictions_qwen3.json`, `eval_test.txt`, and (optionally) the
  `outputs/qwen3-ar-lora/` adapter before stopping the pod.
