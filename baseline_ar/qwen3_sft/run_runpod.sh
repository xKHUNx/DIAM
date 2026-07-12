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
# RTX 5090 = Blackwell (sm_120): REQUIRES a CUDA 12.8 PyTorch build (>=2.7).
# Older cu124/torch2.6 wheels have no Blackwell kernels and also break torchao.
# Strategy: install the ML stack first, then (force-)install cu128 torch LAST so
# nothing downgrades it. Set TORCH_CUDA=cu126 etc. to override for other GPUs.
echo "[1/5] Installing dependencies ..."
TORCH_CUDA="${TORCH_CUDA:-cu128}"
pip install -q --upgrade pip
pip install -q --upgrade unsloth unsloth_zoo
pip install -q --upgrade "transformers>=4.51" "trl>=0.11" "datasets>=2.19" \
                         "accelerate>=0.30" "peft>=0.11" "bitsandbytes>=0.45"
# The base image often pins a broken torchao (built against old torch) that
# crashes `import unsloth` with a register_constant error. We don't use TorchAO
# quantization, so remove it from the import path.
pip uninstall -y -q torchao 2>/dev/null || true
# Install Blackwell-capable torch LAST so nothing downgrades it.
pip install -q --upgrade --force-reinstall torch \
  --index-url "https://download.pytorch.org/whl/${TORCH_CUDA}"

# Sanity: confirm torch sees the 5090 with a matching arch (should list sm_120).
python - <<'PY'
import torch, re
arch = torch.cuda.get_arch_list()
name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE"
print("torch", torch.__version__, "| cuda", torch.version.cuda, "| gpu", name)
print("arch_list", arch)
assert torch.cuda.is_available(), "CUDA not available after install"
# Blackwell (RTX 50xx) reports sm_120; refuse to train on a torch that lacks it.
cc = torch.cuda.get_device_capability(0)  # e.g. (12, 0) for 5090
need = f"sm_{cc[0]}{cc[1]}"
assert any(need in a for a in arch), (
    f"Installed torch has no kernels for {need} ({name}); "
    f"got {arch}. Reinstall torch from a matching CUDA index (e.g. cu128)."
)
print(f"OK: torch supports {need}")
PY

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
