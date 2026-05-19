import os
import json
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import csv
import argparse
from datetime import datetime
from collections import Counter, defaultdict


def plot_combined_histograms(all_df, out_dir="plots"):
    os.makedirs(out_dir, exist_ok=True)
    metrics = ["num_edus", "num_relations", "num_speakers"]

    for metric in metrics:
        if metric not in all_df.columns:
            print(f"⚠️ Skipping {metric}, not found in dataframe")
            continue

        plt.figure(figsize=(8, 6))
        sns.histplot(
            data=all_df,
            x=metric,
            hue="split",
            element="step",   # outline style
            stat="count",
            common_norm=False,
            alpha=0.4,        # transparency
            bins=30
        )
        plt.title(f"Distribution of {metric} across splits")
        plt.xlabel(metric)
        plt.ylabel("Count")
        plt.legend(title="Split")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"{metric}_combined.png"))
        plt.close()



def process_dialogue(data, dialogue_id):
    """
    Parse one dialogue dictionary and return a dictionary with file-level stats.
    If any EDU has zero addressees, print the file path (and EDU indices).
    """
    # edus/relations are at the top level in the new JSON format
    edus = data.get("edus", [])
    relations = data.get("relations", [])

    # Basic counts
    n_edus = len(edus)
    n_relations = len(relations)
    speakers = {edu.get("speaker") for edu in edus if "speaker" in edu}
    n_speakers = len(speakers)

    # New statistic: number of non-verbal actions
    num_non_verbal_actions = 0
    edu_char_lengths = []
    for edu in edus:
        text = edu.get("text", "")
        edu_char_lengths.append(len(text))
        if text.startswith("[") and text.endswith("]"):
            num_non_verbal_actions += 1

    doc_char_count = sum(edu_char_lengths)

    # Date extraction from dialogue_id (DR-DDMMYYYY-XX)
    date_found = None
    session_num = None
    try:
        if dialogue_id.startswith("DR-"):
            parts = dialogue_id.split("-")
            if len(parts) >= 2:
                # Validate it's a date string of 8 digits
                d_str = parts[1]
                if len(d_str) == 8 and d_str.isdigit():
                    date_found = d_str
            if len(parts) >= 3:
                session_num = parts[2]
    except Exception:
        pass

    # Calculate per-node parent/child counts.
    # Convention (verified from the gold data): in a relation, x is the PARENT
    # (antecedent, earlier index) and y is the CHILD (dependent, later index).
    # So a node's #parents = times it appears as y; #children = times it appears as x.
    num_parents_of = Counter()   # node -> how many parents it has
    num_children_of = Counter()  # node -> how many children it has
    pair_counts = Counter()
    for rel in relations:
        if isinstance(rel, dict) and "x" in rel and "y" in rel:
            num_parents_of[rel["y"]] += 1   # y is the child -> gains a parent (x)
            num_children_of[rel["x"]] += 1  # x is the parent -> gains a child (y)
            pair_counts[(rel["x"], rel["y"])] += 1

    # Count EDUs with multiple parents and multiple children
    num_multi_parent_nodes = sum(1 for count in num_parents_of.values() if count > 1)
    num_multi_child_nodes = sum(1 for count in num_children_of.values() if count > 1)
    num_pairs_with_multi_relations = sum(1 for count in pair_counts.values() if count > 1)

    # Addressee distribution (include 0, 1, 2, ...)
    addressee_counter = Counter()
    zero_addressee_indices = []
    has_any_addressee_field = False
    for idx, edu in enumerate(edus):
        if "addressees" in edu:
            has_any_addressee_field = True
            addrs = edu.get("addressees", [])
            if not isinstance(addrs, list):
                # Treat malformed addressees as empty list
                addrs = []
            addressee_counter[len(addrs)] += 1
            if len(addrs) == 0:
                zero_addressee_indices.append(idx)

    # Print a warning with the JSON path if any zero-addressee EDUs are present (only if field exists)
    if has_any_addressee_field and zero_addressee_indices:
        print(f"WARNING: Dialogue {dialogue_id} has {len(zero_addressee_indices)} EDU(s) with zero addressees. EDU indices: {zero_addressee_indices}")

    # Relation type counts
    rel_type_counter = Counter(rel.get("type") for rel in relations if isinstance(rel, dict) and "type" in rel)

    # Relation distances (for per-file average)
    if relations:
        distances = [abs(rel["x"] - rel["y"]) for rel in relations if isinstance(rel, dict) and "x" in rel and "y" in rel]
        avg_distance = float(sum(distances) / len(distances)) if distances else 0.0
    else:
        avg_distance = 0.0

    # Build return dict (file-level row for CSV). We include the raw edus/relations for later statistics.json processing.
    stats = {
        "file": dialogue_id,
        "num_edus": n_edus,
        "num_relations": n_relations,
        "num_speakers": n_speakers,
        "num_non_verbal_actions": num_non_verbal_actions, # New statistic
        "num_multi_parent_nodes": num_multi_parent_nodes,
        "num_multi_child_nodes": num_multi_child_nodes,
        "num_pairs_with_multi_relations": num_pairs_with_multi_relations,
        "avg_relation_distance": avg_distance,
        "doc_char_count": doc_char_count,
        "date": date_found,
        "session": session_num,
        "__edus": edus,
        "__relations": relations,
        "__edu_char_lengths": edu_char_lengths,
        "has_addressees": has_any_addressee_field,
        "has_zero_addressee": bool(zero_addressee_indices) if has_any_addressee_field else False,
    }

    # Expand relation type counts and addressee counts into separate keys
    stats.update({f"relation_{k}": v for k, v in rel_type_counter.items()})
    if has_any_addressee_field:
        stats.update({f"multi_addr_{k}": v for k, v in addressee_counter.items()})

    return stats


def process_split(json_path, split_name, out_file):
    print(f"Processing {split_name} from {json_path}...")
    if not os.path.exists(json_path):
        print(f"⚠️ File not found: {json_path}")
        return pd.DataFrame()

    with open(json_path, "r", encoding="utf-8") as f:
        dialogues = json.load(f)

    if not isinstance(dialogues, list):
         print(f"⚠️ Expected list in {json_path}, got {type(dialogues)}")
         return pd.DataFrame()

    rows = []
    for i, d in enumerate(dialogues):
        # Use existing 'id' or fallback
        d_id = d.get("id", f"{split_name}_{i}")
        rows.append(process_dialogue(d, d_id))

    df = pd.DataFrame(rows).fillna(0)

    # Add column for split
    df.insert(0, "split", split_name)

    # Save per-split CSV
    df.to_csv(out_file, index=False)
    return df

def plot_histograms(df, split_name, out_dir="./statistics/plots"):
    os.makedirs(out_dir, exist_ok=True)
    metrics = ["num_edus", "num_relations", "num_speakers"]

    for metric in metrics:
        if metric not in df.columns:
            print(f"⚠️ Skipping {metric}, not found in dataframe for {split_name}")
            continue

        plt.figure()
        df[metric].astype(float).hist(bins=20)
        plt.title(f"{metric} distribution ({split_name})")
        plt.xlabel(metric)
        plt.ylabel("Count")
        plt.savefig(os.path.join(out_dir, f"{split_name}_{metric}.png"))
        plt.close()


def plot_combined_kde(all_df, out_dir="./statistics/plots"):
    os.makedirs(out_dir, exist_ok=True)
    metrics = ["num_edus", "num_relations", "num_speakers"]
    palette = {"train": "blue", "dev": "green", "test": "orange"}  # consistent colors

    for metric in metrics:
        if metric not in all_df.columns:
            print(f"⚠️ Skipping {metric}, not found in dataframe")
            continue

        plt.figure(figsize=(8, 6))

        for split, color in palette.items():
            subset = all_df[all_df["split"] == split]
            if len(subset) == 0:
                continue
            sns.kdeplot(
                data=subset,
                x=metric,
                fill=True,
                alpha=0.4,
                linewidth=2,
                color=color,
                label=split
            )

        plt.title(f"KDE Distribution of {metric} across splits")
        plt.xlabel(metric)
        plt.ylabel("Density")
        plt.legend(title="Split")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"{metric}_kde.png"))
        plt.close()

def plot_combined_boxplots(all_df, out_dir="./statistics/plots"):
    os.makedirs(out_dir, exist_ok=True)
    metrics = ["num_edus", "num_relations", "num_speakers"]

    for metric in metrics:
        if metric not in all_df.columns:
            print(f"⚠️ Skipping {metric}, not found in dataframe")
            continue

        plt.figure(figsize=(8, 6))
        sns.boxplot(
            data=all_df,
            x="split",
            y=metric,
            palette={"train": "blue", "dev": "green", "test": "orange"}
        )
        sns.stripplot(   # overlay points for visibility
            data=all_df,
            x="split",
            y=metric,
            color="black",
            alpha=0.5,
            size=4
        )
        plt.title(f"Boxplot of {metric} across splits")
        plt.xlabel("Split")
        plt.ylabel(metric)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"{metric}_boxplot.png"))
        plt.close()

def describe_series(series):
    """Return min, max, mean, Q1, median, Q3 for a pandas Series or list."""
    if len(series) == 0:
        return {}
    q1, median, q3 = np.percentile(series, [25, 50, 75])
    return {
        "mean": float(np.mean(series)),
        "min": float(np.min(series)),
        "max": float(np.max(series)),
        "Q1": float(q1),
        "median": float(median),
        "Q3": float(q3),
    }

def describe_list(values):
    """Return min, max, mean, median, Q1, Q3 for a list of numbers."""
    if not values:
        return {
            "mean": None,
            "min": None,
            "max": None,
            "median": None,
            "Q1": None,
            "Q3": None,
        }
    arr = np.array(values)
    return {
        "mean": float(np.mean(arr)),
        "min": int(np.min(arr)),
        "max": int(np.max(arr)),
        "median": float(np.median(arr)),
        "Q1": float(np.percentile(arr, 25)),
        "Q3": float(np.percentile(arr, 75)),
    }

def aggregate_relation_types(df):
    """Aggregate relation type counts across all files in this DataFrame."""
    counter = Counter()
    for _, row in df.iterrows():
        for rel in row["__relations"]:
            if "type" in rel:
                counter[rel["type"]] += 1
    return dict(counter)


def aggregate_multi_addressees(df):
    """Aggregate addressee counts (number of addressees per EDU) across files."""
    counter = Counter()
    has_any = False
    for _, row in df.iterrows():
        for edu in row["__edus"]:
            if "addressees" in edu:
                has_any = True
                addrs = edu.get("addressees", [])
                if isinstance(addrs, list):
                    if "everyone" in addrs:
                        counter["everyone"] += 1
                    else:
                        counter[len(addrs)] += 1
    
    if not has_any:
        return None

    # Sort numeric keys and then add 'everyone' if present
    sorted_keys = sorted([k for k in counter if isinstance(k, int)])
    sorted_dict = {str(k): counter[k] for k in sorted_keys}
    if "everyone" in counter:
        sorted_dict["everyone"] = counter["everyone"]
    return sorted_dict

def aggregate_relation_distances(df):
    relation_distances = {}
    relation_distances_by_type = defaultdict(lambda: defaultdict(int))

    for _, row in df.iterrows():
        if "__relations" in row and isinstance(row["__relations"], list): # Changed from "relations" to "__relations"
            for relation in row["__relations"]:
                if "x" in relation and "y" in relation and "type" in relation:
                    x_val = relation["x"]
                    y_val = relation["y"]
                    distance = abs(x_val - y_val)
                    relation_type = relation["type"]

                    relation_distances[str(distance)] = relation_distances.get(str(distance), 0) + 1
                    relation_distances_by_type[relation_type][str(distance)] += 1

    # Sort the keys numerically for overall relation distances
    sorted_relation_distances = {str(k): relation_distances[str(k)] for k in sorted([int(k) for k in relation_distances.keys()])} if relation_distances else {}

    # Sort the keys numerically for each relation type
    sorted_relation_distances_by_type = {}
    for rel_type, distances_map in relation_distances_by_type.items():
        sorted_relation_distances_by_type[rel_type] = {str(k): distances_map[str(k)] for k in sorted([int(k) for k in distances_map.keys()])} if distances_map else {}

    return sorted_relation_distances, sorted_relation_distances_by_type


def group_distance_map(distances_map):
    """Group distance counts into specified ranges."""
    grouped = {
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 0,
        "5": 0,
        "6-10": 0,
        "11-99": 0,
        ">=100": 0
    }
    for dist_str, count in distances_map.items():
        try:
            d = int(dist_str)
            if d == 1: grouped["1"] += count
            elif d == 2: grouped["2"] += count
            elif d == 3: grouped["3"] += count
            elif d == 4: grouped["4"] += count
            elif d == 5: grouped["5"] += count
            elif 6 <= d <= 10: grouped["6-10"] += count
            elif 11 <= d <= 99: grouped["11-99"] += count
            elif d >= 100: grouped[">=100"] += count
        except ValueError:
            continue
    return grouped


def compute_statistics(all_df, out_file="statistics.json"):
    stats = {}
    for split in ["all", "train", "dev", "test"]:
        df = all_df if split == "all" else all_df[all_df["split"] == split]

        if df.empty:
            continue

        # ---- core distributions ----
        num_edus = df["num_edus"]
        num_relations = df["num_relations"]
        num_speakers = df["num_speakers"]
        num_non_verbal = df["num_non_verbal_actions"]  # New metric
        num_multi_parent = df["num_multi_parent_nodes"]
        num_multi_child = df["num_multi_child_nodes"]
        num_multi_rel_pairs = df["num_pairs_with_multi_relations"]

        # gather relation distances + num_addressees from raw fields
        distances, addrs_per_edu, all_edu_char_lengths, dates, day_agendas = [], [], [], [], Counter()
        distances_by_type = defaultdict(list)
        for _, row in df.iterrows():
            if "__relations" in row and isinstance(row["__relations"], list):
                for rel in row["__relations"]:
                    if "x" in rel and "y" in rel:
                        dist = abs(rel["x"] - rel["y"])
                        distances.append(dist)
                        if "type" in rel:
                            distances_by_type[rel["type"]].append(dist)
            if "__edus" in row and isinstance(row["__edus"], list):
                for edu in row["__edus"]:
                    if "addressees" in edu:
                        addrs = edu.get("addressees", [])
                        if isinstance(addrs, list):
                            addrs_per_edu.append(len(addrs))
            if "__edu_char_lengths" in row and isinstance(row["__edu_char_lengths"], list):
                all_edu_char_lengths.extend(row["__edu_char_lengths"])
            if "date" in row and row["date"]:
                day_agendas[row["date"]] += 1
                try:
                    dates.append(datetime.strptime(row["date"], "%d%m%Y"))
                except ValueError:
                    pass

        multi_addressees_distribution = aggregate_multi_addressees(df)
        relation_distances_overall, relation_distances_by_type = aggregate_relation_distances(df)

        date_range = {}
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            date_range = {
                "min": min_date.strftime("%d/%m/%Y"),
                "max": max_date.strftime("%d/%m/%Y"),
                "range_days": (max_date - min_date).days,
                "unique_days": len(day_agendas),
                "agendas_per_day": dict(day_agendas)
            }

        # ---- build stats dict ----
        stats[split] = {
            # totals
            "total_num_edus": int(num_edus.sum()),
            "total_num_relations": int(num_relations.sum()),
            "total_num_speakers": int(num_speakers.sum()),
            "total_num_non_verbal_actions": int(num_non_verbal.sum()),  # New total
            "total_num_multi_parent_nodes": int(num_multi_parent.sum()),
            "total_num_multi_child_nodes": int(num_multi_child.sum()),
            "total_num_pairs_with_multi_relations": int(num_multi_rel_pairs.sum()),

            # descriptive stats
            "num_edus": describe_series(num_edus),
            "num_relations": describe_series(num_relations),
            "num_speakers": describe_series(num_speakers),
            "num_non_verbal_actions": describe_series(num_non_verbal),  # New stats
            "num_multi_parent_nodes": describe_series(num_multi_parent),
            "num_multi_child_nodes": describe_series(num_multi_child),
            "num_pairs_with_multi_relations": describe_series(num_multi_rel_pairs),
            "relation_distance": describe_list(distances),
            "edu_char_length": describe_list(all_edu_char_lengths),
            "doc_char_length": describe_series(df["doc_char_count"]),

            # date range
            "date_range": date_range,

            # counts (relation types and addressee per EDU)
            "relation_types": aggregate_relation_types(df),
            "relation_distances_distribution": relation_distances_overall,
            "relation_distances_distribution_grouped": group_distance_map(relation_distances_overall),
        }

        # Conditionally add addressee stats
        if addrs_per_edu:
            stats[split]["num_addressees"] = describe_list(addrs_per_edu)
            stats[split]["multi_addressees"] = multi_addressees_distribution

        for rel_type, dist_list in distances_by_type.items():
            stats[split][f"relation_distance_{rel_type.lower()}"] = describe_list(dist_list)
            
            # Distance stats (Median, %d=1, %d=2, %d=3, %d>=4)
            if dist_list:
                total = len(dist_list)
                arr = np.array(dist_list)
                stats[split][f"relation_distance_distance_stat_{rel_type.lower()}"] = {
                    "median": float(np.median(arr)),
                    "% d=1": float((arr == 1).sum() / total * 100),
                    "% d=2": float((arr == 2).sum() / total * 100),
                    "% d=3": float((arr == 3).sum() / total * 100),
                    "% d>=4": float((arr >= 4).sum() / total * 100),
                }

        for rel_type, distances_map in relation_distances_by_type.items():
            stats[split][f"relation_distances_distribution_{rel_type.lower()}"] = distances_map
            stats[split][f"relation_distances_distribution_{rel_type.lower()}_grouped"] = group_distance_map(distances_map)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate statistics for dialogue datasets.")
    parser.add_argument("--dataset", type=str, default="diam", choices=["diam", "molweni", "stac", "msdc"], 
                        help="Dataset name (default: diam)")
    args = parser.parse_args()

    dataset = args.dataset
    if dataset == "diam":
        stats_dir = "./statistics"
        data_dir = "data"
    else:
        stats_dir = f"./statistics_{dataset}"
        data_dir = dataset

    plots_dir = os.path.join(stats_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    dfs = []
    
    # We now look for these specific files
    split_files = {
        "train": os.path.join(data_dir, "train.json"),
        "dev":   os.path.join(data_dir, "dev.json"),
        "test":  os.path.join(data_dir, "test.json")
    }

    for split, json_path in split_files.items():
        out_file = os.path.join(stats_dir, f"{split}.csv")
        df = process_split(json_path, split, out_file)
        
        if not df.empty:
            dfs.append(df)
            # Plot per split
            plot_histograms(df, split, plots_dir)

    if dfs:
        # Concatenate everything
        all_df = pd.concat(dfs, ignore_index=True).fillna(0)
        all_df.to_csv(os.path.join(stats_dir, "all.csv"), index=False)

        # Plot combined distributions
        plot_combined_kde(all_df, plots_dir)
        plot_combined_boxplots(all_df, plots_dir)
        plot_combined_histograms(all_df, plots_dir)

        # Compute all stats
        compute_statistics(all_df, os.path.join(stats_dir, "statistics.json"))
    else:
        print(f"No data processed for {dataset}.")


