# DIAM: Discourse Interaction and Addressee Modeling for Malaysia Hansard

This project contains the dataset, tools, and baselines for Discourse Interaction and Addressee Modeling for Malaysia Hansard (DIAM).

## 1. Dataset & Annotation Protocol

The annotated DIAM corpus is in `data/` (`train.json`, `dev.json`, `test.json`). Each Elementary Unit (EU — either a verbal EDU or a non-verbal EEU) carries one or more addressees and is connected to others by discourse relations under an SDRT-based framework with 17 relation types.

The full annotation protocol is documented in [`annotation_guidelines/ANNOTATION_GUIDELINES.md`](annotation_guidelines/ANNOTATION_GUIDELINES.md), covering EDU/EEU segmentation, addressee rules, the 17 relation types (with cues and Hansard examples), graph structure (multi-parent / multi-child DAG), and known sources of annotator disagreement. UI screenshots of the annotation tool are in `annotation_guidelines/Annotation_Guideline.pdf` (supplementary).

## 2. Baselines

### 2.1 Dialogue Discourse Parsing (DDP)

We benchmark four DDP baselines spanning three paradigms — a task-specialised structured parser, a fully fine-tuned generative model, and prompted LLMs. Each row links to the upstream repository the code was modified from.

| Baseline | Type | Upstream Repo |
|---|---|---|
| **SDDP** (Chi & Rudnicky 2022) | Specialised supervised structured parser (non-LLM) | [chijames/structured_dialogue_discourse_parsing](https://github.com/chijames/structured_dialogue_discourse_parsing) |
| **Seq2Seq-DDP** (Li et al. 2024) | Fully fine-tuned open T0-3B generative model | [chuyuanli/Seq2Seq-DDP](https://github.com/chuyuanli/Seq2Seq-DDP) |
| **Vanilla Llama-3.1-8B** | Prompted open LLM probe (no fine-tuning) | [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) |
| **GPTforDDA** (Fan et al. 2024) | Prompted ChatGPT (code open; requires your own OpenAI API key) | [yxfanSuda/GPTforDDA](https://github.com/yxfanSuda/GPTforDDA) |

Our `baseline_ddp/` directory contains the glue scripts (segmentation, output standardisation, reconstruction, evaluation) used to run each baseline against DIAM; the actual model code lives upstream. Detailed model configurations, decoding parameters, and generation budgets used in the paper are in the paper's Reproducibility appendix.

### 2.2 Addressee Recognition (AR)

A prompted ChatGPT (`gpt-5.2`) baseline is provided in `baseline_ar/`. Because no prior open multi-addressee resolver exists for parliamentary dialogue, the baseline is purpose-built for DIAM and lives entirely in this repository; running it requires your own OpenAI API key.

---

## 3. Generating Dataset Statistics

You can generate comprehensive statistics and visualizations for the dataset (train, dev, and test splits) using the `generate_statistics.py` script.

### Usage
Run the script from the root directory:
```bash
python generate_statistics.py --dataset diam
```

### Outputs
The statistics are saved in the `statistics/` folder:
- `statistics.json`: Detailed numeric stats (EU counts, relation types, etc.).
- `all.csv`, `train.csv`, `dev.csv`, `test.csv`: Tabular data for each split.
- `plots/`: Visualizations including histograms and KDE plots for EU/relation distributions.

---

## 4. Evaluating DDP (Dialogue Discourse Parsing) Baselines

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

## 5. Vanilla LLM Windowing Probe

In addition to the main DDP baselines, we include a controlled within-model probe using **vanilla Llama-3.1-8B-Instruct** (no fine-tuning) to study how the input regime — full dialogue vs.\ 20-EU windows (stride 10) — affects parsing performance. Raw generations, parsed predictions, and evaluation results are in `llama3_1_vanilla/`. The model is fully open; the experimental setup (prompt format, generation budget, decoding) is documented in the paper's Reproducibility appendix.

---

## 6. Addressee Recognition (AR) Baseline

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

## 7. Graph Visualizer

The project includes a web-based Graph Visualizer to interactively explore dialogue relations.

### How to use
1. Open `graph_visualizer/index.html` in any modern web browser.
2. Click **Load JSON** and select a DIAM formatted JSON file (e.g., `data/test.json`).
3. Select a specific conversation from the dropdown menu to visualize its discourse graph.
4. Interact with nodes (EDUs) to see text and metadata, and use the **Summary** buttons to view session-wide analytics.

---

## 8. License & Citation

- **Data** (`data/`, `statistics/`, `annotation_guidelines/`): released under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). See [`DATA_LICENSE`](DATA_LICENSE).
- **Code** (Python scripts, shell scripts, the graph visualizer): released under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). See [`LICENSE`](LICENSE).
- **Citation:** BibTeX will be provided upon paper publication.
