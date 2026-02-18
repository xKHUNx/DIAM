import json
import argparse
import os
import math

def get_segments(edus, window_size, stride):
    """
    Splits a list of EDUs into segments (chunks) based on window_size and stride.
    Returns a list of tuples (segment_edus, start_index, end_index).
    """
    if not edus:
        return []
    
    segments = []
    num_edus = len(edus)
    
    # If smaller than window, just take the whole thing
    if num_edus <= window_size:
        return [(edus, 0, num_edus)]

    # Sliding window
    start = 0
    while start < num_edus:
        end = min(start + window_size, num_edus)
        segment = edus[start:end]
        segments.append((segment, start, end))
        
        # If we reached the end, stop
        if end == num_edus:
            break
            
        start += stride
        
    return segments

def process_file(input_path, output_path, context_size, stride):
    print(f"Reading from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    segmented_data = []

    for entry in data:
        original_id = entry.get('id', 'unknown')
        edus = entry.get('edus', [])
        
        # Determine segments
        segments_with_indices = get_segments(edus, context_size, stride)
        
        for i, (segment_edus, start, end) in enumerate(segments_with_indices):
            
            # Construct new ID
            new_id = f"{original_id}_window_{start}_{end-1}"
            
            # Filter and adjust relations
            original_relations = entry.get('relations', [])
            new_relations = []
            for rel in original_relations:
                rx, ry = rel['x'], rel['y']
                if start <= rx < end and start <= ry < end:
                    new_rel = rel.copy()
                    new_rel['x'] = rx - start
                    new_rel['y'] = ry - start
                    new_relations.append(new_rel)

            # Process EDUs to update indices
            new_segment_edus = []
            for local_idx, edu in enumerate(segment_edus):
                new_edu = edu.copy()
                new_edu['original_index'] = new_edu.get('index')
                new_edu['index'] = local_idx
                new_segment_edus.append(new_edu)

            # Create new entry
            # We copy specific fields. 
            new_entry = {
                "id": new_id,
                "edus": new_segment_edus,
                "relations": new_relations
            }
            
            # Optionally preserve other non-list metadata if needed, 
            # but usually it's safer to stick to what we know is safe.
            # Copying top-level keys that are likely metadata (strings/numbers)
            for k, v in entry.items():
                if k not in ['id', 'edus', 'relations']:
                   new_entry[k] = v

            segmented_data.append(new_entry)

    print(f"Writing {len(segmented_data)} segments to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(segmented_data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Segment JSON dialogue data using a sliding window.")
    parser.add_argument("input_file", help="Path to input JSON file")
    parser.add_argument("output_file", help="Path to output JSON file")
    parser.add_argument("--context_size", type=int, default=20, help="Max context size (window size)")
    parser.add_argument("--stride", type=int, default=10, help="Stride size")

    args = parser.parse_args()

    process_file(args.input_file, args.output_file, args.context_size, args.stride)

if __name__ == "__main__":
    main()
