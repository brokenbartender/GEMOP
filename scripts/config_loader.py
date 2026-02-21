import yaml
from pathlib import Path

def load_config():
    """Loads the unified ecosystem_state.yaml."""
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "ecosystem_state.yaml"
    
    if not config_path.exists():
        return {}
        
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

if __name__ == "__main__":
    import json
    print(json.dumps(load_config(), indent=2))
