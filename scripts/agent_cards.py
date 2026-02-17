from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _read_json(path: Path) -> dict | None:
    try:
        if not path.exists():
            return None
    except Exception:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(errors="ignore"))
        except Exception:
            return None


def _extract_role_name(prompt: str) -> str:
    s = str(prompt or "")
    try:
        i = s.find("[ROLE]")
        if i >= 0:
            rest = s[i + len("[ROLE]") :]
            line = rest.splitlines()[0].strip()
            if line:
                return line
    except Exception:
        pass
    try:
        m = re.search(r"(?mi)^role\s*:\s*(.+?)\s*$", s)
        if m:
            role = (m.group(1) or "").strip()
            if role:
                return role
    except Exception:
        pass
    return "general"


def _service_router_tier(sr: dict | None, role_name: str) -> Tuple[str | None, List[str]]:
    if not isinstance(sr, dict):
        return None, []
    roles = sr.get("roles")
    if not isinstance(roles, dict):
        return None, []

    rn = str(role_name or "").strip()
    cfg = roles.get(rn)
    if cfg is None:
        low = rn.lower()
        for k, v in roles.items():
            try:
                if str(k).lower() == low:
                    cfg = v
                    break
            except Exception:
                continue

    if isinstance(cfg, dict):
        tier = str(cfg.get("tier") or "").strip().lower()
        providers = cfg.get("providers")
        prov_list: List[str] = []
        if isinstance(providers, list):
            for p in providers:
                try:
                    s = str(p).strip()
                    if s:
                        prov_list.append(s)
                except Exception:
                    continue
        if tier in ("local", "cloud"):
            return tier, prov_list

    fb = sr.get("fallback")
    if isinstance(fb, dict):
        tier = str(fb.get("tier") or "").strip().lower()
        if tier in ("local", "cloud"):
            return tier, []
    return None, []


def _skills_selected_names(payload: dict | None) -> List[str]:
    if not isinstance(payload, dict):
        return []
    sel = payload.get("selected")
    if not isinstance(sel, list):
        return []
    out: List[str] = []
    for row in sel:
        if isinstance(row, dict):
            nm = str(row.get("name") or "").strip()
        else:
            nm = str(row or "").strip()
        if nm:
            out.append(nm)
    # stable order, unique
    seen: set[str] = set()
    uniq: List[str] = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate A2A-style Agent Cards for a run directory.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=0)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(state_dir / "manifest.json") or {}
    sr = manifest.get("service_router") if isinstance(manifest, dict) else None
    sr_source = str(state_dir / "manifest.json") if sr else ""

    tool_registry = _read_json(state_dir / "tool_registry.json") or {}
    tools = tool_registry.get("tools") if isinstance(tool_registry, dict) else None
    tool_ids: List[str] = []
    if isinstance(tools, list):
        for t in tools:
            if isinstance(t, dict):
                tid = str(t.get("id") or "").strip()
                if tid:
                    tool_ids.append(tid)

    skills = _skills_selected_names(_read_json(state_dir / "skills_selected.json"))

    # Prompts are prompt{agent_id}.txt in the run dir.
    cards: List[Dict[str, Any]] = []
    for p in sorted(run_dir.glob("prompt*.txt")):
        m = re.search(r"prompt(\d+)\.txt$", p.name, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            agent_id = int(m.group(1))
        except Exception:
            continue
        try:
            prompt = p.read_text(encoding="utf-8")
        except Exception:
            try:
                prompt = p.read_text(errors="ignore")
            except Exception:
                prompt = ""
        role = _extract_role_name(prompt)
        tier, prov = _service_router_tier(sr if isinstance(sr, dict) else None, role)
        cards.append(
            {
                "agent_id": agent_id,
                "role": role,
                "prompt_path": str(p),
                "service_router": {
                    "tier": tier,
                    "providers": prov,
                    "source": sr_source,
                },
                "advertised": {
                    "tools": tool_ids,
                    "skills": skills,
                },
            }
        )

    payload: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at": time.time(),
        "repo_root": str(repo_root),
        "run_dir": str(run_dir),
        "round": int(args.round or 0),
        "cards": cards,
    }

    # Stable outputs (latest) + per-round snapshot when round is provided.
    (state_dir / "agent_cards.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if int(args.round or 0) > 0:
        (state_dir / f"agent_cards_round{int(args.round)}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md: List[str] = ["# Agent Cards", ""]
    md.append(f"generated_at: {payload['generated_at']}")
    md.append(f"round: {payload['round']}")
    md.append("")
    for c in sorted(cards, key=lambda x: int(x.get("agent_id") or 0)):
        md.append(f"- agent_id: {c.get('agent_id')}")
        md.append(f"  role: {c.get('role')}")
        md.append(f"  service_router_tier: {((c.get('service_router') or {}) if isinstance(c.get('service_router'), dict) else {}).get('tier')}")
        if skills:
            md.append(f"  skills: {', '.join(skills)}")
    (state_dir / "agent_cards.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    if int(args.round or 0) > 0:
        (state_dir / f"agent_cards_round{int(args.round)}.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "agent_cards": str(state_dir / "agent_cards.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

