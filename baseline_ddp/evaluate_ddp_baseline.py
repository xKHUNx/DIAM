import json
import argparse
from collections import defaultdict

def calculate_f1(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return f1, precision, recall

def get_distance_bin(dist):
    if dist == 1:
        return "d=1"
    elif 2 <= dist <= 3:
        return "d=2-3"
    elif 4 <= dist <= 8:
        return "d=4-8"
    else:
        return "d>=9"

def evaluate(ground_truth_file, prediction_file):
    print(f"Evaluating {prediction_file} against {ground_truth_file}")
    
    with open(ground_truth_file, 'r', encoding='utf-8') as f:
        gt_data = json.load(f)
    
    with open(prediction_file, 'r', encoding='utf-8') as f:
        pred_data = json.load(f)
        
    gt_map = {item['id']: item for item in gt_data}
    pred_map = {item['id']: item for item in pred_data}
    
    # Global counts
    link_tp, link_fp, link_fn = 0, 0, 0
    type_tp, type_fp, type_fn = 0, 0, 0
    
    # Per type counts
    per_type_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})
    
    # Per distance counts
    per_dist_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0})
    
    # Iterate over Ground Truth documents (to handle recall correctly)
    # We only evaluate documents present in Ground Truth.
    # If prediction is missing a document, all its relations are FN.
    
    all_doc_ids = set(gt_map.keys()) | set(pred_map.keys())
    
    for doc_id in all_doc_ids:
        if doc_id not in gt_map:
            # Prediction has a document not in GT? Ignore or count as FP?
            # Typically ignore if dataset mismatch, but assuming aligned.
            continue
            
        gt_doc = gt_map[doc_id]
        pred_doc = pred_map.get(doc_id)
        
        gt_relations = set()
        for r in gt_doc.get('relations', []):
            gt_relations.add((r['x'], r['y'], r['type']))
            
        pred_relations = set()
        if pred_doc:
            for r in pred_doc.get('relations', []):
                pred_relations.add((r['x'], r['y'], r['type']))
                
        # Link Only Evaluation (x, y)
        gt_links = set((x, y) for x, y, t in gt_relations)
        pred_links = set((x, y) for x, y, t in pred_relations)
        
        # Calculate Link TP, FP, FN
        # Using sets automatically handles duplicates if any
        tp_links = gt_links.intersection(pred_links)
        fp_links = pred_links - gt_links
        fn_links = gt_links - pred_links
        
        link_tp += len(tp_links)
        link_fp += len(fp_links)
        link_fn += len(fn_links)
        
        # Link and Relation Type Evaluation (x, y, type)
        tp_rels = gt_relations.intersection(pred_relations)
        fp_rels = pred_relations - gt_relations
        fn_rels = gt_relations - pred_relations
        
        type_tp += len(tp_rels)
        type_fp += len(fp_rels)
        type_fn += len(fn_rels)
        
        # Per Type Evaluation
        # We define "Per Type" as: For a specific type T, how well do we predict (x, y) relations of type T?
        # Alternatively: How well do we predict (x, y, T)?
        # Usually it is P/R/F1 for extracting triples (x, y, T) where gt.type == T.
        
        # Collect all types
        doc_types = set(t for x, y, t in gt_relations) | set(t for x, y, t in pred_relations)
        
        for t in doc_types:
            gt_subset = set((x, y) for x, y, rt in gt_relations if rt == t)
            pred_subset = set((x, y) for x, y, rt in pred_relations if rt == t)
            
            sub_tp = gt_subset.intersection(pred_subset)
            sub_fp = pred_subset - gt_subset
            sub_fn = gt_subset - pred_subset
            
            per_type_stats[t]['tp'] += len(sub_tp)
            per_type_stats[t]['fp'] += len(sub_fp)
            per_type_stats[t]['fn'] += len(sub_fn)

        # Distance Evaluation (Link + Type)
        for (x, y, t) in gt_relations:
            dist = abs(y - x)
            bin_name = get_distance_bin(dist)
            if (x, y, t) in pred_relations:
                per_dist_stats[bin_name]['tp'] += 1
            else:
                per_dist_stats[bin_name]['fn'] += 1
        
        for (x, y, t) in pred_relations:
            if (x, y, t) not in gt_relations:
                dist = abs(y - x)
                bin_name = get_distance_bin(dist)
                per_dist_stats[bin_name]['fp'] += 1

    # Calculate Global Metrics
    link_f1, link_p, link_r = calculate_f1(link_tp, link_fp, link_fn)
    type_f1, type_p, type_r = calculate_f1(type_tp, type_fp, type_fn)
    
    print("-" * 30)
    print(f"Overall Link Only: F1: {link_f1:.4f}, P: {link_p:.4f}, R: {link_r:.4f}")
    print(f"Overall Link + Type: F1: {type_f1:.4f}, P: {type_p:.4f}, R: {type_r:.4f}")
    print("-" * 30)
    print("Per Relation Type Scores:")
    print(f"{'Type':<30} {'F1':<10} {'Precision':<10} {'Recall':<10} {'Support (GT)':<10}")
    
    sorted_types = sorted(per_type_stats.keys())
    for t in sorted_types:
        s = per_type_stats[t]
        f1, p, r = calculate_f1(s['tp'], s['fp'], s['fn'])
        support = s['tp'] + s['fn']
        print(f"{t:<30} {f1:.4f}     {p:.4f}        {r:.4f}        {support:<10}")

    print("-" * 30)
    print("Distance-wise Performance (Link + Type):")
    print(f"{'Distance':<15} {'F1':<10} {'Precision':<10} {'Recall':<10} {'Support (GT)':<10}")
    
    distance_order = ["d=1", "d=2-3", "d=4-8", "d>=9"]
    for d_bin in distance_order:
        s = per_dist_stats[d_bin]
        f1, p, r = calculate_f1(s['tp'], s['fp'], s['fn'])
        support = s['tp'] + s['fn']
        print(f"{d_bin:<15} {f1:.4f}     {p:.4f}        {r:.4f}        {support:<10}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate baseline.")
    parser.add_argument("ground_truth", help="Path to ground truth JSON")
    parser.add_argument("predictions", nargs='+', help="Paths to prediction JSONs")
    
    args = parser.parse_args()
    
    for pred_file in args.predictions:
        evaluate(args.ground_truth, pred_file)
        print("\n" + "="*50 + "\n")
