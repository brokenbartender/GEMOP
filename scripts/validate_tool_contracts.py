"""
Smoke-check tool contract types and basic schema shape.

This is intentionally lightweight: it should run fast and from any working
directory (Council runs, patch-apply verification, CI, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path


# Ensure repo root is on sys.path even when invoked with a different cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from mcp.tool_contracts import ToolContract

    # Example of a mock tool contract (just to ensure the type is importable and usable).
    example: ToolContract = {
        "name": "web_search",
        "description": "Perform a web search for a query string.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"results": {"type": "array"}},
            "required": ["results"],
            "additionalProperties": True,
        },
        "version": "v1",
    }

    # Minimal runtime checks (TypedDict is not enforced at runtime).
    for k in ("name", "description", "input_schema"):
        if k not in example:
            raise SystemExit(f"missing_key:{k}")
    if example["input_schema"].get("type") != "object":
        raise SystemExit("input_schema_not_object")

    print(f"[ok] tool_contract_smoke name={example['name']} version={example.get('version','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

