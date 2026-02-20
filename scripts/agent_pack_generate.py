from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
PACKS_DIR = REPO_ROOT / "agents" / "packs"


def now_run_id(prefix: str = "pack") -> str:
    return f"{prefix}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_pack(pack_ref: str) -> Path:
    p = Path(pack_ref)
    if p.exists():
        return p.resolve()
    if not pack_ref.endswith(".json"):
        p = PACKS_DIR / f"{pack_ref}.json"
    else:
        p = PACKS_DIR / pack_ref
    if p.exists():
        return p.resolve()
    raise FileNotFoundError(f"Pack not found: {pack_ref}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_vars(raw_vars: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in raw_vars:
        if "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def substitute(template: str, mapping: Dict[str, str]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out


def write_run_agent_script(run_dir: Path, index: int) -> None:
    script = run_dir / f"run-agent{index}.ps1"
    repo = str(REPO_ROOT).replace("\\", "\\\\")
    text = f"""$ErrorActionPreference = 'Stop'
$repo = '{repo}'
$prompt = Join-Path $PSScriptRoot 'prompt{index}.txt'
$roundOut = Join-Path $PSScriptRoot 'round1_agent{index}.md'
$finalOut = Join-Path $PSScriptRoot 'agent{index}.md'
python (Join-Path $repo 'scripts\\agent_runner_v2.py') $prompt $roundOut
if (Test-Path -LiteralPath $roundOut) {{
  Copy-Item -LiteralPath $roundOut -Destination $finalOut -Force
}}
"""
    script.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a runnable .agent-jobs scaffold from an agents pack JSON.")
    ap.add_argument("--pack", required=True, help="Pack id or JSON path.")
    ap.add_argument("--task", default="", help="Mission/task statement.")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--run-dir", default="")
    ap.add_argument("--var", action="append", default=[], help="Template variable override, KEY=VALUE (repeatable).")
    args = ap.parse_args()

    pack_path = resolve_pack(args.pack)
    pack = load_json(pack_path)
    pack_id = str(pack.get("pack_id") or pack_path.stem)

    run_id = str(args.run_id).strip() or now_run_id(prefix=pack_id)
    if str(args.run_dir).strip():
        run_dir = Path(args.run_dir).resolve()
    else:
        run_dir = REPO_ROOT / ".agent-jobs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state").mkdir(parents=True, exist_ok=True)
    (run_dir / "out").mkdir(parents=True, exist_ok=True)

    shared_templates = pack.get("shared_header_templates") or []
    roles = pack.get("roles") or []
    if not isinstance(roles, list) or not roles:
        raise SystemExit("Pack has no roles")

    extra_vars = parse_vars(args.var)
    header_chunks: List[str] = []
    for rel in shared_templates:
        p = REPO_ROOT / str(rel)
        if p.exists():
            header_chunks.append(read_text(p))
    shared_header = "\n\n".join(header_chunks).strip()

    generated = []
    for idx, role in enumerate(roles, start=1):
        role_id = str((role or {}).get("role_id") or f"role_{idx}")
        tpl_rel = str((role or {}).get("template") or "")
        if not tpl_rel:
            continue
        tpl_path = REPO_ROOT / tpl_rel
        if not tpl_path.exists():
            continue
        out_role_dir = run_dir / "out" / role_id
        out_role_dir.mkdir(parents=True, exist_ok=True)

        base_map = {
            "RUN_ID": run_id,
            "ROLE_ID": role_id,
            "OUT_ROLE_DIR": str(out_role_dir).replace("\\", "/"),
            "OUT_SHARED_DIR": str((run_dir / "out" / "shared")).replace("\\", "/"),
            "DATASET_DIR": str((REPO_ROOT / "data").resolve()).replace("\\", "/"),
            "CONCEPT_COUNT": "24",
            "TASK": str(args.task).strip(),
        }
        base_map.update(extra_vars)

        role_body = substitute(read_text(tpl_path), base_map)
        header = substitute(shared_header, base_map) if shared_header else ""
        prompt = []
        if args.task:
            prompt.extend(["[MISSION]", str(args.task).strip(), ""])
        if header:
            prompt.extend([header, ""])
        prompt.append(role_body)
        prompt_text = "\n".join(prompt).strip() + "\n"

        prompt_path = run_dir / f"prompt{idx}.txt"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        write_run_agent_script(run_dir, idx)
        generated.append(
            {
                "agent_index": idx,
                "role_id": role_id,
                "template": tpl_rel,
                "prompt_path": str(prompt_path),
            }
        )

    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "pack_id": pack_id,
        "pack_path": str(pack_path),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "task": str(args.task),
        "agents": generated,
    }
    (run_dir / "state" / "pack_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
