from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# Secret patterns: fail closed.
SECRET_PATTERNS = [
    r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----",
    r"-----BEGIN PRIVATE KEY-----",
    r"\bOPENAI_API_KEY\s*=",
    r"\bGROQ_API_KEY\s*=",
    r"\bANTHROPIC_API_KEY\s*=",
    r"\bGOOGLE_API_KEY\s*=",
    r"\bAWS_ACCESS_KEY_ID\s*=",
    r"\bAWS_SECRET_ACCESS_KEY\s*=",
    r"\bSALES_PASSWORD\s*=",
    r"Authorization:\s*Bearer\s+",
]

# Risky capability markers: warn by default; allow override.
RISK_PATTERNS = [
    r"\.onion\b",
    r"\bTor\b",
    r"socks5://",
    r"\blead[_ -]?gen\b",
    r"\boutreach\b",
    r"\bstealth\b",
]


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Force utf-8 so staged diffs with non-ASCII won't crash on Windows codepages.
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", errors="replace")


def repo_root_from_env_or_file() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def scan_text(text: str) -> dict[str, Any]:
    hits_secret: list[str] = []
    hits_risk: list[str] = []
    for pat in SECRET_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits_secret.append(pat)
    for pat in RISK_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits_risk.append(pat)
    return {"secret_patterns": hits_secret, "risk_patterns": hits_risk}


def staged_paths(repo_root: Path) -> list[str]:
    p = run(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    out: list[str] = []
    for ln in (p.stdout or "").splitlines():
        ln = ln.strip()
        if ln:
            out.append(ln.replace("\\", "/"))
    return out


def read_staged_file(repo_root: Path, rel: str) -> str:
    # Read from index, not the working tree.
    p = run(["git", "show", f":{rel}"], cwd=repo_root)
    return p.stdout or ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan diffs/files for secrets and risky capability markers.")
    ap.add_argument("--repo-root", default="", help="Repo root (defaults to GEMINI_OP_REPO_ROOT or scripts/..)")
    ap.add_argument("--staged", action="store_true", help="Scan staged diff (git diff --cached).")
    ap.add_argument("--paths", nargs="*", default=[], help="Paths to scan (raw file content).")
    ap.add_argument("--format", choices=("json", "text"), default="json")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_env_or_file()
    files_scanned: list[str] = []

    if args.staged:
        files_scanned = staged_paths(repo_root)

    data = ""
    for p in args.paths:
        try:
            pp = Path(p)
            if not pp.is_absolute():
                pp = (repo_root / pp).resolve()
            if not pp.exists() or pp.is_dir():
                continue
            data += "\n" + pp.read_text(encoding="utf-8", errors="ignore")
            files_scanned.append(str(pp))
        except Exception:
            continue

    # For staged scans, scan each staged file content from the index, excluding this scanner.
    if args.staged:
        hits_secret: list[str] = []
        hits_risk: list[str] = []
        for rel in files_scanned:
            if rel == "scripts/scan_risk.py":
                continue
            # Avoid self-triggering on other scanners that necessarily contain secret-marker strings.
            if rel == "scripts/scan_secrets.py":
                continue
            txt = read_staged_file(repo_root, rel)
            resi = scan_text(txt)
            for pat in resi["secret_patterns"]:
                if pat not in hits_secret:
                    hits_secret.append(pat)
            for pat in resi["risk_patterns"]:
                if pat not in hits_risk:
                    hits_risk.append(pat)
        res = {"secret_patterns": hits_secret, "risk_patterns": hits_risk}
    else:
        res = scan_text(data)
    res["files_scanned"] = files_scanned
    has_secrets = bool(res["secret_patterns"])
    has_risk = bool(res["risk_patterns"])

    allow_risk = (os.environ.get("GEMINI_OP_ALLOW_RISKY_CODE") or "").strip().lower() in ("1", "true", "yes")
    ok = (not has_secrets) and ((not has_risk) or allow_risk)

    out = {
        "ok": ok,
        "has_secrets": has_secrets,
        "has_risk": has_risk,
        "allow_risk": allow_risk,
        **res,
    }

    if args.format == "text":
        if has_secrets:
            print("SECRETS: HIT")
            for p in out["secret_patterns"]:
                print(f"- {p}")
        if has_risk:
            print("RISK: HIT")
            for p in out["risk_patterns"]:
                print(f"- {p}")
        print("OK" if ok else "FAIL")
    else:
        print(json.dumps(out, indent=2))

    if has_secrets:
        return 2
    if has_risk and not allow_risk:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
