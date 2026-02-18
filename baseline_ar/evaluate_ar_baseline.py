import json
import argparse
import os
from collections import defaultdict
from typing import List, Set

def get_candidate_pool(edus: List[dict]) -> List[str]:
    """
    Reproduce the candidate pool logic from the baseline script.
    """
    speakers = set()
    for edu in edus:
        speaker = edu.get("speaker")
        if speaker and speaker.lower() != "everyone":
            speakers.add(speaker)
    candidates = ["everyone"] + sorted(list(speakers))
    return candidates

def calculate_metrics(y_true: List[Set[str]], y_pred: List[Set[str]]):
    if not y_true:
        return 0.0, 0.0
    
    em_count = 0
    f1_sum = 0.0
    
    for gold, pred in zip(y_true, y_pred):
        if gold == pred:
            em_count += 1
            
        if not gold and not pred:
            f1_sum += 1.0
            continue
        if not gold or not pred:
            f1_sum += 0.0
            continue
            
        intersection = len(gold.intersection(pred))
        precision = intersection / len(pred) if len(pred) > 0 else 0
        recall = intersection / len(gold) if len(gold) > 0 else 0
        
        if precision + recall > 0:
            f1_sum += (2 * precision * recall) / (precision + recall)
        else:
            f1_sum += 0.0
            
    return em_count / len(y_true), f1_sum / len(y_true)

def main():
    parser = argparse.ArgumentParser(description="Evaluate Addressee Recognition Baseline")
    parser.add_argument("--gt_file", type=str, required=True, help="Ground truth JSON file (diam format)")
    parser.add_argument("--pred_file", type=str, required=True, help="Prediction JSON file (baseline output)")
    args = parser.parse_args()

    if not os.path.exists(args.gt_file):
        print(f"Ground truth file {args.gt_file} not found.")
        return
    if not os.path.exists(args.pred_file):
        print(f"Prediction file {args.pred_file} not found.")
        return

    with open(args.gt_file, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
    with open(args.pred_file, "r", encoding="utf-8") as f:
        pred_data = json.load(f)

    # Map predictions by dialogue_id
    pred_map = {item["dialogue_id"]: item["addressees"] for item in pred_data}

    # Statistics containers
    all_y_true = []
    all_y_pred = []
    
    by_cand_count = defaultdict(lambda: {"true": [], "pred": []})
    by_type = {
        "everyone": {"true": [], "pred": []},
        "single": {"true": [], "pred": []},
        "multi": {"true": [], "pred": []}
    }

    total_edus_evaluated = 0

    for session in gt_data:
        session_id = session.get("id")
        if session_id not in pred_map:
            continue
            
        edus = session.get("edus", [])
        pred_addresses = pred_map[session_id]
        
        candidate_pool = get_candidate_pool(edus)
        cand_count = len(candidate_pool)
        
        # In case of length mismatch (though script handles it)
        num_to_eval = min(len(edus), len(pred_addresses))
        
        for i in range(num_to_eval):
            gold_set = set(edus[i].get("addressees", []))
            pred_set = set(pred_addresses[i])
            
            # Categorize
            if "everyone" in gold_set:
                cat = "everyone"
            elif len(gold_set) > 1:
                cat = "multi"
            else:
                cat = "single"
                
            # Add to containers
            all_y_true.append(gold_set)
            all_y_pred.append(pred_set)
            
            by_cand_count[cand_count]["true"].append(gold_set)
            by_cand_count[cand_count]["pred"].append(pred_set)
            
            by_type[cat]["true"].append(gold_set)
            by_type[cat]["pred"].append(pred_set)
            
            total_edus_evaluated += 1

    if total_edus_evaluated == 0:
        print("No matching sessions found between GT and Pred files.")
        return

    # Print overall results
    overall_em, overall_f1 = calculate_metrics(all_y_true, all_y_pred)
    print("=" * 60)
    print(f"{'OVERALL PERFORMANCE':^60}")
    print("=" * 60)
    print(f"Total EDUs Evaluated: {total_edus_evaluated}")
    print(f"Exact Match (EM):     {overall_em:.4f}")
    print(f"F1 Score:            {overall_f1:.4f}")
    print("-" * 60)

    # Print results by category type
    print(f"{'PERFORMANCE BY SCENARIO':^60}")
    print("-" * 60)
    print(f"{'Scenario':<15} | {'Count':<8} | {'EM':<8} | {'F1':<8}")
    print("-" * 60)
    for cat in ["everyone", "single", "multi"]:
        stats = by_type[cat]
        if not stats["true"]:
            continue
        em, f1 = calculate_metrics(stats["true"], stats["pred"])
        print(f"{cat:<15} | {len(stats['true']):<8} | {em:.4f} | {f1:.4f}")
    print("-" * 60)

    # Print results by candidate pool size
    print(f"{'PERFORMANCE BY CANDIDATE POOL SIZE':^60}")
    print("-" * 60)
    print(f"{'Pool Size':<15} | {'Count':<8} | {'EM':<8} | {'F1':<8}")
    print("-" * 60)
    for size in sorted(by_cand_count.keys()):
        stats = by_cand_count[size]
        em, f1 = calculate_metrics(stats["true"], stats["pred"])
        print(f"{size:<15} | {len(stats['true']):<8} | {em:.4f} | {f1:.4f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
