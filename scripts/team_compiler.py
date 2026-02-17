from __future__ import annotations

import argparse
import json
import re
from typing import List


DEFAULT_ROLES = [
    "Architect",
    "ResearchLead",
    "Engineer",
    "Tester",
    "Critic",
    "Security",
    "Ops",
    "Docs",
    "Release",
]


def compile_team(prompt: str, *, max_agents: int = 7) -> List[str]:
    s = (prompt or "").lower()

    # Always keep a minimal, strong core.
    roles: List[str] = ["Architect", "Engineer", "Tester", "Critic"]

    if any(k in s for k in ("research", "browse", "web", "docs", "compare", "evaluate", "latest")):
        roles.append("ResearchLead")
    if any(k in s for k in ("security", "threat", "prompt injection", "secrets", "rbac", "auth")):
        roles.append("Security")
    if any(k in s for k in ("deploy", "release", "version", "changelog", "ship")):
        roles.append("Release")
    if any(k in s for k in ("ops", "monitor", "logging", "tracing", "sentry", "metrics")):
        roles.append("Ops")
    if any(k in s for k in ("docs", "readme", "documentation")):
        roles.append("Docs")

    # Dedupe while preserving order.
    out: List[str] = []
    seen = set()
    for r in roles:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)

    # Enforce 3..7 rule.
    out = out[: max(3, min(int(max_agents), 7))]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile a role team (3..7) based on the prompt.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-agents", type=int, default=7)
    args = ap.parse_args()

    roles = compile_team(str(args.prompt), max_agents=int(args.max_agents))
    print(json.dumps({"ok": True, "roles": roles, "agents": len(roles)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

