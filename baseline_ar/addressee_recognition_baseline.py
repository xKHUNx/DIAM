import json
import os
import argparse
from tqdm import tqdm
from openai import OpenAI
from typing import List, Dict

# Set up OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_candidate_pool(edus: List[Dict]) -> List[str]:
    """
    Extract all unique speakers in the session. "everyone" is always the first candidate.
    """
    speakers = set()
    for edu in edus:
        speaker = edu.get("speaker")
        if speaker and speaker.lower() != "everyone":
            speakers.add(speaker)
    
    candidates = ["everyone"] + sorted(list(speakers))
    return candidates

def format_edu(edu: Dict, index_in_session: int) -> str:
    return f"[edu{index_in_session}] {edu.get('speaker', 'Unknown')}: {edu.get('text', '')}"

def predict_session_addressees(edus: List[Dict], candidate_pool: List[str], model: str = "gpt-3.5-turbo-0125"):
    """
    Call ChatGPT to predict addressees for all EDUs in a session at once using full candidate names.
    """
    edus_str = "\n".join([format_edu(edu, i) for i, edu in enumerate(edus)])
    candidates_str = ", ".join(candidate_pool)
    
    prompt = f"""You are an assistant specializing in dialogue analysis. Given a conversation, identify the addressee(s) for EVERY utterance (EDU).

Candidates Pool (possible addressees):
{candidates_str}

Conversation:
{edus_str}

Instructions:
1. For each EDU in the conversation (identified by [edu0], [edu1], etc.), identify who the speaker is addressing.
2. The addressee(s) MUST be EXACTLY one or more items from the Candidates Pool above.
3. If an utterance is directed to everyone, use "everyone".
4. Multiple addressees are allowed (e.g., ["Speaker A", "Speaker B"]).
5. Return a JSON object with a key "addressees" containing a list of lists of strings. Each inner list corresponds to the candidate name(s) for the EDU at that index.

Output format:
{{
  "addressees": [
    ["everyone"],
    ["Name 1"],
    ["Name 2", "Name 3"],
    ...
  ]
}}
"""

    try:
        if not os.getenv("OPENAI_API_KEY"):
            return [["API_KEY_MISSING"]] * len(edus)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant specializes in dialogue discourse parsing."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        predicted_addressees = result.get("addressees", [])
        
        # Validation
        if len(predicted_addressees) != len(edus):
            print(f"Warning: Expected {len(edus)} addressee entries, but got {len(predicted_addressees)}. Padding/Truncating.")
            if len(predicted_addressees) < len(edus):
                predicted_addressees.extend([[]] * (len(edus) - len(predicted_addressees)))
            else:
                predicted_addressees = predicted_addressees[:len(edus)]
        
        # Simple cleanup - ensure they are in the pool or return as is if close enough
        return predicted_addressees
        
    except Exception as e:
        print(f"Error predicting for session: {e}")
        return [[]] * len(edus)

def main():
    parser = argparse.ArgumentParser(description="Addressee Recognition Baseline (Session-level) using ChatGPT")
    parser.add_argument("--input_file", type=str, required=True, help="Path to the input JSON file")
    parser.add_argument("--output_file", type=str, required=True, help="Path to save the predictions")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo-0125", help="OpenAI model to use")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of sessions to process")
    
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Input file {args.input_file} not found.")
        return

    with open(args.input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Input file should be a list of dialogue sessions.")
        return

    output_results = []
    
    sessions_to_process = data[:args.limit] if args.limit else data

    for session in tqdm(sessions_to_process, desc="Processing Sessions"):
        edus = session.get("edus", [])
        if not edus:
            continue
            
        dialogue_id = session.get("id", "Unknown")
        candidate_pool = get_candidate_pool(edus)
        
        predictions = predict_session_addressees(edus, candidate_pool, model=args.model)
        
        output_results.append({
            "dialogue_id": dialogue_id,
            "addressees": predictions
        })

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(output_results, f, indent=2, ensure_ascii=False)

    print(f"Predictions saved to {args.output_file}")

if __name__ == "__main__":
    main()
