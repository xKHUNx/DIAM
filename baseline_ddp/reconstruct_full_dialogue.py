import json
import argparse
import re
import os
from collections import defaultdict

def reconstruct(input_file, output_file):
    print(f"Processing {input_file} -> {output_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Group by base ID
    # Pattern: ID_window_START_END
    # Example: DR-06112023-03_window_0_19
    regex = re.compile(r'^(.*)_window_(\d+)_(\d+)$')

    grouped = defaultdict(list)

    for entry in data:
        eid = str(entry['id'])
        match = regex.match(eid)
        if match:
            base_id = match.group(1)
            start_off = int(match.group(2))
            grouped[base_id].append({
                'entry': entry,
                'start': start_off
            })
        else:
            # Not segmented or unknown format, treat as base
            grouped[eid].append({
                'entry': entry,
                'start': 0
            })

    output_data = []

    for base_id, chunks in grouped.items():
        # Sort chunks by start offset to process in order
        chunks.sort(key=lambda x: x['start'])

        final_edus = {}
        final_relations = [] 

        for chunk in chunks:
            offset = chunk['start']
            entry = chunk['entry']
            
            # Process EDUs
            for edu in entry.get('edus', []):
                # Use original_index if available (global index), otherwise use index + offset
                # If original_index is strictly local (0,1,2), this logic fails.
                # But we fixed standardize script to make original_index global.
                # So we prioritize original_index.
                
                # However, our reconstruction logic previously used local_idx + offset.
                # If standardize script is fixed, 'original_index' is now GLOBAL.
                # 'index' might still be local (0..N).
                
                # Let's verify what we want.
                # We want to place this EDU in the global map.
                
                local_idx = edu.get('index')
                original_idx = edu.get('original_index')
                
                if original_idx is not None:
                    global_idx_candidate = original_idx
                elif local_idx is not None:
                    global_idx_candidate = offset + local_idx
                else:
                    continue
                
                # Check consistency if it already exists
                if global_idx_candidate in final_edus:
                    continue

                # Create new EDU
                new_edu = edu.copy()
                # Ensure index is global in the reconstructed file
                new_edu['index'] = global_idx_candidate
                new_edu['original_index'] = global_idx_candidate
                
                final_edus[global_idx_candidate] = new_edu
            
            # Process Relations
            for rel in entry.get('relations', []):
                x = rel.get('x')
                y = rel.get('y')
                
                if x is None or y is None:
                    continue

                # x and y are typically indices. 
                # If they refer to local indices, we need to shift them.
                # If the input file has them as local indices (0..N), we add offset.
                
                # Assumption: standardize script produces local relations (0..N) in each window.
                
                new_rel = rel.copy()
                new_rel['x'] = offset + x
                new_rel['y'] = offset + y
                
                final_relations.append(new_rel)

        # Reassemble EDUs into a list
        if not final_edus:
            sorted_edus = []
        else:
            max_idx = max(final_edus.keys())
            sorted_edus = []
            # Ensure continuity
            for i in range(max_idx + 1):
                if i in final_edus:
                    sorted_edus.append(final_edus[i])
                else:
                    # Gap
                    sorted_edus.append({
                        "text": "",
                        "speaker": "",
                        "index": i,
                        "original_index": i,
                        "is_gap": True
                    })

        new_entry = {
            "id": base_id,
            "edus": sorted_edus,
            "relations": final_relations
        }
        output_data.append(new_entry)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Done. Reconstructed {len(output_data)} documents.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruct segmented dialogues into full dialogues.")
    parser.add_argument("input_file", help="Path to the input JSON file (converted output)")
    parser.add_argument("output_file", help="Path to save the reconstructed JSON file")
    
    args = parser.parse_args()
    
    reconstruct(args.input_file, args.output_file)
