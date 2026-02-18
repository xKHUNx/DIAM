import json
import argparse
import os
import re
import ast

def parse_seq2seq_gen_output(gen_output):
    """
    Parses the generation output string from Seq2Seq model.
    Expected format: [ Speaker: Text | edu0 | root = edu0 ] [ ... | edu1 | Continuation = edu0 ] ...
    """
    # Clean wrapping brackets if the whole string is wrapped
    inner = gen_output.strip()
    if inner.startswith('[ ') and inner.endswith(' ]'):
        inner = inner[2:-2]
    elif inner.startswith('[') and inner.endswith(']'):
        inner = inner[1:-1]
        
    # Split by "] [" which separates EDUs
    # Note: simple split might be fragile if text contains "] [", but assuming standard format
    parts = inner.split(' ] [')
    
    edus = []
    relations = []
    label_to_index = {}
    
    for i, part in enumerate(parts):
        # We process the string assuming "Text | Label | Relation"
        # Since text can contain pipes, we split from the right
        # But commonly the format is fixed. Let's try splitting by " | ".
        
        segments = part.split(' | ')
        if len(segments) < 3:
            # Fallback or malformed
            continue
            
        # The last two are label and relation. The rest is text (joined back if split)
        edu_label = segments[-2].strip()
        relation_part = segments[-1].strip()
        text_part = " | ".join(segments[:-2]).strip()
        
        # Remove "Speaker: " prefix if standard
        # But we leave text as is for now or clean it if needed.
        
        label_to_index[edu_label] = i
        
        edus.append({
            "text": text_part,
            "index": i,
            "edu_label": edu_label
        })
        
        # Parse Relation: "Type = Target"
        if '=' in relation_part:
            rel_type, rel_target = [x.strip() for x in relation_part.split('=', 1)]
            
            # We ignore root relations for the list, or keep them if needed. 
            # Standard format usually implies dependency pairs.
            if rel_type.lower() != 'root':
                relations.append({
                    "source": edu_label,
                    "target": rel_target,
                    "type": rel_type,
                    "y": i 
                })

    # Resolve Relation Indices
    final_relations = []
    for rel in relations:
        target_label = rel['target']
        if target_label in label_to_index:
            final_relations.append({
                "y": rel['y'],
                "x": label_to_index[target_label],
                "type": rel['type']
            })
            
    return edus, final_relations

def parse_transition_gen_output(gen_output, current_edu_index):
    """
    Parses the generation output string from transition-based Seq2Seq model.
    Expected format: Type of [eduX] [Type of [eduY]] ... or just 'root'
    """
    relations = []
    if not gen_output or gen_output.strip().lower() == 'root':
        return relations
        
    # Regex to find relation patterns like "Relation of [eduX]" or "Relation of [ eduX]"
    # It can handle multiple relations in one line
    matches = re.finditer(r'([A-Za-z_-]+)\s+of\s+\[\s*edu(\d+)\s*\]', gen_output)
    for match in matches:
        rel_type = match.group(1)
        target_idx = int(match.group(2))
        relations.append({
            "y": current_edu_index,
            "x": target_idx,
            "type": rel_type
        })
    return relations

def parse_gpt_output(output_content):
    if not output_content:
        return []
    
    if isinstance(output_content, list):
        # If it's already a list of lists/dicts
        relations = []
        for item in output_content:
            if isinstance(item, list) and len(item) >= 3:
                relations.append({"x": item[0], "y": item[1], "type": item[2]})
            elif isinstance(item, dict) and "x" in item and "y" in item:
                relations.append(item)
        return relations
        
    if isinstance(output_content, str):
        # Try regex first as it's quite reliable for the expected format
        relations = []
        matches = re.finditer(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*[\'"]([^\'"]+)[\'"]\s*\]', output_content)
        for match in matches:
            relations.append({
                "x": int(match.group(1)),
                "y": int(match.group(2)),
                "type": match.group(3)
            })
        if relations:
            return relations
            
        # Fallback to ast.literal_eval if regex failed
        try:
            parsed = ast.literal_eval(output_content.strip())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, list) and len(item) >= 3:
                        relations.append({"x": item[0], "y": item[1], "type": item[2]})
                return relations
        except:
            pass
            
    return []

def convert_sddp(input_file, output_file, mapping_file):
    print(f"Converting SDDP from {input_file}...")
    
    if not mapping_file:
        raise ValueError("Mapping file is required for SDDP conversion to map integer IDs to string IDs.")
        
    predictions = []
    # Try reading as JSONL first, since that seems to be the format
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            # Read first line to check format
            first_line = f.readline()
            f.seek(0)
            json.loads(first_line) # Check if line is valid JSON
            
            for line in f:
                if line.strip():
                    predictions.append(json.loads(line))
    except json.JSONDecodeError:
        # Fallback to reading as a single JSON object (list)
        print("Warning: Failed to read as JSONL, attempting to read as standard JSON list...")
        with open(input_file, 'r', encoding='utf-8') as f:
            predictions = json.load(f)
        
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
        
    if len(predictions) != len(mapping_data):
        print(f"Warning: Number of predictions ({len(predictions)}) does not match mapping data ({len(mapping_data)}). Mapping might be misaligned.")
    
    converted_data = []
    for i, pred in enumerate(predictions):
        if i < len(mapping_data):
            ref_entry = mapping_data[i]
            str_id = ref_entry.get('id', pred.get('id', f"unknown_{i}"))
            
            # If the reference has EDUs, we can include them to make it "Universal"
            edus = ref_entry.get('edus', [])
            
            relations = pred.get("relations", [])
            if not relations and "gen_output" in pred:
                # Parse relations from gen_output if relations not explicit
                _, relations = parse_seq2seq_gen_output(pred["gen_output"])
            
            # Post-process relations: remove "Special" and shift indices
            final_relations = []
            for rel in relations:
                if rel.get("type") == "Special":
                    continue
                
                # Shift indices by -1 because 0 was dummy
                new_rel = rel.copy()
                new_rel["x"] = rel["x"] - 1
                new_rel["y"] = rel["y"] - 1
                final_relations.append(new_rel)

            entry = {
                "id": str_id,
                "edus": edus,
                "relations": final_relations
            }
            converted_data.append(entry)
            
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_file}")

def convert_seq2seq(input_file, output_file, mapping_file=None):
    print(f"Converting Seq2Seq from {input_file}...")
    
    mapping_data = {}
    if mapping_file:
        print(f"Loading reference data from {mapping_file}...")
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                raw_mapping = json.load(f)
                # Create lookup dict by ID
                for item in raw_mapping:
                    if 'id' in item:
                        mapping_data[str(item['id'])] = item
        except Exception as e:
            print(f"Warning: Failed to load mapping file: {e}")

    converted_data = []
    
    # Read all lines to peek at the format
    lines = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    if not lines:
        print("Warning: No valid JSON lines found in input file.")
        return

    # Check if it's transition-based (e.g., "root" or "Relation of [eduX]")
    first_gen = lines[0].get('gen_output', '')
    is_transition = first_gen.strip().lower() == 'root' or ' of [' in first_gen.lower()

    if is_transition:
        print("Detected transition-based format. Grouping by session...")
        # Group by base ID (everything before the last underscore)
        sessions = {}
        for obj in lines:
            full_id = str(obj.get('id', ''))
            if '_' in full_id:
                session_id, edu_idx_str = full_id.rsplit('_', 1)
                try:
                    edu_idx = int(edu_idx_str)
                except ValueError:
                    session_id = full_id
                    edu_idx = -1 # Or handle as non-indexed
            else:
                session_id = full_id
                edu_idx = -1
            
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append({
                "index": edu_idx,
                "gen_output": obj.get('gen_output', '')
            })
        
        for session_id, outputs in sessions.items():
            # Sort by EDU index if available
            outputs.sort(key=lambda x: x['index'])
            
            ref_entry = mapping_data.get(session_id)
            ref_edus = ref_entry.get('edus', []) if ref_entry else []
            
            session_relations = []
            for item in outputs:
                if item['index'] >= 0:
                    rels = parse_transition_gen_output(item['gen_output'], item['index'])
                    session_relations.extend(rels)
            
            # Use reference EDUs if available, otherwise minimal placeholders
            final_edus = []
            if ref_edus:
                for edu in ref_edus:
                    new_edu = edu.copy()
                    if 'original_index' not in new_edu and 'index' in new_edu:
                        new_edu['original_index'] = new_edu['index']
                    final_edus.append(new_edu)
            else:
                # Create minimal EDUs based on the indices we saw
                max_idx = max([x['index'] for x in outputs]) if outputs else -1
                for i in range(max_idx + 1):
                    final_edus.append({
                        "index": i,
                        "original_index": i,
                        "text": f"EDU {i}",
                        "speaker": "Unknown",
                        "addressees": []
                    })
            
            entry = {
                "id": session_id,
                "edus": final_edus,
                "relations": session_relations
            }
            converted_data.append(entry)
    else:
        # Original logic for non-transition (one dialogue/window per line)
        for obj in lines:
            str_id = str(obj.get('id'))
            gen_output = obj.get('gen_output', '')
            
            raw_edus, relations = parse_seq2seq_gen_output(gen_output)
            
            # Post-process EDUs for Seq2Seq
            # Get reference entry if available
            ref_entry = mapping_data.get(str_id)
            ref_edus = ref_entry.get('edus', []) if ref_entry else []
            
            processed_edus = []
            for edu in raw_edus:
                full_text = edu.get('text', '')
                speaker = ""
                content = full_text
                
                # Simple heuristic to extract speaker: "Speaker Name : Content"
                if " : " in full_text:
                    parts = full_text.split(" : ", 1)
                    speaker = parts[0].strip()
                    content = parts[1].strip()
                
                addressees = []
                idx = edu['index']
                
                ref_original_index = None
                if ref_edus and idx < len(ref_edus):
                    ref_edu = ref_edus[idx]
                    addressees = ref_edu.get('addressees', [])
                    ref_original_index = ref_edu.get('original_index')
                
                if ref_original_index is not None:
                    final_original_index = ref_original_index
                else:
                    start_offset = 0
                    match = re.search(r'_window_(\d+)_(\d+)$', str_id)
                    if match:
                        start_offset = int(match.group(1))
                    final_original_index = edu['index'] + start_offset

                new_edu = {
                    "text": content,
                    "speaker": speaker,
                    "addressees": addressees, 
                    "index": edu['index'],
                    "original_index": final_original_index
                }
                processed_edus.append(new_edu)

            entry = {
                "id": str_id,
                "edus": processed_edus,
                "relations": relations
            }
            converted_data.append(entry)
            
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_file}")

def convert_gpt(input_file, output_file):
    print(f"Converting GPT from {input_file}...")
    converted_data = []
    
    # Handle JSONL format
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                obj = json.loads(line)
                
                edus = obj.get('edus', [])
                # Ensure "original_index" exists
                for edu in edus:
                    if 'original_index' not in edu and 'index' in edu:
                        edu['original_index'] = edu['index']

                # Parse predictions from 'output' field
                relations = parse_gpt_output(obj.get('output', ''))
                
                # If 'output' was empty but 'relations' exists, we might want to skip or keep?
                # The user says "should take the content in 'output'". 
                # If output parsing fails, relations will be empty.
                
                # Keep only necessary fields
                entry = {
                    "id": obj.get('id'),
                    "edus": edus,
                    "relations": relations
                }
                converted_data.append(entry)
            except json.JSONDecodeError:
                continue

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Convert baseline outputs to a universal JSON format.")
    parser.add_argument("input_file", help="Path to the input file")
    parser.add_argument("output_file", help="Path to the output file")
    parser.add_argument("--type", choices=["sddp", "seq2seq", "gpt"], required=True, help="Type of the input model")
    parser.add_argument("--mapping_file", help="Path to the segmented JSON file (required for sddp, optional for seq2seq)")
    
    args = parser.parse_args()
    
    if args.type == "sddp":
        convert_sddp(args.input_file, args.output_file, args.mapping_file)
    elif args.type == "seq2seq":
        convert_seq2seq(args.input_file, args.output_file, args.mapping_file)
    elif args.type == "gpt":
        convert_gpt(args.input_file, args.output_file)

if __name__ == "__main__":
    main()
