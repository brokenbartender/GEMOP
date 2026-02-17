from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# This scanner is intentionally conservative: it aims to prevent accidental
# commits of credentials and private keys. It is not a substitute for gitleaks.

SECRET_PATTERNS = [
    # Private keys
    r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----",
    r"-----BEGIN PRIVATE KEY-----",
    # GitHub tokens
    r"\bghp_[A-Za-z0-9]{36}\b",
    r"\bgho_[A-Za-z0-9]{36}\b",
    r"\bghu_[A-Za-z0-9]{36}\b",
    r"\bghs_[A-Za-z0-9]{36}\b",
    r"\bghr_[A-Za-z0-9]{36}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    # Google API keys / OAuth
    r"\bAIzaSy[A-Za-z0-9_\-]{30,}\b",
    r"\bya29\.[A-Za-z0-9_\-]+\b",
    # AWS keys (best-effort)
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bASIA[0-9A-Z]{16}\b",
    r"\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{30,}['\"]?",
    # Slack tokens
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
    # OpenAI-style keys (best-effort; avoid too many false positives)
    r"\bsk-[A-Za-z0-9]{20,}\b",
    # Generic Bearer tokens in headers
    r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.=]{20,}",
]


SERVICE_ACCOUNT_HINTS = [
    r"\"type\"\s*:\s*\"service_account\"",
    r"\"private_key\"\s*:\s*\"-----BEGIN PRIVATE KEY-----",
    r"\"client_email\"\s*:\s*\"[^\"]+@[^\\s\"]+\"",
]


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", errors="replace")


def repo_root_from_env_or_file() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def looks_binary(b: bytes) -> bool:
    # Heuristic: NUL byte = likely binary.
    return b"\x00" in b[:4096]


def scan_text(text: str) -> dict[str, Any]:
    hits: list[str] = []
    for pat in SECRET_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits.append(pat)

    # Service account JSON: treat as a high-signal secret even if no token regex matches.
    sa_hits: list[str] = []
    for pat in SERVICE_ACCOUNT_HINTS:
        if re.search(pat, text, flags=re.IGNORECASE):
            sa_hits.append(pat)
    if len(sa_hits) >= 2:
        hits.append("service_account_json")

    return {"secret_patterns": sorted(set(hits))}


def staged_paths(repo_root: Path) -> list[str]:
    p = run(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    out: list[str] = []
    for ln in (p.stdout or "").splitlines():
        ln = ln.strip()
        if ln:
            out.append(ln.replace("\\", "/"))
    return out


def read_staged_bytes(repo_root: Path, rel: str) -> bytes:
    p = subprocess.run(["git", "show", f":{rel}"], cwd=str(repo_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout or b""


def scan_paths(repo_root: Path, paths: list[str]) -> tuple[list[str], dict[str, Any]]:
    files_scanned: list[str] = []
    agg_hits: set[str] = set()

    for p in paths:
        try:
            pp = Path(p)
            if not pp.is_absolute():
                pp = (repo_root / pp).resolve()
            if not pp.exists() or pp.is_dir():
                continue
            b = pp.read_bytes()
            if looks_binary(b):
                continue
            txt = b.decode("utf-8", errors="ignore")
            res = scan_text(txt)
            for pat in res["secret_patterns"]:
                agg_hits.add(pat)
            files_scanned.append(str(pp))
        except Exception:
            continue

    return files_scanned, {"secret_patterns": sorted(agg_hits)}


def scan_diff(repo_root: Path, *, staged: bool) -> dict[str, Any]:
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    p = run(cmd, cwd=repo_root)
    return scan_text(p.stdout or "")


def scan_diff_range(repo_root: Path, rev_range: str) -> dict[str, Any]:
    rr = (rev_range or "").strip()
    if not rr:
        return {"secret_patterns": []}
    p = run(["git", "diff", rr], cwd=repo_root)
    return scan_text(p.stdout or "")


def upstream_rev(repo_root: Path) -> str:
    try:
        p = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=repo_root)
        s = (p.stdout or "").strip()
        return s
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan for likely secrets (fail closed by default).")
    ap.add_argument("--repo-root", default="", help="Repo root (defaults to GEMINI_OP_REPO_ROOT or scripts/..)")
    ap.add_argument("--staged", action="store_true", help="Scan staged file contents from the git index.")
    ap.add_argument("--diff", action="store_true", help="Scan git diff output (useful after auto-apply).")
    ap.add_argument("--diff-staged", action="store_true", help="Scan staged git diff output.")
    ap.add_argument("--diff-range", default="", help="Scan git diff over a rev range (e.g., origin/main..HEAD).")
    ap.add_argument("--against-upstream", action="store_true", help="Scan git diff from upstream to HEAD (best-effort).")
    ap.add_argument("--paths", nargs="*", default=[], help="Paths to scan from the working tree.")
    ap.add_argument("--format", choices=("json", "text"), default="json")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_env_or_file()

    allow = (os.environ.get("GEMINI_OP_ALLOW_SECRETS") or "").strip().lower() in ("1", "true", "yes")

    files_scanned: list[str] = []
    hits: set[str] = set()

    if args.diff:
        res = scan_diff(repo_root, staged=False)
        hits.update(res["secret_patterns"])
        files_scanned.append("git diff")

    if args.diff_staged:
        res = scan_diff(repo_root, staged=True)
        hits.update(res["secret_patterns"])
        files_scanned.append("git diff --cached")

    if args.diff_range:
        res = scan_diff_range(repo_root, args.diff_range)
        hits.update(res["secret_patterns"])
        files_scanned.append(f"git diff {args.diff_range}")

    if args.against_upstream:
        up = upstream_rev(repo_root)
        if up:
            rr = f"{up}..HEAD"
            res = scan_diff_range(repo_root, rr)
            hits.update(res["secret_patterns"])
            files_scanned.append(f"git diff {rr}")
        else:
            files_scanned.append("upstream: none")

    if args.paths:
        f2, res2 = scan_paths(repo_root, args.paths)
        files_scanned += f2
        hits.update(res2["secret_patterns"])

    if args.staged:
        rels = staged_paths(repo_root)
        for rel in rels:
            # Don't self-trigger on this file.
            reln = rel.replace("\\", "/")
            if reln in ("scripts/scan_secrets.py", "scripts/scan_risk.py"):
                continue
            b = read_staged_bytes(repo_root, rel)
            if looks_binary(b):
                continue
            txt = b.decode("utf-8", errors="ignore")
            res = scan_text(txt)
            hits.update(res["secret_patterns"])
        files_scanned += rels

    out = {
        "ok": (len(hits) == 0) or allow,
        "allow_secrets": allow,
        "files_scanned": files_scanned,
        "secret_patterns": sorted(hits),
    }

    if args.format == "text":
        if out["secret_patterns"]:
            print("SECRETS: HIT")
            for p in out["secret_patterns"]:
                print(f"- {p}")
        print("OK" if out["ok"] else "FAIL")
    else:
        print(json.dumps(out, indent=2))

    if out["secret_patterns"] and not allow:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
