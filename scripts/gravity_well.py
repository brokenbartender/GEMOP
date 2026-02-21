import argparse
import sys
import os
from pathlib import Path
import math

try:
    from sentence_transformers import SentenceTransformer, util
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    MODEL = None

def calculate_semantic_mass(anchor_text: str, candidates: list) -> list:
    """
    Calculates the 'Semantic Mass' of memory blocks.
    Heavier mass = Higher relevance to the anchor.
    """
    results = []
    if not candidates:
        return results
    
    if MODEL:
        # Vector-based Gravity (High Precision)
        anchor_vec = MODEL.encode(anchor_text, convert_to_tensor=True)
        cand_vecs = MODEL.encode([c['content'] for c in candidates], convert_to_tensor=True)
        scores = util.cos_sim(anchor_vec, cand_vecs)[0]
        
        for i, score in enumerate(scores):
            results.append({
                "content": candidates[i]['content'],
                "mass": float(score), # Cosine similarity as mass (0.0 to 1.0)
                "source": candidates[i]['source']
            })
    else:
        # Keyword-based Gravity (Fallback for i5/No GPU)
        anchor_words = set(w.lower() for w in anchor_text.split() if len(w) > 4)
        for cand in candidates:
            c_words = set(w.lower() for w in cand['content'].split() if len(w) > 4)
            if not anchor_words:
                mass = 0.0
            else:
                overlap = len(anchor_words.intersection(c_words))
                mass = overlap / len(anchor_words) # Density ratio
            
            results.append({
                "content": cand['content'],
                "mass": mass,
                "source": cand['source']
            })

    # Sort by Mass (Heaviest first)
    results.sort(key=lambda x: x['mass'], reverse=True)
    return results

def apply_gravity(run_dir: Path, query_text: str):
    print("--- GRAVITY WELL: Warping Semantic Space ---")
    
    # 1. Harvest candidates from recent history
    candidates = []
    for f in sorted(run_dir.glob("round*_agent*.md"), reverse=True)[:10]:
        try:
            candidates.append({
                "content": f.read_text(encoding='utf-8', errors='ignore')[:2000],
                "source": f.name
            })
        except: pass

    # 2. Calculate Mass
    results = calculate_semantic_mass(query_text, candidates)
    
    # 3. Form the Core (Top 3 Densest Memories)
    core = results[:3]
    
    # 4. Output the Event Horizon
    out_path = run_dir / "state" / "gravity_well_core.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    md = [f"# Gravity Well Core (Query: {query_text[:50]}...)"]
    for item in core:
        if item['mass'] > 0.25: # Event Horizon Threshold
            md.append(f"## Mass: {item['mass']:.4f} | Source: {item['source']}")
            md.append(item['content'])
            md.append("\n---\n")
            print(f" -> Captured {item['source']} (Mass: {item['mass']:.2f})")
    
    out_path.write_text("\n".join(md), encoding='utf-8')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    apply_gravity(Path(args.run_dir), args.query)
