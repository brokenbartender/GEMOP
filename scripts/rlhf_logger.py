import json
import time
from pathlib import Path
import sys

def log_feedback(run_dir, event_type, feedback_score, context=""):
    repo_root = Path(__file__).resolve().parents[1]
    pref_path = repo_root / "ramshare" / "learning" / "preference_model.json"
    
    # Load existing model
    if pref_path.exists():
        model = json.loads(pref_path.read_text())
    else:
        model = {"style_weights": {}, "interaction_history": []}
    
    # Record event
    entry = {
        "ts": time.time(),
        "run_id": Path(run_dir).name,
        "type": event_type,
        "score": feedback_score,
        "context": context
    }
    model["interaction_history"].append(entry)
    
    # Simple Heuristic Update (Implicit RL)
    # If user approves a specific pattern, boost its weight
    if event_type == "approval" and feedback_score > 0:
        if "verbose" in context: model["style_weights"]["verbosity"] = model["style_weights"].get("verbosity", 0.5) + 0.1
        if "concise" in context: model["style_weights"]["verbosity"] = model["style_weights"].get("verbosity", 0.5) - 0.1
        if "visual" in context: model["style_weights"]["visuals"] = model["style_weights"].get("visuals", 0.5) + 0.1
    
    pref_path.write_text(json.dumps(model, indent=2))
    print(f"[RLHF] Preference Model Updated. Events: {len(model['interaction_history'])}")

if __name__ == "__main__":
    # CLI usage: python rlhf_logger.py <run_dir> <type> <score> [context]
    if len(sys.argv) > 3:
        log_feedback(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4] if len(sys.argv)>4 else "")
