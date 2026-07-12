"""
Run the fine-tuned Qwen3-8B AR model over inference prompts and reconstruct
per-session, index-aligned predictions compatible with evaluate_ar_baseline.py.

Output format (identical contract to the GPT baseline):
  [{"dialogue_id": <id>, "addressees": [[...], [...], ...]}, ...]
where addressees[i] is the predicted set for edu i.

Usage:
  python predict_qwen3_ar.py \
      --adapter outputs/qwen3-ar-lora \
      --prompts_file data_sft/test_prompts.jsonl \
      --data_file ../../data/test.json \
      --out predictions_qwen3.json
"""
import argparse
import json
import re
from collections import defaultdict
from typing import List, Dict

from unsloth import FastLanguageModel


def get_candidate_pool(edus: List[Dict]) -> List[str]:
    speakers = set()
    for edu in edus:
        sp = edu.get("speaker")
        if sp and sp.lower() != "everyone":
            speakers.add(sp)
    return ["everyone"] + sorted(speakers)


def parse_addressees(text: str, pool: List[str]) -> List[str]:
    """Robustly extract the addressee set and keep only exact pool members.

    1. Try to json.loads the first {...} block and read 'addressees'.
    2. Fallback: substring-match pool names (longest first) against the raw text.
    """
    candidates = None

    # strip a leading <think>...</think> if the model emitted one anyway
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            val = obj.get("addressees", [])
            if isinstance(val, list):
                candidates = [str(x) for x in val]
        except (json.JSONDecodeError, AttributeError):
            candidates = None

    pool_set = set(pool)
    if candidates is not None:
        kept = [c for c in candidates if c in pool_set]
        # de-dup, preserve order
        seen, out = set(), []
        for c in kept:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    # fallback: match pool names by substring (longest names first to avoid
    # matching a name that is a prefix of another)
    out = []
    for name in sorted(pool, key=len, reverse=True):
        if name in text and name not in out:
            out.append(name)
    return out


def batched(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="outputs/qwen3-ar-lora",
                    help="path to the saved LoRA adapter (or a merged model)")
    ap.add_argument("--prompts_file", default="data_sft/test_prompts.jsonl")
    ap.add_argument("--data_file", default="../../data/test.json",
                    help="original split JSON (for per-session EDU counts + pools)")
    ap.add_argument("--out", default="predictions_qwen3.json")
    ap.add_argument("--max_seq_len", type=int, default=2048)
    ap.add_argument("--max_new_tokens", type=int, default=64)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--load_in_4bit", action="store_true")
    args = ap.parse_args()

    # per-session pools + lengths from the original data
    with open(args.data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    pools = {}
    n_edus = {}
    order = []
    for s in data:
        sid = s.get("id", "Unknown")
        edus = s.get("edus", [])
        pools[sid] = get_candidate_pool(edus)
        n_edus[sid] = len(edus)
        order.append(sid)

    # load inference prompts
    prompts = []
    with open(args.prompts_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prompts.append(json.loads(line))

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.adapter,
        max_seq_length=args.max_seq_len,
        load_in_4bit=args.load_in_4bit,
        dtype=None,
    )
    FastLanguageModel.for_inference(model)

    # predictions[sid][edu_index] = [addressees]
    preds = defaultdict(dict)

    for batch in batched(prompts, args.batch_size):
        texts = [
            tokenizer.apply_chat_template(
                p["messages"],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for p in batch
        ]
        enc = tokenizer(texts, return_tensors="pt", padding=True, truncation=True,
                        max_length=args.max_seq_len).to(model.device)
        out = model.generate(
            **enc,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
        gen = out[:, enc["input_ids"].shape[1]:]
        decoded = tokenizer.batch_decode(gen, skip_special_tokens=True)

        for p, text in zip(batch, decoded):
            sid = p["dialogue_id"]
            i = p["edu_index"]
            preds[sid][i] = parse_addressees(text, pools.get(sid, ["everyone"]))

    # reconstruct index-aligned lists, preserving original session order
    results = []
    for sid in order:
        n = n_edus.get(sid, 0)
        per_edu = preds.get(sid, {})
        addressees = [per_edu.get(i, []) for i in range(n)]
        results.append({"dialogue_id": sid, "addressees": addressees})

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote predictions for {len(results)} sessions -> {args.out}")


if __name__ == "__main__":
    main()
