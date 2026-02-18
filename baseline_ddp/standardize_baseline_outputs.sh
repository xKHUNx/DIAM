# Structured Dialogue Discourse Parsing (SDDP)
# windows: 
python standardize_baseline_outputs.py baseline_result/structured_dialogue_discourse_parsing/test_predictions.json baseline_result/structured_dialogue_discourse_parsing/converted.json --type sddp --mapping_file ../data/test-context-20-stride-10.json
python reconstruct_full_dialogue.py baseline_result/structured_dialogue_discourse_parsing/converted.json baseline_result/structured_dialogue_discourse_parsing/reconstructed.json
python evaluate_ddp_baseline.py ../data/test.json baseline_result/structured_dialogue_discourse_parsing/reconstructed.json

# Seq2Seq-DDP
# windows: 
python standardize_baseline_outputs.py baseline_result/Seq2Seq-DDP/t0-3b-3b_train_diam_test_diam_natural2_seed27_gen512_lr2e-5-v2.jsonl baseline_result/Seq2Seq-DDP/converted.json --type seq2seq --mapping_file ../data/test-context-8-stride-4.json
python reconstruct_full_dialogue.py baseline_result/Seq2Seq-DDP/converted.json baseline_result/Seq2Seq-DDP/reconstructed.json
python evaluate_ddp_baseline.py ../data/test.json baseline_result/Seq2Seq-DDP/reconstructed.json

# GPTforDDA
# windows: 
python standardize_baseline_outputs.py baseline_result/GPTforDDA/DIAMResponse.json baseline_result/GPTforDDA/converted.json --type gpt
python evaluate_ddp_baseline.py ../data/test.json baseline_result/GPTforDDA/reconstructed.json

