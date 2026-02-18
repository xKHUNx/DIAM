# DIAM: Discourse Interaction and Addressee Modeling for Malaysia Hansard

This project contains tools and baselines for Discourse Interaction and Addressee Modeling for Malaysia Hansard (DIAM) dataset.

## 1. Generating Dataset Statistics

You can generate comprehensive statistics and visualizations for the dataset (train, dev, and test splits) using the `generate_statistics.py` script.

### Usage
Run the script from the root directory:
```bash
python generate_statistics.py --dataset diam
```

### Outputs
The statistics are saved in the `statistics/` folder:
- `statistics.json`: Detailed numeric stats (EDU counts, relation types, etc.).
- `all.csv`, `train.csv`, `dev.csv`, `test.csv`: Tabular data for each split.
- `plots/`: Visualizations including histograms and KDE plots for EDU/relation distributions.

---

## 2. Evaluating DDP (Dialogue Discourse Parsing) Baselines

Evaluating a baseline model for DDP follows a multi-step pipeline to ensure all model outputs are standardized and reconstructed into full dialogues before scoring.

### Step A: Data Segmentation (Optional)
If a baseline requires windowed input (e.g., SDDP), use `segment_dialogue.py` to chunk the data.
```bash
python baseline_ddp/segment_dialogue.py data/test.json data/test-segmented.json --context_size 20 --stride 10
```

### Step B: Standardize Baseline Outputs
Convert raw baseline outputs into a "Universal" JSON format.
```bash
# Supported types: sddp, seq2seq, gpt
python baseline_ddp/standardize_baseline_outputs.py <path_to_raw_output> <path_to_converted.json> --type <model_type> --mapping_file <optional_mapping_json>
```

### Step C: Reconstruct Full Dialogue
Merge the standardized segments back into full dialogue sessions.
```bash
python baseline_ddp/reconstruct_full_dialogue.py <path_to_converted.json> <path_to_reconstructed.json>
```

### Step D: Evaluate
Score the reconstructed predictions against the ground truth.
```bash
python baseline_ddp/evaluate_ddp_baseline.py data/test.json <path_to_reconstructed.json>
```

> **Note:** For convenience, you can refer to `baseline_ddp/standardize_baseline_outputs.sh` for pre-configured commands for SDDP, Seq2Seq-DDP, and GPTforDDA.

---

## 3. Addressee Recognition (AR) Baseline

The project includes a session-level baseline for Addressee Recognition using large language models.

### Running the Baseline
To generate predictions for addressees:
```bash
python baseline_ar/addressee_recognition_baseline.py --input_file data/test.json --output_file baseline_ar/predictions.json --model gpt-5.2
```

### Evaluating the Baseline
To evaluate the predictions against ground truth:
```bash
python baseline_ar/evaluate_ar_baseline.py --gt_file data/test.json --pred_file baseline_ar/predictions.json
```

---

## 4. Graph Visualizer

The project includes a web-based Graph Visualizer to interactively explore dialogue relations.

### How to use
1. Open `graph_visualizer/index.html` in any modern web browser.
2. Click **Load JSON** and select a DIAM formatted JSON file (e.g., `data/test.json`).
3. Select a specific conversation from the dropdown menu to visualize its discourse graph.
4. Interact with nodes (EDUs) to see text and metadata, and use the **Summary** buttons to view session-wide analytics.
