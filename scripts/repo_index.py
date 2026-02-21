from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable


DEFAULT_PREFIXES = ("docs/", "scripts/", "config/", "mcp/", "agents/templates/")


def _iter_files(repo_root: Path, prefixes: Iterable[str]) -> list[str]:
    out: list[str] = []
    root = repo_root.resolve()
    for pref in prefixes:
        pref = (pref or "").strip().replace("\\", "/")
        if not pref:
            continue
        base = (root / pref).resolve()
        try:
            base.relative_to(root)
        except Exception:
            continue
        if not base.exists():
            continue
        if base.is_file():
            rel = base.relative_to(root).as_posix()
            out.append(rel)
            continue
        for p in base.rglob("*"):
            try:
                if not p.is_file():
                    continue
            except Exception:
                continue
            try:
                rel = p.resolve().relative_to(root).as_posix()
            except Exception:
                continue
            out.append(rel)
    # Stable de-dupe.
    seen: set[str] = set()
    dedup: list[str] = []
    for p in sorted(out):
        if p in seen:
            continue
        seen.add(p)
        dedup.append(p)
    return dedup


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a repo-local file index for grounding (allowed edit surface).")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", default="")
    ap.add_argument("--max-files", type=int, default=2200)
    ap.add_argument("--prefixes", default=",".join(DEFAULT_PREFIXES))
    args = ap.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    out_md = Path(args.out_md).expanduser().resolve()
    out_json = Path(args.out_json).expanduser().resolve() if args.out_json else None

    prefixes = [p.strip() for p in str(args.prefixes).split(",") if p.strip()]
    if not prefixes:
        prefixes = list(DEFAULT_PREFIXES)

    files = _iter_files(repo_root, prefixes)
    max_files = max(100, min(int(args.max_files or 2200), 20000))
    truncated = len(files) > max_files
    files_out = files[:max_files]

    payload = {
        "ok": True,
        "generated_at": time.time(),
        "repo_root": str(repo_root),
        "prefixes": prefixes,
        "count_total": len(files),
        "count_emitted": len(files_out),
        "truncated": bool(truncated),
        "files": files_out,
    }

    out_md.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append("# Repo File Index (Grounding)")
    md.append("")
    md.append("This is the authoritative list of repo files you may cite as existing.")
    md.append("If a path is not in this list, treat it as non-existent unless you are creating it via a patch.")
    md.append("")
    md.append(f"generated_at: {payload['generated_at']}")
    md.append(f"count_total: {payload['count_total']}")
    md.append(f"count_emitted: {payload['count_emitted']}")
    md.append(f"truncated: {payload['truncated']}")
    md.append("")
    md.append("## Allowed Prefixes")
    md.append("")
    for p in prefixes:
        md.append(f"- `{p}`")
    md.append("")
    md.append("## Files")
    md.append("")
    for f in files_out:
        md.append(f"- `{f}`")
    md.append("")
    out_md.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")

    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "out_md": str(out_md), "count": len(files_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

