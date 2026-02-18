# 1. SDDP
# Copy the generated JSONs, and renamed them as train/dev/test.json respectively.
# Placed them into the SDDP data/diam folder as the paths and filenames are hardcoded.
# You still need to run the `parse.sh` in their repo for training.
python segment_dialogue.py ../data/train.json  ../data/train-context-20-stride-10.json  --context_size 20 --stride 10
python segment_dialogue.py ../data/dev.json    ../data/dev-context-20-stride-10.json    --context_size 20 --stride 10
python segment_dialogue.py ../data/test.json   ../data/test-context-20-stride-10.json   --context_size 20 --stride 10

# 2. GPTforDDA
# Nothing need to be done

# 3. Seq2Seq-DDP
# Nothing need to be done
