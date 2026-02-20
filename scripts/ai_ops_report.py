import json
import os
import datetime as dt
from pathlib import Path
from collections import Counter

def generate_report():
    repo_root = Path(__file__).resolve().parents[1]
    jobs_dir = repo_root / ".agent-jobs"
    
    total_turns = 0
    cache_hits = 0
    tier_usage = Counter()
    model_usage = Counter()
    total_duration = 0.0
    estimated_human_minutes_saved = 0.0
    
    print("\n" + "="*40)
    print("      GEMINI OP: AI OPS & ROI REPORT")
    print("="*40)
    
    # Analyze all recent metrics
    for metrics_file in jobs_dir.glob("**/state/agent_metrics.jsonl"):
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    total_turns += 1
                    
                    # ROI Estimation: 
                    # Routine turn = 5 min saved, 
                    # Implementation/Architect turn = 15 min saved
                    # Cache hit = 2 min saved (redundancy avoidance)
                    if data.get("cached"):
                        cache_hits += 1
                        estimated_human_minutes_saved += 2
                    else:
                        role = data.get("role", "").lower()
                        if any(r in role for r in ["architect", "engineer", "operator"]):
                            estimated_human_minutes_saved += 15
                        else:
                            estimated_human_minutes_saved += 5
                    
                    tier_usage[data.get("tier", "unknown")] += 1
                    model_usage[data.get("model", "unknown")] += 1
                    total_duration += data.get("duration_s") or 0
        except: continue

    if total_turns == 0:
        print("No metrics found. Run some agents first!")
        return

    hit_rate = (cache_hits / total_turns) * 100
    hours_saved = estimated_human_minutes_saved / 60.0
    
    print(f"\n[VALUE REALIZATION / ROI]")
    print(f"- Est. Human Time Saved: {hours_saved:.1f} hours")
    print(f"- Avg Saved per Turn:   {estimated_human_minutes_saved/total_turns:.1f} min")
    print(f"- Productivity Boost:   {((estimated_human_minutes_saved*60)/max(1, total_duration)):.1f}x vs Manual")

    print(f"\n[OVERALL EFFICIENCY]")
    print(f"- Total Agent Turns: {total_turns}")
    print(f"- Cache Hit Rate:    {hit_rate:.1f}% (Tokens Saved)")
    print(f"- Avg Turn Latency:  {total_duration/total_turns:.2f}s")

    print(f"\n[TIER DISTRIBUTION]")
    for tier, count in tier_usage.most_common():
        pct = (count / total_turns) * 100
        print(f"- {tier.upper():<10}: {count} turns ({pct:.1f}%)")

    print(f"\n[MODEL USAGE]")
    for model, count in model_usage.most_common(5):
        print(f"- {model:<25}: {count} calls")

    print("\n" + "="*40)

if __name__ == "__main__":
    generate_report()
