import argparse
import os
import re
from pathlib import Path

# Common conversational filler to remove
FILLER_PATTERNS = [
    r"I agree with agent \d+",
    r"Let's think about this",
    r"That's a good point",
    r"Building on what was said",
    r"In conclusion",
    r"To summarize",
    r"As previously mentioned",
    r"I will now",
    r"Let's consider",
    r"It is important to note"
]

def compress_text(text: str) -> str:
    """
    Maxwell's Demon: Artificially lowers entropy by deleting filler.
    """
    original_len = len(text)
    
    # Remove filler lines/phrases
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # Simple compression: remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    # In a real system, this would use a transformer to summarize/vectorize
    # For now, we simulate 'dense vector' by keeping only high-signal sentences (pseudo-vectorization)
    sentences = text.split(". ")
    dense_sentences = [s for s in sentences if len(s) > 20] # Keep only substantial sentences
    
    compressed = ". ".join(dense_sentences)
    
    new_len = len(compressed)
    reduction = ((original_len - new_len) / original_len * 100) if original_len > 0 else 0
    
    print(f"[Maxwell] Context Compressed: {original_len} -> {new_len} tokens ({reduction:.1f}% reduction)")
    return compressed

def process_round_outputs(run_dir: Path, round_num: int):
    """
    Finds round outputs and applies Maxwell's Demon compression.
    """
    for f in run_dir.glob(f"round{round_num}_agent*.md"):
        print(f"[Maxwell] Venting heat from {f.name}...")
        content = f.read_text(encoding='utf-8')
        compressed = compress_text(content)
        
        # Write compressed version back (or to a .compressed file)
        # The prompt says 'venting the heat... so the core can keep thinking'
        # We'll overwrite the file so the next round's context builder sees the compressed version.
        f.write_text(compressed, encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Maxwell's Demon: Context Entropy Radiator.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--round", type=int, required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    process_round_outputs(run_dir, args.round)

if __name__ == "__main__":
    main()
