from pathlib import Path
try:
    from scripts.system_metrics import get_ground_state
except ImportError:
    from system_metrics import get_ground_state
import json
import os

# Find latest god_run
jobs_dir = Path('.agent-jobs')
runs = sorted([d for d in jobs_dir.iterdir() if d.name.startswith('god_run_')], key=os.path.getmtime, reverse=True)
if runs:
    latest = runs[0]
    gs = get_ground_state(latest)
    print(json.dumps({"run": latest.name, "metrics": gs}))
else:
    print("{}")
