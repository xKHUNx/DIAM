"""
Build per-EDU, windowed SFT data for the fine-tuned Qwen3-8B addressee-recognition
baseline (DIAM, Design C).

For every EDU in a session we emit one example:
  - context = the previous K EDUs + the target EDU (formatted like the GPT baseline)
  - candidate pool = ["everyone"] + sorted(unique speakers)   (same as baseline_ar)
  - target label = the gold addressee set of the target EDU

Outputs (JSONL):
  train.jsonl / dev.jsonl   -> chat messages incl. the gold assistant turn (for SFT)
  {split}_prompts.jsonl     -> {dialogue_id, edu_index, messages:[system,user]} for inference

Usage:
  python build_ar_sft_data.py --data_dir ../../data --out_dir data_sft --window 20
"""
import json
import os
import argparse
from typing import List, Dict

SYSTEM_PROMPT = (
    "You are an expert in parliamentary dialogue analysis. "
    "You determine who each utterance is addressed to."
)


def get_candidate_pool(edus: List[Dict]) -> List[str]:
    """Same convention as baseline_ar: 'everyone' first, then sorted unique speakers."""
    speakers = set()
    for edu in edus:
        sp = edu.get("speaker")
        if sp and sp.lower() != "everyone":
            speakers.add(sp)
    return ["everyone"] + sorted(speakers)


def format_context_line(edu: Dict, idx: int) -> str:
    return f"[edu{idx}] {edu.get('speaker', 'Unknown')}: {edu.get('text', '')}"


def build_user_prompt(edus: List[Dict], i: int, pool: List[str], window: int) -> str:
    lo = max(0, i - window)
    ctx = "\n".join(format_context_line(edus[j], j) for j in range(lo, i + 1))
    pool_str = ", ".join(pool)
    speaker = edus[i].get("speaker", "Unknown")
    return (
        f"Identify the addressee(s) of the TARGET utterance [edu{i}] in the conversation below.\n\n"
        f"Candidate addressees (choose ONLY from these, copy names exactly):\n{pool_str}\n\n"
        f"Conversation (the TARGET is the last line, [edu{i}]):\n{ctx}\n\n"
        f"Instructions:\n"
        f"- Report only who [edu{i}] (\"{speaker}\") is speaking to.\n"
        f"- Each addressee MUST be copied exactly from the candidate list above.\n"
        f"- Use \"everyone\" if the utterance addresses the whole chamber.\n"
        f"- Multiple addressees are allowed.\n"
        f"- Respond with ONLY a JSON object: {{\"addressees\": [\"Name\", ...]}}"
    )


def build_split(data: List[Dict], window: int):
    """Return (train_rows_with_labels, prompt_rows_for_inference)."""
    train_rows, prompt_rows = [], []
    for session in data:
        edus = session.get("edus", [])
        if not edus:
            continue
        pool = get_candidate_pool(edus)
        sid = session.get("id", "Unknown")
        for i, edu in enumerate(edus):
            user = build_user_prompt(edus, i, pool, window)
            gold = edu.get("addressees", []) or []
            assistant = json.dumps({"addressees": gold}, ensure_ascii=False)
            base_msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ]
            train_rows.append(
                {
                    "dialogue_id": sid,
                    "edu_index": i,
                    "messages": base_msgs + [{"role": "assistant", "content": assistant}],
                }
            )
            prompt_rows.append(
                {"dialogue_id": sid, "edu_index": i, "messages": base_msgs}
            )
    return train_rows, prompt_rows


def write_jsonl(path: str, rows: List[Dict]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  wrote {len(rows):>6} rows -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="../../data", help="dir with train/dev/test.json")
    ap.add_argument("--out_dir", default="data_sft")
    ap.add_argument("--window", type=int, default=20, help="number of preceding EDUs of context")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    for split in ("train", "dev", "test"):
        src = os.path.join(args.data_dir, f"{split}.json")
        if not os.path.exists(src):
            print(f"[skip] {src} not found")
            continue
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[{split}] {len(data)} sessions")
        train_rows, prompt_rows = build_split(data, args.window)

        # SFT training data only needed for train (and optionally dev for eval loss)
        if split in ("train", "dev"):
            write_jsonl(os.path.join(args.out_dir, f"{split}.jsonl"), train_rows)
        # inference prompts for dev + test
        if split in ("dev", "test"):
            write_jsonl(os.path.join(args.out_dir, f"{split}_prompts.jsonl"), prompt_rows)

    print("Done.")


if __name__ == "__main__":
    main()
