import sys
import json
import argparse

def normalize_text(text: str, token_limit: int = 4000):
    """
    Enforces the 'Bed of Procrustes' on input data.
    Truncates if too long, pads with metadata if too short.
    """
    # 1. Amputation (Truncation)
    if len(text) > (token_limit * 4): # Rough char to token estimate
        print(f"[Procrustes] Input exceeds limit. Amputating...")
        text = text[:(token_limit * 4)] + "\n...[CONTENT TRUNCATED BY PROCRUSTES]..."
    
    # 2. Stretching (Padding with context)
    if len(text) < 100:
        print(f"[Procrustes] Input too short. Stretching with system metadata...")
        text = f"[METADATA] System: Gemini-OP | State: Active\n[CONTENT]\n{text}"
        
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--limit", type=int, default=4000)
    args = parser.parse_args()
    
    print(normalize_text(args.text, args.limit))

if __name__ == "__main__":
    main()
