from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
GEMINI_DIR = Path.home() / ".Gemini"
CONFIG_TOML = GEMINI_DIR / "config.toml"
CONFIG_LOCAL = GEMINI_DIR / "config.local.toml"
DISABLED_CONFIGS = list(GEMINI_DIR.glob("config*.toml.mcp.disabled"))


@dataclass
class Request:
    kind: str
    name: str
    reason: str
    source: str


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def list_local_skills() -> List[str]:
    skills_dir = GEMINI_DIR / "skills"
    if not skills_dir.exists():
        return []
    names = {p.parent.name for p in skills_dir.rglob("SKILL.md")}
    return sorted(names)


def load_mcp_blocks() -> Dict[str, str]:
    blocks: Dict[str, str] = {}
    cfgs = [p for p in [CONFIG_TOML, CONFIG_LOCAL] if p.exists()] + DISABLED_CONFIGS
    for cfg in cfgs:
        text = cfg.read_text(encoding="utf-8", errors="ignore")
        parts = re.split(r"(?=\[mcp_servers\.)", text)
        for part in parts:
            m = re.match(r"\[mcp_servers\.([^\]]+)\]", part)
            if not m:
                continue
            name = m.group(1).strip()
            if name and name not in blocks:
                blocks[name] = part.strip()
    return blocks


def parse_enabled_mcps(path: Path) -> List[str]:
    if not path.exists():
        return []
    names: List[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r"^\[mcp_servers\.([^\]]+)\]", text, flags=re.M):
        names.append(m.group(1).strip())
    return sorted(dict.fromkeys([n for n in names if n]))


def ensure_local_mcp_enabled(name: str, blocks: Dict[str, str]) -> Tuple[bool, str]:
    if name not in blocks:
        return False, "mcp_not_in_catalog"
    existing = CONFIG_LOCAL.read_text(encoding="utf-8", errors="ignore") if CONFIG_LOCAL.exists() else ""
    if re.search(rf"^\[mcp_servers\.{re.escape(name)}\]", existing, flags=re.M):
        return True, "already_enabled"
    new_text = existing.rstrip() + ("\n\n" if existing.strip() else "") + blocks[name].rstrip() + "\n"
    CONFIG_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_LOCAL.write_text(new_text, encoding="utf-8")
    return True, "enabled_in_config_local"


def parse_requests_from_agent_md(path: Path) -> List[Request]:
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except Exception:
        txt = raw.decode("utf-16", errors="ignore")
    txt = txt.replace("\x00", "")
    out: List[Request] = []

    # Bullet format:
    # - mcp: playwright | reason: browser automation
    # - skill: pdf
    # - tool: gh
    for ln in txt.splitlines():
        m = re.match(
            r"^\s*[-*]\s*(skill|mcp|tool)\s*[:=]\s*([A-Za-z0-9._/\-]+)(?:\s*\|\s*reason\s*:\s*(.+))?\s*$",
            ln.strip(),
            flags=re.I,
        )
        if m:
            out.append(
                Request(
                    kind=m.group(1).lower(),
                    name=_clean(m.group(2).lower()),
                    reason=_clean(m.group(3) or ""),
                    source=path.name,
                )
            )

    # Inline tags: [mcp:playwright], [skill:pdf], [tool:gh]
    for kind, name in re.findall(r"\[(skill|mcp|tool)\s*:\s*([A-Za-z0-9._/\-]+)\]", txt, flags=re.I):
        out.append(Request(kind=kind.lower(), name=_clean(name.lower()), reason="", source=path.name))

    return out


def collect_requests(run_dir: Path) -> List[Request]:
    reqs: List[Request] = []
    for p in sorted(run_dir.glob("agent*.md")):
        reqs.extend(parse_requests_from_agent_md(p))
    # Deduplicate by (kind,name)
    seen = set()
    uniq: List[Request] = []
    for r in reqs:
        k = (r.kind, r.name)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def classify_and_apply(
    requests: List[Request],
    auto_apply_mcp: bool,
    max_items: int,
) -> Dict[str, object]:
    skills = set(list_local_skills())
    mcp_blocks = load_mcp_blocks()
    mcp_catalog = set(mcp_blocks.keys())
    enabled_before = set(parse_enabled_mcps(CONFIG_TOML) + parse_enabled_mcps(CONFIG_LOCAL))
    enabled_now = set(enabled_before)

    resolved: List[Dict[str, object]] = []
    new_acquired: List[Dict[str, object]] = []
    failures: List[Dict[str, object]] = []

    for req in requests[: max(1, max_items)]:
        row: Dict[str, object] = {
            "kind": req.kind,
            "name": req.name,
            "reason": req.reason,
            "source": req.source,
            "status": "unknown",
            "detail": "",
            "verified": False,
        }
        if req.kind == "skill":
            if req.name in skills:
                row["status"] = "available"
                row["detail"] = "skill_present"
                row["verified"] = True
            else:
                row["status"] = "missing"
                row["detail"] = "skill_not_installed"
                failures.append(dict(row))
        elif req.kind == "tool":
            cmd = shutil.which(req.name)
            if cmd:
                row["status"] = "available"
                row["detail"] = f"tool_path={cmd}"
                row["verified"] = True
            else:
                row["status"] = "missing"
                row["detail"] = "tool_not_found_in_path"
                failures.append(dict(row))
        elif req.kind == "mcp":
            if req.name not in mcp_catalog:
                row["status"] = "missing"
                row["detail"] = "mcp_not_in_disabled_catalog"
                failures.append(dict(row))
            else:
                if req.name in enabled_now:
                    row["status"] = "enabled"
                    row["detail"] = "already_enabled"
                    row["verified"] = True
                elif auto_apply_mcp:
                    ok, msg = ensure_local_mcp_enabled(req.name, mcp_blocks)
                    if ok:
                        enabled_now.add(req.name)
                        row["status"] = "enabled"
                        row["detail"] = msg
                        row["verified"] = True
                        if req.name not in enabled_before:
                            new_acquired.append({"kind": "mcp", "name": req.name, "source": req.source})
                    else:
                        row["status"] = "failed"
                        row["detail"] = msg
                        failures.append(dict(row))
                else:
                    row["status"] = "available"
                    row["detail"] = "cataloged_not_enabled_auto_apply_off"
                    row["verified"] = True
        else:
            row["status"] = "ignored"
            row["detail"] = "unsupported_kind"
        resolved.append(row)

    enabled_after = sorted(parse_enabled_mcps(CONFIG_TOML) + parse_enabled_mcps(CONFIG_LOCAL))
    return {
        "requests_count": len(requests),
        "resolved": resolved,
        "new_acquired": new_acquired,
        "failures": failures,
        "enabled_mcp_before": sorted(enabled_before),
        "enabled_mcp_after": sorted(dict.fromkeys(enabled_after)),
        "catalog_sizes": {
            "skills": len(skills),
            "mcp": len(mcp_catalog),
        },
    }


def write_markdown_summary(path: Path, payload: Dict[str, object]) -> None:
    lines: List[str] = []
    lines.append("# Capability Catalog")
    lines.append("")
    lines.append(f"- Requests scanned: {payload.get('requests_count', 0)}")
    lines.append(f"- MCP enabled before: {len(payload.get('enabled_mcp_before', []))}")
    lines.append(f"- MCP enabled after: {len(payload.get('enabled_mcp_after', []))}")
    lines.append("")
    lines.append("## New Capabilities Acquired")
    new_items = payload.get("new_acquired", []) or []
    if not new_items:
        lines.append("- None")
    else:
        for item in new_items:
            lines.append(f"- `{item.get('kind')}` `{item.get('name')}` (source: `{item.get('source')}`)")
    lines.append("")
    lines.append("## Resolution Log")
    lines.append("| Kind | Name | Status | Verified | Detail | Source |")
    lines.append("|---|---|---|---|---|---|")
    for r in payload.get("resolved", []) or []:
        lines.append(
            f"| {r.get('kind','')} | {r.get('name','')} | {r.get('status','')} | "
            f"{str(bool(r.get('verified'))).lower()} | {r.get('detail','')} | {r.get('source','')} |"
        )
    lines.append("")
    lines.append("## Missing/Failed")
    fails = payload.get("failures", []) or []
    if not fails:
        lines.append("- None")
    else:
        for f in fails:
            lines.append(f"- `{f.get('kind')}` `{f.get('name')}`: {f.get('detail')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Resolve/apply/verify capabilities requested by run agents.")
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--auto-apply-mcp", action="store_true", help="Enable requested MCPs in ~/.Gemini/config.local.toml")
    ap.add_argument("--max-items", type=int, default=30)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    reqs = collect_requests(run_dir)
    payload = classify_and_apply(reqs, auto_apply_mcp=args.auto_apply_mcp, max_items=args.max_items)
    payload["run_dir"] = str(run_dir)
    payload["env"] = {
        "GEMINI_dir": str(GEMINI_DIR),
        "user": os.environ.get("USERNAME", ""),
    }

    out_json = run_dir / "capability-catalog.json"
    out_md = run_dir / "capability-catalog.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown_summary(out_md, payload)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
