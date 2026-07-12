#!/usr/bin/env bash
# =============================================================================
# One-shot RunPod driver: fine-tune Qwen3-8B for DIAM addressee recognition.
#
# Recommended pod: 1x RTX 5090 (32GB) or any >=24GB GPU.
#   - PyTorch image, CUDA 12.x, Python 3.10/3.11.
#   - Persistent volume mounted at /workspace.
#
# HOW TO USE
#   1. Upload the DIAM repo to the pod (so data/ and baseline_ar/ exist), e.g.:
#        runpodctl send DIAM        # or scp -r, or `git clone`
#   2. On the pod:
#        cd DIAM/baseline_ar/qwen3_sft
#        chmod +x run_runpod.sh
#        ./run_runpod.sh
#   3. Download results afterwards: predictions_qwen3.json + eval_test.txt
#
# Override any knob via env vars, e.g.:  EPOCHS=2 BATCH=16 ./run_runpod.sh
# =============================================================================
set -euo pipefail

# ----------------------------- configuration --------------------------------
MODEL="${MODEL:-unsloth/Qwen3-8B}"
WINDOW="${WINDOW:-20}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}"
EPOCHS="${EPOCHS:-3}"
LR="${LR:-2e-4}"
BATCH="${BATCH:-8}"
GRAD_ACCUM="${GRAD_ACCUM:-2}"
LOAD_IN_4BIT="${LOAD_IN_4BIT:-0}"   # set to 1 to use QLoRA on <24GB GPUs

DATA_DIR="${DATA_DIR:-../../data}"
OUT_DIR="${OUT_DIR:-outputs/qwen3-ar-lora}"
SFT_DIR="${SFT_DIR:-data_sft}"
PRED_FILE="${PRED_FILE:-predictions_qwen3.json}"

FOURBIT_FLAG=""
[ "$LOAD_IN_4BIT" = "1" ] && FOURBIT_FLAG="--load_in_4bit"

echo "=============================================================="
echo " DIAM AR  |  model=$MODEL  window=$WINDOW  max_seq=$MAX_SEQ_LEN"
echo "          |  epochs=$EPOCHS  batch=$BATCH  grad_accum=$GRAD_ACCUM"
echo "          |  4bit=$LOAD_IN_4BIT"
echo "=============================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

# ------------------------------ dependencies --------------------------------
echo "[1/5] Installing dependencies ..."
pip install -q --upgrade pip
# Unsloth pulls compatible torch/transformers/trl/peft/bitsandbytes wheels.
pip install -q "unsloth[cu124-torch260]" 2>/dev/null \
  || pip install -q unsloth
pip install -q "trl>=0.11" "datasets>=2.19" "transformers>=4.51" "accelerate>=0.30"

# ------------------------------ build data ----------------------------------
echo "[2/5] Building windowed per-EDU SFT data ..."
python build_ar_sft_data.py --data_dir "$DATA_DIR" --out_dir "$SFT_DIR" --window "$WINDOW"

# ------------------------------ train ---------------------------------------
echo "[3/5] Fine-tuning ($EPOCHS epochs) ..."
python train_qwen3_ar.py \
  --model "$MODEL" \
  --train_file "$SFT_DIR/train.jsonl" \
  --out_dir "$OUT_DIR" \
  --max_seq_len "$MAX_SEQ_LEN" \
  --epochs "$EPOCHS" \
  --lr "$LR" \
  --batch "$BATCH" \
  --grad_accum "$GRAD_ACCUM" \
  $FOURBIT_FLAG

# ------------------------------ predict -------------------------------------
echo "[4/5] Running inference on test split ..."
python predict_qwen3_ar.py \
  --adapter "$OUT_DIR" \
  --prompts_file "$SFT_DIR/test_prompts.jsonl" \
  --data_file "$DATA_DIR/test.json" \
  --out "$PRED_FILE" \
  --max_seq_len "$MAX_SEQ_LEN" \
  $FOURBIT_FLAG

# ------------------------------ evaluate ------------------------------------
echo "[5/5] Evaluating against ground truth ..."
python ../evaluate_ar_baseline.py \
  --gt_file "$DATA_DIR/test.json" \
  --pred_file "$PRED_FILE" | tee eval_test.txt

echo ""
echo "=============================================================="
echo " DONE. Download these before stopping the pod:"
echo "   - $PRED_FILE   (predictions)"
echo "   - eval_test.txt          (EM/F1 scores)"
echo "   - $OUT_DIR/    (LoRA adapter, if you want to keep it)"
echo "=============================================================="
