import argparse
import json
import pathlib
import re

GEMINI_DIR = pathlib.Path(r"C:\Users\codym\.Gemini")
PRESETS_PATH = GEMINI_DIR / "presets.json"
CONFIG_LOCAL = GEMINI_DIR / "config.local.toml"
CONFIG_BASE = GEMINI_DIR / "config.base.toml"
CONFIG_ACTIVE = GEMINI_DIR / "config.toml"
DISABLED_CONFIGS = list(GEMINI_DIR.glob("config*.toml.mcp.disabled"))


def load_presets():
    data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return (
        data.get("globals", {}),
        data.get("presets", {}),
        data.get("task_rules", {}),
        data.get("project_rules", {}),
    )


def load_mcp_blocks():
    blocks = {}
    for cfg in DISABLED_CONFIGS:
        text = cfg.read_text(encoding="utf-8", errors="ignore")
        parts = re.split(r"(?=\[mcp_servers\.)", text)
        for part in parts:
            m = re.match(r"\[mcp_servers\.([^\]]+)\]", part)
            if not m:
                continue
            name = m.group(1).strip()
            if name not in blocks:
                blocks[name] = part.strip()
    return blocks


def choose_preset(task: str, task_rules: dict, project_rules: dict, project_path: str | None):
    if not task:
        task = ""
    t = task.lower()
    for key, preset in task_rules.items():
        if key in t:
            return preset
    if project_path:
        try:
            p = pathlib.Path(project_path).resolve()
            p_str = str(p).lower()
            for key, preset in project_rules.items():
                if p_str.startswith(str(pathlib.Path(key)).lower()):
                    return preset
        except Exception:
            pass
    return "core-dev"


def write_config(selected_mcp: list[str], mcp_blocks: dict[str, str]):
    lines = []
    for name in selected_mcp:
        block = mcp_blocks.get(name)
        if block:
            lines.append(block)
            lines.append("")
    CONFIG_LOCAL.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_active_config():
    base = ""
    if CONFIG_BASE.exists():
        base = CONFIG_BASE.read_text(encoding="utf-8", errors="ignore").rstrip()
    local = ""
    if CONFIG_LOCAL.exists():
        local = CONFIG_LOCAL.read_text(encoding="utf-8", errors="ignore").strip()
    merged = base
    if local:
        merged = (base + "\n\n" + local).strip()
    CONFIG_ACTIVE.write_text(merged + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Manage Gemini MCP presets")
    ap.add_argument("--list", action="store_true", help="List presets")
    ap.add_argument("--preset", help="Preset name to apply")
    ap.add_argument("--task", help="Task description to choose a preset")
    ap.add_argument("--project", help="Project path for per-project preset")
    ap.add_argument("--show", action="store_true", help="Show preset contents")
    ap.add_argument("--apply", action="store_true", help="Apply preset to config.local.toml")
    ap.add_argument("--disable", action="store_true", help="Disable all MCPs (clear config.local.toml)")
    ap.add_argument("--confirm", action="store_true", help="Prompt before applying preset")
    ap.add_argument("--auto-disable", action="store_true", help="Disable MCPs after Gemini exits (use with launcher)")
    args = ap.parse_args()

    globals_cfg, presets, task_rules, project_rules = load_presets()
    mcp_blocks = load_mcp_blocks()

    if args.list:
        for name in presets.keys():
            print(name)
        return

    if args.disable:
        CONFIG_LOCAL.write_text("\n", encoding="utf-8")
        write_active_config()
        print(f"Cleared {CONFIG_LOCAL}")
        return

    preset_name = args.preset or choose_preset(args.task or "", task_rules, project_rules, args.project)
    if preset_name not in presets:
        print(f"Unknown preset: {preset_name}")
        return

    preset = presets[preset_name]
    mcps = (globals_cfg.get("mcps") or []) + (preset.get("mcps") or [])
    skills = (globals_cfg.get("skills") or []) + (preset.get("skills") or [])

    print(f"PRESET: {preset_name}")
    if args.show or not args.apply:
        print("MCPs:")
        for s in mcps:
            print(f"- {s}")
        print("Skills:")
        for s in skills:
            print(f"- {s}")

    if args.apply:
        if args.confirm:
            answer = input("Apply this preset to config.local.toml? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled.")
                return
        write_config(mcps, mcp_blocks)
        write_active_config()
        print(f"Applied to {CONFIG_LOCAL}")
    else:
        print("Run with --apply to enable this preset.")


if __name__ == "__main__":
    main()
