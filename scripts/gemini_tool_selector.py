import argparse
import json
import pathlib
import re

GEMINI_DIR = pathlib.Path(r"C:\Users\codym\.Gemini")
INVENTORY_PATH = GEMINI_DIR / "inventory.md"
CONFIG_LOCAL = GEMINI_DIR / "config.local.toml"
DISABLED_CONFIGS = list(GEMINI_DIR.glob("config*.toml.mcp.disabled"))
SKILLS_DIR = GEMINI_DIR / "skills"
PRESETS_PATH = GEMINI_DIR / "presets.json"

KEYWORD_MAP = {
    "code": ["filesystem", "shell", "shell-exec", "git"],
    "repo": ["git", "github"],
    "github": ["github", "git"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes"],
    "db": ["postgres", "sqlite"],
    "database": ["postgres", "sqlite"],
    "sql": ["postgres", "sqlite"],
    "browser": ["playwright", "browser-use", "chrome-devtools"],
    "ui": ["playwright", "browser-use"],
    "test": ["playwright"],
    "playwright": ["playwright"],
    "docs": ["openaiDeveloperDocs", "web-search"],
    "openai": ["openaiDeveloperDocs"],
    "research": ["web-search", "brave-search"],
    "aws": ["aws"],
    "azure": ["azure"],
    "gcp": ["gcp"],
    "cloudflare": ["cloudflare"],
    "vercel": ["vercel"],
    "netlify": ["netlify"],
}

SKILL_KEYWORDS = {
    "playwright": ["playwright"],
    "figma": ["figma", "figma-implement-design"],
    "pdf": ["pdf"],
    "docx": ["doc"],
    "image": ["imagegen"],
    "speech": ["speech"],
    "transcribe": ["transcribe"],
    "spreadsheet": ["spreadsheet"],
    "sentry": ["sentry"],
}


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


def load_skills():
    if not SKILLS_DIR.exists():
        return []
    return sorted({p.parent.name for p in SKILLS_DIR.rglob("SKILL.md")})


def build_inventory():
    skills = load_skills()
    mcp_blocks = load_mcp_blocks()
    mcp_names = sorted(mcp_blocks.keys())
    return skills, mcp_names


def load_inventory_hints():
    if not INVENTORY_PATH.exists():
        return {}, {}
    mcp_hints = {}
    skill_hints = {}
    for raw in INVENTORY_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        line = line[2:].strip()
        if line.lower().startswith("mcp:"):
            # Format: mcp: keyword => a, b, c
            try:
                _, rest = line.split(":", 1)
                key, targets = rest.split("=>", 1)
                keyword = key.strip().lower()
                names = [s.strip() for s in targets.split(",") if s.strip()]
                if keyword and names:
                    mcp_hints[keyword] = names
            except ValueError:
                continue
        if line.lower().startswith("skill:"):
            # Format: skill: keyword => a, b, c
            try:
                _, rest = line.split(":", 1)
                key, targets = rest.split("=>", 1)
                keyword = key.strip().lower()
                names = [s.strip() for s in targets.split(",") if s.strip()]
                if keyword and names:
                    skill_hints[keyword] = names
            except ValueError:
                continue
    return mcp_hints, skill_hints


def recommend(task: str, mcp_names: list[str], skills: list[str]):
    task_l = task.lower()
    rec_mcp = []
    rec_skills = []
    inv_mcp_hints, inv_skill_hints = load_inventory_hints()
    # Merge inventory hints first so they can be used alongside defaults
    for key, mcp_list in inv_mcp_hints.items():
        if key in task_l:
            rec_mcp.extend([m for m in mcp_list if m in mcp_names])
    for key, skill_list in inv_skill_hints.items():
        if key in task_l:
            rec_skills.extend([s for s in skill_list if s in skills])
    for key, mcp_list in KEYWORD_MAP.items():
        if key in task_l:
            rec_mcp.extend([m for m in mcp_list if m in mcp_names])
    for key, skill_list in SKILL_KEYWORDS.items():
        if key in task_l:
            rec_skills.extend([s for s in skill_list if s in skills])
    rec_mcp = sorted(dict.fromkeys(rec_mcp))
    rec_skills = sorted(dict.fromkeys(rec_skills))
    return rec_mcp, rec_skills


def score_presets(task: str, presets: dict, task_rules: dict) -> list[tuple[str, int]]:
    t = task.lower()
    scores = []
    for name in presets.keys():
        score = 0
        for key, preset in task_rules.items():
            if preset == name and key in t:
                score += 3
        # small boost for core keywords in name
        if any(tok in name for tok in t.split()):
            score += 1
        scores.append((name, score))
    scores.sort(key=lambda x: (-x[1], x[0]))
    return scores


def write_config(selected_mcp: list[str], mcp_blocks: dict[str, str]):
    lines = []
    for name in selected_mcp:
        block = mcp_blocks.get(name)
        if block:
            lines.append(block)
            lines.append("")
    CONFIG_LOCAL.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_presets():
    if not PRESETS_PATH.exists():
        return {}, {}, {}
    data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return data.get("globals", {}), data.get("presets", {}), data.get("task_rules", {})


def choose_preset(task: str, task_rules: dict):
    t = task.lower()
    for key, preset in task_rules.items():
        if key in t:
            return preset
    return "core-dev"


def main():
    ap = argparse.ArgumentParser(description="Recommend MCPs/skills and optionally write config.local.toml")
    ap.add_argument("--task", help="Short task description for recommendations")
    ap.add_argument("--list", action="store_true", help="List full inventory")
    ap.add_argument("--apply", action="store_true", help="Write recommended MCPs to config.local.toml")
    ap.add_argument("--no-preset", action="store_true", help="Disable preset selection and use keyword map")
    args = ap.parse_args()

    skills, mcp_names = build_inventory()
    mcp_blocks = load_mcp_blocks()
    globals_cfg, presets, task_rules = load_presets()

    if args.list:
        print("SKILLS:")
        for s in skills:
            print(f"- {s}")
        print("\nMCP CATALOG:")
        for s in mcp_names:
            print(f"- {s}")
        return

    if not args.task:
        print("Provide --task or --list")
        return

    if (not args.no_preset) and presets:
        preset_name = choose_preset(args.task, task_rules)
        preset = presets.get(preset_name, {})
        rec_mcp = (globals_cfg.get("mcps") or []) + (preset.get("mcps") or [])
        rec_skills = (globals_cfg.get("skills") or []) + (preset.get("skills") or [])
        scored = score_presets(args.task, presets, task_rules)
        print(f"RECOMMENDED PRESET: {preset_name}")
        print("PRESET SCORES:")
        for name, score in scored[:5]:
            print(f"- {name}: {score}")
    else:
        rec_mcp, rec_skills = recommend(args.task, mcp_names, skills)
        print("RECOMMENDED MCPs:")

    if args.no_preset or not presets:
        for s in rec_mcp:
            print(f"- {s}")

    print("\nRECOMMENDED SKILLS:")
    for s in rec_skills:
        print(f"- {s}")

    if not rec_mcp:
        print("\nNo MCPs recommended. Nothing to apply.")
        return

    if args.apply:
        write_config(rec_mcp, mcp_blocks)
        print(f"\nWrote {CONFIG_LOCAL}")
    else:
        print("\nRun again with --apply to write config.local.toml")


if __name__ == "__main__":
    main()
